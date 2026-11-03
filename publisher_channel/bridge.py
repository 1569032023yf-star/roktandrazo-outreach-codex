"""RoktDeployBridge - authenticated loopback call bridge for Codex.

- Binds 127.0.0.1 only. Never 0.0.0.0. No internet exposure.
- Bearer token read from Windows Credential Manager (never logged).
- Exposes deploy operations (preflight/apply/status/rollback), scoped release
  registration (register/releases) and read-only production telemetry.
- Every request - including denied ones - is appended to the audit log.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The reviewed U1 helper package lives at the existing channel root, alongside
# releases/, rather than accepting any import location from an HTTP request.
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import executor as ex  # noqa: E402
import prodobs as obs  # noqa: E402

CST = timezone(timedelta(hours=8))
CHANNEL_ROOT = Path(__file__).resolve().parent.parent
INFLIGHT = CHANNEL_ROOT / "state" / "inflight.json"
HEARTBEAT = CHANNEL_ROOT / "state" / "supervisor_heartbeat.json"

AUTH_POST = ("/v1/preflight", "/v1/apply", "/v1/status", "/v1/rollback",
             "/v1/register", "/v1/releases", "/v1/telemetry", "/v1/health",
             "/v1/runtime", "/v1/city", "/v1/provider-audit", "/v1/scheduler",
             "/v1/safe", "/v1/u1-install")
WRITE_OPS = ("/v1/apply", "/v1/rollback", "/v1/register", "/v1/u1-install")
OBS_ROUTES = {"/v1/runtime": "runtime", "/v1/city": "city",
              "/v1/provider-audit": "provider_audit", "/v1/scheduler": "scheduler",
              "/v1/safe": "safe"}


def iso_now() -> str:
    return datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")



# ------------------------------------------------------- credential (CredMan)
class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_ulong), ("Type", ctypes.c_ulong),
        ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
        ("LastWritten", ctypes.c_ulonglong), ("CredentialBlobSize", ctypes.c_ulong),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", ctypes.c_ulong), ("AttributeCount", ctypes.c_ulong),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


def cred_read(target: str) -> str:
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.CredReadW.restype = ctypes.c_long
    adv.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
                              ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
    cred = ctypes.POINTER(CREDENTIALW)()
    if not adv.CredReadW(target, 1, 0, ctypes.byref(cred)):
        raise RuntimeError(f"CredReadW failed err={ctypes.get_last_error()}")
    n = cred.contents.CredentialBlobSize
    blob = ctypes.string_at(cred.contents.CredentialBlob, n)
    ctypes.windll.advapi32.CredFree(cred)
    if b"\x00" in blob:
        token = blob.decode("utf-16-le", "replace").strip("\x00").strip()
    else:
        token = blob.decode("utf-8", "replace").strip()
    if not token:
        raise RuntimeError("empty credential blob")
    return token


def cred_write(target: str, secret: str) -> None:
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    adv.CredWriteW.restype = ctypes.c_long

    class CREDENTIALW_W(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_ulong), ("Type", ctypes.c_ulong),
            ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
            ("LastWritten", ctypes.c_ulonglong), ("CredentialBlobSize", ctypes.c_ulong),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", ctypes.c_ulong), ("AttributeCount", ctypes.c_ulong),
            ("Attributes", ctypes.c_void_p), ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    blob = secret.encode("utf-8")
    cb = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    c = CREDENTIALW_W()
    c.Flags = 0
    c.Type = 1  # CRED_TYPE_GENERIC
    c.TargetName = target
    c.Comment = "rokt-deploy-channel bridge bearer token"
    c.CredentialBlobSize = len(blob)
    c.CredentialBlob = cb
    c.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
    c.AttributeCount = 0
    c.UserName = "rokt-deploy-channel"
    if adv.CredWriteW(ctypes.byref(c), 0) == 0:  # BOOL: nonzero = success
        raise RuntimeError(f"CredWriteW failed err={ctypes.get_last_error()}")


# ------------------------------------------------------------------ handler
class Bridge:
    def __init__(self, cfg: dict, token: str):
        self.cfg = cfg
        self.token = token
        self.token_fp = hashlib.sha256(token.encode()).hexdigest()[:12]
        self.lock = threading.Lock()

    def audit(self, event: dict) -> None:
        with self.lock:
            ex.audit(self.cfg, {"via": "bridge", **event})

    def authorized(self, header: str) -> bool:
        if not header or not header.startswith("Bearer "):
            return False
        presented = header[len("Bearer "):].strip()
        return hmac.compare_digest(presented, self.token)

    # ---- in-flight marker: the supervisor never force-restarts mid-write
    def _read_inflight(self) -> dict:
        try:
            return json.loads(INFLIGHT.read_text(encoding="utf-8"))
        except Exception:
            return {"count": 0, "operations": [], "since": None}

    def _write_inflight(self, d: dict) -> None:
        try:
            INFLIGHT.parent.mkdir(parents=True, exist_ok=True)
            tmp = INFLIGHT.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, INFLIGHT)
        except OSError:
            pass

    def inflight_begin(self, op: str) -> None:
        with self.lock:
            d = self._read_inflight()
            d["count"] = int(d.get("count") or 0) + 1
            d["operations"] = list(d.get("operations") or []) + [{"op": op, "at": iso_now()}]
            d["since"] = d.get("since") or iso_now()
            self._write_inflight(d)

    def inflight_end(self, op: str) -> None:
        with self.lock:
            d = self._read_inflight()
            d["count"] = max(0, int(d.get("count") or 0) - 1)
            ops = list(d.get("operations") or [])
            for i in range(len(ops) - 1, -1, -1):
                if ops[i].get("op") == op:
                    ops.pop(i)
                    break
            d["operations"] = ops
            if d["count"] <= 0:
                d["since"] = None
            self._write_inflight(d)

    def channel_health(self) -> dict:
        import registry
        seal = registry.verify_seal(self.cfg)
        hb = None
        try:
            hb = json.loads(HEARTBEAT.read_text(encoding="utf-8"))
        except Exception:
            pass
        scope = str(self.cfg.get("_paths", {}).get("releases") or
                    (CHANNEL_ROOT / "releases"))
        code = {}
        root = Path(self.cfg["production"]["root"])
        try:
            import json as _j
            paths = _j.loads((Path(scope) / "allowed_scope.json").read_text(encoding="utf-8"))["paths"]
        except Exception:
            paths = ["bd_orchestrator.py"]
        for rel in paths:
            p = root / rel.replace("/", os.sep)
            code[rel] = (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
        return {"ok": True, "channel_id": self.cfg["channel_id"], "bridge_version": "2.1",
                "python": sys.version.split()[0], "pid": os.getpid(),
                "endpoint": "http://%s:%s" % (self.cfg["endpoint"]["host"],
                                              self.cfg["endpoint"]["port"]),
                "test_mode": self.cfg.get("_test_mode", False),
                "operations": [p[len("/v1/"):] for p in AUTH_POST],
                "release_count": len(self.cfg["releases"]),
                "registry_seal": seal, "supervisor": hb,
                "inflight": self._read_inflight(), "production_code_sha256": code,
                "token_fingerprint": self.token_fp, "ts": iso_now()}



def make_handler(bridge: Bridge):
    cfg = bridge.cfg

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "RoktDeployBridge/2.1"

        def log_message(self, fmt, *args):  # silence default stderr logging
            pass

        def _json(self, code: int, payload: dict, started: float, auth_ok, note=""):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Channel-Id", cfg["channel_id"])
            self.end_headers()
            self.wfile.write(body)
            bridge.audit({"path": self.path, "method": self.command,
                          "auth": {True: "granted", False: "denied",
                                   None: "not_applicable"}[auth_ok],
                          "code": code, "ms": round((time.time() - started) * 1000, 1),
                          "note": note})

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 65536:
                raise ex.GateError("EMPTY_OR_OVERSIZE_BODY", str(n))
            raw = self.rfile.read(n)
            try:
                if self.path == "/v1/u1-install":
                    from publisher_channel.install_verifier import parse
                    data = parse(raw)
                else:
                    data = json.loads(raw.decode("utf-8"))
            except Exception:
                raise ex.GateError("INVALID_JSON", "")
            if not isinstance(data, dict):
                raise ex.GateError("BODY_NOT_OBJECT", "")
            return data

        def do_GET(self):
            started = time.time()
            if self.path == "/healthz":
                self._json(200, {"ok": True, "channel_id": cfg["channel_id"],
                                 "bridge_version": "2.1",
                                 "operations": [p[len("/v1/"):] for p in AUTH_POST],
                                 "test_mode": cfg.get("_test_mode", False),
                                 "ts": iso_now()}, started, None, note="healthz")
                return
            self._json(404, {"error": "NOT_FOUND",
                             "note": "authenticated operations are POST /v1/{preflight,apply,"
                                     "status,rollback,register,releases,telemetry,health,runtime,city,provider-audit,scheduler,safe}; "
                                     "no arbitrary command or file surface"}, started, None)

        def do_POST(self):
            started = time.time()
            auth_ok = bridge.authorized(self.headers.get("Authorization") or "")
            if not auth_ok:
                self._json(401, {"error": "UNAUTHORIZED",
                                 "note": "bearer token required; token is stored in Windows "
                                         "Credential Manager, never in chat or Git"},
                           started, False)
                return
            if self.path not in AUTH_POST:
                self._json(404, {"error": "NOT_FOUND",
                                 "note": "unknown endpoint; the channel exposes only the pinned "
                                         "deploy, registration and telemetry operations"},
                           started, True)
                return
            op_name = self.path[len("/v1/"):]
            write_op = self.path in WRITE_OPS
            inflight_started = False
            try:
                data = self._body() if self.path != "/v1/health" else {}
                if self.path == "/v1/u1-install" and data.get('action') == 'status':
                    write_op = False
                if write_op:
                    bridge.inflight_begin(op_name)
                    inflight_started = True
                if self.path == "/v1/u1-install":
                    out = ex.op_u1_install(cfg, data, "bridge")
                    code = 200
                elif self.path == "/v1/preflight":
                    out = ex.op_preflight(cfg, data.get("release_id"), "bridge")
                    code = 200 if out["summary"]["all_pass"] else 409
                elif self.path == "/v1/apply":
                    out = ex.op_apply(cfg, data.get("release_id"), "bridge",
                                      data.get("confirm"))
                    code = 200 if out.get("state") == "applied" else 409
                elif self.path == "/v1/status":
                    out = ex.op_status(cfg, data.get("operation_id"), "bridge")
                    code = 200
                elif self.path == "/v1/rollback":
                    out = ex.op_rollback(cfg, data.get("operation_id"), "bridge")
                    code = 200 if out.get("state") == "rolled_back" else 409
                elif self.path == "/v1/register":
                    out = ex.op_register(cfg, data.get("release_id"), "bridge")
                    code = 200 if out.get("state") in ("registered", "already_registered") else 409
                elif self.path == "/v1/releases":
                    out = ex.op_releases(cfg, "bridge")
                    code = 200
                elif self.path == "/v1/telemetry":
                    out = ex.op_telemetry(cfg, "bridge", write_snapshot=True)
                    code = 200
                elif self.path in OBS_ROUTES:
                    out = obs.dispatch(cfg, OBS_ROUTES[self.path], data or {})
                    out.setdefault("operation", OBS_ROUTES[self.path])
                    out.setdefault("verdict", "ok")
                    code = 200
                else:  # /v1/health
                    out = bridge.channel_health()
                    code = 200
                self._json(code, out, started, True)
            except ex.GateError as e:
                self._json(400, {"error": e.code, "detail": e.detail}, started, True,
                           note=f"gate:{e.code}")
            except ValueError as e:
                # prodobs rejects bad parameters with ValueError; a rejected input is a
                # client error (400), not an internal failure (500).
                msg = str(e)
                code_name = msg.split(":")[0].split(" ")[0] if msg else "BAD_PARAM"
                self._json(400, {"error": code_name or "BAD_PARAM", "detail": msg},
                           started, True, note="param_rejected")
            except Exception as e:  # never leak internals
                self._json(500, {"error": "INTERNAL", "note": "see audit log"},
                           started, True, note=f"internal:{type(e).__name__}")
            finally:
                if inflight_started:
                    bridge.inflight_end(op_name)


    return H


def _emit(payload: dict) -> None:
    """Print without ever crashing when stdout is unavailable (pythonw at logon)."""
    try:
        print(json.dumps(payload), flush=True)
    except Exception:
        pass


def main() -> int:
    cfg = ex.load_config()
    target = cfg["endpoint"]["credential_target"]
    try:
        token = cred_read(target)
    except RuntimeError as e:
        _emit({"error": "CREDENTIAL_MISSING", "detail": str(e),
               "hint": f"provision once with: python bridge.py --init-credential "
                       f"(stores a fresh token under Credential Manager target "
                       f"'{target}')"})
        return 3
    bridge = Bridge(cfg, token)
    host, port = cfg["endpoint"]["host"], cfg["endpoint"]["port"]
    httpd = ThreadingHTTPServer((host, port), make_handler(bridge))
    httpd.daemon_threads = True
    _emit({"status": "LISTENING", "endpoint": f"http://{host}:{port}",
           "channel_id": cfg["channel_id"], "bridge_version": "2.1",
           "operations": [p[len("/v1/"):] for p in AUTH_POST],
           "test_mode": cfg.get("_test_mode", False),
           "credential_target": target, "token_fingerprint": bridge.token_fp,
           "ts": iso_now()})
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    if "--init-credential" in sys.argv:
        import secrets
        cfg = ex.load_config()
        target = cfg["endpoint"]["credential_target"]
        tok = secrets.token_hex(32)
        cred_write(target, tok)
        _emit({"status": "CREDENTIAL_STORED", "credential_target": target,
               "token_length": len(tok),
               "token_fingerprint": hashlib.sha256(tok.encode()).hexdigest()[:12],
               "note": "token value is NOT printed; retrieve locally via CredReadW",
               "ts": iso_now()})
        sys.exit(0)
    sys.exit(main())
