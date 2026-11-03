"""Fixed-schema, read-only production observability for Codex.

Design rules (enforced here, not by convention):
  * every database handle is opened ``mode=ro``; this module never writes;
  * parameters are validated against a closed allowlist and bounded ranges,
    so no caller-supplied string ever reaches SQL as text;
  * payloads are counters / states / timestamps / fingerprints only -- store
    names, emails, domains, addresses and phones are never selected;
  * a whole-payload redaction assert fails closed if a forbidden key appears;
  * unavailable evidence is reported as ``NOT_RECORDED`` / ``UNKNOWN`` with a
    reason.  Nothing is inferred into a zero.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))
SCHEMA_RUNTIME = "rokt.runtime.v1"
SCHEMA_CITY = "rokt.city.v1"
SCHEMA_PROVIDER = "rokt.provider_audit.v1"
SCHEMA_SCHEDULER = "rokt.scheduler.v1"
SCHEMA_SAFE = "rokt.safe_authority.v1"

RUN_ID_RE = re.compile(r"^[A-Za-z0-9:_\-]{1,80}$")
FORBIDDEN_KEYS = frozenset({
    "business_name", "normalized_business_name", "email", "linked_email", "website",
    "normalized_domain", "formatted_address", "normalized_address", "phone",
    "normalized_phone", "raw_payload_json", "payload", "token", "password", "secret",
    "source_query", "evidence_url", "evidence_snippet",
})
NET_ERROR_CLASSES = (
    ("website_resolution:network_retry:", "network_retry"),
    ("website_resolution:network_error:", "network_error"),
    ("website_resolution:not_found:", "not_found"),
)


# ── primitives ────────────────────────────────────────────────────────────
def _ro(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % str(path).replace("\\", "/"), uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []


def _one(conn, sql, params=()):
    r = _rows(conn, sql, params)
    return r[0] if r else None


def _scalar(conn, sql, params=(), default=None):
    r = _one(conn, sql, params)
    if r is None:
        return default
    try:
        return list(r)[0]
    except Exception:
        return default


def _now_iso() -> str:
    return datetime.now(CST).replace(microsecond=0).isoformat()


def _utc_naive_to_cst(value):
    """``job_runs.started_at`` is naive UTC; render it in the business timezone."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace(" ", "T"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(CST).isoformat()


def _iso_to_cst(value):
    """ISO-8601 with explicit offset (provider audit) -> business timezone."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CST).isoformat()


def _epochms_to_cst(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000.0, CST).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _age_hours(iso: str | None):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return round((datetime.now(CST) - dt).total_seconds() / 3600.0, 2)


def _sha_file(path: Path) -> dict:
    try:
        data = path.read_bytes()
    except OSError:
        return {"sha256": None, "bytes": None, "mtime": None}
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            "mtime": datetime.fromtimestamp(path.stat().st_mtime, CST).isoformat()}


def _error_class(reason: str | None) -> str:
    text = str(reason or "")
    for prefix, label in NET_ERROR_CLASSES:
        if text.startswith(prefix):
            return label
    if not text:
        return "none"
    return "other"


def assert_redacted(payload, path="payload") -> None:
    """Fail closed if any forbidden (customer-identifying) key leaked."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if str(k).lower() in FORBIDDEN_KEYS:
                raise ValueError("REDACTION_VIOLATION %s.%s" % (path, k))
            assert_redacted(v, "%s.%s" % (path, k))
    elif isinstance(payload, list):
        for i, v in enumerate(payload):
            assert_redacted(v, "%s[%d]" % (path, i))


# ── parameter validation (closed allowlist) ───────────────────────────────
def _param_run_id(params) -> str | None:
    v = (params or {}).get("run_id")
    if v in (None, ""):
        return None
    v = str(v)
    if not RUN_ID_RE.match(v):
        raise ValueError("BAD_PARAM run_id")
    return v


def _param_range(params, name, default, lo, hi) -> int:
    v = (params or {}).get(name)
    if v in (None, ""):
        return default
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError("BAD_PARAM %s" % name)
    if n < lo or n > hi:
        raise ValueError("BAD_PARAM %s_range" % name)
    return n


def _resolve_city(conn, params) -> sqlite3.Row | None:
    """Only an integer id (1..9999) or an exact name from the queue is accepted."""
    raw = (params or {}).get("city")
    if raw in (None, ""):
        return _one(conn, "SELECT * FROM retail_city_queue WHERE status='active' ORDER BY priority, id LIMIT 1")
    text = str(raw).strip()
    if text.isdigit():
        nid = int(text)
        if not 1 <= nid <= 9999:
            raise ValueError("BAD_PARAM city_range")
        return _one(conn, "SELECT * FROM retail_city_queue WHERE id=?", (nid,))
    if len(text) > 64 or not re.match(r"^[A-Za-z .'\-]+$", text):
        raise ValueError("BAD_PARAM city")
    return _one(conn, "SELECT * FROM retail_city_queue WHERE city=? LIMIT 1", (text,))


# ── A1: inventory runtime detail ──────────────────────────────────────────
def _rrule_seconds(rrule: str) -> int:
    m = re.search(r"INTERVAL=(\d+)", str(rrule or ""))
    n = int(m.group(1)) if m else 1
    n = max(1, min(n, 168))
    if "HOURLY" in str(rrule or ""):
        return n * 3600
    if "DAILY" in str(rrule or ""):
        return n * 86400
    return n * 3600


def _firings(cfg: dict, limit: int) -> dict:
    """Automation trigger receipts for the canonical Inventory automation."""
    wb = cfg["production"]["workbuddy_db_path"]
    aid = cfg["inventory_automation_id"]
    out = {"automation_id": aid, "interval_seconds": None, "next_run_at": None,
           "runtime_last_run_at": None, "firings": [], "source": "workbuddy.db:automation_runs",
           "note": "planned_at is DERIVED from the previous firing's completion + rrule interval "
                   "(the scheduler anchors hourly rules to the completion moment); the raw "
                   "historical next_run_at is overwritten on every run and is NOT_RECORDED."}
    try:
        conn = _ro(wb)
    except sqlite3.Error as e:
        out["error"] = "AUTOMATION_DB_UNAVAILABLE: %s" % e
        return out
    try:
        a = _one(conn, "SELECT rrule, next_run_at, status FROM automations WHERE id=? AND deleted_at IS NULL", (aid,))
        if a:
            out["interval_seconds"] = _rrule_seconds(a["rrule"])
            out["next_run_at"] = _epochms_to_cst(a["next_run_at"])
            out["automation_status"] = a["status"]
        rs = _one(conn, "SELECT last_run_at, last_error, running FROM automation_runtime_state WHERE automation_id=?", (aid,))
        if rs:
            out["runtime_last_run_at"] = _epochms_to_cst(rs["last_run_at"])
            out["runtime_last_error"] = rs["last_error"]
            out["runtime_running"] = bool(rs["running"])
        rows = _rows(conn,
                     "SELECT thread_id, status, result_success, created_at, updated_at, failure_code, reason_code "
                     "FROM automation_runs WHERE automation_id=? ORDER BY created_at DESC LIMIT ?",
                     (aid, limit))
        firings = []
        for r in rows:
            firings.append({
                "firing_id": r["thread_id"],
                "triggered_at": _epochms_to_cst(r["created_at"]),
                "completed_at": _epochms_to_cst(r["updated_at"]),
                "trigger_epoch_ms": r["created_at"],
                "automation_status": r["status"],
                "automation_result_success": bool(r["result_success"]),
                "automation_failure_code": r["failure_code"],
                "automation_reason_code": r["reason_code"],
            })
        for i, f in enumerate(firings):
            prev = firings[i + 1] if i + 1 < len(firings) else None
            iv = out["interval_seconds"]
            if prev and iv:
                try:
                    prev_done = datetime.fromisoformat(prev["completed_at"])
                    trig = datetime.fromisoformat(f["triggered_at"])
                    planned = prev_done + timedelta(seconds=iv)
                    gap = (trig - prev_done).total_seconds()
                    f["planned_at"] = planned.isoformat()
                    f["planned_basis"] = "DERIVED_PREVIOUS_COMPLETION_PLUS_INTERVAL"
                    f["trigger_drift_seconds"] = round((trig - planned).total_seconds(), 1)
                    f["cycle_gap_seconds"] = round(gap, 1)
                    f["skipped_slots_between"] = max(0, int(round(gap / iv)) - 1)
                except Exception:
                    f["planned_at"] = None
                    f["planned_basis"] = "NOT_RECORDED"
                    f["trigger_drift_seconds"] = None
                    f["cycle_gap_seconds"] = None
                    f["skipped_slots_between"] = None
            else:
                f["planned_at"] = None
                f["planned_basis"] = "NOT_RECORDED"
                f["trigger_drift_seconds"] = None
                f["cycle_gap_seconds"] = None
                f["skipped_slots_between"] = None
            f["executed"] = False
            f["run_id"] = None
            f["execution_evidence"] = "NO_RUN_ROW_IN_TRIGGER_WINDOW"
            f.pop("trigger_epoch_ms", None)
        out["firings"] = firings
    finally:
        conn.close()
    return out


def runtime_detail(cfg: dict, params=None) -> dict:
    limit = _param_range(params, "limit", 10, 1, 50)
    run_id = _param_run_id(params)
    db = cfg["production"]["db_path"]
    root = Path(cfg["production"]["root"])
    bd_today = datetime.now(CST).strftime("%Y-%m-%d")
    lock_key = cfg["lock"]["key_prefix"] + bd_today

    conn = _ro(db)
    try:
        if run_id:
            rows = _rows(conn, "SELECT * FROM job_runs WHERE run_id=? LIMIT 1", (run_id,))
        else:
            rows = _rows(conn, "SELECT * FROM job_runs ORDER BY started_at DESC LIMIT ?", (limit,))
        runs = []
        for r in rows:
            d = dict(r)
            started = _utc_naive_to_cst(d.get("started_at"))
            finished = _utc_naive_to_cst(d.get("finished_at"))
            dur = None
            try:
                if d.get("started_at") and d.get("finished_at"):
                    a = datetime.fromisoformat(str(d["started_at"]).replace(" ", "T"))
                    b = datetime.fromisoformat(str(d["finished_at"]).replace(" ", "T"))
                    dur = round((b - a).total_seconds(), 1)
            except ValueError:
                dur = None
            runs.append({
                "run_id": d.get("run_id"),
                "stage": d.get("stage"),
                "business_date": d.get("business_date"),
                "status": d.get("status"),
                "stop_reason": d.get("stop_reason") or "NOT_RECORDED",
                "current_step": d.get("current_step"),
                "current_step_note": "written once at run start; the orchestrator does not "
                                     "checkpoint intermediate stages in this column",
                "target": d.get("target"),
                "actual": d.get("actual"),
                "gap": d.get("gap"),
                "error_class": _error_class(d.get("error")),
                "error_present": bool(d.get("error")),
                "dry_run": bool(d.get("dry_run")),
                "process_id": d.get("process_id"),
                "process_started_at": started,
                "process_finished_at": finished,
                "process_duration_seconds": dur,
                "trigger_id": cfg["inventory_automation_id"] if d.get("stage") == "inventory" else "NOT_RECORDED",
                "entrypoint": "bd_orchestrator.py",
                "entrypoint_fingerprint": _sha_file(root / "bd_orchestrator.py"),
            })
        lock_val = _scalar(conn, "SELECT value FROM system_config WHERE key=?", (lock_key,))
        lock_acq = _scalar(conn, "SELECT value FROM system_config WHERE key=?", (lock_key + "_acquired_at",))
        lock_state = "RELEASED" if str(lock_val) == "released" else (
            "ACQUIRED" if lock_val else "NO_LOCK_KEY_TODAY")
        running = _scalar(conn, "SELECT COUNT(*) FROM job_runs WHERE finished_at IS NULL AND stage='inventory'",
                          default=None)
        runs_2h = _scalar(conn,
                          "SELECT COUNT(*) FROM job_runs WHERE stage='inventory' "
                          "AND started_at >= datetime('now','-2 hours')", default=None)
        runs_24h = _scalar(conn,
                           "SELECT COUNT(*) FROM job_runs WHERE stage='inventory' "
                           "AND started_at >= datetime('now','-24 hours')", default=None)
        integrity = _scalar(conn, "PRAGMA quick_check", default="unknown")
    finally:
        conn.close()

    firings = _firings(cfg, min(limit * 2, 50))
    # join trigger receipts to job_runs by window [triggered_at, completed_at + 5 min]
    for f in firings.get("firings", []):
        f["executed"] = False
        f["run_id"] = None
        f["execution_evidence"] = "NO_RUN_ROW_IN_TRIGGER_WINDOW"
        try:
            t0 = datetime.fromisoformat(f["triggered_at"])
            t1 = datetime.fromisoformat(f["completed_at"]) + timedelta(seconds=300)
        except Exception:
            continue
        for r in runs:
            ps = r.get("process_started_at")
            if not ps:
                continue
            try:
                pdt = datetime.fromisoformat(ps)
            except ValueError:
                continue
            if t0 <= pdt <= t1:
                f["executed"] = True
                f["run_id"] = r["run_id"]
                f["execution_evidence"] = "JOB_RUNS_ROW_IN_TRIGGER_WINDOW"
                break

    payload = {
        "schema": SCHEMA_RUNTIME,
        "generated_at": _now_iso(),
        "business_timezone": "Asia/Shanghai (+08)",
        "source": "bd_leads.db:job_runs + system_config(run_lock) + workbuddy.db:automation_runs",
        "code": {"bd_orchestrator.py": _sha_file(root / "bd_orchestrator.py")},
        "db": {"path_basename": Path(db).name, "quick_check": integrity},
        "lock": {"key": lock_key, "value": lock_val, "acquired_at": lock_acq, "state": lock_state},
        "runs": runs,
        "running_inventory_now": running,
        "inventory_runs_last_2h": runs_2h,
        "inventory_runs_last_24h": runs_24h,
        "trigger_receipts": firings,
        "field_notes": {
            "planned_vs_triggered_vs_started": "planned_at (derived) != triggered_at (scheduler receipt) "
                                               "!= process_started_at (job_runs, UTC->+08)",
            "unrecorded": "stage-level events (activate_next_city / run_places_batch / staging postprocess / "
                          "completion checks) are NOT persisted per run; current_step only holds the first "
                          "step. Reported as NOT_RECORDED rather than reconstructed from source.",
        },
    }
    assert_redacted(payload)
    return payload


# ── A2/A3: city stage + completion conditions ─────────────────────────────
def _retry_state(raw_json: str | None) -> dict:
    try:
        data = json.loads(str(raw_json or "{}"))
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for key in ("website_resolution_retry", "linked_backlog_retry"):
        blk = data.get(key)
        if isinstance(blk, dict):
            out[key] = {
                "kind": key,
                "attempts": blk.get("attempts", blk.get("unavailable_attempts")),
                "failure_events": len(blk.get("failures") or []),
                "status": blk.get("status"),
                "next_retry_at": _iso_to_cst(blk.get("next_retry_at")),
                "last_failure_at": _iso_to_cst(blk.get("last_failure_at")),
                "terminal_outcome": blk.get("automation_terminal_outcome"),
            }
    return out


def city_detail(cfg: dict, params=None) -> dict:
    db = cfg["production"]["db_path"]
    root = Path(cfg["production"]["root"])
    conn = _ro(db)
    try:
        city = _resolve_city(conn, params)
        active_state = _scalar(conn, "SELECT value FROM system_config WHERE key='active_discovery_state'")
        active_state_row = _scalar(conn, "SELECT value FROM system_config WHERE key='active_city_state'")
        if not city:
            payload = {"schema": SCHEMA_CITY, "generated_at": _now_iso(),
                       "business_timezone": "Asia/Shanghai (+08)",
                       "resolved_city": None, "reason": "NO_MATCHING_CITY_ROW",
                       "active_discovery_state": active_state,
                       "active_city_state_config": active_state_row}
            assert_redacted(payload)
            return payload
        c = dict(city)
        cid = int(c["id"])
        provider = c.get("active_provider") or "browser_maps"

        families = []
        try:
            sys.path.insert(0, str(root))
            import retail_city_queue as rcq  # read-only module: SELECTs only
        except Exception as e:  # pragma: no cover - defensive
            rcq = None
            families_error = "CITY_RULESET_IMPORT_FAILED: %s" % e
        else:
            families_error = None

        if rcq is not None:
            all_fams = list(rcq.RETAIL_QUERY_FAMILIES)
            rows = _rows(conn,
                         "SELECT query_family, status, page_cursor, pages_processed, completed_at "
                         "FROM lead_discovery_query_state WHERE active_city_id=? AND provider=?",
                         (cid, provider))
            by_fam = {r["query_family"]: dict(r) for r in rows}
            for fam in all_fams:
                r = by_fam.get(fam)
                families.append({
                    "query_family": fam,
                    "status": (r or {}).get("status", "NOT_STARTED"),
                    "pages_processed": (r or {}).get("pages_processed"),
                    "completed_at": _iso_to_cst((r or {}).get("completed_at")),
                })
            fam_total = len(all_fams)
            fam_done = sum(1 for f in families if f["status"] == "completed")
            try:
                checks = rcq.city_completion_checks(conn, cid, provider)
                all_met = bool(rcq.all_city_completion_conditions_met(checks))
                ruleset_error = None
            except Exception as e:
                checks = {k: None for k in sorted(rcq._COMPLETION_KEYS)}
                all_met = False
                ruleset_error = "COMPLETION_CHECK_FAILED: %s" % e
        else:
            fam_total = fam_done = None
            checks = {}
            all_met = False
            ruleset_error = families_error

        status_rows = _rows(conn,
                            "SELECT validation_status, COUNT(*) AS n FROM lead_discovery_results "
                            "WHERE active_city_id=? GROUP BY validation_status ORDER BY n DESC", (cid,))
        by_status = {r["validation_status"]: r["n"] for r in status_rows}
        pending_states = ("validation_pending", "history_check_pending",
                          "website_lookup_pending", "email_extraction_pending")
        pending_refs = []
        for r in _rows(conn,
                       "SELECT id, validation_status, rejection_reason, discovered_at, raw_payload_json "
                       "FROM lead_discovery_results WHERE active_city_id=? AND validation_status IN "
                       "('validation_pending','history_check_pending','website_lookup_pending',"
                       "'email_extraction_pending') ORDER BY id LIMIT 40", (cid,)):
            retry = _retry_state(r["raw_payload_json"])
            one_retry = retry.get("website_resolution_retry") or retry.get("linked_backlog_retry")
            pending_refs.append({
                "ref": "ldr:%d" % int(r["id"]),
                "validation_status": r["validation_status"],
                "error_class": _error_class(r["rejection_reason"]),
                "discovered_at": _iso_to_cst(r["discovered_at"]),
                "age_hours": _age_hours(_iso_to_cst(r["discovered_at"])),
                "retry": one_retry or None,
            })
        due = [p["retry"]["next_retry_at"] for p in pending_refs
               if isinstance(p.get("retry"), dict) and p["retry"].get("next_retry_at")]
        next_retry = sorted(due)[0] if due else None
        exhausted = sum(1 for p in pending_refs if isinstance(p.get("retry"), dict)
                        and p["retry"].get("terminal_outcome") == "network_retry_exhausted")

        # Official blocking attribution: which rows keep `no_open_work` false.
        blocking = {"staged_pending_refs": [p["ref"] for p in pending_refs],
                    "retryable_manual_review_refs": [], "linked_backlog_retry_refs": [],
                    "auto_recovery_deferred_refs": [], "candidate_rows_scanned": None,
                    "evaluator": "production retail_city_queue helpers "
                                 "(_manual_review_retryable / _linked_backlog_retryable / "
                                 "automatic_recovery_deferred)",
                    "available": rcq is not None}
        if rcq is not None:
            try:
                cand = _rows(conn,
                             "SELECT d.*, l.email AS linked_email, l.status AS linked_status, "
                             "l.review_status AS linked_review_status, "
                             "l.review_reason_code AS linked_review_reason_code, "
                             "l.review_reason_detail AS linked_review_reason_detail "
                             "FROM lead_discovery_results d LEFT JOIN leads l ON l.id=d.linked_lead_id "
                             "WHERE d.active_city_id=?", (cid,))
                blocking["candidate_rows_scanned"] = len(cand)
                for row in cand:
                    d = dict(row)
                    ref = "ldr:%d" % int(d["id"])
                    if rcq.automatic_recovery_deferred(d):
                        blocking["auto_recovery_deferred_refs"].append(ref)
                        continue
                    if rcq._manual_review_retryable(d):
                        blocking["retryable_manual_review_refs"].append(ref)
                    if rcq._linked_backlog_retryable(d):
                        blocking["linked_backlog_retry_refs"].append(ref)
                for key in ("retryable_manual_review_refs", "linked_backlog_retry_refs",
                            "auto_recovery_deferred_refs", "staged_pending_refs"):
                    blocking[key + "_count"] = len(blocking[key])
                    blocking[key] = blocking[key][:20]
            except Exception as e:
                blocking["error"] = "BLOCKING_ATTRIBUTION_FAILED: %s" % e

        audit = _one(conn,
                     "SELECT COUNT(*) AS n, MAX(requested_at) AS last FROM provider_request_audit "
                     "WHERE active_city_id=?", (cid,))
        nxt = _one(conn,
                   "SELECT id, city, status, priority FROM retail_city_queue WHERE id<>? AND status IN "
                   "('pending','QUEUED') ORDER BY priority, id LIMIT 1", (cid,))
        payload = {
            "schema": SCHEMA_CITY,
            "generated_at": _now_iso(),
            "business_timezone": "Asia/Shanghai (+08)",
            "source": "bd_leads.db:retail_city_queue + lead_discovery_query_state + "
                      "lead_discovery_results + provider_request_audit + system_config; "
                      "completion rules from production retail_city_queue.city_completion_checks",
            "ruleset": {"provider": provider,
                        "module": "retail_city_queue.py",
                        "module_fingerprint": _sha_file(root / "retail_city_queue.py"),
                        "discovery_fingerprint": _sha_file(root / "discovery" / "discovery_service.py"),
                        "import_error": families_error,
                        "evaluation_error": ruleset_error},
            "city": {
                "city_id": cid,
                "city": c.get("city"),
                "state": c.get("state"),
                "city_status": c.get("status"),
                "priority": c.get("priority"),
                "started_at": c.get("started_at"),
                "completed_at": c.get("completed_at"),
                "completion_reason": c.get("completion_reason"),
                "pages_processed": c.get("pages_processed"),
                "results_seen": c.get("results_seen"),
                "consecutive_pages_without_new_place": c.get("consecutive_pages_without_new_place"),
                "resume_state": c.get("resume_state"),
                "web_directory_status": c.get("web_directory_status"),
                "last_success_at": c.get("last_success_at"),
                "last_error_class": _error_class(c.get("last_error")),
            },
            "active_discovery_state": active_state,
            "active_city_state_config": active_state_row,
            "query_families": {
                "total": fam_total,
                "completed": fam_done,
                "remaining": (fam_total - fam_done) if (fam_total is not None and fam_done is not None) else None,
                "detail": families,
            },
            "records": {
                "by_validation_status": by_status,
                "total": sum(by_status.values()),
                "pending_states_total": sum(by_status.get(s, 0) for s in pending_states),
                "website_lookup_pending": by_status.get("website_lookup_pending", 0),
                "network_retry_pending": sum(1 for p in pending_refs
                                             if p["error_class"] in ("network_retry", "network_error")),
                "retry_exhausted": exhausted,
                "next_retry_due_at": next_retry,
            },
            "pending_items": pending_refs,
            "blocking_attribution": blocking,
            "completion_checks": {k: checks.get(k) for k in sorted(checks)},
            "completion_checks_all_met": all_met,
            "next_city": {"city_id": nxt["id"], "city": nxt["city"], "status": nxt["status"],
                          "priority": nxt["priority"],
                          "activatable": bool(nxt and str(nxt["status"]).lower() in ("pending", "queued"))} if nxt else None,
            "provider_audit": {"requests": int(audit["n"]) if audit else 0,
                               "last_requested_at": _iso_to_cst(audit["last"]) if audit else None},
            "stage_events": {
                "available": False,
                "reason": "NOT_RECORDED: the orchestrator persists no per-run stage event log. "
                          "Durable proxies only: lead_discovery_query_state (discovery), "
                          "provider_request_audit (provider calls), retail_city_queue counters. "
                          "No stage trace is reconstructed from source code.",
                "observable_proxies": {
                    "entered_stage_inventory": "job_runs.stage='inventory'",
                    "resolved_active_discovery_state": active_state,
                    "activate_next_city": "retail_city_queue.started_at of the active row",
                    "run_places_batch": "provider_request_audit rows dated inside the run window",
                    "run_staging_postprocess": "lead_discovery_results.validation_status transitions "
                                               "(not timestamped per run)",
                    "city_completion_check": "completion_checks (current truth, not historical)",
                },
            },
        }
        assert_redacted(payload)
        return payload
    finally:
        conn.close()


# ── A4: provider request audit ────────────────────────────────────────────
def provider_audit(cfg: dict, params=None) -> dict:
    hours = _param_range(params, "hours", 24, 1, 168)
    db = cfg["production"]["db_path"]
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    conn = _ro(db)
    try:
        city = _resolve_city(conn, params)
        cid = int(city["id"]) if city else None
        sql = ("SELECT provider, query_family, status, error, result_count, request_count, requested_at "
               "FROM provider_request_audit WHERE requested_at >= ?")
        args = [since]
        if cid is not None:
            sql += " AND active_city_id=?"
            args.append(cid)
        rows = _rows(conn, sql, tuple(args))
        per_provider: dict[str, dict] = {}
        for r in rows:
            p = per_provider.setdefault(str(r["provider"]), {
                "provider": r["provider"], "requests": 0, "success": 0, "failed": 0,
                "timeout": 0, "rate_limited": 0, "last_requested_at": None, "audit_rows": 0})
            p["audit_rows"] += 1
            p["requests"] += int(r["request_count"] or 0)
            p["last_requested_at"] = max(filter(None, [p["last_requested_at"],
                                                       _iso_to_cst(r["requested_at"])]), default=None)
            st = str(r["status"] or "").lower()
            err = str(r["error"] or "").lower()
            if st in ("ok", "success", "completed"):
                p["success"] += 1
            else:
                p["failed"] += 1
            if "timeout" in err or "timed out" in err:
                p["timeout"] += 1
            if "429" in err or "rate" in err or "quota" in err or "restricted" in err:
                p["rate_limited"] += 1
        runs_in_window = 0
        for r in _rows(conn, "SELECT run_id FROM job_runs WHERE stage='inventory' "
                             "AND started_at >= datetime('now','-%d hours')" % hours):
            runs_in_window += 1
        fam_total = fam_done = None
        query_complete = None
        if cid is not None and city is not None:
            prov = city["active_provider"] or "browser_maps"
            rows2 = _rows(conn, "SELECT status FROM lead_discovery_query_state "
                                "WHERE active_city_id=? AND provider=?", (cid, prov))
            fam_total = len(rows2)
            fam_done = sum(1 for r in rows2 if r["status"] == "completed")
            query_complete = bool(fam_total) and fam_done == fam_total
        if rows:
            verdict = "REAL_REQUESTS"
            basis = "provider_request_audit rows present in window"
        elif query_complete:
            verdict = "ZERO_REQUESTS_CONFIRMED"
            basis = ("no audit row in window AND all query families for the city/provider are "
                     "already completed, so discovery had no request to issue")
        else:
            verdict = "UNKNOWN_NO_RECORD"
            basis = ("no audit row in window but the query matrix is not exhausted, so absence of "
                     "an audit row does not prove zero provider calls")
        payload = {
            "schema": SCHEMA_PROVIDER,
            "generated_at": _now_iso(),
            "business_timezone": "Asia/Shanghai (+08)",
            "window_hours": hours,
            "window_start_utc": since + "+00:00",
            "city_id": cid,
            "source": "bd_leads.db:provider_request_audit + job_runs + lead_discovery_query_state",
            "verdict": verdict,
            "verdict_basis": basis,
            "audit_rows": len(rows),
            "per_provider": sorted(per_provider.values(), key=lambda x: x["provider"]),
            "inventory_runs_in_window": runs_in_window,
            "query_matrix": {"total": fam_total, "completed": fam_done, "exhausted": query_complete},
            "distinction": {"zero_real_requests": "ZERO_REQUESTS_CONFIRMED",
                            "no_evidence": "UNKNOWN_NO_RECORD"},
        }
        assert_redacted(payload)
        return payload
    finally:
        conn.close()


# ── C: scheduler reconciliation ───────────────────────────────────────────
def _service_state(name: str = "BDExecutionHost") -> dict:
    """Read-only SCM query via the Windows API. No service control, no shell."""
    out = {"name": name, "status": "UNKNOWN", "start_type": "UNKNOWN",
           "method": "Read-only SCM QueryServiceStatusEx + registry Start value; "
                     "no start/stop/delete, no schtasks/sc.exe shell-out"}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Services\%s" % name, 0, winreg.KEY_READ) as k:
            out["start_type"] = {2: "AUTO_START", 3: "MANUAL", 4: "DISABLED"}.get(
                winreg.QueryValueEx(k, "Start")[0], "UNKNOWN")
    except OSError as e:
        out["registry_error"] = str(e)
    try:
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi.OpenSCManagerW.restype = ctypes.c_void_p
        advapi.OpenSCManagerW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
        advapi.OpenServiceW.restype = ctypes.c_void_p
        advapi.OpenServiceW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
        advapi.QueryServiceStatus.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        advapi.CloseServiceHandle.argtypes = [ctypes.c_void_p]

        class SERVICE_STATUS(ctypes.Structure):
            _fields_ = [("dwServiceType", ctypes.c_ulong), ("dwCurrentState", ctypes.c_ulong),
                        ("dwControlsAccepted", ctypes.c_ulong), ("dwWin32ExitCode", ctypes.c_ulong),
                        ("dwServiceSpecificExitCode", ctypes.c_ulong), ("dwCheckPoint", ctypes.c_ulong),
                        ("dwWaitHint", ctypes.c_ulong)]

        h = advapi.OpenSCManagerW(None, None, 0x0001)  # SC_MANAGER_CONNECT
        if not h:
            out["scm_error"] = "OpenSCManagerW err=%s" % ctypes.get_last_error()
        else:
            s = advapi.OpenServiceW(h, name, 0x0004)  # SERVICE_QUERY_STATUS
            if not s:
                out["scm_error"] = "OpenServiceW err=%s" % ctypes.get_last_error()
            else:
                st = SERVICE_STATUS()
                if advapi.QueryServiceStatus(s, ctypes.byref(st)):
                    out["status_raw"] = int(st.dwCurrentState)
                    out["status"] = {1: "STOPPED", 2: "START_PENDING", 3: "STOP_PENDING",
                                     4: "RUNNING", 5: "CONTINUE_PENDING",
                                     6: "PAUSE_PENDING", 7: "PAUSED"}.get(st.dwCurrentState, "UNKNOWN")
                else:
                    out["scm_error"] = "QueryServiceStatus err=%s" % ctypes.get_last_error()
                advapi.CloseServiceHandle(s)
            advapi.CloseServiceHandle(h)
    except Exception as e:  # pragma: no cover - platform guard
        out["scm_error"] = str(e)
    return out


def scheduler_reconciliation(cfg: dict, params=None) -> dict:
    hours = _param_range(params, "hours", 48, 1, 168)
    runtime = runtime_detail(cfg, {"limit": 20})
    receipts = runtime["trigger_receipts"]
    firings = receipts.get("firings", [])
    iv = receipts.get("interval_seconds")
    now = datetime.now(CST)

    window_start = now - timedelta(hours=hours)
    in_window = []
    for f in firings:
        try:
            t = datetime.fromisoformat(f["triggered_at"])
        except Exception:
            continue
        if t >= window_start:
            in_window.append(f)

    # Pairwise slot reconciliation.
    #
    # The scheduler re-anchors an HOURLY rule on the *completion* of the previous
    # run, so the cadence drifts with run duration and an absolute grid can never
    # match.  The honest model is: planned(next) = completed(previous) + interval.
    # A gap materially longer than one interval means one or more slots were
    # skipped between two real receipts.
    matched = 0
    drifts = []
    skipped_total = 0
    skipped_detail = []
    for f in in_window:
        if f.get("planned_at") and f.get("trigger_drift_seconds") is not None:
            matched += 1
            drifts.append(f["trigger_drift_seconds"])
            sk = f.get("skipped_slots_between")
            if isinstance(sk, int) and sk > 0:
                skipped_total += sk
                skipped_detail.append({"before_trigger": f["triggered_at"],
                                       "planned_at": f["planned_at"],
                                       "gap_seconds": f.get("cycle_gap_seconds"),
                                       "skipped_slots": sk})
    try:
        newest = datetime.fromisoformat(in_window[0]["completed_at"])
        pending_slot = newest + timedelta(seconds=iv) if iv else None
    except Exception:
        pending_slot = None
    next_run_at = receipts.get("next_run_at")
    next_run_lag_seconds = None
    if pending_slot and next_run_at:
        try:
            next_run_lag_seconds = round(
                (datetime.fromisoformat(next_run_at) - pending_slot).total_seconds(), 1)
        except Exception:
            next_run_lag_seconds = None

    executed = sum(1 for f in in_window if f.get("executed"))
    blocked = [f for f in in_window if not f.get("executed")]

    # Uniqueness of the Inventory driver.
    #
    # Prompt text alone is not proof (the read-only SAFE checkpoint also mentions
    # bd_orchestrator.py).  So every ACTIVE automation that references the
    # orchestrator is classified against an explicit, auditable role table;
    # anything not in the table is UNCLASSIFIED and fails the uniqueness verdict
    # closed instead of being assumed harmless.
    KNOWN_AUTOMATION_ROLES = {
        "75fbacd1-fa43-46ea-8388-1d47647c3f4d": "READ_ONLY_SAFE_CHECKPOINT",
        "automation-1786002601925": "RESULT_RECOVERY_SYNC",
        # read-only evidence refresher: mentions the orchestrator only to forbid running it
        "c6bf1717-a7a6-40c7-a1de-074fab9b6128": "READ_ONLY_EVIDENCE_REFRESH",
    }
    wb = cfg["production"]["workbuddy_db_path"]
    send_ids = set((cfg.get("sending_automation_ids") or {}).values())
    drivers = []
    try:
        conn = _ro(wb)
        try:
            for r in _rows(conn, "SELECT id, name, status, prompt FROM automations WHERE deleted_at IS NULL"):
                aid = r["id"]
                pr = str(r["prompt"] or "")
                referenced = "bd_orchestrator.py" in pr
                if not (referenced or aid == cfg["inventory_automation_id"]
                        or aid in KNOWN_AUTOMATION_ROLES or aid in send_ids):
                    continue
                if aid == cfg["inventory_automation_id"]:
                    role = "INVENTORY"
                elif aid in send_ids:
                    role = "SEND_STAGE"
                else:
                    role = KNOWN_AUTOMATION_ROLES.get(aid, "UNCLASSIFIED")
                drivers.append({"id": aid, "name": r["name"], "status": r["status"],
                                "role": role, "references_orchestrator": referenced,
                                "canonical": aid == cfg["inventory_automation_id"]})
        finally:
            conn.close()
    except sqlite3.Error as e:
        drivers = [{"error": "AUTOMATION_DB_UNAVAILABLE: %s" % e}]
    active_inventory = [d for d in drivers if d.get("status") == "ACTIVE" and d.get("role") == "INVENTORY"]
    active_unclassified = [d for d in drivers
                           if d.get("status") == "ACTIVE" and d.get("role") == "UNCLASSIFIED"]
    service = _service_state()
    uniqueness = {
        "workbuddy_active_inventory_drivers": len(active_inventory),
        "workbuddy_active_unclassified_drivers": len(active_unclassified),
        "workbuddy_drivers": drivers,
        "windows_service": service,
        "scheduled_tasks": {"status": "UNKNOWN",
                            "reason": "schtasks.exe / sc.exe are blocked by host policy; no "
                                      "equivalent read-only enumeration is available from this "
                                      "process, so task-level uniqueness stays UNKNOWN"},
        "verdict": "UNIQUE" if (len(active_inventory) == 1 and not active_unclassified
                                and service.get("status") != "RUNNING") else "NOT_PROVEN",
        "basis": "exactly one ACTIVE non-deleted WorkBuddy automation is classified "
                 "role=INVENTORY, no ACTIVE orchestrator-referencing automation is "
                 "UNCLASSIFIED, and the BDExecutionHost service is not RUNNING; Windows "
                 "scheduled tasks remain UNKNOWN by policy",
    }

    verified = (len(active_inventory) == 1
                and not active_unclassified
                and skipped_total == 0
                and matched >= 2
                and service.get("status") != "RUNNING"
                and receipts.get("automation_status") == "ACTIVE")

    payload = {
        "schema": SCHEMA_SCHEDULER,
        "generated_at": _now_iso(),
        "business_timezone": "Asia/Shanghai (+08)",
        "window_hours": hours,
        "source": "workbuddy.db:automations/automation_runs/automation_runtime_state + "
                  "bd_leads.db:job_runs/system_config + Windows SCM (read-only)",
        "canonical_automation": {
            "id": cfg["inventory_automation_id"],
            "status": receipts.get("automation_status"),
            "rrule": "FREQ=HOURLY;INTERVAL=%d" % (iv // 3600) if iv else "NOT_RECORDED",
            "next_run_at": receipts.get("next_run_at"),
            "runtime_last_run_at": receipts.get("runtime_last_run_at"),
            "runtime_last_error": receipts.get("runtime_last_error"),
            "automations_last_run_at_note": "automations.last_run_at is stale/unreliable; "
                                            "automation_runtime_state.last_run_at is authoritative",
        },
        "reconciliation_model": {
            "method": "PAIRWISE: planned(next) = completed(previous) + rrule interval, because the "
                      "scheduler re-anchors HOURLY rules on run completion, so an absolute grid "
                      "cannot match and would report false misses",
            "tolerance_seconds": 600,
            "receipts_paired": matched,
            "drift_seconds": {"min": min(drifts) if drifts else None,
                              "max": max(drifts) if drifts else None,
                              "avg": round(sum(drifts) / len(drifts), 1) if drifts else None},
            "skipped_slots_total": skipped_total,
            "skipped_slot_detail": skipped_detail,
            "pending_slot": pending_slot.isoformat() if pending_slot else None,
            "next_run_at_vs_pending_slot_seconds": next_run_lag_seconds,
        },
        "matched_slots": matched,
        "missed_inventory_runs_confirmed": skipped_total,
        "firings_in_window": len(in_window),
        "firings_executed_production": executed,
        "firings_without_production_run": len(blocked),
        "firings": in_window,
        "uniqueness": uniqueness,
        "verdict": {
            "inventory_scheduler_verified": bool(verified),
            "expected_vs_actual_reconciled": bool(matched >= 2 and skipped_total == 0),
            "note": "a firing that produced no job_runs row is classified "
                    "firings_without_production_run, NOT automatically a missed firing: the "
                    "agent layer can refuse to execute fail-closed (e.g. network gate).",
        },
    }
    assert_redacted(payload)
    return payload


# ── B: SAFE authority ─────────────────────────────────────────────────────
SAFE_PYTHON_CANDIDATES = (
    r"C:\Users\15690\AppData\Local\Programs\Python\Python313\python.exe",
)


def _safe_interpreter() -> str:
    """The measurement needs dnspython, which the managed 3.13.12 build lacks."""
    env = os.environ.get("PRODOBS_SAFE_PYTHON")
    if env and Path(env).is_file():
        return env
    for cand in SAFE_PYTHON_CANDIDATES:
        if Path(cand).is_file():
            return cand
    return sys.executable


def safe_authority(cfg: dict, params=None) -> dict:
    base = Path(__file__).resolve().parent.parent
    state = Path(cfg["_paths"]["state"])
    path = state / "safe_latest.json"
    refresh = str((params or {}).get("refresh", "")).lower() in ("1", "true", "yes")
    prompt = None
    if refresh:
        launcher = base / "bin" / "safe_measure.py"
        try:
            subprocess.Popen([_safe_interpreter(), str(launcher)],
                             cwd=str(base),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=0x00000008)
            prompt = "MEASUREMENT_STARTED"
        except OSError as e:
            prompt = "MEASUREMENT_START_FAILED: %s" % e
    if not path.is_file():
        payload = {"schema": SCHEMA_SAFE, "generated_at": _now_iso(),
                   "available": False, "refresh_requested": refresh, "refresh_result": prompt,
                   "reason": "NO_SAFE_SNAPSHOT: run /v1/safe?refresh=1 to measure through the "
                             "authoritative path (campaign_eligible_v2 + MX control probe)"}
        assert_redacted(payload)
        return payload
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        payload = {"schema": SCHEMA_SAFE, "generated_at": _now_iso(), "available": False,
                   "reason": "SAFE_SNAPSHOT_UNREADABLE: %s" % e, "refresh_result": prompt}
        assert_redacted(payload)
        return payload
    data.setdefault("schema", SCHEMA_SAFE)
    data.setdefault("measurement_complete",
                    bool(data.get("mx_probe_ok") and isinstance(data.get("safe_unique_orgs"), int)))
    data.setdefault("safe_net_growth", {"h24": "UNKNOWN", "d7": "UNKNOWN"})
    data["available"] = bool(isinstance(data.get("safe_unique_orgs"), int))
    if not data["available"]:
        data.setdefault("failure_reason", "SAFE_NUMBER_ABSENT_IN_SNAPSHOT")
    data["generated_at"] = _now_iso()
    data["refresh_requested"] = refresh
    data["refresh_result"] = prompt
    data["age_hours"] = _age_hours(data.get("measured_at"))
    data["fresh"] = bool(data.get("age_hours") is not None and data["age_hours"] <= 6)
    data["authoritative_route"] = "/v1/safe"
    assert_redacted(data)
    return data


# ── dispatch ──────────────────────────────────────────────────────────────
OPS = {
    "runtime": runtime_detail,
    "city": city_detail,
    "provider_audit": provider_audit,
    "scheduler": scheduler_reconciliation,
    "safe": safe_authority,
}


def dispatch(cfg: dict, op: str, params=None) -> dict:
    fn = OPS.get(op)
    if fn is None:
        raise ValueError("UNKNOWN_OBS_OP %s" % op)
    return fn(cfg, params or {})
