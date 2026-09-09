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
Phase 2 Send — 7 A-grade leads (Christmas Concept Template)
真实发送，逐条执行，60秒间隔
"""
import sqlite3
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

LEGACY_LIVE_DISABLED_MESSAGE = (
    "LEGACY_LIVE_DISABLED: send_phase2.py real-send script is disabled. "
    "Use bd_sender.py/daily_operator_auto.py controlled workflow only."
)


def fail_closed_legacy_live():
    print(LEGACY_LIVE_DISABLED_MESSAGE)
    return 2


if __name__ == '__main__':
    sys.exit(fail_closed_legacy_live())

sys.path.insert(0, '.')
from bd_template import get_email_for_lead
from bd_sender import send_one
from bd_db import is_suppressed

DB_PATH = 'data/bd_leads.db'

SEND_ORDER = [
    "The Philly Game Shop",
    "Vault of Midnight",
    "Beyond the Blackboard",
    "The Wizard's Chest",
    "Razzle Toys",
    "Clothes Pony & Dandelion Toys",
    "Eureka Puzzles & Games",
]

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 80)
    print("PHASE 2 REAL SEND — 7 A-Grade Leads")
    print("=" * 80)
    print()

    results = []
    sent_count = 0

    for i, store_name in enumerate(SEND_ORDER, 1):
        # Find lead
        cur.execute('SELECT * FROM leads WHERE store_name LIKE ? AND confidence_score = "A" LIMIT 1',
                    (f'%{store_name}%',))
        lead = cur.fetchone()
        if not lead:
            print(f"[{i}] NOT FOUND: {store_name}")
            results.append({"store_name": store_name, "success": False, "message": "Not found"})
            continue

        lead_dict = dict(lead)
        email = lead_dict.get('email', '')
        status = lead_dict.get('status', '')

        # Pre-checks
        if status in ('sent', 'bounced', 'unsubscribed', 'do_not_contact'):
            print(f"[{i}] SKIP — status={status}: {store_name}")
            results.append({"store_name": store_name, "success": False, "message": f"Status: {status}"})
            continue

        if is_suppressed(email):
            print(f"[{i}] SKIP — suppressed: {store_name} ({email})")
            results.append({"store_name": store_name, "success": False, "message": "Suppressed"})
            continue

        # Generate email
        email_data = get_email_for_lead(lead_dict)
        lead_dict['email_subject'] = email_data['subject']
        lead_dict['email_body'] = email_data['body_text']
        lead_dict['email_body_html'] = email_data['body_html']

        # Send
        print(f"[{i}/7] Sending to {store_name} ({email})...")
        result = send_one(lead_dict, dry_run=False)
        result['store_name'] = store_name
        results.append(result)

        if result['success']:
            sent_count += 1
            print(f"  -> SENT OK")
        else:
            print(f"  -> FAILED: {result['message']}")

        # Delay between sends (60s)
        if i < len(SEND_ORDER) and result['success']:
            print(f"  Waiting 60 seconds before next send...")
            time.sleep(60)

    # Summary
    print()
    print("=" * 80)
    print("SEND RESULTS")
    print("=" * 80)
    for r in results:
        status_icon = "OK" if r['success'] else "FAIL"
        print(f"  [{status_icon}] {r['store_name']:40s} -> {r.get('email', 'N/A'):40s} | {r.get('message', '')}")
    print()
    print(f"  Sent: {sent_count} / {len(SEND_ORDER)}")
    print()

    conn.close()

if __name__ == '__main__':
    main()
