"""
BD Execution Host — Windows Service
====================================
Runs as a Windows Service to ensure Delivery Guard, Ops Center, and Poller
start automatically on boot, even before user login.

SERVICE: BDExecutionHost
Startup: Automatic (Delayed Start recommended)
Account: LocalSystem (no user login required)

NEVER calls SMTP. NEVER creates Final Send Plan.
NEVER accesses customer data.

RESPONSIBILITIES:
- 生产调度权威时区：Asia/Shanghai（UTC+8，无 DST）。
- 只调用唯一 Orchestrator（bd_orchestrator.py）执行各 stage；
  不自己选客户、不建邮件、不建 Auth、不调 SMTP。
"""

import os
import sys
import time
import json
import socket
import subprocess
import logging
import win32event
import win32service
import win32serviceutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Constants ──
ASIA_SHANGHAI = timezone(timedelta(hours=8))  # 生产调度权威时区：UTC+8，无 DST
BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = Path(sys.executable).resolve()
# Child scripts run under a real Python interpreter, not the service host
# (pythonservice.exe). In a Windows Service / debug runtime, sys.executable is
# pythonservice.exe, which cannot launch ordinary scripts (exits with code 2).
# Resolve the sibling python.exe so managed child components start correctly.
CHILD_PYTHON_EXE = PYTHON_EXE
if CHILD_PYTHON_EXE.name.lower() == "pythonservice.exe":
    _sibling_python = CHILD_PYTHON_EXE.with_name("python.exe")
    if _sibling_python.is_file():
        CHILD_PYTHON_EXE = _sibling_python
LOG_DIR = BASE_DIR / "output"
LOG_FILE = LOG_DIR / "bd_execution_host.log"
STATUS_FILE = LOG_DIR / "bd_execution_host_status.json"
PID_FILE = LOG_DIR / "bd_execution_host.pid"

SERVICE_NAME = "BDExecutionHost"
SERVICE_DISPLAY_NAME = "RoktAndRazoBDExecutionHost"
SERVICE_DESCRIPTION = (
    "Rokt&Razo BD Production Execution Host — "
    "Auto-starts Delivery Guard, Ops Center, Poller, and scheduled send stages. "
    "Production send authority. No WorkBuddy UI required."
)

# Components to manage
COMPONENTS = {
    "delivery_guard": {
        "script": "bd_delivery_guard.py",
        "args": ["run"],
        "description": "Delivery Guard (power/sleep prevention)",
        "heartbeat": LOG_DIR / "bd_delivery_guard_status.json",
        "heartbeat_max_age": 90,
    },
    "ops_center": {
        "script": "bd_review_server.py",
        "args": ["--port", "8765"],
        "description": "Ops Center (dashboard server)",
        "port": 8765,
    },
    "poller": {
        # MODE_A: the poller (bd_ops_poller.start_poller) is hosted INSIDE the
        # ops_center (bd_review_server.py) process, which calls start_poller() at
        # startup. Its heartbeat thread writes output/bd_ops_poller_status.json.
        # The host therefore must NOT spawn a separate _start_poller_inline.py
        # child (that was a redundant duplicate that produced a false-healthy
        # poller with owned_by_service=False / pid=None). The host only tracks
        # poller as embedded in the host-owned ops_center.
        "embedded_in": "ops_center",
        "heartbeat": LOG_DIR / "bd_ops_poller_status.json",
        "heartbeat_max_age": 150,
    },
}

# ── Send Stage Schedule (Asia/Shanghai) ──
# 生产调度权威时区：Asia/Shanghai（UTC+8，无 DST），无 DST 切换。
# stage 名必须与 bd_orchestrator.py 的 argparse choices 完全一致。
# hour=0 表示次日午夜：post-send 00:10 / end-of-day 00:25 为跨午夜阶段，
# 按次日处理，hour/min 字段天然支持该语义。
SEND_SCHEDULE = [
    {"stage": "inventory",  "hour": 15, "minute": 0,  "script": "bd_orchestrator.py", "args": ["--stage", "inventory", "--live"]},
    {"stage": "pre-send",   "hour": 22, "minute": 30, "script": "bd_orchestrator.py", "args": ["--stage", "pre-send", "--live"]},
    {"stage": "outreach",   "hour": 23, "minute": 0,  "script": "bd_orchestrator.py", "args": ["--stage", "outreach", "--live"]},
    {"stage": "post-send",  "hour": 0,  "minute": 10, "script": "bd_orchestrator.py", "args": ["--stage", "post-send", "--live"]},
    {"stage": "end-of-day", "hour": 0,  "minute": 25, "script": "bd_orchestrator.py", "args": ["--stage", "end-of-day", "--live"]},
]

SEND_SCHEDULE_BOOKMARK_FILE = LOG_DIR / "bd_execution_host_send_bookmark.json"
SEND_POLICY_HASH = "3a7f9c20"  # Policy: weekday_new_outreach_sh2300 (max_new_outreach=40)
CURRENT_SEND_POLICY = {
    "policy_name": "weekday_new_outreach_sh2300",
    "timezone": "Asia/Shanghai",
    "business_days": [0, 1, 2, 3, 4],  # Monday=0
    "max_new_outreach": 40,
    "follow_up_enabled": False,
    "allowed_template_keys": ["retail_distributor_v5_locked", "custom_printing_production_v5_locked"],
    "allowed_template_shas": ["ccb51505", "5893dbc9"],
}

class BDExecutionHost(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.processes = {}
        self._owned = {}
        self._child_log_handles = {}
        self._child_env = None
        self._last_error = None
        self._running = True
        self._started_at = None
        self._last_heartbeat = None
        self._hostname = socket.gethostname()
        self._setup_logging()

    def _setup_logging(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self._log = logging.getLogger("ExecutionHost")

    def _now_iso(self):
        return datetime.now(ASIA_SHANGHAI).isoformat()

    def _load_service_env(self):
        """Load the project .env explicitly; services do not inherit a user shell."""
        env_path = BASE_DIR / ".env"
        child_env = os.environ.copy()
        if not env_path.is_file():
            raise FileNotFoundError(f"Required .env file is missing: {env_path}")
        loaded = 0
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key and value and not value.startswith("__"):
                child_env.setdefault(key, value)
                loaded += 1
        child_env["BD_PROJECT_ROOT"] = str(BASE_DIR)
        # This is the only permitted unattended Poller mode: no DB / Final Send Plan.
        child_env["BD_POLLER_SAFE_UNATTENDED"] = "1"
        self._child_env = child_env
        self._log.info("Loaded .env for service children (%d non-empty entries; values not logged)", loaded)

    @staticmethod
    def _heartbeat_is_fresh(path: Path, max_age_seconds: int) -> bool:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            value = payload.get("last_heartbeat_at")
            if not value:
                return False
            stamp = datetime.fromisoformat(value)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=ASIA_SHANGHAI)
            return (datetime.now(ASIA_SHANGHAI) - stamp.astimezone(ASIA_SHANGHAI)).total_seconds() <= max_age_seconds
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _port_is_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            return False

    def _component_healthy(self, name: str) -> bool:
        comp = COMPONENTS[name]
        if "port" in comp:
            return self._port_is_open(comp["port"])
        if not self._heartbeat_is_fresh(comp["heartbeat"], comp["heartbeat_max_age"]):
            return False
        # Poller health is intentionally DECOUPLED from tracking / open-monitoring
        # (Cloudflare Worker) reachability. A tracking failure is a DEGRADED, non-critical
        # state and must NOT block host startup or mark the poller unhealthy. The only
        # conditions that make the poller unhealthy are a dead process or a missing/stale
        # heartbeat — both enforced above by _heartbeat_is_fresh.
        return True

    def _write_status(self):
        """Write current status to JSON file."""
        now = self._now_iso()
        self._last_heartbeat = now
        comp_status = {}
        for name in COMPONENTS:
            comp = COMPONENTS[name]
            if comp.get("embedded_in"):
                # Embedded components are hosted by a host-owned process.
                # Report them as owned, with the host process's real PID, so the
                # heartbeat file's writer is unambiguously identified.
                host_proc = self.processes.get(comp["embedded_in"])
                healthy = self._component_healthy(name)
                comp_status[name] = {
                    "running": healthy,
                    "pid": host_proc.pid if host_proc else None,
                    "owned_by_service": True,
                    "healthy": healthy,
                    "embedded_in": comp["embedded_in"],
                }
                continue
            proc = self.processes.get(name)
            comp_status[name] = {
                "running": (proc is not None and proc.poll() is None) or self._component_healthy(name),
                "pid": proc.pid if proc else None,
                "owned_by_service": bool(self._owned.get(name)),
                "healthy": self._component_healthy(name),
            }
        status = {
            "service_started_at": self._started_at,
            "last_heartbeat_at": now,
            "hostname": self._hostname,
            "components": comp_status,
            "last_error": self._last_error,
        }
        try:
            STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            self._log.error(f"Status write failed: {e}")

    def _start_component(self, name: str) -> subprocess.Popen | None:
        """Start a managed component process."""
        comp = COMPONENTS[name]
        # Embedded components (e.g. poller) are hosted inside another host-owned
        # component (ops_center) and must NOT be spawned as a separate child.
        # Their lifecycle is owned by that host process; the host only tracks them.
        if comp.get("embedded_in"):
            self._owned[name] = True
            self._log.info(
                "%s: embedded in %s (hosted by a host-owned process); "
                "not spawning a separate child", name, comp["embedded_in"]
            )
            return None
        script_path = BASE_DIR / comp["script"]
        if self._component_healthy(name):
            self._owned[name] = False
            self._log.info("%s: already healthy; not starting a duplicate", name)
            return None
        if not CHILD_PYTHON_EXE.is_file():
            self._last_error = f"Child Python executable not found: {CHILD_PYTHON_EXE}"
            self._log.error(self._last_error)
            return None
        if not script_path.exists():
            self._log.error(f"{name}: script not found at {script_path}")
            return None

        try:
            cmd = [str(CHILD_PYTHON_EXE), str(script_path)] + comp["args"]
            child_log = open(LOG_DIR / f"bd_execution_host_{name}.stdout.log", "a", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                env=self._child_env,
                stdout=child_log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._log.info(f"{name}: started (PID={proc.pid}) — {comp['description']}")
            self._child_log_handles[name] = child_log
            self._owned[name] = True
            return proc
        except Exception as e:
            self._log.error(f"{name}: failed to start — {e}")
            return None

    def _wait_for_component(self, name: str, timeout_seconds: int = 90) -> bool:
        """Wait for a real component health signal, never merely a successful Popen."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline and self._running:
            proc = self.processes.get(name)
            if proc is not None and proc.poll() is not None:
                self._last_error = f"{name}: child exited with code {proc.returncode} before healthy"
                self._log.error(self._last_error)
                return False
            if self._component_healthy(name):
                self._log.info("%s: startup health check passed", name)
                return True
            time.sleep(2)
        self._last_error = f"{name}: startup health check timed out"
        self._log.error(self._last_error)
        return False

    def _stop_component(self, name: str) -> None:
        """Stop a managed component process."""
        proc = self.processes.get(name)
        if proc and self._owned.get(name) and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
                self._log.info(f"{name}: stopped (PID={proc.pid})")
            except subprocess.TimeoutExpired:
                proc.kill()
                self._log.warning(f"{name}: force-killed (PID={proc.pid})")
            except Exception as e:
                self._log.error(f"{name}: stop error — {e}")

        handle = self._child_log_handles.pop(name, None)
        if handle:
            handle.close()

    def _monitor_components(self) -> None:
        """Check component health and restart if needed."""
        for name in COMPONENTS:
            if COMPONENTS[name].get("embedded_in"):
                # Lifecycle is owned by the hosting component (ops_center);
                # the host must never stop/restart an embedded component here.
                continue
            proc = self.processes.get(name)
            if not self._component_healthy(name):
                if proc is not None and proc.poll() is not None:
                    self._log.warning("%s: child exited (code=%s), restarting", name, proc.returncode)
                elif proc is not None and self._owned.get(name):
                    self._log.warning("%s: owned child is unhealthy; stopping before restart", name)
                    self._stop_component(name)
                elif proc is not None:
                    self._last_error = f"{name}: externally started process is unhealthy; refusing duplicate launch"
                    self._log.error(self._last_error)
                    continue
                else:
                    self._log.warning("%s: health check failed, starting/restarting", name)
                self.processes[name] = self._start_component(name)

    def SvcStop(self):
        """Service stop handler."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._log.info("Service stop requested")
        self._running = False
        win32event.SetEvent(self.stop_event)

        # Stop all managed components
        for name in list(self.processes.keys()):
            self._stop_component(name)

        self._log.info("All components stopped")
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        """Main service loop."""
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self._started_at = self._now_iso()
        self._log.info("=" * 60)
        self._log.info(f"BD Execution Host starting (PID={os.getpid()})")
        self._log.info(f"Host: {self._hostname}")
        self._log.info(f"Base dir: {BASE_DIR}")
        self._log.info(f"Python: {PYTHON_EXE}")
        self._log.info(f"Child interpreter: {CHILD_PYTHON_EXE}")
        self._log.info("=" * 60)

        try:
            self._load_service_env()
            data_dir = BASE_DIR / "data"
            if not data_dir.is_dir():
                raise FileNotFoundError(f"Required data directory is missing: {data_dir}")
            next(data_dir.iterdir(), None)  # Explicitly verify directory enumeration access.
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            # The host status file is also an explicit LocalSystem write-permission check.
            PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
            self._log.info("Verified .env read, data directory access, and output write access")
        except Exception as exc:
            self._last_error = f"Service preflight failed: {exc}"
            self._log.error(self._last_error)
            self._write_status()
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return

        # Start each component only once and wait for its heartbeat/listener before proceeding.
        for name in COMPONENTS:
            self.processes[name] = self._start_component(name)
            if not self._wait_for_component(name):
                for started_name in self.processes:
                    self._stop_component(started_name)
                self._write_status()
                self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                return

        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._log.info("Service RUNNING — all components started")

        # Main loop: heartbeat every 30s, health check every 60s
        tick = 0
        while self._running:
            try:
                self._monitor_components()
                self._write_status()

                if tick % 60 == 0:  # Every ~1800s (30 min), full log
                    self._log.info(
                        f"Heartbeat: components={', '.join(f'{n}={p.poll() is None if p else 'dead'}' for n, p in self.processes.items())}"
                    )

                tick += 1
                # Wait with timeout on stop event
                rc = win32event.WaitForSingleObject(self.stop_event, 30000)  # 30s
                if rc == win32event.WAIT_OBJECT_0:
                    break  # Stop event signaled

            except Exception as e:
                self._log.error(f"Main loop error: {e}")
                time.sleep(30)


def _create_poller_script():
    """Create a minimal inline poller starter script for the service."""
    script = BASE_DIR / "_start_poller_inline.py"
    content = '''"""Inline poller starter for BD Execution Host service.
Launches bd_ops_poller in a standalone thread."""
import os, sys, threading
BASE = r"C:\\Users\\15690\\WorkBuddy\\2026-06-05-15-31-42\\roktandrazo-outreach"
sys.path.insert(0, BASE)
os.chdir(BASE)
from bd_ops_poller import start_poller
start_poller(daemon=True)
# Keep alive
import time
while True:
    time.sleep(60)
'''
    script.write_text(content.strip(), encoding="utf-8")
    return script


# ── Install / Uninstall helpers ──

def install_service():
    """Install the Windows Service."""
    python_path = PYTHON_EXE.resolve()
    script_path = Path(__file__).resolve()

    # Use sc.exe to create the service with proper settings
    import subprocess
    bin_path = f'"{python_path}" "{script_path}" run'

    existing = subprocess.run(["sc", "query", SERVICE_NAME], capture_output=True,
                              text=True, encoding="gbk", errors="replace")
    if existing.returncode == 0:
        # Do not delete/recreate a service or kill a PID from a mutable PID file.
        result = subprocess.run([
            "sc", "config", SERVICE_NAME, f"binPath={bin_path}", "start=auto",
            f"DisplayName={SERVICE_DISPLAY_NAME}",
        ], capture_output=True, text=True, encoding="gbk", errors="replace")
    else:
        result = subprocess.run([
            "sc", "create", SERVICE_NAME,
            f"binPath={bin_path}",
            "start=auto",
            "type=own",
            f"DisplayName={SERVICE_DISPLAY_NAME}",
        ], capture_output=True, text=True, encoding="gbk", errors="replace")

    if result.returncode == 0:
        # Configure failure recovery: restart after 1 minute
        subprocess.run([
            "sc", "failure", SERVICE_NAME,
            "reset=86400",
            "actions=restart/60000/restart/60000/restart/60000",
        ], capture_output=True, encoding="gbk", errors="replace")
        subprocess.run(["sc", "failureflag", SERVICE_NAME, "1"], capture_output=True,
                       encoding="gbk", errors="replace")

        print(f"[OK] Service '{SERVICE_DISPLAY_NAME}' installed.")
        print(f"     Startup: Automatic")
        print(f"     Recovery: Restart after 60s on failure")
        print(f"     Start with: sc start {SERVICE_NAME}")
    else:
        print(f"[FAIL] Service install failed: {result.stderr}")


def uninstall_service():
    """Uninstall the Windows Service."""
    import subprocess
    subprocess.run(["sc", "stop", SERVICE_NAME], capture_output=True, encoding="gbk", errors="replace")
    time.sleep(2)
    result = subprocess.run(["sc", "delete", SERVICE_NAME], capture_output=True, text=True, encoding="gbk", errors="replace")
    if result.returncode == 0:
        print(f"[OK] Service '{SERVICE_NAME}' uninstalled.")
    else:
        print(f"[WARN] Uninstall result: {result.stdout} {result.stderr}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BD Execution Host Service")
    parser.add_argument("action", nargs="?", default="run",
                        choices=["install", "uninstall", "start", "stop", "restart", "status", "run"])
    args = parser.parse_args()

    if args.action == "install":
        install_service()
    elif args.action == "uninstall":
        uninstall_service()
    elif args.action == "start":
        win32serviceutil.StartService(SERVICE_NAME)
        print(f"Service '{SERVICE_NAME}' start requested.")
    elif args.action == "stop":
        win32serviceutil.StopService(SERVICE_NAME)
        print(f"Service '{SERVICE_NAME}' stop requested.")
    elif args.action == "restart":
        win32serviceutil.RestartService(SERVICE_NAME)
        print(f"Service '{SERVICE_NAME}' restart requested.")
    elif args.action == "status":
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
        status_map = {
            1: "STOPPED", 2: "START_PENDING", 3: "STOP_PENDING",
            4: "RUNNING", 5: "CONTINUE_PENDING", 6: "PAUSE_PENDING", 7: "PAUSED"
        }
        print(f"Service '{SERVICE_NAME}': {status_map.get(status[1], 'UNKNOWN')}")
    else:
        # Run as service (called by SCM)
        win32serviceutil.HandleCommandLine(BDExecutionHost)
