#!/usr/bin/env python3
"""
Daily Report Generator — Roktandrazo BD Outreach
Generates a report for the day's sending, pool status, and recommendations.
Can run standalone or be called by daily_session.py.

Usage:
    python agent_daily_report.py                    # Normal report
    python agent_daily_report.py --date 2026-06-25  # Specific date
    python agent_daily_report.py --dry-run           # Dry-run marker
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bd_db import get_db, get_config

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(OUT_DIR, exist_ok=True)

DAILY_TARGET = 20


def generate_report(report_date: str = None, dry_run: bool = False) -> str:
    """Generate the daily report and return the file path."""
    if report_date is None:
        report_date = datetime.now().strftime('%Y-%m-%d')

    report_path = os.path.join(OUT_DIR, f'daily_report_{report_date}.md')
    conn = get_db()
    c = conn.cursor()

    # --- Today's sending ---
    today_sent = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE status='sent' AND date(sent_at) = ?",
        (report_date,)
    ).fetchone()[0]

    today_failed = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE status IN ('failed','error') AND date(sent_at) = ?",
        (report_date,)
    ).fetchone()[0]

    today_bounced = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE status='bounced' AND date(sent_at) = ?",
        (report_date,)
    ).fetchone()[0]

    # --- Batch breakdown ---
    batch_labels = ['08:40-09:00', '09:30-09:50', '10:20-10:40', '11:10-11:30']
    batch_info = []
    for bl in batch_labels:
        # Approximate: log entries in time ranges
        start_h, start_m = bl.split('-')[0].split(':')
        end_h, end_m = bl.split('-')[1].split(':')
        # Simple: count total sent on this date — we don't have batch granularity in DB
        pass

    # --- Bounce breakdown ---
    hard_bounces = c.execute(
        "SELECT COUNT(*) FROM bounce_log WHERE bounce_type='hard' AND date(bounce_received_at) = ?",
        (report_date,)
    ).fetchone()[0]
    policy_bounces = c.execute(
        "SELECT COUNT(*) FROM bounce_log WHERE bounce_type='policy' AND date(bounce_received_at) = ?",
        (report_date,)
    ).fetchone()[0]

    # --- Replies ---
    replies = c.execute(
        "SELECT COUNT(*) FROM reply_log WHERE date(reply_received_at) = ?",
        (report_date,)
    ).fetchone()[0]

    # --- Unsubscribes ---
    unsubscribes = c.execute(
        "SELECT COUNT(*) FROM suppression_list WHERE reason='unsubscribed' AND date(added_at) = ?",
        (report_date,)
    ).fetchone()[0]

    # --- Pool status ---
    a0_count = c.execute("""SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page')
        AND email IS NOT NULL AND email != ''""").fetchone()[0]

    a1_count = c.execute("""SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email IS NOT NULL AND email != ''
        AND mx_provider LIKE '%exchange%'""").fetchone()[0]

    ams_count = c.execute(
        "SELECT COUNT(*) FROM leads WHERE status='approved_manual_send'"
    ).fetchone()[0]

    b_count = c.execute(
        "SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='B' AND email IS NOT NULL AND email != ''"
    ).fetchone()[0]

    c_count = c.execute(
        "SELECT COUNT(*) FROM leads WHERE status='contact_form_pool' OR (status='new' AND (email IS NULL OR email='') AND contact_form_url IS NOT NULL AND contact_form_url != '')"
    ).fetchone()[0]

    # --- Config ---
    send_pause = get_config('send_pause') or 'true'
    pause_reason = get_config('pause_reason') or '-'
    daily_target = int(get_config('daily_run_target') or get_config('daily_send_target') or DAILY_TARGET)
    run_status = get_config('daily_run_status') or ('completed' if today_sent >= daily_target else 'underfilled')
    root_cause = get_config('root_cause') or ''
    actual = int(get_config('daily_run_actual') or today_sent)
    gap = max(0, daily_target - actual)
    next_window_needed = int(get_config('next_window_needed_count') or gap)
    recovery_pending = get_config('recovery_pending') or 'false'

    conn.close()

    # --- Write report ---
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# BD Daily Report — {report_date}\n\n")
        if dry_run:
            f.write(f"> **DRY RUN** — no real emails were sent\n\n")
        f.write("---\n\n")

        # Sending summary
        f.write("## [发送摘要]\n\n")
        f.write(f"| 指标 | 数值 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 当天目标 | {daily_target} |\n")
        f.write(f"| 实际发送 | {today_sent} |\n")
        f.write(f"| 缺口 | {gap} |\n")
        f.write(f"| 状态 | {run_status} |\n")
        f.write(f"| 发送失败 | {today_failed} |\n")
        f.write(f"| 退信 | {today_bounced} |\n")
        f.write(f"| 完成率 | {today_sent / daily_target * 100:.0f}% |\n")
        f.write(f"| 根因 | {root_cause or '-'} |\n\n")

        # Delivery
        f.write("## [送达状态]\n\n")
        f.write(f"| 类型 | 数量 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 成功送达 | {today_sent} |\n")
        f.write(f"| Hard Bounce | {hard_bounces} |\n")
        f.write(f"| Policy Bounce | {policy_bounces} |\n")
        if hard_bounces > 0 or policy_bounces > 0:
            f.write("\n  **Bounce触发批暂停**\n\n")

        # Replies
        f.write("\n## [回复摘要]\n\n")
        f.write(f"| 类型 | 数量 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 新回复 | {replies} |\n")
        f.write(f"| 自动回复 | 0 (需IMAP扫描) |\n")
        f.write(f"| 退订 | {unsubscribes} |\n\n")

        # Pool status
        f.write("## [池剩余]\n\n")
        f.write(f"| 池 | 数量 | 说明 |\n")
        f.write(f"|---|------|------|\n")
        f.write(f"| A0 (可发) | {a0_count} | 已验证邮箱，非Exchange |\n")
        f.write(f"| A1 (Exchange) | {a1_count} | 已验证邮箱，Exchange MX，高风险 |\n")
        f.write(f"| approved_manual | {ams_count} | 人工确认邮箱 |\n")
        f.write(f"| B (需人工确认) | {b_count} | 猜测邮箱，需在CSV中补充 |\n")
        f.write(f"| C (contact form) | {c_count} | 仅contact form |\n\n")

        # Tomorrow readiness
        tomorrow_sendable = a0_count + ams_count
        f.write("## [明日可发准备度]\n\n")
        f.write(f"| 指标 | 数值 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 明日可发库存 | {tomorrow_sendable} |\n")
        f.write(f"| 明日目标 | {daily_target} |\n")
        f.write(f"| 明日缺口 | {max(0, daily_target - tomorrow_sendable)} |\n")
        f.write(f"| next_window_needed_count | {next_window_needed} |\n")
        f.write(f"| recovery_pending | {recovery_pending} |\n\n")

        # Pause state
        f.write("## [暂停状态]\n\n")
        f.write(f"| 项 | 值 |\n")
        f.write(f"|----|----|\n")
        f.write(f"| send_pause | {send_pause} |\n")
        f.write(f"| pause_reason | {pause_reason} |\n\n")

        # Anomalies
        f.write("## [违规/异常]\n\n")
        anomalies = []
        if hard_bounces > 0:
            anomalies.append(f"Hard bounce ({hard_bounces}) — 已自动加入 suppression")
        if policy_bounces > 0:
            anomalies.append(f"Policy bounce ({policy_bounces}) — 建议检查发信认证")
        if unsubscribes > 0:
            anomalies.append(f"退订 ({unsubscribes}) — 已加入 suppression")
        if today_failed > 3:
            anomalies.append(f"高失败率 ({today_failed}/{today_sent + today_failed})")
        if run_status == 'paused':
            anomalies.append(f"发送暂停: {pause_reason}")
        if today_sent < daily_target:
            anomalies.append(f"未完成目标 (sent {today_sent}/{daily_target})")

        if not anomalies:
            f.write("  无异常\n\n")
        else:
            for a in anomalies:
                f.write(f"  * {a}\n")
            f.write("\n")

        # Suggestions
        f.write("## [建议]\n\n")
        suggestions = []
        if a0_count + ams_count < daily_target:
            suggestions.append(f"A0+approved_manual 仅剩 {a0_count + ams_count} 条，建议先运行 Browser Verification 清洗 B 池")
        if b_count > 0:
            suggestions.append(f"B 池有 {b_count} 条待浏览器验证，不建议直接交给人工全量确认")
        if send_pause == 'true':
            suggestions.append("send_pause 仍为 true — 如需发送请先解除")
        if run_status == 'underfilled':
            suggestions.append(f"今日状态 underfilled，缺口 {gap} 封，需进入 recovery 或 next window")
        suggestions.append("下一个 operator window: 明天 08:30-12:00")

        for s in suggestions:
            f.write(f"  * {s}\n")
        f.write("\n")

        # Footer
        f.write("---\n")
        f.write(f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    print(f"[REPORT] Saved: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description='BD Daily Report')
    parser.add_argument('--date', help='Report date (YYYY-MM-DD), default: today')
    parser.add_argument('--dry-run', action='store_true', help='Mark report as dry run')
    args = parser.parse_args()

    generate_report(report_date=args.date, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
