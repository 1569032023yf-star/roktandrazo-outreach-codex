"""P8 Dashboard 收敛测试：搜索进度动态化 + 术语统一 + 旧生成器归档。

- get_search_progress 从 system_config 动态读取城市（绝不硬编码 Nashville）
- 无配置数据 → available=false, status='unknown'
- bd_ops_api.py 源码不含 Nashville 字面量（注释除外）
- bd_dashboard_v3.2.py 源码不含 "Delivered" / "Confirmed Read"
- 归档的两个旧 dashboard 文件含禁用标记

使用临时文件 SQLite（等效内存库，隔离生产 DB）。
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bd_ops_api import get_search_progress  # noqa: E402

ARCHIVED_DIR = ROOT / "_archived_scripts" / "2026-08-07"


def _insert_config(conn, pairs):
    for k, v in pairs:
        conn.execute(
            "INSERT INTO system_config (key, value) VALUES (?, ?)",
            (k, str(v) if not isinstance(v, str) else v),
        )


def _make_city_queue_row(city="Knoxville", state="TN", status="in_progress",
                         priority=1, active_source="google_places"):
    return (
        1, city, state, priority, "America/New_York", status,
        None, None, None, None, None, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        None, None, None, 0, 0, 0, 0, 0, None, None, None, None, None,
    )


class TestSearchProgress(unittest.TestCase):
    """get_search_progress 动态城市读取。"""

    def setUp(self):
        # 临时文件库，仅本测试使用，隔离生产 DB
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "test.db")
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE system_config (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE retail_city_queue (
                id INTEGER PRIMARY KEY, city TEXT, state TEXT, priority INTEGER,
                timezone TEXT, status TEXT, started_at TEXT, completed_at TEXT,
                active_query_family TEXT, active_source TEXT, page_cursor TEXT,
                discovered_count INTEGER, unique_domain_count INTEGER,
                official_site_count INTEGER, public_email_count INTEGER,
                strict_a0_count INTEGER, manual_review_count INTEGER,
                contact_form_count INTEGER, duplicate_count INTEGER, rejected_count INTEGER,
                last_new_domain_at TEXT, completion_reason TEXT, active_provider TEXT,
                pages_processed INTEGER, results_seen INTEGER, new_unique_places INTEGER,
                duplicate_places INTEGER, provider_errors INTEGER,
                consecutive_pages_without_new_place INTEGER, last_success_at TEXT,
                last_error TEXT, resume_state TEXT, web_directory_status TEXT
            );
            CREATE TABLE lead_discovery_query_state (
                id INTEGER PRIMARY KEY, active_city_id INTEGER, provider TEXT,
                query_family TEXT, query_text TEXT, status TEXT, page_cursor TEXT,
                pages_processed INTEGER, results_seen INTEGER, new_unique_places INTEGER,
                duplicate_places INTEGER, provider_errors INTEGER,
                consecutive_pages_without_new_place INTEGER, last_success_at TEXT,
                last_error TEXT, resume_state TEXT, started_at TEXT, completed_at TEXT
            );
        """)
        self.conn = conn

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_active_city_from_system_config(self):
        """system_config 配置 Knoxville 时返回 Knoxville（不硬编码 Nashville）。"""
        _insert_config(self.conn, [
            ("active_retail_city", "Knoxville"),
            ("active_city_state", "TN"),
        ])
        self.conn.execute(
            "INSERT INTO retail_city_queue VALUES (%s)" %
            ", ".join(["?"] * 33),
            _make_city_queue_row(city="Knoxville"),
        )
        # 2 条查询：1 条完成、1 条待执行
        self.conn.executemany(
            "INSERT INTO lead_discovery_query_state (active_city_id, provider, query_family, "
            "query_text, status) VALUES (?, ?, ?, ?, ?)",
            [(1, "google_places", "toy store", "toy store Knoxville TN", "completed"),
             (1, "google_places", "game store", "game store Knoxville TN", "pending")],
        )
        self.conn.commit()

        result = get_search_progress(self.db_path)

        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("active_city"), "Knoxville")
        self.assertEqual(result.get("active_state"), "TN")
        self.assertNotEqual(result.get("active_city"), "Nashville")
        self.assertEqual(result.get("queries_total"), 2)
        self.assertEqual(result.get("queries_executed"), 1)
        self.assertEqual(result.get("queries_remaining"), ["game store"])
        self.assertEqual(result.get("current_query"), "game store")

    def test_system_config_fallback_to_search_queries(self):
        """无城市队列查询时回退 system_config.search_queries JSON。"""
        _insert_config(self.conn, [
            ("active_retail_city", "Memphis"),
            ("active_city_state", "TN"),
            ("search_queries", '["toy store","game store"]'),
        ])
        self.conn.commit()

        result = get_search_progress(self.db_path)

        self.assertTrue(result.get("available"))
        self.assertEqual(result.get("active_city"), "Memphis")
        self.assertEqual(result.get("queries_total"), 2)
        self.assertEqual(result.get("queries_executed"), 0)

    def test_no_data_returns_unavailable(self):
        """system_config 无数据 → available=false, status='unknown'（fail-closed）。"""
        result = get_search_progress(self.db_path)

        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("status"), "unknown")
        self.assertIsNone(result.get("active_city"))
        # 绝不回退到 22/22 之类的硬编码值
        self.assertEqual(result.get("queries_total"), 0)
        self.assertEqual(result.get("queries_executed"), 0)


class TestSourceAudit(unittest.TestCase):
    """源码审计：无 Nashville 硬编码、无错误术语、归档标记存在。"""

    @staticmethod
    def _strip_comments(text):
        """去掉整行注释（以 # 开头的行），允许注释中出现城市名。"""
        lines = []
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            lines.append(line)
        return "\n".join(lines)

    def test_bd_ops_api_no_nashville_literal(self):
        """bd_ops_api.py 源码（非注释）不含 'Nashville'。"""
        src = (ROOT / "bd_ops_api.py").read_text(encoding="utf-8")
        code = self._strip_comments(src)
        self.assertNotIn("Nashville", code)
        self.assertNotIn("nashville", code)

    def test_dashboard_v32_no_legacy_terms(self):
        """bd_dashboard_v3.2.py 不含 'Delivered' / 'Confirmed Read'。"""
        src = (ROOT / "bd_dashboard_v3.2.py").read_text(encoding="utf-8")
        self.assertNotIn("Delivered", src)
        self.assertNotIn("Confirmed Read", src)
        self.assertNotIn("已读", src)

    def test_archived_dashboards_have_disable_marker(self):
        """归档的两个旧 dashboard 文件含禁用标记。"""
        marker = "LEGACY_DASHBOARD_ARCHIVED"
        for name in ("dashboard.py", "bd_operations_dashboard.py"):
            path = ARCHIVED_DIR / name
            self.assertTrue(path.exists(), f"缺少归档文件 {path}")
            text = path.read_text(encoding="utf-8")
            self.assertIn(marker, text)
            self.assertIn("bd_dashboard_v3.2", text)
        # 原路径不应再存在
        self.assertFalse((ROOT / "dashboard.py").exists())
        self.assertFalse((ROOT / "bd_operations_dashboard.py").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
