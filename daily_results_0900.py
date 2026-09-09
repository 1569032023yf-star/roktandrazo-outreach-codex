"""
daily_results_0900.py -- 09:00 Daily Results 只读日报
======================================================
只读已同步结果（08:45 result_recovery_sync 写入的 system_config 状态），绝不自己扫描：
  - 不调用 bounce_pipeline / IMAP / tracking 扫描
  - 不发送 SMTP、不重建 dashboard
  - 仅读取 system_config 状态 key 与业务表，输出 markdown / json

告警规则（满足任一即进入告警模式）：
  - sync_0845_last_success_at 缺失或距今 > 90 分钟  -> DATA STALE
  - sync_0845_steps.bounce_scan.ok == False          -> BOUNCE SCAN FAILED
  - sync_0845_steps.reply_scan.ok == False           -> REPLY SCAN FAILED
  告警模式下 Bounce / Reply 一律显示 UNAVAILABLE，绝不显示 Bounce=0 / Reply=0。

命令行：
  python daily_results_0900.py        # 打印报告并写 output/daily_results_<date>.md
  python daily_results_0900.py --json # 额外输出 output/daily_results_<date>.json
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from bd_db import get_db

# Asia/Shanghai 固定 UTC+8（项目惯例，参考 _daily_collection_report.py）
CST = timezone(timedelta(hours=8))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

OUT_DIR = os.path.join(BASE_DIR, "output")

STALE_MINUTES = 90
SYNC_LAST_SUCCESS_KEY = "sync_0845_last_success_at"
SYNC_STEPS_KEY = "sync_0845_steps"
REPLY_SCAN_KEY = "last_reply_scan_at"

# bounce 分类展示顺序：key 对应 last_imap_scan_result 的字段
BOUNCE_CATEGORY_ORDER = [
    ("domain_invalid", "domain_invalid"),
    ("mailbox_invalid", "mailbox_invalid"),
    ("policy_bounce", "policy"),
    ("soft_bounce", "soft"),
    ("unmatched_dsn", "unmatched"),
]


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def now_cst() -> datetime:
    return datetime.now(CST)


def today_str() -> str:
    return now_cst().strftime("%Y-%m-%d")


def _get_config(conn: sqlite3.Connection, key: str) -> str | None:
    cur = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,))
    row = cur.fetchone()
    return row[0] if row else None


def _parse_time(value: str | None) -> datetime | None:
    """兼容 ISO8601（含时区）与 sqlite datetime('now') 两种格式。"""
    if not value:
        return None
    v = str(value).strip()
    try:
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        return datetime.fromisoformat(v)
    except ValueError:
        pass
    try:
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def age_minutes(value: str | None) -> float | None:
    """返回时间戳距今的分钟数；无法解析返回 None。"""
    t = _parse_time(value)
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=CST)
    return (now_cst() - t).total_seconds() / 60.0


# ---------------------------------------------------------------------------
# 状态读取（全部只读）
# ---------------------------------------------------------------------------

def _local_tracking_stats(cur: sqlite3.Cursor) -> dict:
    """本地只读兜底：统计 tracking 命中率（不扫描）。"""
    cols = {r[1] for r in cur.execute("PRAGMA table_info(send_log)")}
    has_token = "tracking_token_hash" in cols
    total = cur.execute(
        "SELECT COUNT(*) FROM email_tracking_messages WHERE token_hash IS NOT NULL"
    ).fetchone()[0]
    if total == 0:
        return {"total": 0, "matched": 0, "hit_rate": 0.0}
    conds = []
    if has_token:
        conds.append("EXISTS (SELECT 1 FROM send_log s WHERE s.tracking_token_hash = t.token_hash)")
    conds.append("EXISTS (SELECT 1 FROM send_log s WHERE s.id = t.send_log_id)")
    conds.append("EXISTS (SELECT 1 FROM send_log s WHERE s.message_id = t.smtp_message_id)")
    matched = cur.execute(
        "SELECT COUNT(*) FROM email_tracking_messages t "
        "WHERE t.token_hash IS NOT NULL AND (" + " OR ".join(conds) + ")"
    ).fetchone()[0]
    return {"total": total, "matched": matched, "hit_rate": round(matched / total * 100, 2)}


def _collect_metrics(conn: sqlite3.Connection, imap: dict | None,
                     steps: dict, last_send_date: str | None) -> dict:
    """从业务表读取指标（只读，不触发任何扫描）。"""
    cur = conn.cursor()

    # 昨日/最近发送数：优先 last_send_date，否则用昨天 Asia/Shanghai 日期
    send_date = last_send_date or (now_cst() - timedelta(days=1)).strftime("%Y-%m-%d")
    sends = cur.execute(
        "SELECT COUNT(*) FROM send_log WHERE sent_at LIKE ?", (send_date + "%",)
    ).fetchone()[0]

    # bounce 主来源：08:45 已同步的 last_imap_scan_result
    bounce_categories = {}
    if isinstance(imap, dict):
        for key, _label in BOUNCE_CATEGORY_ORDER:
            bounce_categories[key] = int(imap.get(key, 0))

    # 交叉核对：bounce_log 表分类统计
    bounce_log_by_type = {}
    for row in cur.execute("SELECT bounce_type, COUNT(*) AS n FROM bounce_log GROUP BY bounce_type"):
        bounce_log_by_type[row[0]] = row[1]
    bounce_log_total = cur.execute("SELECT COUNT(*) FROM bounce_log").fetchone()[0]

    reply_total = cur.execute("SELECT COUNT(*) FROM reply_log").fetchone()[0]
    reply_last = cur.execute("SELECT MAX(reply_received_at) FROM reply_log").fetchone()[0]

    unsubscribe_total = cur.execute(
        "SELECT COUNT(*) FROM suppression_list WHERE LOWER(reason) LIKE '%unsubscribe%'"
    ).fetchone()[0]

    # tracking 命中率：优先用 08:45 同步结果，缺失则本地只读兜底
    tracking = None
    ts = (steps or {}).get("tracking_sync") or {}
    if ts.get("ok", False) and isinstance(ts.get("data"), dict):
        tracking = ts["data"]
    if not tracking:
        tracking = _local_tracking_stats(cur)

    return {
        "send_date": send_date,
        "sends": sends,
        "bounce_categories": bounce_categories,
        "bounce_log_total": bounce_log_total,
        "bounce_log_by_type": bounce_log_by_type,
        "reply_total": reply_total,
        "reply_last_at": reply_last,
        "unsubscribe_total": unsubscribe_total,
        "tracking": tracking,
    }


def read_synced_state(conn: sqlite3.Connection | None = None) -> dict:
    """读取 system_config 同步状态与业务表指标（全部只读）。"""
    own = conn is None
    if conn is None:
        conn = get_db()
    try:
        last_success = _get_config(conn, SYNC_LAST_SUCCESS_KEY)
        steps_raw = _get_config(conn, SYNC_STEPS_KEY)
        steps = {}
        if steps_raw:
            try:
                steps = json.loads(steps_raw)
            except Exception:  # noqa: BLE001 json 损坏视为无状态
                steps = {}

        imap_raw = _get_config(conn, "last_imap_scan_result")
        imap = None
        if imap_raw:
            try:
                imap = json.loads(imap_raw)
            except Exception:  # noqa: BLE001 解析失败视为无数据
                imap = None

        age = age_minutes(last_success)
        return {
            "date": today_str(),
            "generated_at": now_cst().isoformat(),
            "sync_0845_last_success_at": last_success,
            "sync_age_minutes": age,
            "sync_stale": age is None or age > STALE_MINUTES,
            "steps": steps,
            "last_bounce_scan_at": _get_config(conn, "last_bounce_scan_at"),
            "last_imap_scan_result": imap,
            "last_reply_scan_at": _get_config(conn, REPLY_SCAN_KEY),
            "last_successful_sync_at": _get_config(conn, "last_successful_sync_at"),
            "last_send_date": _get_config(conn, "last_send_date"),
            "metrics": _collect_metrics(conn, imap, steps, _get_config(conn, "last_send_date")),
        }
    finally:
        if own:
            conn.close()


# ---------------------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------------------

def _metric_table_rows(state: dict, steps: dict) -> list[str]:
    """按指标可用性渲染 metric 表格行。

    规则：
      - 该指标对应 step 失败           -> UNAVAILABLE
      - 同步整体 stale                -> UNAVAILABLE (stale)
      - 其余情况显示真实值
    """
    m = state.get("metrics") or {}
    stale = state.get("sync_stale") or not state.get("sync_0845_last_success_at")
    bounce_ok = (steps.get("bounce_scan") or {}).get("ok", False)
    reply_ok = (steps.get("reply_scan") or {}).get("ok", False)

    bc = m.get("bounce_categories") or {}
    bl_types = m.get("bounce_log_by_type") or {}
    tracking = m.get("tracking") or {}
    t_total = tracking.get("total", 0)
    t_matched = tracking.get("matched", 0)
    t_rate = tracking.get("hit_rate")
    t_rate_s = f"{t_rate}%" if t_rate is not None else "n/a"

    rows: list[str] = []
    # Sends：send_log 直读，仅同步整体 stale 时置不可信
    if stale:
        rows.append(f"| Sends ({m.get('send_date', 'n/a')}) | UNAVAILABLE (stale) |")
    else:
        rows.append(f"| Sends ({m.get('send_date', 'n/a')}) | {m.get('sends', 0)} |")

    # Bounce
    if not bounce_ok:
        rows.append("| Bounce total | UNAVAILABLE |")
    elif stale:
        rows.append("| Bounce total | UNAVAILABLE (stale) |")
    else:
        rows.append(f"| Bounce total (imap scan) | {sum(bc.values())} |")
        for key, label in BOUNCE_CATEGORY_ORDER:
            rows.append(f"|  - {label} | {bc.get(key, 0)} |")
        rows.append(f"| Bounce total (bounce_log) | {m.get('bounce_log_total', 0)} |")
        if bl_types:
            rows.append(f"  bounce_log 分类: {json.dumps(bl_types, ensure_ascii=False)}")

    # Reply
    if not reply_ok:
        rows.append("| Replies | UNAVAILABLE |")
    elif stale:
        rows.append("| Replies | UNAVAILABLE (stale) |")
    else:
        rows.append(f"| Replies | {m.get('reply_total', 0)} |")

    # Unsubscribe / Tracking：同步整体 stale 时不可信
    if stale:
        rows.append("| Unsubscribes | UNAVAILABLE (stale) |")
        rows.append("| Tracking hit rate | UNAVAILABLE (stale) |")
    else:
        rows.append(f"| Unsubscribes | {m.get('unsubscribe_total', 0)} |")
        rows.append(f"| Tracking hit rate | {t_rate_s} ({t_matched}/{t_total}) |")
    return rows


def _render_header(state: dict) -> list[str]:
    return [
        f"# BD Daily Results -- {state.get('date', today_str())} 09:00 Asia/Shanghai",
        "",
        f"- Generated: {state.get('generated_at')}",
        "- Mode: read-only (uses 08:45 synced results)",
    ]


def _render_footer(state: dict) -> list[str]:
    return [
        "",
        f"*BD Daily Results -- read-only report | {state.get('generated_at')} Asia/Shanghai*",
    ]


def generate_report(state: dict) -> str:
    """根据同步状态生成 markdown 报告。"""
    steps = state.get("steps") or {}
    stale = state.get("sync_stale") or not state.get("sync_0845_last_success_at")
    # step 未记录（从未运行过 sync）不算"失败"，由 DATA STALE 覆盖；仅在明确失败时才报 FAILED
    bounce_step = steps.get("bounce_scan") or {}
    reply_step = steps.get("reply_scan") or {}
    bounce_failed = bool(bounce_step) and not bounce_step.get("ok", False)
    reply_failed = bool(reply_step) and not reply_step.get("ok", False)

    issues: list[str] = []
    if stale:
        issues.append("DATA STALE")
    if bounce_failed:
        issues.append("BOUNCE SCAN FAILED")
    if reply_failed:
        issues.append("REPLY SCAN FAILED")

    lines = _render_header(state)
    lines.append("")

    if not issues:
        # 正常模式
        lines.append("## Sync Status")
        lines.append("")
        lines.append(f"- Last successful sync: {state.get('sync_0845_last_success_at')}")
        lines.append(f"- Sync age: {state.get('sync_age_minutes')} min")
        for name in ("tracking_sync", "bounce_scan", "reply_scan", "unsubscribe_scan"):
            s = steps.get(name) or {}
            status = "OK" if s.get("ok", False) else ("FAILED: " + str(s.get("error")))
            lines.append(f"- {name}: {status}")
        lines.append("")
        lines.append("## Results")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.extend(_metric_table_rows(state, steps))
        lines.extend(_render_footer(state))
        return "\n".join(lines) + "\n"

    # 告警模式：大字警告 + LAST SUCCESSFUL SYNC + 失败信息 + 按指标可用性显示
    last_sync = state.get("sync_0845_last_success_at") or "NEVER"
    age = state.get("sync_age_minutes")
    if age is not None:
        last_sync_line = f"LAST SUCCESSFUL SYNC: {last_sync} ({age:.0f} min ago)"
    else:
        last_sync_line = f"LAST SUCCESSFUL SYNC: {last_sync}"

    lines.append("")
    lines.append(f"## !!! {' / '.join(issues)} !!!")
    lines.append("")
    lines.append(f"**{last_sync_line}**")
    lines.append("")
    if stale:
        lines.append("- 同步结果已超过 90 分钟未更新，以下指标不可信。")
    for name, label in (("bounce_scan", "Bounce"), ("reply_scan", "Reply")):
        step = steps.get(name) or {}
        if step and not step.get("ok", False):
            err = step.get("error") or "unknown error"
            lines.append(f"- {label} 数据不可用：{name} 失败 -> {err}")
        elif not step:
            lines.append(f"- {label} 数据不可用：{name} 未运行（无同步记录）")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.extend(_metric_table_rows(state, steps))
    lines.extend(_render_footer(state))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    want_json = "--json" in args

    state = read_synced_state()
    report = generate_report(state)
    print(report)

    os.makedirs(OUT_DIR, exist_ok=True)
    md_path = os.path.join(OUT_DIR, f"daily_results_{today_str()}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OK] Markdown: {md_path}")

    if want_json:
        payload = dict(state)
        payload["report"] = report
        json_path = os.path.join(OUT_DIR, f"daily_results_{today_str()}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        print(f"[OK] JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
