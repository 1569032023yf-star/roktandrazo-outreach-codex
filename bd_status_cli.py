#!/usr/bin/env python3
"""
BD Status CLI — Zero-Model Read-Only Status Query.

Usage:
  python bd_status_cli.py all         # Full status
  python bd_status_cli.py today       # Today's send count + gap
  python bd_status_cli.py inventory   # A0 inventory snapshot
  python bd_status_cli.py followup    # Follow-up queue stats
  python bd_status_cli.py inbox       # Inbox risk snapshot
  python bd_status_cli.py scheduler   # Scheduler state

NO model calls. NO collection. NO sending. Database reads only.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from bd_db import (
    get_db, get_config, get_state,
    get_today_sent_asia_shanghai, get_daily_target, get_daily_gap,
    get_risk_gate, get_manual_pause, get_standing_authorization,
    get_scheduler_enabled, get_execution_mode,
)


def now_cst():
    return datetime.utcnow() + timedelta(hours=8)


def cmd_all():
    print(f"=== BD Status — {now_cst().strftime('%Y-%m-%d %H:%M:%S')} CST ===\n")

    # Today
    today_sent = get_today_sent_asia_shanghai()
    target = get_daily_target()
    gap = get_daily_gap()
    print("── Today ──")
    print(f"  Sent:       {today_sent}/{target} (gap: {gap})")

    # Inbox
    conn = get_db()
    c = conn.cursor()
    today_str = now_cst().strftime('%Y-%m-%d')
    today_hard = c.execute("SELECT COUNT(*) FROM bounce_log WHERE bounce_type='hard' AND date(bounce_received_at)=?",
                           (today_str,)).fetchone()[0]
    today_unsub = c.execute("SELECT COUNT(*) FROM suppression_list WHERE reason LIKE 'unsub%' AND date(added_at)=?",
                            (today_str,)).fetchone()[0]
    print(f"  Hard bounces: {today_hard}")
    print(f"  Unsubs:       {today_unsub}")

    # Follow-up queue
    try:
        from workbuddy_candidate_modules.follow_up_queue_builder import build_followup_queue
        fq = build_followup_queue()
        print("\n── Follow-up Queue ──")
        print(f"  Sendable:    {fq['final_sendable_count']}")
        print(f"  Daily limit: min(5, {fq['final_sendable_count']}) = {fq['suggested_daily_count']}")
    except Exception as e:
        print(f"\n── Follow-up Queue ──")
        print(f"  [ERROR] {e}")

    # Inventory
    a0 = c.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1 AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
    """).fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_sent = c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent'").fetchone()[0]
    b_count = c.execute("SELECT COUNT(*) FROM leads WHERE confidence_score='B'").fetchone()[0]
    conn.close()

    print("\n── Inventory ──")
    print(f"  A0 sendable: {a0}/60 (gap: {max(0, 60-a0)})")
    print(f"  B pool:      {b_count}")
    print(f"  Total:       {total} ({total_sent} sent)")

    # Scheduler
    gate = get_risk_gate()
    print("\n── Scheduler ──")
    print(f"  Authority:       {get_config('production_scheduler_authority') or 'not set'}")
    print(f"  Scheduler:       {'ENABLED' if get_scheduler_enabled() else 'DISABLED'}")
    print(f"  Manual pause:    {get_manual_pause()}")
    print(f"  Standing auth:   {get_standing_authorization()}")
    print(f"  Execution mode:  {get_execution_mode()}")
    print(f"  Risk gate:       {gate['status']} ({gate['reason'] or 'N/A'})")
    print(f"  Cooldown until:  {gate['cooldown_until'] or 'N/A'}")


def cmd_today():
    today_sent = get_today_sent_asia_shanghai()
    target = get_daily_target()
    gap = get_daily_gap()
    print(f"Today: {today_sent}/{target} (gap: {gap})")


def cmd_inventory():
    conn = get_db()
    c = conn.cursor()
    a0 = c.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1 AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
    """).fetchone()[0]
    ams = c.execute("SELECT COUNT(*) FROM leads WHERE status='approved_manual_send'").fetchone()[0]
    b = c.execute("SELECT COUNT(*) FROM leads WHERE confidence_score='B'").fetchone()[0]
    cf = c.execute("SELECT COUNT(*) FROM leads WHERE status='contact_form_pool'").fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    conn.close()
    print(f"A0: {a0}  AMS: {ams}  B: {b}  ContactForm: {cf}  Total: {total}")
    print(f"A0 gap to 60: {max(0, 60-a0)}")


def cmd_followup():
    try:
        from workbuddy_candidate_modules.follow_up_queue_builder import build_followup_queue
        fq = build_followup_queue()
        print(f"Final sendable: {fq['final_sendable_count']}")
        print(f"Daily limit: {fq['suggested_daily_count']}")
        print(f"Excluded: time={fq['exclusion_counts'].get('not_14d_yet', 0)} "
              f"replied={fq['exclusion_counts'].get('already_replied', 0)} "
              f"bounced={fq['exclusion_counts'].get('hard_bounced', 0)} "
              f"followed={fq['exclusion_counts'].get('already_followed_up', 0)}")
    except Exception as e:
        print(f"ERROR: {e}")


def cmd_inbox():
    try:
        from agent_reply_monitor import scan_mailbox
        scans = scan_mailbox('INBOX', since_days=1, dry_run=True)
        hard = [s for s in scans if s['type'] == 'hard_bounce']
        replies = [s for s in scans if s['type'] in ('reply', 'hot_reply', 'warm_reply')]
        unsubs = [s for s in scans if s['type'] == 'unsubscribe']
        print(f"Inbox (24h): hard_bounces={len(hard)} replies={len(replies)} unsubs={len(unsubs)} total={len(scans)}")
    except Exception as e:
        print(f"ERROR: {e}")


def cmd_scheduler():
    gate = get_risk_gate()
    print(f"Authority:      {get_config('production_scheduler_authority') or 'not set'}")
    print(f"Scheduler:      {'ENABLED' if get_scheduler_enabled() else 'DISABLED'}")
    print(f"Manual pause:   {get_manual_pause()}")
    print(f"Standing auth:  {get_standing_authorization()}")
    print(f"Execution mode: {get_execution_mode()}")
    print(f"Risk gate:      {gate['status']} ({gate['reason'] or 'N/A'})")
    print(f"Cooldown:       {gate['cooldown_until'] or 'N/A'}")
    # Last runs
    conn = get_db()
    c = conn.cursor()
    runs = c.execute("""
        SELECT stage, MAX(finished_at) FROM job_runs
        WHERE status='completed' GROUP BY stage
    """).fetchall()
    if runs:
        print("\nLast successful runs:")
        for r in runs:
            print(f"  {r[0]:20s} {r[1] or 'never'}")
    conn.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['all', 'today', 'inventory', 'followup', 'inbox', 'scheduler'])
    args = parser.parse_args()

    cmds = {
        'all': cmd_all, 'today': cmd_today, 'inventory': cmd_inventory,
        'followup': cmd_followup, 'inbox': cmd_inbox, 'scheduler': cmd_scheduler,
    }
    cmds[args.command]()
