"""
Phase 2 Dry-Run — 7 A-grade leads (Christmas Concept Template)
按用户指定顺序执行 dry-run
"""
import sqlite3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, '.')
from bd_template import get_email_for_lead
from bd_db import is_suppressed

DB_PATH = 'data/bd_leads.db'

DRYRUN_ORDER = [
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

    # Get sent emails
    cur.execute('SELECT email FROM send_log WHERE status="sent"')
    sent_emails = set(r['email'] for r in cur.fetchall())

    # Get suppression emails
    cur.execute('SELECT email FROM suppression_list')
    suppressed_emails = set(r['email'] for r in cur.fetchall())

    print("=" * 100)
    print("PHASE 2 DRY-RUN — Christmas Puzzle Concept Template")
    print("=" * 100)
    print()

    all_ok = True
    results = []

    for i, store_name in enumerate(DRYRUN_ORDER, 1):
        # Find lead in DB
        cur.execute('SELECT * FROM leads WHERE store_name LIKE ? AND confidence_score = "A" AND status = "new" LIMIT 1',
                    (f'%{store_name}%',))
        lead = cur.fetchone()
        if not lead:
            # Try broader match
            cur.execute('SELECT * FROM leads WHERE store_name LIKE ? AND confidence_score = "A" LIMIT 1',
                        (f'%{store_name}%',))
            lead = cur.fetchone()

        if not lead:
            print(f"[{i}] NOT FOUND: {store_name}")
            all_ok = False
            continue

        lead_dict = dict(lead)
        email = lead_dict.get('email', '')

        # Generate email
        email_data = get_email_for_lead(lead_dict)

        # Checks
        suppressed = email in suppressed_emails if email else False
        already_sent = email in sent_emails if email else False
        no_email = not email or email.strip() == ''
        status = lead_dict.get('status', '')
        if status in ('sent', 'bounced', 'unsubscribed', 'do_not_contact'):
            already_sent = True

        # Unreplaced variable check
        body = email_data['body_text']
        unreplaced = []
        if '{{' in body or '}}' in body:
            unreplaced.append('{{}}')
        if 'undefined' in body.lower():
            unreplaced.append('undefined')
        if 'None' in body:
            unreplaced.append('None')
        if 'null' in body.lower():
            unreplaced.append('null')
        if '&ndash;' in body:
            unreplaced.append('&ndash;')
        if 'stationary' in body.lower():
            unreplaced.append('stationary (typo)')

        can_send = not suppressed and not already_sent and not no_email and not unreplaced

        print(f"{'=' * 100}")
        print(f"[{i}/7] {lead_dict['store_name']}")
        print(f"{'=' * 100}")
        print(f"  Store Type       : {lead_dict.get('store_type', '')}")
        print(f"  City, State      : {lead_dict.get('city', '')}, {lead_dict.get('state', '')}")
        print(f"  Official Website : {lead_dict.get('official_website', '')}")
        print(f"  Evidence URL     : {lead_dict.get('evidence_url', '')}")
        print(f"  Email            : {email}")
        print(f"  Status           : {status}")
        print()
        print(f"  From             : Ian <ianyf@roktandrazo.com>")
        print(f"  Reply-To         : ianyf@roktandrazo.com")
        print(f"  Subject          : {email_data['subject']}")
        print()
        print(f"  In Suppression?  : {'YES' if suppressed else 'NO'}")
        print(f"  Already Sent?    : {'YES' if already_sent else 'NO'}")
        print(f"  Has Email?       : {'YES' if not no_email else 'NO'}")
        print(f"  Unreplaced Vars  : {', '.join(unreplaced) if unreplaced else 'None'}")
        print()

        if can_send:
            print(f"  RECOMMEND: SEND")
        else:
            reasons = []
            if suppressed: reasons.append("in suppression list")
            if already_sent: reasons.append("already sent/bounced/unsubscribed")
            if no_email: reasons.append("no email address")
            if unreplaced: reasons.append(f"unreplaced: {', '.join(unreplaced)}")
            print(f"  RECOMMEND: DO NOT SEND — {'; '.join(reasons)}")
            all_ok = False

        print()
        print(f"  --- FULL EMAIL BODY ---")
        for line in email_data['body_text'].split('\n'):
            print(f"  | {line}")
        print(f"  --- END ---")
        print()

        results.append({
            "id": lead_dict['id'],
            "store_name": lead_dict['store_name'],
            "email": email,
            "can_send": can_send,
        })

    # Summary
    sendable = [r for r in results if r['can_send']]
    print("=" * 100)
    print("DRY-RUN SUMMARY")
    print("=" * 100)
    print(f"  Total checked: {len(results)}")
    print(f"  Can send:      {len(sendable)}")
    print(f"  Blocked:       {len(results) - len(sendable)}")
    print()
    if sendable:
        print("  Ready to send:")
        for r in sendable:
            print(f"    {r['store_name']:40s} -> {r['email']}")
    print()

    conn.close()
    return all_ok

if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
