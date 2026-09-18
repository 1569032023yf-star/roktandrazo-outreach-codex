"""Fail-closed guards for this development copy only."""
from __future__ import annotations

import imaplib
import importlib.util
import os
from pathlib import Path
import smtplib
import socket
import subprocess
import sys
import tempfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / ".development-copy"
PRODUCTION_ROOT = Path(r"C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach")
_INSTALLED = False


class DevelopmentSafetyError(RuntimeError):
    """An unsafe side effect was attempted in development."""


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def assert_safe_database_path(value: str | os.PathLike[str]) -> Path | None:
    """Allow memory DBs, this development root and OS temporary files."""
    raw = str(value)
    if raw == ":memory:" or raw.startswith("file::memory:"):
        return None
    if raw.startswith("file:"):
        raw = unquote(raw[5:].split("?", 1)[0])
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    allowed = _within(candidate, ROOT) or _within(candidate, Path(tempfile.gettempdir()))
    if not allowed or _within(candidate, PRODUCTION_ROOT):
        raise DevelopmentSafetyError(f"DEVELOPMENT_DB_PATH_BLOCKED: {candidate}")
    return candidate


def _blocked_transport(*_args, **_kwargs):
    raise DevelopmentSafetyError("DEVELOPMENT_EXTERNAL_TRANSPORT_DISABLED")


def _active_playwright_driver_root() -> Path | None:
    """Return the active interpreter's installed Playwright driver tree only."""
    try:
        spec = importlib.util.find_spec("playwright")
        locations = list(spec.submodule_search_locations or []) if spec else []
        if not locations:
            return None
        driver_root = (Path(locations[0]).resolve() / "driver").resolve()
        return driver_root if driver_root.is_dir() else None
    except (ImportError, OSError, ValueError):
        return None


def _is_active_playwright_driver(command_path: Path) -> bool:
    """Allow only node.exe shipped in the current interpreter's Playwright package."""
    driver_root = _active_playwright_driver_root()
    return bool(
        os.environ.get("ROKT_DEV_CONTROLLED_WEB") == "1"
        and command_path.name.lower() == "node.exe"
        and driver_root
        and _within(command_path, driver_root)
    )


def _subprocess_is_allowed(args, cwd: Path) -> bool:
    """Fail-closed subprocess decision shared by the guard and its regression tests."""
    command = args if isinstance(args, (list, tuple)) else []
    executable = Path(str(command[0])).name.lower() if command else ""
    tokens = {str(part) for part in command[1:]}
    command_path = Path(str(command[0])).resolve() if command else Path()
    python_names = {Path(sys.executable).name.lower(), "python", "python.exe", "python3", "python3.exe"}
    safe_cwd = _within(cwd, ROOT) or _within(cwd, Path(tempfile.gettempdir()))
    safe_python = executable in python_names and not ({"-I", "-S"} & tokens)
    return safe_cwd and (safe_python or _is_active_playwright_driver(command_path))


def _install_transport_guards() -> None:
    original_create_connection = socket.create_connection
    original_connect = socket.socket.connect

    def controlled_web_enabled() -> bool:
        return os.environ.get("ROKT_DEV_CONTROLLED_WEB") == "1"

    def address_allowed(address) -> bool:
        if not isinstance(address, tuple) or len(address) < 2:
            return False
        host, port = str(address[0]).lower(), int(address[1])
        if host in {"127.0.0.1", "::1", "localhost"}:
            return controlled_web_enabled() or os.environ.get("ROKT_DEV_ALLOW_LOOPBACK") == "1"
        return controlled_web_enabled() and port in {80, 443}

    def guarded_create_connection(address, *args, **kwargs):
        if address_allowed(address):
            return original_create_connection(address, *args, **kwargs)
        return _blocked_transport(address, *args, **kwargs)

    def guarded_connect(sock, address):
        if address_allowed(address):
            return original_connect(sock, address)
        return _blocked_transport(sock, address)

    socket.create_connection = guarded_create_connection
    socket.socket.connect = guarded_connect
    smtplib.SMTP = _blocked_transport
    smtplib.SMTP_SSL = _blocked_transport
    imaplib.IMAP4 = _blocked_transport
    imaplib.IMAP4_SSL = _blocked_transport


def _install_process_guard() -> None:
    original_popen = subprocess.Popen

    class GuardedPopen(original_popen):
        def __init__(self, args, *positional, **kwargs):
            cwd = Path(kwargs.get("cwd") or ROOT).resolve()
            if not _subprocess_is_allowed(args, cwd):
                raise DevelopmentSafetyError(f"DEVELOPMENT_SUBPROCESS_BLOCKED: {args!r}")
            child_env = dict(kwargs.get("env") or os.environ)
            child_env["ROKT_DEVELOPMENT_ONLY"] = "1"
            child_env["ROKT_DEV_ROOT"] = str(ROOT)
            kwargs["env"] = child_env
            super().__init__(args, *positional, **kwargs)

    subprocess.Popen = GuardedPopen
    os.system = _blocked_transport


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    if not MARKER.is_file():
        raise DevelopmentSafetyError("DEVELOPMENT_MARKER_MISSING")
    os.environ["ROKT_DEVELOPMENT_ONLY"] = "1"
    os.environ["ROKT_DEV_ROOT"] = str(ROOT)
    os.environ["WORKBUDDY_BD_DB_PATH"] = str(ROOT / "data" / "bd_leads_dev_runtime.db")
    os.environ.update({
        "BD_SMTP_HOST": "127.0.0.1", "BD_SMTP_PORT": "1",
        "BD_SMTP_USER": "AUDIT_DISABLED", "BD_SMTP_PASS": "AUDIT_DISABLED",
        "BD_IMAP_HOST": "127.0.0.1", "BD_IMAP_PORT": "1",
        "BD_IMAP_USER": "AUDIT_DISABLED", "BD_IMAP_PASS": "AUDIT_DISABLED",
        "BD_TEST_MODE": "false", "BD_FROM_EMAIL": "",
    })
    _install_transport_guards()
    _install_process_guard()
    _INSTALLED = True
