#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收件人当地发送窗口分批调度器（P0）。

生产政策（P2.3I 调整）：RECIPIENT_LOCAL_SEND_WINDOW = 08:00–11:10 local time，
allowed_weekdays=Mon-Fri。
按收件人 IANA 时区计算当地 08:00:00-11:10:59 发送窗口对应的 UTC 时刻，
实现分批发送（Eastern 先、Pacific 后）。

上海 23:00 单一 Outreach 通过该窗口覆盖美国大陆：
  ET ≈ 11:00   CT ≈ 10:00   MT ≈ 09:00   PT ≈ 08:00（均落在 08:00–11:10 内）。

本模块只读：dry_run_batch 绝不写库、绝不 SMTP。所有调度时间计算
强制使用 zoneinfo，自动处理 DST 切换。删时区 gate / send_window_override /
全天任意发送 / 新增四套时区 Scheduler / 修改其它安全门 均禁止——本文件
仅修改收件人当地窗口的起止时刻。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

PROJECT_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("WORKBUDDY_BD_DB_PATH") or str(PROJECT_DIR / "data" / "bd_leads.db")

# 生产政策常量（P2.3I）：收件人当地时间窗口 08:00:00–11:10:59。
# 仅改此窗口的起止时刻；时区 gate / DST / weekday 逻辑保持不变。
RECIPIENT_LOCAL_SEND_START_HOUR = 8
RECIPIENT_LOCAL_SEND_START_MIN = 0
RECIPIENT_LOCAL_SEND_END_HOUR = 11
RECIPIENT_LOCAL_SEND_END_MIN = 10

UTC = timezone.utc


def _as_utc(dt: datetime | None) -> datetime:
    """把 dt 归一化为带 UTC 时区的 aware datetime；默认取当前 UTC 时间。"""
    if dt is None:
        return datetime.now(UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def local_send_window_utc(tz_name: str, on_date: date | None = None) -> tuple[datetime, datetime]:
    """计算某时区某日当地 08:00:00 与 11:10:59 对应的 UTC 时刻（P2.3I 窗口）。

    必须用 zoneinfo 自动处理 DST（非夏令时/夏令时窗口会随偏移变化）。
    on_date 为收件人当地日历日；为 None 时取该时区当前本地日期。
    返回 (窗口起始 UTC 时刻, 窗口结束 UTC 时刻)，均带 UTC 时区。
    """
    tz = ZoneInfo(tz_name)
    if on_date is None:
        on_date = datetime.now(tz).date()
    start_local = datetime.combine(
        on_date,
        time(RECIPIENT_LOCAL_SEND_START_HOUR, RECIPIENT_LOCAL_SEND_START_MIN, 0),
        tzinfo=tz,
    )
    end_local = datetime.combine(
        on_date,
        time(RECIPIENT_LOCAL_SEND_END_HOUR, RECIPIENT_LOCAL_SEND_END_MIN, 59),
        tzinfo=tz,
    )
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def is_weekday_local(tz_name: str, dt_utc: datetime | None = None) -> bool:
    """把 dt_utc 转成该时区当地日期，判断是否为周一至周五（weekday 0-4）。"""
    dt_utc = _as_utc(dt_utc)
    local_date = dt_utc.astimezone(ZoneInfo(tz_name)).date()
    return local_date.weekday() < 5


def in_send_window(tz_name: str, now_utc: datetime | None = None) -> bool:
    """now 是否落在该时区当地 10:00:00-10:09:59 窗口内（含边界）。

    窗口按 now_utc 对应的该时区当地日期计算，保证传入固定时间时结果可复现。
    """
    now_utc = _as_utc(now_utc)
    on_date = now_utc.astimezone(ZoneInfo(tz_name)).date()
    start, end = local_send_window_utc(tz_name, on_date=on_date)
    return start <= now_utc <= end


def _flag_ok(value) -> bool:
    """sendable_for_automatic_schedule 是否视为可自动调度。0/None/空串 -> False。"""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() not in ("", "0", "false", "no")


def schedule_plan_entry(lead: dict, plan_entry: dict, now_utc: datetime | None = None) -> dict:
    """对单个 plan entry 计算调度信息。

    lead:       dict，须含 recipient_timezone / timezone_status / sendable_for_automatic_schedule。
    plan_entry: dict，final_send_plan 行（含 lead_id / recipient_email / outreach_batch_date）。

    返回：
      {
        lead_id, recipient_email,
        recipient_timezone,           # IANA 时区或 None
        scheduled_local_time,         # ISO 当地（含 tz 名，如 2026-08-07T10:00:00-04:00[America/New_York]）
        scheduled_utc_time,           # ISO UTC（窗口起始）
        sendable: bool,
        block_reason: str | None,
      }

    sendable=False 条件：recipient_timezone 空或不在 zoneinfo.available_timezones()、
    timezone_status='TIMEZONE_UNRESOLVED'、sendable_for_automatic_schedule=0、
    今天非收件人当地工作日。窗口按 now_utc 所在当地日期计算。
    """
    now_utc = _as_utc(now_utc)
    tz = (lead.get("recipient_timezone") or "").strip()
    tz_status = str(lead.get("timezone_status") or "")
    entry: dict = {
        "lead_id": plan_entry.get("lead_id"),
        "recipient_email": plan_entry.get("recipient_email"),
        "recipient_timezone": tz or None,
        "scheduled_local_time": None,
        "scheduled_utc_time": None,
        "sendable": False,
        "block_reason": None,
    }

    reason: str | None = None
    if not tz:
        reason = "no_recipient_timezone"
    elif tz not in available_timezones():
        reason = f"invalid_timezone:{tz}"
    elif tz_status == "TIMEZONE_UNRESOLVED":
        reason = "TIMEZONE_UNRESOLVED"
    elif not _flag_ok(lead.get("sendable_for_automatic_schedule")):
        reason = "not_sendable_for_automatic_schedule"
    elif not is_weekday_local(tz, now_utc):
        reason = "not_weekday_local"

    # 时区有效即计算窗口时刻（即使因工作日等原因不发送，也便于 dry-run 展示）
    if tz and tz in available_timezones():
        on_date = now_utc.astimezone(ZoneInfo(tz)).date()
        start, _end = local_send_window_utc(tz, on_date=on_date)
        local_start = start.astimezone(ZoneInfo(tz))
        entry["scheduled_local_time"] = f"{local_start.isoformat()}[{tz}]"
        entry["scheduled_utc_time"] = start.isoformat()

    entry["sendable"] = reason is None
    entry["block_reason"] = reason
    return entry


def group_entries_by_timezone(plan_rows: list[dict]) -> dict[str, list]:
    """把已调度 entries 按 IANA 时区分组。

    plan_rows: schedule_plan_entry 的返回 dict 列表。
    返回 {tz_name: [entry, ...]}，组内按 scheduled_utc_time 升序排序。
    同组条目共享同一发送窗口，组内任意条目的 scheduled_utc_time 即该组
    当地 10:00 对应的 UTC 时刻（"每组标注"的体现）。
    """
    groups: dict[str, list] = {}
    for e in plan_rows:
        tz = e.get("recipient_timezone")
        if not tz:
            continue
        groups.setdefault(tz, []).append(e)
    for items in groups.values():
        items.sort(key=lambda x: x.get("scheduled_utc_time") or "")
    return groups


def dry_run_batch(conn: sqlite3.Connection, batch_id: str, now_utc: datetime | None = None) -> dict:
    """读 final_send_plan 中该 batch 的 planned 行，逐条调度并汇总。

    只读：绝不写库、绝不 SMTP。
    now_utc 用于模拟某天（配合 --simulate-date）。

    返回 dict：
      {
        batch_id, total, timezone_distribution: {tz: count},
        entries: [schedule_plan_entry 结果...],
        sendable_count, blocked_count, blocked_reasons: {reason: count},
        send_order_suggestion: [{timezone, count, window_utc_start}...]（UTC 最早->最晚）
      }
    """
    now_utc = _as_utc(now_utc)
    rows = conn.execute(
        "SELECT * FROM final_send_plan WHERE outreach_batch_date=? AND status='planned' "
        "ORDER BY planned_sequence",
        (batch_id,),
    ).fetchall()
    lead_ids = [r["lead_id"] for r in rows]
    leads: dict = {}
    if lead_ids:
        ph = ",".join("?" for _ in lead_ids)
        for lr in conn.execute(f"SELECT * FROM leads WHERE id IN ({ph})", lead_ids).fetchall():
            leads[lr["id"]] = lr

    entries = []
    for row in rows:
        lead = leads.get(row["lead_id"])
        entries.append(schedule_plan_entry(dict(lead) if lead else {}, dict(row), now_utc=now_utc))

    timezone_distribution: dict = {}
    for e in entries:
        tz = e["recipient_timezone"]
        timezone_distribution[tz] = timezone_distribution.get(tz, 0) + 1

    # 发送顺序建议：按组窗口 UTC 起始最早->最晚（Eastern 先、Pacific 后）
    groups = group_entries_by_timezone(entries)
    send_order = []
    for tz, items in groups.items():
        starts = [e["scheduled_utc_time"] for e in items if e["scheduled_utc_time"]]
        send_order.append({
            "timezone": tz,
            "count": len(items),
            "window_utc_start": min(starts) if starts else None,
        })
    send_order.sort(key=lambda x: x["window_utc_start"] or "")

    blocked_reasons: dict = {}
    for e in entries:
        if not e["sendable"]:
            r = e["block_reason"] or "unknown"
            blocked_reasons[r] = blocked_reasons.get(r, 0) + 1

    return {
        "batch_id": batch_id,
        "total": len(entries),
        "timezone_distribution": timezone_distribution,
        "entries": entries,
        "sendable_count": sum(1 for e in entries if e["sendable"]),
        "blocked_count": sum(1 for e in entries if not e["sendable"]),
        "blocked_reasons": blocked_reasons,
        "send_order_suggestion": send_order,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI：--batch <id> dry-run；--simulate-date <YYYY-MM-DD> 模拟某天的调度。"""
    parser = argparse.ArgumentParser(description="收件人当地 10:00 分批调度 dry-run（只读）")
    parser.add_argument("--batch", required=True, help="batch id")
    parser.add_argument("--db", default=DB_PATH, help="sqlite db 路径")
    parser.add_argument("--simulate-date", default=None, help="模拟某天的调度，格式 YYYY-MM-DD")
    args = parser.parse_args(argv)

    now_utc = None
    if args.simulate_date:
        sim = date.fromisoformat(args.simulate_date)
        now_utc = datetime.combine(sim, time(12, 0, 0), tzinfo=UTC)  # 模拟当日中午 UTC

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        result = dry_run_batch(conn, args.batch, now_utc=now_utc)
    finally:
        conn.close()

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
