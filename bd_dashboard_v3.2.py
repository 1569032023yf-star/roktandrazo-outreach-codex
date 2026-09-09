#!/usr/bin/env python3
"""
BD Operations Dashboard v3.2 — Manual Review + Inventory + Follow-up
Generates output/bd_operations_dashboard.html with all tabs.
Also generates output/manual_review_queue.json and output/followup_rotation_status.json.

v3.2 增强：新增 Delivery Outcome / Data Freshness / Plan-Auth-SMTP-send_log 对账三个区块。
  - SMTP Accepted 与 Delivery Outcome 分开统计：bounced 邮件不会从 SMTP Accepted 中扣除。
  - Data Freshness 徽章：<90min GREEN，90min-24h YELLOW，>24h 或缺失 RED + 'DATA STALE'。
  - 对账读取 output/post_send_reconciliation_*.json 与 system_config.post_send_reconciliation_*。
"""
import json, sqlite3, sys, os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from recipient_scheduler import schedule_plan_entry

DB_PATH = PROJECT_DIR / 'data' / 'bd_leads.db'
OUT_DIR = PROJECT_DIR / 'output'
OUT_DIR.mkdir(exist_ok=True)

POLLER_STATUS_FILE = OUT_DIR / 'bd_ops_poller_status.json'

CST = timezone(timedelta(hours=8))

PRIMARY_STATES = {'TN', 'AR', 'KY'}


def now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


def today_cst():
    return now_cst().strftime('%Y-%m-%d')


def db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def collect_all_data():
    conn = db()
    c = conn.cursor()
    today = today_cst()

    # === Manual Review Breakdown ===
    manual = {
        'manual_review_needed': c.execute(
            "SELECT COUNT(*) FROM leads WHERE status='manual_review_needed'").fetchone()[0],
        'b_pool_new': c.execute(
            "SELECT COUNT(*) FROM leads WHERE confidence_score='B' AND status='new'").fetchone()[0],
        'bounce_review': c.execute(
            "SELECT COUNT(*) FROM leads WHERE status='bounce_review'").fetchone()[0],
        'contact_form_pool': c.execute(
            "SELECT COUNT(*) FROM leads WHERE status='contact_form_pool'").fetchone()[0],
        'delivery_issue': c.execute(
            "SELECT COUNT(*) FROM leads WHERE status='delivery_issue'").fetchone()[0],
        'approved_manual_send': c.execute(
            "SELECT COUNT(*) FROM leads WHERE status='approved_manual_send'").fetchone()[0],
        'approved_count': c.execute(
            "SELECT COUNT(*) FROM leads WHERE manual_decision='approved_manual_send'").fetchone()[0],
        'rejected_count': c.execute(
            "SELECT COUNT(*) FROM leads WHERE manual_decision='rejected'").fetchone()[0],
        'deferred_count': c.execute(
            "SELECT COUNT(*) FROM leads WHERE manual_decision='deferred'").fetchone()[0],
        'total_pending': c.execute(
            "SELECT COUNT(*) FROM leads WHERE status IN ('manual_review_needed','bounce_review','contact_form_pool')").fetchone()[0],
        'oldest_wait': c.execute(
            "SELECT collected_at FROM leads WHERE status='manual_review_needed' ORDER BY collected_at ASC LIMIT 1").fetchone(),
    }
    manual['oldest_wait_days'] = 0
    if manual['oldest_wait'] and manual['oldest_wait'][0]:
        try:
            dt = datetime.fromisoformat(manual['oldest_wait'][0].replace('Z', '+00:00'))
            manual['oldest_wait_days'] = (datetime.utcnow().replace(tzinfo=dt.tzinfo) - dt).days
        except Exception:
            manual['oldest_wait_days'] = '?'
    manual.pop('oldest_wait', None)

    # === Sample review queue (export JSON) ===
    review_sample = c.execute("""
        SELECT id, store_name, city, state, official_website, email, email_source_type,
               evidence_url, confidence_score, status, collected_at, manual_decision,
               store_type, contact_form_url, source_keyword
        FROM leads WHERE status IN ('manual_review_needed','bounce_review','contact_form_pool')
        ORDER BY collected_at ASC LIMIT 200
    """).fetchall()
    review_queue = [dict(r) for r in review_sample]
    for rq in review_queue:
        for k in list(rq.keys()):
            if isinstance(rq[k], datetime):
                rq[k] = rq[k].isoformat()

    # === Inventory Truth ===
    # A0 auto-sendable (strict rules)
    a0_retail = c.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page','manual_lookup')
        AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
        AND id NOT IN (SELECT lead_id FROM bounce_log)
        AND (mx_provider IS NULL OR mx_provider = '' OR
             (mx_provider NOT LIKE '%exchange%' AND mx_provider NOT LIKE '%outlook%'))
        AND state IN ('TN','AR','KY')
    """).fetchone()[0]

    # Custom (non-retail, any state)
    a0_custom = c.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page','manual_lookup')
        AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
        AND id NOT IN (SELECT lead_id FROM bounce_log)
        AND (mx_provider IS NULL OR mx_provider = '' OR
             (mx_provider NOT LIKE '%exchange%' AND mx_provider NOT LIKE '%outlook%'))
        AND (store_type LIKE '%custom%' OR store_type LIKE '%brand%' OR store_type LIKE '%publisher%'
             OR store_type LIKE '%manufacturer%' OR store_type LIKE '%online%')
    """).fetchone()[0]

    # Overlap (retail + custom same lead)
    overlap = c.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page','manual_lookup')
        AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
        AND id NOT IN (SELECT lead_id FROM bounce_log)
        AND (mx_provider IS NULL OR mx_provider = '' OR
             (mx_provider NOT LIKE '%exchange%' AND mx_provider NOT LIKE '%outlook%'))
        AND state IN ('TN','AR','KY')
        AND (store_type LIKE '%custom%' OR store_type LIKE '%brand%' OR store_type LIKE '%publisher%')
    """).fetchone()[0]

    # Other-state retail (BLOCKED from auto-send)
    other_retail = c.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
        AND state NOT IN ('TN','AR','KY')
        AND (store_type NOT LIKE '%custom%' AND store_type NOT LIKE '%brand%' AND store_type NOT LIKE '%publisher%')
    """).fetchone()[0]

    # Other-state custom
    other_custom = c.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
        AND state NOT IN ('TN','AR','KY')
        AND (store_type LIKE '%custom%' OR store_type LIKE '%brand%' OR store_type LIKE '%publisher%')
    """).fetchone()[0]

    unique_auto = a0_retail + a0_custom - overlap

    # Today's changes
    today_sent = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE date(sent_at)=? AND status='sent'", (today,)
    ).fetchone()[0]
    today_demoted = c.execute(
        "SELECT COUNT(*) FROM leads WHERE date(last_checked_at)=? AND confidence_score IN ('B','C')", (today,)
    ).fetchone()[0]
    today_new_a0 = c.execute(
        "SELECT COUNT(*) FROM leads WHERE date(collected_at)=? AND confidence_score='A'", (today,)
    ).fetchone()[0]

    # Total leads
    total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    total_sent_all = c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent'").fetchone()[0]

    # State breakdown
    state_breakdown = {}
    for row in c.execute("SELECT state, COUNT(*) FROM leads WHERE state IS NOT NULL AND state!='' GROUP BY state"):
        state_breakdown[row[0]] = row[1]

    # === 新增：Delivery Outcome / Data Freshness / 对账（在 conn 关闭前计算） ===
    delivery_outcome = compute_delivery_outcome(conn)
    freshness = compute_data_freshness(conn, POLLER_STATUS_FILE)
    reconciliation = collect_reconciliation(conn, OUT_DIR)

    # === 新增：P0 时区增强（在 conn 关闭前计算） ===
    timezone_stats = compute_timezone_stats(conn)
    schedule_preview = compute_schedule_preview(conn)
    send_results_tz = compute_send_results_tz(conn)

    conn.close()

    # === Follow-up Status ===
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from workbuddy_candidate_modules.follow_up_queue_builder import build_followup_queue
        fq = build_followup_queue()
    except Exception as e:
        fq = {'final_sendable_count': 0, 'suggested_daily_count': 0, 'queue': [], 'exclusion_counts': {},
              'dedup_counts': {}, 'error': str(e)}

    # Check if follow-up was ever wired and executed
    fu_wired = 'build_followup_queue' in open(str(PROJECT_DIR / 'bd_orchestrator.py'), encoding='utf-8').read()
    fu_ever_sent = db_conn_check('SELECT COUNT(*) FROM leads WHERE followup_count > 0')
    fu_status = 'not_wired' if not fu_wired else ('never_executed' if fu_ever_sent == 0 else 'partial')

    followup_data = {
        'status': fu_status,
        'is_wired': fu_wired,
        'ever_sent_live': fu_ever_sent > 0,
        'raw_candidates': fq.get('exclusion_counts', {}).get('total_sent_log_entries', 0),
        'hygiene_passed': fq.get('final_sendable_count', 0),
        'final_sendable': fq.get('final_sendable_count', 0),
        'suggested_daily': fq.get('suggested_daily_count', 5),
        'daily_limit': 5,
        'today_planned': 0,
        'today_sent': 0,
        'last_run': 'never',
        'next_planned': 'tomorrow 09:00',
        'oldest_waiting_days': fq.get('exclusion_counts', {}).get('not_14d_yet', '?'),
        'excluded_replied': fq.get('exclusion_counts', {}).get('already_replied', 0),
        'excluded_bounced': fq.get('exclusion_counts', {}).get('hard_bounced', 0),
        'excluded_unsubscribed': fq.get('exclusion_counts', {}).get('unsubscribed', 0),
        'excluded_suppressed': fq.get('exclusion_counts', {}).get('suppressed', 0),
        'excluded_already_followed': fq.get('exclusion_counts', {}).get('already_followed_up', 0),
        'excluded_domain_mismatch': fq.get('exclusion_counts', {}).get('domain_mismatch', 0),
    }

    inventory_data = {
        'retail_auto_sendable': a0_retail,
        'custom_auto_sendable': a0_custom,
        'overlap': overlap,
        'other_state_custom': other_custom,
        'other_state_retail_blocked': other_retail,
        'manual_review_count': manual['total_pending'],
        'custom_c_pool': manual['contact_form_pool'],
        'unique_auto_sendable': unique_auto,
        'today_sent': today_sent,
        'today_demoted': today_demoted,
        'today_new_a0': today_new_a0,
        'total_leads': total,
        'total_sent_all': total_sent_all,
        'state_breakdown': state_breakdown,
        'reconciled': True,  # We CAN reconcile with today's data
    }

    return {
        'manual': manual,
        'inventory': inventory_data,
        'followup': followup_data,
        'review_queue': review_queue,
        'delivery': delivery_outcome,
        'freshness': freshness,
        'reconciliation': reconciliation,
        'timezone_stats': timezone_stats,
        'schedule_preview': schedule_preview,
        'send_results_tz': send_results_tz,
    }


def db_conn_check(sql):
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    result = c.execute(sql).fetchone()[0]
    conn.close()
    return result


# ==========================================================================
# Delivery Outcome / Data Freshness / 对账 —— 计算函数（独立于 HTML，可单测）
# ==========================================================================

def _parse_ts(s):
    """把多种格式的时间字符串解析为带时区的 datetime（naive 按 CST 处理）。"""
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt.astimezone(CST)


def compute_delivery_outcome(conn):
    """计算 SMTP Accepted 与 Delivery Outcome 分类计数。

    SMTP Accepted 只统计 send_log.status='sent'，不因 bounce_log 而减少；
    Delivery Outcome 从 bounce_log（按 bounce_type 分类）+ unmatched_dsn + reply_log 统计。
    """
    c = conn.cursor()
    now = now_cst()
    cut_30d = (now - timedelta(days=30)).strftime('%Y-%m-%d')

    # SMTP Accepted：最近30天 / 全部两个口径
    smtp_accepted_all = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE status='sent'").fetchone()[0]
    smtp_accepted_30d = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE status='sent' AND substr(sent_at,1,10) >= ?",
        (cut_30d,)).fetchone()[0]

    # bounce_log 按 bounce_type 分类（兼容历史值：domain / policy / soft）
    raw = {}
    for r in c.execute("SELECT bounce_type, COUNT(*) FROM bounce_log GROUP BY bounce_type"):
        raw[r[0]] = r[1]
    domain_invalid = raw.get('domain_invalid', 0) + raw.get('domain', 0)
    mailbox_invalid = raw.get('mailbox_invalid', 0) + raw.get('mailbox', 0)
    policy_bounce = raw.get('policy_bounce', 0) + raw.get('policy', 0)
    soft_bounce = raw.get('soft_bounce', 0) + raw.get('soft', 0)
    hard_bounce = raw.get('hard', 0)
    other_bounce = sum(v for k, v in raw.items()
                       if k not in ('domain_invalid', 'domain', 'mailbox_invalid', 'mailbox',
                                    'policy_bounce', 'policy', 'soft_bounce', 'soft', 'hard'))

    # Unmatched DSN：优先 unmatched_dsn 表行数，空表时回退 last_imap_scan_result
    unmatched_dsn = c.execute("SELECT COUNT(*) FROM unmatched_dsn").fetchone()[0]
    if unmatched_dsn == 0:
        try:
            row = c.execute(
                "SELECT value FROM system_config WHERE key='last_imap_scan_result'").fetchone()
            if row and row[0]:
                scan = json.loads(row[0])
                unmatched_dsn = int(scan.get('unmatched_dsn') or 0)
        except Exception:
            pass

    # reply_log：reply_type 含 auto/ooo/notification 视为自动回复
    reply_total = c.execute("SELECT COUNT(*) FROM reply_log").fetchone()[0]
    auto_reply = c.execute(
        "SELECT COUNT(*) FROM reply_log WHERE reply_type LIKE '%auto%' "
        "OR reply_type LIKE '%ooo%' OR reply_type LIKE '%autoreply%' "
        "OR reply_type LIKE '%notification%'").fetchone()[0]
    human_reply = reply_total - auto_reply

    classified_total = (domain_invalid + mailbox_invalid + policy_bounce + soft_bounce
                        + hard_bounce + other_bounce + unmatched_dsn
                        + human_reply + auto_reply)
    outcome_unresolved = max(0, smtp_accepted_all - classified_total)

    hard_failures = domain_invalid + mailbox_invalid + hard_bounce
    return {
        'smtp_accepted_all': smtp_accepted_all,
        'smtp_accepted_30d': smtp_accepted_30d,
        'domain_invalid': domain_invalid,
        'mailbox_invalid': mailbox_invalid,
        'policy_bounce': policy_bounce,
        'soft_bounce': soft_bounce,
        'hard_bounce': hard_bounce,
        'other_bounce': other_bounce,
        'unmatched_dsn': unmatched_dsn,
        'human_reply': human_reply,
        'auto_reply': auto_reply,
        'classified_total': classified_total,
        'outcome_unresolved': outcome_unresolved,
        'hard_delivery_rate': round(
            (smtp_accepted_all - hard_failures) / max(1, smtp_accepted_all) * 100, 1),
    }


def freshness_level(scan_ts, now=None):
    """返回 (level, label)。<90min GREEN，90min-24h YELLOW，>24h 或缺失 RED + 'DATA STALE'。"""
    now = now or now_cst()
    dt = _parse_ts(scan_ts)
    if dt is None:
        return ('red', 'DATA STALE')
    age_min = (now - dt).total_seconds() / 60.0
    if age_min < 90:
        return ('green', 'FRESH')
    if age_min <= 24 * 60:
        return ('yellow', 'AGING')
    return ('red', 'DATA STALE')


def compute_data_freshness(conn, poller_file=None):
    """计算数据新鲜度：Last Bounce Scan / Last Reply Scan / 同步时间 / 状态徽章。"""
    c = conn.cursor()

    def cfg(key):
        r = c.execute("SELECT value FROM system_config WHERE key=?", (key,)).fetchone()
        return r[0] if r else None

    last_bounce_scan_at = cfg('last_bounce_scan_at')
    if not last_bounce_scan_at and poller_file and os.path.exists(str(poller_file)):
        try:
            with open(poller_file, 'r', encoding='utf-8') as f:
                p = json.load(f)
            last_bounce_scan_at = (
                p.get('jobs', {}).get('bounce', {}).get('last_success_at')
                or p.get('last_heartbeat'))
        except Exception:
            pass

    # Reply Scan：优先专用 key，缺失时回退到 IMAP 扫描时间（bounce/reply 同一次扫描）
    last_reply_scan_at = (cfg('last_reply_scan_at') or cfg('last_imap_scan_at')
                          or last_bounce_scan_at)
    sync_success_at = cfg('sync_0845_last_success_at')  # 由其他 Agent 创建，可能缺失

    level, label = freshness_level(last_bounce_scan_at)
    age_minutes = None
    if last_bounce_scan_at:
        dt = _parse_ts(last_bounce_scan_at)
        if dt:
            age_minutes = int((now_cst() - dt).total_seconds() // 60)

    return {
        'last_bounce_scan_at': last_bounce_scan_at,
        'last_reply_scan_at': last_reply_scan_at,
        'sync_0845_last_success_at': sync_success_at,
        'level': level,
        'badge_label': label,
        'age_minutes': age_minutes,
    }


# ==========================================================================
# P0 时区增强 —— 时区统计 / 发送预览 / 发送结果（独立于 HTML，可单测）
# ==========================================================================

EASTERN_KEYWORDS = ('eastern', 'new_york', 'us/eastern')
CENTRAL_KEYWORDS = ('central', 'chicago', 'us/central')
MOUNTAIN_KEYWORDS = ('mountain', 'denver', 'us/mountain', 'phoenix')
PACIFIC_KEYWORDS = ('pacific', 'los_angeles', 'us/pacific')

# 生产政策：收件人当地 10:00 发送，Mon-Fri
LOCAL_SEND_HOUR = 10


def _tz_region(tz_name):
    """把 IANA 时区归类为 Eastern/Central/Mountain/Pacific/Other（宽松关键字匹配）。"""
    if not tz_name:
        return 'Other'
    n = str(tz_name).lower()
    if any(k in n for k in EASTERN_KEYWORDS):
        return 'Eastern'
    if any(k in n for k in CENTRAL_KEYWORDS):
        return 'Central'
    if any(k in n for k in MOUNTAIN_KEYWORDS):
        return 'Mountain'
    if any(k in n for k in PACIFIC_KEYWORDS):
        return 'Pacific'
    return 'Other'


def _parse_scheduled_local(s):
    """解析 scheduled_local_time（如 2026-08-07T10:00:00-04:00[America/New_York]）→ aware datetime。

    兼容无 [IANA] 后缀、无偏移、'Z' 结尾等多种格式；解析失败返回 None。
    """
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    tz_name = None
    body = s
    if '[' in s and s.endswith(']'):
        idx = s.rfind('[')
        body, tz_name = s[:idx], s[idx + 1:-1]
    try:
        dt = datetime.fromisoformat(body)
    except ValueError:
        try:
            dt = datetime.fromisoformat(body.replace('Z', '+00:00'))
        except ValueError:
            return None
    if dt.tzinfo is None:
        if tz_name:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(tz_name))
            except Exception:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _scheduled_to_china(s):
    """把 scheduled_local_time（收件人当地时间）转成 Asia/Shanghai（北京/中国时间）字符串。"""
    dt = _parse_scheduled_local(s)
    if dt is None:
        return None
    return dt.astimezone(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def _deviation_seconds(actual_local, scheduled_local):
    """actual_sent_at_local 与 scheduled_local_time 的秒差；无法解析返回 None。"""
    a = _parse_scheduled_local(actual_local)
    s = _parse_scheduled_local(scheduled_local)
    if a is None or s is None:
        return None
    return int((a - s).total_seconds())


def compute_timezone_stats(conn):
    """时区统计卡：RESOLVED / TIMEZONE_UNRESOLVED / 自动调度可发送 / 按时区分布。"""
    c = conn.cursor()
    total = c.execute('SELECT COUNT(*) FROM leads').fetchone()[0]
    resolved = c.execute(
        "SELECT COUNT(*) FROM leads WHERE recipient_timezone IS NOT NULL AND recipient_timezone != ''"
    ).fetchone()[0]
    unresolved = c.execute(
        "SELECT COUNT(*) FROM leads WHERE recipient_timezone IS NULL OR recipient_timezone = '' "
        "OR timezone_status='TIMEZONE_UNRESOLVED'"
    ).fetchone()[0]
    sendable_auto = c.execute(
        'SELECT COUNT(*) FROM leads WHERE sendable_for_automatic_schedule=1'
    ).fetchone()[0]
    distribution = {'Eastern': 0, 'Central': 0, 'Mountain': 0, 'Pacific': 0, 'Other': 0}
    for r in c.execute(
        "SELECT recipient_timezone FROM leads WHERE recipient_timezone IS NOT NULL AND recipient_timezone != ''"
    ):
        distribution[_tz_region(r[0])] += 1
    return {
        'total': total,
        'resolved': resolved,
        'unresolved': unresolved,
        'sendable_for_automatic_schedule': sendable_auto,
        'distribution': distribution,
    }


def compute_schedule_preview(conn, limit=200, now_utc=None):
    """发送预览：final_send_plan 的 planned 行（无 planned 时取最近批次 planned/sent）。

    用 recipient_scheduler.schedule_plan_entry 计算收件人当地 10:00 的
    scheduled_local_time / scheduled_utc_time，并额外转出 China 时间。
    recipient_timezone 为空的行标记 timezone_unresolved=True（NOT SCHEDULABLE）。
    """
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM final_send_plan WHERE status='planned' "
        "ORDER BY planned_sequence LIMIT ?",
        (limit,),
    ).fetchall()
    if not rows:
        batch = c.execute(
            "SELECT outreach_batch_date FROM final_send_plan "
            "WHERE status IN ('planned','sent') ORDER BY created_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if batch and batch[0]:
            rows = c.execute(
                "SELECT * FROM final_send_plan WHERE outreach_batch_date=? "
                "AND status IN ('planned','sent') ORDER BY planned_sequence LIMIT ?",
                (batch[0], limit),
            ).fetchall()
    lead_ids = list({r['lead_id'] for r in rows if r['lead_id']})
    leads = {}
    if lead_ids:
        ph = ','.join('?' for _ in lead_ids)
        for lr in c.execute(f"SELECT * FROM leads WHERE id IN ({ph})", lead_ids).fetchall():
            leads[lr['id']] = lr

    entries = []
    for r in rows:
        lead = dict(leads.get(r['lead_id']) or {})
        plan = dict(r)
        sched = schedule_plan_entry(lead, plan, now_utc=now_utc)
        tz = sched.get('recipient_timezone')
        local_time = sched.get('scheduled_local_time')
        tz_unresolved = (not tz
                         or str(lead.get('timezone_status') or '') == 'TIMEZONE_UNRESOLVED')
        body = plan.get('rendered_text_body') or plan.get('body_text') or ''
        first_line = body.splitlines()[0] if body else ''
        entries.append({
            'plan_id': plan.get('plan_id', ''),
            'lead_id': plan.get('lead_id'),
            'store': lead.get('store_name', '') or plan.get('company_name', ''),
            'city': lead.get('city', ''),
            'state': lead.get('state', ''),
            'recipient_timezone': tz,
            'timezone_unresolved': bool(tz_unresolved),
            'schedulable': bool(sched.get('sendable', False)),
            'scheduled_local_time': local_time,
            'scheduled_china_time': _scheduled_to_china(local_time),
            'template': plan.get('template_key') or plan.get('template_id') or '',
            'renderer_version': plan.get('renderer_version') or '',
            'preview': first_line[:80],
        })
    return entries


def compute_send_results_tz(conn, days=30):
    """发送结果：send_log 最近 days 天，join leads，并关联 bounce_log 的 bounce_type。"""
    c = conn.cursor()
    cut = (now_cst() - timedelta(days=days)).strftime('%Y-%m-%d')
    rows = c.execute("""
        SELECT sl.id AS log_id, sl.lead_id, sl.status AS smtp_status, sl.sent_at,
               sl.recipient_timezone, sl.scheduled_local_time, sl.scheduled_utc_time,
               sl.actual_sent_at_local, sl.local_time_deviation_seconds,
               l.store_name, l.city, l.state
        FROM send_log sl LEFT JOIN leads l ON sl.lead_id = l.id
        WHERE substr(COALESCE(sl.sent_at, ''), 1, 10) >= ?
        ORDER BY sl.sent_at DESC
    """, (cut,)).fetchall()
    # 每 lead 取最近一条 bounce_log 的 bounce_type 作为 Delivery Outcome
    bounce_by_lead = {}
    for br in c.execute("SELECT lead_id, bounce_type FROM bounce_log ORDER BY id DESC"):
        if br['lead_id'] is not None and br['lead_id'] not in bounce_by_lead:
            bounce_by_lead[br['lead_id']] = br['bounce_type']

    results = []
    for r in rows:
        deviation = r['local_time_deviation_seconds']
        if deviation is None:
            deviation = _deviation_seconds(r['actual_sent_at_local'], r['scheduled_local_time'])
        results.append({
            'lead_id': r['lead_id'],
            'store': r['store_name'] or '',
            'city': r['city'] or '',
            'state': r['state'] or '',
            'planned_local_time': r['scheduled_local_time'],
            'actual_local_time': r['actual_sent_at_local'],
            'deviation_seconds': deviation,
            'smtp_status': r['smtp_status'] or '',
            'delivery_outcome': bounce_by_lead.get(r['lead_id']) or '—',
        })
    return results


# 6 类异常计数：key 同义词 -> 展示名（对齐 post_send_reconciliation.ISSUE_CATEGORIES）
ANOMALY_CATEGORIES = [
    ('consumed_but_no_send_log', 'Consumed But No Send Log',
     ['consumed_but_no_send_log', 'consumed_no_log']),
    ('send_log_without_plan', 'Send Log Without Plan',
     ['send_log_without_plan', 'sent_without_plan', 'send_without_plan', 'orphan_send']),
    ('smtp_accepted_but_missing_log', 'SMTP Accepted But Missing Log',
     ['smtp_accepted_but_missing_log', 'smtp_missing_log', 'accepted_but_missing']),
    ('duplicate_send', 'Duplicate Send',
     ['duplicate_send', 'duplicate_sent', 'dup_send', 'duplicate']),
    ('unconsumed_after_send', 'Unconsumed After Send',
     ['unconsumed_after_send', 'unconsumed']),
    ('tracking_token_missing', 'Tracking Token Missing',
     ['tracking_token_missing', 'token_missing']),
]


def _match_anomaly(counts, key, value):
    """把对账数据里的一个 key/value 归入 6 类异常之一（宽松子串匹配）。"""
    if isinstance(value, bool):
        return
    kl = str(key).lower()
    if isinstance(value, (int, float)):
        for cat_key, _label, synonyms in ANOMALY_CATEGORIES:
            if any(syn in kl for syn in synonyms):
                counts[cat_key] = max(counts.get(cat_key, 0), int(value))
                return
    elif isinstance(value, list):
        for cat_key, _label, synonyms in ANOMALY_CATEGORIES:
            if any(syn in kl for syn in synonyms):
                counts[cat_key] = max(counts.get(cat_key, 0), len(value))
                return


def _extract_anomaly_counts(payload):
    """从对账结果 dict 中提取 6 类异常计数。

    兼容两种格式：
      - issues: {cat: {'count': N, 'items': [...]}}   （reconcile_batch 返回 / output JSON）
      - issue_counts: {cat: N}                         （system_config 值）
    """
    counts = {}
    if not isinstance(payload, dict):
        return counts

    # 情况 1：issue_counts 扁平映射
    ic = payload.get('issue_counts')
    if isinstance(ic, dict):
        for k, v in ic.items():
            _match_anomaly(counts, k, v)

    # 情况 2：issues 子结构（每类 {'count': N, 'items': [...]}）
    issues = payload.get('issues')
    if isinstance(issues, dict):
        for k, v in issues.items():
            if isinstance(v, dict) and 'count' in v:
                _match_anomaly(counts, k, v['count'])

    # 情况 3：顶层/嵌套的宽松匹配兜底
    for k, v in payload.items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, dict) and 'count' in v2:
                    _match_anomaly(counts, k2, v2['count'])
                else:
                    _match_anomaly(counts, k2, v2)
        else:
            _match_anomaly(counts, k, v)
    return counts


def _normalize_recon_batch(payload, source=''):
    """把单个对账结果归一化为展示用 dict。"""
    if not isinstance(payload, dict):
        return None
    status_raw = str(payload.get('status') or payload.get('verdict')
                     or payload.get('result') or payload.get('overall') or '').upper()
    passed = any(tok in status_raw for tok in ('PASS', 'OK', 'GOOD'))
    failed = any(tok in status_raw for tok in ('FAIL', 'ERROR', 'BAD'))
    if not status_raw:
        status_raw = 'PASSED' if passed else ('FAILED' if failed else 'UNKNOWN')
    return {
        'batch_id': (payload.get('batch_id') or payload.get('batch') or source),
        'source': source,
        'status_raw': status_raw,
        'passed': passed,
        'failed': failed,
        'checked_at': (payload.get('checked_at') or payload.get('reconciled_at')
                       or payload.get('generated_at') or payload.get('timestamp')),
        'anomalies': _extract_anomaly_counts(payload),
        'summary': (payload.get('summary') or payload.get('message') or ''),
    }


def collect_reconciliation(conn, out_dir=None):
    """读取 output/post_send_reconciliation_*.json 与 system_config 的 post_send_reconciliation_* key。"""
    batches = []
    if out_dir:
        for f in sorted(out_dir.glob('post_send_reconciliation_*.json')):
            try:
                payload = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            b = _normalize_recon_batch(payload, source=f.name)
            if b:
                batches.append(b)
    c = conn.cursor()
    for r in c.execute("SELECT key, value FROM system_config WHERE key LIKE 'post_send_reconciliation_%'"):
        try:
            payload = json.loads(r[1])
            if not isinstance(payload, dict):
                payload = {'status': r[1]}
            # system_config 值可能不含 batch_id，从 key 剥离前缀推导
            if not payload.get('batch_id'):
                payload['batch_id'] = r[0][len('post_send_reconciliation_'):]
            b = _normalize_recon_batch(payload, source=r[0])
        except Exception:
            b = _normalize_recon_batch({'status': r[1],
                                        'batch_id': r[0][len('post_send_reconciliation_'):]},
                                       source=r[0])
        if b:
            batches.append(b)

    # 按 batch_id 去重（JSON 文件与 system_config 可能指向同一批次），再按检查时间倒序
    seen = set()
    unique = []
    for b in batches:
        key = b.get('batch_id') or b.get('source')
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(b)
    unique.sort(key=lambda x: x.get('checked_at') or '', reverse=True)
    return {
        'batches': unique,
        'any_failed': any(b.get('failed') for b in unique),
    }


def _render_timezone_stats(tzs):
    """时区统计卡：RESOLVED / UNRESOLVED / 自动调度可发送 + 按时区分布徽章。"""
    stats = ''
    for key, label in (
        ('resolved', 'Timezone RESOLVED'),
        ('unresolved', 'TIMEZONE_UNRESOLVED'),
        ('sendable_for_automatic_schedule', 'Auto-Schedule Sendable'),
    ):
        stats += (
            f'<div class="stat"><div class="num {"" if key != "unresolved" else "red"}">'
            f'{tzs.get(key, 0)}</div><div class="label">{label}</div></div>'
        )
    dist = tzs.get('distribution', {})
    dist_html = ' '.join(
        f'<span class="badge badge-{"green" if region == "Eastern" else ("blue" if region == "Central" else "yellow")}">'
        f'{region}: {dist.get(region, 0)}</span>'
        for region in ('Eastern', 'Central', 'Mountain', 'Pacific', 'Other')
    )
    return stats, dist_html


def _render_schedule_rows(entries):
    """发送预览表格行：Store/City/State/Timezone/本地/China/Template/Renderer/Preview。"""
    rows = ''
    for e in entries:
        if e.get('timezone_unresolved'):
            tz_cell = ('<span class="badge badge-red">TIMEZONE_UNRESOLVED</span> '
                       '<span class="badge badge-yellow">NOT SCHEDULABLE</span>')
        elif not e.get('schedulable'):
            tz_cell = (f"{e.get('recipient_timezone') or '—'} "
                       '<span class="badge badge-yellow">NOT SCHEDULABLE</span>')
        else:
            tz_cell = e.get('recipient_timezone') or '—'
        rows += (
            f'<tr><td>{e.get("store") or "—"}</td>'
            f'<td>{e.get("city") or "—"}</td>'
            f'<td>{e.get("state") or "—"}</td>'
            f'<td>{tz_cell}</td>'
            f'<td>{e.get("scheduled_local_time") or "—"}</td>'
            f'<td>{e.get("scheduled_china_time") or "—"}</td>'
            f'<td>{e.get("template") or "—"}</td>'
            f'<td>{e.get("renderer_version") or "—"}</td>'
            f'<td>{e.get("preview") or "—"}</td></tr>'
        )
    return rows or '<tr><td colspan="9" style="color:#8b949e">暂无计划行（final_send_plan 无 planned/最近批次数据）</td></tr>'


def _render_send_results_rows(entries):
    """发送结果表格行：Store/Planned/Actual/Deviation/SMTP Status/Delivery Outcome。"""
    rows = ''
    for e in entries:
        dev = e.get('deviation_seconds')
        if dev is None:
            dev_cell = '—'
        elif abs(dev) > 300:
            dev_cell = f'<span class="red">{dev}</span>'
        else:
            dev_cell = str(dev)
        rows += (
            f'<tr><td>{e.get("store") or "—"}</td>'
            f'<td>{e.get("planned_local_time") or "—"}</td>'
            f'<td>{e.get("actual_local_time") or "—"}</td>'
            f'<td>{dev_cell}</td>'
            f'<td>{e.get("smtp_status") or "—"}</td>'
            f'<td>{e.get("delivery_outcome") or "—"}</td></tr>'
        )
    return rows or '<tr><td colspan="6" style="color:#8b949e">最近 30 天无发送记录</td></tr>'


def generate_dashboard(data):
    m = data['manual']
    inv = data['inventory']
    fu = data['followup']
    dl = data.get('delivery', {})
    fr = data.get('freshness', {})
    rc = data.get('reconciliation', {})
    tzs = data.get('timezone_stats', {})
    schedule_entries = data.get('schedule_preview', [])
    send_entries = data.get('send_results_tz', [])

    # 时区统计卡 + 两个表格
    tz_stat_html, tz_dist_html = _render_timezone_stats(tzs)
    schedule_rows = _render_schedule_rows(schedule_entries)
    send_rows = _render_send_results_rows(send_entries)

    # Data Freshness 徽章
    fr_badge = f'<span class="badge badge-{fr.get("level", "red")}">{fr.get("badge_label", "DATA STALE")}</span>'

    # Delivery Outcome 分类统计卡片（stat 块拼接）
    delivery_stats = ''
    for label, key in (
        ('Domain Invalid', 'domain_invalid'),
        ('Mailbox Invalid', 'mailbox_invalid'),
        ('Policy Bounce', 'policy_bounce'),
        ('Soft Bounce', 'soft_bounce'),
        ('Hard Bounce', 'hard_bounce'),
        ('Unmatched DSN', 'unmatched_dsn'),
        ('Human Reply', 'human_reply'),
        ('Auto Reply', 'auto_reply'),
        ('Other Bounce', 'other_bounce'),
    ):
        delivery_stats += (
            f'<div class="stat"><div class="num">{dl.get(key, 0)}</div>'
            f'<div class="label">{label}</div></div>'
        )

    # 对账批次行（表头与 6 类异常列动态生成）
    recon_headers = ''.join(f'<th>{label}</th>' for _cat, label, _syn in ANOMALY_CATEGORIES)
    recon_rows = ''
    if rc.get('batches'):
        for b in rc['batches']:
            if b.get('failed'):
                badge = '<span class="badge badge-red">FAILED</span>'
            elif b.get('passed'):
                badge = '<span class="badge badge-green">PASSED</span>'
            else:
                badge = f'<span class="badge badge-yellow">{b.get("status_raw", "UNKNOWN")}</span>'
            anom_cells = ''
            for cat_key, _label, _syn in ANOMALY_CATEGORIES:
                anom_cells += (
                    f'<td class="{"red" if b["anomalies"].get(cat_key, 0) else ""}">'
                    f'{b["anomalies"].get(cat_key, 0)}</td>'
                )
            recon_rows += (
                f'<tr><td>{b.get("batch_id", "")}<br><span class="recon">{b.get("checked_at") or b.get("source")}</span></td>'
                f'<td>{badge}</td>{anom_cells}</tr>'
            )
    else:
        recon_rows = (
            f'<tr><td colspan="{2 + len(ANOMALY_CATEGORIES)}" style="color:#8b949e">无对账记录（尚未生成 '
            'post_send_reconciliation_*.json 或 system_config.post_send_reconciliation_*）</td></tr>'
        )

    recon_banner = ''
    if rc.get('any_failed'):
        recon_banner = (
            '<div style="background:#da3633;color:#fff;padding:10px 14px;border-radius:6px;'
            'font-size:13px;font-weight:600;margin-bottom:12px">'
            'POST_SEND_RECONCILIATION_FAILED — 最近批次对账失败，请立即人工核查</div>'
        )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BD Operations Dashboard — {today_cst()}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, Segoe UI, sans-serif; background: #0d1117; color: #c9d1d9; }}
.header {{ background: #161b22; padding: 16px 24px; border-bottom: 1px solid #30363d; }}
.header h1 {{ font-size: 20px; color: #58a6ff; }}
.header span {{ font-size: 12px; color: #8b949e; }}
.tabs {{ display: flex; gap: 0; background: #161b22; padding: 0 24px; border-bottom: 1px solid #30363d; }}
.tab {{ padding: 10px 18px; cursor: pointer; border: none; background: none; color: #8b949e; font-size: 13px; border-bottom: 2px solid transparent; }}
.tab:hover {{ color: #c9d1d9; }}
.tab.active {{ color: #58a6ff; border-bottom-color: #f78166; }}
.content {{ display: none; padding: 20px 24px; }}
.content.active {{ display: block; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 16px; margin-bottom: 16px; }}
.card-title {{ font-size: 14px; font-weight: 600; color: #58a6ff; margin-bottom: 12px; }}
.stat-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 12px; }}
.stat {{ background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 12px 16px; min-width: 120px; }}
.stat .num {{ font-size: 24px; font-weight: 700; }}
.stat .label {{ font-size: 11px; color: #8b949e; margin-top: 4px; }}
.green {{ color: #3fb950; }}
.yellow {{ color: #d29922; }}
.red {{ color: #f85149; }}
.blue {{ color: #58a6ff; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th {{ text-align: left; padding: 8px; background: #21262d; color: #8b949e; font-weight: 500; }}
td {{ padding: 6px 8px; border-bottom: 1px solid #21262d; }}
tr:hover {{ background: #161b22; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; }}
.badge-green {{ background: #238636; color: #fff; }}
.badge-yellow {{ background: #9e6a03; color: #fff; }}
.badge-red {{ background: #da3633; color: #fff; }}
.badge-blue {{ background: #1f6feb; color: #fff; }}
.btn {{ padding: 6px 14px; border-radius: 6px; border: 1px solid #30363d; background: #21262d; color: #c9d1d9; cursor: pointer; font-size: 12px; }}
.btn:hover {{ background: #30363d; }}
.btn-primary {{ background: #238636; border-color: #238636; color: #fff; }}
.btn-danger {{ background: #da3633; border-color: #da3633; color: #fff; }}
.recon {{ font-size: 12px; color: #8b949e; font-family: monospace; margin-top: 8px; }}
</style>
</head>
<body>
<div class="header">
  <h1>BD Operations Dashboard</h1>
  <span>Generated: {now_cst().strftime('%Y-%m-%d %H:%M:%S')} CST | Scheduler: Windows Task | Authority: windows_task_scheduler</span>
</div>

<div class="tabs">
  <button class="tab active" onclick="switchTab('overview')">Overview</button>
  <button class="tab" onclick="switchTab('manual')">Manual Review ({m['total_pending']})</button>
  <button class="tab" onclick="switchTab('inventory')">Inventory</button>
  <button class="tab" onclick="switchTab('followup')">Follow-up</button>
  <button class="tab" onclick="switchTab('delivery')">Delivery Outcome</button>
  <button class="tab" onclick="switchTab('schedule')">Schedule</button>
  <button class="tab" onclick="switchTab('sendresults')">Send Results</button>
  <button class="tab" onclick="switchTab('ops')">Ops Health</button>
</div>

<!-- OVERVIEW TAB -->
<div class="content active" id="tab-overview">
  <div class="card">
    <div class="card-title">Today — {today_cst()}</div>
    <div class="stat-row">
      <div class="stat"><div class="num blue">{inv['today_sent']}/20</div><div class="label">New Outreach Today</div></div>
      <div class="stat"><div class="num">{inv['unique_auto_sendable']}</div><div class="label">Auto-Sendable A0</div></div>
      <div class="stat"><div class="num">{m['total_pending']}</div><div class="label">Pending Manual Review</div></div>
      <div class="stat"><div class="num {('green' if fu['final_sendable']>0 else 'yellow')}">{fu['final_sendable']}</div><div class="label">Follow-up Sendable</div></div>
      <div class="stat"><div class="num">{inv['total_leads']}</div><div class="label">Total Inventory</div></div>
      <div class="stat"><div class="num">{inv['total_sent_all']}</div><div class="label">All-time Sent</div></div>
      <div class="stat"><div class="num"><span class="badge badge-{fr.get('level', 'red')}">{fr.get('badge_label', 'DATA STALE')}</span></div><div class="label">Data Freshness</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Timezone Status（时区统计）</div>
    <div class="stat-row">
      {tz_stat_html}
    </div>
    <div style="font-size:12px;margin-top:8px">
      按时区分布：{tz_dist_html}
    </div>
    <p style="font-size:12px;color:#8b949e;margin-top:8px">
      RESOLVED = leads 已解析出 recipient_timezone；TIMEZONE_UNRESOLVED = 无时区或标记 UNRESOLVED（不可自动调度）；
      Auto-Schedule Sendable = sendable_for_automatic_schedule=1 的数量。
    </p>
  </div>

  <div class="card">
    <div class="card-title">SMTP Accepted vs Delivery Outcome (all-time)</div>
    <div class="stat-row">
      <div class="stat"><div class="num green">{dl.get('smtp_accepted_all', 0)}</div><div class="label">SMTP Accepted (All)</div></div>
      <div class="stat"><div class="num blue">{dl.get('smtp_accepted_30d', 0)}</div><div class="label">SMTP Accepted (30d)</div></div>
      <div class="stat"><div class="num">{dl.get('classified_total', 0)}</div><div class="label">Classified Outcomes</div></div>
      <div class="stat"><div class="num yellow">{dl.get('outcome_unresolved', 0)}</div><div class="label">Outcome Unresolved</div></div>
    </div>
    <p style="font-size:12px;color:#8b949e;margin-top:8px">
      SMTP Accepted 与 Delivery Outcome 分开统计：bounced 邮件视为「已发送但投递失败」，
      不会从 SMTP Accepted 中扣除。
    </p>
  </div>

  <div class="card">
    <div class="card-title">Quick Actions</div>
    <button class="btn btn-primary" onclick="switchTab('manual')">Open Manual Review ({m['total_pending']})</button>
    <button class="btn" onclick="switchTab('inventory')">View Inventory Breakdown</button>
    <button class="btn" onclick="switchTab('followup')">Check Follow-up Status</button>
  </div>
</div>

<!-- MANUAL REVIEW TAB -->
<div class="content" id="tab-manual">
  <div class="card">
    <div class="card-title">Manual Review Queue</div>
    <div class="stat-row">
      <div class="stat"><div class="num yellow">{m['manual_review_needed']}</div><div class="label">Needs Review (B)</div></div>
      <div class="stat"><div class="num">{m['b_pool_new']}</div><div class="label">B-Pool New</div></div>
      <div class="stat"><div class="num red">{m['bounce_review']}</div><div class="label">Bounce Review</div></div>
      <div class="stat"><div class="num blue">{m['contact_form_pool']}</div><div class="label">Contact Form Pool</div></div>
      <div class="stat"><div class="num">{m['delivery_issue']}</div><div class="label">Delivery Issues</div></div>
      <div class="stat"><div class="num">{m['oldest_wait_days']}d</div><div class="label">Oldest Waiting</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Review Actions (this session)</div>
    <div class="stat-row">
      <div class="stat"><div class="num green">{m['approved_count']}</div><div class="label">Approved</div></div>
      <div class="stat"><div class="num red">{m['rejected_count']}</div><div class="label">Rejected</div></div>
      <div class="stat"><div class="num yellow">{m['deferred_count']}</div><div class="label">Deferred</div></div>
      <div class="stat"><div class="num">{m['approved_manual_send']}</div><div class="label">Approved Manual Send</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Categories</div>
    <div class="stat-row">
      <div class="stat"><div class="num">{len(data['review_queue'])}</div><div class="label">Sample Ready</div></div>
      <div class="stat"><div class="num">{m['contact_form_pool']}</div><div class="label">Custom C (Contact Form)</div></div>
    </div>
    <p style="font-size:12px;color:#8b949e;margin-top:8px">
      Full queue exported to: <code>output/manual_review_queue.json</code><br>
      Review actions available via: <code>python bd_review_cli.py approve/reject/defer [lead_id]</code>
    </p>
  </div>
</div>

<!-- INVENTORY TAB -->
<div class="content" id="tab-inventory">
  <div class="card">
    <div class="card-title">Auto-Sendable A0 Inventory</div>
    <div class="stat-row">
      <div class="stat"><div class="num green">{inv['retail_auto_sendable']}</div><div class="label">Retail (TN/AR/KY)</div></div>
      <div class="stat"><div class="num blue">{inv['custom_auto_sendable']}</div><div class="label">Custom (Any State)</div></div>
      <div class="stat"><div class="num yellow">-{inv['overlap']}</div><div class="label">Overlap</div></div>
      <div class="stat"><div class="num" style="font-size:28px">{inv['unique_auto_sendable']}</div><div class="label">Unique Auto-Sendable</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Blocked / Other State</div>
    <div class="stat-row">
      <div class="stat"><div class="num">{inv['other_state_custom']}</div><div class="label">Other-State Custom</div></div>
      <div class="stat"><div class="num red">{inv['other_state_retail_blocked']}</div><div class="label">Other-State Retail BLOCKED</div></div>
      <div class="stat"><div class="num">{inv['manual_review_count']}</div><div class="label">Manual Review Pool</div></div>
      <div class="stat"><div class="num">{inv['custom_c_pool']}</div><div class="label">Custom C (Contact Form)</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Today's Inventory Changes</div>
    <div class="recon">
      Sent: -{inv['today_sent']} | New A0: +{inv['today_new_a0']} | Demoted: -{inv['today_demoted']} | Moved to Review: -{m['total_pending']}
    </div>
    <div class="recon" style="margin-top:4px">
      Current Unique: {inv['unique_auto_sendable']} = previous - sent + new - demoted - review
    </div>
  </div>

  <div class="card">
    <div class="card-title">State Distribution</div>
    <table>
      <tr><th>State</th><th>Count</th><th>Status</th></tr>
      {''.join(f'<tr><td>{state}</td><td>{count}</td><td><span class="badge {"badge-green" if state in ("TN","AR","KY") else "badge-red"}">{"Auto-Send" if state in ("TN","AR","KY") else "Blocked/Manual"}</span></td></tr>' for state, count in sorted(inv['state_breakdown'].items(), key=lambda x: -x[1])[:15])}
    </table>
  </div>
</div>

<!-- FOLLOW-UP TAB -->
<div class="content" id="tab-followup">
  <div class="card">
    <div class="card-title">Follow-up Rotation Status: <span class="badge {"badge-red" if fu['status']=='never_executed' else ("badge-green" if fu['status']=='active' else "badge-yellow")}">{fu['status']}</span></div>
    <div class="stat-row">
      <div class="stat"><div class="num blue">{fu['final_sendable']}</div><div class="label">Final Sendable</div></div>
      <div class="stat"><div class="num">{fu['today_planned']}</div><div class="label">Today Planned</div></div>
      <div class="stat"><div class="num">{fu['today_sent']}</div><div class="label">Today Sent</div></div>
      <div class="stat"><div class="num">{fu['daily_limit']}</div><div class="label">Daily Limit</div></div>
      <div class="stat"><div class="num">{fu['last_run']}</div><div class="label">Last Run</div></div>
      <div class="stat"><div class="num">{fu['next_planned']}</div><div class="label">Next Planned</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Exclusions (from {fu['raw_candidates']} raw candidates)</div>
    <div class="stat-row">
      <div class="stat"><div class="num">{fu['raw_candidates']}</div><div class="label">Total Sent Log</div></div>
      <div class="stat"><div class="num yellow">{fu.get('excluded_not_14d', 0)}</div><div class="label">Not 14 Days Yet</div></div>
      <div class="stat"><div class="num red">{fu['excluded_bounced']}</div><div class="label">Hard Bounced</div></div>
      <div class="stat"><div class="num">{fu['excluded_unsubscribed']}</div><div class="label">Unsubscribed</div></div>
      <div class="stat"><div class="num">{fu['excluded_suppressed']}</div><div class="label">Suppressed</div></div>
      <div class="stat"><div class="num">{fu['excluded_already_followed']}</div><div class="label">Already Followed</div></div>
      <div class="stat"><div class="num">{fu['excluded_domain_mismatch']}</div><div class="label">Domain Mismatch</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Wiring Status</div>
    <table>
      <tr><th>Check</th><th>Status</th></tr>
      <tr><td>09:00 code calls build_followup_queue</td><td><span class="badge {"badge-green" if fu['is_wired'] else "badge-red"}">{"Yes" if fu['is_wired'] else "No"}</span></td></tr>
      <tr><td>Ever sent live follow-up</td><td><span class="badge {"badge-green" if fu['ever_sent_live'] else "badge-red"}">{"Yes" if fu['ever_sent_live'] else "No — never executed"}</span></td></tr>
      <tr><td>Follow-up template</td><td><span class="badge badge-yellow">Standalone (no In-Reply-To)</span></td></tr>
      <tr><td>Daily max 5 enforced</td><td><span class="badge badge-green">Yes (hardcoded in stage_outreach)</span></td></tr>
      <tr><td>Separate from New Outreach 20</td><td><span class="badge badge-green">Yes (Phase 1 vs Phase 2)</span></td></tr>
      <tr><td>Status writeback on success</td><td><span class="badge badge-yellow">Never tested live</span></td></tr>
      <tr><td>Duplicate protection</td><td><span class="badge badge-green">Yes (email + domain dedup)</span></td></tr>
    </table>
  </div>
</div>

<!-- DELIVERY OUTCOME TAB -->
<div class="content" id="tab-delivery">
  <div class="card">
    <div class="card-title">SMTP Accepted <span style="color:#8b949e;font-weight:400">（已成功接收于 SMTP，按最近30天/全部两个口径）</span></div>
    <div class="stat-row">
      <div class="stat"><div class="num green">{dl.get('smtp_accepted_all', 0)}</div><div class="label">SMTP Accepted (All-time)</div></div>
      <div class="stat"><div class="num blue">{dl.get('smtp_accepted_30d', 0)}</div><div class="label">SMTP Accepted (Last 30d)</div></div>
      <div class="stat"><div class="num yellow">{dl.get('outcome_unresolved', 0)}</div><div class="label">Outcome Unresolved</div></div>
      <div class="stat"><div class="num">{dl.get('hard_delivery_rate', 0)}%</div><div class="label">Hard Delivery Rate</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Delivery Outcome 分类 <span style="color:#8b949e;font-weight:400">（投递失败 ≠ 未发送，这些邮件已计入上方 SMTP Accepted）</span></div>
    <div class="stat-row">
      {delivery_stats}
    </div>
  </div>

  <div class="card">
    <div class="card-title">口径说明</div>
    <p style="font-size:12px;color:#8b949e;line-height:1.7">
      - SMTP Accepted = send_log 中 status='sent' 的总数，只反映「SMTP 服务器已接受」<br>
      - Delivery Outcome 来自 bounce_log（bounce_type 分类）、unmatched_dsn 表与 reply_log<br>
      - bounced 邮件显示为「已发送但投递失败」，不从 SMTP Accepted 中扣除<br>
      - Outcome Unresolved = SMTP Accepted (All-time) − 已分类计数，代表已发送但暂未观测到 bounce/reply
    </p>
  </div>
</div>

<!-- SCHEDULE PREVIEW TAB -->
<div class="content" id="tab-schedule">
  <div class="card">
    <div class="card-title">Scheduled Sends Preview（发送预览）</div>
    <p style="font-size:12px;color:#8b949e;margin-bottom:8px">
      数据来源：final_send_plan 中 status='planned'（无 planned 时取最近批次的 planned/sent）join leads。
      Scheduled Local Time 按生产政策「收件人当地 10:00, Mon-Fri」由 recipient_scheduler 计算；
      Scheduled China Time = 收件人当地时刻转 Asia/Shanghai。Recipient Timezone 为空 → TIMEZONE_UNRESOLVED + NOT SCHEDULABLE。
    </p>
    <table>
      <tr>
        <th>Store</th><th>City</th><th>State</th><th>Recipient Timezone</th>
        <th>Scheduled Local Time</th><th>Scheduled China Time</th>
        <th>Template</th><th>Renderer Version</th><th>Preview</th>
      </tr>
      {schedule_rows}
    </table>
  </div>
</div>

<!-- SEND RESULTS TAB -->
<div class="content" id="tab-sendresults">
  <div class="card">
    <div class="card-title">Send Results with Timezone（最近 30 天）</div>
    <p style="font-size:12px;color:#8b949e;margin-bottom:8px">
      数据来源：send_log 最近 30 天 join leads；Delivery Outcome 来自 bounce_log 的 bounce_type（无则为 —）。
      Local Time Deviation = actual_sent_at_local 与 scheduled_local_time 的秒差（>300s 标红）。
    </p>
    <table>
      <tr>
        <th>Store</th><th>Planned Local Time</th><th>Actual Local Time</th>
        <th>Local Time Deviation (秒)</th><th>SMTP Status</th><th>Delivery Outcome</th>
      </tr>
      {send_rows}
    </table>
  </div>
</div>

<!-- OPS HEALTH TAB -->
<div class="content" id="tab-ops">
  <div class="card">
    <div class="card-title">数据新鲜度 Data Freshness {fr_badge}</div>
    <div class="stat-row">
      <div class="stat"><div class="num" style="font-size:14px">{fr.get('last_bounce_scan_at') or 'N/A'}</div><div class="label">Last Bounce Scan</div></div>
      <div class="stat"><div class="num" style="font-size:14px">{fr.get('last_reply_scan_at') or 'N/A'}</div><div class="label">Last Reply Scan</div></div>
      <div class="stat"><div class="num" style="font-size:14px">{fr.get('sync_0845_last_success_at') or 'N/A'}</div><div class="label">Last Successful Sync (08:45)</div></div>
      <div class="stat"><div class="num">{fr.get('age_minutes') if fr.get('age_minutes') is not None else 'N/A'}</div><div class="label">Bounce Scan Age (min)</div></div>
    </div>
    <p style="font-size:12px;color:#8b949e;margin-top:8px">
      徽章规则：距 last_bounce_scan_at &lt; 90min → GREEN；90min-24h → YELLOW；&gt; 24h 或缺失 → RED + 'DATA STALE'
    </p>
  </div>

  <div class="card">
    <div class="card-title">Plan / Auth / SMTP / send_log 对账</div>
    {recon_banner}
    <table>
      <tr>
        <th>Batch</th><th>Status</th>
        {recon_headers}
      </tr>
      {recon_rows}
    </table>
    <p style="font-size:12px;color:#8b949e;margin-top:8px">
      数据来源：output/post_send_reconciliation_*.json 与 system_config.post_send_reconciliation_*
    </p>
  </div>
</div>

<script>
function switchTab(name) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.tab').forEach(t => {{ if (t.textContent.toLowerCase().includes(name)) t.classList.add('active'); }});
}}
</script>
</body>
</html>'''
    return html


def main():
    data = collect_all_data()

    # Write dashboard
    html = generate_dashboard(data)
    dash_path = OUT_DIR / 'bd_operations_dashboard.html'
    dash_path.write_text(html, encoding='utf-8')
    print(f'Dashboard: {dash_path}')

    # Write review queue JSON
    queue_path = OUT_DIR / 'manual_review_queue.json'
    with open(queue_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': now_cst().isoformat(),
            'total_pending': data['manual']['total_pending'],
            'categories': {
                'manual_review_needed': data['manual']['manual_review_needed'],
                'bounce_review': data['manual']['bounce_review'],
                'contact_form_pool': data['manual']['contact_form_pool'],
            },
            'queue': data['review_queue'][:100],
        }, f, indent=2, default=str)
    print(f'Review queue: {queue_path}')

    # Write follow-up status JSON
    fu_path = OUT_DIR / 'followup_rotation_status.json'
    with open(fu_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': now_cst().isoformat(),
            **data['followup'],
        }, f, indent=2, default=str)
    print(f'Follow-up status: {fu_path}')

    print(f'\nManual Review: {data["manual"]["total_pending"]} pending')
    print(f'Inventory: {data["inventory"]["unique_auto_sendable"]} A0 sendable')
    print(f'Follow-up: {data["followup"]["status"]} ({data["followup"]["final_sendable"]} sendable)')
    print(f'SMTP Accepted: {data["delivery"]["smtp_accepted_all"]} (30d: {data["delivery"]["smtp_accepted_30d"]})')
    print(f'Delivery Outcome: domain_invalid={data["delivery"]["domain_invalid"]} '
          f'mailbox_invalid={data["delivery"]["mailbox_invalid"]} '
          f'policy={data["delivery"]["policy_bounce"]} soft={data["delivery"]["soft_bounce"]} '
          f'hard={data["delivery"]["hard_bounce"]} unmatched_dsn={data["delivery"]["unmatched_dsn"]} '
          f'human_reply={data["delivery"]["human_reply"]} auto_reply={data["delivery"]["auto_reply"]} '
          f'unresolved={data["delivery"]["outcome_unresolved"]}')
    print(f'Data Freshness: {data["freshness"]["badge_label"]} '
          f'(last_bounce_scan_at={data["freshness"]["last_bounce_scan_at"]}, '
          f'age={data["freshness"]["age_minutes"]}min)')
    print(f'Reconciliation: {len(data["reconciliation"]["batches"])} batch(es), '
          f'any_failed={data["reconciliation"]["any_failed"]}')
    print(f'Timezone: resolved={data["timezone_stats"]["resolved"]} '
          f'unresolved={data["timezone_stats"]["unresolved"]} '
          f'auto_schedule_sendable={data["timezone_stats"]["sendable_for_automatic_schedule"]} '
          f'distribution={data["timezone_stats"]["distribution"]}')
    print(f'Schedule Preview: {len(data["schedule_preview"])} row(s)')
    print(f'Send Results (30d): {len(data["send_results_tz"])} row(s)')


if __name__ == '__main__':
    main()
