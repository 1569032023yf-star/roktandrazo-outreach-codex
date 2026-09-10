#!/usr/bin/env python3
"""
BD Production Orchestrator v3.1 — Single Entry Point for All BD Automation.

Scheduler authority: Windows Task Scheduler only.
WorkBuddy Automations: DISABLED for production sends.

Usage:
  python bd_orchestrator.py --stage morning          # 08:30
  python bd_orchestrator.py --stage outreach         # 09:00
  python bd_orchestrator.py --stage post-send        # 00:10
  python bd_orchestrator.py --stage inventory        # 15:00
  python bd_orchestrator.py --stage end-of-day       # 17:30
  python bd_orchestrator.py --stage status           # any time
  python bd_orchestrator.py --stage outreach --dry-run

All stages are dry-run by default. Pass --live to actually send.
"""
from __future__ import annotations

import argparse
import os
import signal
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# SIGPIPE-safe: prevent BrokenPipeError from skipping finally blocks
if sys.platform != 'win32':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
else:
    # Windows: ignore broken pipe to ensure finally blocks execute
    try:
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)
    except Exception:
        pass

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
import env_loader  # P2.2A: ensure .env (MX Worker token) loaded before any V2 query_mx call

from bd_db import (
    get_db, get_config, set_config, set_state, get_state,
    get_today_sent_asia_shanghai, get_daily_target, get_daily_gap, get_batch_send_counts,
    get_sendable_leads, is_suppressed, add_to_suppression,
    update_lead_status, log_send,
    set_execution_mode, get_execution_mode,
    get_standing_authorization, set_standing_authorization,
    get_manual_pause, set_manual_pause,
    get_scheduler_enabled,
    get_risk_gate, set_risk_gate, clear_risk_gate, is_risk_gate_active, can_send_live,
    check_run_lock, acquire_run_lock, release_run_lock,
    get_scheduler_state,
    start_job_run, update_job_run, finish_job_run,
)

OUT_DIR = PROJECT_DIR / 'output'
OUT_DIR.mkdir(exist_ok=True)

# ── Constants ──────────────────────────────────────────────
from outreach_control import (
    FOLLOW_UP_ENABLED, FOLLOW_UP_MAX, INVENTORY_CRITICAL_THRESHOLD, INVENTORY_TARGET,
    INVENTORY_WARNING_THRESHOLD, NEW_OUTREACH_TARGET, outreach_batch_date,
    may_start_smtp_request, inventory_target_for_date,
)
SEND_WINDOW_START = 23.0
SEND_WINDOW_END = 24.0
BATCH_SIZE = 5

# 生产调度权威时区：Asia/Shanghai（UTC+8，无 DST）。
# 客户 IANA 时区只用于报告/分析，不用于主调度。
ASIA_SH = timezone(timedelta(hours=8))


def now_shanghai() -> datetime:
    """当前 Asia/Shanghai（UTC+8）时间，生产调度唯一时钟。"""
    return datetime.now(ASIA_SH)


def business_date_shanghai() -> str:
    """按 Asia/Shanghai 时区计算业务日期。"""
    return outreach_batch_date(now_shanghai())


def is_in_send_window() -> bool:
    return may_start_smtp_request(now_shanghai())


def stage_pre_send(run_id: str, business_date: str, dry_run: bool):
    """22:30 stage: freeze the only recipients the 23:00 SMTP session may consume."""
    header("STAGE: Pre-Send (22:30) — Final Send Plan")
    if not dry_run:
        update_job_run(run_id, current_step='freeze_final_send_plan', target=NEW_OUTREACH_TARGET)
    from bd_template import apply_email_to_lead
    from final_send_plan import create_plan
    from campaign_eligible import campaign_eligible_check, select_candidates_for_plan
    from campaign_eligible_v2 import (
        campaign_eligible_check_v2, select_candidates_for_plan_v2,
    )

    conn = get_db()
    eligible = []
    # 正式政策：Broad Ready → ICP Qualified → Campaign Eligible → Final Send Plan。
    # Strict A0 只是优先层，不是唯一发送池；Campaign Eligible 是主池判定。
    for row in select_candidates_for_plan_v2(conn, NEW_OUTREACH_TARGET):
        lead = apply_email_to_lead(dict(row))
        lead['hygiene_passed_at'] = now_shanghai().isoformat()
        eligible.append(lead)
    # P2.4A: 最小排序修复 —— 收件人当地窗口最早到期优先（ET→CT→MT→PT），
    # 使 planned_sequence / execute 顺序按 recipient local window deadline 升序，
    # 不再依赖 id 顺序。只排序，不改变入选的 lead 集合。
    _TZ_PRIORITY = {
        "America/New_York": 0, "America/Chicago": 1,
        "America/Denver": 2, "America/Los_Angeles": 3,
    }
    eligible.sort(key=lambda L: _TZ_PRIORITY.get(str(L.get("recipient_timezone") or ""), 9))
    # ── P2.3P: follow-up 已按生产策略停用 ──
    # CURRENT_SEND_POLICY["follow_up_enabled"] == False → 不得创建 follow_up FSP。
    # 原因：follow_up 行 template_id 为空且其邮箱必然已在 send_log 中，
    # preflight 的 check_template/check_hygiene/check_duplicates 扫描全部 plan_rows，
    # 4 条坏行会拖垮整批（含 19 条健康 new_outreach）→ PRE_AUTH FAIL → 整批零发送。
    # 代码与历史数据保留，仅生产不再产出。
    followups = []
    if not FOLLOW_UP_ENABLED:
        log(f"[POLICY] follow_up_enabled=false — skipping follow-up queue (no follow_up FSP will be created)")
    else:
        try:
            from workbuddy_candidate_modules.follow_up_queue_builder import build_followup_queue
            from bd_template import get_email_for_lead
            for item in build_followup_queue().get('queue', [])[:FOLLOW_UP_MAX]:
                row = conn.execute("SELECT * FROM leads WHERE id=?", (item['lead_id'],)).fetchone()
                if not row:
                    continue
                lead = dict(row)
                template = get_email_for_lead(lead)
                lead.update(email_subject=template['subject'], email_body=template['body_text'],
                            email_body_html=template.get('body_html', ''),
                            hygiene_passed_at=now_shanghai().isoformat())
                followups.append(lead)
        except Exception as exc:
            log(f"[WARN] Follow-up plan unavailable: {exc}")
    if dry_run:
        conn.close()
        preview = {
            'new_outreach': len(eligible),
            'follow_up': len(followups),
            'lead_ids': [lead['id'] for lead in eligible + followups],
        }
        log(f"[DRY RUN] Final Send Plan preview only: new={preview['new_outreach']}, follow-up={preview['follow_up']}")
        return preview
    with conn:
        plan_id = create_plan(conn, eligible, business_date, 'new_outreach',
                              eligible_check=campaign_eligible_check_v2(conn))
        # ── P2.3P: 策略关闭时不调用 create_plan(..., 'follow_up') ──
        # 注意：create_plan 对空 entries 会提前返回且不清理旧 planned 行，
        # 因此这里必须显式不调用，旧 follow_up 残留由 C 步按 status='cancelled' 退役。
        followup_plan_id = ""
        if FOLLOW_UP_ENABLED:
            followup_plan_id = create_plan(conn, followups, business_date, 'follow_up')
    conn.close()
    log(f"Final plans frozen: new={plan_id} ({len(eligible)}), "
        f"follow-up={followup_plan_id or 'DISABLED_BY_POLICY'} ({len(followups)})")
    finish_job_run(run_id, 'completed', actual=len(eligible), gap=max(0, NEW_OUTREACH_TARGET - len(eligible)))
    return True


def _stage_outreach_from_final_plan(run_id: str, business_date: str, dry_run: bool):
    """23:00 stage: consume an existing plan; no candidate selection or inventory recovery."""
    from daily_session import execute_final_send_plan
    conn = get_db()
    has_plan = conn.execute(
        "SELECT 1 FROM final_send_plan WHERE outreach_batch_date=? AND status='planned' LIMIT 1",
        (business_date,),
    ).fetchone()
    conn.close()
    if not has_plan:
        log('[BLOCKED] No Final Send Plan for this outreach batch')
        if not dry_run:
            finish_job_run(run_id, 'stopped', stop_reason='final_send_plan_missing')
        return False
    result = execute_final_send_plan(business_date, dry_run=dry_run)
    if dry_run:
        log(f"[DRY RUN] Final-plan preview: {len(result.get('preview', []))} entries")
        return result
    counts = get_batch_send_counts(business_date)
    new_sent = counts.get('new_outreach', 0)
    gap = max(0, NEW_OUTREACH_TARGET - new_sent)
    finish_job_run(run_id, 'completed' if gap == 0 else 'underfilled', actual=new_sent, gap=gap,
                   stop_reason='target_met' if gap == 0 else 'plan_exhausted_or_skipped')
    log(f"Final-plan outreach complete: new={new_sent}/{NEW_OUTREACH_TARGET}; follow_up={counts.get('follow_up', 0)}/{FOLLOW_UP_MAX}")
    return gap == 0


def header(text: str):
    print(f"\n{'='*60}\n  {text}\n{'='*60}")


def log(*args):
    ts = now_shanghai().strftime('%H:%M:%S')
    print(f"[{ts}]", *args)


# ═══════════════════════════════════════════════════════════
# Stage: morning (08:30)
# ═══════════════════════════════════════════════════════════
def stage_morning(run_id: str, business_date: str, dry_run: bool):
    header("STAGE: Morning (08:30) — Inbox + Risk Recovery + Follow-up Refresh")
    if dry_run:
        log('[DRY RUN] Morning preview only; risk gate and job state are unchanged')
        return {'preview': 'morning_read_only'}
    update_job_run(run_id, current_step='morning')

    # 1. Run inbox risk recovery
    log("Running inbox incremental scan...")
    from bd_db import get_risk_gate, clear_risk_gate
    gate = get_risk_gate()

    try:
        from agent_reply_monitor import scan_mailbox
        scans = scan_mailbox('INBOX', since_days=1, dry_run=dry_run)
        log(f"  Inbox scan: {len(scans)} messages found")
    except Exception as e:
        log(f"  [WARN] Inbox scan failed: {e}")
        scans = []

    # 2. Auto-clear expired risk gate
    if not is_risk_gate_active() and gate['status'] == 'temporary_block':
        log("[AUTO-RECOVERY] Risk gate cooldown expired — clearing")
        clear_risk_gate()
        set_config('send_pause', 'false')
        set_config('pause_reason', '')

    # 3. Refresh follow-up queue
    log("Refreshing follow-up queue...")
    try:
        from workbuddy_candidate_modules.follow_up_queue_builder import build_followup_queue
        fq = build_followup_queue()
        log(f"  Follow-up queue: {fq['final_sendable_count']} sendable, suggested daily: {fq['suggested_daily_count']}")
    except Exception as e:
        log(f"  [WARN] Follow-up queue refresh failed: {e}")
        fq = {'final_sendable_count': 0, 'queue': []}

    update_job_run(run_id, current_step='morning_done', status='completed')
    return True


# ═══════════════════════════════════════════════════════════
# Stage: outreach (09:00) — the main send loop
# ═══════════════════════════════════════════════════════════
def stage_outreach(run_id: str, business_date: str, dry_run: bool):
    header("STAGE: Outreach (23:00) - Final Plan Only")

    if dry_run:
        return _stage_outreach_from_final_plan(run_id, business_date, dry_run=True)

    if get_manual_pause():
        log("[BLOCKED] manual_pause=true - cannot send")
        finish_job_run(run_id, 'stopped', stop_reason='manual_pause')
        return False

    if not get_standing_authorization():
        log("[BLOCKED] standing_authorization=false")
        finish_job_run(run_id, 'stopped', stop_reason='no_authorization')
        return False

    if not is_in_send_window():
        log("[SKIP] Outside send window (23:00-23:59:30 Asia/Shanghai)")
        finish_job_run(run_id, 'stopped', stop_reason='outside_send_window')
        return False

    today = business_date
    if not acquire_run_lock(f'outreach:{today}', run_id):
        log(f"[LOCKED] outreach:{today} already running")
        finish_job_run(run_id, 'stopped', stop_reason='lock_conflict')
        return False

    set_execution_mode('daily_outreach')
    update_job_run(run_id, current_step='outreach_start', target=NEW_OUTREACH_TARGET)
    try:
        return _stage_outreach_from_final_plan(run_id, business_date, dry_run)
    finally:
        release_run_lock(f'outreach:{today}', run_id)


def stage_post_send(run_id: str, business_date: str, dry_run: bool):
    header("STAGE: Post-Send (00:10) — Inbox + Dashboard Update")
    if dry_run:
        log('[DRY RUN] Post-send preview only; dashboard and status files are unchanged')
        return {'preview': 'post_send_read_only'}
    update_job_run(run_id, current_step='post_send')

    # 1. Incremental inbox scan
    log("Incremental inbox scan...")
    try:
        from agent_reply_monitor import scan_mailbox
        results = scan_mailbox('INBOX', since_days=0, dry_run=dry_run)
        log(f"  Messages: {len(results)}")
        for r in results[:5]:
            log(f"    [{r['type']}] {r.get('subject', '')[:60]}")
    except Exception as e:
        log(f"  [WARN] Inbox scan error: {e}")

    # 2. Reconcile send results
    today_sent = get_today_sent_asia_shanghai()
    gap = get_daily_gap()
    log(f"  Today: {today_sent}/{NEW_OUTREACH_TARGET} (gap: {gap})")

    # 3. Update dashboard
    log("Generating dashboard...")
    try:
        from bd_operations_dashboard import main as generate_operations_dashboard
        generate_operations_dashboard()
        log("  Dashboard: bd_operations_dashboard.html")
    except Exception as e:
        log(f"  [WARN] Dashboard error: {e}")

    finish_job_run(run_id, 'completed', actual=today_sent, gap=gap)
    return True


# ═══════════════════════════════════════════════════════════
# Stage: inventory (15:00) — target Broad Ready >= 30 (main pool)
# ═══════════════════════════════════════════════════════════

def _count_broad_ready_pool(limit: int = 1000) -> int:
    """生产主池口径：Broad Outreach Ready（非 Strict A0）。
    Strict A0 只是优先层；inventory 的 final_pool 必须用主池。
    只读，不写库。
    """
    try:
        from broad_ready import is_broad_outreach_ready
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            c = conn.cursor()
            c.execute("""
                SELECT * FROM leads
                WHERE status NOT IN ('sent','bounced','do_not_contact','rejected',
                                   'failed','delivery_issue','bounce_review','contact_form_pool')
                AND email IS NOT NULL AND email != '' AND email LIKE '%@%.%'
                LIMIT ?
            """, (limit,))
            rows = [dict(r) for r in c.fetchall()]
            ready = 0
            for ld in rows:
                if is_broad_outreach_ready(ld, {'conn': conn}).get('ready'):
                    ready += 1
            return ready
        finally:
            conn.close()
    except Exception as e:
        log(f"  [WARN] _count_broad_ready_pool error: {e}")
        return 0


# P1.7C final wiring: canonical Discovery must run one Active State at a time.
# Valid 2-letter US state codes (50 states; DC excluded unless added explicitly).
US_STATE_CODES = frozenset({
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY",
})


def _resolve_active_discovery_state() -> tuple[str | None, str | None]:
    """Read active_discovery_state from system_config and validate.

    Returns (state, error_code); error_code in
    (None, 'ACTIVE_STATE_NOT_SET', 'ACTIVE_STATE_INVALID').
    Fail-closed: canonical Discovery never falls back to state=None (nationwide queue).
    """
    from bd_db import get_config
    raw = (get_config('active_discovery_state') or '').strip().upper()
    if not raw:
        return None, 'ACTIVE_STATE_NOT_SET'
    if len(raw) != 2 or not raw.isalpha() or raw not in US_STATE_CODES:
        return None, 'ACTIVE_STATE_INVALID'
    return raw, None


def _count_safe_ready_pool(conn):
    """Read-only frozen V2 selection; never materialize a plan or authorization."""
    from campaign_eligible_v2 import select_candidates_for_plan_v2
    count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    rows = select_candidates_for_plan_v2(conn, max(1, count))
    return len({str(r.get('organization_key') or '').strip() for r in rows
                if str(r.get('organization_key') or '').strip()})


def stage_inventory(run_id: str, business_date: str, dry_run: bool):
    target = inventory_target_for_date(business_date)
    header(f"STAGE: Inventory — Target {target}, send_enabled=false")
    if dry_run:
        conn = get_db()
        try:
            a0 = len(get_sendable_leads(limit=target + 1, conn=conn))
            broad = _count_broad_ready_pool()
            safe = _count_safe_ready_pool(conn)
        finally:
            conn.close()
        return {'strict_a0': a0, 'broad_ready': broad, 'safe_ready_unique_orgs': safe,
                'target': target, 'gap': max(0, target - safe)}
    set_execution_mode('inventory_recovery')
    update_job_run(run_id, current_step='inventory_start', target=target)
    if not acquire_run_lock(f'inventory:{business_date}', run_id):
        finish_job_run(run_id, 'stopped', stop_reason='lock_conflict')
        return False
    try:
        from retail_city_queue import activate_next_city, seed_default_queue
        from discovery.discovery_service import DiscoveryService
        from discovery.website_resolver import ProviderWebsiteResolver
        active_state, state_error = _resolve_active_discovery_state()
        if state_error:
            finish_job_run(run_id, 'stopped', stop_reason=state_error)
            return False
        conn = get_db()
        try:
            with conn:
                seed_default_queue(conn)
                city = activate_next_city(conn, state=active_state)
            log(f"Active city: {city['city']}, {city['state']}; existing linked backlog only")
            service = DiscoveryService(conn)
            # Reuse both canonical lane limits; no new discovery or unlinked processing
            # during this intentionally narrow linked-backlog release.
            limit = min(20, max(0, int(os.getenv('WORKBUDDY_WEBSITE_RESOLUTION_MAX', '20'))),
                        max(0, int(os.getenv('WORKBUDDY_STAGING_POSTPROCESS_MAX', '20'))))
            with conn:
                summary = service.run_linked_backlog(city, ProviderWebsiteResolver(service.provider), max_results=limit)
            log(f"Linked backlog: {summary}")
            safe = _count_safe_ready_pool(conn)
            broad = _count_broad_ready_pool()
            gap = max(0, target - safe)
            finish_job_run(run_id, 'completed' if gap == 0 else 'partial', actual=safe, gap=gap,
                           stop_reason='' if gap == 0 else 'linked_backlog_budget_exhausted')
            log(f"SAFE_READY_UNIQUE_ORGS={safe}/{target}; BroadReady={broad} (informational only)")
            return gap == 0
        finally:
            conn.close()
    except Exception as exc:
        finish_job_run(run_id, 'stopped', stop_reason=f'linked_backlog_error:{type(exc).__name__}')
        raise
    finally:
        release_run_lock(f'inventory:{business_date}', run_id)

# ═══════════════════════════════════════════════════════════
# Stage: end-of-day (17:30) — Dashboard + Daily Summary
# ═══════════════════════════════════════════════════════════
def stage_end_of_day(run_id: str, business_date: str, dry_run: bool):
    header("STAGE: End-of-Day (17:30) — Dashboard + Daily Summary")
    if dry_run:
        log('[DRY RUN] End-of-day preview only; production reports are unchanged')
        return {'preview': 'end_of_day_read_only'}
    update_job_run(run_id, current_step='eod_start')

    # 1. Final inbox scan
    log("Final inbox scan...")
    try:
        from agent_reply_monitor import scan_mailbox
        scans = scan_mailbox('INBOX', since_days=1, dry_run=dry_run)
        hard_bounces = len([s for s in scans if s['type'] == 'hard_bounce'])
        replies = len([s for s in scans if s['type'] in ('reply', 'hot_reply', 'warm_reply')])
        unsubs = len([s for s in scans if s['type'] == 'unsubscribe'])
        log(f"  Hard bounces: {hard_bounces}, Replies: {replies}, Unsubs: {unsubs}")
    except Exception as e:
        log(f"  [WARN] Inbox scan error: {e}")
        hard_bounces, replies, unsubs = 0, 0, 0

    # 2. Collect stats
    today_sent = get_today_sent_asia_shanghai()
    conn = get_db()
    c = conn.cursor()
    a0_count = len(get_sendable_leads(limit=INVENTORY_TARGET + 1, conn=conn))
    total_leads = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_sent_all = c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent'").fetchone()[0]
    conn.close()

    # 3. Generate dashboard
    log("Generating dashboard...")
    try:
        from dashboard import generate_dashboard
        dash_path = generate_dashboard(str(OUT_DIR / 'bd_operations_dashboard.html'))
        log(f"  Dashboard: {dash_path}")
    except Exception as e:
        log(f"  [WARN] Dashboard error: {e}")
        dash_path = ''

    # 4. Generate daily summary report JSON
    import json
    summary = {
        'date': business_date,
        'new_outreach_sent': today_sent,
        'new_outreach_target': NEW_OUTREACH_TARGET,
        'new_outreach_gap': max(0, NEW_OUTREACH_TARGET - today_sent),
        'followup_sent': 0,  # populated by outreach stage
        'hard_bounces': hard_bounces,
        'replies': replies,
        'unsubscribes': unsubs,
        'a0_sendable': a0_count,
        'inventory_target': inventory_target_for_date(business_date),
        'inventory_gap': max(0, inventory_target_for_date(business_date) - a0_count),
        'total_leads': total_leads,
        'total_sent_all': total_sent_all,
        'risk_gate': get_risk_gate()['status'],
        'generated_at': now_shanghai().isoformat(),
    }
    json_path = OUT_DIR / 'latest_operations_report.json'
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    log(f"  JSON report: {json_path}")

    # Also write end_of_day_status.json for downstream consumers
    eod_path = OUT_DIR / 'end_of_day_status.json'
    with open(eod_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    log(f"  EOD status: {eod_path}")

    # 5. Daily summary delivery is not routed through the outreach SMTP sender.
    report_to = get_config('BD_REPORT_TO') or ''
    if report_to:
        log(f"  Report recipient configured: {report_to}")
        log("  [INFO] Summary email delivery requires a controlled report channel; outreach SMTP is not used.")
    else:
        log("  [INFO] BD_REPORT_TO not configured - skipping summary email")

    finish_job_run(run_id, 'completed', actual=today_sent)
    return True


# ═══════════════════════════════════════════════════════════
# Stage: status — read-only query
# ═══════════════════════════════════════════════════════════
def stage_status():
    """Read-only status. No model call, no collection, no send."""
    header("STAGE: Status (read-only)")

    today_sent = get_today_sent_asia_shanghai()
    gap = get_daily_gap()
    target = get_daily_target()

    conn = get_db()
    c = conn.cursor()
    a0 = len(get_sendable_leads(limit=INVENTORY_TARGET + 1, conn=conn))
    total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_sent = c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent'").fetchone()[0]
    today_bounce = c.execute("SELECT COUNT(*) FROM bounce_log WHERE date(bounce_received_at)=?",
                             (business_date_shanghai(),)).fetchone()[0]
    conn.close()

    gate = get_risk_gate()

    print(f"  Today:          {today_sent}/{target} (gap: {gap})")
    print(f"  Today bounces:  {today_bounce}")
    print(f"  A0 sendable:    {a0}")
    print(f"  Total inventory: {total} ({total_sent} sent)")
    print(f"  Risk gate:      {gate['status']} ({gate['reason'] or 'N/A'})")
    print(f"  Manual pause:   {get_manual_pause()}")
    print(f"  Standing auth:  {get_standing_authorization()}")
    print(f"  Scheduler:      {'ENABLED' if get_scheduler_enabled() else 'DISABLED'}")

    return True


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description='BD Production Orchestrator v3.1')
    parser.add_argument('--stage', required=True,
                        choices=['morning', 'pre-send', 'outreach', 'post-send', 'inventory', 'end-of-day', 'status'])
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run (default)')
    parser.add_argument('--live', action='store_true', help='Actually send emails')
    args = parser.parse_args()

    dry_run = not args.live
    business_date = business_date_shanghai()
    run_id = f"{args.stage}:{business_date}:{uuid.uuid4().hex[:8]}"

    log(f"BD Orchestrator v3.1 | stage={args.stage} | dry_run={dry_run}")
    log(f"Business date: {business_date} | run_id: {run_id}")

    # Start job run record
    target_map = {
        'morning': 0, 'pre-send': NEW_OUTREACH_TARGET, 'outreach': NEW_OUTREACH_TARGET,
        'post-send': 0, 'inventory': inventory_target_for_date(business_date), 'end-of-day': 0, 'status': 0,
    }
    job_run_started = args.stage != 'status' and not dry_run
    if job_run_started:
        if not start_job_run(run_id, args.stage, business_date, target=target_map.get(args.stage, 0), dry_run=dry_run):
            log(f"[DUPLICATE] Active {args.stage} job already exists for {business_date}; exiting without stage execution")
            return False

    try:
        if args.stage == 'morning':
            stage_morning(run_id, business_date, dry_run)
        elif args.stage == 'pre-send':
            stage_pre_send(run_id, business_date, dry_run)
        elif args.stage == 'outreach':
            stage_outreach(run_id, business_date, dry_run)
        elif args.stage == 'post-send':
            stage_post_send(run_id, business_date, dry_run)
        elif args.stage == 'inventory':
            stage_inventory(run_id, business_date, dry_run)
        elif args.stage == 'end-of-day':
            stage_end_of_day(run_id, business_date, dry_run)
        elif args.stage == 'status':
            stage_status()
    except Exception as e:
        import traceback
        error_msg = f"{e}\n{traceback.format_exc()}"
        log(f"[FATAL] {error_msg}")
        if job_run_started:
            finish_job_run(run_id, 'failed', error=error_msg[:500])
        print(error_msg)
        sys.exit(1)


if __name__ == '__main__':
    main()
