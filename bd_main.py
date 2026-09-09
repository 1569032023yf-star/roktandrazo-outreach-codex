"""
Roktandrazo BD Outreach - Main Pipeline (Closed-Loop)
主入口：dry-run / test-send / real-send / status

用法:
  python bd_main.py status           # 查看系统状态
  python bd_main.py dry-run          # Dry run 预览
  python bd_main.py test-send        # 发送到测试邮箱
  python bd_main.py send             # 实际发送 (approved 线索)
  python bd_main.py approve-all      # 将所有 new A/B 级线索标记为 approved
"""

import sys
import json
from datetime import datetime

from env_loader import is_configured, get_smtp_config, get_sender_info, get_test_config, mask
from bd_db import init_db, get_stats, get_leads_by_status, get_approved_leads, update_lead_status
from bd_template import apply_email_to_lead, SUBJECT
from bd_sender import send_one, batch_send


def cmd_status():
    """Show system status"""
    stats = get_stats()
    smtp = get_smtp_config()
    sender = get_sender_info()
    test = get_test_config()

    print("\n" + "="*60)
    print("  ROKTANDRAZO BD OUTREACH - SYSTEM STATUS")
    print("="*60)

    print(f"\n  SMTP: {smtp['host']}:{smtp['port']} (SSL)")
    print(f"  User: {mask(smtp['user']) if smtp['user'] else 'NOT SET'}")
    print(f"  Pass: {'***configured***' if smtp['password'] else 'NOT SET'}")
    print(f"  From: {sender['name']} <{sender['email'] if sender['email'] else 'NOT SET'}>")
    print(f"  Test Mode: {test['test_mode']}")
    print(f"  Test Email: {test['test_email'] if test['test_email'] else 'NOT SET'}")
    print(f"  Configured: {'YES' if is_configured() else 'NO - check .env'}")

    print(f"\n  Leads: {stats.get('total', 0)}")
    print(f"  With Email: {stats.get('with_email', 0)}")
    print(f"  Suppressed: {stats.get('suppressed', 0)}")
    print(f"  By Status: {json.dumps(stats.get('by_status', {}), ensure_ascii=False)}")
    print(f"  By Score: {json.dumps(stats.get('by_score', {}), ensure_ascii=False)}")
    print(f"  Send Log: {json.dumps(stats.get('send_log', {}), ensure_ascii=False)}")
    print()


def cmd_approve_all():
    """Approve all new A/B leads with email"""
    leads = get_leads_by_status("new", limit=500)
    approved = 0
    for lead in leads:
        if lead.get("confidence_score") in ("A", "B") and lead.get("email"):
            apply_email_to_lead(lead)
            update_lead_status(lead["id"], "approved",
                             email_subject=lead["email_subject"],
                             email_body=lead["email_body"])
            approved += 1
            print(f"  [OK] {lead['store_name']:35s} | {lead['email']}")

    print(f"\nApproved: {approved} / {len(leads)}")


def cmd_dry_run():
    """Dry run - preview what would be sent"""
    leads = get_approved_leads(limit=100)
    test = get_test_config()

    print("\n" + "="*60)
    print("  DRY RUN - PREVIEW")
    print("="*60)

    if not leads:
        # If no approved leads, check what's available
        new_leads = get_leads_by_status("new", limit=100)
        a_leads = [l for l in new_leads if l.get("confidence_score") == "A" and l.get("email")]
        b_leads = [l for l in new_leads if l.get("confidence_score") == "B" and l.get("email")]
        sent_leads = get_leads_by_status("sent", limit=100)

        print(f"\n  No approved leads found.")
        print(f"  New A-grade with email: {len(a_leads)}")
        print(f"  New B-grade with email: {len(b_leads)}")
        print(f"  Already sent: {len(sent_leads)}")
        print(f"\n  Run 'python bd_main.py approve-all' first to approve leads.")
        return

    print(f"\n  Would send {len(leads)} emails:")
    print(f"  From: {get_sender_info()['name']} <{get_sender_info()['email']}>")
    print(f"  Subject: {SUBJECT}")
    print(f"  Test Mode: {test['test_mode']}")
    if test['test_mode']:
        print(f"  (All emails redirected to test inbox: {test['test_email']})")

    for i, lead in enumerate(leads, 1):
        apply_email_to_lead(lead)
        print(f"\n  --- {i}. {lead['store_name']} ({lead['city']}, {lead['state']}) ---")
        print(f"  To: {lead['email']}")
        print(f"  Score: {lead['confidence_score']} | Fit: {lead['product_fit']}")
        print(f"  Body preview:")
        body_lines = lead['email_body'].split('\n')
        for line in body_lines[:6]:
            print(f"    {line}")
        print(f"    ... ({len(body_lines)} lines total)")

    # Also show skipped
    all_new = get_leads_by_status("new", limit=500)
    skipped_no_email = [l for l in all_new if l.get("confidence_score") in ("A", "B") and not l.get("email")]
    skipped_c = [l for l in all_new if l.get("confidence_score") == "C"]

    if skipped_no_email or skipped_c:
        print(f"\n  --- SKIPPED ---")
        for l in skipped_no_email:
            print(f"  [SKIP] {l['store_name']:35s} | No email")
        for l in skipped_c:
            print(f"  [SKIP] {l['store_name']:35s} | C-grade (needs manual review)")

    print()


def cmd_test_send():
    """Send one test email to test inbox"""
    if not is_configured():
        print("ERROR: SMTP not configured. Check .env file.")
        return

    test = get_test_config()
    if not test["test_email"]:
        print("ERROR: BD_TEST_EMAIL not set in .env")
        return

    print(f"\nSending test email to {test['test_email']}...")

    test_lead = {
        "id": 0,
        "email": test["test_email"],
        "store_name": "TEST STORE",
    }
    apply_email_to_lead(test_lead)

    result = send_one(test_lead, dry_run=False)
    if result["success"]:
        print(f"  Test email sent successfully to {test['test_email']}")
        print(f"  Check your inbox (and spam folder) to verify.")
    else:
        print(f"  Test failed: {result['message']}")


def cmd_send():
    """Send to approved leads"""
    if not is_configured():
        print("ERROR: SMTP not configured. Check .env file.")
        return

    leads = get_approved_leads(limit=100)
    if not leads:
        print("No approved leads to send. Run 'approve-all' first.")
        return

    print(f"\nSending to {len(leads)} approved leads...")
    results = batch_send(leads, dry_run=False)

    sent = sum(1 for r in results if r["status"] == "sent")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    print(f"\nResults: sent={sent}, failed={failed}, skipped={skipped}")
    for r in results:
        icon = "OK" if r["success"] else "XX"
        print(f"  [{icon}] {r.get('store_name', 'N/A'):35s} | {r['message']}")


if __name__ == "__main__":
    init_db()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    commands = {
        "status": cmd_status,
        "approve-all": cmd_approve_all,
        "dry-run": cmd_dry_run,
        "test-send": cmd_test_send,
        "send": cmd_send,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(commands.keys())}")
