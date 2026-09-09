# -*- coding: utf-8 -*-
"""收件人时区解析器（P0）。

根据 lead 的 city / state 解析出 IANA 时区，用于按收件人当地时间 10:00 发送。

规则：
- 单一时区州：查 STATE_DEFAULT_TZ。
- 跨时区州（TN/KY/FL/MI/IN/SD/ND/NE/KS/ID/AK/AZ）：必须城市级解析，
  命中 CITY_TZ_OVERRIDES 才解析成功，否则 TIMEZONE_UNRESOLVED。
- 不使用 CST/EST 缩写，不写死 UTC 偏移，全部用 IANA 时区名。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

# 单一时区州的 IANA 默认时区。
# 注意：TN/KY/FL/MI/IN/SD/ND/NE/KS/ID/AK/AZ 为跨时区州，不在此 dict。
STATE_DEFAULT_TZ: dict[str, str] = {
    # Eastern
    "NY": "America/New_York",
    "MA": "America/New_York",
    "PA": "America/New_York",
    "GA": "America/New_York",
    "NC": "America/New_York",
    "SC": "America/New_York",
    "VA": "America/New_York",
    "MD": "America/New_York",
    "DE": "America/New_York",
    "NJ": "America/New_York",
    "CT": "America/New_York",
    "RI": "America/New_York",
    "NH": "America/New_York",
    "VT": "America/New_York",
    "ME": "America/New_York",
    "WV": "America/New_York",
    "OH": "America/New_York",
    # Central
    "TX": "America/Chicago",
    "MN": "America/Chicago",
    "WI": "America/Chicago",
    "IL": "America/Chicago",
    "MO": "America/Chicago",
    "AR": "America/Chicago",
    "LA": "America/Chicago",
    "MS": "America/Chicago",
    "AL": "America/Chicago",
    "OK": "America/Chicago",
    "IA": "America/Chicago",
    # Mountain
    "CO": "America/Denver",
    "UT": "America/Denver",
    "NM": "America/Denver",
    "MT": "America/Denver",
    "WY": "America/Denver",
    # Pacific
    "CA": "America/Los_Angeles",
    "WA": "America/Los_Angeles",
    "OR": "America/Los_Angeles",
    "NV": "America/Los_Angeles",
    # 其他单一时区州
    "HI": "Pacific/Honolulu",
}

# 跨时区州：必须城市级解析，不能回落州级默认。
SPLIT_TZ_STATES: set = {
    "TN", "KY", "FL", "MI", "IN", "SD", "ND", "NE", "KS", "ID", "AK", "AZ",
}

# 跨时区州的城市级精确映射：(city, state) -> IANA 时区。
# city 统一用 Title Case，state 统一大写；resolve_timezone 内部会做同样的规范化。
CITY_TZ_OVERRIDES: dict[tuple[str, str], str] = {
    # ---- TN：中部（Central）----
    ("Nashville", "TN"): "America/Chicago",
    ("Memphis", "TN"): "America/Chicago",
    ("Jackson", "TN"): "America/Chicago",
    ("Clarksville", "TN"): "America/Chicago",
    ("Franklin", "TN"): "America/Chicago",
    ("Murfreesboro", "TN"): "America/Chicago",
    ("Brentwood", "TN"): "America/Chicago",
    ("Hendersonville", "TN"): "America/Chicago",
    ("Bartlett", "TN"): "America/Chicago",
    ("Collierville", "TN"): "America/Chicago",
    ("Germantown", "TN"): "America/Chicago",
    ("Spring Hill", "TN"): "America/Chicago",
    ("Gallatin", "TN"): "America/Chicago",
    ("Smyrna", "TN"): "America/Chicago",
    ("Columbia", "TN"): "America/Chicago",
    ("Lebanon", "TN"): "America/Chicago",
    ("Cookeville", "TN"): "America/Chicago",
    ("Tullahoma", "TN"): "America/Chicago",
    ("McMinnville", "TN"): "America/Chicago",
    ("Shelbyville", "TN"): "America/Chicago",
    ("Dickson", "TN"): "America/Chicago",
    ("Hermitage", "TN"): "America/Chicago",
    ("Springfield", "TN"): "America/Chicago",
    ("Madison", "TN"): "America/Chicago",
    ("Mount Juliet", "TN"): "America/Chicago",
    # 项目库中真实出现的补充城市（西/中 TN）
    ("Millington", "TN"): "America/Chicago",
    ("Shiloh", "TN"): "America/Chicago",
    ("Fayetteville", "TN"): "America/Chicago",
    # ---- TN：东部（Eastern）----
    ("Knoxville", "TN"): "America/New_York",
    ("Chattanooga", "TN"): "America/New_York",
    ("Johnson City", "TN"): "America/New_York",
    ("Kingsport", "TN"): "America/New_York",
    ("Bristol", "TN"): "America/New_York",
    ("Cleveland", "TN"): "America/New_York",
    ("Oak Ridge", "TN"): "America/New_York",
    ("Alcoa", "TN"): "America/New_York",
    ("Maryville", "TN"): "America/New_York",
    ("Morristown", "TN"): "America/New_York",
    ("Greeneville", "TN"): "America/New_York",
    ("Elizabethton", "TN"): "America/New_York",
    ("Sevierville", "TN"): "America/New_York",
    ("Pigeon Forge", "TN"): "America/New_York",
    ("Gatlinburg", "TN"): "America/New_York",
    ("Clinton", "TN"): "America/New_York",
    # 项目库中真实出现的补充城市（东 TN）
    ("Vonore", "TN"): "America/New_York",
    # ---- KY：东部（Eastern）----
    ("Louisville", "KY"): "America/New_York",
    ("Lexington", "KY"): "America/New_York",
    ("Florence", "KY"): "America/New_York",
    ("Elizabethtown", "KY"): "America/New_York",
    ("Richmond", "KY"): "America/New_York",
    ("Frankfort", "KY"): "America/New_York",
    ("Covington", "KY"): "America/New_York",
    ("Georgetown", "KY"): "America/New_York",
    # 项目库中真实出现的补充城市（东/中 KY）
    ("Somerset", "KY"): "America/New_York",
    ("Salyersville", "KY"): "America/New_York",
    ("Radcliff", "KY"): "America/New_York",
    ("Middlesboro", "KY"): "America/New_York",
    ("La Grange", "KY"): "America/New_York",
    ("Danville", "KY"): "America/New_York",
    ("Shelbyville", "KY"): "America/New_York",
    # ---- KY：中部（Central）----
    ("Paducah", "KY"): "America/Chicago",
    ("Owensboro", "KY"): "America/Chicago",
    ("Bowling Green", "KY"): "America/Chicago",
    ("Hopkinsville", "KY"): "America/Chicago",
    ("Murray", "KY"): "America/Chicago",
    ("Henderson", "KY"): "America/Chicago",
    # 项目库中真实出现的补充城市（西 KY）
    ("Smiths Grove", "KY"): "America/Chicago",
    ("Princeton", "KY"): "America/Chicago",
    ("Mammoth Cave", "KY"): "America/Chicago",
    # ---- FL：东部（Eastern，大部分州）----
    ("Miami", "FL"): "America/New_York",
    ("Orlando", "FL"): "America/New_York",
    ("Jacksonville", "FL"): "America/New_York",
    ("Tampa", "FL"): "America/New_York",
    ("Gainesville", "FL"): "America/New_York",
    ("Tallahassee", "FL"): "America/New_York",
    # 项目库中真实出现的补充城市（FL 东部）
    ("Sarasota", "FL"): "America/New_York",
    ("Vero Beach", "FL"): "America/New_York",
    ("St. Augustine", "FL"): "America/New_York",
    ("Naples", "FL"): "America/New_York",
    ("Maitland", "FL"): "America/New_York",
    ("Kissimmee", "FL"): "America/New_York",
    ("Fort Myers", "FL"): "America/New_York",
    ("Fort Lauderdale", "FL"): "America/New_York",
    ("Clearwater", "FL"): "America/New_York",
    # ---- FL：中部（Central，狭长地带）----
    ("Pensacola", "FL"): "America/Chicago",
    ("Panama City", "FL"): "America/Chicago",
    ("Destin", "FL"): "America/Chicago",
    # ---- MI：东部（Eastern，下半岛为主）----
    ("Detroit", "MI"): "America/New_York",
    ("Grand Rapids", "MI"): "America/New_York",
    ("Ann Arbor", "MI"): "America/New_York",
    # 项目库中真实出现的补充城市（MI 下半岛）
    ("Warren", "MI"): "America/New_York",
    ("Traverse City", "MI"): "America/New_York",
    ("Petoskey", "MI"): "America/New_York",
    ("Livonia", "MI"): "America/New_York",
    ("Lansing", "MI"): "America/New_York",
    ("Kalamazoo", "MI"): "America/New_York",
    ("Farmington Hills", "MI"): "America/New_York",
    # ---- MI：中部（Central，上半岛）----
    ("Marquette", "MI"): "America/Chicago",
    ("Sault Ste Marie", "MI"): "America/Chicago",
    # ---- IN：东部（Eastern）----
    ("Indianapolis", "IN"): "America/New_York",
    ("Fort Wayne", "IN"): "America/New_York",
    ("Bloomington", "IN"): "America/New_York",
    ("South Bend", "IN"): "America/New_York",
    # 项目库中真实出现的补充城市（IN 中部）
    ("Nashville", "IN"): "America/New_York",
    # ---- IN：中部（Central）----
    ("Evansville", "IN"): "America/Chicago",
    # ---- NE（跨时区州，数据中出现的城市）----
    ("Omaha", "NE"): "America/Chicago",
    # ---- KS（跨时区州，数据中出现的城市）----
    ("Prairie Village", "KS"): "America/Chicago",
    # ---- ID（跨时区州，数据中出现的城市，均在南 Idaho）----
    ("Boise", "ID"): "America/Denver",
    ("Meridian", "ID"): "America/Denver",
    # ---- AZ：大部分无 DST，IANA 统一用 America/Phoenix ----
    ("Tempe", "AZ"): "America/Phoenix",
    ("Phoenix", "AZ"): "America/Phoenix",
    ("Tucson", "AZ"): "America/Phoenix",
    ("Scottsdale", "AZ"): "America/Phoenix",
    ("Mesa", "AZ"): "America/Phoenix",
    ("Grand Canyon Village", "AZ"): "America/Phoenix",
}

# 被排除的状态：已发送 / 已退信 / 拒绝联系。
EXCLUDED_STATUSES: tuple[str, ...] = ("sent", "bounced", "do_not_contact")

RESOLVED = "RESOLVED"
UNRESOLVED = "TIMEZONE_UNRESOLVED"

# 生产库相对路径（相对本脚本所在目录）。
DB_PATH = str(Path(__file__).resolve().parent / "data" / "bd_leads.db")


def _normalize_city(city: str | None) -> str:
    """规范化城市名：去首尾空格、压缩多余空格、转 Title Case。"""
    if not city:
        return ""
    return " ".join(str(city).strip().split()).title()


def _normalize_state(state: str | None) -> str:
    """规范化州代码：去空格、转大写。"""
    if not state:
        return ""
    return str(state).strip().upper()


def resolve_timezone(
    city: str | None, state: str | None, zip_code: str | None = None
) -> tuple[str | None, str]:
    """解析 (city, state) 的 IANA 时区。

    优先级：CITY_TZ_OVERRIDES -> STATE_DEFAULT_TZ -> TIMEZONE_UNRESOLVED。
    跨时区州（SPLIT_TZ_STATES）不在 STATE_DEFAULT_TZ 中，城市未命中 override
    时必然返回 TIMEZONE_UNRESOLVED，不会错误回落州级默认。

    返回 (iana_tz, status)，status 取 RESOLVED 或 TIMEZONE_UNRESOLVED。
    zip_code 预留，当前数据表无该列。
    """
    norm_city = _normalize_city(city)
    norm_state = _normalize_state(state)
    if not norm_state:
        return None, UNRESOLVED
    # 城市为空时无法精确解析（即使是单时区州也保守返回 UNRESOLVED）
    if not norm_city:
        return None, UNRESOLVED
    override = CITY_TZ_OVERRIDES.get((norm_city, norm_state))
    if override is not None:
        return override, RESOLVED
    default_tz = STATE_DEFAULT_TZ.get(norm_state)
    if default_tz is not None:
        return default_tz, RESOLVED
    return None, UNRESOLVED


def apply_timezone_to_leads(
    conn: sqlite3.Connection, dry_run: bool = False, state_filter: str | None = None
) -> dict:
    """扫描可发送线索并逐行解析时区，更新 recipient_timezone 等字段。

    只处理 status NOT IN (sent/bounced/do_not_contact) 且 email 非空的行。
    RESOLVED  -> sendable_for_automatic_schedule = 1
    UNRESOLVED -> sendable_for_automatic_schedule = 0
    dry_run=True 时只统计不写库。

    返回统计 dict：{resolved, unresolved, skipped, unresolved_examples}。
    """
    stats = {
        "resolved": 0,
        "unresolved": 0,
        "skipped": 0,
        "unresolved_examples": [],
    }
    placeholders = ",".join("?" for _ in EXCLUDED_STATUSES)
    # 状态范围内所有行（含 email 为空的行），用于计算 skipped
    count_sql = (
        "SELECT COUNT(*) FROM leads WHERE status NOT IN ({})".format(placeholders)
    )
    count_params: list = list(EXCLUDED_STATUSES)
    scan_sql = (
        "SELECT id, store_name, city, state FROM leads "
        "WHERE status NOT IN ({}) AND email IS NOT NULL AND TRIM(email) != ''".format(
            placeholders
        )
    )
    scan_params: list = list(EXCLUDED_STATUSES)
    if state_filter:
        count_sql += " AND UPPER(TRIM(state)) = ?"
        scan_sql += " AND UPPER(TRIM(state)) = ?"
        norm_state = state_filter.strip().upper()
        count_params.append(norm_state)
        scan_params.append(norm_state)

    total_in_scope = conn.execute(count_sql, count_params).fetchone()[0]
    rows = conn.execute(scan_sql, scan_params).fetchall()
    stats["skipped"] = total_in_scope - len(rows)

    updates: list[tuple] = []
    for lead_id, store_name, city, state in rows:
        tz, status = resolve_timezone(city, state)
        sendable = 1 if status == RESOLVED else 0
        if status == RESOLVED:
            stats["resolved"] += 1
        else:
            stats["unresolved"] += 1
            if len(stats["unresolved_examples"]) < 10:
                stats["unresolved_examples"].append(store_name or "(no store name)")
        updates.append((tz, status, sendable, lead_id))

    if not dry_run and updates:
        conn.executemany(
            "UPDATE leads SET recipient_timezone=?, timezone_status=?, "
            "sendable_for_automatic_schedule=? WHERE id=?",
            updates,
        )
        conn.commit()
    return stats


def _print_stats(label: str, stats: dict) -> None:
    """打印一组统计。"""
    print("==" + label + "==")
    print("resolved:   {}".format(stats["resolved"]))
    print("unresolved: {}".format(stats["unresolved"]))
    print("skipped:    {}".format(stats["skipped"]))
    if stats["unresolved_examples"]:
        print("unresolved_examples:")
        for name in stats["unresolved_examples"]:
            print("  - " + name)


def main() -> None:
    parser = argparse.ArgumentParser(description="收件人时区解析器（P0）")
    parser.add_argument("--apply", action="store_true", help="写库（默认不写库）")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    parser.add_argument("--state", default=None, help="只看某州，如 --state TN")
    args = parser.parse_args()

    if args.apply and args.dry_run:
        parser.error("--apply 与 --dry-run 不能同时使用")

    # 默认不写库：只有显式 --apply 才会写库
    write_db = args.apply

    if not os.path.exists(DB_PATH):
        parser.error("未找到生产库: " + DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        label = "ALL" + ((" [{}]".format(args.state)) if args.state else "")
        stats = apply_timezone_to_leads(
            conn, dry_run=not write_db, state_filter=args.state
        )
        _print_stats(label, stats)
        # 默认模式下额外打印 TN / KY 各自解析情况，便于报告
        if not args.state:
            for st in ("TN", "KY"):
                sub = apply_timezone_to_leads(
                    conn, dry_run=True, state_filter=st
                )
                _print_stats("STATE [{}]".format(st), sub)
        if write_db:
            print("已写库（--apply）。")
        else:
            print("本次为 dry-run，未写库。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
