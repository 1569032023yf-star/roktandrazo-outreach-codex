#!/usr/bin/env python3
"""
BD Manual Review Server — local-only review center.
Uses Python stdlib only. No Flask, no FastAPI.

Only listens on 127.0.0.1. Never exposes to public network.
Port auto-selection if default is occupied.
"""
import argparse
import json
import os
import re
import socket
import sqlite3
import sys
import uuid
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from review_workflow import apply_review_action
from history_crosscheck import cross_check
from manual_email_workflow import submit_manual_email
from review_evidence_workbench import (
    build_review_evidence, recovery_classification, render_facebook_page,
    verify_recovered_website,
)
from bd_ops_api import (
    get_ops_summary, get_today_stats, get_tracking_stats, get_inventory,
    get_search_progress, get_final_plan, get_health, get_data_quality,
    get_schedule_preview_summary,
)
from bd_ops_poller import start_poller, get_state as get_poller_state

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

# Dashboard HTML — loaded from external file
DASHBOARD_HTML_PATH = PROJECT_DIR / 'bd_ops_dashboard.html'
try:
    DASHBOARD_HTML = open(DASHBOARD_HTML_PATH, 'r', encoding='utf-8').read()
except Exception:
    DASHBOARD_HTML = "<html><body><h1>Dashboard file not found</h1></body></html>"

DB_PATH = Path(os.getenv("WORKBUDDY_BD_DB_PATH") or PROJECT_DIR / 'data' / 'bd_leads.db')
LOG_PATH = PROJECT_DIR / 'output' / 'review_action_log.jsonl'
STATUS_PATH = PROJECT_DIR / 'output' / 'review_server_status.json'

PRIMARY_STATES = {'TN', 'AR', 'KY'}
_EVIDENCE_RESULTS = {}
_EVIDENCE_LOCK = threading.Lock()
_EVIDENCE_BUSY = False


def now_cst():
    return datetime.utcnow() + timedelta(hours=8)


def db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        # A second connection against a temp DB can be read-only while the
        # creating connection is still open; the review API should still read.
        pass
    return conn


# ═══════════════════════════════════════════════
# API Handlers
# ═══════════════════════════════════════════════

def api_summary():
    conn = db()
    c = conn.cursor()
    rows = c.execute("""
        SELECT review_reason_code, review_status, COUNT(*) cnt
        FROM leads WHERE review_reason_code IS NOT NULL AND review_reason_code != ''
        GROUP BY review_reason_code, review_status
    """).fetchall()

    summary = {}
    for r in rows:
        code = r[0]
        status = r[1]
        if code not in summary:
            summary[code] = {'pending': 0, 'approved_auto': 0, 'approved_manual': 0, 'rejected': 0, 'deferred': 0}
        if status in summary[code]:
            summary[code][status] += r[2]

    total_pending = sum(s.get('pending', 0) for s in summary.values())
    total_processed = sum(s.get('approved_auto', 0) + s.get('approved_manual', 0) + s.get('rejected', 0) for s in summary.values())

    conn.close()
    return json.dumps({'total_pending': total_pending, 'total_processed': total_processed, 'by_reason': summary,
                       'generated_at': now_cst().isoformat()})


def api_leads(params):
    page = max(1, int(params.get('page', ['1'])[0]))
    per_page = min(100, max(5, int(params.get('per_page', ['25'])[0])))
    reason = params.get('reason', [None])[0]
    status = params.get('status', ['pending'])[0]
    q = params.get('q', [''])[0]
    sort = params.get('sort', ['oldest'])[0]
    priority = params.get('priority', [None])[0]

    conn = db()
    c = conn.cursor()

    where = ["(review_reason_code IS NOT NULL AND review_reason_code != '')"]
    vals = []

    # Only pending by default, but allow all statuses
    if status != 'all':
        where.append("COALESCE(review_status, 'pending') = ?")
        vals.append(status)
    if reason:
        where.append("review_reason_code = ?")
        vals.append(reason)
    if priority:
        where.append("review_priority = ?")
        vals.append(priority)
    if q:
        where.append("(store_name LIKE ? OR city LIKE ? OR email LIKE ?)")
        vals.extend([f'%{q}%', f'%{q}%', f'%{q}%'])

    where_clause = " AND ".join(where)

    # Count
    count_sql = f"SELECT COUNT(*) FROM leads WHERE {where_clause}"
    total = c.execute(count_sql, vals).fetchone()[0]

    # Order
    order_map = {
        'oldest': 'COALESCE(review_created_at, collected_at) ASC',
        'newest': 'COALESCE(review_created_at, collected_at) DESC',
        'priority': "CASE review_priority WHEN 'high' THEN 0 ELSE 1 END, id ASC",
    }
    order_clause = order_map.get(sort, order_map['oldest'])

    offset = (page - 1) * per_page
    data_sql = f"""SELECT id, store_name, store_type, city, state, official_website,
        email, email_source_type, contact_form_url, evidence_url,
        confidence_score, status AS lead_status, review_reason_code,
        review_reason_detail, review_status, review_priority,
        review_created_at, review_updated_at, collected_at, notes, formatted_address, phone
        FROM leads WHERE {where_clause} ORDER BY {order_clause} LIMIT ? OFFSET ?"""

    rows = c.execute(data_sql, vals + [per_page, offset]).fetchall()
    conn.close()

    # Separately fetch FB data for better performance
    lead_ids = [r['id'] for r in rows]
    fb_data = {}
    if lead_ids:
        conn2 = db()
        c2 = conn2.cursor()
        placeholders = ','.join(['?'] * len(lead_ids))
        fb_rows = c2.execute(
            f"SELECT lead_id, fb_check_status, facebook_url, fb_email, fb_evidence_url FROM fb_enrichment_queue WHERE lead_id IN ({placeholders})",
            lead_ids).fetchall()
        for fr in fb_rows:
            fb_data[fr[0]] = {'fb_check_status': fr[1] or '', 'facebook_url': fr[2] or '',
                              'fb_email': fr[3] or '', 'fb_evidence_url': fr[4] or ''}
        conn2.close()

    leads = []
    for r in rows:
        ld = dict(r)
        ld['email_masked'] = _mask_email(ld.get('email'))
        fb = fb_data.get(ld['id'], {})
        ld['fb_check_status'] = fb.get('fb_check_status', '')
        ld['facebook_url'] = fb.get('facebook_url', '')
        ld['fb_email'] = fb.get('fb_email', '')
        ld['fb_evidence_url'] = fb.get('fb_evidence_url', '')
        leads.append(ld)

    return json.dumps({
        'page': page, 'per_page': per_page, 'total': total,
        'pages': max(1, (total + per_page - 1) // per_page),
        'leads': leads,
    }, default=str)


def _mask_email(email):
    if not email or '@' not in email: return 'N/A'
    user, domain = email.split('@')
    if len(user) <= 3: return f'{user[0]}***@{domain}'
    return f'{user[:2]}***@{domain}'


def _review_action(body, action):
    """The web UI shares the CLI's single audited, no-send review workflow."""
    try:
        lead_id = int(body.get('lead_id'))
    except (TypeError, ValueError):
        return json.dumps({'ok': False, 'error': 'lead_id_required'})
    conn = db()
    try:
        with conn:
            result = apply_review_action(
                conn, lead_id, action, reviewer='web', reason=str(body.get('reason', '')),
                request_id=body.get('request_id'), next_review_at=str(body.get('next_review_at', '')),
            )
        return json.dumps(result)
    finally:
        conn.close()


def api_approve(body):
    decision = body.get('decision', 'approve_auto')
    if decision not in {'approve_auto', 'approve_manual'}:
        return json.dumps({'ok': False, 'error': 'invalid_approval_decision'})
    return _review_action(body, decision)


def api_reject(body):
    return _review_action(body, 'reject')


def api_defer(body):
    return _review_action(body, 'defer')


def api_history(lead_id):
    conn = db()
    try:
        row = conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
        if not row:
            return json.dumps({'ok': False, 'error': 'lead_not_found'})
        return json.dumps({'ok': True, 'history': cross_check(conn, dict(row), exclude_lead_id=lead_id)}, default=str)
    finally:
        conn.close()


def api_manual_email(body):
    try:
        lead_id = int(body.get('lead_id'))
    except (TypeError, ValueError):
        return json.dumps({'ok': False, 'error': 'lead_id_required'})
    conn = db()
    try:
        with conn:
            result = submit_manual_email(conn, lead_id, 'web', email=str(body.get('email', '')),
                evidence_url=str(body.get('evidence_url', '')), evidence_snippet=str(body.get('evidence_snippet', '')),
                evidence_method=str(body.get('evidence_method', '')), contact_role=str(body.get('contact_role', '')),
                notes=str(body.get('notes', '')), official_website=str(body.get('official_website', '')))
        return json.dumps(result, default=str)
    finally:
        conn.close()


def api_manual_a0(body):
    """Legacy endpoint retained, but never bypasses verified manual evidence."""
    return api_manual_email(body)


def api_review_evidence(lead_id):
    try:
        lead_id = int(lead_id)
    except (TypeError, ValueError):
        return json.dumps({'ok': False, 'error': 'lead_id_required'})
    conn = db()
    try:
        with _EVIDENCE_LOCK:
            state = dict(_EVIDENCE_RESULTS.get(lead_id) or {})
        evidence = build_review_evidence(conn, lead_id, state.get('facebook'))
        if evidence.get('ok'):
            evidence['recovered_website'] = state.get('recovered_website') or {}
            evidence['browser_job_status'] = state.get('job_status') or 'idle'
        return json.dumps(evidence, default=str)
    finally:
        conn.close()


def _start_evidence_job(lead_id, task):
    """One bounded browser job at a time; the review HTTP handler never waits."""
    global _EVIDENCE_BUSY
    with _EVIDENCE_LOCK:
        if _EVIDENCE_BUSY:
            return json.dumps({'ok': False, 'error': 'evidence_browser_busy'})
        _EVIDENCE_BUSY = True
        _EVIDENCE_RESULTS.setdefault(lead_id, {})['job_status'] = 'running'

    def runner():
        global _EVIDENCE_BUSY
        try:
            key, result = task()
            with _EVIDENCE_LOCK:
                _EVIDENCE_RESULTS.setdefault(lead_id, {})[key] = result
                _EVIDENCE_RESULTS[lead_id]['job_status'] = 'complete'
        except Exception as exc:
            with _EVIDENCE_LOCK:
                _EVIDENCE_RESULTS.setdefault(lead_id, {})['job_status'] = 'error:' + type(exc).__name__
        finally:
            with _EVIDENCE_LOCK:
                _EVIDENCE_BUSY = False

    threading.Thread(target=runner, daemon=True, name='review-evidence-browser').start()
    return json.dumps({'ok': True, 'status': 'running', 'lead_id': lead_id})


def api_fetch_facebook_evidence(body):
    try:
        lead_id = int(body.get('lead_id'))
    except (TypeError, ValueError):
        return json.dumps({'ok': False, 'error': 'lead_id_required'})
    conn = db()
    try:
        row = conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
        if not row:
            return json.dumps({'ok': False, 'error': 'lead_not_found'})
        lead = dict(row)
        recovery = recovery_classification(conn, lead)
        if recovery['value'] == 'NONE':
            return json.dumps({'ok': False, 'error': 'history_blocked', 'reasons': recovery['reasons']})
        queued = conn.execute('SELECT facebook_url FROM fb_enrichment_queue WHERE lead_id=?', (lead_id,)).fetchone()
        fb_url = str((queued[0] if queued else None) or lead.get('facebook_url') or '')
        if not fb_url:
            return json.dumps({'ok': False, 'error': 'no_existing_facebook_business_url'})
    finally:
        conn.close()
    return _start_evidence_job(lead_id, lambda: ('facebook', render_facebook_page(lead, fb_url)))


def api_verify_recovered_website(body):
    try:
        lead_id = int(body.get('lead_id'))
    except (TypeError, ValueError):
        return json.dumps({'ok': False, 'error': 'lead_id_required'})
    with _EVIDENCE_LOCK:
        facebook = dict((_EVIDENCE_RESULTS.get(lead_id) or {}).get('facebook') or {})
    website = facebook.get('public_website') or ''
    if not website or facebook.get('status') != 'opened' or facebook.get('facebook_provenance_tier', '').startswith('TIER_C'):
        return json.dumps({'ok': False, 'error': 'no_strong_recovered_website'})
    conn = db()
    try:
        row = conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
        if not row or recovery_classification(conn, dict(row))['value'] == 'NONE':
            return json.dumps({'ok': False, 'error': 'history_blocked_or_missing'})
        lead = dict(row)
    finally:
        conn.close()
    return _start_evidence_job(lead_id, lambda: ('recovered_website', verify_recovered_website(lead, website)))


def api_evidence_decision(body):
    """Audit a human judgment of Facebook identity; never change lead eligibility."""
    action = str(body.get('action') or '')
    if action not in {'accept_facebook_identity', 'reject_facebook_match'}:
        return json.dumps({'ok': False, 'error': 'invalid_evidence_action'})
    try:
        lead_id = int(body.get('lead_id'))
    except (TypeError, ValueError):
        return json.dumps({'ok': False, 'error': 'lead_id_required'})
    reason = str(body.get('reason') or '').strip()[:300]
    if not reason:
        return json.dumps({'ok': False, 'error': 'reason_required'})
    with _EVIDENCE_LOCK:
        facebook = dict((_EVIDENCE_RESULTS.get(lead_id) or {}).get('facebook') or {})
    if facebook.get('status') != 'opened':
        return json.dumps({'ok': False, 'error': 'no_rendered_evidence'})
    if action == 'accept_facebook_identity' and facebook.get('facebook_provenance_tier', '').startswith('TIER_C'):
        return json.dumps({'ok': False, 'error': 'weak_identity_cannot_be_accepted'})
    conn = db()
    try:
        with conn:
            lead = conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
            if not lead:
                return json.dumps({'ok': False, 'error': 'lead_not_found'})
            before = dict(lead)
            if recovery_classification(conn, before)['value'] == 'NONE' and action == 'accept_facebook_identity':
                return json.dumps({'ok': False, 'error': 'history_blocked'})
            prior = before.get('review_status') or before.get('status') or 'pending'
            conn.execute('''INSERT INTO review_log
                (action_id,lead_id,previous_status,new_status,decision,reviewer,reason_code,reason_detail,
                 reviewed_at,hygiene_result,request_id,evidence_url,source_channel,
                 whether_auto_sendable,whether_manual_sendable)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (str(uuid.uuid4()), lead_id, prior, prior, action, 'web', before.get('review_reason_code') or '',
                 reason, datetime.now().isoformat(), json.dumps({'send_eligibility_changed': False}),
                 str(uuid.uuid4()), facebook.get('facebook_page_url') or '', 'facebook_rendered', 0, 0))
        return json.dumps({'ok': True, 'send_eligibility_changed': False, 'review_status': prior})
    finally:
        conn.close()


def _run_hygiene(c, lead):
    """Re-run hygiene checks. Returns (passed, reasons_list)."""
    email = (lead.get('email') or '').strip()
    state = (lead.get('state') or '').strip()
    store_type = (lead.get('store_type') or '').lower()
    reasons = []

    if not email or '@' not in email:
        reasons.append('no_public_email')

    # Suppression
    suppressed = c.execute("SELECT 1 FROM suppression_list WHERE email=?", (email,)).fetchone()
    if suppressed:
        reasons.append('suppressed')

    # Already sent
    sent = c.execute("SELECT 1 FROM send_log WHERE email=? AND status='sent'", (email,)).fetchone()
    if sent:
        reasons.append('already_sent')

    # Hard bounce
    bounced = c.execute("SELECT 1 FROM bounce_log WHERE email=? AND bounce_type='hard'", (email,)).fetchone()
    if bounced:
        reasons.append('hard_bounce_history')

    # P1.7C: State no longer part of review/email-safety eligibility.
    # (other_state_retail_blocked removed — all states allowed in Review.)

    # Exchange MX block (check if mx_provider exists)
    lead_full = c.execute("SELECT mx_provider FROM leads WHERE id=?", (lead['id'],)).fetchone()
    if lead_full and lead_full[0]:
        mx = lead_full[0].lower()
        if 'exchange' in mx or 'outlook' in mx or 'microsoft' in mx:
            reasons.append('exchange_mx')

    return len(reasons) == 0, reasons


def _jsonl_log(action_id, lead_id, prev_st, new_st, decision, reason, hygiene_ok):
    entry = {
        'action_id': action_id,
        'lead_id': lead_id,
        'previous_status': prev_st,
        'new_status': new_st,
        'decision': decision,
        'reviewer': 'web',
        'reason_code': '',
        'reason_detail': reason,
        'reviewed_at': now_cst().isoformat(),
        'hygiene_result': str(hygiene_ok),
        'request_id': str(uuid.uuid4()),
    }
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def api_fb_queue(body):
    """Queue a single lead for Facebook enrichment check."""
    lead_id = body.get('lead_id')
    if not lead_id:
        return json.dumps({'ok': False, 'error': 'lead_id required'})

    conn = db()
    c = conn.cursor()
    lead = c.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        conn.close()
        return json.dumps({'ok': False, 'error': 'Not found'})

    lead = dict(lead)
    recovery = recovery_classification(conn, lead)
    if recovery['value'] == 'NONE':
        conn.close()
        return json.dumps({'ok': False, 'error': 'history_blocked', 'reasons': recovery['reasons']})
    web = lead.get('official_website', '') or ''
    fb_url = lead.get('facebook_url', '') or ''
    fb_source = 'existing_unverified' if fb_url else ''

    # Check if already queued
    existing = c.execute("SELECT fb_check_status FROM fb_enrichment_queue WHERE lead_id=?", (lead_id,)).fetchone()
    if existing and existing[0] not in ('pending',):
        conn.close()
        return json.dumps({'ok': False, 'error': f'Already checked: {existing[0]}'})

    # Try to find FB link from website if not already known
    if not fb_url and web:
        try:
            import httpx, re as _re
            client = httpx.Client(timeout=10, follow_redirects=True)
            resp = client.get(web)
            if resp.status_code == 200:
                fb_match = _re.findall(
                    r'href=["\']?(https?://(?:www\.)?facebook\.com/(?!login|sharer|share|dialog|plugins)[^"\'> ]+)', 
                    resp.text)
                if fb_match:
                    fb_url = fb_match[0].split('?')[0].split('#')[0]
                    fb_source = 'official_website_link'
                else:
                    social = _re.findall(r'\"sameAs\".*?\"(https?://(?:www\.)?facebook\.com/[^\"]+)\"', resp.text)
                    if social:
                        fb_url = social[0]
                        fb_source = 'jsonld_social_profile'
            client.close()
        except Exception:
            pass

    c.execute('''INSERT OR REPLACE INTO fb_enrichment_queue
        (lead_id, store_name, city, state, official_website, review_reason_code,
         facebook_url, facebook_source, fb_check_status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,'pending',datetime('now'),datetime('now'))''',
        (lead_id, lead.get('store_name',''), lead.get('city',''), lead.get('state',''),
         web, lead.get('review_reason_code',''), fb_url, fb_source if fb_url else ''))

    conn.commit()
    conn.close()
    return json.dumps({'ok': True, 'lead_id': lead_id, 'fb_found': bool(fb_url)})


def api_fb_batch(body):
    """Queue multiple leads for FB check."""
    lead_ids = body.get('lead_ids', [])
    if not lead_ids:
        return json.dumps({'ok': False, 'error': 'lead_ids required'})

    queued = 0
    skipped = 0
    for lid in lead_ids[:25]:
        r = json.loads(api_fb_queue({'lead_id': lid}))
        if r.get('ok'):
            queued += 1
        else:
            skipped += 1
    return json.dumps({'ok': True, 'queued': queued, 'skipped': skipped})


# ═══════════════════════════════════════════════
# HTML Page (inline, single-file)
# ═══════════════════════════════════════════════

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BD 人工审核中心 / Manual Review Center</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Microsoft YaHei,PingFang SC,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px}
h1{font-size:18px;color:#58a6ff;margin-bottom:4px}
.subtitle{font-size:12px;color:#8b949e;margin-bottom:16px}
.summary{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.card{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:12px 16px;min-width:130px;text-align:center}
.card .n{font-size:22px;font-weight:700}
.card .l{font-size:10px;color:#8b949e;margin-top:2px}
.card .le{font-size:9px;color:#484f58;margin-top:1px}
.g{color:#3fb950}.y{color:#d29922}.r{color:#f85149}.b{color:#58a6ff}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center}
.filters select,.filters input,.filters button{background:#21262d;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;padding:4px 10px;font-size:12px}
.filters button{cursor:pointer}
.filters button:hover{background:#30363d}
.btn{padding:5px 10px;border-radius:4px;border:1px solid #30363d;background:#21262d;color:#c9d1d9;cursor:pointer;font-size:11px;margin:1px;white-space:nowrap}
.btn:hover{background:#30363d}
.btn-ap{background:#238636;border-color:#238636;color:#fff}
.btn-ap:hover{background:#2ea043}
.btn-rj{background:#da3633;border-color:#da3633;color:#fff}
.btn-rj:hover{background:#f85149}
.btn-df{background:#9e6a03;color:#fff}
.btn-df:hover{background:#d29922}
.btn-re{background:#1f6feb;color:#fff}
.btn-re:hover{background:#388bfd}
table{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px}
th{text-align:left;padding:8px;background:#21262d;color:#8b949e;position:sticky;top:0;z-index:1}
td{padding:5px 8px;border-bottom:1px solid #21262d;vertical-align:top}
tr:hover{background:#161b22}
.badge{display:inline-block;padding:1px 6px;border-radius:10px;font-size:10px}
.bg-g{background:#238636;color:#fff}.bg-r{background:#da3633;color:#fff}
.bg-y{background:#9e6a03;color:#fff}.bg-b{background:#1f6feb;color:#fff}
.pagination{display:flex;gap:4px;align-items:center;margin-top:12px;font-size:12px}
.pagination button{padding:3px 10px;cursor:pointer;background:#21262d;border:1px solid #30363d;border-radius:4px;color:#c9d1d9}
.pagination button:hover{background:#30363d}
.pagination .active{background:#1f6feb;border-color:#1f6feb}
.pagination span{color:#8b949e}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:100;justify-content:center;align-items:center}
.modal.show{display:flex}
.modal-box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;min-width:360px;max-width:520px}
.modal-box h3{font-size:15px;margin-bottom:12px;color:#58a6ff}
.modal-box textarea{width:100%;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:8px;border-radius:4px;font-size:12px;margin:8px 0;resize:vertical}
.modal-box select{width:100%;background:#21262d;border:1px solid #30363d;color:#c9d1d9;padding:6px;border-radius:4px;margin:8px 0}
.modal-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;margin-top:12px}
.hygiene-fail{background:#3d1c1c;border:1px solid #da3633;border-radius:4px;padding:8px;margin:8px 0;font-size:11px;color:#f85149}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
.detail-row{margin:3px 0;font-size:11px}
.detail-row strong{color:#8b949e}
.lead-name{font-weight:600;color:#c9d1d9}
.lead-meta{font-size:10px;color:#8b949e}
.lead-city{color:#8b949e}
.ev-links{white-space:nowrap}
.ev-links a{font-size:10px;margin-right:4px;padding:1px 4px;border:1px solid #30363d;border-radius:3px}
.ev-links a:hover{background:#21262d;text-decoration:none}
.evidence-box{max-width:900px;width:92vw;max-height:88vh;overflow:auto}
.evidence-section{border-top:1px solid #30363d;padding:10px 0;font-size:12px;line-height:1.5}
.evidence-section h4{color:#58a6ff;margin-bottom:5px}
.gate-grid{display:grid;grid-template-columns:1fr auto;gap:3px 10px}
</style>
</head>
<body>
<h1>BD 人工审核中心 / Manual Review Center</h1>
<div class="subtitle">127.0.0.1 only | {server_start} | Pending / 待审: <span id="totalPending">-</span></div>

<div class="summary" id="summary"></div>

<div class="filters">
  <select id="filterReason" onchange="loadPage(1)"><option value="">All / 全部原因</option></select>
  <select id="filterStatus" onchange="loadPage(1)">
    <option value="pending">Pending / 待审</option><option value="all">All / 全部状态</option>
    <option value="approved_auto">Approved Auto / 已批自动</option><option value="approved_manual">Approved Manual / 已批手动</option>
    <option value="rejected">Rejected / 已拒绝</option><option value="deferred">Deferred / 已延期</option>
  </select>
  <select id="filterSort" onchange="loadPage(1)">
    <option value="oldest">Oldest / 最早优先</option><option value="newest">Newest / 最新优先</option>
    <option value="priority">High Priority / 高优先</option>
  </select>
  <select id="filterPriority" onchange="loadPage(1)">
    <option value="">All Priority / 全部优先级</option><option value="high">High / 高</option><option value="normal">Normal / 普通</option>
  </select>
  <input id="filterQ" placeholder="Search name/city/email... / 搜索" onkeydown="if(event.key==='Enter')loadPage(1)" style="min-width:160px">
  <button onclick="loadPage(1)">Search / 搜索</button>
  <button class="btn" onclick="loadPage(1)">Refresh / 刷新</button>
</div>

<div id="tableContainer"></div>
<div class="pagination" id="pagination"></div>

<div class="modal" id="emailModal"><div class="modal-box">
  <h3>补充官方邮箱 / Add Official Email</h3><div class="detail-row"><strong>ID:</strong> <span id="emailLeadId"></span></div>
  <input id="newOfficialWebsite" placeholder="Official website / 官方网站" style="width:100%;margin:6px 0;padding:7px">
  <input id="newEmail" placeholder="Official email / 官方邮箱" style="width:100%;margin:6px 0;padding:7px">
  <input id="newEvidenceUrl" placeholder="Evidence URL / 证据网址" style="width:100%;margin:6px 0;padding:7px">
  <textarea id="newEvidenceSnippet" rows="2" placeholder="Evidence snippet / 页面证据片段"></textarea>
  <select id="newEvidenceMethod"><option value="official_mailto">official_mailto</option><option value="official_contact_page">official_contact_page</option><option value="official_about_page">official_about_page</option><option value="official_footer">official_footer</option><option value="official_wholesale_page">official_wholesale_page</option><option value="official_vendor_page">official_vendor_page</option><option value="manual_user_supplied">manual_user_supplied</option><option value="other_official_source">other_official_source</option></select>
  <input id="newContactRole" placeholder="Contact role / 联系人角色" style="width:100%;margin:6px 0;padding:7px">
  <textarea id="newEmailNotes" rows="2" placeholder="Notes / 备注"></textarea>
  <div class="modal-actions"><button class="btn btn-ap" onclick="submitOfficialEmail()">Verify / 验证邮箱</button><button class="btn" onclick="closeEmailModal()">Cancel / 取消</button></div>
</div></div>

<div class="modal" id="evidenceModal"><div class="modal-box evidence-box">
  <h3>审核证据工作台 / Review Evidence Workbench</h3>
  <div id="evidenceContent">Loading / 加载中…</div>
  <div class="modal-actions"><button class="btn" onclick="closeEvidence()">Close / 关闭</button></div>
</div></div>

<!-- Action Modal -->
<div class="modal" id="actionModal">
  <div class="modal-box">
    <h3 id="modalTitle">Action / 操作</h3>
    <div class="detail-row"><strong>ID:</strong> <span id="modalId"></span></div>
    <div class="detail-row"><strong>Store / 商家:</strong> <span id="modalName"></span></div>
    <div id="modalHygiene"></div>
    <label style="font-size:11px;color:#8b949e;margin-top:8px;display:block">Reason / 审核原因 (required / 必填):</label>
    <textarea id="modalReason" rows="2" placeholder="Why this decision? / 为什么做这个决定？"></textarea>
    <div class="modal-actions">
      <button class="btn btn-ap" id="btnApprove">Approve Auto / 批准自动发送</button>
      <button class="btn" id="btnApproveManual">Approve Manual / 批准手动发送</button>
      <button class="btn btn-rj" id="btnReject">Reject / 拒绝</button>
      <button class="btn btn-df" id="btnDefer">Defer / 延期</button>
      <button class="btn" onclick="closeModal()">Cancel / 取消</button>
    </div>
  </div>
</div>

<script>
var REASONS = ["CONTACT_ROLE_UNCERTAIN","WEAK_EVIDENCE","CONTACT_FORM_ONLY","OTHER_STATE_RETAIL",
  "BOUNCE_REVIEW","DOMAIN_MISMATCH","MATURE_BRAND","COUNTRY_UNCERTAIN","POSSIBLE_DUPLICATE",
  "EMAIL_SOURCE_UNCERTAIN","BUSINESS_FIT_UNCERTAIN","MANUAL_SEND_CANDIDATE","OTHER"];
var REASON_CN = {
  "CONTACT_ROLE_UNCERTAIN":"Email Role Uncertain / 邮箱角色不确定",
  "WEAK_EVIDENCE":"Weak Evidence / 证据不足",
  "CONTACT_FORM_ONLY":"Contact Form Only / 仅联系表单",
  "OTHER_STATE_RETAIL":"Other-State Retail / 非目标州零售",
  "BOUNCE_REVIEW":"Bounce Review / 退信核查",
  "DOMAIN_MISMATCH":"Domain Mismatch / 域名不匹配",
  "MATURE_BRAND":"Mature Brand / 成熟品牌",
  "COUNTRY_UNCERTAIN":"Country Uncertain / 国家不确定",
  "POSSIBLE_DUPLICATE":"Possible Duplicate / 疑似重复",
  "EMAIL_SOURCE_UNCERTAIN":"Email Source Uncertain / 邮箱来源不确定",
  "BUSINESS_FIT_UNCERTAIN":"Business Fit Uncertain / 业务匹配不确定",
  "MANUAL_SEND_CANDIDATE":"Manual Send Candidate / 手动发送候选",
  "OTHER":"Other / 其他"
};
var STATUS_CN = {
  "pending":"Pend / 待审","approved_auto":"Approved / 已批",
  "approved_manual":"Manual / 手动","rejected":"Rejected / 拒绝","deferred":"Deferred / 延期"
};
let currentPage=1, currentLead=null;

async function api(path, body){let r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});return r.json()}

function reasonLabel(code){return REASON_CN[code]||code.replace(/_/g,' ')}

async function loadSummary(){
  let d=await api('/api/summary');
  document.getElementById('totalPending').textContent=d.total_pending;
  let h='', by=d.by_reason||{};
  // Sort by pending count desc
  let codes=REASONS.concat().sort((a,b)=>(by[b]?.pending||0)-(by[a]?.pending||0));
  for(let code of codes){
    let c=by[code]||{};
    if(!c.pending&&!c.approved_auto&&!c.approved_manual&&!c.rejected&&!c.deferred)continue;
    let cnName=reasonLabel(code).split(' / ')[0];
    h+=`<div class="card"><div class="n">${c.pending||0}</div><div class="l">${cnName}</div><div class="le">${code}</div></div>`;
  }
  document.getElementById('summary').innerHTML=h;
  let sel=document.getElementById('filterReason');
  sel.innerHTML='<option value="">All / 全部原因</option>';
  for(let code of REASONS){if((by[code]||{}).pending||0>0)sel.innerHTML+=`<option value="${code}">${reasonLabel(code)}</option>`}
}

async function loadPage(pg){
  currentPage=pg||1;
  let params=new URLSearchParams({
    page:currentPage, per_page:25,
    reason:document.getElementById('filterReason').value,
    status:document.getElementById('filterStatus').value,
    sort:document.getElementById('filterSort').value,
    priority:document.getElementById('filterPriority').value,
    q:document.getElementById('filterQ').value
  });
  let d=await api('/api/leads?'+params);
  let t=`<table><tr>
    <th>ID</th>
    <th>Store / 商家</th>
    <th>City/State / 城市州</th>
    <th>Review Reason / 审核原因</th>
    <th>FB / 社交验证</th>
    <th>Evidence / 证据</th>
    <th>Since / 时间</th>
    <th>Actions / 操作</th>
  </tr>`;
  for(let l of d.leads||[]){
    let rlabel=reasonLabel(l.review_reason_code||'');
    let since=l.review_created_at?l.review_created_at.slice(0,10):(l.collected_at||'').slice(0,10);
    let evidence=l.official_website?`<a href="${l.official_website}" target="_blank">Site / 网站</a>`:'-';
    if(l.evidence_url)evidence+=` <a href="${l.evidence_url}" target="_blank">Map/Evid</a>`;

    // FB status column
    let fbHtml='<span style="color:#484f58;font-size:10px">-</span>';
    let fbData=(l.fb_check_status||'');
    if(fbData){
      let fbMap={'pending':'FB Queued / 等待','running':'FB Checking / 检查中','email_found':'FB Email Found / 找到邮箱',
        'social_contact_only':'Messenger Only / 仅社交','no_public_email':'No Public Email / 无公开邮箱',
        'no_facebook_link':'No FB Link / 无链接','mismatch':'FB Mismatch / 不匹配','blocked':'FB Blocked / 阻塞','failed':'FB Failed'};
      fbHtml=`<span style="font-size:10px">${fbMap[fbData]||fbData}</span>`;
      if(l.facebook_url)fbHtml+=`<br><a href="${l.facebook_url}" target="_blank" style="font-size:9px">FB Page</a>`;
    }

    // Determine if Auto should be disabled
    let noEmail=!l.email||l.email.indexOf('@')===-1;
    let isContactForm=l.review_reason_code==='CONTACT_FORM_ONLY'||l.lead_status==='contact_form_pool';
    let disableAuto=noEmail||isContactForm;
    let sn=h(l.store_name);
    let autoBtn=disableAuto
      ?`<span class="btn" style="opacity:0.4;cursor:not-allowed" title="Need public email first / 需先验证公开邮箱">--</span>`
      :`<button class="btn btn-ap" title="Approve Auto / 批准自动" onclick="openAction(${l.id},'${sn}','approve_auto')">Auto</button>`;

    // FB recheck button
    let fbRecheck=`<button class="btn btn-re" style="font-size:9px;padding:2px 6px" title="Recheck Facebook / 重检FB" onclick="recheck(${l.id},'recheck_facebook')">FB</button>`;
    let siteRecheck=`<button class="btn btn-re" style="font-size:9px;padding:2px 6px" title="Recheck Official Site / 重检官网" onclick="recheck(${l.id},'recheck_official')">Site</button>`;
    let manualBtn=isContactForm
      ?`<span class="btn" style="opacity:0.4;cursor:not-allowed" title="Contact Form cannot enter email queue / 联系表单不能进入邮件队列">--</span>`
      :`<button class="btn" title="Approve Manual / 批准手动" onclick="openAction(${l.id},'${sn}','approve_manual')">Manual</button>`;
    t+=`<tr>
      <td>${l.id}</td>
      <td><span class="lead-name">${sn}</span><br><span class="lead-meta">${l.store_type||'?'}</span></td>
      <td><span class="lead-city">${l.city||'-'}, ${l.state||'-'}</span></td>
      <td><span class="badge ${badgeClass(l.review_reason_code)}">${rlabel}</span><br><span class="lead-meta">${l.email_masked}</span></td>
      <td>${fbHtml}</td>
      <td><span class="ev-links">${evidence}</span></td>
      <td>${since}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-re" onclick="openEvidence(${l.id})">Evidence / 证据</button>
        ${autoBtn}
        ${manualBtn}
        <button class="btn btn-rj" title="Reject / 拒绝" onclick="openAction(${l.id},'${sn}','reject')">R</button>
        <button class="btn btn-df" title="Defer / 延期" onclick="openAction(${l.id},'${sn}','defer')">D</button>
        <button class="btn" title="Add Official Email / 补充官方邮箱" onclick="openEmailModal(${l.id})">Email</button>
        ${siteRecheck} ${fbRecheck}
      </td></tr>`;
  }
  t+='</table>';
  document.getElementById('tableContainer').innerHTML=t||'<p style="padding:20px;color:#8b949e">No leads found / 未找到线索</p>';
  let pgHtml=`<span>${d.total} leads / 条, Page / 第 ${d.page}/${d.pages} 页</span>`;
  if(d.page>1)pgHtml+=`<button onclick="loadPage(${d.page-1})">Prev / 上页</button>`;
  for(let i=Math.max(1,d.page-2);i<=Math.min(d.pages,d.page+2);i++)
    pgHtml+=`<button class="${i==d.page?'active':''}" onclick="loadPage(${i})">${i}</button>`;
  if(d.page<d.pages)pgHtml+=`<button onclick="loadPage(${d.page+1})">Next / 下页</button>`;
  document.getElementById('pagination').innerHTML=pgHtml;
}
function h(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,"\\'")}
function badgeClass(c){
  if(c==='BOUNCE_REVIEW'||c==='DOMAIN_MISMATCH')return'bg-r';
  if(c==='MATURE_BRAND'||c==='OTHER_STATE_RETAIL')return'bg-y';
  if(c==='CONTACT_FORM_ONLY')return'bg-b';
  return'';
}

function openAction(id,name,action){
  currentLead={id:id,name:name,action:action};
  document.getElementById('modalId').textContent=id;
  document.getElementById('modalName').textContent=name;
  document.getElementById('modalTitle').textContent={
    approve_auto:'Approve for Auto Send / 批准自动发送',approve_manual:'Approve as Manual Send Only / 批准手动发送',
    reject:'Reject / 拒绝',defer:'Defer / Recheck Later / 延期'}[action];
  document.getElementById('modalReason').value='';
  document.getElementById('modalHygiene').innerHTML='';
  document.getElementById('actionModal').classList.add('show');
  if(action==='approve_auto')checkHygiene(id);
}
function closeModal(){document.getElementById('actionModal').classList.remove('show');currentLead=null}
function openEmailModal(id){document.getElementById('emailLeadId').textContent=id;document.getElementById('newOfficialWebsite').value='';document.getElementById('newEmail').value='';document.getElementById('newEvidenceUrl').value='';document.getElementById('newEvidenceSnippet').value='';document.getElementById('newContactRole').value='';document.getElementById('newEmailNotes').value='';document.getElementById('emailModal').classList.add('show')}
function closeEmailModal(){document.getElementById('emailModal').classList.remove('show')}
async function submitOfficialEmail(){let id=parseInt(document.getElementById('emailLeadId').textContent);let body={lead_id:id,official_website:document.getElementById('newOfficialWebsite').value,email:document.getElementById('newEmail').value,evidence_url:document.getElementById('newEvidenceUrl').value,evidence_snippet:document.getElementById('newEvidenceSnippet').value,evidence_method:document.getElementById('newEvidenceMethod').value,contact_role:document.getElementById('newContactRole').value,notes:document.getElementById('newEmailNotes').value};let d=await api('/api/manual-email',body);alert((d.final_status||'failed')+(d.failure_reason?': '+d.failure_reason:''));if(d.ok){closeEmailModal();loadPage(currentPage);loadSummary()};refreshAll()}


async function checkHygiene(id){
  document.getElementById('modalHygiene').innerHTML='<div style="font-size:11px;color:#d29922;margin:4px 0">Hygiene Gate / 安全门禁: suppression / bounce / duplicate / state / Exchange MX will be checked on approve</div>';
}

async function doAction(action){
  if(!currentLead)return;
  let reason=document.getElementById('modalReason').value.trim();
  if(!reason){alert('Please provide a reason / 请填写审核原因');return}
  let endpoint={approve_auto:'approve',approve_manual:'approve',reject:'reject',defer:'defer'}[action];
  let bodyNext='';
  if(action==='defer'){bodyNext=prompt('Next review at (ISO date/time) / 下次审核时间（ISO）','');if(!bodyNext)return;}
  let body={lead_id:currentLead.id,decision:action==='approve_manual'?'approve_manual':(action==='approve_auto'?'approve_auto':action),reason:reason};
  if(action==='defer')body.next_review_at=bodyNext;
  let d=await api('/api/'+endpoint,body);
  if(d.ok){alert('Done / 完成: '+(d.new_status||action));closeModal();loadPage(currentPage);loadSummary()}
  else{alert('Failed / 失败: '+d.error);document.getElementById('modalHygiene').innerHTML='<div class="hygiene-fail">'+h(d.error)+'</div>'}
}

document.getElementById('btnApprove').onclick=()=>doAction('approve_auto');
document.getElementById('btnApproveManual').onclick=()=>doAction('approve_manual');
document.getElementById('btnReject').onclick=()=>doAction('reject');
document.getElementById('btnDefer').onclick=()=>doAction('defer');

async function recheck(leadId, action){
  let endpoint=action==='recheck_official'?'recheck-official':'recheck-facebook';
  let r=await api('/api/'+endpoint,{lead_id:leadId,reason:'review recheck requested'});
  if(r.ok){alert('Recheck pending / 已进入复核队列');loadPage(currentPage);loadSummary()}
  else{alert('Failed / 失败: '+r.error)}
}

// Batch FB check for visible leads
async function batchFB(){
  let ids=[];
  document.querySelectorAll('tr td:first-child').forEach(td=>{let v=parseInt(td.textContent);if(v)ids.push(v)});
  if(!ids.length){alert('No leads visible');return}
  let r=await api('/api/fb_batch',{lead_ids:ids.slice(0,25)});
  if(r.ok){alert('Queued / 已入队: '+r.queued);loadPage(currentPage)}
  else{alert('Failed: '+r.error)}
}
function refreshAll(){loadPage(currentPage);loadSummary()}
setInterval(refreshAll, 30000);

loadSummary();loadPage(1);
</script>
<script src="/review-evidence.js"></script>
</body>
</html>"""


def _safe_ops(fn):
    try: return fn()
    except Exception as e: return {"error": str(e)}


def get_scheduler_state():
    ps = get_poller_state()
    # Read heartbeat file
    hb = {}
    try:
        with open(PROJECT_DIR / "output" / "bd_ops_poller_status.json", "r") as f:
            hb = json.load(f)
    except Exception:
        pass
    return {
        "scheduler_authority": "workbuddy_automations",
        "production_schedule_state": "paused_pending_pilot",
        "windows_tasks": "blocked_by_security_policy",
        "ops_center": "running",
        "outreach_enabled": False,
        "today_pilot": "manual_control",
        "poller": {
            "running": ps.get("running"),
            "started_at": ps.get("started_at"),
            "last_heartbeat_at": hb.get("last_heartbeat_at", ps.get("last_heartbeat_at")),
            "jobs": ps.get("jobs", {}),
        },
        "reply_monitor": {
            "level": "partial",
            "capability": "basic_reply_polling",
            "scans_inbox": True,
            "scans_all_mail": False,
            "scans_spam": False,
            "message_id_matching": False,
            "in_reply_to_matching": False,
            "references_matching": False,
            "note": "Basic Inbox header scan only — matches by From email fallback"
        },
        "automations_count": 7,
        "outreach_automation_enabled": False,
        "inventory_next_run": "today_1500_if_enabled",
        "wake_timer": "unavailable_cannot_create_tasks",
        "generated_at": now_cst().isoformat(),
    }


def _get_guard_state():
    """Read Delivery Guard status from status file and PID check."""
    import subprocess
    guard = {
        "running": False,
        "heartbeat_fresh": False,
        "status": {},
    }

    # Check PID file
    pid_path = PROJECT_DIR / "output" / "bd_delivery_guard.pid"
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            if "python" in r.stdout.lower() or "bd_delivery" in r.stdout.lower():
                guard["running"] = True
        except (ValueError, FileNotFoundError):
            pass

    # Read status JSON
    status_path = PROJECT_DIR / "output" / "bd_delivery_guard_status.json"
    if status_path.exists():
        try:
            guard["status"] = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            pass

    # Check heartbeat freshness
    last_hb = guard["status"].get("last_heartbeat_at", "")
    if last_hb:
        try:
            hb_time = datetime.fromisoformat(last_hb)
            age = (now_cst() - hb_time).total_seconds()
            guard["heartbeat_fresh"] = age < 120
        except (ValueError, TypeError):
            pass

    return guard


def api_reconciliation(limit: int = 10):
    """读取最近几次发信后对账结果。

    数据来源：output/post_send_reconciliation_*.json + system_config 中的
    post_send_reconciliation_* 状态 key。返回 POST_SEND_RECONCILIATION_FAILED
    标记（任一批次对账 FAILED 即置真），供运维在监控面板上使用。
    """
    results = []
    # 1) output 目录下的对账 JSON 文件（按修改时间倒序）
    out_dir = PROJECT_DIR / 'output'
    if out_dir.exists():
        for p in sorted(out_dir.glob('post_send_reconciliation_*.json'),
                        key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                data.setdefault('batch_id', p.stem.replace('post_send_reconciliation_', '', 1))
                results.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    # 2) system_config 中的对账状态 key
    conn = db()
    try:
        rows = conn.execute(
            "SELECT key, value FROM system_config WHERE key LIKE 'post_send_reconciliation_%'"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()

    config_status = {}
    for key, value in rows:
        batch_id = key.replace('post_send_reconciliation_', '', 1)
        status = (value or '').strip() or 'UNKNOWN'
        try:
            parsed = json.loads(status)
            status = parsed.get('status', 'UNKNOWN')
        except (json.JSONDecodeError, TypeError):
            pass
        config_status[batch_id] = status
        if not any(r.get('batch_id') == batch_id for r in results):
            results.append({'batch_id': batch_id, 'verdict': status, 'source': 'system_config'})

    for r in results:
        r['config_status'] = config_status.get(r.get('batch_id'), r.get('verdict'))

    failed_present = any(s == 'FAILED' for s in config_status.values()) or \
        any(r.get('verdict') == 'FAILED' for r in results)

    return json.dumps({
        'results': results[:limit],
        'post_send_reconciliation_failed_present': failed_present,
        'generated_at': now_cst().isoformat(),
    })


class ReviewHandler(BaseHTTPRequestHandler):
    server_start = ''

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(data.encode())

    def _html(self, html, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/' or path == '/index.html':
            self._html(DASHBOARD_HTML)
        elif path == '/review':
            self._html(HTML_PAGE.replace('{server_start}', self.server_start))
        elif path == '/review-evidence.js':
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript; charset=utf-8')
            self.end_headers()
            self.wfile.write((PROJECT_DIR / 'review_evidence_ui.js').read_bytes())
        elif path == '/api/summary':
            self._json(api_summary())
        elif path == '/api/leads':
            self._json(api_leads(params))
        elif path == '/api/history':
            self._json(api_history(params.get('lead_id', [''])[0]))
        elif path == '/api/review-evidence':
            self._json(api_review_evidence(params.get('lead_id', [''])[0]))
        elif path == '/api/dashboard':
            self._json(json.dumps({'server_running': True, 'started_at': self.server_start}))
        elif path == '/api/ops/summary':
            self._json(json.dumps(_safe_ops(lambda: get_ops_summary(str(DB_PATH)))))
        elif path == '/api/ops/today':
            self._json(json.dumps(_safe_ops(lambda: get_today_stats(str(DB_PATH)))))
        elif path == '/api/ops/inventory':
            self._json(json.dumps(_safe_ops(lambda: get_inventory(str(DB_PATH)))))
        elif path == '/api/ops/search':
            self._json(json.dumps(_safe_ops(lambda: get_search_progress(str(DB_PATH)))))
        elif path == '/api/ops/plan':
            data = _safe_ops(lambda: get_final_plan(str(DB_PATH)))
            if isinstance(data, dict) and 'error' not in data:
                # 附加 schedule_preview 摘要（时区分布 + UNRESOLVED 数 + 当地10:00 的 China 时间样例）
                data['schedule_preview'] = _safe_ops(
                    lambda: get_schedule_preview_summary(str(DB_PATH)))
            self._json(json.dumps(data))
        elif path == '/api/ops/health':
            self._json(json.dumps(_safe_ops(lambda: get_health(str(DB_PATH)))))
        elif path == '/api/ops/quality':
            self._json(json.dumps(_safe_ops(lambda: get_data_quality(str(DB_PATH)))))
        elif path == '/api/ops/scheduler':
            self._json(json.dumps(get_scheduler_state()))
        elif path == '/api/ops/guard':
            self._json(json.dumps(_get_guard_state()))
        elif path == '/api/ops/reconciliation':
            self._json(api_reconciliation())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body_raw = self.rfile.read(length) if length else b'{}'
        try:
            body = json.loads(body_raw)
        except json.JSONDecodeError:
            body = {}

        parsed = urlparse(self.path)

        if parsed.path == '/api/approve':
            self._json(api_approve(body))
        elif parsed.path == '/api/reject':
            self._json(api_reject(body))
        elif parsed.path == '/api/defer':
            self._json(api_defer(body))
        elif parsed.path == '/api/recheck-official':
            self._json(_review_action(body, 'recheck_official'))
        elif parsed.path == '/api/recheck-facebook':
            self._json(_review_action(body, 'recheck_facebook'))
        elif parsed.path == '/api/manual-email':
            self._json(api_manual_email(body))
        elif parsed.path == '/api/manual-a0':
            try:
                self._json(api_manual_a0(body))
            except Exception as e:
                self._json(json.dumps({'ok': False, 'error': str(e)[:200]}))
        elif parsed.path == '/api/fetch-facebook-evidence':
            self._json(api_fetch_facebook_evidence(body))
        elif parsed.path == '/api/verify-recovered-website':
            self._json(api_verify_recovered_website(body))
        elif parsed.path == '/api/evidence-decision':
            self._json(api_evidence_decision(body))
        elif parsed.path == '/api/fb':
            self._json(api_fb_queue(body))
        elif parsed.path == '/api/fb_batch':
            self._json(api_fb_batch(body))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')

    def log_message(self, format, *args):
        # Quiet logging
        pass


def find_free_port(start=8765):
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOL_SOCKET) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()

    port = args.port if args.port > 0 else find_free_port()

    server = HTTPServer(('127.0.0.1', port), ReviewHandler)
    ReviewHandler.server_start = now_cst().strftime('%Y-%m-%d %H:%M:%S')

    # Write status
    STATUS_PATH.parent.mkdir(exist_ok=True)
    with open(STATUS_PATH, 'w') as f:
        json.dump({
            'running': True, 'host': '127.0.0.1', 'port': port,
            'url': f'http://127.0.0.1:{port}/',
            'started_at': ReviewHandler.server_start,
        }, f, indent=2)

    print(f'BD Review Server: http://127.0.0.1:{port}/')
    print(f'Status: {STATUS_PATH}')
    # Start background poller
    poller_result = start_poller()
    print(f'Poller: {poller_result}')
    print('Press Ctrl+C to stop.')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        # Update status
        with open(STATUS_PATH, 'w') as f:
            json.dump({'running': False, 'stopped_at': now_cst().isoformat()}, f, indent=2)


if __name__ == '__main__':
    main()
