#!/usr/bin/env python3
"""Standalone Modern Standby execution-state verifier.

This tool intentionally has no SMTP, database, or business-program dependency.
It does not send SC_MONITORPOWER; the operator must turn the display off manually.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import subprocess
import sys
import time
import winsound
from datetime import datetime, timezone
from pathlib import Path

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
HEARTBEAT_SECONDS = 30
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "output" / "modern_standby_test.log"
POWER_REQUESTS_FILE = BASE_DIR / "output" / "modern_standby_power_requests_before_screen_off.txt"

KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL32.SetThreadExecutionState.argtypes = [ctypes.c_uint]
KERNEL32.SetThreadExecutionState.restype = ctypes.c_uint


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def precise_local_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def set_execution_state(flags: int) -> int:
    """Set a persistent execution requirement on this test process main thread."""
    ctypes.set_last_error(0)
    previous = KERNEL32.SetThreadExecutionState(flags)
    error = ctypes.get_last_error()
    if previous == 0 and error:
        raise ctypes.WinError(error)
    return previous


def setup_logging() -> logging.Logger:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("ModernStandbyGuardTest")


def capture_power_requests() -> tuple[bool, str]:
    """Capture the exact pre-screen-off power request report for later audit."""
    try:
        result = subprocess.run(
            ["powercfg", "/requests"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        POWER_REQUESTS_FILE.write_text(f"powercfg /requests failed: {exc}\n", encoding="utf-8")
        return False, str(exc)
    report = (result.stdout or "") + ("\nSTDERR:\n" + result.stderr if result.stderr else "")
    POWER_REQUESTS_FILE.write_text(report, encoding="utf-8")
    return result.returncode == 0, report


def power_request_belongs_to_current_test(report: str) -> tuple[bool, str]:
    """Fail closed because powercfg reports executable images, not process IDs."""
    upper = report.upper()
    system_start = upper.find("SYSTEM:")
    if system_start < 0:
        return False, "SYSTEM section absent"
    section_end = upper.find("DISPLAY:", system_start)
    system_section = report[system_start:section_end if section_end >= 0 else len(report)]
    image_name = Path(sys.executable).name.lower()
    if "[PROCESS]" not in system_section.upper() or image_name not in system_section.lower():
        return False, f"SYSTEM section has no {image_name} process request"

    # powercfg does not expose a PID.  Do not claim this is this test if another
    # Python process could be the source of the identical image request.
    try:
        query = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "ForEach-Object { $_.ProcessId }"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
        pids = {int(value.strip()) for value in query.stdout.splitlines() if value.strip().isdigit()}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return False, f"cannot establish Python process identity: {exc}"
    if pids != {os.getpid()}:
        return False, f"Python process identity is ambiguous: observed PIDs={sorted(pids)}"
    return True, f"SYSTEM request matches {image_name}; sole Python PID={os.getpid()}"


def announce_ready(log: logging.Logger) -> None:
    for _ in range(3):
        try:
            winsound.Beep(880, 180)
        except RuntimeError as exc:
            log.warning("READY beep unavailable: %s", exc)
            break
    print("READY_FOR_SCREEN_OFF — 现在运行 screen_off.vbs", flush=True)
    log.info("READY_FOR_SCREEN_OFF — 现在运行 screen_off.vbs")


def kernel_power_events_since(seconds: int) -> tuple[bool, str]:
    """Return raw Kernel-Power 506/507 evidence from a bounded recent window."""
    xpath = (
        "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] "
        "and (EventID=506 or EventID=507) "
        f"and TimeCreated[timediff(@SystemTime) <= {seconds * 1000}]]]"
    )
    try:
        result = subprocess.run(
            ["wevtutil", "qe", "System", f"/q:{xpath}", "/f:text", "/rd:true"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except OSError as exc:
        return False, f"wevtutil unavailable: {exc}"
    except subprocess.TimeoutExpired:
        return False, "wevtutil timed out"
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "wevtutil query failed").strip()
    return True, result.stdout.strip()


def log_event_verdict(log: logging.Logger, started_monotonic: float) -> None:
    elapsed = int(time.monotonic() - started_monotonic)
    # Include one minute of clock/event-flush tolerance; raw output retains timestamps.
    available, evidence = kernel_power_events_since(elapsed + 60)
    if not available:
        log.error("EVENT_LOG_UNAVAILABLE: cannot verify Kernel-Power 506/507: %s", evidence)
        return
    if evidence:
        log.error("MODERN_STANDBY_NOT_BLOCKED: Kernel-Power 506/507 appeared in the test window.")
        log.error("Event evidence follows; compare its timestamps with TEST_START_UTC: %s", evidence)
        return
    log.warning(
        "BLOCKED_NOT_PROVEN: no Kernel-Power 506/507 found in the test window. "
        "This is not a success claim unless the operator confirms the display was manually off "
        "for the full interval and Event Viewer was queried successfully."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone Modern Standby execution-state test")
    parser.add_argument("--mode", choices=("system", "display"), required=True)
    args = parser.parse_args()

    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    if args.mode == "display":
        flags |= ES_DISPLAY_REQUIRED

    log = setup_logging()
    started_monotonic = time.monotonic()
    log.info("TEST_START local=%s utc=%s mode=%s", now_iso(), utc_iso(), args.mode)
    log.info("SetThreadExecutionState flags=0x%08X", flags)
    log.info("No SMTP, database, SC_MONITORPOWER, or business program is used by this tool.")
    try:
        previous = set_execution_state(flags)
        if previous == 0:
            raise RuntimeError("SetThreadExecutionState returned zero; refusing to arm the test")
        armed_at = precise_local_iso()
        log.info("API_ARMED")
        log.info("armed_at=%s", armed_at)
        log.info("return_value=0x%08X", previous)
        log.info("pid=%s", os.getpid())
        log.info("HEARTBEAT_0 local=%s flags=0x%08X previous_state=0x%08X", armed_at, flags, previous)

        powercfg_ok, requests_report = capture_power_requests()
        request_confirmed, request_detail = (
            power_request_belongs_to_current_test(requests_report) if powercfg_ok else (False, "powercfg /requests failed")
        )
        log.info("powercfg_requests_saved=%s", POWER_REQUESTS_FILE)
        log.info("powercfg_system_request_confirmed=%s detail=%s", request_confirmed, request_detail)
        if not request_confirmed:
            log.error("READY_REFUSED: SYSTEM request was not confirmed for the current test process")
            return 2

        announce_ready(log)
        log.info("Operator action after READY only: run screen_off.vbs, observe for 60 seconds, wake the display, then press Ctrl+C.")
        while True:
            time.sleep(HEARTBEAT_SECONDS)
            # Reassert on the same main thread and record the continuing liveness evidence.
            previous = set_execution_state(flags)
            log.info("HEARTBEAT local=%s flags=0x%08X previous_state=0x%08X", now_iso(), flags, previous)
    except KeyboardInterrupt:
        log.info("TEST_STOP requested local=%s", now_iso())
        return 0
    except Exception as exc:
        log.exception("TEST_ERROR: %s", exc)
        return 1
    finally:
        try:
            set_execution_state(ES_CONTINUOUS)
            log.info("Execution state cleared with ES_CONTINUOUS")
        except Exception as exc:
            log.error("Could not clear execution state: %s", exc)
        log_event_verdict(log, started_monotonic)


if __name__ == "__main__":
    raise SystemExit(main())
