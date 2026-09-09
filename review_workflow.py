"""Shared, database-backed review workflow used by both the local web UI and CLI."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from lead_hygiene_gate import evaluate_a0
from production_adapter import build_candidate_from_db_row, build_context


def now_shanghai() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()


def _is_contact_form(lead: dict) -> bool:
    return lead.get('status') == 'contact_form_pool' or bool(lead.get('contact_form_url')) and not lead.get('email')


def _audit(conn, lead, previous_status, new_status, action, reviewer, reason, hygiene, source_channel, request_id):
    conn.execute("""INSERT INTO review_log
        (action_id, lead_id, previous_status, new_status, decision, reviewer, reason_code, reason_detail,
         reviewed_at, hygiene_result, request_id, evidence_url, source_channel, whether_auto_sendable, whether_manual_sendable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), lead['id'], previous_status, new_status, action, reviewer,
          lead.get('review_reason_code', ''), reason, now_shanghai(), json.dumps(hygiene), request_id,
          lead.get('evidence_url', ''), source_channel, int(bool(hygiene.get('auto_sendable'))),
          int(bool(hygiene.get('manual_sendable')))))


def _hygiene(conn, lead: dict) -> tuple[bool, list[str]]:
    candidate = build_candidate_from_db_row(lead, build_context(conn))
    decision = evaluate_a0(candidate)
    return decision.a0_eligible, list(decision.reasons)


def apply_review_action(conn: sqlite3.Connection, lead_id: int, action: str, reviewer: str,
                        reason: str = '', request_id: str | None = None, next_review_at: str = '') -> dict:
    """Apply one audited action. No action creates a Final Send Plan or sends email."""
    if action not in {'approve_auto', 'approve_manual', 'reject', 'defer', 'recheck_official', 'recheck_facebook'}:
        return {'ok': False, 'error': 'unsupported_action'}
    request_id = request_id or str(uuid.uuid4())
    if conn.execute('SELECT 1 FROM review_log WHERE request_id=?', (request_id,)).fetchone():
        return {'ok': False, 'error': 'duplicate_request'}
    row = conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
    if not row:
        return {'ok': False, 'error': 'lead_not_found'}
    lead = dict(row)
    previous_status = lead.get('review_status') or lead.get('status') or 'pending'
    contact_form = _is_contact_form(lead)
    hygiene_ok, hygiene_reasons = _hygiene(conn, lead)
    hygiene = {'passed': hygiene_ok, 'reasons': hygiene_reasons, 'auto_sendable': False, 'manual_sendable': False}

    if action == 'approve_auto':
        if contact_form:
            return {'ok': False, 'error': 'contact_form_cannot_be_approved_for_email'}
        if not hygiene_ok:
            return {'ok': False, 'error': 'hygiene_failed', 'reasons': hygiene_reasons}
        hygiene['auto_sendable'] = True
        conn.execute("""UPDATE leads SET status='new', confidence_score='A', review_status='approved_auto',
            manual_decision='approved_auto', auto_sendable=1, manual_sendable=0, review_updated_at=?,
            last_checked_at=? WHERE id=?""", (now_shanghai(), now_shanghai(), lead_id))
        _audit(conn, lead, previous_status, 'approved_auto', action, reviewer, reason, hygiene, 'review', request_id)
        return {'ok': True, 'new_status': 'approved_auto', 'auto_sendable': True}

    if action == 'approve_manual':
        if contact_form or not lead.get('email'):
            return {'ok': False, 'error': 'contact_form_cannot_be_approved_for_manual_email'}
        # Manual permission still cannot ignore a suppressed, bounced, or already-sent recipient.
        blocking = {'suppressed', 'bounced', 'already_sent'}
        if any(reason_name in blocking or 'bounce' in reason_name for reason_name in hygiene_reasons):
            return {'ok': False, 'error': 'manual_send_hygiene_failed', 'reasons': hygiene_reasons}
        hygiene['manual_sendable'] = True
        conn.execute("""UPDATE leads SET status='approved_manual_send', review_status='approved_manual',
            manual_decision='approved_manual_send', auto_sendable=0, manual_sendable=1,
            review_updated_at=?, last_checked_at=? WHERE id=?""", (now_shanghai(), now_shanghai(), lead_id))
        conn.execute("""INSERT INTO manual_send_queue (lead_id, status, approved_at, reviewer, reason)
            VALUES (?, 'pending_manual_action', ?, ?, ?)
            ON CONFLICT(lead_id) DO UPDATE SET status='pending_manual_action', approved_at=excluded.approved_at,
            reviewer=excluded.reviewer, reason=excluded.reason""", (lead_id, now_shanghai(), reviewer, reason))
        _audit(conn, lead, previous_status, 'approved_manual', action, reviewer, reason, hygiene, 'review', request_id)
        return {'ok': True, 'new_status': 'approved_manual', 'manual_sendable': True}

    if action == 'reject':
        if not reason.strip():
            return {'ok': False, 'error': 'rejection_reason_required'}
        conn.execute("""UPDATE leads SET status='review_rejected', review_status='rejected', manual_decision='rejected',
            auto_sendable=0, manual_sendable=0, review_updated_at=? WHERE id=?""", (now_shanghai(), lead_id))
        _audit(conn, lead, previous_status, 'rejected', action, reviewer, reason, hygiene, 'review', request_id)
        return {'ok': True, 'new_status': 'rejected'}

    if action == 'defer':
        if not reason.strip() or not next_review_at.strip():
            return {'ok': False, 'error': 'defer_reason_and_next_review_at_required'}
        conn.execute("""UPDATE leads SET review_status='deferred', manual_decision='deferred', defer_reason=?,
            next_review_at=?, auto_sendable=0, manual_sendable=0, review_updated_at=? WHERE id=?""",
            (reason, next_review_at, now_shanghai(), lead_id))
        _audit(conn, lead, previous_status, 'deferred', action, reviewer, reason, hygiene, 'review', request_id)
        return {'ok': True, 'new_status': 'deferred'}

    source = 'official_site' if action == 'recheck_official' else 'facebook'
    conn.execute("""UPDATE leads SET review_status='recheck_pending', recheck_pending=?, review_updated_at=?
        WHERE id=?""", (source, now_shanghai(), lead_id))
    _audit(conn, lead, previous_status, 'recheck_pending', action, reviewer, reason, hygiene, source, request_id)
    return {'ok': True, 'new_status': 'recheck_pending', 'source_channel': source}
