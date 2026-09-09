"""Audited manual official-email submission; never bypasses Strict A0 hygiene."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from history_crosscheck import cross_check, host, normalize_email
from lead_hygiene_gate import evaluate_a0
from production_adapter import build_candidate_from_db_row, build_context

ALLOWED_METHODS = {
    'official_mailto', 'official_contact_page', 'official_about_page', 'official_footer',
    'official_privacy_page', 'official_terms_page', 'official_wholesale_page',
    'official_vendor_page', 'official_partnership_page', 'manual_user_supplied', 'other_official_source',
}


def now_shanghai() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()


def _fetch(url: str) -> str:
    request = Request(url, headers={'User-Agent': 'WorkBuddy-review-verifier/1.0'})
    with urlopen(request, timeout=10) as response:
        return response.read(1_000_000).decode('utf-8', errors='replace')


def submit_manual_email(conn: sqlite3.Connection, lead_id: int, submitted_by: str, *, email: str,
                        evidence_url: str = '', evidence_snippet: str = '', evidence_method: str = '',
                        contact_role: str = '', notes: str = '', page_text: str | None = None,
                        official_website: str = '') -> dict:
    """Validate one email. Remote evidence fetch happens only for this explicit action."""
    lead_row = conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
    if not lead_row:
        return {'ok': False, 'final_status': 'rejected', 'failure_reason': 'lead_not_found'}
    lead = dict(lead_row)
    normalized = normalize_email(email)
    if not normalized:
        return _record(conn, lead, submitted_by, email, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       {}, {}, 'invalid_email', 'invalid_or_multiple_email')
    if evidence_method not in ALLOWED_METHODS:
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       {}, {}, 'pending_official_verification', 'invalid_evidence_method')
    history = cross_check(conn, {**lead, 'email': normalized}, exclude_lead_id=lead_id)
    if history['suppressed'] or history['unsubscribed']:
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'suppressed', 'suppression_or_unsubscribe')
    if history['hard_bounced']:
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'hard_bounced', 'hard_bounce_history')
    if history['previously_sent']:
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'previously_sent', 'historical_new_outreach_send')
    if history['result'] == 'exact_duplicate':
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'duplicate_email', 'email_belongs_to_existing_lead')
    if not evidence_url:
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'pending_official_verification', 'evidence_url_required_for_a0')
    current_website = lead.get('official_website', '')
    supplied_website = official_website.strip()
    verified_website = current_website or supplied_website
    if not verified_website or (current_website and supplied_website and host(current_website) != host(supplied_website)):
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'pending_official_verification', 'official_website_required_or_mismatch')
    if host(evidence_url) != host(verified_website):
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'domain_mismatch_review', 'evidence_url_not_official_domain')
    try:
        text = page_text if page_text is not None else _fetch(evidence_url)
    except Exception as exc:
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'pending_official_verification', f'evidence_fetch_failed:{type(exc).__name__}')
    if normalized not in text.lower() or (evidence_snippet and evidence_snippet.lower() not in text.lower()):
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, {}, 'pending_official_verification', 'email_or_snippet_not_found_on_official_page')
    candidate_row = {**lead, 'official_website': verified_website, 'email': normalized, 'evidence_url': evidence_url, 'evidence_snippet': evidence_snippet,
                     'email_verified_on_official_site': 1,
                     'email_source_type': 'wholesale_vendor_page' if 'wholesale' in evidence_method or 'vendor' in evidence_method else 'official_page_visible',
                     'status': 'new'}
    decision = evaluate_a0(build_candidate_from_db_row(candidate_row, build_context(conn)))
    hygiene = {'passed': decision.a0_eligible, 'reasons': list(decision.reasons)}
    if not decision.a0_eligible:
        status = 'identity_duplicate_new_email' if history['result'] == 'identity_duplicate_new_email' else 'manual_send_only'
        return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                       history, hygiene, status, ';'.join(decision.reasons))
    old_email = lead.get('email', '')
    conn.execute("""INSERT INTO lead_email_history (lead_id, email, email_status, role, evidence_url, evidence_snippet,
        evidence_method, replaced_at, replaced_by, replacement_reason) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (lead_id, old_email, 'replaced' if old_email else 'empty', '', lead.get('evidence_url', ''), lead.get('evidence_snippet', ''),
         lead.get('evidence_method', ''), now_shanghai(), submitted_by, notes))
    conn.execute("""UPDATE leads SET official_website=?, email=?, evidence_url=?, evidence_snippet=?, evidence_method=?, email_source_type=?,
        email_verified_on_official_site=1, email_type=?, manual_found_email=?, manual_email_source_url=?,
        manual_email_source_type=?, manual_decision='promoted_to_strict_a0', manual_verified_by=?, manual_verified_at=?,
        status='new', confidence_score='A', review_status='approved_auto', auto_sendable=1, manual_sendable=0 WHERE id=?""",
        (verified_website, normalized, evidence_url, evidence_snippet, evidence_method, candidate_row['email_source_type'], contact_role,
         normalized, evidence_url, evidence_method, submitted_by, now_shanghai(), lead_id))
    return _record(conn, lead, submitted_by, normalized, evidence_url, evidence_snippet, evidence_method, contact_role, notes,
                   history, hygiene, 'promoted_to_strict_a0', '', promoted=True)


def _record(conn, lead, submitted_by, email, evidence_url, snippet, method, role, notes, history, hygiene, status, failure, promoted=False):
    conn.execute("""INSERT INTO manual_email_submission (id, lead_id, previous_email, submitted_email, submitted_by, submitted_at,
        evidence_url, evidence_snippet, evidence_method, contact_role, notes, history_match_result, hygiene_result, final_status,
        failure_reason, promoted_to_a0_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), lead['id'], lead.get('email', ''), email, submitted_by, now_shanghai(), evidence_url, snippet, method,
         role, notes, json.dumps(history), json.dumps(hygiene), status, failure, now_shanghai() if promoted else None))
    conn.execute("""INSERT INTO review_log (action_id, lead_id, previous_status, new_status, decision, reviewer, reason_code,
        reason_detail, reviewed_at, hygiene_result, request_id, evidence_url, source_channel, whether_auto_sendable, whether_manual_sendable)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), lead['id'], lead.get('review_status') or lead.get('status'), status, 'manual_email_submission', submitted_by,
         lead.get('review_reason_code', ''), failure or status, now_shanghai(), json.dumps(hygiene), str(uuid.uuid4()), evidence_url,
         'web_or_cli', int(promoted), int(status == 'manual_send_only')))
    return {'ok': True, 'final_status': status, 'failure_reason': failure, 'history': history, 'hygiene': hygiene, 'promoted': promoted}
