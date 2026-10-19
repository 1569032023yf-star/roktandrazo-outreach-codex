"""Phase 5A fail-closed operational evidence and cross-batch SMTP budgets.

No production transport or authorization creation lives here. Read evidence from
an operator-installed policy; never infer evidence from a candidate or environment flag.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from contextlib import closing

POLICY_PATH = Path(__file__).resolve().parent / "data" / "phase5a_send_policy.json"
SH = timezone(timedelta(hours=8))
CAPS = {1: 5, 2: 10, 3: 20, 4: 40}
CLAIMS = ("products_and_24_in_1", "low_moq_ddp_samples", "ten_years_experience",
          "custom_card_puzzle_paper_packaging", "flexible_production_runs")
LIVE_EVIDENCE = ("unsubscribe_receiving", "suppression_processing", "spf", "dkim", "dmarc",
    "sender_identity", "tls", "v6_three_template_test", "mx_control", "feedback_monitoring",
    "supported_unique_send_chain")


def load_policy():
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        if not isinstance(policy, dict):
            raise ValueError("policy must be an object")
        return policy
    except (OSError, ValueError) as exc:
        raise ValueError("SEND_RESUMPTION_BLOCKED:POLICY_UNAVAILABLE") from exc


def require_content_evidence(policy):
    if policy.get("authorization_scope") != "phase5a-v6-controlled-resumption":
        raise ValueError("SEND_RESUMPTION_BLOCKED:WRONG_AUTHORIZATION_SCOPE")
    if policy.get("postal_address_verified") is not True or not policy.get("postal_address_evidence"):
        raise ValueError("SEND_RESUMPTION_BLOCKED:POSTAL_ADDRESS_UNVERIFIED")
    address = str(policy.get("verified_postal_address") or "").strip()
    if len(address) < 12 or any(x in address.upper() for x in ("VERIFIED_BUSINESS_POSTAL_ADDRESS", "PLACEHOLDER", "EXAMPLE", "TODO", "HTTP")):
        raise ValueError("SEND_RESUMPTION_BLOCKED:POSTAL_ADDRESS_MISSING")
    if any((policy.get("verified_claims") or {}).get(k) is not True for k in CLAIMS):
        raise ValueError("SEND_RESUMPTION_BLOCKED:BUSINESS_CLAIMS_UNVERIFIED")


def _time(value):
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        raise ValueError("EVIDENCE_TIMEZONE_REQUIRED")
    return dt


def require_ready(policy, now=None, *, testing=False, actual_from=None, test_recipient=None):
    require_content_evidence(policy)
    now = now or datetime.now(SH)
    if policy.get("follow_up_enabled") is not False:
        raise ValueError("SEND_RESUMPTION_BLOCKED:FOLLOW_UP_MUST_BE_DISABLED")
    if policy.get("emergency_stop") is not False:
        raise ValueError("SEND_RESUMPTION_BLOCKED:EMERGENCY_STOP")
    if policy.get("risk_signals") != []:
        raise ValueError("SEND_RESUMPTION_BLOCKED:RISK_SIGNALS_NOT_CLEAR")
    if actual_from is not None and (not actual_from or actual_from.casefold() != str(policy.get("verified_from_email") or "").casefold()):
        raise ValueError("SEND_RESUMPTION_BLOCKED:SENDER_IDENTITY_MISMATCH")
    evidence = policy.get("evidence") or {}
    required = ("sender_identity", "tls", "unsubscribe_receiving", "suppression_processing") if testing else LIVE_EVIDENCE
    for key in required:
        ev = evidence.get(key) or {}
        if ev.get("passed") is not True or not ev.get("reference"):
            raise ValueError("SEND_RESUMPTION_BLOCKED:EVIDENCE_MISSING:" + key)
        age = now - _time(ev.get("checked_at"))
        if age < timedelta(0) or age > timedelta(hours=24):
            raise ValueError("SEND_RESUMPTION_BLOCKED:EVIDENCE_STALE:" + key)
    if testing:
        owned = {str(x).casefold() for x in policy.get("controlled_test_recipients", [])}
        if not test_recipient or test_recipient.casefold() not in owned:
            raise ValueError("SEND_RESUMPTION_BLOCKED:TEST_RECIPIENT_NOT_CONTROLLED")
        return 0
    if policy.get("enabled") is not True or policy.get("pilot_completed") is True:
        raise ValueError("SEND_RESUMPTION_BLOCKED:NOT_ACTIVE")
    stage = policy.get("stage")
    if isinstance(stage, bool) or stage not in CAPS:
        raise ValueError("SEND_RESUMPTION_BLOCKED:INVALID_STAGE")
    for previous in range(1, stage):
        review = (policy.get("stage_feedback") or {}).get(str(previous)) or {}
        if review.get("passed") is not True or not review.get("reference"):
            raise ValueError("SEND_RESUMPTION_BLOCKED:STAGE_FEEDBACK_REQUIRED")
        start, checked = _time(review.get("started_at")), _time(review.get("reviewed_at"))
        if checked > now or start > checked or checked - start < timedelta(hours=24):
            raise ValueError("SEND_RESUMPTION_BLOCKED:FEEDBACK_CYCLE_TOO_SHORT")
    if policy.get("daily_cap") != CAPS[stage]:
        raise ValueError("SEND_RESUMPTION_BLOCKED:CAP_MISMATCH")
    return CAPS[stage]


def used_slots(conn, business_date):
    """Count sent FSPs plus durable reservations, including ambiguous SMTP outcomes."""
    ids = {r[0] for r in conn.execute("SELECT id FROM final_send_plan WHERE message_type='new_outreach' AND outreach_batch_date=? AND status='sent'", (business_date,))}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase5a_send_reservations'").fetchone():
        ids.update(r[0] for r in conn.execute("SELECT plan_entry_id FROM phase5a_send_reservations WHERE business_date=?", (business_date,)))
    return len(ids)


def halt_new_outreach(db_path, reason):
    """Durable stop; clearing it requires a reviewed operations action, never retry."""
    with closing(sqlite3.connect(db_path, timeout=10)) as conn, conn:
        conn.execute("CREATE TABLE IF NOT EXISTS phase5a_send_halts (reason TEXT, created_at TEXT)")
        conn.execute("INSERT INTO phase5a_send_halts VALUES (?,?)", (reason, datetime.now(SH).isoformat()))


def check_halt(conn):
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase5a_send_halts'").fetchone():
        if conn.execute("SELECT 1 FROM phase5a_send_halts LIMIT 1").fetchone():
            raise ValueError("SEND_RESUMPTION_BLOCKED:DURABLE_EMERGENCY_HALT")


def reserve_smtp(db_path, entry_id, org_key, business_date, policy, now=None):
    """Reserve BEFORE connecting. A crash/ambiguous response cannot free a quota slot.

    Serializes competing workers across all batches. This append-only safety
    ledger does not create/alter send_authorizations or bypass existing history gates.
    """
    now = now or datetime.now(SH)
    cap = require_ready(policy, now)
    if not isinstance(entry_id, int) or isinstance(entry_id, bool) or not org_key:
        raise ValueError("SEND_RESUMPTION_BLOCKED:RESERVATION_IDENTITY_REQUIRED")
    if business_date != now.astimezone(SH).date().isoformat() or now.astimezone(SH).weekday() >= 5:
        raise ValueError("SEND_RESUMPTION_BLOCKED:BUSINESS_DATE_OR_WEEKEND")
    with closing(sqlite3.connect(db_path, timeout=10)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        check_halt(conn)
        conn.execute("""CREATE TABLE IF NOT EXISTS phase5a_send_reservations (
            plan_entry_id INTEGER PRIMARY KEY, business_date TEXT NOT NULL,
            organization_key TEXT NOT NULL UNIQUE, reserved_at TEXT NOT NULL)""")
        row = conn.execute("SELECT p.status, p.message_type, p.outreach_batch_date, l.organization_key "
            "FROM final_send_plan p JOIN leads l ON l.id=p.lead_id WHERE p.id=?", (entry_id,)).fetchone()
        if not row or tuple(row) != ("planned", "new_outreach", business_date, org_key):
            raise ValueError("SEND_RESUMPTION_BLOCKED:PLAN_CHANGED")
        if policy["stage"] == 1 and conn.execute("SELECT COUNT(*) FROM phase5a_send_reservations").fetchone()[0] >= 5:
            raise ValueError("SEND_RESUMPTION_BLOCKED:PILOT_FEEDBACK_REQUIRED")
        if used_slots(conn, business_date) >= cap:
            raise ValueError("SEND_RESUMPTION_BLOCKED:DAILY_CAP")
        try:
            conn.execute("INSERT INTO phase5a_send_reservations VALUES (?,?,?,?)", (entry_id, business_date, org_key, now.isoformat()))
        except sqlite3.IntegrityError as exc:
            raise ValueError("SEND_RESUMPTION_BLOCKED:ORG_OR_PLAN_ALREADY_RESERVED") from exc


def remaining_plan_capacity(conn, business_date, policy):
    cap = require_ready(policy)
    check_halt(conn)
    remaining = max(0, cap - used_slots(conn, business_date))
    if policy["stage"] == 1 and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='phase5a_send_reservations'").fetchone():
        remaining = min(remaining, max(0, 5 - conn.execute("SELECT COUNT(*) FROM phase5a_send_reservations").fetchone()[0]))
    return remaining
