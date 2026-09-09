#!/usr/bin/env python3
"""P5 事务边界 + Authorization fail-closed 单测。

用内存 sqlite + mock SMTP，绝不真实发送。
覆盖场景：
  A. SMTP accepted → send_log 恰 1 条 / FSP='sent' / auth consumed / lead='sent'
  B. 第二次执行同 entry → skipped，SMTP 调用次数不增加
  C. SMTP rejected → 无该 plan_entry 的 send_log，FSP 不变，auth 不 consumed
  D. SMTP accepted 后 DB 异常 → 事务 rollback，可重发
  E. final_plan_entry_id 用 lead_id 冒充 → 被拒绝
  F. consume 第二次 → False
  G. sender copy 失败 → 仍 success，但返回 sender_copy_status='failed'
"""
import os
import sqlite3
import smtplib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bd_sender

ASIA_SH = timezone(timedelta(hours=8))

SCHEMA = """
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT NOT NULL,
    store_type TEXT,
    city TEXT,
    state TEXT,
    official_website TEXT,
    email TEXT,
    status TEXT DEFAULT 'new',
    confidence_score TEXT,
    auto_sendable INTEGER DEFAULT 0,
    email_verified_on_official_site INTEGER DEFAULT 0,
    email_source_type TEXT,
    sent_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    error_message TEXT,
    domain_hash TEXT
);
CREATE TABLE suppression_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    reason TEXT,
    added_at TIMESTAMP
);
CREATE TABLE final_send_plan (
    id INTEGER PRIMARY KEY,
    plan_id TEXT NOT NULL,
    lead_id INTEGER NOT NULL,
    recipient_email TEXT NOT NULL,
    company_name TEXT NOT NULL,
    customer_type TEXT,
    template_id TEXT,
    message_type TEXT NOT NULL,
    outreach_batch_date TEXT NOT NULL,
    planned_sequence INTEGER NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    skip_reason TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER,
    email TEXT,
    subject TEXT,
    status TEXT,
    error_message TEXT,
    sent_at TIMESTAMP,
    message_id TEXT,
    template_id TEXT,
    customer_type TEXT,
    routing_reason TEXT,
    batch_id TEXT,
    source_platform TEXT,
    message_type TEXT,
    outreach_batch_date TEXT,
    plan_entry_id INTEGER,
    tracking_token_hash TEXT
);
CREATE TABLE send_authorizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    authorization_id TEXT,
    plan_id TEXT,
    outreach_batch_date TEXT,
    plan_entries_hash TEXT,
    approved_entry_count INTEGER,
    database_sha256 TEXT,
    preflight_status TEXT,
    approved_at TEXT,
    expires_at TEXT,
    approved_by TEXT,
    consumed_at TEXT,
    status TEXT,
    created_at TEXT
);
CREATE TABLE send_authorization_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    authorization_id TEXT,
    plan_entry_id INTEGER,
    lead_id INTEGER,
    recipient_email TEXT,
    entry_hash TEXT,
    consumed_at TEXT,
    status TEXT
);
CREATE TABLE system_config (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
"""


class FakeServer:
    """SMTP mock：sendmail 计数，可配置抛异常。"""

    def __init__(self):
        self.sendmail_count = 0
        self.fail = None

    def sendmail(self, *args, **kwargs):
        self.sendmail_count += 1
        if self.fail is not None:
            raise self.fail
        return {}

    def quit(self):
        return None


class SharedConn:
    """包装共享内存连接：所有属性转发给内层，close() 置空避免误关共享库。"""

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __setattr__(self, name, value):
        setattr(self._inner, name, value)

    def close(self):
        return None


class FlakyProxy:
    """包装共享内存连接，commit() 抛错模拟 DB 故障；其余全部转发给内层。"""

    def __init__(self, inner):
        object.__setattr__(self, "_inner", inner)

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __setattr__(self, name, value):
        setattr(self._inner, name, value)

    def commit(self):
        raise sqlite3.OperationalError("simulated db failure on commit")

    def close(self):
        return None


class SenderTransactionTest(unittest.TestCase):
    FSP_ID = 100
    AUTH_ID = "auth_test"
    BATCH = "2026-08-07"
    RECIPIENT = "sales@example.com"
    SENDER = "sender@example.com"

    def setUp(self):
        # 共享内存连接：多函数各自 open/close，close 置空避免误关
        self._raw = sqlite3.connect(":memory:")
        self._raw.row_factory = sqlite3.Row
        self.conn = SharedConn(self._raw)
        self.conn.executescript(SCHEMA)
        self._seed()

        self.server = FakeServer()
        self._patchers = [
            mock.patch.object(bd_sender.sqlite3, "connect", return_value=self.conn),
            mock.patch.object(bd_sender, "get_test_config",
                              return_value={"test_mode": False, "test_email": ""}),
            mock.patch.object(bd_sender, "is_configured", return_value=True),
            mock.patch.object(bd_sender, "get_sender_info",
                              return_value={"name": "BD Sender", "email": self.SENDER}),
            mock.patch.object(bd_sender, "_create_connection", return_value=self.server),
            mock.patch.object(bd_sender, "_save_to_sent", return_value=(True, "")),
            mock.patch.object(bd_sender, "_activate_tracking", return_value=None),
        ]
        for p in self._patchers:
            p.start()
        self.addCleanup(self._stop_patchers)

    def _stop_patchers(self):
        for p in reversed(self._patchers):
            p.stop()
        self._raw.close()

    def _seed(self):
        c = self.conn
        c.execute(
            "INSERT INTO leads (id, store_name, email, status) VALUES (1, 'Store', ?, 'new')",
            (self.RECIPIENT,),
        )
        c.execute(
            """INSERT INTO final_send_plan
               (id, plan_id, lead_id, recipient_email, company_name, customer_type,
                template_id, message_type, outreach_batch_date, planned_sequence,
                subject, body_text, body_html, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'planned')""",
            (self.FSP_ID, "P1", 1, self.RECIPIENT, "Company", "retail", "tpl",
             "follow_up", self.BATCH, 1, "Premium puzzles", "We craft premium puzzles.", ""),
        )
        now = datetime.now(ASIA_SH)
        c.execute(
            """INSERT INTO send_authorizations
               (authorization_id, plan_id, outreach_batch_date, plan_entries_hash,
                approved_entry_count, database_sha256, preflight_status, approved_at,
                expires_at, approved_by, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,'approved')""",
            (self.AUTH_ID, "P1", self.BATCH, "h", 1, "d", "passed",
             now.isoformat(), (now + timedelta(hours=1)).isoformat(), "system"),
        )
        c.execute(
            """INSERT INTO send_authorization_entries
               (authorization_id, plan_entry_id, lead_id, recipient_email, entry_hash, status)
               VALUES (?,?,?,?,?, 'pending')""",
            (self.AUTH_ID, self.FSP_ID, 1, self.RECIPIENT, "eh"),
        )
        for k, v in (("manual_pause", "false"),
                     ("standing_authorization", "true"),
                     ("risk_gate_status", "clear")):
            c.execute("INSERT INTO system_config (key, value) VALUES (?,?)", (k, v))
        self.conn.commit()

    def _lead(self, **overrides):
        lead = {
            "id": 1,
            "email": self.RECIPIENT,
            "email_subject": "Premium puzzles",
            "email_body": "We craft premium puzzles.",
            "email_body_html": "",
            "email_body_html_no_pixel": "",
            "pixel_tracking": False,
            "message_type": "follow_up",
            "outreach_batch_date": self.BATCH,
            "final_plan_entry_id": self.FSP_ID,
            "authorization_id": self.AUTH_ID,
            "template_id": "tpl",
            "customer_type": "retail",
            "batch_id": "P1",
            "source_platform": "test",
        }
        lead.update(overrides)
        return lead

    # ── 场景 A：原子提交成功 ────────────────────────────
    def test_scenario_a_atomic_commit_success(self):
        result = bd_sender.send_one(self._lead())

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["plan_entry_id"], self.FSP_ID)
        self.assertTrue(result["plan_lead_id_matched"])

        rows = self.conn.execute("SELECT * FROM send_log").fetchall()
        self.assertEqual(len(rows), 1)
        log = rows[0]
        self.assertEqual(log["status"], "sent")
        self.assertEqual(log["plan_entry_id"], self.FSP_ID)
        self.assertEqual(log["authorization_id"], self.AUTH_ID)
        self.assertTrue(log["smtp_accepted_at"])          # P5 时间戳已写入
        self.assertTrue(log["sent_at"])

        fsp = self.conn.execute("SELECT status, sent_at FROM final_send_plan WHERE id=?",
                                (self.FSP_ID,)).fetchone()
        self.assertEqual(fsp["status"], "sent")
        self.assertTrue(fsp["sent_at"])

        entry = self.conn.execute(
            "SELECT status, consumed_at FROM send_authorization_entries WHERE plan_entry_id=?",
            (self.FSP_ID,)).fetchone()
        self.assertEqual(entry["status"], "consumed")
        self.assertTrue(entry["consumed_at"])

        lead = self.conn.execute("SELECT status FROM leads WHERE id=1").fetchone()
        self.assertEqual(lead["status"], "sent")

    # ── 场景 B：幂等防重 ────────────────────────────────
    def test_scenario_b_second_run_skips_without_smtp(self):
        first = bd_sender.send_one(self._lead())
        self.assertEqual(first["status"], "sent")
        smtp_calls_after_first = self.server.sendmail_count

        second = bd_sender.send_one(self._lead())

        self.assertFalse(second["success"])
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["message"], "ALREADY_SENT_SKIP")
        # SMTP 调用次数不增加（不再真实发送）
        self.assertEqual(self.server.sendmail_count, smtp_calls_after_first)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM send_log").fetchone()[0], 1)

    # ── 场景 C：SMTP rejected → 无 sent 记录 / FSP 不变 / auth 不 consumed ──
    def test_scenario_c_smtp_rejected_no_send_log(self):
        self.server.fail = smtplib.SMTPRecipientsRefused({self.RECIPIENT: (550, b"nope")})
        result = bd_sender.send_one(self._lead())

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM send_log WHERE plan_entry_id=?", (self.FSP_ID,)
            ).fetchone()[0], 0,
        )
        fsp = self.conn.execute("SELECT status FROM final_send_plan WHERE id=?",
                                (self.FSP_ID,)).fetchone()
        self.assertEqual(fsp["status"], "planned")
        entry = self.conn.execute(
            "SELECT status FROM send_authorization_entries WHERE plan_entry_id=?",
            (self.FSP_ID,)).fetchone()
        self.assertEqual(entry["status"], "pending")

    # ── 场景 D：SMTP accepted 后 DB 异常 → rollback → 可重发 ──
    def test_scenario_d_db_failure_rollback_then_retry_succeeds(self):
        with mock.patch.object(bd_sender.sqlite3, "connect", return_value=FlakyProxy(self.conn)):
            result = bd_sender.send_one(self._lead())

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "failed")
        # 事务已回滚：无 send_log、FSP 不变、auth 不 consumed、lead 不变
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM send_log").fetchone()[0], 0)
        fsp = self.conn.execute("SELECT status FROM final_send_plan WHERE id=?",
                                (self.FSP_ID,)).fetchone()
        self.assertEqual(fsp["status"], "planned")
        entry = self.conn.execute(
            "SELECT status FROM send_authorization_entries WHERE plan_entry_id=?",
            (self.FSP_ID,)).fetchone()
        self.assertEqual(entry["status"], "pending")
        lead = self.conn.execute("SELECT status FROM leads WHERE id=1").fetchone()
        self.assertEqual(lead["status"], "new")

        # 第二次执行（无 DB 故障）→ 可重发成功
        retry = bd_sender.send_one(self._lead())
        self.assertTrue(retry["success"])
        self.assertEqual(retry["status"], "sent")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM send_log").fetchone()[0], 1)
        self.assertGreaterEqual(self.server.sendmail_count, 2)  # 第二次确实又走了一次 SMTP

    # ── 场景 E：final_plan_entry_id 用 lead_id 冒充 → fail ──
    def test_scenario_e_lead_id_impersonation_rejected(self):
        result = bd_sender.send_one(self._lead(final_plan_entry_id=1))  # 1 是 lead.id，不是 FSP.id

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["message"], "Missing real final_send_plan.id")
        self.assertEqual(self.server.sendmail_count, 0)

    def test_scenario_e_non_int_or_empty_rejected(self):
        for bad in (None, "abc", True):
            with self.subTest(bad=bad):
                result = bd_sender.send_one(self._lead(final_plan_entry_id=bad))
                self.assertFalse(result["success"])
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["message"], "Missing real final_send_plan.id")

    def test_scenario_e_lead_id_mismatch_rejected(self):
        # FSP 存在但 lead_id 不匹配（lead id=1，而该 plan 属于 lead 2）
        self.conn.execute(
            "INSERT INTO final_send_plan "
            "(id, plan_id, lead_id, recipient_email, company_name, message_type, "
            "outreach_batch_date, planned_sequence, subject, body_text, body_html, status) "
            "VALUES (200, 'P2', 2, 'other@example.com', 'Co', 'follow_up', ?, 1, 's', 'b', '', 'planned')",
            (self.BATCH,),
        )
        result = bd_sender.send_one(self._lead(final_plan_entry_id=200))

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["message"], "Missing real final_send_plan.id")

    # ── 场景 F：consume 第二次 → False ──────────────────
    def test_scenario_f_consume_second_time_false(self):
        self.assertTrue(bd_sender.consume_authorization_entry(self.AUTH_ID, self.FSP_ID))
        self.assertFalse(bd_sender.consume_authorization_entry(self.AUTH_ID, self.FSP_ID))

        entry = self.conn.execute(
            "SELECT status FROM send_authorization_entries WHERE plan_entry_id=?",
            (self.FSP_ID,)).fetchone()
        self.assertEqual(entry["status"], "consumed")

    # ── 场景 G：sender copy 失败 → 仍 success，但记录失败 ──
    def test_scenario_g_sender_copy_failure_reported(self):
        def flaky_factory():
            if flaky_factory.n == 0:
                flaky_factory.n += 1
                return self.server
            raise RuntimeError("sender copy smtp down")
        flaky_factory.n = 0

        with mock.patch.object(bd_sender, "_create_connection", side_effect=flaky_factory):
            result = bd_sender.send_one(self._lead())

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["sender_copy_status"], "failed")
        self.assertIn("sender_copy", result["sender_copy_error"])
        # 客户发送结果不受影响
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM send_log").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
