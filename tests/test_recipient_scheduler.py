#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recipient_scheduler 的单元测试（P0）。

全部使用纯内存 mock（内存 sqlite / 固定 datetime），绝不碰生产库、绝不发 SMTP。
"""
from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import recipient_scheduler as rs

UTC = timezone.utc


def utc_dt(*args):
    """构造带 UTC 时区的 datetime。"""
    return datetime(*args, tzinfo=UTC)


def make_conn():
    """内存 sqlite，含调度所需的 leads / final_send_plan 表。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE leads (
          id INTEGER PRIMARY KEY, store_name TEXT, city TEXT, state TEXT, email TEXT,
          status TEXT, recipient_timezone TEXT, timezone_status TEXT,
          sendable_for_automatic_schedule INTEGER
        );
        CREATE TABLE final_send_plan (
          id INTEGER PRIMARY KEY, plan_id TEXT, lead_id INTEGER, recipient_email TEXT,
          company_name TEXT, template_id TEXT, message_type TEXT, outreach_batch_date TEXT,
          planned_sequence INTEGER, subject TEXT, body_text TEXT, body_html TEXT,
          status TEXT, created_at TEXT
        );
        """
    )
    return conn


def add_lead(conn, lid, tz, status="RESOLVED", flag=1, email=None):
    conn.execute(
        "INSERT INTO leads (id, store_name, email, status, recipient_timezone, "
        "timezone_status, sendable_for_automatic_schedule) VALUES (?,?,?,?,?,?,?)",
        (lid, f"Store {lid}", email or f"{lid}@x.com", "new", tz, status, flag),
    )


def add_plan(conn, lid, batch="B1", seq=1, email=None):
    conn.execute(
        "INSERT INTO final_send_plan (plan_id, lead_id, recipient_email, company_name, "
        "template_id, message_type, outreach_batch_date, planned_sequence, subject, "
        "body_text, body_html, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"{batch}_{seq:04d}", lid, email or f"{lid}@x.com", "Co", "tpl", "new_outreach",
         batch, seq, "Subj", "body", "<p>html</p>", "planned",
         utc_dt(2026, 8, 6, 12, 0).isoformat()),
    )


class TestLocalSendWindowUtc(unittest.TestCase):
    """窗口计算：跨时区同一天差 3 小时 + DST 切换日。"""

    def test_new_york_vs_los_angeles_same_day_diff_3h(self):
        d = date(2026, 7, 15)  # 夏季：EDT(-4) / PDT(-7)
        ny_start, ny_end = rs.local_send_window_utc("America/New_York", d)
        la_start, la_end = rs.local_send_window_utc("America/Los_Angeles", d)
        self.assertEqual(ny_start, utc_dt(2026, 7, 15, 12, 0, 0))
        self.assertEqual(ny_end, utc_dt(2026, 7, 15, 15, 10, 59))
        self.assertEqual(la_start, utc_dt(2026, 7, 15, 15, 0, 0))
        self.assertEqual(la_end, utc_dt(2026, 7, 15, 18, 10, 59))
        self.assertEqual((la_start - ny_start).total_seconds(), 3 * 3600)

    def test_dst_spring_forward_2026_03_08(self):
        # 03-07 仍为 EST(-5)，03-08 凌晨 2 点切 EDT(-4)，同一当地 08:00 对应 UTC 提前 1 小时
        before = rs.local_send_window_utc("America/New_York", date(2026, 3, 7))[0]
        after = rs.local_send_window_utc("America/New_York", date(2026, 3, 8))[0]
        self.assertEqual(before, utc_dt(2026, 3, 7, 13, 0, 0))
        self.assertEqual(after, utc_dt(2026, 3, 8, 12, 0, 0))
        # 本地偏移从 -5h 跳到 -4h（DST 开启）
        self.assertEqual(before.astimezone(ZoneInfo("America/New_York")).utcoffset(),
                         timedelta(hours=-5))
        self.assertEqual(after.astimezone(ZoneInfo("America/New_York")).utcoffset(),
                         timedelta(hours=-4))

    def test_dst_fall_back_2026_11_01(self):
        # 10-31 仍为 EDT(-4)，11-01 凌晨 2 点切 EST(-5)，同一当地 08:00 对应 UTC 推迟 1 小时
        before = rs.local_send_window_utc("America/New_York", date(2026, 10, 31))[0]
        after = rs.local_send_window_utc("America/New_York", date(2026, 11, 2))[0]
        self.assertEqual(before, utc_dt(2026, 10, 31, 12, 0, 0))
        self.assertEqual(after, utc_dt(2026, 11, 2, 13, 0, 0))
        # 本地偏移从 -4h 回到 -5h（DST 关闭）
        self.assertEqual(before.astimezone(ZoneInfo("America/New_York")).utcoffset(),
                         timedelta(hours=-4))
        self.assertEqual(after.astimezone(ZoneInfo("America/New_York")).utcoffset(),
                         timedelta(hours=-5))


class TestIsWeekdayLocal(unittest.TestCase):
    """UTC -> 当地日期的工作日判断。"""

    def test_weekend_returns_false(self):
        # 2026-08-08 是周六，2026-08-09 是周日（UTC 15:00 -> NY 当地 11:00，日期不变）
        self.assertFalse(rs.is_weekday_local("America/New_York", utc_dt(2026, 8, 8, 15, 0)))
        self.assertFalse(rs.is_weekday_local("America/New_York", utc_dt(2026, 8, 9, 15, 0)))

    def test_weekday_returns_true(self):
        # 2026-08-07 周五，2026-08-10 周一
        self.assertTrue(rs.is_weekday_local("America/New_York", utc_dt(2026, 8, 7, 15, 0)))
        self.assertTrue(rs.is_weekday_local("America/New_York", utc_dt(2026, 8, 10, 15, 0)))


class TestInSendWindow(unittest.TestCase):
    """发送窗口边界（含端点）。窗口为 2026-08-07 当地 08:00:00-11:10:59（EDT -> 12:00:00-15:10:59 UTC）。"""

    def test_boundaries(self):
        self.assertFalse(rs.in_send_window("America/New_York", utc_dt(2026, 8, 7, 11, 59, 59)))
        self.assertTrue(rs.in_send_window("America/New_York", utc_dt(2026, 8, 7, 12, 0, 0)))
        self.assertTrue(rs.in_send_window("America/New_York", utc_dt(2026, 8, 7, 15, 10, 59)))
        self.assertFalse(rs.in_send_window("America/New_York", utc_dt(2026, 8, 7, 15, 11, 0)))


class TestSchedulePlanEntry(unittest.TestCase):
    """schedule_plan_entry 单条调度。默认用固定周五 2026-08-07 作为 now。"""

    FRIDAY = utc_dt(2026, 8, 7, 12, 0, 0)
    SATURDAY = utc_dt(2026, 8, 8, 12, 0, 0)

    def _lead(self, tz="America/New_York", status="RESOLVED", flag=1):
        return {
            "id": 1,
            "recipient_timezone": tz,
            "timezone_status": status,
            "sendable_for_automatic_schedule": flag,
        }

    def _plan(self):
        return {"lead_id": 1, "recipient_email": "a@x.com", "outreach_batch_date": "B1"}

    def test_valid_entry_sendable(self):
        e = rs.schedule_plan_entry(self._lead(), self._plan(), now_utc=self.FRIDAY)
        self.assertTrue(e["sendable"])
        self.assertIsNone(e["block_reason"])
        self.assertEqual(e["recipient_timezone"], "America/New_York")
        self.assertEqual(e["scheduled_utc_time"], "2026-08-07T12:00:00+00:00")
        self.assertEqual(e["scheduled_local_time"], "2026-08-07T08:00:00-04:00[America/New_York]")
        self.assertEqual(e["lead_id"], 1)
        self.assertEqual(e["recipient_email"], "a@x.com")

    def test_empty_timezone_not_sendable(self):
        e = rs.schedule_plan_entry(self._lead(tz=""), self._plan(), now_utc=self.FRIDAY)
        self.assertFalse(e["sendable"])
        self.assertEqual(e["block_reason"], "no_recipient_timezone")
        self.assertIsNone(e["scheduled_utc_time"])

    def test_invalid_timezone_not_sendable(self):
        e = rs.schedule_plan_entry(self._lead(tz="Mars/Olympus"), self._plan(), now_utc=self.FRIDAY)
        self.assertFalse(e["sendable"])
        self.assertEqual(e["block_reason"], "invalid_timezone:Mars/Olympus")

    def test_timezone_unresolved_not_sendable(self):
        e = rs.schedule_plan_entry(
            self._lead(tz="America/Chicago", status="TIMEZONE_UNRESOLVED"),
            self._plan(), now_utc=self.FRIDAY,
        )
        self.assertFalse(e["sendable"])
        self.assertEqual(e["block_reason"], "TIMEZONE_UNRESOLVED")

    def test_sendable_flag_zero_not_sendable(self):
        e = rs.schedule_plan_entry(self._lead(flag=0), self._plan(), now_utc=self.FRIDAY)
        self.assertFalse(e["sendable"])
        self.assertEqual(e["block_reason"], "not_sendable_for_automatic_schedule")

    def test_weekend_not_sendable(self):
        e = rs.schedule_plan_entry(self._lead(), self._plan(), now_utc=self.SATURDAY)
        self.assertFalse(e["sendable"])
        self.assertEqual(e["block_reason"], "not_weekday_local")


class TestGroupEntriesByTimezone(unittest.TestCase):
    def test_groups_by_iana_timezone(self):
        friday = utc_dt(2026, 8, 7, 12, 0, 0)
        ny = rs.schedule_plan_entry(
            {"recipient_timezone": "America/New_York", "timezone_status": "RESOLVED",
             "sendable_for_automatic_schedule": 1},
            {"lead_id": 1, "recipient_email": "a@x.com"},
            now_utc=friday,
        )
        ny2 = rs.schedule_plan_entry(
            {"recipient_timezone": "America/New_York", "timezone_status": "RESOLVED",
             "sendable_for_automatic_schedule": 1},
            {"lead_id": 2, "recipient_email": "b@x.com"},
            now_utc=friday,
        )
        la = rs.schedule_plan_entry(
            {"recipient_timezone": "America/Los_Angeles", "timezone_status": "RESOLVED",
             "sendable_for_automatic_schedule": 1},
            {"lead_id": 3, "recipient_email": "c@x.com"},
            now_utc=friday,
        )
        groups = rs.group_entries_by_timezone([ny, la, ny2])
        self.assertEqual(set(groups), {"America/New_York", "America/Los_Angeles"})
        self.assertEqual(len(groups["America/New_York"]), 2)
        # 组内按 UTC 升序
        self.assertEqual(
            [e["lead_id"] for e in groups["America/New_York"]], [1, 2]
        )
        # LA 窗口晚于 NY
        self.assertEqual(
            groups["America/Los_Angeles"][0]["scheduled_utc_time"],
            "2026-08-07T15:00:00+00:00",
        )


class TestDryRunBatch(unittest.TestCase):
    """dry_run_batch 输出结构；只读、不写库。"""

    def test_output_structure_and_read_only(self):
        conn = make_conn()
        add_lead(conn, 1, "America/New_York")      # sendable
        add_lead(conn, 2, "America/Los_Angeles")   # sendable
        add_lead(conn, 3, None, status="UNSET")    # 无时区 -> blocked
        add_plan(conn, 1, seq=1)
        add_plan(conn, 2, seq=2)
        add_plan(conn, 3, seq=3)
        conn.commit()

        res = rs.dry_run_batch(conn, "B1", now_utc=utc_dt(2026, 8, 7, 12, 0, 0))

        self.assertEqual(res["batch_id"], "B1")
        self.assertEqual(res["total"], 3)
        self.assertEqual(res["sendable_count"], 2)
        self.assertEqual(res["blocked_count"], 1)
        self.assertEqual(res["blocked_reasons"], {"no_recipient_timezone": 1})
        self.assertEqual(res["timezone_distribution"], {
            "America/New_York": 1,
            "America/Los_Angeles": 1,
            None: 1,
        })
        self.assertEqual(len(res["entries"]), 3)
        # 发送顺序：NY(Eastern) 先，LA(Pacific) 后
        order = res["send_order_suggestion"]
        self.assertEqual([o["timezone"] for o in order],
                         ["America/New_York", "America/Los_Angeles"])
        self.assertEqual(order[0]["window_utc_start"], "2026-08-07T12:00:00+00:00")
        self.assertEqual(order[1]["window_utc_start"], "2026-08-07T15:00:00+00:00")

        # 只读验证：计划仍为 planned，未创建任何新表（无 send_log 写入迹象）
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM final_send_plan WHERE status='planned'").fetchone()[0], 3
        )
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        self.assertNotIn("send_log", tables)
        conn.close()

    def test_batch_with_zero_planned(self):
        conn = make_conn()
        res = rs.dry_run_batch(conn, "NONEXIST", now_utc=utc_dt(2026, 8, 7, 12, 0, 0))
        self.assertEqual(res["total"], 0)
        self.assertEqual(res["sendable_count"], 0)
        self.assertEqual(res["blocked_count"], 0)
        self.assertEqual(res["send_order_suggestion"], [])
        conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
