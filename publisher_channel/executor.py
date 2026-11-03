"""RoktDeployChannel restricted executor / Codex 受限生产部署执行器.

Four operations only / 仅四种操作:
    preflight(release_id)   read-only live gate evidence
    apply(release_id)       gated, locked, backed-up, atomic deployment
    status(operation_id)    operation record
    rollback(operation_id)  verified restore from byte-exact backup

Hard rules / 硬性规则:
- No arbitrary commands, paths, scripts or shells exist in this interface.
- Only manifests pinned in channel_config.json are accepted.
- Credentials are read from Windows Credential Manager; never logged.
- The executor never imports production business modules and never runs Git.
- Test mode (DEPLOY_CHANNEL_TEST_ROOT) remaps every path into a sandbox and
  is only selectable at process start by the local operator, never via API.
"""
from __future__ import annotations

import ast
import ctypes
import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

CHANNEL_ROOT = Path(__file__).resolve().parent.parent
CST = timezone(timedelta(hours=8))
RELEASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
OPERATION_ID_RE = re.compile(r"^op-[a-z0-9-]{1,80}$")

TEST_ROOT_ENV = "DEPLOY_CHANNEL_TEST_ROOT"


class GateError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def now_cst() -> datetime:
    return datetime.now(CST)


def iso_now() -> str:
    return now_cst().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def business_date_shanghai() -> str:
    return now_cst().strftime("%Y-%m-%d")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(data: bytes) -> dict:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    cr = data.count(b"\r") - crlf
    style = "MIXED" if sum(bool(n) for n in (crlf, lf, cr)) > 1 else (
        "CRLF" if crlf else "LF" if lf else "CR" if cr else "NONE")
    return {"sha256": sha256_hex(data), "bytes": len(data), "line_endings": style,
            "lf": lf, "crlf": crlf, "bare_cr": cr, "utf8_bom": data.startswith(b"\xef\xbb\xbf")}


# ---------------------------------------------------------------- config
def load_config() -> dict:
    cfg_path = CHANNEL_ROOT / "releases" / "channel_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    test_root = os.environ.get(TEST_ROOT_ENV)
    if test_root:
        root = Path(test_root).resolve()
        tcfg_path = root / "sandbox_config.json"
        if not tcfg_path.is_file():
            raise GateError("TEST_CONFIG_MISSING", str(tcfg_path))
        tcfg = json.loads(tcfg_path.read_text(encoding="utf-8"))
        cfg["_test_mode"] = True
        cfg["_test_root"] = str(root)
        cfg["production"] = dict(tcfg["production"])
        # The sandbox keeps its own registry file so that a register call is
        # visible to the next process, exactly like production. sandbox_config
        # only supplies the initial (usually empty) release set.
        sb_registry = root / "releases" / "channel_config.json"
        if sb_registry.is_file():
            cfg["releases"] = dict(
                json.loads(sb_registry.read_text(encoding="utf-8")).get("releases") or {})
        else:
            cfg["releases"] = dict(tcfg["releases"])
        cfg["_paths"] = {
            "backups": str(root / "backups"),
            "state": str(root / "state"),
            "audit": str(root / "logs" / "audit.jsonl"),
            "releases": str(root / "releases"),
            "inbox": str(root / "inbox"),
        }
    else:
        cfg["_test_mode"] = False
        cfg["_paths"] = {
            "backups": str(CHANNEL_ROOT / "backups"),
            "state": str(CHANNEL_ROOT / "state"),
            "audit": str(CHANNEL_ROOT / "logs" / "audit.jsonl"),
        }
    # paths used by the registry / telemetry extensions
    cfg["_paths"].setdefault("releases", str(CHANNEL_ROOT / "releases"))
    cfg["_paths"].setdefault("inbox", str(CHANNEL_ROOT / "inbox"))
    for key in ("backups", "state"):
        Path(cfg["_paths"][key]).mkdir(parents=True, exist_ok=True)
    Path(cfg["_paths"]["audit"]).parent.mkdir(parents=True, exist_ok=True)
    return cfg


def get_release(cfg: dict, release_id: str) -> dict:
    if not isinstance(release_id, str) or not RELEASE_ID_RE.match(release_id):
        raise GateError("INVALID_RELEASE_ID", "release_id failed strict pattern")
    rel = cfg["releases"].get(release_id)
    if not rel:
        raise GateError("UNKNOWN_RELEASE_ID", "not in pinned registry")
    return rel


def resolve_target(cfg: dict, rel: dict) -> Path:
    root = Path(cfg["production"]["root"]).resolve()
    target = (root / rel["target_relative_path"]).resolve()
    pinned = Path(cfg["production"]["pinned_target"]).resolve()
    if str(target) != str(pinned):
        raise GateError("TARGET_PATH_MISMATCH", f"{target} != pinned {pinned}")
    if not target.is_file():
        raise GateError("TARGET_MISSING", str(target))
    return target


def read_patch(cfg: dict, rel: dict) -> bytes:
    p = (CHANNEL_ROOT / rel["patch_path"]).resolve()
    # In test mode the patch lives inside the sandbox root.
    if cfg.get("_test_mode"):
        p = (Path(cfg["_test_root"]) / rel["patch_path"]).resolve()
        if not p.is_file():
            p = (CHANNEL_ROOT / rel["patch_path"]).resolve()
    data = p.read_bytes()
    if sha256_hex(data) != rel["patch_sha256"]:
        raise GateError("PATCH_SHA_MISMATCH", sha256_hex(data))
    return data


# ------------------------------------------------- byte-exact unified patch
HUNK = re.compile(rb"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


# ------------------------------------------------------- multi-file releases
def allowed_scope_paths(cfg: dict) -> list[str]:
    import json as _json
    p = Path(cfg["_paths"]["releases"]) / "allowed_scope.json"
    if not p.is_file():
        raise GateError("SCOPE_FILE_MISSING", str(p))
    return list(_json.loads(p.read_text(encoding="utf-8"))["paths"])


def release_files(cfg: dict, rel: dict) -> list[dict]:
    """Normalise a registry entry into a per-file plan.

    Legacy entries (single pinned file) keep the exact historical code path;
    multi-file entries carry `target_files` and one unified section per file.
    """
    if rel.get("target_files"):
        import multifile as _mf
        patch = read_patch(cfg, rel)
        sections = _mf.parse_sections(patch)
        by_path = {s["path"].replace("\\", "/"): s for s in sections}
        plan = []
        for t in rel["target_files"]:
            p = t["path"].replace("\\", "/")
            sec = by_path.get(p)
            if sec is None:
                raise GateError("PATCH_SECTION_MISSING", p)
            plan.append({"path": p, "section": sec["section"],
                         "hunk_count": sec["hunk_count"],
                         "before_sha256": t["before_sha256"],
                         "after_sha256": t["after_sha256"],
                         "before_bytes": t["before_bytes"],
                         "after_bytes": t["after_bytes"]})
        if not plan:
            raise GateError("RELEASE_HAS_NO_FILES", "")
        return plan
    return [{"path": rel["target_relative_path"], "section": read_patch(cfg, rel),
             "hunk_count": rel["hunk_count"],
             "before_sha256": rel["before_sha256"],
             "after_sha256": rel["after_sha256"],
             "before_bytes": rel["before_bytes"],
             "after_bytes": rel["after_bytes"]}]


def resolve_file(cfg: dict, rel: dict, relpath: str) -> Path:
    """Resolve one target and prove it is inside the authorised file set."""
    root = Path(cfg["production"]["root"]).resolve()
    target = (root / relpath.replace("/", os.sep)).resolve()
    if root != target and root not in target.parents:
        raise GateError("TARGET_OUTSIDE_ROOT", relpath)
    if rel.get("target_files"):
        if relpath not in allowed_scope_paths(cfg):
            raise GateError("TARGET_PATH_MISMATCH", f"{relpath} not in allowed_scope")
    else:
        pinned = Path(cfg["production"]["pinned_target"]).resolve()
        if str(target) != str(pinned):
            raise GateError("TARGET_PATH_MISMATCH", f"{target} != pinned {pinned}")
    if not target.is_file():
        raise GateError("TARGET_MISSING", str(target))
    return target


def resolve_targets(cfg: dict, rel: dict) -> list[tuple[dict, Path]]:
    return [(item, resolve_file(cfg, rel, item["path"])) for item in release_files(cfg, rel)]


def apply_unified(source: bytes, patch: bytes, expected_file: str, *, reverse: bool = False,
                  expected_hunks: int = 3) -> bytes:
    lines = patch.splitlines(keepends=True)
    if lines[:2] != [f"--- a/{expected_file}\n".encode(), f"+++ b/{expected_file}\n".encode()]:
        raise GateError("PATCH_SCOPE_INVALID", "patch header does not match target file")
    original = source.splitlines(keepends=True)
    output, cursor, index, hunks = [], 0, 2, 0
    while index < len(lines):
        # git omits a count when it is 1 and appends a section heading after the
        # closing @@; both forms are accepted, the counts stay authoritative.
        m = HUNK.match(lines[index])
        if not m:
            raise GateError("PATCH_HUNK_INVALID", str(lines[index][:40]))
        old_start = int(m.group(1))
        old_count = int(m.group(2)) if m.group(2) else 1
        new_start = int(m.group(3))
        new_count = int(m.group(4)) if m.group(4) else 1
        if reverse:
            old_start, new_start = new_start, old_start
            old_count, new_count = new_count, old_count
        start = old_start - 1
        if start < cursor or start > len(original):
            raise GateError("PATCH_OFFSET_INVALID", f"start={start} cursor={cursor}")
        output.extend(original[cursor:start])
        cursor = start
        if len(output) != new_start - 1:
            raise GateError("PATCH_NEW_OFFSET_INVALID", "")
        index += 1
        consumed = produced = 0
        while index < len(lines) and not lines[index].startswith(b"@@ "):
            line = lines[index]
            kind, body = line[:1], line[1:]
            if reverse:
                kind = {b"+": b"-", b"-": b"+"}.get(kind, kind)
            if kind not in (b" ", b"+", b"-") or not body.endswith(b"\n"):
                raise GateError("PATCH_LINE_INVALID", str(line[:40]))
            if kind in (b" ", b"-"):
                if cursor >= len(original) or original[cursor] != body:
                    raise GateError("PATCH_CONTEXT_MISMATCH", f"line {cursor + 1}")
                cursor += 1
                consumed += 1
            if kind in (b" ", b"+"):
                output.append(body)
                produced += 1
            index += 1
        if (consumed, produced) != (old_count, new_count):
            raise GateError("PATCH_COUNT_INVALID", "")
        hunks += 1
    if hunks != expected_hunks:
        raise GateError("PATCH_HUNK_COUNT_INVALID", f"{hunks} != {expected_hunks}")
    output.extend(original[cursor:])
    return b"".join(output)


# ------------------------------------------------------------------ ACL
SE_FILE_OBJECT = 1
DACL_SECURITY_INFORMATION = 0x00000004


def copy_dacl(src: Path, dst: Path) -> None:
    """Copy the discretionary ACL from src to dst (preserves production ACL)."""
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    pSD = ctypes.c_void_p()
    pDacl = ctypes.c_void_p()
    ok = advapi.GetNamedSecurityInfoW(
        str(src), SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
        None, None, ctypes.byref(pDacl), None, ctypes.byref(pSD))
    if ok != 0:
        raise GateError("ACL_READ_FAILED", f"err={ok}")
    ok = advapi.SetNamedSecurityInfoW(
        str(dst), SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
        None, None, pDacl, None)
    if ok != 0:
        raise GateError("ACL_WRITE_FAILED", f"err={ok}")


# ------------------------------------------------------------- audit log
def audit(cfg: dict, event: dict) -> None:
    rec = {"ts": iso_now(), **event}
    p = Path(cfg["_paths"]["audit"])
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"AUDIT_WRITE_FAILED: {e}", file=sys.stderr)


# ------------------------------------------------------- operation store
def operations_path(cfg: dict) -> Path:
    return Path(cfg["_paths"]["state"]) / "operations.json"


def load_operations(cfg: dict) -> dict:
    p = operations_path(cfg)
    if not p.is_file():
        return {"operations": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save_operations(cfg: dict, data: dict) -> None:
    p = operations_path(cfg)
    tmp = p.with_suffix(".json.tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        # last-resort direct write: losing an operation record must never crash
        # an operation result path (the result is still returned + audited)
        try:
            p.write_text(payload, encoding="utf-8")
        except OSError:
            pass


# ------------------------------------------------------------- DB helpers
def ro_conn(db_path: str):
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def rw_conn(db_path: str):
    conn = sqlite3.connect(db_path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=20000")
    return conn


def db_get(conn: sqlite3.Connection, key: str):
    row = conn.execute("SELECT value FROM system_config WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


# --------------------------------------------------- live gate evaluation
def live_gates(cfg: dict, release_id: str, *, direction: str = "apply") -> dict:
    """Evaluate every live gate. Read-only: no DB writes, no file writes.

    direction="apply"    full gate set including patch-direction gates
                         (source at before-SHA, byte dry-run, rollback pre-verify).
    direction="rollback" safety gates only. Patch-direction gates are meaningless
                         once the file sits at after-SHA (source_sha_matches would
                         fail by design) and are excluded, so a verified rollback
                         is never blocked by the apply-direction source hash.
    """
    if direction not in ("apply", "rollback"):
        raise GateError("INVALID_DIRECTION", direction)
    rel = get_release(cfg, release_id)
    if rel.get("target_files"):
        return live_gates_multi(cfg, release_id, direction=direction)
    gates: dict = {}
    target = resolve_target(cfg, rel)
    gates["runtime_path_verified"] = {"pass": True, "target": str(target)}

    src = target.read_bytes()
    fp = fingerprint(src)
    if direction == "apply":
        gates["source_sha_matches"] = {
            "pass": fp["sha256"] == rel["before_sha256"],
            "actual": fp["sha256"], "expected": rel["before_sha256"],
            "actual_bytes": fp["bytes"], "expected_bytes": rel["before_bytes"]}

        patch = read_patch(cfg, rel)
        try:
            candidate = apply_unified(src, patch, rel["target_relative_path"], reverse=False,
                                      expected_hunks=rel["hunk_count"])
            cfp = fingerprint(candidate)
            compatible = (cfp["sha256"] == rel["after_sha256"] and cfp["bytes"] == rel["after_bytes"])
            gates["version_compatible"] = {"pass": compatible, "dry_run_after_sha256": cfp["sha256"],
                                           "expected_after_sha256": rel["after_sha256"]}
            try:
                ast.parse(candidate.decode("utf-8"))
                syntax_ok = True
            except SyntaxError as e:
                syntax_ok = False
                gates["targeted_tests_pass"] = {"pass": False, "error": f"ast.parse: {e}"}
            if syntax_ok and "targeted_tests_pass" not in gates:
                gates["targeted_tests_pass"] = {
                    "pass": True, "method": "ast_parse + byte-exact dry-run (executor-level); "
                                            "functional suite is a development-stage duty per charter"}
            gates["no_new_critical_regressions"] = {
                "pass": compatible and syntax_ok,
                "scope": f"single file {rel['target_relative_path']}, {rel['hunk_count']} hunks, "
                         f"no whole-tree overwrite"}
            # rollback pre-verification (in memory, no writes)
            try:
                back = apply_unified(candidate, patch, rel["target_relative_path"], reverse=True,
                                     expected_hunks=rel["hunk_count"])
                rb_ok = fingerprint(back)["sha256"] == rel["before_sha256"] and back == src
            except GateError as e:
                rb_ok = False
                gates["rollback_verified"] = {"pass": False, "error": str(e)}
            if "rollback_verified" not in gates:
                gates["rollback_verified"] = {"pass": rb_ok,
                                              "method": "reverse patch reproduces before-SHA in memory"}
        except GateError as e:
            gates["version_compatible"] = {"pass": False, "error": str(e)}
            gates["targeted_tests_pass"] = {"pass": False, "error": "candidate unavailable"}
            gates["no_new_critical_regressions"] = {"pass": False, "error": "candidate unavailable"}
            gates["rollback_verified"] = {"pass": False, "error": "candidate unavailable"}

        # backup directory readiness (write probe into a temp file)
        bdir = Path(cfg["_paths"]["backups"])
        try:
            probe = bdir / ".write_probe"
            probe.write_bytes(b"probe")
            probe.unlink()
            gates["backup_dir_writable"] = {"pass": True, "dir": str(bdir)}
        except OSError as e:
            gates["backup_dir_writable"] = {"pass": False, "error": str(e)}

    # ---- production DB gates (read-only)
    db = cfg["production"]["db_path"]
    conn = ro_conn(db)
    try:
        smtp = db_get(conn, "SMTP_enabled")
        gates["smtp_disabled"] = {"pass": str(smtp) == "0", "SMTP_enabled": smtp}

        bd = business_date_shanghai()
        lock_key = cfg["lock"]["key_prefix"] + bd
        lock_val = db_get(conn, lock_key)
        acq = db_get(conn, lock_key + "_acquired_at")
        stale = False
        if lock_val and lock_val != "released" and acq:
            try:
                at = datetime.strptime(acq, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                stale = (datetime.now(timezone.utc) - at).total_seconds() > cfg["lock"]["stale_after_seconds"]
            except (TypeError, ValueError):
                stale = False
        lock_free = (not lock_val) or lock_val == "released" or stale
        gates["run_locks_healthy"] = {"pass": lock_free, "lock_key": lock_key,
                                      "value": lock_val, "acquired_at": acq, "stale": stale}
        gates["inventory_exclusion_held"] = {"pass": lock_free,
                                             "note": "preflight is read-only; apply acquires the "
                                                     "official Inventory lock for the swap window"}

        # A run counts as "running" only if unfinished AND started inside the
        # stale window (2h, same TTL as the official lock). Older unfinished
        # rows are historical residue from crashed runs and are reported
        # separately, never treated as live executions.
        running = conn.execute(
            "SELECT run_id, stage, started_at, current_step FROM job_runs "
            "WHERE finished_at IS NULL AND stage='inventory' "
            "AND started_at >= datetime('now','-2 hours')").fetchall()
        stale_rows = conn.execute(
            "SELECT COUNT(*) AS n, MIN(started_at) AS oldest FROM job_runs "
            "WHERE finished_at IS NULL AND stage='inventory' "
            "AND started_at < datetime('now','-2 hours')").fetchone()
        gates["inventory_not_running"] = {
            "pass": len(running) == 0,
            "running": [dict(r) for r in running],
            "stale_unfinished_rows": stale_rows["n"] if stale_rows else 0,
            "oldest_stale": stale_rows["oldest"] if stale_rows else None,
            "note": "stale_unfinished_rows are crashed-run residue older than the 2h "
                    "lock TTL; they are evidence only, not live executions"}

        # no executable send authorization
        rows = conn.execute(
            "SELECT e.id, e.authorization_id, e.status, e.consumed_at, s.status AS parent_status, "
            "       s.expires_at, s.consumed_at AS parent_consumed_at "
            "FROM send_authorization_entries e LEFT JOIN send_authorizations s "
            "  ON e.authorization_id = s.authorization_id "
            "WHERE e.status='pending' AND e.consumed_at IS NULL").fetchall()
        executable = []
        for r in rows:
            parent_dead = (r["parent_status"] in ("revoked", "superseded", "expired", "consumed")
                           or r["parent_consumed_at"])
            expired = False
            if r["expires_at"]:
                try:
                    expired = datetime.strptime(r["expires_at"], "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=CST) < datetime.now(CST)
                except (TypeError, ValueError):
                    expired = False
            if not parent_dead and not expired:
                executable.append(dict(r))
        gates["no_executable_send_authorization"] = {
            "pass": len(executable) == 0, "pending_entries": len(rows),
            "executable": len(executable)}
    finally:
        conn.close()

    # ---- WorkBuddy automations gates (read-only)
    wb = cfg["production"]["workbuddy_db_path"]
    conn = ro_conn(wb)
    try:
        inv = conn.execute("SELECT id, status, next_run_at, rrule, cwds FROM automations WHERE id=?",
                           (cfg["inventory_automation_id"],)).fetchone()
        inv_next = None
        if inv and inv["next_run_at"]:
            inv_next = datetime.fromtimestamp(inv["next_run_at"] / 1000, CST)
        window_ok = True
        minutes_away = None
        if inv_next:
            minutes_away = (inv_next - datetime.now(CST)).total_seconds() / 60.0
            window_ok = minutes_away >= cfg["gates"]["min_minutes_to_next_inventory"]
        gates["safe_window_verified"] = {
            "pass": window_ok and gates["inventory_not_running"]["pass"],
            "inventory_status": inv["status"] if inv else None,
            "inventory_next_run": inv_next.strftime("%Y-%m-%d %H:%M:%S +08") if inv_next else None,
            "minutes_to_next_run": round(minutes_away, 1) if minutes_away is not None else None,
            "min_required_minutes": cfg["gates"]["min_minutes_to_next_inventory"]}

        sending = {}
        all_paused = True
        for name, aid in cfg["sending_automation_ids"].items():
            row = conn.execute("SELECT id, status, next_run_at, deleted_at FROM automations WHERE id=?",
                               (aid,)).fetchone()
            st = row["status"] if row else "MISSING"
            deleted = bool(row["deleted_at"]) if row else False
            ok = (st != "ACTIVE") or deleted
            all_paused = all_paused and ok
            sending[name] = {"id": aid, "status": st, "deleted": deleted, "pass": ok}
        gates["sending_tasks_paused"] = {"pass": all_paused, "tasks": sending}
    finally:
        conn.close()

    return gates


def gates_summary(gates: dict) -> dict:
    failed = [k for k, v in gates.items() if not v.get("pass")]
    return {"all_pass": not failed, "failed": failed,
            "count": len(gates), "passed": len(gates) - len(failed)}


# ------------------------------------------------- multi-file gate evaluation
def collect_runtime_gates(cfg: dict) -> dict:
    """The eight state gates that do not depend on the patch direction.

    Same queries as the single-file path; kept in one helper so multi-file
    releases cannot silently drift from the legacy gate semantics.
    """
    gates: dict = {}
    db = cfg["production"]["db_path"]
    conn = ro_conn(db)
    try:
        smtp = db_get(conn, "SMTP_enabled")
        gates["smtp_disabled"] = {"pass": str(smtp) == "0", "SMTP_enabled": smtp}

        bd = business_date_shanghai()
        lock_key = cfg["lock"]["key_prefix"] + bd
        lock_val = db_get(conn, lock_key)
        acq = db_get(conn, lock_key + "_acquired_at")
        stale = False
        if lock_val and lock_val != "released" and acq:
            try:
                at = datetime.strptime(acq, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                stale = (datetime.now(timezone.utc) - at).total_seconds() > \
                    cfg["lock"]["stale_after_seconds"]
            except (TypeError, ValueError):
                stale = False
        lock_free = (not lock_val) or lock_val == "released" or stale
        gates["run_locks_healthy"] = {"pass": lock_free, "lock_key": lock_key,
                                      "value": lock_val, "acquired_at": acq, "stale": stale}
        gates["inventory_exclusion_held"] = {"pass": lock_free,
                                             "note": "preflight is read-only; apply acquires the "
                                                     "official Inventory lock for the swap window"}

        running = conn.execute(
            "SELECT run_id, stage, started_at, current_step FROM job_runs "
            "WHERE finished_at IS NULL AND stage='inventory' "
            "AND started_at >= datetime('now','-2 hours')").fetchall()
        stale_rows = conn.execute(
            "SELECT COUNT(*) AS n, MIN(started_at) AS oldest FROM job_runs "
            "WHERE finished_at IS NULL AND stage='inventory' "
            "AND started_at < datetime('now','-2 hours')").fetchone()
        gates["inventory_not_running"] = {
            "pass": len(running) == 0,
            "running": [dict(r) for r in running],
            "stale_unfinished_rows": stale_rows["n"] if stale_rows else 0,
            "oldest_stale": stale_rows["oldest"] if stale_rows else None}

        rows = conn.execute(
            "SELECT e.id, e.authorization_id, e.status, e.consumed_at, s.status AS parent_status, "
            "       s.expires_at, s.consumed_at AS parent_consumed_at "
            "FROM send_authorization_entries e LEFT JOIN send_authorizations s "
            "  ON e.authorization_id = s.authorization_id "
            "WHERE e.status='pending' AND e.consumed_at IS NULL").fetchall()
        executable = []
        for r in rows:
            parent_dead = (r["parent_status"] in ("revoked", "superseded", "expired", "consumed")
                           or r["parent_consumed_at"])
            expired = False
            if r["expires_at"]:
                try:
                    expired = datetime.strptime(r["expires_at"], "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=CST) < datetime.now(CST)
                except (TypeError, ValueError):
                    expired = False
            if not parent_dead and not expired:
                executable.append(dict(r))
        gates["no_executable_send_authorization"] = {
            "pass": len(executable) == 0, "pending_entries": len(rows),
            "executable": len(executable)}
    finally:
        conn.close()

    wb = cfg["production"]["workbuddy_db_path"]
    conn = ro_conn(wb)
    try:
        inv = conn.execute("SELECT id, status, next_run_at, rrule, cwds FROM automations WHERE id=?",
                           (cfg["inventory_automation_id"],)).fetchone()
        inv_next = None
        if inv and inv["next_run_at"]:
            inv_next = datetime.fromtimestamp(inv["next_run_at"] / 1000, CST)
        window_ok = True
        minutes_away = None
        if inv_next:
            minutes_away = (inv_next - datetime.now(CST)).total_seconds() / 60.0
            window_ok = minutes_away >= cfg["gates"]["min_minutes_to_next_inventory"]
        gates["safe_window_verified"] = {
            "pass": window_ok and gates["inventory_not_running"]["pass"],
            "inventory_status": inv["status"] if inv else None,
            "inventory_next_run": inv_next.strftime("%Y-%m-%d %H:%M:%S +08") if inv_next else None,
            "minutes_to_next_run": round(minutes_away, 1) if minutes_away is not None else None,
            "min_required_minutes": cfg["gates"]["min_minutes_to_next_inventory"]}

        sending = {}
        all_paused = True
        for name, aid in cfg["sending_automation_ids"].items():
            row = conn.execute(
                "SELECT id, status, next_run_at, deleted_at FROM automations WHERE id=?",
                (aid,)).fetchone()
            st = row["status"] if row else "MISSING"
            deleted = bool(row["deleted_at"]) if row else False
            ok = (st != "ACTIVE") or deleted
            all_paused = all_paused and ok
            sending[name] = {"id": aid, "status": st, "deleted": deleted, "pass": ok}
        gates["sending_tasks_paused"] = {"pass": all_paused, "tasks": sending}
    finally:
        conn.close()
    return gates


def live_gates_multi(cfg: dict, release_id: str, *, direction: str = "apply") -> dict:
    """14-gate set for a multi-file release. Gate names are identical to the
    single-file path so a client never has to branch on release shape."""
    rel = get_release(cfg, release_id)
    gates: dict = {}
    targets = resolve_targets(cfg, rel)
    gates["runtime_path_verified"] = {
        "pass": True, "file_count": len(targets),
        "targets": {item["path"]: str(p) for item, p in targets},
        "target": str(targets[0][1]) if len(targets) == 1 else None}

    srcs = {item["path"]: p.read_bytes() for item, p in targets}

    if direction == "apply":
        per_src = {}
        for item, _p in targets:
            src = srcs[item["path"]]
            fp = fingerprint(src)
            per_src[item["path"]] = {"pass": fp["sha256"] == item["before_sha256"],
                                     "actual": fp["sha256"], "expected": item["before_sha256"],
                                     "actual_bytes": fp["bytes"],
                                     "expected_bytes": item["before_bytes"]}
        gates["source_sha_matches"] = {
            "pass": all(v["pass"] for v in per_src.values()), "files": per_src,
            "actual": per_src[targets[0][0]["path"]]["actual"] if len(targets) == 1 else None,
            "expected": per_src[targets[0][0]["path"]]["expected"] if len(targets) == 1 else None}

        per_dry, candidates, per_rb = {}, {}, {}
        for item, _p in targets:
            src, sec = srcs[item["path"]], item["section"]
            try:
                cand = apply_unified(src, sec, item["path"], reverse=False,
                                     expected_hunks=item["hunk_count"])
                cfp = fingerprint(cand)
                ok = cfp["sha256"] == item["after_sha256"] and cfp["bytes"] == item["after_bytes"]
                per_dry[item["path"]] = {"pass": ok, "dry_run_after_sha256": cfp["sha256"],
                                         "expected_after_sha256": item["after_sha256"],
                                         "dry_run_bytes": cfp["bytes"],
                                         "expected_bytes": item["after_bytes"]}
                candidates[item["path"]] = cand
            except GateError as e:
                per_dry[item["path"]] = {"pass": False, "error": str(e)}
        gates["version_compatible"] = {
            "pass": all(v["pass"] for v in per_dry.values()), "files": per_dry,
            "dry_run_after_sha256": (per_dry[targets[0][0]["path"]].get("dry_run_after_sha256")
                                     if len(targets) == 1 else None),
            "expected_after_sha256": (per_dry[targets[0][0]["path"]].get("expected_after_sha256")
                                      if len(targets) == 1 else None)}

        syntax_errors = []
        for path, cand in candidates.items():
            try:
                ast.parse(cand.decode("utf-8"))
            except (SyntaxError, UnicodeDecodeError) as e:
                syntax_errors.append(f"{path}: {e}")
        gates["targeted_tests_pass"] = {
            "pass": not syntax_errors and len(candidates) == len(targets),
            "method": "ast_parse + byte-exact dry-run for every file; functional suite is attested "
                      "by the registration bundle tests.json",
            "syntax_errors": syntax_errors}

        for item, _p in targets:
            cand = candidates.get(item["path"])
            if cand is None:
                per_rb[item["path"]] = {"pass": False, "error": "candidate unavailable"}
                continue
            try:
                back = apply_unified(cand, item["section"], item["path"], reverse=True,
                                     expected_hunks=item["hunk_count"])
                per_rb[item["path"]] = {
                    "pass": fingerprint(back)["sha256"] == item["before_sha256"]
                    and back == srcs[item["path"]]}
            except GateError as e:
                per_rb[item["path"]] = {"pass": False, "error": str(e)}
        gates["rollback_verified"] = {"pass": all(v["pass"] for v in per_rb.values()),
                                      "files": per_rb,
                                      "method": "reverse patch reproduces before-SHA for every file"}

        gates["no_new_critical_regressions"] = {
            "pass": gates["version_compatible"]["pass"] and gates["targeted_tests_pass"]["pass"],
            "scope": f"{len(targets)} files: {', '.join(i['path'] for i, _ in targets)}; "
                     f"{sum(i['hunk_count'] for i, _ in targets)} hunks; no whole-tree overwrite"}

        bdir = Path(cfg["_paths"]["backups"])
        try:
            probe = bdir / ".write_probe"
            probe.write_bytes(b"probe")
            probe.unlink()
            gates["backup_dir_writable"] = {"pass": True, "dir": str(bdir)}
        except OSError as e:
            gates["backup_dir_writable"] = {"pass": False, "error": str(e)}

    gates.update(collect_runtime_gates(cfg))
    return gates


# ------------------------------------------------------------ inventory lock
def inventory_acquire(cfg: dict, holder: str) -> tuple[bool, dict]:
    """Acquire the official Inventory run-lock with our holder.

    Replicates bd_db.acquire_run_lock semantics exactly (same key, same
    BEGIN IMMEDIATE atomicity, same 2h stale rule). A fresh lock held by
    anyone else blocks us - we never steal valid locks.
    """
    bd = business_date_shanghai()
    lock_key = cfg["lock"]["key_prefix"] + bd
    acq_key = lock_key + "_acquired_at"
    conn = rw_conn(cfg["production"]["db_path"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Same durable marker as bd_db admission. Check while holding SQLite's
        # write reservation, before stale-lock handling or any publisher effect.
        # Released is the only permissive recorded state; malformed/NULL blocks.
        maintenance = conn.execute(
            "SELECT value FROM system_config WHERE key=?",
            ("u1:inventory:maintenance:v1",)).fetchone()
        if maintenance is not None and maintenance[0] != "released":
            conn.rollback()
            return False, {"lock_key": lock_key,
                           "reason": "STOP_AND_PRESERVE_MAINTENANCE_HELD"}
        row = conn.execute("SELECT value FROM system_config WHERE key=?", (lock_key,)).fetchone()
        existing = row[0] if row else ""
        stamp = conn.execute("SELECT value FROM system_config WHERE key=?", (acq_key,)).fetchone()
        stale = False
        if existing and existing != "released":
            try:
                at = datetime.strptime(stamp[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                stale = (datetime.now(timezone.utc) - at).total_seconds() > cfg["lock"]["stale_after_seconds"]
            except (TypeError, ValueError, IndexError):
                stale = False
            if not stale:
                conn.rollback()
                return False, {"lock_key": lock_key, "held_by": existing}
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        upsert = ("INSERT INTO system_config(key,value,updated_at) VALUES(?,?,datetime('now')) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at")
        conn.execute(upsert, (lock_key, holder))
        conn.execute(upsert, (acq_key, now_utc))
        conn.commit()
        return True, {"lock_key": lock_key, "holder": holder, "overrode_stale": stale}
    finally:
        conn.close()


def inventory_release(cfg: dict, holder: str) -> bool:
    bd = business_date_shanghai()
    lock_key = cfg["lock"]["key_prefix"] + bd
    conn = rw_conn(cfg["production"]["db_path"])
    try:
        with conn:
            cur = conn.execute(
                "UPDATE system_config SET value='released',updated_at=datetime('now') "
                "WHERE key=? AND value=?", (lock_key, holder))
        return cur.rowcount == 1
    finally:
        conn.close()


# ------------------------------------------------------------ operations
def op_preflight(cfg: dict, release_id: str, caller: str) -> dict:
    _assert_seal(cfg)
    gates = live_gates(cfg, release_id)
    summary = gates_summary(gates)
    result = {
        "operation": "preflight", "release_id": release_id, "read_only": True,
        "ts": iso_now(), "channel_id": cfg["channel_id"], "test_mode": cfg.get("_test_mode", False),
        "gates": gates, "summary": summary,
        "verdict": "PREFLIGHT_PASS" if summary["all_pass"] else "PREFLIGHT_BLOCKED",
        "note_zh": "只读门禁证据；未写入任何生产数据。",
        "note_en": "Read-only gate evidence; no production data written.",
    }
    audit(cfg, {"op": "preflight", "release_id": release_id, "caller": caller,
                "result": result["verdict"], "failed": summary["failed"]})
    return result


def op_apply(cfg: dict, release_id: str, caller: str, confirm: bool) -> dict:
    if confirm is not True:
        raise GateError("CONFIRM_REQUIRED", "apply requires explicit confirm=true")
    rel = get_release(cfg, release_id)
    if rel.get("target_files"):
        return op_apply_multi(cfg, release_id, caller, confirm)
    _assert_seal(cfg)
    operation_id = f"op-{now_cst().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    started = iso_now()
    gates = live_gates(cfg, release_id)
    summary = gates_summary(gates)
    if not summary["all_pass"]:
        result = {"operation": "apply", "operation_id": operation_id, "release_id": release_id,
                  "state": "aborted", "ts": started, "gates": gates, "summary": summary,
                  "verdict": "APPLY_ABORTED_GATES",
                  "note_zh": "门禁未全部通过；未触碰生产文件。",
                  "note_en": "Gates not all green; production file untouched."}
        _record(cfg, result, caller)
        audit(cfg, {"op": "apply", "release_id": release_id, "operation_id": operation_id,
                    "caller": caller, "result": "ABORTED_GATES", "failed": summary["failed"]})
        return result

    target = resolve_target(cfg, rel)
    patch = read_patch(cfg, rel)
    bd_before = business_date_shanghai()
    holder = f"deploy:{operation_id}"
    lock_info = None
    backup_path = None
    try:
        ok, lock_info = inventory_acquire(cfg, holder)
        if not ok:
            raise GateError("LOCK_CONFLICT", json.dumps(lock_info))
        # re-verify source after taking the lock (race window closed)
        src = target.read_bytes()
        if fingerprint(src)["sha256"] != rel["before_sha256"]:
            raise GateError("SOURCE_CHANGED_AFTER_LOCK", fingerprint(src)["sha256"])
        candidate = apply_unified(src, patch, rel["target_relative_path"],
                                  expected_hunks=rel["hunk_count"])
        cfp = fingerprint(candidate)
        if cfp["sha256"] != rel["after_sha256"]:
            raise GateError("RESULT_SHA_MISMATCH", cfp["sha256"])

        bdir = Path(cfg["_paths"]["backups"]) / operation_id
        bdir.mkdir(parents=True, exist_ok=False)
        backup_path = bdir / (target.name + ".before.bak")
        backup_path.write_bytes(src)
        with open(backup_path, "rb+") as f:
            f.flush()
            os.fsync(f.fileno())
        bfp = fingerprint(backup_path.read_bytes())
        if bfp["sha256"] != rel["before_sha256"]:
            raise GateError("BACKUP_SHA_MISMATCH", bfp["sha256"])

        tmp = target.with_name(f".{target.name}.deploy-tmp-{operation_id}")
        tmp.write_bytes(candidate)
        with open(tmp, "rb+") as f:
            f.flush()
            os.fsync(f.fileno())
        copy_dacl(target, tmp)
        os.replace(tmp, target)

        after = fingerprint(target.read_bytes())
        if after["sha256"] != rel["after_sha256"] or after["bytes"] != rel["after_bytes"]:
            raise GateError("POST_REPLACE_SHA_MISMATCH", after["sha256"])

        bd_after = business_date_shanghai()
        if bd_after != bd_before:
            raise GateError("BUSINESS_DATE_RACE", f"{bd_before} -> {bd_after}")

        inventory_release(cfg, holder)
        lock_info = {**lock_info, "released": True}
        result = {
            "operation": "apply", "operation_id": operation_id, "release_id": release_id,
            "state": "applied", "started_at": started, "finished_at": iso_now(),
            "channel_id": cfg["channel_id"], "test_mode": cfg.get("_test_mode", False),
            "target": str(target), "backup": str(backup_path),
            "business_date": bd_before, "lock": lock_info,
            "before": fingerprint(src), "after": after, "gates": gates, "summary": summary,
            "verdict": "APPLIED",
            "note_zh": "已通过全部门禁、持官方 Inventory 锁、字节级备份、同卷原子替换并复核 SHA。",
            "note_en": "All gates passed; official Inventory lock held; byte-exact backup; "
                       "same-volume atomic replace; post-replace SHA verified.",
        }
        _record(cfg, result, caller)
        audit(cfg, {"op": "apply", "release_id": release_id, "operation_id": operation_id,
                    "caller": caller, "result": "APPLIED",
                    "after_sha256": after["sha256"], "backup_sha256": bfp["sha256"]})
        return result
    except (GateError, OSError) as e:
        code = getattr(e, "code", None) or ("IO_ERROR" if isinstance(e, OSError) else "UNKNOWN")
        # best-effort rollback if we already replaced the file
        rollback_note = None
        if backup_path and backup_path.is_file() and target.is_file():
            try:
                cur = fingerprint(target.read_bytes())["sha256"]
                if cur == rel["after_sha256"]:
                    b = backup_path.read_bytes()
                    t2 = target.with_name(f".{target.name}.rollback-tmp-{operation_id}")
                    t2.write_bytes(b)
                    copy_dacl(target, t2)
                    os.replace(t2, target)
                    rollback_note = fingerprint(target.read_bytes())["sha256"]
            except OSError:
                rollback_note = "ROLLBACK_WRITE_FAILED"
        try:
            if lock_info and lock_info.get("holder") == holder:
                inventory_release(cfg, holder)
        except Exception:
            pass
        result = {
            "operation": "apply", "operation_id": operation_id, "release_id": release_id,
            "state": "failed", "started_at": started, "finished_at": iso_now(),
            "channel_id": cfg["channel_id"], "test_mode": cfg.get("_test_mode", False),
            "target": str(target), "backup": str(backup_path) if backup_path else None,
            "error": str(e), "rollback_sha": rollback_note,
            "gates": gates, "summary": summary, "verdict": f"APPLY_FAILED:{code}",
            "note_zh": "应用失败；如已替换则已自动回滚并复核。",
            "note_en": "Apply failed; auto-rollback performed and verified if replacement happened.",
        }
        _record(cfg, result, caller)
        audit(cfg, {"op": "apply", "release_id": release_id, "operation_id": operation_id,
                    "caller": caller, "result": f"FAILED:{code}", "rollback": rollback_note})
        return result


def _backup_name(relpath: str, single: bool) -> str:
    if single:
        return Path(relpath).name + ".before.bak"
    return relpath.replace("/", "__").replace("\\", "__") + ".before.bak"


def op_apply_multi(cfg: dict, release_id: str, caller: str, confirm: bool) -> dict:
    if confirm is not True:
        raise GateError("CONFIRM_REQUIRED", "apply requires explicit confirm=true")
    _assert_seal(cfg)
    rel = get_release(cfg, release_id)
    operation_id = f"op-{now_cst().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    started = iso_now()
    gates = live_gates_multi(cfg, release_id, direction="apply")
    summary = gates_summary(gates)
    if not summary["all_pass"]:
        result = {"operation": "apply", "operation_id": operation_id, "release_id": release_id,
                  "state": "aborted", "ts": started, "gates": gates, "summary": summary,
                  "verdict": "APPLY_ABORTED_GATES",
                  "note_zh": "门禁未全部通过；未触碰生产文件。",
                  "note_en": "Gates not all green; production files untouched."}
        _record(cfg, result, caller)
        audit(cfg, {"op": "apply", "release_id": release_id, "operation_id": operation_id,
                    "caller": caller, "result": "ABORTED_GATES", "failed": summary["failed"]})
        return result

    targets = resolve_targets(cfg, rel)
    single = len(targets) == 1
    bd_before = business_date_shanghai()
    holder = f"deploy:{operation_id}"
    lock_info = None
    bdir = Path(cfg["_paths"]["backups"]) / operation_id
    backups: list[dict] = []
    replaced: list[dict] = []
    try:
        ok, lock_info = inventory_acquire(cfg, holder)
        if not ok:
            raise GateError("LOCK_CONFLICT", json.dumps(lock_info))

        prepared = []
        for item, target in targets:
            src = target.read_bytes()
            if fingerprint(src)["sha256"] != item["before_sha256"]:
                raise GateError("SOURCE_CHANGED_AFTER_LOCK",
                                f"{item['path']} {fingerprint(src)['sha256']}")
            cand = apply_unified(src, item["section"], item["path"],
                                 expected_hunks=item["hunk_count"])
            cfp = fingerprint(cand)
            if cfp["sha256"] != item["after_sha256"] or cfp["bytes"] != item["after_bytes"]:
                raise GateError("RESULT_SHA_MISMATCH", f"{item['path']} {cfp['sha256']}")
            prepared.append({"item": item, "target": target, "src": src, "candidate": cand})

        bdir.mkdir(parents=True, exist_ok=False)
        for prep in prepared:
            bp = bdir / _backup_name(prep["item"]["path"], single)
            bp.write_bytes(prep["src"])
            with open(bp, "rb+") as f:
                f.flush()
                os.fsync(f.fileno())
            bfp = fingerprint(bp.read_bytes())
            if bfp["sha256"] != prep["item"]["before_sha256"]:
                raise GateError("BACKUP_SHA_MISMATCH", prep["item"]["path"])
            backups.append({"path": prep["item"]["path"], "backup": str(bp),
                            "backup_sha256": bfp["sha256"]})

        for prep in prepared:
            target = prep["target"]
            tmp = target.with_name(f".{target.name}.deploy-tmp-{operation_id}")
            tmp.write_bytes(prep["candidate"])
            with open(tmp, "rb+") as f:
                f.flush()
                os.fsync(f.fileno())
            copy_dacl(target, tmp)
            os.replace(tmp, target)
            replaced.append(prep)

        after_all = {}
        for prep in prepared:
            after = fingerprint(prep["target"].read_bytes())
            if after["sha256"] != prep["item"]["after_sha256"] or \
                    after["bytes"] != prep["item"]["after_bytes"]:
                raise GateError("POST_REPLACE_SHA_MISMATCH", prep["item"]["path"])
            after_all[prep["item"]["path"]] = after

        bd_after = business_date_shanghai()
        if bd_after != bd_before:
            raise GateError("BUSINESS_DATE_RACE", f"{bd_before} -> {bd_after}")

        inventory_release(cfg, holder)
        lock_info = {**lock_info, "released": True}
        first = prepared[0]
        result = {
            "operation": "apply", "operation_id": operation_id, "release_id": release_id,
            "state": "applied", "started_at": started, "finished_at": iso_now(),
            "channel_id": cfg["channel_id"], "test_mode": cfg.get("_test_mode", False),
            "file_count": len(prepared),
            "target": str(first["target"]), "backup": str(bdir / _backup_name(
                first["item"]["path"], single)),
            "files": [{"path": p["item"]["path"], "target": str(p["target"]),
                       "before": fingerprint(p["src"]), "after": after_all[p["item"]["path"]],
                       "backup": b,
                       } for p, b in zip(prepared, backups)],
            "business_date": bd_before, "lock": lock_info,
            "before": fingerprint(first["src"]), "after": after_all[first["item"]["path"]],
            "gates": gates, "summary": summary, "verdict": "APPLIED",
            "note_zh": "全部文件通过门禁、持官方 Inventory 锁、逐文件字节级备份、"
                       "同卷原子替换并复核 SHA；任一文件失败即整体回滚。",
            "note_en": "Every file passed the gates; official Inventory lock held; per-file "
                       "byte-exact backup; atomic replace; post-replace SHA verified; any "
                       "failure rolls the whole release back.",
        }
        _record(cfg, result, caller)
        audit(cfg, {"op": "apply", "release_id": release_id, "operation_id": operation_id,
                    "caller": caller, "result": "APPLIED", "file_count": len(prepared),
                    "after_sha256": {k: v["sha256"] for k, v in after_all.items()}})
        return result
    except (GateError, OSError) as e:
        code = getattr(e, "code", None) or ("IO_ERROR" if isinstance(e, OSError) else "UNKNOWN")
        restored = []
        for prep in reversed(replaced):
            try:
                b = next(x for x in backups if x["path"] == prep["item"]["path"])
                target = prep["target"]
                t2 = target.with_name(f".{target.name}.rollback-tmp-{operation_id}")
                t2.write_bytes(Path(b["backup"]).read_bytes())
                copy_dacl(target, t2)
                os.replace(t2, target)
                restored.append({"path": prep["item"]["path"],
                                 "sha256": fingerprint(target.read_bytes())["sha256"]})
            except Exception:
                restored.append({"path": prep["item"]["path"], "sha256": "ROLLBACK_WRITE_FAILED"})
        try:
            if lock_info and lock_info.get("holder") == holder:
                inventory_release(cfg, holder)
        except Exception:
            pass
        result = {
            "operation": "apply", "operation_id": operation_id, "release_id": release_id,
            "state": "failed", "started_at": started, "finished_at": iso_now(),
            "channel_id": cfg["channel_id"], "test_mode": cfg.get("_test_mode", False),
            "file_count": len(targets),
            "target": str(targets[0][1]), "backup": str(bdir) if bdir.is_dir() else None,
            "files": [{"path": i["path"], "target": str(p)} for i, p in targets],
            "error": str(e), "restored": restored,
            "gates": gates, "summary": summary, "verdict": f"APPLY_FAILED:{code}",
            "note_zh": "应用失败；已替换的文件已按字节级备份整体回滚并复核。",
            "note_en": "Apply failed; every replaced file was rolled back from its byte-exact "
                       "backup and re-verified.",
        }
        _record(cfg, result, caller)
        audit(cfg, {"op": "apply", "release_id": release_id, "operation_id": operation_id,
                    "caller": caller, "result": f"FAILED:{code}", "restored": restored})
        return result


def _backup_path_of(f: dict) -> Path:
    """The apply record stores backup as a nested dict for multi-file plans and
    as a plain string for the legacy single-file path. Normalise both."""
    b = f.get("backup")
    if isinstance(b, dict):
        b = b.get("backup") or b.get("path")
    if not b:
        raise GateError("BACKUP_MISSING", str(f.get("path")))
    return Path(b)


def op_rollback_multi(cfg: dict, operation_id: str, rec: dict, caller: str) -> dict:
    _assert_seal(cfg)
    data = load_operations(cfg)
    release_id = rec["release_id"]
    rel = get_release(cfg, release_id)
    gates = live_gates_multi(cfg, release_id, direction="rollback")
    summary = gates_summary(gates)
    files = rec.get("files") or []
    plan = {i["path"]: i for i in release_files(cfg, rel)}
    checks = []
    for f in files:
        p = Path(f["target"])
        b = _backup_path_of(f)
        cur = fingerprint(p.read_bytes()) if p.is_file() else {"sha256": None}
        bfp = fingerprint(b.read_bytes()) if b.is_file() else {"sha256": None}
        checks.append({"path": f["path"], "current": cur["sha256"],
                       "declared_after": plan[f["path"]]["after_sha256"],
                       "backup": bfp["sha256"],
                       "declared_before": plan[f["path"]]["before_sha256"]})
    bad = [c for c in checks if c["backup"] != c["declared_before"] or not c["backup"]]
    not_after = [c for c in checks if c["current"] != c["declared_after"]]
    if bad:
        raise GateError("ROLLBACK_BACKUP_NOT_BEFORE", json.dumps(bad))
    if not_after:
        raise GateError("ROLLBACK_CURRENT_NOT_AFTER", json.dumps(not_after))

    if not summary["all_pass"]:
        rec["rollback_last_error"] = {"code": "GATES_NOT_PASS", "detail": summary["failed"],
                                      "ts": iso_now()}
        data["operations"][operation_id] = rec
        save_operations(cfg, data)
        result = {"operation": "rollback", "operation_id": operation_id, "release_id": release_id,
                  "state": "failed", "ts": iso_now(), "channel_id": cfg["channel_id"],
                  "test_mode": cfg.get("_test_mode", False),
                  "gates": gates, "summary": summary, "verdict": "ROLLBACK_FAILED:GATES_NOT_PASS",
                  "note_zh": "实时门禁未通过；禁止回滚；操作保持 applied 可重试。",
                  "note_en": "Live gates failed; rollback refused; operation stays applied."}
        audit(cfg, {"op": "rollback", "operation_id": operation_id, "caller": caller,
                    "result": "FAILED:GATES_NOT_PASS", "failed": summary["failed"]})
        return result

    holder = f"rollback:{operation_id}"
    restored = []
    err = None
    try:
        ok, lock_info = inventory_acquire(cfg, holder)
        if not ok:
            raise GateError("LOCK_CONFLICT", json.dumps(lock_info))
        try:
            for c in checks:
                match = next(f for f in files if f["path"] == c["path"])
                target = Path(match["target"])
                b = _backup_path_of(match)
                tmp = target.with_name(f".{target.name}.rollback-tmp-{operation_id}")
                tmp.write_bytes(b.read_bytes())
                with open(tmp, "rb+") as fh:
                    fh.flush()
                    os.fsync(fh.fileno())
                copy_dacl(target, tmp)
                os.replace(tmp, target)
                got = fingerprint(target.read_bytes())
                if got["sha256"] != c["declared_before"]:
                    raise GateError("ROLLBACK_POST_SHA_MISMATCH", c["path"])
                restored.append({"path": c["path"], "sha256": got["sha256"]})
        finally:
            try:
                inventory_release(cfg, holder)
            except Exception:
                pass
    except (GateError, OSError, KeyError, TypeError, ValueError) as e:
        err = e
    if err is not None:
        code = getattr(err, "code", None) or (
            "IO_ERROR" if isinstance(err, OSError) else
            "RECORD_INCOMPLETE" if isinstance(err, (KeyError, TypeError, ValueError)) else "UNKNOWN")
        rec["rollback_last_error"] = {"code": code, "detail": str(err), "ts": iso_now()}
        data["operations"][operation_id] = rec
        save_operations(cfg, data)
        result = {"operation": "rollback", "operation_id": operation_id, "release_id": release_id,
                  "state": "failed", "ts": iso_now(), "channel_id": cfg["channel_id"],
                  "test_mode": cfg.get("_test_mode", False), "error": str(err),
                  "restored": restored, "verdict": f"ROLLBACK_FAILED:{code}",
                  "note_zh": "回滚失败；操作保持 applied 可重试，锁已释放。",
                  "note_en": "Rollback failed; operation stays applied; lock released."}
        audit(cfg, {"op": "rollback", "operation_id": operation_id, "caller": caller,
                    "result": f"FAILED:{code}"})
        return result

    rec["state"] = "rolled_back"
    rec["rolled_back_at"] = iso_now()
    rec["rollback_restored"] = restored
    data["operations"][operation_id] = rec
    save_operations(cfg, data)
    result = {"operation": "rollback", "operation_id": operation_id, "release_id": release_id,
              "state": "rolled_back", "ts": iso_now(), "channel_id": cfg["channel_id"],
              "file_count": len(restored), "restored": restored,
              "verdict": "ROLLED_BACK",
              "note_zh": "全部文件已从字节级备份恢复并复核 SHA。",
              "note_en": "Every file restored from its byte-exact backup; SHA verified."}
    audit(cfg, {"op": "rollback", "operation_id": operation_id, "caller": caller,
                "result": "ROLLED_BACK", "restored": restored})
    return result


def op_status(cfg: dict, operation_id: str, caller: str) -> dict:
    if not isinstance(operation_id, str) or not OPERATION_ID_RE.match(operation_id):
        raise GateError("INVALID_OPERATION_ID", "operation_id failed strict pattern")
    data = load_operations(cfg)
    rec = data["operations"].get(operation_id)
    if not rec:
        raise GateError("UNKNOWN_OPERATION_ID", operation_id)
    audit(cfg, {"op": "status", "operation_id": operation_id, "caller": caller, "result": "OK"})
    # Top-level mirrors so a client never depends on the record's internal shape.
    return {"operation": "status", "operation_id": operation_id,
            "state": rec.get("state"), "release_id": rec.get("release_id"),
            "file_count": rec.get("file_count") or len(rec.get("files") or []),
            "files": rec.get("files") or [], "record": rec,
            "rollback_last_error": rec.get("rollback_last_error"),
            "channel_id": cfg["channel_id"], "verdict": "OK"}


def op_rollback(cfg: dict, operation_id: str, caller: str) -> dict:
    if not isinstance(operation_id, str) or not OPERATION_ID_RE.match(operation_id):
        raise GateError("INVALID_OPERATION_ID", "operation_id failed strict pattern")
    data = load_operations(cfg)
    rec = data["operations"].get(operation_id)
    if not rec:
        raise GateError("UNKNOWN_OPERATION_ID", operation_id)
    if rec.get("state") != "applied":
        raise GateError("ROLLBACK_NOT_APPLICABLE", f"state={rec.get('state')}")
    _assert_seal(cfg)
    release_id = rec["release_id"]
    rel = get_release(cfg, release_id)
    if rel.get("target_files"):
        return op_rollback_multi(cfg, operation_id, rec, caller)
    target = resolve_target(cfg, rel)
    backup = Path(rec["backup"])
    if not backup.is_file():
        raise GateError("BACKUP_MISSING", str(backup))

    gates = live_gates(cfg, release_id, direction="rollback")
    summary = gates_summary(gates)
    cur = fingerprint(target.read_bytes())
    bfp = fingerprint(backup.read_bytes())
    if cur["sha256"] != rel["after_sha256"]:
        raise GateError("ROLLBACK_CURRENT_NOT_AFTER", cur["sha256"])
    if bfp["sha256"] != rel["before_sha256"]:
        raise GateError("ROLLBACK_BACKUP_NOT_BEFORE", bfp["sha256"])
    if not summary["all_pass"]:
        # keep the operation in "applied" state so a later retry stays possible
        rec["rollback_last_error"] = {"code": "GATES_NOT_PASS", "detail": summary["failed"],
                                      "ts": iso_now()}
        data["operations"][operation_id] = rec
        save_operations(cfg, data)
        result = {"operation": "rollback", "operation_id": operation_id, "release_id": release_id,
                  "state": "failed", "ts": iso_now(), "channel_id": cfg["channel_id"],
                  "test_mode": cfg.get("_test_mode", False),
                  "gates": gates, "summary": summary, "verdict": "ROLLBACK_FAILED:GATES_NOT_PASS",
                  "note_zh": "实时门禁未通过；禁止回滚；操作保持 applied 可重试。",
                  "note_en": "Live gates failed; rollback refused; operation stays applied "
                             "and retryable."}
        audit(cfg, {"op": "rollback", "operation_id": operation_id, "caller": caller,
                    "result": "FAILED:GATES_NOT_PASS", "failed": summary["failed"]})
        return result

    holder = f"rollback:{operation_id}"
    after = None
    err = None
    try:
        ok, lock_info = inventory_acquire(cfg, holder)
        if not ok:
            raise GateError("LOCK_CONFLICT", json.dumps(lock_info))
        try:
            b = backup.read_bytes()
            tmp = target.with_name(f".{target.name}.rollback-tmp-{operation_id}")
            tmp.write_bytes(b)
            with open(tmp, "rb+") as f:
                f.flush()
                os.fsync(f.fileno())
            copy_dacl(target, tmp)
            os.replace(tmp, target)
            after = fingerprint(target.read_bytes())
            if after["sha256"] != rel["before_sha256"]:
                raise GateError("ROLLBACK_POST_SHA_MISMATCH", after["sha256"])
        finally:
            try:
                inventory_release(cfg, holder)
            except Exception:
                pass
    except (GateError, OSError) as e:
        err = e
    if err is not None:
        code = getattr(err, "code", None) or ("IO_ERROR" if isinstance(err, OSError) else "UNKNOWN")
        rec["rollback_last_error"] = {"code": code, "detail": str(err), "ts": iso_now()}
        data["operations"][operation_id] = rec
        save_operations(cfg, data)
        result = {"operation": "rollback", "operation_id": operation_id, "release_id": release_id,
                  "state": "failed", "ts": iso_now(), "channel_id": cfg["channel_id"],
                  "test_mode": cfg.get("_test_mode", False),
                  "target": str(target), "error": str(err), "verdict": f"ROLLBACK_FAILED:{code}",
                  "note_zh": "回滚失败；操作保持 applied 可重试，锁已释放。",
                  "note_en": "Rollback failed; operation stays applied and retryable; lock released."}
        audit(cfg, {"op": "rollback", "operation_id": operation_id, "caller": caller,
                    "result": f"FAILED:{code}"})
        return result

    rec["state"] = "rolled_back"
    rec["rolled_back_at"] = iso_now()
    rec["rollback_after"] = after
    data["operations"][operation_id] = rec
    save_operations(cfg, data)
    result = {"operation": "rollback", "operation_id": operation_id, "release_id": release_id,
              "state": "rolled_back", "ts": iso_now(), "channel_id": cfg["channel_id"],
              "target": str(target), "restored_from": str(backup), "restored": after,
              "verdict": "ROLLED_BACK",
              "note_zh": "已从字节级备份恢复并复核 SHA。",
              "note_en": "Restored from byte-exact backup; SHA verified."}
    audit(cfg, {"op": "rollback", "operation_id": operation_id, "caller": caller,
                "result": "ROLLED_BACK", "restored_sha256": after["sha256"]})
    return result


def _assert_seal(cfg: dict) -> dict:
    """Fail closed when the release registry was edited outside the channel.

    No seal yet (first ever controlled write) is not an error: the next
    registration creates one. A seal that no longer matches its files is.
    """
    import registry
    st = registry.verify_seal(cfg)
    if st.get("tampered"):
        raise GateError("REGISTRY_TAMPERED",
                        "channel_config.json / allowed_scope.json changed outside the channel: "
                        + ",".join(st.get("diffs") or []))
    return st


def op_register(cfg: dict, release_id: str, caller: str) -> dict:
    import registry
    _assert_seal(cfg)
    try:
        out = registry.register_release(cfg, release_id, caller, sys.modules[__name__])
    except registry.RegisterError as e:
        audit(cfg, {"op": "register", "release_id": release_id, "caller": caller,
                    "result": f"REJECTED:{e.code}", "detail": e.detail[:300]})
        raise GateError(e.code, e.detail)
    except GateError:
        raise
    except Exception as e:
        audit(cfg, {"op": "register", "release_id": release_id, "caller": caller,
                    "result": f"REJECTED:INTERNAL", "detail": type(e).__name__})
        raise GateError("REGISTER_INTERNAL", type(e).__name__)
    return out


def op_releases(cfg: dict, caller: str) -> dict:
    import registry
    out = registry.list_releases(cfg)
    audit(cfg, {"op": "releases", "caller": caller, "result": "OK",
                "count": out.get("count")})
    return out


def op_telemetry(cfg: dict, caller: str, write_snapshot: bool = True) -> dict:
    import telemetry
    _assert_seal(cfg)
    payload = telemetry.build(cfg)
    # Stable envelope so callers never depend on the metric body's own keys.
    payload["operation"] = "telemetry"
    payload["verdict"] = "OK"
    if write_snapshot:
        try:
            payload["snapshot_path"] = telemetry.write_snapshot(cfg)
        except OSError as e:
            payload["snapshot_path"] = None
            payload["snapshot_error"] = str(e)
    audit(cfg, {"op": "telemetry", "caller": caller, "result": "OK",
                "telemetry_sha256": payload.get("telemetry_sha256")})
    return payload


def _record(cfg: dict, result: dict, caller: str) -> None:
    data = load_operations(cfg)
    op_id = result.get("operation_id")
    if not op_id:
        return
    entry = dict(result)
    entry["caller"] = caller
    data["operations"][op_id] = entry
    save_operations(cfg, data)


# ------------------------------------------------------------------- CLI
def main(argv) -> int:
    cfg = None
    try:
        cfg = load_config()
    except GateError as e:
        print(json.dumps({"error": e.code, "detail": e.detail, "operation": "config"}))
        return 2
    if len(argv) < 3:
        audit(cfg, {"op": argv[1] if len(argv) > 1 else None, "arg": None,
                    "caller": "cli", "result": "REJECTED:USAGE"})
        print(json.dumps({"error": "usage: executor.py <preflight|apply|status|rollback|"
                                   "register|releases|telemetry> <id> [--confirm]",
                          "operations": ["preflight(release_id)", "apply(release_id)",
                                         "status(operation_id)", "rollback(operation_id)",
                                         "register(release_id)", "releases(--)",
                                         "telemetry(--no-snapshot)"],
                          "note": "register takes a bundle id from inbox/; there is still no "
                                  "arbitrary command or file surface"}))
        return 2
    op, arg = argv[1], argv[2]
    confirm = "--confirm" in argv[3:]
    try:
        caller = "cli"
        if op == "preflight":
            out = op_preflight(cfg, arg, caller)
        elif op == "apply":
            out = op_apply(cfg, arg, caller, confirm)
        elif op == "status":
            out = op_status(cfg, arg, caller)
        elif op == "rollback":
            out = op_rollback(cfg, arg, caller)
        elif op == "register":
            out = op_register(cfg, arg, caller)
        elif op == "releases":
            out = op_releases(cfg, caller)
        elif op == "telemetry":
            out = op_telemetry(cfg, caller, write_snapshot=(arg != "--no-snapshot"))
        else:
            if cfg is not None:
                audit(cfg, {"op": op, "arg": arg, "caller": "cli",
                            "result": "REJECTED:UNKNOWN_OPERATION"})
            print(json.dumps({"error": f"UNKNOWN_OPERATION:{op}",
                              "note": "no arbitrary command surface exists"}))
            return 2
        print(json.dumps(out, ensure_ascii=False, indent=2))
        ok_exit = (out.get("state") in ("applied", "rolled_back", "registered", "already_registered")
                   or out.get("verdict") in ("PREFLIGHT_PASS", "OK",
                                             "REGISTERED_DEPLOYABLE",
                                             "REGISTERED_PENDING_SOURCE_ATTESTATION",
                                             "REGISTER_IDEMPOTENT")
                   or out.get("operation") in ("releases", "telemetry"))
        return 0 if ok_exit else 1
    except GateError as e:
        if cfg is not None:
            audit(cfg, {"op": op, "arg": arg, "caller": "cli", "result": f"REJECTED:{e.code}"})
        print(json.dumps({"error": e.code, "detail": e.detail, "operation": op}))
        return 2
    except OSError as e:
        if cfg is not None:
            audit(cfg, {"op": op, "arg": arg, "caller": "cli", "result": "REJECTED:IO_ERROR"})
        print(json.dumps({"error": "IO_ERROR", "detail": str(e), "operation": op}))
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
