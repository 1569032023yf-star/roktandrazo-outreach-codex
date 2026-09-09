#!/usr/bin/env python3
"""
Daily Operator Session — Roktandrazo BD Outreach

DESIGNED FOR: Manual operator window 09:00-13:00 Asia/Shanghai.
NOT designed for automated cron scheduling (this machine is not a server).

Usage:
    # Dry run (default — no real sending, no DB changes)
    python daily_session.py --dry-run

    # Live session (WARNING: actually sends emails)
    python daily_session.py --live

    # Outside window: will prompt "wait for next window"
    python daily_session.py --dry-run --force  (override window check)

Schedule:
    08:40-09:00  Batch 1 (5 emails, 3-5min intervals)
    09:15        Scan: bounce + reply + unsub + auto_reply
    09:30-09:50  Batch 2 (5 emails)
    10:05        Scan
    10:20-10:40  Batch 3 (5 emails)
    10:55        Scan
    11:10-11:30  Batch 4 (5 emails)
    11:45        Scan
    12:00        Daily report

SAFETY NOTES:
    - send_pause must be 'false' for live mode
    - Never sends: guessed_email, Exchange MX, B/C pool, suppressed, already sent
    - Hard bounce >= 1 or total bounce >= 2 → pause remaining batches
    - Outside 09:00-13:00 → refuses to send (unless --force)
"""

import argparse
import csv
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bd_db import (
    get_db, get_sendable_leads, update_lead_status, add_to_suppression,
    log_send, is_suppressed, check_sent_log, check_bounce_history,
    check_mx_provider, is_exchange_mx, get_config, set_config
)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(OUT_DIR, exist_ok=True)

# 生产调度权威时区：Asia/Shanghai（UTC+8，无 DST）。
# 客户 IANA 时区只用于报告/分析，不用于主调度。
ASIA_SH = timezone(timedelta(hours=8))

# Session constants
WINDOW_START = 23.0    # 23:00 Asia/Shanghai
WINDOW_END = 24.0      # 24:00 Asia/Shanghai
BATCH_SIZE = 5
DEFAULT_DAILY_TARGET = 40
MIN_DELAY = 45
MAX_DELAY = 85
CATCHUP_MIN_DELAY = 120  # 2 minutes (faster for catchup)
CATCHUP_MAX_DELAY = 180  # 3 minutes


def execute_final_send_plan(batch_date: str, dry_run: bool = True,
                            send_window_override: bool = False) -> dict:
    """Consume a frozen plan only; never query leads to replace skipped recipients.

    send_window_override: 仅一次性时间规则 override（如 P1.2 延误批次补发）。
    只跳过 recipient_scheduler.in_send_window() 这一道时间窗口 gate；
    其余 Gate（suppression/bounce/unsubscribe/duplicate/evidence/hygiene/
    template/tracking/authorization/preflight）全部保持 fail-closed。
    默认 False，永久 Scheduler 规则（Recipient Local Time 10:00）不变。
    """
    from outreach_control import (
        FOLLOW_UP_MAX, MAX_SEND_DELAY_SECONDS, MIN_SEND_DELAY_SECONDS,
        NEW_OUTREACH_TARGET, may_start_smtp_request,
    )
    from final_send_plan import load_planned_entries, mark_entry

    conn = get_db()
    entries = load_planned_entries(conn, batch_date)
    # P2.3I: 本 batch 的 message_type（FSP 通常单一 message_type；混合后取首条，
    # 仅用于把 preflight 的 planned_rows_present / stale_objects 正确 scope 到
    # batch_date + message_type，避免 new_outreach 与 follow_up 相互污染）。
    batch_message_type = entries[0]["message_type"] if entries else None
    result = {'new_outreach': 0, 'follow_up': 0, 'skipped': 0, 'failed': 0, 'test': 0,
              'planned': len(entries), 'preview': []}

    # ── P1.0: 正式链 Authorization ──
    # 创建时 plan_entry_id 必须等于真实 final_send_plan.id（create_send_authorization
    # 内部已强制校验）。真实发送前创建；dry-run 只做 shadow 验证不写库。
    from bd_sender import create_send_authorization
    auth_entries = [
        {"lead_id": e["lead_id"], "recipient_email": e["recipient_email"],
         "message_type": e["message_type"], "final_plan_entry_id": e["id"]}
        for e in entries
    ]
    authorization_id = ""
    # P2.3B: 真实 preflight 硬门 —— 创建授权前先跑 PRE_AUTH 检查（不含 auth_entries，
    # 因为授权此刻尚不存在）。结果必须来自可追溯到 real preflight evidence 的检查，
    # 不得再用 create_send_authorization(preflight_passed=True) 硬编码假通过。
    from preflight_gate import run_preflight
    _snapshot_path = os.path.join(OUT_DIR, f"frozen_{batch_date}.json")
    # dry-run 用 persist_cache=False（只读，不写 system_config.mx_cache）；live 才写真实缓存。
    _pf_pre = run_preflight(conn, batch_date, snapshot_path=_snapshot_path,
                            persist_cache=(not dry_run), include_auth_entries=False,
                            message_type=batch_message_type)
    result["preflight_pre_auth"] = {
        "pass": _pf_pre["pass"],
        "blocks": _pf_pre["blocks"],
        "checked_at": _pf_pre["checked_at"],
    }
    if entries and not dry_run:
        plan_id = entries[0]["plan_id"]
        # 使用与 conn 相同的 DB 文件（避免 bd_sender.DB_PATH 与 bd_db.DB_PATH 不一致导致写错库）
        _db_file = conn.execute("PRAGMA database_list").fetchone()[2]
        # 幂等：同一 plan 已存在 approved auth（ET/CT 分批多次调用）→ 复用，不重复创建
        existing = None
        if _table_exists(conn, "send_authorizations"):
            existing = conn.execute(
                "SELECT authorization_id FROM send_authorizations "
                "WHERE plan_id=? AND status='approved' ORDER BY rowid DESC LIMIT 1",
                (plan_id,),
            ).fetchone()
        if existing:
            authorization_id = existing["authorization_id"]
            result["authorization_id"] = authorization_id
            result["authorization_reused"] = True
        elif _pf_pre["pass"]:
            # 真实 preflight 通过 → 用真实结果创建授权（preflight_status='passed' 可追溯到本次检查）
            auth = create_send_authorization(
                plan_id, batch_date, auth_entries,
                preflight_passed=True, preflight_passed_status='passed',
                db_path=_db_file,
            )
            authorization_id = auth["authorization_id"]
            result["authorization_id"] = authorization_id
            # POST_AUTH 一致性校验：授权已存在 → 纳入 auth_entries 检查（plan 与 entries 逐条一致）
            _pf_post = run_preflight(conn, batch_date, snapshot_path=_snapshot_path,
                                     include_auth_entries=True, message_type=batch_message_type)
            result["preflight_post_auth"] = {
                "pass": _pf_post["pass"],
                "blocks": _pf_post["blocks"],
                "checked_at": _pf_post["checked_at"],
            }
        else:
            # 真实 preflight 失败 → fail-closed：不创建授权，send_one 将因无 approved 授权而拒绝，
            # 条目被标记 failed，SMTP 保持 0。
            result["preflight_blocked"] = True
            authorization_id = ""
    else:
        result["authorization_shadow"] = {
            "entries": len(auth_entries),
            "plan_entry_id_is_fsp_id": all(isinstance(e["final_plan_entry_id"], int) for e in auth_entries),
        }

    limits = {'new_outreach': NEW_OUTREACH_TARGET, 'follow_up': FOLLOW_UP_MAX}
    for entry in entries:
        message_type = entry['message_type']
        if result[message_type] >= limits[message_type]:
            break
        lead = _load_and_recheck_plan_lead(conn, entry)
        if lead is None:
            if not dry_run:
                mark_entry(conn, entry['id'], 'skipped', 'recipient_state_changed_after_plan')
                conn.commit()
                _close_unsent_auth_entry(authorization_id, entry['id'])
            result['skipped'] += 1
            continue
        # P2.3I: 收件人当地时区窗口（08:00-11:10 local）——客户当地时间才是业务时钟。
        # 不用全局 Asia/Shanghai 23:00 gate；UNSET/UNRESOLVED/非工作日/窗口外 → BLOCK。
        if not dry_run:
            from recipient_scheduler import in_send_window
            tz_name = str(lead.get('recipient_timezone') or '').strip()
            tz_status = str(lead.get('timezone_status') or '').upper()
            if not tz_name or tz_status != 'RESOLVED':
                mark_entry(conn, entry['id'], 'skipped', 'recipient_timezone_unresolved')
                conn.commit()
                _close_unsent_auth_entry(authorization_id, entry['id'])
                result['skipped'] += 1
                continue
            if not send_window_override and not in_send_window(tz_name):
                mark_entry(conn, entry['id'], 'skipped', 'recipient_local_time_outside_0800_1110')
                conn.commit()
                _close_unsent_auth_entry(authorization_id, entry['id'])
                result['skipped'] += 1
                continue
        lead.update({
            'email_subject': entry['subject'], 'email_body': entry['body_text'],
            'email_body_html': entry['body_html'] or '', 'template_id': entry['template_id'] or '',
            'customer_type': entry['customer_type'] or '', 'batch_id': entry['plan_id'],
            'message_type': message_type, 'outreach_batch_date': batch_date,
            'final_plan_entry_id': entry['id'], 'authorization_id': authorization_id,
        })
        from bd_sender import send_one
        sent = send_one(lead, dry_run=dry_run)
        if dry_run:
            result['preview'].append({
                'entry_id': entry['id'], 'lead_id': entry['lead_id'], 'message_type': message_type,
                'result': sent.get('status'), 'message': sent.get('message', ''),
            })
            continue
        if sent.get('status') == 'test':
            result['test'] += 1
            continue
        if sent.get('success'):
            _persist_final_plan_success(conn, entry, lead)
            result[message_type] += 1
        else:
            mark_entry(conn, entry['id'], 'failed', sent.get('message', 'send_failed'))
            _close_unsent_auth_entry(authorization_id, entry['id'])
            result['failed'] += 1
        conn.commit()
        if not dry_run and sent.get('success'):
            time.sleep(random.randint(MIN_SEND_DELAY_SECONDS, MAX_SEND_DELAY_SECONDS))
    conn.close()
    return result


def _persist_final_plan_success(conn, entry: dict, lead: dict) -> None:
    """Commit the immutable-plan result, history, and lead state together.

    P1.0 单写保证：send_one._commit_send_success 已在一个事务里原子完成
    send_log / final_send_plan→sent / authorization→consumed / leads→sent。
    本函数只补 send_one 未覆盖的部分：follow_up 的 followup_count 递增。
    1 次 SMTP Accepted = 恰好 1 条 send_log，绝不在此重复 INSERT send_log。
    """
    now = datetime.now(ASIA_SH).isoformat()
    if entry['message_type'] == 'follow_up':
        conn.execute("UPDATE leads SET followup_count=COALESCE(followup_count,0)+1, last_followup_at=? WHERE id=?",
                     (now, entry['lead_id']))


def _close_unsent_auth_entry(authorization_id: str | None, plan_entry_id: int | None) -> None:
    """Skipped/failed plan entries MUST also consume their authorization entry.

    Root cause of the 2026-09-02 blackout: on 2026-09-01, 5 leads were skipped
    (recipient window closed) or failed (auth expired mid-batch). Their
    final_send_plan rows were marked skipped/failed, but their
    send_authorization_entries stayed 'pending' forever -> the 09-01 auth never
    reached pending=0 -> never marked consumed -> check_stale_objects flagged it
    old_active_auth -> blocked the 2026-09-02 preflight -> all 5 09-02 rows failed
    with 'No authorization_id provided.' (0 sends).

    Fix: whenever an entry ends unsent, consume its auth entry so the parent auth
    can terminate. The lead, if still eligible, is re-planned by the plan builder
    next batch; this only closes the stale authorization-scope slot.
    """
    if not authorization_id or not plan_entry_id:
        return
    try:
        from bd_sender import consume_authorization_entry
        consume_authorization_entry(authorization_id, plan_entry_id)
    except Exception:
        pass


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _columns(conn, name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({name})")} if _table_exists(conn, name) else set()


def _lead_or_email_exists(conn, table: str, lead_id: int, email: str, extra_sql: str = '', params: tuple = ()) -> bool:
    if not _table_exists(conn, table):
        return False
    cols = _columns(conn, table)
    matches, values = [], []
    if 'lead_id' in cols:
        matches.append('lead_id=?')
        values.append(lead_id)
    if 'email' in cols:
        matches.append('lower(email)=lower(?)')
        values.append(email)
    if not matches:
        return False
    return bool(conn.execute(
        f"SELECT 1 FROM {table} WHERE ({' OR '.join(matches)}) {extra_sql} LIMIT 1", tuple(values) + params
    ).fetchone())


def _load_and_recheck_plan_lead(conn, entry: dict) -> dict | None:
    """Re-read the live lead and apply a message-type-specific gate before SMTP."""
    row = conn.execute('SELECT * FROM leads WHERE id=?', (entry['lead_id'],)).fetchone()
    if not row:
        return None
    lead = dict(row)
    email = str(entry['recipient_email'] or '').strip().lower()
    if str(lead.get('email') or '').strip().lower() != email:
        return None
    if entry['message_type'] == 'follow_up':
        return lead if _follow_up_gate(conn, lead, entry) else None
    return lead if _new_outreach_gate(conn, lead, entry) else None


def _new_outreach_gate(conn, lead: dict, entry: dict) -> bool:
    from campaign_eligible_v2 import review_campaign_eligible_v2

    # 正式政策：Broad Ready → ICP Qualified → Campaign Eligible → Final Send Plan。
    # Strict A0 只是优先层，不是唯一发送门槛。发送前 recheck 用 Campaign Eligible 判定。
    # status 不再硬性要求 'new'（Campaign Eligible 已含未发送/未 suppression 检查，
    # 且已复核的 manual_review_needed lead 也可进入发送池）。
    if lead.get('unsubscribed_at'):
        return False
    if _table_exists(conn, 'manual_send_queue') and conn.execute(
        "SELECT 1 FROM manual_send_queue WHERE lead_id=? AND COALESCE(status,'') NOT IN ('rejected','cancelled','consumed')", (lead['id'],)
    ).fetchone():
        return False
    if _lead_or_email_exists(conn, 'send_log', lead['id'], entry['recipient_email'], "AND status='sent' AND COALESCE(message_type,'new_outreach')='new_outreach'"):
        return False
    # explicit fail-closed rechecks (additive to V2 broad_ready history checks)
    if is_suppressed(entry['recipient_email']):
        return False
    if check_bounce_history(entry['recipient_email'])['hard']:
        return False
    # Campaign Eligible V2: V1 + explicit MX PASS + evidence fresh + official source quality
    r = review_campaign_eligible_v2(lead, {"conn": conn})
    return bool(r.get("eligible"))


def _follow_up_gate(conn, lead: dict, entry: dict) -> bool:
    """Follow-up requires an initial send; it must never be blocked merely by it."""
    email = entry['recipient_email']
    status = str(lead.get('status') or '').lower()
    if status in {'unsubscribed', 'review_rejected', 'rejected', 'deferred'} or lead.get('unsubscribed_at'):
        return False
    if str(lead.get('review_status') or '').lower() in {'rejected', 'deferred', 'recheck_pending'}:
        return False
    if str(lead.get('manual_decision') or '').lower() in {'rejected', 'deferred'}:
        return False
    if _lead_or_email_exists(conn, 'suppression_list', lead['id'], email):
        return False
    if _lead_or_email_exists(conn, 'bounce_log', lead['id'], email,
                             "AND lower(COALESCE(bounce_type,'')) IN ('hard','policy','permanent')"):
        return False
    if _lead_or_email_exists(conn, 'reply_log', lead['id'], email):
        return False
    if not _lead_or_email_exists(conn, 'send_log', lead['id'], email,
                                 "AND status='sent' AND COALESCE(message_type,'new_outreach')='new_outreach'"):
        return False
    if int(lead.get('followup_count') or 0) >= 1 or lead.get('last_followup_at'):
        return False
    if _lead_or_email_exists(conn, 'send_log', lead['id'], email,
                             "AND status='sent' AND COALESCE(message_type,'')='follow_up'"):
        return False
    if _lead_or_email_exists(conn, 'send_log', lead['id'], email,
                             "AND status='sent' AND COALESCE(message_type,'')='follow_up' AND outreach_batch_date=?", (entry['outreach_batch_date'],)):
        return False
    return True

BATCH_SCHEDULE = [
    {'batch': 1, 'start': '08:40', 'end': '09:00', 'scan_at': '09:15'},
    {'batch': 2, 'start': '09:30', 'end': '09:50', 'scan_at': '10:05'},
    {'batch': 3, 'start': '10:20', 'end': '10:40', 'scan_at': '10:55'},
    {'batch': 4, 'start': '11:10', 'end': '11:30', 'scan_at': '11:45'},
]


def is_in_window() -> bool:
    """Check the 23:00-23:59:30 Asia/Shanghai new-request window."""
    from outreach_control import may_start_smtp_request
    return may_start_smtp_request()


def is_window_about_to_close(batch_schedule_index: int) -> bool:
    """Check if there's enough time left for the next batch."""
    now = datetime.now(ASIA_SH)
    current_hour = now.hour + now.minute / 60.0
    if batch_schedule_index < len(BATCH_SCHEDULE):
        batch_end_hour = float(BATCH_SCHEDULE[batch_schedule_index]['end'].replace(':', '.'))
        # Need at least 30 min buffer
        return current_hour + 0.5 > batch_end_hour
    return True


def get_today_sent_count() -> int:
    """Count how many emails were sent today."""
    today = datetime.now(ASIA_SH).strftime('%Y-%m-%d')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent' AND date(sent_at) = ?", (today,))
    count = c.fetchone()[0]
    conn.close()
    return count


def batch_send(batch_num: int, leads: list[dict], dry_run: bool,
               min_delay: int = MIN_DELAY, max_delay: int = MAX_DELAY) -> list[dict]:
    """Send one batch (max 5 emails). Returns list of result dicts."""
    results = []
    batch_sent = 0
    batch_failed = 0
    batch_bounced = 0
    batch_skipped = 0
    batch_store_list = []

    print(f"\n    {'[DRY RUN]' if dry_run else ''} Starting batch {batch_num} ({len(leads[:BATCH_SIZE])} emails)...")
    for i, lead in enumerate(leads[:BATCH_SIZE], 1):
        email = lead.get('email', '').strip().lower()
        lead_id = lead.get('id')
        store_name = lead.get('store_name', '?')
        store_info = {'store_name': store_name, 'email': email, 'status': 'unknown'}

        if dry_run:
            delay = random.randint(min_delay, max_delay)
            print(f"    {i}. {store_name:35s} | {email:35s} | wait {delay}s")
            store_info['status'] = 'dry_run'
            store_info['delay'] = delay
            batch_store_list.append(store_info)
            results.append({
                'store_name': store_name, 'email': email,
                'status': 'dry_run', 'message': 'DRY RUN',
            })
            continue

        # --- Pre-send checks ---
        if is_suppressed(email):
            print(f"    {i}. {store_name}: SKIPPED (suppressed)")
            store_info['status'] = 'skipped'
            store_info['reason'] = 'suppressed'
            batch_skipped += 1
            batch_store_list.append(store_info)
            results.append({'store_name': store_name, 'email': email, 'status': 'skipped', 'message': 'suppressed'})
            continue

        if check_sent_log(email):
            print(f"    {i}. {store_name}: SKIPPED (already sent)")
            store_info['status'] = 'skipped'
            store_info['reason'] = 'already sent'
            batch_skipped += 1
            batch_store_list.append(store_info)
            results.append({'store_name': store_name, 'email': email, 'status': 'skipped', 'message': 'already sent'})
            continue

        bounce = check_bounce_history(email)
        if bounce['hard']:
            print(f"    {i}. {store_name}: SKIPPED (hard bounce)")
            store_info['status'] = 'skipped'
            store_info['reason'] = 'hard bounce'
            batch_skipped += 1
            batch_store_list.append(store_info)
            results.append({'store_name': store_name, 'email': email, 'status': 'skipped', 'message': 'hard bounce'})
            continue

        domain = email.split('@')[1] if '@' in email else ''
        if domain:
            mx = check_mx_provider(domain)
            if mx in ('exchange', 'exchange_online'):
                print(f"    {i}. {store_name}: SKIPPED (Exchange MX: {mx})")
                store_info['status'] = 'skipped'
                store_info['reason'] = f'Exchange MX: {mx}'
                batch_skipped += 1
                batch_store_list.append(store_info)
                results.append({'store_name': store_name, 'email': email, 'status': 'skipped', 'message': f'Exchange MX: {mx}'})
                continue

        # --- Draft email using V5 template ---
        from bd_template import apply_email_to_lead
        lead = apply_email_to_lead(lead)

        # --- Send (via bd_sender) ---
        subject = lead.get('email_subject', '') or f"Wholesale Inquiry - {lead.get('store_name', '')}"
        body_text = lead.get('email_body', '') or f"Hi {lead.get('store_name', '')} team,\n\nThis is a test message..."
        # Ensure fields are populated in lead dict for bd_sender
        lead['email_subject'] = subject
        lead['email_body'] = body_text

        from bd_sender import send_one
        result = send_one(lead, dry_run=False)
        result['store_name'] = store_name
        result['email'] = email
        results.append(result)

        if result.get('status') == 'sent':
            batch_sent += 1
            store_info['status'] = 'sent'
            print(f"    {i}. {store_name}: SENT to {email}")
        elif result.get('status') == 'bounced':
            batch_bounced += 1
            store_info['status'] = 'bounced'
            store_info['reason'] = result.get('message', '')
            print(f"    {i}. {store_name}: BOUNCED ({result.get('message', '')})")
        else:
            batch_failed += 1
            store_info['status'] = 'failed'
            store_info['reason'] = result.get('message', '')
            print(f"    {i}. {store_name}: FAILED ({result.get('message', '')})")

        batch_store_list.append(store_info)

        # Delay between emails
        if i < len(leads[:BATCH_SIZE]):
            delay = random.randint(min_delay, max_delay)
            print(f"       waiting {delay}s...")
            time.sleep(delay)

    print(f"    Batch {batch_num} summary: sent={batch_sent} failed={batch_failed} bounced={batch_bounced} skipped={batch_skipped}")
    return results


def scan_bounce_and_reply(dry_run: bool) -> dict:
    """Scan for bounce notifications and replies after a batch.
    Returns scan results dict.
    """
    result = {
        'bounces': [],
        'hard_bounces': [],
        'policy_bounces': [],
        'replies': [],
        'hot_replies': [],
        'unsubscribes': [],
        'auto_replies': [],
    }

    if dry_run:
        print(f"    [DRY RUN] Would scan IMAP for: bounce / reply / unsub / auto_reply")
        return result

    try:
        from agent_bounce_auditor import scan_bounces
        from agent_reply_monitor import scan_replies

        print("    Scanning bounces...")
        bounce_results = scan_bounces(dry_run=False)
        if isinstance(bounce_results, dict):
            for b in bounce_results.get('bounces', []):
                result['bounces'].append(b)
                if b.get('type') == 'message_id_missing':
                    # Sender-side header defect: do not suppress the recipient.
                    result['policy_bounces'].append(b)
                    print(f"    [MESSAGE-ID] {b.get('email', '')}: missing Message-ID bounce - NOT suppressed")
                elif b.get('type') == 'hard':
                    result['hard_bounces'].append(b)
                    # Auto-suppress hard bounces
                    email = b.get('email', '')
                    if email:
                        add_to_suppression(email, 'hard_bounce')
                elif b.get('type') == 'policy':
                    result['policy_bounces'].append(b)

        print("    Scanning replies...")
        reply_results = scan_replies(dry_run=False)
        if isinstance(reply_results, dict):
            result['replies'] = reply_results.get('replies', [])
            result['hot_replies'] = reply_results.get('hot_replies', [])
            result['unsubscribes'] = reply_results.get('unsubscribes', [])
            result['auto_replies'] = reply_results.get('auto_replies', [])

    except Exception as e:
        print(f"    [SCAN ERROR] {e}")

    return result


def should_pause_after_scan(scan_result: dict) -> tuple[bool, str]:
    """Check if we should pause remaining batches based on scan result.
    Returns (should_pause, reason).
    """
    if len(scan_result.get('hard_bounces', [])) >= 1:
        return True, f"Hard bounce >= 1 ({len(scan_result['hard_bounces'])})"
    if len(scan_result.get('bounces', [])) >= 2:
        return True, f"Total bounce >= 2 ({len(scan_result['bounces'])})"
    if len(scan_result.get('unsubscribes', [])) >= 1:
        return True, f"Unsubscribe >= 1 ({len(scan_result['unsubscribes'])})"
    return False, ""


def run_scan(dry_run: bool, label: str) -> dict:
    """Run a scan cycle and print results."""
    print(f"\n  [{label}] Scanning...")
    scan_result = scan_bounce_and_reply(dry_run)

    if not dry_run:
        b = scan_result
        print(f"    Bounces: {len(b['bounces'])} (hard: {len(b['hard_bounces'])}, policy: {len(b['policy_bounces'])})")
        print(f"    Replies: {len(b['replies'])} (hot: {len(b['hot_replies'])})")
        print(f"    Unsubscribes: {len(b['unsubscribes'])}")
        print(f"    Auto-replies: {len(b['auto_replies'])}")
    else:
        print(f"    [DRY RUN] Would report bounce/reply stats here")

    return scan_result


def generate_daily_report(dry_run: bool, session_results: dict, daily_target: int = DEFAULT_DAILY_TARGET):
    """Generate the 12:00 daily report and save to file."""
    today = datetime.now(ASIA_SH).strftime('%Y-%m-%d')
    report_path = os.path.join(OUT_DIR, f'daily_report_{today}.md')

    total_sent = session_results.get('total_sent', 0)
    total_failed = session_results.get('total_failed', 0)
    total_bounced = session_results.get('total_bounced', 0)
    total_skipped = session_results.get('total_skipped', 0)
    scan_results = session_results.get('scan_results', [])
    pause_reason = session_results.get('pause_reason', '')
    batch_details = session_results.get('batch_details', [])
    catchup = session_results.get('catchup', False)
    deadline = session_results.get('deadline', '')

    # Aggregate scan data
    all_hard_bounces = []
    all_policy_bounces = []
    all_replies = []
    all_hot_replies = []
    all_unsubscribes = []
    all_auto_replies = []
    for sr in scan_results:
        all_hard_bounces.extend(sr.get('hard_bounces', []))
        all_policy_bounces.extend(sr.get('policy_bounces', []))
        all_replies.extend(sr.get('replies', []))
        all_hot_replies.extend(sr.get('hot_replies', []))
        all_unsubscribes.extend(sr.get('unsubscribes', []))
        all_auto_replies.extend(sr.get('auto_replies', []))

    # Pool state
    conn = get_db()
    c = conn.cursor()
    a0_count = c.execute("""SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1 AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page')
        AND email IS NOT NULL AND email != ''""").fetchone()[0]
    ams_count = c.execute("SELECT COUNT(*) FROM leads WHERE status='approved_manual_send'").fetchone()[0]
    b_count = c.execute("SELECT COUNT(*) FROM leads WHERE status IN ('new', 'manual_review_needed') AND confidence_score='B' AND email IS NOT NULL AND email != ''").fetchone()[0]
    c_count = c.execute("""SELECT COUNT(*) FROM leads WHERE status='contact_form_pool'
        OR (status='new' AND (email IS NULL OR email='') AND contact_form_url IS NOT NULL AND contact_form_url != '')""").fetchone()[0]
    sp = get_config('send_pause') or 'true'
    pr = get_config('pause_reason') or ''
    conn.close()

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# BD Daily Report — {today}\n\n")
        if catchup:
            f.write(f"> **Today Catch-up Mode** | Target: {daily_target} | Deadline: {deadline or '12:00'}\n\n")
        f.write("---\n\n")

        # 1. Send summary
        f.write("## [发送摘要]\n\n")
        f.write(f"| 指标 | 数值 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 今日目标 | {daily_target} |\n")
        f.write(f"| 实际发送 | {total_sent} |\n")
        f.write(f"| 发送失败 | {total_failed} |\n")
        f.write(f"| 跳过 | {total_skipped} |\n")
        f.write(f"| 退信 | {total_bounced} |\n")
        f.write(f"| 完成率 | {total_sent / daily_target * 100:.0f}% |\n\n")

        # 2. Per-batch breakdown
        f.write("## [每批发送清单]\n\n")
        for bd in batch_details:
            bn = bd['batch']
            f.write(f"### Batch {bn}\n\n")
            f.write(f"| # | 门店 | 邮箱 | 状态 |\n")
            f.write(f"|---|------|------|------|\n")
            for i, s in enumerate(bd.get('stores', []), 1):
                status_icon = {'sent': 'SENT', 'skipped': 'SKIP', 'bounced': 'BOUNCE', 'failed': 'FAIL', 'dry_run': 'DRY'}.get(s.get('status',''), s.get('status',''))
                f.write(f"| {i} | {s.get('name','?')} | {s.get('email','')} | {status_icon} |\n")
            f.write(f"\nBatch {bn} summary: sent={bd['sent']} failed={bd['failed']} bounced={bd['bounced']} skipped={bd['skipped']}\n\n")

        # 3. Delivery status
        f.write("## [送达状态]\n\n")
        f.write(f"| 类型 | 数量 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 成功送达 | {total_sent} |\n")
        f.write(f"| Hard Bounce | {len(all_hard_bounces)} |\n")
        f.write(f"| Policy Bounce | {len(all_policy_bounces)} |\n")

        # 4. Replies
        f.write("\n## [回复摘要]\n\n")
        f.write(f"| 类型 | 数量 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 新回复 | {len(all_replies)} |\n")
        f.write(f"| 高意向回复 | {len(all_hot_replies)} |\n")
        f.write(f"| 自动回复 | {len(all_auto_replies)} |\n")
        f.write(f"| 退订 | {len(all_unsubscribes)} |\n\n")

        # 5. Pool remaining
        f.write("## [池剩余]\n\n")
        f.write(f"| 池 | 数量 | 说明 |\n")
        f.write(f"|---|------|------|\n")
        f.write(f"| A0 (可发) | {a0_count} | 已验证邮箱，非Exchange |\n")
        f.write(f"| A1 (Exchange) | 0 | 已验证邮箱，Exchange MX |\n")
        f.write(f"| approved_manual | {ams_count} | 人工确认邮箱 |\n")
        f.write(f"| B (需人工确认) | {b_count} | 猜测邮箱 |\n")
        f.write(f"| C (contact form) | {c_count} | 仅contact form |\n\n")

        # 6. Pause state
        f.write("## [暂停状态]\n\n")
        f.write(f"| 项 | 值 |\n")
        f.write(f"|----|----|\n")
        f.write(f"| send_pause | {sp} |\n")
        f.write(f"| pause_reason | {pr} |\n")
        if pause_reason:
            f.write(f"| batch_paused | {pause_reason} |\n\n")
        else:
            f.write(f"| batch_paused | - |\n\n")

        # 7. Anomalies
        f.write("## [违规/异常]\n\n")
        anomalies = []
        if all_hard_bounces:
            anomalies.append(f"Hard bounce detected: {len(all_hard_bounces)} emails (auto-suppressed)")
        if all_policy_bounces:
            anomalies.append(f"Policy bounce detected: {len(all_policy_bounces)}")
        if all_unsubscribes:
            anomalies.append(f"Unsubscribe detected: {len(all_unsubscribes)}")
        if total_failed > 3:
            anomalies.append(f"High failure rate: {total_failed}/{total_sent + total_failed}")
        if total_sent < daily_target:
            anomalies.append(f"未完成目标 (sent {total_sent}/{daily_target})")
        if not anomalies:
            f.write(f"  无异常\n\n")
        else:
            for a in anomalies:
                f.write(f"  * {a}\n")
            f.write("\n")

        # 8. Suggestions
        f.write("## [建议]\n\n")
        if dry_run:
            f.write(f"  * DRY RUN — no real emails were sent\n\n")
        else:
            if a0_count < daily_target:
                f.write(f"  * A0 剩余 {a0_count} 条，不足下次 {daily_target} 封目标\n")
                f.write(f"  * 建议先运行 Browser Verification 清洗 B 池，再只人工查看 Top 30 高价值例外\n")
            else:
                f.write(f"  * A0 剩余 {a0_count} 条，足够下次发送\n")
            if a0_count >= daily_target:
                f.write(f"  * 建议明天按 09:00-13:00 Asia/Shanghai 标准窗口执行\n")
            else:
                f.write(f"  * 建议先补足 A0 或 approved_manual_send 后再发送\n")
            if b_count > 0:
                f.write(f"  * B 池仍有 {b_count} 条待浏览器验证，不建议全量人工确认\n")
            if sp == 'true' and not pause_reason:
                f.write(f"  * send_pause 仍为 true — 如需发送请先解除\n")
            f.write(f"  * 下一个 operator window: 明天 09:00-13:00 Asia/Shanghai\n\n")

    print(f"\n  [REPORT] Daily report saved: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description='Daily Operator Session')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run (no real send)')
    parser.add_argument('--live', action='store_true', help='Live send mode')
    parser.add_argument('--force', action='store_true', help='Override window check')
    parser.add_argument('--skip-window-check', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--today-catchup', action='store_true',
                        help='Today Catch-up Mode: send immediately, no window restriction, 2-3min intervals')
    parser.add_argument('--target-count', type=int, default=DEFAULT_DAILY_TARGET,
                        help=f'Target emails to send (default: {DEFAULT_DAILY_TARGET})')
    parser.add_argument('--deadline', type=str, default='',
                        help='Deadline time, e.g. "12:00 Asia/Shanghai". If reached, stop sending.')
    parser.add_argument('--outreach-batch-date', type=str, default='',
                        help='Required for live mode; consumes only the immutable Final Send Plan for this batch.')
    args = parser.parse_args()

    dry_run = not args.live
    catchup = args.today_catchup
    daily_target = args.target_count
    deadline_str = args.deadline

    print("=" * 60)
    title = "BD DAILY OPERATOR SESSION"
    if catchup:
        title = "BD TODAY CATCH-UP MODE"
    print(title)
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE SEND'}{' (Catch-up)' if catchup else ''}")
    if not dry_run:
        if not args.outreach_batch_date:
            print('[BLOCKED] Live session requires --outreach-batch-date and an immutable Final Send Plan.')
            return
        result = execute_final_send_plan(args.outreach_batch_date, dry_run=False)
        print(f"[FINAL PLAN] {result}")
        return
    if catchup and not dry_run:
        print(f"Target: {daily_target} emails before {deadline_str or '12:00'}")

    # --- Window check (skip for catchup mode) ---
    if not args.force and not catchup:
        if not is_in_window():
            now_str = datetime.now(ASIA_SH).strftime('%H:%M')
            print(f"\n[WINDOW] Current time: {now_str}")
            print(f"[WINDOW] Operator window: 09:00 - 13:00 Asia/Shanghai")
            print(f"[WINDOW] Outside window — not sending.")
            print(f"[WINDOW] Please wait for the next 09:00-13:00 Asia/Shanghai window,")
            print(f"         or use --force to override this check.")
            sys.exit(0)
        else:
            print(f"\n[WINDOW] Within operator window (09:00-13:00 Asia/Shanghai) [OK]")
    elif catchup:
        print(f"\n[CATCHUP] Today Catch-up Mode activated — window restriction overridden.")
        print(f"[CATCHUP] All safety checks remain active.")

    # --- Live mode check: send_pause must be false ---
    if not dry_run:
        sp = get_config('send_pause')
        if sp == 'true':
            print(f"\n[BLOCKED] send_pause = true")
            reason = get_config('pause_reason') or 'No reason set'
            print(f"  Reason: {reason}")
            print(f"  Set send_pause to 'false' before running live session.")
            print(f"  Use --dry-run for testing without sending.")
            sys.exit(1)

        print(f"\n[LIVE] Sending mode active. This WILL send real emails.")
        if not catchup:
            print("[LIVE] Press Ctrl+C within 5 seconds to abort...")
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                print("\n[ABORTED] by user")
                sys.exit(0)
        else:
            print("[CATCHUP] Proceeding immediately (user confirmed catch-up)...")
        print("[LIVE] Proceeding...")

    print(f"\n[INIT] Today's sent count so far: {get_today_sent_count()}")

    # Deadline check helper
    def is_past_deadline():
        if deadline_str:
            try:
                now = datetime.now(ASIA_SH)
                deadline_parts = deadline_str.split()[0].split(':')
                dl_hour = int(deadline_parts[0])
                dl_min = int(deadline_parts[1])
                current_hour = now.hour + now.minute / 60.0
                dl_hour_float = dl_hour + dl_min / 60.0
                if current_hour >= dl_hour_float:
                    return True
            except:
                pass
        return False

    # Use faster intervals for catchup
    if catchup:
        effective_min_delay = CATCHUP_MIN_DELAY
        effective_max_delay = CATCHUP_MAX_DELAY
    else:
        effective_min_delay = MIN_DELAY
        effective_max_delay = MAX_DELAY

    print(f"\n[INIT] Interval: {effective_min_delay}s-{effective_max_delay}s per email")
    print(f"[INIT] Daily target: {daily_target}")

    # ================================================================
    # Session execution
    # ================================================================
    session_results = {
        'total_sent': 0,
        'total_failed': 0,
        'total_bounced': 0,
        'total_skipped': 0,
        'scan_results': [],
        'pause_reason': '',
        'batch_details': [],
        'catchup': catchup,
        'daily_target': daily_target,
        'deadline': deadline_str,
    }
    all_batch_results = []

    # In catchup mode: 4 sequential batches
    # In normal mode: follow BATCH_SCHEDULE
    if catchup:
        batch_schedule = [
            {'batch': 1, 'label': 'Catch-up Batch 1'},
            {'batch': 2, 'label': 'Catch-up Batch 2'},
            {'batch': 3, 'label': 'Catch-up Batch 3'},
            {'batch': 4, 'label': 'Catch-up Batch 4'},
        ]
    else:
        batch_schedule = BATCH_SCHEDULE

    for batch_info in batch_schedule:
        bnum = batch_info['batch']

        # Deadline check before each batch
        if is_past_deadline():
            print(f"\n  [DEADLINE] Reached deadline {deadline_str}. Stopping.")
            session_results['pause_reason'] = f'Deadline reached: {deadline_str}'
            break

        # Check if we should continue after pause
        if session_results['pause_reason']:
            print(f"\n  [PAUSED] Remaining batches skipped. Reason: {session_results['pause_reason']}")
            break

        # Check daily limit
        today_sent = get_today_sent_count() if not dry_run else 0
        remaining = daily_target - today_sent
        if remaining <= 0:
            print(f"\n  [LIMIT] Daily target of {daily_target} reached. Stopping.")
            break

        batch_size = min(BATCH_SIZE, remaining)

        # Fetch leads for this batch
        leads = get_sendable_leads(limit=batch_size)
        if not leads:
            print(f"\n  [EMPTY] No sendable leads remaining.")
            break

        batch_label = batch_info.get('label', f"Batch {bnum}")
        print(f"\n  >>> {batch_label} ({batch_size} emails)")
        batch_results = batch_send(bnum, leads[:batch_size], dry_run, effective_min_delay, effective_max_delay)

        # Track results
        for r in batch_results:
            status = r.get('status', '')
            if status == 'sent':
                session_results['total_sent'] += 1
            elif status in ('failed', 'error'):
                session_results['total_failed'] += 1
            elif status == 'bounced':
                session_results['total_bounced'] += 1
            elif status == 'skipped':
                session_results['total_skipped'] += 1

        all_batch_results.extend(batch_results)

        # Store batch details for report
        batch_detail = {
            'batch': bnum,
            'sent': sum(1 for r in batch_results if r.get('status') == 'sent'),
            'failed': sum(1 for r in batch_results if r.get('status') in ('failed', 'error')),
            'bounced': sum(1 for r in batch_results if r.get('status') == 'bounced'),
            'skipped': sum(1 for r in batch_results if r.get('status') == 'skipped'),
            'stores': [{'name': r.get('store_name','?'), 'email': r.get('email',''), 'status': r.get('status','')}
                       for r in batch_results],
        }
        session_results.setdefault('batch_details', []).append(batch_detail)

        # Scan after batch
        scan_result = run_scan(dry_run, f"Scan after Batch {bnum}")
        session_results['scan_results'].append(scan_result)

        # Check if we should pause
        should_pause, reason = should_pause_after_scan(scan_result)
        if should_pause:
            session_results['pause_reason'] = reason
            print(f"\n  [PAUSE] Triggered: {reason}")
            # NOTE: send_pause is NOT auto-set here.
            # The orchestrator (daily_operator_auto.py) handles pausing
            # based on aggregated session results.

        # If not the last batch, wait until next batch time
        if bnum < 4 and not session_results['pause_reason']:
            print(f"\n  [WAIT] Next batch at {BATCH_SCHEDULE[bnum]['start']}...")

    # ================================================================
    # Daily report
    # ================================================================
    print(f"\n{'=' * 60}")
    print("SESSION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total sent:    {session_results['total_sent']}")
    print(f"  Total failed:  {session_results['total_failed']}")
    print(f"  Total bounced: {session_results['total_bounced']}")
    print(f"  Total skipped: {session_results['total_skipped']}")
    if session_results['pause_reason']:
        print(f"  Paused:        {session_results['pause_reason']}")

    report_path = generate_daily_report(dry_run, session_results, daily_target)

    if dry_run:
        print(f"\n[SAFE] DRY RUN — no emails were sent, no database changes.")
        print(f"       Run with --live for real sending.")
    else:
        print(f"\n[LIVE] Session complete. Check daily report for details.")


if __name__ == '__main__':
    main()
