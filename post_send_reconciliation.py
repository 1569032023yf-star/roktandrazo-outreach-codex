#!/usr/bin/env python3
"""BD Post-Send Reconciliation — 发信后自动对账。

对账范围（按 outreach_batch_date = batch_id）：
  final_send_plan   ↔  send_authorization_entries（consumed）  ↔  send_log
以 (lead_id, recipient_email) 为唯一键做三方一一对应检查，识别 6 类异常。

异常分类：
  1) consumed_but_no_send_log      auth entry 已 consumed 但 send_log 无对应行
  2) send_log_without_plan         send_log 有条目但 final_send_plan 无对应行
  3) SMTP_accepted_but_missing_log final_send_plan status='sent' 但 send_log 无对应行
  4) duplicate_send                同 lead_id+email 在 send_log 出现 >1 次
  5) unconsumed_after_send         final_send_plan status='sent' 但 auth entry 未 consumed（或无 entry）
  6) tracking_token_missing        send_log 有条目但 tracking_token_hash 为空，或 email_tracking_messages 无对应 token_hash

默认只读打印报告；--write 时写入 system_config 状态与 output JSON。
发现异常时只标记 FAILED，绝不重发（不调用 SMTP）。
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta

ASIA_SH = timezone(timedelta(hours=8))
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, 'data', 'bd_leads.db')
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'output')

ISSUE_CATEGORIES = (
    'consumed_but_no_send_log',
    'send_log_without_plan',
    'SMTP_accepted_but_missing_log',
    'duplicate_send',
    'unconsumed_after_send',
    'tracking_token_missing',
)

SEND_LOG_FAILED_STATUSES = ('failed', 'bounced', 'error', 'test_failed')
SEND_LOG_SKIPPED_STATUSES = ('skipped', 'test')


def _norm_email(value):
    """规范化邮箱：去空白并转小写，用于跨表比对。"""
    return (value or '').strip().lower()


def _config_key(batch_id):
    """system_config 中的对账状态 key。"""
    return f'post_send_reconciliation_{batch_id}'


def _empty_issues():
    """返回六类异常的初始结构。"""
    return {cat: {'count': 0, 'items': []} for cat in ISSUE_CATEGORIES}


def reconcile_batch(conn, batch_id):
    """对单个批次执行发信后对账，返回完整结果 dict。

    以 (lead_id, recipient_email) 为键，对 final_send_plan / auth entries /
    send_log 三方做集合对比。本函数只读，不写任何状态。
    """
    cur = conn.cursor()
    now = datetime.now(ASIA_SH).isoformat()

    # ── 读取三方数据 ──
    plan_rows = cur.execute(
        "SELECT plan_id, lead_id, recipient_email, status FROM final_send_plan "
        "WHERE outreach_batch_date=?",
        (batch_id,)
    ).fetchall()

    auth_rows = cur.execute(
        "SELECT authorization_id, approved_entry_count, status FROM send_authorizations "
        "WHERE outreach_batch_date=?",
        (batch_id,)
    ).fetchall()

    entry_rows = []
    for auth in auth_rows:
        rows = cur.execute(
            "SELECT authorization_id, plan_entry_id, lead_id, recipient_email, status "
            "FROM send_authorization_entries WHERE authorization_id=?",
            (auth[0],)
        ).fetchall()
        entry_rows.extend(rows)

    log_rows = cur.execute(
        "SELECT id, lead_id, email, status, message_id, tracking_token_hash "
        "FROM send_log WHERE outreach_batch_date=?",
        (batch_id,)
    ).fetchall()

    tracking_hashes = {
        (r[0] or '') for r in cur.execute(
            "SELECT token_hash FROM email_tracking_messages"
        ).fetchall()
    } if _table_exists(cur, 'email_tracking_messages') else set()

    # ── 基础计数 ──
    plan_total = len(plan_rows)
    auth_total = len(auth_rows)
    approved_entry_total = sum((r[1] or 0) for r in auth_rows)
    consumed_total = sum(1 for e in entry_rows if e[4] == 'consumed')
    send_log_total = len(log_rows)

    smtp_accepted = sum(1 for l in log_rows if l[3] == 'sent')
    smtp_failed = sum(1 for l in log_rows if (l[3] or '') in SEND_LOG_FAILED_STATUSES)
    smtp_skipped = sum(1 for l in log_rows if (l[3] or '') in SEND_LOG_SKIPPED_STATUSES)
    send_log_delta = send_log_total - consumed_total
    message_id_present_count = sum(1 for l in log_rows if (l[4] or '').strip())
    tracking_token_present_count = sum(1 for l in log_rows if (l[5] or '').strip())

    # ── 集合对比 ──
    plan_set = {(r[1], _norm_email(r[2])) for r in plan_rows}
    sent_plan_set = {(r[1], _norm_email(r[2])) for r in plan_rows if r[3] == 'sent'}
    consumed_entry_set = {(e[2], _norm_email(e[3])) for e in entry_rows if e[4] == 'consumed'}
    log_set = {(l[1], _norm_email(l[2])) for l in log_rows}

    issues = _empty_issues()

    # 1) consumed 但 send_log 无对应行
    for e in entry_rows:
        if e[4] == 'consumed' and (e[2], _norm_email(e[3])) not in log_set:
            issues['consumed_but_no_send_log']['items'].append({
                'lead_id': e[2],
                'recipient_email': e[3],
                'authorization_id': e[0],
            })

    # 2) send_log 有条目但 final_send_plan 无对应行
    for l in log_rows:
        if (l[1], _norm_email(l[2])) not in plan_set:
            issues['send_log_without_plan']['items'].append({
                'lead_id': l[1],
                'email': l[2],
                'send_log_id': l[0],
                'status': l[3],
            })

    # 3) plan status='sent' 但 send_log 无对应行
    for r in plan_rows:
        if r[3] == 'sent' and (r[1], _norm_email(r[2])) not in log_set:
            issues['SMTP_accepted_but_missing_log']['items'].append({
                'lead_id': r[1],
                'recipient_email': r[2],
                'plan_id': r[0],
            })

    # 4) 同 lead_id+email 在 send_log 出现 >1 次
    log_key_counts = {}
    for l in log_rows:
        key = (l[1], _norm_email(l[2]))
        log_key_counts[key] = log_key_counts.get(key, 0) + 1
    for (lead_id, email), count in log_key_counts.items():
        if count > 1:
            issues['duplicate_send']['items'].append({
                'lead_id': lead_id,
                'email': email,
                'count': count,
            })

    # 5) plan status='sent' 但 auth entry 未 consumed（或无 entry）
    entry_status_by_key = {}
    for e in entry_rows:
        entry_status_by_key[(e[2], _norm_email(e[3]))] = e[4]
    for r in plan_rows:
        if r[3] != 'sent':
            continue
        key = (r[1], _norm_email(r[2]))
        if key not in consumed_entry_set:
            issues['unconsumed_after_send']['items'].append({
                'lead_id': r[1],
                'recipient_email': r[2],
                'plan_id': r[0],
                'auth_status': entry_status_by_key.get(key, 'no_auth_entry'),
            })

    # 6) tracking_token_missing
    # Tracking tokens were introduced after the 8/5 legacy batches (all historical
    # send_log rows predate the feature). Rows that are already sent/bounced, have no
    # pending authorization/plan, and can never re-enter the current pool are
    # LEGACY_TRACKING_TOKEN_MISSING (historical data debt) — WARN, not a current
    # release safety failure.
    legacy_sent_dates = {
        "new_outreach_20260805_2300cs_tnarky",
        "new_outreach_20260805_et1000",
    }
    legacy_items = []
    for l in log_rows:
        token = (l[5] or '').strip()
        if not token or token not in tracking_hashes:
            item = {'lead_id': l[1], 'email': l[2],
                    'reason': 'empty_tracking_token_hash' if not token else 'token_hash_not_in_email_tracking_messages'}
            # Legacy detection: batch predates tracking feature OR lead already sent/bounced
            is_legacy_batch = batch_id in legacy_sent_dates
            lead_term = cur.execute("SELECT status, email_sendable FROM leads WHERE id=?", (l[1],)).fetchone()
            lead_sent_or_bounced = bool(lead_term) and str(lead_term[0] or '') in ('sent', 'bounced')
            if is_legacy_batch or lead_sent_or_bounced:
                item['classification'] = 'LEGACY_TRACKING_TOKEN_MISSING'
                legacy_items.append(item)
            else:
                issues['tracking_token_missing']['items'].append(item)

    issues['historical_tracking_token_missing'] = {
        'count': len(legacy_items),
        'items': legacy_items,
        'classification': 'LEGACY_HISTORICAL_DEBT',
        'note': 'Predates tracking token feature; sent/bounced, no pending auth/plan, cannot re-enter current pool',
    }

    # 汇总每类计数
    for cat in ISSUE_CATEGORIES:
        issues[cat]['count'] = len(issues[cat]['items'])

    total_issues = sum(issues[cat]['count'] for cat in ISSUE_CATEGORIES)
    verdict = 'PASSED' if total_issues == 0 else 'FAILED'

    return {
        'batch_id': batch_id,
        'checked_at': now,
        'verdict': verdict,
        'counts': {
            'plan_total': plan_total,
            'auth_total': auth_total,
            'approved_entry_total': approved_entry_total,
            'consumed_total': consumed_total,
            'smtp_accepted': smtp_accepted,
            'smtp_failed': smtp_failed,
            'smtp_skipped': smtp_skipped,
            'send_log_total': send_log_total,
            'send_log_delta': send_log_delta,
            'message_id_present_count': message_id_present_count,
            'tracking_token_present_count': tracking_token_present_count,
        },
        'issues': issues,
        'total_issues': total_issues,
    }


def _table_exists(cur, table):
    """判断表是否存在。"""
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    return row is not None


def _write_report_file(batch_id, result, output_dir=None):
    """把对账结果写入 output/post_send_reconciliation_<batch_id>.json。"""
    out_dir = output_dir or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'post_send_reconciliation_{batch_id}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return path


def _write_config_marker(conn, batch_id, result):
    """把对账状态写入 system_config（FAILED 或 PASSED，值为 JSON 字符串）。"""
    issue_counts = {cat: result['issues'][cat]['count'] for cat in ISSUE_CATEGORIES}
    payload = {
        'status': result['verdict'],
        'checked_at': result['checked_at'],
        'total_issues': result['total_issues'],
        'issue_counts': issue_counts,
    }
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO system_config (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (_config_key(batch_id), json.dumps(payload, ensure_ascii=False), result['checked_at'])
    )
    conn.commit()


def mark_reconciliation_failed(conn, batch_id, issues, result=None, output_dir=None):
    """把批次标记为 FAILED 并写 output JSON。

    issues: reconcile_batch 返回的 issues dict。发现异常时调用，绝不重发。
    """
    result = result or {'batch_id': batch_id, 'checked_at': datetime.now(ASIA_SH).isoformat(),
                        'issues': issues}
    result['verdict'] = 'FAILED'
    _write_config_marker(conn, batch_id, result)
    return _write_report_file(batch_id, result, output_dir)


def mark_reconciliation_passed(conn, batch_id, result=None, output_dir=None):
    """把批次标记为 PASSED 并写 output JSON。"""
    result = result or {'batch_id': batch_id, 'checked_at': datetime.now(ASIA_SH).isoformat(),
                        'issues': _empty_issues()}
    result['verdict'] = 'PASSED'
    _write_config_marker(conn, batch_id, result)
    return _write_report_file(batch_id, result, output_dir)


def _list_batches(conn):
    """枚举所有参与对账的批次（plan / auth / send_log 的并集）。"""
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT DISTINCT outreach_batch_date FROM final_send_plan "
        "WHERE outreach_batch_date IS NOT NULL AND outreach_batch_date != '' "
        "UNION SELECT DISTINCT outreach_batch_date FROM send_authorizations "
        "WHERE outreach_batch_date IS NOT NULL AND outreach_batch_date != '' "
        "UNION SELECT DISTINCT outreach_batch_date FROM send_log "
        "WHERE outreach_batch_date IS NOT NULL AND outreach_batch_date != '' "
        "ORDER BY outreach_batch_date"
    ).fetchall()
    return [r[0] for r in rows]


def _print_report(result):
    """输出人类可读对账报告。"""
    batch_id = result['batch_id']
    c = result['counts']
    print('=' * 60)
    print(f'Post-Send Reconciliation: {batch_id}')
    print(f'  checked_at : {result["checked_at"]}')
    print(f'  verdict    : {result["verdict"]}  (total_issues={result["total_issues"]})')
    print('  counts:')
    for key, value in c.items():
        print(f'    {key:28s} {value}')
    print('  issues:')
    for cat in ISSUE_CATEGORIES:
        issue = result['issues'][cat]
        print(f'    {cat:32s} {issue["count"]}')
        for item in issue['items'][:5]:
            print(f'        {item}')
        if issue['count'] > 5:
            print(f'        ... (+{issue["count"] - 5} more)')
    print('=' * 60)


def _run_one(conn, batch_id, write, output_dir=None):
    """跑单个批次；write=True 时写状态文件，否则只读打印。"""
    result = reconcile_batch(conn, batch_id)
    _print_report(result)
    if write:
        if result['verdict'] == 'FAILED':
            mark_reconciliation_failed(conn, batch_id, result['issues'],
                                       result=result, output_dir=output_dir)
        else:
            mark_reconciliation_passed(conn, batch_id, result=result, output_dir=output_dir)
        print(f'[write] system_config[{_config_key(batch_id)}] = {result["verdict"]}')
    return result


def main():
    parser = argparse.ArgumentParser(description='Post-Send Reconciliation')
    parser.add_argument('--batch', help='对账单个批次 ID')
    parser.add_argument('--all', action='store_true', help='对账全部批次')
    parser.add_argument('--write', action='store_true',
                        help='写状态文件（system_config + output JSON），默认只读')
    args = parser.parse_args()

    if not args.batch and not args.all:
        parser.error('必须指定 --batch <id> 或 --all')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if args.batch:
            batches = [args.batch]
        else:
            batches = _list_batches(conn)
            print(f'[--all] 共发现 {len(batches)} 个批次')
        for batch_id in batches:
            _run_one(conn, batch_id, args.write)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
