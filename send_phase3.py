import os as _dev_os
if _dev_os.path.exists(_dev_os.path.join(_dev_os.path.dirname(__file__), ".development-copy")):
    from development_safety import install as _install_development_safety
    _install_development_safety()

# ══ P0 HARD-DISABLED: Production SMTP blocked ══
class LegacySMTPDisabledError(Exception): pass
import os as _os
if not _os.environ.get('BD_TEST_MODE')=='true':
    raise LegacySMTPDisabledError('Legacy SMTP disabled. Use bd_orchestrator with valid authorization.')
"""
Phase 3 Batch 1 — Real Send for 15 A-grade leads
Christmas Puzzle Concept template. 90s interval between sends.
BCC-to-self enabled. IMAP save attempted.
"""
import sqlite3, sys, io, time, os
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

LEGACY_LIVE_DISABLED_MESSAGE = (
    "LEGACY_LIVE_DISABLED: send_phase3.py real-send script is disabled. "
    "Use bd_sender.py/daily_operator_auto.py controlled workflow only."
)


def fail_closed_legacy_live():
    print(LEGACY_LIVE_DISABLED_MESSAGE)
    return 2


if __name__ == '__main__':
    sys.exit(fail_closed_legacy_live())
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from bd_template import get_email_for_lead
from bd_sender import send_one
from bd_db import is_suppressed

DB_PATH = 'data/bd_leads.db'

# The 15 Phase 3 dry-run leads by ID (in same order as dry-run)
# ID 74 (Battleground Games) already sent in first run — excluded
SEND_IDS = [76, 69, 68, 81, 92, 57, 65, 62, 77, 58, 86, 83, 75, 59]

# Card Kingdom needs a notes update
CARD_KINGDOM_LABEL = "orders@ email is general/order contact. If no reply, look for vendor/buyer contact."

def domain_hash(website):
    if not website: return ""
    d = website.lower().strip()
    d = d.replace("https://","").replace("http://","").replace("www.","")
    d = d.split("/")[0].split("?")[0].split("#")[0]
    return d

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Load pre-send reference data
    cur.execute('SELECT email FROM suppression_list')
    suppressed_emails = set(r['email'] for r in cur.fetchall())

    cur.execute('SELECT DISTINCT email FROM send_log WHERE status="sent"')
    sent_emails = set(r['email'] for r in cur.fetchall())

    cur.execute('SELECT official_website FROM leads WHERE status="sent"')
    sent_domains = set()
    for r in cur.fetchall():
        d = domain_hash(r['official_website'])
        if d: sent_domains.add(d)

    # Load leads
    leads = []
    for lid in SEND_IDS:
        cur.execute('SELECT * FROM leads WHERE id = ?', (lid,))
        r = cur.fetchone()
        if r:
            leads.append(dict(r))
        else:
            print(f"[SKIP] ID={lid} not found in database")

    print(f"Loaded {len(leads)} leads for Phase 3 Batch 1 send")
    print(f"{'='*80}")
    print()

    results = []
    sent_count = 0
    skip_count = 0
    fail_count = 0

    for i, lead in enumerate(leads, 1):
        email = lead['email']
        lead_id = lead['id']
        store_name = lead['store_name']
        domain = domain_hash(lead.get('official_website', ''))
        
        print(f"[{i}/15] {store_name} ({email})...")

        # ===== Pre-send checks =====
        skip_reason = None

        # Suppression check
        if is_suppressed(email):
            skip_reason = f"suppressed email"
        
        # Sent email check
        if not skip_reason and email in sent_emails:
            skip_reason = f"already sent ({email})"
        
        # Sent domain check
        if not skip_reason and domain and domain in sent_domains:
            skip_reason = f"domain already sent ({domain})"

        if skip_reason:
            print(f"  -> SKIP: {skip_reason}")
            results.append({
                "store_name": store_name, "email": email, "status": "skipped",
                "message": skip_reason, "lead_id": lead_id
            })
            skip_count += 1
            continue

        # ===== Generate email =====
        email_data = get_email_for_lead(lead)
        lead['email_subject'] = email_data['subject']
        lead['email_body'] = email_data['body_text']
        lead['email_body_html'] = email_data['body_html']

        # ===== Safety check =====
        body = lead['email_body']
        safety_issues = []
        if '{{' in body or '}}' in body: safety_issues.append('{{}}')
        if 'undefined' in body.lower(): safety_issues.append('undefined')
        if 'None' in body: safety_issues.append('None')
        if 'null' in body.lower(): safety_issues.append('null')
        if '&ndash;' in body: safety_issues.append('&ndash;')
        if 'stationary' in body.lower(): safety_issues.append('stationary')

        if safety_issues:
            print(f"  -> FAILED (safety): {', '.join(safety_issues)}")
            results.append({
                "store_name": store_name, "email": email, "status": "failed",
                "message": f"Safety check: {', '.join(safety_issues)}", "lead_id": lead_id
            })
            fail_count += 1
            continue

        # ===== Send =====
        try:
            result = send_one(lead, dry_run=False)
        except Exception as e:
            result = {"success": False, "message": str(e), "status": "failed"}

        result['store_name'] = store_name
        result['email'] = email
        result['lead_id'] = lead_id

        if result['success'] and result['status'] == 'sent':
            sent_count += 1
            now = datetime.now().isoformat()
            
            # Card Kingdom note
            if 'card kingdom' in store_name.lower():
                existing_notes = lead.get('notes', '')
                new_notes = f"{existing_notes} [Phase3 send] {CARD_KINGDOM_LABEL}"
                cur.execute('UPDATE leads SET notes = ? WHERE id = ?', (new_notes, lead_id))
            
            conn.commit()
            print(f"  -> SENT OK at {now}")
        else:
            fail_count += 1
            print(f"  -> FAILED: {result['message']}")

        results.append(result)

        # ===== Delay =====
        if i < len(leads):
            delay = 90
            print(f"  Waiting {delay}s before next send...")
            time.sleep(delay)

    conn.close()

    # ===== FINAL REPORT =====
    print()
    print("=" * 80)
    print("PHASE 3 BATCH 1 — SEND REPORT")
    print("=" * 80)
    print()
    print(f"  Total attempted: {len(leads)}")
    print(f"  Successfully sent: {sent_count}")
    print(f"  Skipped: {skip_count}")
    print(f"  Failed: {fail_count}")
    print()

    if sent_count > 0:
        print("--- SUCCESSFUL SENDS ---")
        for r in results:
            if r['status'] == 'sent':
                print(f"  ✅ {r['store_name']:40s} | {r['email']:35s} | SENT")
    print()

    if skip_count > 0:
        print("--- SKIPPED ---")
        for r in results:
            if r['status'] == 'skipped':
                print(f"  ⏭️ {r['store_name']:40s} | {r['email']:35s} | {r['message']}")
    print()

    if fail_count > 0:
        print("--- FAILED ---")
        for r in results:
            if r['status'] in ('failed', 'bounced'):
                print(f"  ❌ {r['store_name']:40s} | {r['email']:35s} | {r['message']}")
    print()

    # Database totals
    conn2 = sqlite3.connect(DB_PATH)
    cur2 = conn2.cursor()
    cur2.execute('SELECT COUNT(*) FROM leads WHERE status="sent"')
    total_sent = cur2.fetchone()[0]
    cur2.execute('SELECT COUNT(*) FROM send_log WHERE status="sent"')
    log_entries = cur2.fetchone()[0]
    cur2.execute('SELECT COUNT(*) FROM leads')
    total_leads = cur2.fetchone()[0]
    conn2.close()

    print("--- DATABASE TOTALS ---")
    print(f"  Total leads: {total_leads}")
    print(f"  Total status=sent: {total_sent}")
    print(f"  Total send_log entries (sent): {log_entries}")
    print()
    print("--- SEND LOG VERIFICATION ---")
    conn3 = sqlite3.connect(DB_PATH)
    cur3 = conn3.cursor()
    cur3.execute('''SELECT sl.id, sl.lead_id, l.store_name, sl.email, sl.status, sl.sent_at
    FROM send_log sl
    JOIN leads l ON sl.lead_id = l.id
    WHERE sl.status = "sent"
    ORDER BY sl.sent_at DESC
    LIMIT 20''')
    for r in cur3.fetchall():
        print(f"  log_id={r[0]} | lead_id={r[1]} | {r[2]:40s} | {r[3]:35s} | {r[5]}")
    conn3.close()

if __name__ == '__main__':
    main()
