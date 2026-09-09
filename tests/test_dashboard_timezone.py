#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0「Dashboard 时区增强」单元测试。

用内存 sqlite 造 leads + final_send_plan + send_log + bounce_log 数据，
测试 bd_dashboard_v3.2.py 中的纯计算函数（不渲染 HTML）：
  - 时区统计卡计数（RESOLVED / TIMEZONE_UNRESOLVED / 自动调度可发送 / 分布）
  - 发送预览行含 Recipient Timezone / Scheduled China Time 转换
  - Local Time Deviation 秒差计算
  - recipient_timezone 为空的行标记 TIMEZONE_UNRESOLVED（NOT SCHEDULABLE）
"""
import importlib.util
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

# 文件名含点号，须用 importlib 加载
_SPEC = importlib.util.spec_from_file_location(
    "bd_dashboard_v3_2", str(PROJECT_DIR / "bd_dashboard_v3.2.py"))
DASH = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(DASH)

# 固定模拟时刻：2026-08-05（周三）中午 UTC，保证窗口计算可复现
NOW_UTC = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


def make_db():
    """造内存库：3 条 leads + 2 条 planned 计划 + 2 条 send_log + 2 条 bounce_log。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE leads (
            id INTEGER, store_name TEXT, city TEXT, state TEXT,
            recipient_timezone TEXT, timezone_status TEXT,
            sendable_for_automatic_schedule INTEGER
        );
        CREATE TABLE final_send_plan (
            id INTEGER, plan_id TEXT, lead_id INTEGER, recipient_email TEXT,
            company_name TEXT, outreach_batch_date TEXT, planned_sequence INTEGER,
            status TEXT, created_at TEXT, template_id TEXT, template_key TEXT,
            renderer_version TEXT, rendered_text_body TEXT, body_text TEXT
        );
        CREATE TABLE send_log (
            id INTEGER, lead_id INTEGER, status TEXT, sent_at TEXT,
            recipient_timezone TEXT, scheduled_local_time TEXT,
            scheduled_utc_time TEXT, actual_sent_at_local TEXT,
            local_time_deviation_seconds INTEGER
        );
        CREATE TABLE bounce_log (
            id INTEGER, lead_id INTEGER, bounce_type TEXT
        );
    """)
    # leads：1 个 Eastern 已解析、1 个 Chicago 已解析、1 个 UNRESOLVED
    c.executemany(
        "INSERT INTO leads VALUES (?,?,?,?,?,?,?)",
        [
            (1, "Alpha Games", "New York", "NY", "America/New_York", "RESOLVED", 1),
            (2, "Beta Toys", "Nashville", "TN", None, "TIMEZONE_UNRESOLVED", 0),
            (3, "Gamma Books", "Chicago", "IL", "America/Chicago", "RESOLVED", 1),
        ],
    )
    # planned 计划：lead1（有时区）、lead2（无时区）
    c.executemany(
        "INSERT INTO final_send_plan VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (11, "batch_a_0001", 1, "a@alpha.com", "Alpha Games", "batch_a", 1, "planned",
             "2026-08-05T00:00:00+08:00", "retail_v5", "retail_distributor_v5",
             "v5.2.1", "Line one of body\nLine two", "Line one of body"),
            (12, "batch_a_0002", 2, "b@beta.com", "Beta Toys", "batch_a", 2, "planned",
             "2026-08-05T00:00:00+08:00", "retail_v5", None, None, None, None),
        ],
    )
    # send_log：lead1 有 scheduled/actual（偏差 300s）、lead3 无 scheduled 字段
    c.executemany(
        "INSERT INTO send_log VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (21, 1, "sent", "2026-08-05T14:05:00+00:00", "America/New_York",
             "2026-08-05T10:00:00-04:00[America/New_York]",
             "2026-08-05T14:00:00+00:00",
             "2026-08-05T10:05:00-04:00[America/New_York]", None),
            (22, 3, "sent", "2026-08-05T15:00:00+00:00", "America/Chicago",
             None, None, None, None),
        ],
    )
    # bounce_log：lead1 硬退信，lead3 无记录
    c.executemany("INSERT INTO bounce_log VALUES (?,?,?)",
                  [(31, 1, "hard"), (32, 2, "policy")])
    conn.commit()
    return conn


class TimezoneStatsTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def tearDown(self):
        self.conn.close()

    def test_timezone_stats_counts(self):
        """时区统计卡：RESOLVED=2、UNRESOLVED=1、自动调度可发送=2。"""
        s = DASH.compute_timezone_stats(self.conn)
        self.assertEqual(s["resolved"], 2)
        self.assertEqual(s["unresolved"], 1)
        self.assertEqual(s["sendable_for_automatic_schedule"], 2)
        self.assertEqual(s["total"], 3)

    def test_timezone_distribution(self):
        """按时区分布：Eastern=1（New_York）、Central=1（Chicago）、其余 0。"""
        s = DASH.compute_timezone_stats(self.conn)
        self.assertEqual(s["distribution"]["Eastern"], 1)
        self.assertEqual(s["distribution"]["Central"], 1)
        self.assertEqual(s["distribution"]["Mountain"], 0)
        self.assertEqual(s["distribution"]["Pacific"], 0)
        self.assertEqual(s["distribution"]["Other"], 0)


class SchedulePreviewTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def tearDown(self):
        self.conn.close()

    def test_preview_rows_include_planned(self):
        """预览读 planned 行，且 join leads 的 store/city/state。"""
        entries = DASH.compute_schedule_preview(self.conn, now_utc=NOW_UTC)
        by_lead = {e["lead_id"]: e for e in entries}
        self.assertEqual(len(entries), 2)
        self.assertEqual(by_lead[1]["store"], "Alpha Games")
        self.assertEqual(by_lead[1]["city"], "New York")
        self.assertEqual(by_lead[1]["state"], "NY")

    def test_preview_timezone_and_china_time(self):
        """纽约当地 08:00（2026-08-05）→ Asia/Shanghai 应为 20:00 当日（P2.3I 窗口 08:00-11:10）。"""
        entries = DASH.compute_schedule_preview(self.conn, now_utc=NOW_UTC)
        e = next(x for x in entries if x["lead_id"] == 1)
        self.assertEqual(e["recipient_timezone"], "America/New_York")
        self.assertIn("08:00:00", e["scheduled_local_time"])
        # 8 月纽约为 EDT（UTC-4），当地 08:00 = UTC 12:00 = 上海 20:00
        self.assertIn("20:00:00", e["scheduled_china_time"])
        self.assertTrue(e["schedulable"])

    def test_preview_unresolved_marker(self):
        """recipient_timezone 为空 → timezone_unresolved=True、scheduled_local_time=None。"""
        entries = DASH.compute_schedule_preview(self.conn, now_utc=NOW_UTC)
        e = next(x for x in entries if x["lead_id"] == 2)
        self.assertTrue(e["timezone_unresolved"])
        self.assertIsNone(e["scheduled_local_time"])
        self.assertIsNone(e["scheduled_china_time"])
        self.assertFalse(e["schedulable"])

    def test_preview_template_renderer(self):
        """Template / Renderer Version / Preview 首行截断。"""
        entries = DASH.compute_schedule_preview(self.conn, now_utc=NOW_UTC)
        e = next(x for x in entries if x["lead_id"] == 1)
        self.assertEqual(e["template"], "retail_distributor_v5")
        self.assertEqual(e["renderer_version"], "v5.2.1")
        self.assertEqual(e["preview"], "Line one of body")


class SendResultsTzTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def tearDown(self):
        self.conn.close()

    def test_deviation_computed(self):
        """Local Time Deviation = actual_sent_at_local 与 scheduled_local_time 的秒差（300s）。"""
        results = DASH.compute_send_results_tz(self.conn, days=365)
        r = next(x for x in results if x["lead_id"] == 1)
        self.assertEqual(r["deviation_seconds"], 300)

    def test_deviation_none_when_missing(self):
        """无 scheduled/actual 字段时 deviation 为 None。"""
        results = DASH.compute_send_results_tz(self.conn, days=365)
        r = next(x for x in results if x["lead_id"] == 3)
        self.assertIsNone(r["deviation_seconds"])

    def test_delivery_outcome_from_bounce(self):
        """Delivery Outcome 取 bounce_log 的 bounce_type；无则 '—'。"""
        results = DASH.compute_send_results_tz(self.conn, days=365)
        by_lead = {x["lead_id"]: x for x in results}
        self.assertEqual(by_lead[1]["delivery_outcome"], "hard")
        self.assertEqual(by_lead[3]["delivery_outcome"], "—")

    def test_smtp_status_present(self):
        results = DASH.compute_send_results_tz(self.conn, days=365)
        r = next(x for x in results if x["lead_id"] == 1)
        self.assertEqual(r["smtp_status"], "sent")


class HelperTest(unittest.TestCase):
    def test_parse_scheduled_local(self):
        """解析带 [IANA] 后缀的 scheduled_local_time。"""
        dt = DASH._parse_scheduled_local("2026-08-05T10:00:00-04:00[America/New_York]")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.utcoffset().total_seconds(), -4 * 3600)

    def test_scheduled_to_china(self):
        """本地 10:00 转 Asia/Shanghai。"""
        s = DASH._scheduled_to_china("2026-08-05T10:00:00-04:00[America/New_York]")
        self.assertIsNotNone(s)
        self.assertIn("22:00:00", s)

    def test_deviation_seconds_helper(self):
        self.assertEqual(
            DASH._deviation_seconds("2026-08-05T10:05:00-04:00",
                                    "2026-08-05T10:00:00-04:00"), 300)
        self.assertIsNone(DASH._deviation_seconds(None, "2026-08-05T10:00:00-04:00"))

    def test_tz_region(self):
        self.assertEqual(DASH._tz_region("America/New_York"), "Eastern")
        self.assertEqual(DASH._tz_region("America/Chicago"), "Central")
        self.assertEqual(DASH._tz_region("America/Denver"), "Mountain")
        self.assertEqual(DASH._tz_region("America/Los_Angeles"), "Pacific")
        self.assertEqual(DASH._tz_region("Europe/London"), "Other")
        self.assertEqual(DASH._tz_region(None), "Other")


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT_DIR))
    unittest.main(verbosity=2)
