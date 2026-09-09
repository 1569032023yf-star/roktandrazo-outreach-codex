#!/usr/bin/env python3
"""
BD Delivery Guard — 任务送达优先电源与执行保障系统
====================================================
Prevents Windows Modern Standby from killing scheduled outreach tasks.

Architecture:
  Normal mode  (14:45-00:35 Asia/Shanghai):  ES_CONTINUOUS | ES_SYSTEM_REQUIRED
  Critical mode (22:15-23:20 Asia/Shanghai): ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED

Key constraint: NEVER calls SMTP. NEVER accesses customer data.
"""

from __future__ import annotations

import atexit
import ctypes
import json
import logging
import os
import signal
import socket
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Constants ──────────────────────────────────────────────
# Asia/Shanghai timezone (UTC+8) — NEVER use ASIA_SHANGHAI to avoid confusion with US Central Standard Time
ASIA_SHANGHAI = timezone(timedelta(hours=8))
PID_FILE = Path(__file__).resolve().parent / "output" / "bd_delivery_guard.pid"
LOCK_FILE = Path(__file__).resolve().parent / "output" / "bd_delivery_guard.lock"
LOG_FILE = Path(__file__).resolve().parent / "output" / "bd_delivery_guard.log"
STATUS_FILE = Path(__file__).resolve().parent / "output" / "bd_delivery_guard_status.json"

NORMAL_START_HOUR = 14
NORMAL_START_MIN = 45
NORMAL_END_HOUR = 0
NORMAL_END_MIN = 35
CRITICAL_START_HOUR = 22
CRITICAL_START_MIN = 15
CRITICAL_END_HOUR = 23
CRITICAL_END_MIN = 20

HEARTBEAT_INTERVAL = 30  # seconds
TIME_JUMP_THRESHOLD = 10  # seconds - detect clock jumps

# Windows Execution State flags
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

# ── Windows API ────────────────────────────────────────────
_kernel32 = ctypes.windll.kernel32


def set_thread_execution_state(flags: int) -> int:
    """Set Windows thread execution state to prevent sleep."""
    return _kernel32.SetThreadExecutionState(flags)


def clear_execution_state() -> None:
    """Release all power requests."""
    _kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def get_ac_power_status() -> bool | None:
    """Check if system is on AC power. Returns None if cannot determine."""
    try:
        import ctypes.wintypes
        sps = ctypes.c_byte()
        result = _kernel32.GetSystemPowerStatus(ctypes.byref(sps))
        if result:
            return bool(sps.value)  # ACLineStatus: 1=AC, 0=battery, 255=unknown
    except Exception:
        pass

    # Fallback: check if battery exists
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue).BatteryStatus"],
            capture_output=True, text=True, timeout=5
        )
        status = r.stdout.strip()
        if not status:
            return True  # No battery = desktop, always AC
        return status == "2"  # 2 = AC power
    except Exception:
        pass

    return None


class DeliveryGuard:
    """Core Delivery Guard with single-instance lock, heartbeat, and mode management."""

    def __init__(self):
        self._lock_fd = None
        self._mode = "init"
        self._system_required = False
        self._display_required = False
        self._started_at = None
        self._last_heartbeat = None
        self._last_error = None
        self._restart_count = 0
        self._running = True
        self._setup_logging()

    def _setup_logging(self) -> None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self._log = logging.getLogger("DeliveryGuard")

    def acquire_lock(self) -> bool:
        """Acquire single-instance lock using a file lock."""
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            import msvcrt
            self._lock_fd = open(str(LOCK_FILE), "w")
            msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            return True
        except (IOError, OSError):
            self._log.error("Another Delivery Guard instance is already running (lock held)")
            return False
        except Exception:
            # Fallback: PID file check
            if PID_FILE.exists():
                try:
                    old_pid = int(PID_FILE.read_text().strip())
                    # Check if process still alive
                    handle = _kernel32.OpenProcess(0x0400, False, old_pid)  # PROCESS_QUERY_INFORMATION
                    if handle:
                        _kernel32.CloseHandle(handle)
                        self._log.error(f"Delivery Guard already running (PID {old_pid})")
                        return False
                except (ValueError, OSError):
                    pass  # PID file stale, continue

            PID_FILE.write_text(str(os.getpid()))
            return True

    def release_lock(self) -> None:
        """Release the instance lock."""
        if self._lock_fd:
            try:
                import msvcrt
                msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            self._lock_fd.close()
            self._lock_fd = None
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def _determine_mode(self) -> tuple[str, bool, bool]:
        """Determine current mode based on Asia/Shanghai time."""
        now = datetime.now(ASIA_SHANGHAI)
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()  # 0=Monday

        # Critical window: 22:15-23:20
        in_critical = False
        if hour == 22 and minute >= 15:
            in_critical = True
        elif hour == 23 and minute <= 20:
            in_critical = True

        # Normal window: 14:45-00:35 (next day)
        in_normal = False
        total_minutes = hour * 60 + minute
        normal_start = NORMAL_START_HOUR * 60 + NORMAL_START_MIN  # 885
        normal_end = NORMAL_END_HOUR * 60 + NORMAL_END_MIN  # 35

        if total_minutes >= normal_start or total_minutes <= normal_end:
            in_normal = True

        if in_critical:
            return "critical", True, True
        elif in_normal:
            return "normal", True, False
        else:
            return "idle", False, False

    def _apply_execution_state(self, system_required: bool, display_required: bool) -> None:
        """Apply Windows execution state flags."""
        flags = ES_CONTINUOUS
        if system_required:
            flags |= ES_SYSTEM_REQUIRED
        if display_required:
            flags |= ES_DISPLAY_REQUIRED

        result = set_thread_execution_state(flags)
        self._log.info(
            f"SetThreadExecutionState(0x{flags:08X}) -> 0x{result:08X} "
            f"(system_required={system_required}, display_required={display_required})"
        )

        # If display required, try to reduce brightness to minimum safe level
        if display_required:
            self._dim_display()

    def _dim_display(self) -> None:
        """Reduce display brightness to minimum safe level (not off)."""
        try:
            import subprocess
            # Use WMI to set brightness - minimum safe = 5-10%
            ps_cmd = (
                '(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).'
                'WmiSetBrightness(1, 5)'
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, timeout=5
            )
            self._log.info("Display brightness set to minimum safe level (5)")
        except Exception as e:
            self._log.warning(f"Could not dim display: {e}")

    def _restore_brightness(self) -> None:
        """Restore display brightness to a reasonable level."""
        try:
            import subprocess
            ps_cmd = (
                '(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).'
                'WmiSetBrightness(1, 50)'
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, timeout=5
            )
            self._log.info("Display brightness restored to 50")
        except Exception:
            pass

    def _detect_time_jump(self) -> bool:
        """Detect system clock jumps that could disrupt scheduling."""
        now = time.time()
        if self._last_heartbeat is not None:
            elapsed = now - self._last_heartbeat
            if elapsed > HEARTBEAT_INTERVAL + TIME_JUMP_THRESHOLD:
                self._log.warning(
                    f"Possible time jump detected: {elapsed:.1f}s since last heartbeat "
                    f"(expected ~{HEARTBEAT_INTERVAL}s)"
                )
                return True
            if elapsed < HEARTBEAT_INTERVAL - TIME_JUMP_THRESHOLD:
                self._log.warning(
                    f"Possible negative time jump: {elapsed:.1f}s since last heartbeat"
                )
                return True
        return False

    def _write_status(self) -> None:
        """Write current status to JSON file."""
        now = datetime.now(ASIA_SHANGHAI)
        status = {
            "process_started_at": self._started_at.isoformat() if self._started_at else None,
            "last_heartbeat_at": now.isoformat(),
            "current_mode": self._mode,
            "system_required": self._system_required,
            "display_required": self._display_required,
            "ac_power": get_ac_power_status(),
            "critical_window": self._mode == "critical",
            "last_error": self._last_error,
            "restart_count": self._restart_count,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
        }
        try:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            self._log.error(f"Failed to write status: {e}")

    def run(self) -> None:
        """Main guard loop."""
        if not self.acquire_lock():
            sys.exit(1)

        self._started_at = datetime.now(ASIA_SHANGHAI)
        self._log.info("=" * 60)
        self._log.info("BD Delivery Guard started")
        self._log.info(f"PID: {os.getpid()}")
        self._log.info(f"Normal window: {NORMAL_START_HOUR:02d}:{NORMAL_START_MIN:02d} - "
                       f"{NORMAL_END_HOUR:02d}:{NORMAL_END_MIN:02d} Asia/Shanghai")
        self._log.info(f"Critical window: {CRITICAL_START_HOUR:02d}:{CRITICAL_START_MIN:02d} - "
                       f"{CRITICAL_END_HOUR:02d}:{CRITICAL_END_MIN:02d} Asia/Shanghai")
        self._log.info("=" * 60)

        # Register cleanup
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, lambda s, f: self._signal_handler())
        signal.signal(signal.SIGINT, lambda s, f: self._signal_handler())

        last_mode = None
        last_system_required = None
        last_display_required = None

        try:
            while self._running:
                try:
                    # Determine mode
                    self._mode, self._system_required, self._display_required = self._determine_mode()

                    # Log mode changes
                    if self._mode != last_mode:
                        self._log.info(
                            f"Mode: {last_mode} -> {self._mode} "
                            f"(system_required={self._system_required}, "
                            f"display_required={self._display_required})"
                        )
                        last_mode = self._mode

                    # Apply execution state if changed
                    if (self._system_required != last_system_required or
                            self._display_required != last_display_required):
                        self._apply_execution_state(self._system_required, self._display_required)
                        last_system_required = self._system_required
                        last_display_required = self._display_required

                    # Detect time jumps
                    self._detect_time_jump()

                    # Check AC power
                    ac = get_ac_power_status()
                    if ac is False:
                        self._log.warning("System switched to battery power!")

                    # Update heartbeat and status
                    self._last_heartbeat = time.time()
                    self._write_status()

                    # Log heartbeat at debug level
                    self._log.debug(
                        f"Heartbeat: mode={self._mode}, "
                        f"ac={ac}, "
                        f"system_req={self._system_required}, "
                        f"display_req={self._display_required}"
                    )

                except Exception as e:
                    self._last_error = f"{type(e).__name__}: {e}"
                    self._log.error(f"Guard loop error: {self._last_error}")
                    self._log.debug(traceback.format_exc())

                time.sleep(HEARTBEAT_INTERVAL)

        except KeyboardInterrupt:
            self._log.info("Received interrupt signal")
        finally:
            self.cleanup()

    def _signal_handler(self) -> None:
        """Handle termination signals."""
        self._log.info("Received termination signal")
        self._running = False

    def cleanup(self) -> None:
        """Clean shutdown: release power requests and locks."""
        self._log.info("Cleaning up...")
        clear_execution_state()
        self._restore_brightness()
        self._log.info("Execution state cleared (ES_CONTINUOUS only)")
        self.release_lock()
        self._log.info("BD Delivery Guard stopped")


# ── CLI Entry Point ────────────────────────────────────────

def main():
    """CLI for Delivery Guard."""
    import argparse
    parser = argparse.ArgumentParser(description="BD Delivery Guard")
    parser.add_argument("command", nargs="?", default="run",
                        choices=["run", "status", "stop"])
    args = parser.parse_args()

    if args.command == "status":
        try:
            if STATUS_FILE.exists():
                print(STATUS_FILE.read_text(encoding="utf-8"))
            else:
                print(json.dumps({"error": "No status file found. Guard may not be running."}))
        except Exception as e:
            print(json.dumps({"error": str(e)}))

    elif args.command == "stop":
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to PID {pid}")
            except ProcessLookupError:
                print("Delivery Guard process not found (stale PID file)")
            except Exception as e:
                print(f"Error stopping: {e}")
        else:
            print("No PID file found. Guard may not be running.")

    else:  # run
        guard = DeliveryGuard()
        guard.run()


if __name__ == "__main__":
    main()
