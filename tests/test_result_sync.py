"""
P0 结果同步与日报 -- result_recovery_sync / daily_results_0900 单元测试。

用临时 sqlite 文件（内存库）Mock system_config 状态，不碰生产 DB。
覆盖场景：
  ① sync 新鲜且成功     -> 报告正常显示数字
  ② sync 过期           -> 报告显示 DATA STALE 且无 Bounce=0
  ③ bounce step 失败    -> 报告显示 BOUNCE SCAN FAILED
  另测 run_sync() 的 bounce_pipeline import 失败降级路径（monkeypatch import）。
"""

import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone

# 保证能 import 项目根目录下的模块
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bd_db  # noqa: E402
import daily_results_0900 as drs  # noqa: E402
import result_recovery_sync as rrs  # noqa: E402

CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(CST).isoformat()


def _old_iso(hours_ago: float = 5.0) -> str:
    return (datetime.now(CST) - timedelta(hours=hours_ago)).isoformat()


# 与生产 schema 对齐的最小表结构（init_db 未建 reply_log / email_tracking_messages）
_EXTRA_TABLES = """
CREATE TABLE IF NOT EXISTS reply_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER, email TEXT, reply_received_at TEXT, reply_type TEXT,
    summary TEXT, suggested_action TEXT, raw_subject TEXT, processed_at TEXT
);
CREATE TABLE IF NOT EXISTS email_tracking_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_message_id TEXT, plan_entry_id TEXT, lead_id INTEGER,
    organization_key TEXT, send_log_id INTEGER, smtp_message_id TEXT,
    token_hash TEXT, status TEXT, tracking_base_url TEXT, created_at TEXT,
    activated_at TEXT, disabled_at TEXT, is_test INTEGER
);
CREATE TABLE IF NOT EXISTS unmatched_dsn (
    id INTEGER PRIMARY KEY AUTOINCREMENT, raw_message_id TEXT,
    final_recipient TEXT, original_recipient TEXT, x_failed_recipients TEXT,
    diagnostic_code TEXT, status_code TEXT, original_message_id TEXT,
    original_subject TEXT, original_sent_at TEXT, detected_at TEXT,
    processed_at TEXT, matched_send_log_id INTEGER, notes TEXT
);
"""


class BaseResultSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.sqlite")
        self.old_db_path = bd_db.DB_PATH
        self.old_rrs_out = rrs.OUT_DIR
        self.old_drs_out = drs.OUT_DIR
        bd_db.DB_PATH = self.db_path
        rrs.OUT_DIR = self.tmp.name
        drs.OUT_DIR = self.tmp.name
        bd_db.init_db()

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.executescript(_EXTRA_TABLES)
            # 兼容旧 schema：为 send_log 补列
            cols = {r[1] for r in cur.execute("PRAGMA table_info(send_log)")}
            if "message_id" not in cols:
                cur.execute("ALTER TABLE send_log ADD COLUMN message_id TEXT")
            if "tracking_token_hash" not in cols:
                cur.execute("ALTER TABLE send_log ADD COLUMN tracking_token_hash TEXT")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        bd_db.DB_PATH = self.old_db_path
        rrs.OUT_DIR = self.old_rrs_out
        drs.OUT_DIR = self.old_drs_out
        sys.modules.pop("bounce_pipeline", None)
        self.tmp.cleanup()

    # ---- 数据构造工具 ----

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _set_config(self, key: str, value: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, _now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def _seed_basic_tables(self, send_rows: int = 3, reply_rows: int = 2,
                           unsub_rows: int = 1, tracking_total: int = 4,
                           tracking_matched: int = 2, send_date: str = "2026-08-05") -> None:
        """写入业务表测试数据，返回最后一个 send_log.id（供 tracking 关联）。"""
        conn = self._conn()
        try:
            cur = conn.cursor()
            last_send_id = None
            for i in range(send_rows):
                cur.execute(
                    "INSERT INTO send_log (lead_id, email, subject, status, sent_at, message_id) "
                    "VALUES (?, ?, ?, 'sent', ?, ?)",
                    (i + 1, f"lead{i + 1}@example.com", "subj", f"{send_date} 10:0{i}:00", f"msg-{i + 1}"),
                )
                last_send_id = cur.lastrowid
            # bounce_log 表分类数据
            for _ in range(2):
                cur.execute(
                    "INSERT INTO bounce_log (email, bounce_type, bounce_received_at) "
                    "VALUES ('b@example.com', 'domain_invalid', ?)", (_now_iso(),)
                )
            cur.execute(
                "INSERT INTO bounce_log (email, bounce_type, bounce_received_at) "
                "VALUES ('b2@example.com', 'policy', ?)", (_now_iso(),)
            )
            # reply_log
            for i in range(reply_rows):
                cur.execute(
                    "INSERT INTO reply_log (email, reply_received_at, reply_type) "
                    "VALUES (?, ?, 'human')", (f"r{i}@example.com", _now_iso())
                )
            # suppression_list
            for i in range(unsub_rows):
                cur.execute(
                    "INSERT INTO suppression_list (email, reason) VALUES (?, 'unsubscribe_request')",
                    (f"u{i}@example.com",),
                )
            cur.execute(
                "INSERT INTO suppression_list (email, reason) VALUES ('other@example.com', 'manual')"
            )
            # email_tracking_messages：tracking_matched 条关联到 send_log
            first_send = last_send_id - (tracking_matched - 1) if last_send_id else None
            for i in range(tracking_total):
                sid = (first_send + i) if (first_send is not None and i < tracking_matched) else None
                cur.execute(
                    "INSERT INTO email_tracking_messages (send_log_id, smtp_message_id, token_hash) "
                    "VALUES (?, ?, ?)",
                    (sid, f"smtp-{i + 1}" if i < tracking_matched else None, f"tok{i + 1}"),
                )
            conn.commit()
            return last_send_id
        finally:
            conn.close()

    def _all_ok_steps(self) -> dict:
        return {
            "tracking_sync": {"ok": True, "at": _now_iso(), "data": {
                "total": 4, "matched": 2, "hit_rate": 50.0}},
            "bounce_scan": {"ok": True, "at": _now_iso(), "data": {"total": 3}},
            "reply_scan": {"ok": True, "at": _now_iso(), "data": {"total_replies": 2}},
            "unsubscribe_scan": {"ok": True, "at": _now_iso(), "data": {"unsubscribe_total": 1}},
        }


class ReportFreshSyncTests(BaseResultSyncTest):
    """场景①：sync 新鲜且成功 -> 报告正常显示数字。"""

    def test_fresh_success_shows_numbers(self):
        self._set_config("sync_0845_last_success_at", _now_iso())
        self._set_config("sync_0845_steps", json.dumps(self._all_ok_steps(), ensure_ascii=False))
        self._set_config("last_send_date", "2026-08-05")
        self._set_config("last_imap_scan_result", json.dumps({
            "domain_invalid": 2, "mailbox_invalid": 0, "policy_bounce": 1,
            "soft_bounce": 0, "unmatched_dsn": 0,
        }))
        self._seed_basic_tables()

        state = drs.read_synced_state()
        report = drs.generate_report(state)

        self.assertNotIn("DATA STALE", report)
        self.assertNotIn("BOUNCE SCAN FAILED", report)
        self.assertIn("| Sends (2026-08-05) | 3 |", report)
        self.assertIn("| Bounce total (imap scan) | 3 |", report)
        self.assertIn("|  - domain_invalid | 2 |", report)
        self.assertIn("| Replies | 2 |", report)
        self.assertIn("| Unsubscribes | 1 |", report)
        self.assertIn("| Tracking hit rate | 50.0% (2/4) |", report)


class ReportStaleSyncTests(BaseResultSyncTest):
    """场景②：sync 过期 -> 显示 DATA STALE 且无 Bounce=0 / Reply=0。"""

    def test_stale_shows_data_stale_and_no_zero(self):
        self._set_config("sync_0845_last_success_at", _old_iso(hours_ago=5))
        self._set_config("sync_0845_steps", json.dumps(self._all_ok_steps(), ensure_ascii=False))
        self._seed_basic_tables()

        state = drs.read_synced_state()
        report = drs.generate_report(state)

        self.assertIn("DATA STALE", report)
        self.assertIn("LAST SUCCESSFUL SYNC", report)
        self.assertIn("UNAVAILABLE", report)
        # 不得出现任何"Bounce 为 0"或"Reply 为 0"的展示
        self.assertNotIn("Bounce total (imap scan)", report)
        self.assertNotIn("Bounce=0", report)
        self.assertNotIn("Reply=0", report)
        self.assertIn("| Bounce total | UNAVAILABLE (stale) |", report)
        self.assertIn("| Replies | UNAVAILABLE (stale) |", report)

    def test_missing_sync_is_stale(self):
        # 从不运行过同步：无 sync_0845_last_success_at
        self._seed_basic_tables()
        state = drs.read_synced_state()
        report = drs.generate_report(state)
        self.assertIn("DATA STALE", report)
        self.assertIn("LAST SUCCESSFUL SYNC: NEVER", report)
        # 从未运行过 sync：不虚构 step 失败告警，由 DATA STALE 覆盖
        self.assertNotIn("BOUNCE SCAN FAILED", report)
        self.assertNotIn("REPLY SCAN FAILED", report)
        self.assertIn("Bounce 数据不可用：bounce_scan 未运行（无同步记录）", report)


class ReportBounceFailedTests(BaseResultSyncTest):
    """场景③：bounce step 失败 -> BOUNCE SCAN FAILED，Bounce 显示 UNAVAILABLE。"""

    def test_bounce_failed_shows_warning(self):
        steps = self._all_ok_steps()
        steps["bounce_scan"] = {"ok": False, "at": _now_iso(),
                                "error": "run_scan_and_writeback failed: mock boom"}
        self._set_config("sync_0845_last_success_at", _now_iso())
        self._set_config("sync_0845_steps", json.dumps(steps, ensure_ascii=False))
        self._seed_basic_tables()

        state = drs.read_synced_state()
        report = drs.generate_report(state)

        self.assertIn("BOUNCE SCAN FAILED", report)
        self.assertNotIn("DATA STALE", report)  # 同步本身新鲜
        self.assertIn("LAST SUCCESSFUL SYNC", report)
        self.assertIn("mock boom", report)
        self.assertIn("| Bounce total | UNAVAILABLE |", report)
        # 禁止 Bounce=0 展示
        self.assertNotIn("Bounce total (imap scan)", report)
        # reply step 正常：在非 stale 告警下仍显示真实数字
        self.assertIn("| Replies | 2 |", report)


class RunSyncDegradeTests(BaseResultSyncTest):
    """run_sync() 的 bounce_pipeline import 失败降级路径。"""

    def test_run_sync_bounce_import_failure_degrades(self):
        # 使 from bounce_pipeline import ... 抛 ImportError
        sys.modules["bounce_pipeline"] = None
        self._seed_basic_tables()

        summary = rrs.run_sync()

        self.assertFalse(summary["all_ok"])
        bounce = summary["steps"]["bounce_scan"]
        self.assertFalse(bounce["ok"])
        self.assertIn("import failed", bounce["error"])
        self.assertTrue(bounce["data"].get("degraded"))
        # 其它步骤不受阻塞
        self.assertTrue(summary["steps"]["tracking_sync"]["ok"])
        self.assertTrue(summary["steps"]["reply_scan"]["ok"])
        self.assertTrue(summary["steps"]["unsubscribe_scan"]["ok"])

        # 状态已写入 system_config
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT value FROM system_config WHERE key='sync_0845_last_success_at'"
            ).fetchone()
            self.assertIsNotNone(row)
            row = conn.execute(
                "SELECT value FROM system_config WHERE key='sync_0845_steps'"
            ).fetchone()
            saved = json.loads(row[0])
            self.assertFalse(saved["bounce_scan"]["ok"])
            self.assertTrue(saved["reply_scan"]["ok"])
        finally:
            conn.close()

        # 摘要文件已写出
        out_path = os.path.join(self.tmp.name, "result_recovery_sync_" + rrs.today_str() + ".json")
        self.assertTrue(os.path.exists(out_path))

    def test_run_sync_bounce_success(self):
        # 用假模块替换 bounce_pipeline，验证成功路径
        fake = types.ModuleType("bounce_pipeline")
        fake.run_scan_and_writeback = lambda: {"total": 7, "domain_invalid": 1}
        sys.modules["bounce_pipeline"] = fake
        self._seed_basic_tables()

        summary = rrs.run_sync()

        self.assertTrue(summary["all_ok"])
        self.assertTrue(summary["steps"]["bounce_scan"]["ok"])
        self.assertEqual(summary["steps"]["bounce_scan"]["data"]["total"], 7)


class ReadSyncStateCheckTests(BaseResultSyncTest):
    """--check 只读模式：read_sync_state() 判断 data_stale。"""

    def test_check_fresh(self):
        self._set_config("sync_0845_last_success_at", _now_iso())
        self._set_config("sync_0845_steps", json.dumps(self._all_ok_steps(), ensure_ascii=False))
        state = rrs.read_sync_state()
        self.assertTrue(state["fresh"])
        self.assertFalse(state["data_stale"])

    def test_check_stale_when_missing(self):
        state = rrs.read_sync_state()
        self.assertFalse(state["fresh"])
        self.assertTrue(state["data_stale"])
        self.assertIsNone(state["sync_0845_last_success_at"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
