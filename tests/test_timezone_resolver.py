# -*- coding: utf-8 -*-
"""timezone_resolver 的单元测试。

纯函数测试：resolve_timezone 直接用内存调用；
apply_timezone_to_leads 使用内存 sqlite 库，不碰生产库。
"""

from __future__ import annotations

import os
import sqlite3
import sys
import unittest

# 把项目根目录加入 sys.path，便于 import timezone_resolver
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timezone_resolver import (  # noqa: E402
    RESOLVED,
    UNRESOLVED,
    CITY_TZ_OVERRIDES,
    SPLIT_TZ_STATES,
    STATE_DEFAULT_TZ,
    apply_timezone_to_leads,
    resolve_timezone,
)


def _assert_resolved(test, city, state, expected_tz):
    tz, status = resolve_timezone(city, state)
    test.assertEqual(status, RESOLVED)
    test.assertEqual(tz, expected_tz)


def _assert_unresolved(test, city, state):
    tz, status = resolve_timezone(city, state)
    test.assertEqual(status, UNRESOLVED)
    test.assertIsNone(tz)


class TestResolveTimezone(unittest.TestCase):
    """resolve_timezone 纯函数用例。"""

    def test_nashville_tn_central(self):
        _assert_resolved(self, "Nashville", "TN", "America/Chicago")

    def test_memphis_tn_central(self):
        _assert_resolved(self, "Memphis", "TN", "America/Chicago")

    def test_knoxville_tn_eastern(self):
        _assert_resolved(self, "Knoxville", "TN", "America/New_York")

    def test_chattanooga_tn_eastern(self):
        _assert_resolved(self, "Chattanooga", "TN", "America/New_York")

    def test_louisville_ky_eastern(self):
        _assert_resolved(self, "Louisville", "KY", "America/New_York")

    def test_lexington_ky_eastern(self):
        _assert_resolved(self, "Lexington", "KY", "America/New_York")

    def test_paducah_ky_central(self):
        _assert_resolved(self, "Paducah", "KY", "America/Chicago")

    def test_bowling_green_ky_central(self):
        _assert_resolved(self, "Bowling Green", "KY", "America/Chicago")

    def test_los_angeles_ca_pacific(self):
        _assert_resolved(self, "Los Angeles", "CA", "America/Los_Angeles")

    def test_single_tz_state_default(self):
        # 单时区州用州级默认（城市无需在 override 中）
        _assert_resolved(self, "Houston", "TX", "America/Chicago")
        _assert_resolved(self, "Seattle", "WA", "America/Los_Angeles")
        _assert_resolved(self, "Denver", "CO", "America/Denver")
        _assert_resolved(self, "Atlanta", "GA", "America/New_York")

    def test_case_insensitive(self):
        _assert_resolved(self, "nashville", "tn", "America/Chicago")
        _assert_resolved(self, "  Nashville  ", " tn ", "America/Chicago")

    def test_split_states_not_in_default_dict(self):
        # 跨时区州不能出现在 STATE_DEFAULT_TZ 中
        for st in SPLIT_TZ_STATES:
            self.assertNotIn(st, STATE_DEFAULT_TZ)

    def test_tn_unknown_city_unresolved(self):
        # TN 城市不在 override -> 必须 UNRESOLVED，不能回落州级默认
        _assert_unresolved(self, "Nowhereville", "TN")

    def test_ky_unknown_city_unresolved(self):
        _assert_unresolved(self, "Nowhereville", "KY")

    def test_empty_city_unresolved(self):
        _assert_unresolved(self, "", "TX")

    def test_empty_state_unresolved(self):
        _assert_unresolved(self, "Nashville", "")

    def test_none_city_or_state_unresolved(self):
        _assert_unresolved(self, None, "TN")
        _assert_unresolved(self, "Nashville", None)

    def test_override_cities_present(self):
        # 任务要求的关键城市必须都在 override 中
        required = [
            ("Nashville", "TN"),
            ("Memphis", "TN"),
            ("Knoxville", "TN"),
            ("Chattanooga", "TN"),
            ("Johnson City", "TN"),
            ("Louisville", "KY"),
            ("Lexington", "KY"),
            ("Paducah", "KY"),
            ("Bowling Green", "KY"),
            ("Florence", "KY"),
            ("Miami", "FL"),
            ("Pensacola", "FL"),
            ("Detroit", "MI"),
            ("Marquette", "MI"),
            ("Indianapolis", "IN"),
            ("Evansville", "IN"),
            ("Phoenix", "AZ"),
        ]
        for key in required:
            self.assertIn(key, CITY_TZ_OVERRIDES)


class TestApplyTimezoneToLeads(unittest.TestCase):
    """apply_timezone_to_leads 用内存 sqlite 验证写库逻辑。"""

    def _make_conn(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            CREATE TABLE leads (
                id INTEGER PRIMARY KEY,
                store_name TEXT,
                city TEXT,
                state TEXT,
                email TEXT,
                status TEXT DEFAULT 'new',
                recipient_timezone TEXT,
                timezone_status TEXT DEFAULT 'UNSET',
                sendable_for_automatic_schedule INTEGER DEFAULT 1
            );
            """
        )
        return conn

    def _insert(self, conn, store, city, state, email, status="new"):
        conn.execute(
            "INSERT INTO leads (store_name, city, state, email, status) VALUES (?,?,?,?,?)",
            (store, city, state, email, status),
        )

    def _get(self, conn, store):
        return conn.execute(
            "SELECT recipient_timezone, timezone_status, "
            "sendable_for_automatic_schedule FROM leads WHERE store_name=?",
            (store,),
        ).fetchone()

    def test_apply_sets_resolved_and_sendable(self):
        conn = self._make_conn()
        self._insert(conn, "Nashville Store", "Nashville", "TN", "a@x.com")
        apply_timezone_to_leads(conn, dry_run=False)
        row = self._get(conn, "Nashville Store")
        self.assertEqual(row[0], "America/Chicago")
        self.assertEqual(row[1], RESOLVED)
        self.assertEqual(row[2], 1)

    def test_apply_unknown_tn_sets_unresolved_sendable_0(self):
        conn = self._make_conn()
        self._insert(conn, "Unknown TN Store", "Nowhereville", "TN", "b@x.com")
        apply_timezone_to_leads(conn, dry_run=False)
        row = self._get(conn, "Unknown TN Store")
        self.assertEqual(row[0], None)
        self.assertEqual(row[1], UNRESOLVED)
        self.assertEqual(row[2], 0)

    def test_apply_skips_empty_email_and_excluded_status(self):
        conn = self._make_conn()
        self._insert(conn, "No Email", "Nashville", "TN", "", "new")
        self._insert(conn, "Sent Store", "Nashville", "TN", "c@x.com", "sent")
        stats = apply_timezone_to_leads(conn, dry_run=False)
        # 仅状态范围内的行被扫描；sent 行本就不在范围内。
        # skipped = 范围内但 email 为空的行数。
        self.assertEqual(stats["resolved"], 0)
        self.assertEqual(stats["skipped"], 1)

    def test_apply_state_filter(self):
        conn = self._make_conn()
        self._insert(conn, "TN Store", "Nashville", "TN", "d@x.com")
        self._insert(conn, "KY Store", "Louisville", "KY", "e@x.com")
        stats = apply_timezone_to_leads(conn, dry_run=False, state_filter="KY")
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(self._get(conn, "KY Store")[0], "America/New_York")
        # TN 行未在本轮处理，字段保持默认
        self.assertEqual(self._get(conn, "TN Store")[0], None)

    def test_dry_run_does_not_write(self):
        conn = self._make_conn()
        self._insert(conn, "Nashville Store", "Nashville", "TN", "f@x.com")
        stats = apply_timezone_to_leads(conn, dry_run=True)
        self.assertEqual(stats["resolved"], 1)
        row = self._get(conn, "Nashville Store")
        self.assertEqual(row[0], None)
        self.assertEqual(row[1], "UNSET")

    def test_stats_counts(self):
        conn = self._make_conn()
        self._insert(conn, "Resolved Store", "Nashville", "TN", "g@x.com")
        self._insert(conn, "Unresolved Store", "Nowhereville", "TN", "h@x.com")
        stats = apply_timezone_to_leads(conn, dry_run=True)
        self.assertEqual(stats["resolved"], 1)
        self.assertEqual(stats["unresolved"], 1)
        self.assertEqual(stats["unresolved_examples"], ["Unresolved Store"])


if __name__ == "__main__":
    unittest.main()
