"""
result_recovery_sync.py -- 08:45 Asia/Shanghai 结果同步入口（Result Recovery Sync）
===================================================================================
用途：
  08:45 定时任务执行结果同步，为 09:00 Daily Results 提供"已同步结果"。

行为约定：
  - 幂等：重复运行只覆盖 system_config 中的同步状态 key，不做增量合并。
  - 只读 + 写状态：只读业务表、调用 bounce_pipeline 扫描、写 system_config 状态 key
    与结果摘要文件；绝不发送 SMTP、绝不重建 dashboard。
  - 单步失败不阻塞后续步骤：bounce_scan 失败不会阻止 reply_scan / unsubscribe_scan
    / tracking_sync。

步骤顺序（每步独立 try/except）：
  1) tracking_sync    本地对比 email_tracking_messages 与 send_log，统计 tracking 命中率。
  2) bounce_scan      调用 bounce_pipeline.run_scan_and_writeback()；若 import 失败则降级
                      读 system_config.last_bounce_scan_at 并标记该步失败。
  3) reply_scan       读 reply_log 最近扫描时间，更新 sync key last_reply_scan_at。
  4) unsubscribe_scan 统计 suppression_list 中 reason 含 unsubscribe 的记录数。
  最后写 sync_0845_last_success_at 与 sync_0845_steps(json) 到 system_config。

命令行：
  python result_recovery_sync.py         # 执行一次同步并打印结果摘要 json
  python result_recovery_sync.py --check # 只读输出上次同步状态（供 09:00 判断 DATA STALE）
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

# system_config 状态 key
SYNC_LAST_SUCCESS_KEY = "sync_0845_last_success_at"
SYNC_STEPS_KEY = "sync_0845_steps"
REPLY_SCAN_KEY = "last_reply_scan_at"

# 供 09:00 判断 DATA STALE 的阈值（分钟）
STALE_MINUTES = 90


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


def _set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO system_config (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                       updated_at = excluded.updated_at
        """,
        (key, value, now_cst().isoformat()),
    )


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
# 各同步步骤
# ---------------------------------------------------------------------------

def _step_tracking_sync(conn: sqlite3.Connection) -> dict:
    """本地对比 email_tracking_messages 与 send_log，统计 tracking 命中率。

    email_tracking_server 没有可复用的同步函数，因此做本地对比。
    匹配方式：token_hash 相等、send_log_id 关联、smtp_message_id 关联任一命中即算命中。
    """
    cur = conn.cursor()
    # 兼容旧 schema：send_log 可能没有 tracking_token_hash 列
    cols = {r[1] for r in cur.execute("PRAGMA table_info(send_log)")}
    has_token_col = "tracking_token_hash" in cols

    total = cur.execute(
        "SELECT COUNT(*) FROM email_tracking_messages WHERE token_hash IS NOT NULL"
    ).fetchone()[0]

    if total == 0:
        return {
            "ok": True,
            "data": {
                "total": 0,
                "matched": 0,
                "hit_rate": 0.0,
                "note": "no tracking messages",
            },
        }

    conds = []
    if has_token_col:
        conds.append("EXISTS (SELECT 1 FROM send_log s WHERE s.tracking_token_hash = t.token_hash)")
    conds.append("EXISTS (SELECT 1 FROM send_log s WHERE s.id = t.send_log_id)")
    conds.append("EXISTS (SELECT 1 FROM send_log s WHERE s.message_id = t.smtp_message_id)")

    matched = cur.execute(
        "SELECT COUNT(*) FROM email_tracking_messages t "
        "WHERE t.token_hash IS NOT NULL AND (" + " OR ".join(conds) + ")"
    ).fetchone()[0]

    hit_rate = round(matched / total * 100, 2) if total else 0.0
    return {
        "ok": True,
        "data": {
            "total": total,
            "matched": matched,
            "hit_rate": hit_rate,
            "matched_by_token": _count_token_match(cur) if has_token_col else 0,
            "matched_by_send_log_id": cur.execute(
                "SELECT COUNT(*) FROM email_tracking_messages t JOIN send_log s "
                "ON t.send_log_id IS NOT NULL AND t.send_log_id = s.id"
            ).fetchone()[0],
            "matched_by_smtp_message_id": cur.execute(
                "SELECT COUNT(*) FROM email_tracking_messages t JOIN send_log s "
                "ON t.smtp_message_id IS NOT NULL AND t.smtp_message_id = s.message_id"
            ).fetchone()[0],
        },
    }


def _count_token_match(cur: sqlite3.Cursor) -> int:
    """统计仅靠 token_hash 相等命中的 tracking 消息数。"""
    return cur.execute(
        "SELECT COUNT(*) FROM email_tracking_messages t JOIN send_log s "
        "ON s.tracking_token_hash = t.token_hash"
    ).fetchone()[0]


def _step_bounce_scan(conn: sqlite3.Connection) -> dict:
    """调用 bounce_pipeline.run_scan_and_writeback()。

    import 失败时降级读 system_config.last_bounce_scan_at 并标记该步失败；
    任何异常都不抛出，由上层记录到 sync_0845_steps 并继续后续步骤。
    """
    at = now_cst().isoformat()
    try:
        # 运行时 import，避免顶层依赖 bounce_pipeline
        from bounce_pipeline import run_scan_and_writeback
    except ImportError as exc:
        last_known = _get_config(conn, "last_bounce_scan_at")
        return {
            "ok": False,
            "at": at,
            "error": f"bounce_pipeline import failed: {exc}",
            "data": {"last_known_bounce_scan_at": last_known, "degraded": True},
        }
    try:
        summary = run_scan_and_writeback()
        return {"ok": True, "at": at, "data": summary}
    except Exception as exc:  # noqa: BLE001 单步失败不阻塞整体
        last_known = _get_config(conn, "last_bounce_scan_at")
        return {
            "ok": False,
            "at": at,
            "error": f"run_scan_and_writeback failed: {exc}",
            "data": {"last_known_bounce_scan_at": last_known},
        }


def _step_reply_scan(conn: sqlite3.Connection) -> dict:
    """查 reply_log 最近扫描时间（MAX processed_at 作为代理），更新 sync key。"""
    cur = conn.cursor()
    last_processed = cur.execute("SELECT MAX(processed_at) FROM reply_log").fetchone()[0]
    last_received = cur.execute("SELECT MAX(reply_received_at) FROM reply_log").fetchone()[0]
    total = cur.execute("SELECT COUNT(*) FROM reply_log").fetchone()[0]
    _set_config(conn, REPLY_SCAN_KEY, now_cst().isoformat())
    return {
        "ok": True,
        "at": now_cst().isoformat(),
        "data": {
            "total_replies": total,
            "last_processed_at": last_processed,
            "last_reply_received_at": last_received,
        },
    }


def _step_unsubscribe_scan(conn: sqlite3.Connection) -> dict:
    """统计 suppression_list 中 reason 含 unsubscribe 的记录数。"""
    cur = conn.cursor()
    unsubscribe_total = cur.execute(
        "SELECT COUNT(*) FROM suppression_list WHERE LOWER(reason) LIKE '%unsubscribe%'"
    ).fetchone()[0]
    total = cur.execute("SELECT COUNT(*) FROM suppression_list").fetchone()[0]
    return {
        "ok": True,
        "at": now_cst().isoformat(),
        "data": {"unsubscribe_total": unsubscribe_total, "suppression_total": total},
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def _write_summary_file(summary: dict) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"result_recovery_sync_{today_str()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    return path


def run_sync() -> dict:
    """执行完整同步：按顺序跑 4 步，写状态 key 与结果摘要文件，返回汇总 dict。"""
    conn = get_db()
    try:
        step_specs = [
            ("tracking_sync", _step_tracking_sync),
            ("bounce_scan", _step_bounce_scan),
            ("reply_scan", _step_reply_scan),
            ("unsubscribe_scan", _step_unsubscribe_scan),
        ]
        steps: dict = {}
        for name, fn in step_specs:
            try:
                result = fn(conn)
            except Exception as exc:  # noqa: BLE001 兜底，保证所有步骤都记录
                result = {"ok": False, "at": now_cst().isoformat(), "error": str(exc), "data": {}}
            steps[name] = result

        _set_config(conn, SYNC_STEPS_KEY, json.dumps(steps, ensure_ascii=False, default=str))
        _set_config(conn, SYNC_LAST_SUCCESS_KEY, now_cst().isoformat())
        conn.commit()

        summary = {
            "run_at": now_cst().isoformat(),
            "date": today_str(),
            "sync_0845_last_success_at": now_cst().isoformat(),
            "steps": steps,
            "all_ok": all(s.get("ok", False) for s in steps.values()),
        }
        _write_summary_file(summary)
        return summary
    finally:
        conn.close()


def read_sync_state() -> dict:
    """只读上次同步状态（供 09:00 判断 DATA STALE），不执行任何扫描。"""
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
        age = age_minutes(last_success)
        return {
            "checked_at": now_cst().isoformat(),
            "date": today_str(),
            "sync_0845_last_success_at": last_success,
            "age_minutes": age,
            "fresh": age is not None and age <= STALE_MINUTES,
            "data_stale": age is None or age > STALE_MINUTES,
            "steps": steps,
            "last_bounce_scan_at": _get_config(conn, "last_bounce_scan_at"),
            "last_reply_scan_at": _get_config(conn, REPLY_SCAN_KEY),
        }
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--check" in args:
        state = read_sync_state()
        print(json.dumps(state, ensure_ascii=False, indent=2, default=str))
        return 0

    summary = run_sync()
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
