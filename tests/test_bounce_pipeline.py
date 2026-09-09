"""P0 退信自动回流 —— bounce_pipeline 单元测试。

用临时 sqlite 内存库，不碰生产 DB。覆盖：
  - parse_bounce_email：4 种 MIME part 解析
  - classify_bounce：5 种分类
  - record_bounce：幂等 + 各类型 leads 回写
  - record_unmatched_dsn：send_log 匹配 / 未匹配兜底
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest

# 保证能 import 项目根目录下的模块
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bounce_pipeline as bp  # noqa: E402
import bd_db  # noqa: E402


_CREATE_SQL = """
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT,
    email TEXT,
    status TEXT DEFAULT 'new',
    email_sendable INTEGER DEFAULT 1,
    follow_up_eligible INTEGER DEFAULT 1,
    contact_recovery_required INTEGER DEFAULT 0,
    delivery_policy_review INTEGER DEFAULT 0,
    deferred_until TEXT,
    bounced_at TEXT,
    campaign TEXT,
    organization_key TEXT DEFAULT '',
    location_key TEXT DEFAULT ''
);
CREATE TABLE bounce_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER, email TEXT, domain TEXT, campaign TEXT,
    bounce_received_at TEXT, status_code TEXT, diagnostic_code TEXT,
    bounce_type TEXT, raw_message_subject TEXT, recommended_action TEXT,
    processed_at TEXT
);
CREATE TABLE unmatched_dsn (
    id INTEGER PRIMARY KEY AUTOINCREMENT, raw_message_id TEXT,
    final_recipient TEXT, original_recipient TEXT, x_failed_recipients TEXT,
    diagnostic_code TEXT, status_code TEXT, original_message_id TEXT,
    original_subject TEXT, original_sent_at TEXT, detected_at TEXT,
    processed_at TEXT, matched_send_log_id INTEGER, notes TEXT
);
CREATE TABLE contact_recovery (
    id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, org_name TEXT,
    email TEXT, domain TEXT, reason TEXT, status TEXT DEFAULT 'pending',
    created_at TEXT, updated_at TEXT
);
CREATE TABLE send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, email TEXT,
    subject TEXT, status TEXT, error_message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, message_id TEXT
);
"""


def _make_conn():
    """构造一个完整表结构的内存 sqlite 连接。"""
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.executescript(_CREATE_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# 构造测试用 DSN 原始邮件（4 种 MIME part）
# ---------------------------------------------------------------------------

def _four_part_dsn(recipient="info@example.com"):
    """含 text/plain + text/html + message/delivery-status + message/rfc822。"""
    domain = recipient.split("@", 1)[1]
    return (
        "From: MAILER-DAEMON@mx.qq.com\r\n"
        "To: agent@roktandrazo.com\r\n"
        "Subject: Undeliverable: Your message\r\n"
        "Date: Thu, 6 Aug 2026 10:00:00 +0800\r\n"
        "Message-ID: <dsn-four-part@qq.com>\r\n"
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/report; report-type=delivery-status;\r\n'
        '    boundary="four-part-boundary"\r\n'
        "\r\n"
        "--four-part-boundary\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "This is the mail system at host mx.qq.com.\r\n"
        "\r\n"
        f"<{recipient}>: host mx.{domain} said:\r\n"
        "    550 5.1.1 user unknown\r\n"
        "\r\n"
        "--four-part-boundary\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        f"<html><body>Delivery to <b>{recipient}</b> failed.<br>\r\n"
        "Diagnostic: mailbox does not exist.</body></html>\r\n"
        "\r\n"
        "--four-part-boundary\r\n"
        "Content-Type: message/delivery-status\r\n"
        "\r\n"
        "Reporting-MTA: dns; mx.qq.com\r\n"
        "\r\n"
        f"Final-Recipient: rfc822; {recipient}\r\n"
        f"Original-Recipient: rfc822; {recipient}\r\n"
        "Action: failed\r\n"
        "Status: 5.1.1\r\n"
        "Diagnostic-Code: smtp; 550 5.1.1 user unknown\r\n"
        "\r\n"
        "--four-part-boundary\r\n"
        "Content-Type: message/rfc822\r\n"
        "\r\n"
        "From: Ian <agent@roktandrazo.com>\r\n"
        f"To: {recipient}\r\n"
        "Subject: Original subject line here\r\n"
        "Date: Wed, 5 Aug 2026 09:30:00 +0800\r\n"
        "Message-ID: <orig-four-part@roktandrazo.com>\r\n"
        "\r\n"
        "original body\r\n"
        "--four-part-boundary--\r\n"
    )


class TestParseBounce(unittest.TestCase):
    def test_parse_four_mime_parts(self):
        parsed = bp.parse_bounce_email(_four_part_dsn().encode("utf-8"))
        self.assertEqual(parsed["final_recipient"], "info@example.com")
        self.assertEqual(parsed["original_recipient"], "info@example.com")
        self.assertEqual(parsed["status_code"], "5.1.1")
        self.assertEqual(parsed["diagnostic_code"], "smtp; 550 5.1.1 user unknown")
        self.assertEqual(parsed["original_message_id"], "<orig-four-part@roktandrazo.com>")
        self.assertEqual(parsed["original_subject"], "Original subject line here")
        self.assertIn("Wed, 5 Aug 2026", parsed["original_sent_at"])
        self.assertIn("mail system at host", parsed["raw_body"])
        self.assertIn("mailbox does not exist", parsed["html_body"])

    def test_parse_html_fallback_email(self):
        raw = (
            "From: postmaster@mx.qq.com\r\n"
            "Subject: Delivery failure\r\n"
            "Message-ID: <dsn-html@qq.com>\r\n"
            "MIME-Version: 1.0\r\n"
            'Content-Type: multipart/alternative; boundary="b"\r\n'
            "\r\n"
            "--b\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            "\r\n"
            '<html><body>Failed to deliver to <a>user@nosuchhost.example</a>. '
            "Host not found.</body></html>\r\n"
            "--b--\r\n"
        )
        parsed = bp.parse_bounce_email(raw.encode("utf-8"))
        self.assertEqual(parsed["final_recipient"], "user@nosuchhost.example")
        # HTML 关键词兜底应产出诊断
        self.assertIsNotNone(parsed["diagnostic_code"])
        self.assertIn("Host not found", parsed["diagnostic_code"])

    def test_parse_original_recipient_prefers_delivery_status(self):
        raw = (
            "From: MAILER-DAEMON@mx.qq.com\r\n"
            "Subject: Undeliverable\r\n"
            "Message-ID: <dsn-2@qq.com>\r\n"
            "MIME-Version: 1.0\r\n"
            'Content-Type: multipart/report; report-type=delivery-status; boundary="x"\r\n'
            "\r\n"
            "--x\r\n"
            "Content-Type: message/delivery-status\r\n"
            "\r\n"
            "Final-Recipient: rfc822; final@dest.com\r\n"
            "X-Failed-Recipients: a@b.com, c@d.com\r\n"
            "Status: 5.7.1\r\n"
            "Diagnostic-Code: smtp; 550 5.7.1 relaying denied\r\n"
            "\r\n"
            "--x--\r\n"
        )
        parsed = bp.parse_bounce_email(raw.encode("utf-8"))
        self.assertEqual(parsed["final_recipient"], "final@dest.com")
        self.assertIn("a@b.com", parsed["x_failed_recipients"])
        self.assertIn("c@d.com", parsed["x_failed_recipients"])
        self.assertEqual(parsed["status_code"], "5.7.1")


class TestClassify(unittest.TestCase):
    def _c(self, diag, status=None, body=""):
        return bp.classify_bounce(diag, status, body)

    def test_domain_invalid(self):
        self.assertEqual(self._c("smtp; 550 type=MX: Host not found", "5.1.1"), "domain_invalid")
        self.assertEqual(self._c("dns; nxdomain", None), "domain_invalid")
        self.assertEqual(self._c("smtp; domain does not exist", "5.4.4"), "domain_invalid")

    def test_mailbox_invalid(self):
        self.assertEqual(self._c("smtp; 550 5.1.1 user unknown", "5.1.1"), "mailbox_invalid")
        self.assertEqual(self._c("smtp; mailbox does not exist", None), "mailbox_invalid")
        self.assertEqual(self._c(None, "5.1.1"), "mailbox_invalid")

    def test_policy_bounce(self):
        self.assertEqual(self._c("smtp; 550 5.7.1 relaying denied", "5.7.1"), "policy_bounce")
        self.assertEqual(self._c("smtp; 554 5.7.1 recipient rejected", "5.7.1"), "policy_bounce")

    def test_soft_bounce(self):
        self.assertEqual(self._c("smtp; 421 4.4.1 try again later", "4.4.1"), "soft_bounce")
        self.assertEqual(self._c("smtp; mailbox full", None), "soft_bounce")
        self.assertEqual(self._c(None, "4.2.2"), "soft_bounce")

    def test_unresolved(self):
        self.assertEqual(self._c("smtp; 550 some unknown error", "5.5.0"), "unresolved")
        self.assertEqual(self._c(None, None, "no hints here"), "unresolved")


class TestRecordBounce(unittest.TestCase):
    def test_domain_invalid_writeback(self):
        conn = _make_conn()
        conn.execute(
            "INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
            (1, "Game Universe", "info@gameuniverse.com"),
        )
        conn.commit()
        res = bp.record_bounce(conn, 1, "info@gameuniverse.com", "domain_invalid",
                               "smtp; 550 type=MX: Host not found", "5.1.1")
        self.assertTrue(res["inserted"])
        lead = conn.execute("SELECT * FROM leads WHERE id=1").fetchone()
        self.assertEqual(lead[4], 0)  # email_sendable
        self.assertEqual(lead[5], 0)  # follow_up_eligible
        self.assertEqual(lead[6], 1)  # contact_recovery_required
        self.assertEqual(lead[3], "bounced")  # status
        cr = conn.execute("SELECT * FROM contact_recovery").fetchall()
        self.assertEqual(len(cr), 1)
        self.assertIn("domain_invalid", cr[0][5])
        conn.close()

    def test_idempotent_bounce_log(self):
        conn = _make_conn()
        conn.execute(
            "INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
            (1, "Game Universe", "info@gameuniverse.com"),
        )
        conn.commit()
        diag = "smtp; 550 type=MX: Host not found"
        bp.record_bounce(conn, 1, "info@gameuniverse.com", "domain_invalid", diag, "5.1.1")
        bp.record_bounce(conn, 1, "info@gameuniverse.com", "domain_invalid", diag, "5.1.1")
        rows = conn.execute("SELECT COUNT(*) FROM bounce_log").fetchone()[0]
        self.assertEqual(rows, 1)
        conn.close()

    def test_mailbox_invalid_writeback(self):
        conn = _make_conn()
        conn.execute(
            "INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
            (2, "Some Store", "buyer@example.com"),
        )
        conn.commit()
        bp.record_bounce(conn, 2, "buyer@example.com", "mailbox_invalid",
                         "smtp; 550 5.1.1 user unknown", "5.1.1")
        lead = conn.execute("SELECT * FROM leads WHERE id=2").fetchone()
        self.assertEqual(lead[4], 0)  # email_sendable
        self.assertEqual(lead[6], 1)  # contact_recovery_required
        # 仅停用当前邮箱，不判组织/域名级
        cr = conn.execute("SELECT * FROM contact_recovery WHERE lead_id=2").fetchall()
        self.assertEqual(len(cr), 1)
        conn.close()

    def test_policy_and_soft_writeback(self):
        conn = _make_conn()
        conn.execute("INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
                     (3, "Policy Store", "a@policy.com"))
        conn.execute("INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
                     (4, "Soft Store", "b@soft.com"))
        conn.commit()
        bp.record_bounce(conn, 3, "a@policy.com", "policy_bounce",
                         "smtp; 550 5.7.1 relaying denied", "5.7.1")
        lead3 = conn.execute("SELECT * FROM leads WHERE id=3").fetchone()
        self.assertEqual(lead3[7], 1)  # delivery_policy_review
        self.assertEqual(lead3[4], 1)  # email_sendable 仍保留
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM contact_recovery").fetchone()[0], 0)

        bp.record_bounce(conn, 4, "b@soft.com", "soft_bounce",
                         "smtp; 421 4.4.1 try again", "4.4.1")
        lead4 = conn.execute("SELECT * FROM leads WHERE id=4").fetchone()
        self.assertIsNotNone(lead4[8])  # deferred_until
        self.assertEqual(lead4[4], 1)  # email_sendable 不永久停用
        conn.close()


class TestUnmatchedDsn(unittest.TestCase):
    def test_unmatched_saved_without_lead(self):
        conn = _make_conn()
        parsed = bp.parse_bounce_email(_four_part_dsn("ghost@nolead.example").encode("utf-8"))
        result = bp.record_unmatched_dsn(conn, parsed)
        self.assertTrue(result["saved"])
        self.assertIsNone(result["matched_send_log_id"])
        self.assertTrue(result["unmatched"])
        self.assertIsNone(result["lead_id"])
        rows = conn.execute("SELECT * FROM unmatched_dsn").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "ghost@nolead.example")  # final_recipient
        self.assertIsNotNone(rows[0][11])  # processed_at
        # 未匹配到 lead，不写 bounce_log
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bounce_log").fetchone()[0], 0)
        conn.close()

    def test_matched_via_send_log(self):
        conn = _make_conn()
        conn.execute("INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
                     (10, "Lead Co", "info@example.com"))
        conn.execute(
            "INSERT INTO send_log (id, lead_id, email, subject, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (100, 10, "info@example.com", "Subject", "sent"),
        )
        conn.commit()
        parsed = bp.parse_bounce_email(_four_part_dsn().encode("utf-8"))
        result = bp.record_unmatched_dsn(conn, parsed)
        self.assertEqual(result["matched_send_log_id"], 100)
        self.assertEqual(result["lead_id"], 10)
        self.assertFalse(result["unmatched"])
        row = conn.execute("SELECT * FROM unmatched_dsn").fetchone()
        self.assertEqual(row[12], 100)  # matched_send_log_id
        bl = conn.execute("SELECT * FROM bounce_log").fetchall()
        self.assertEqual(len(bl), 1)
        self.assertEqual(bl[0][1], 10)  # lead_id
        conn.close()

    def test_matched_via_lead_email(self):
        conn = _make_conn()
        conn.execute("INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
                     (20, "Direct Co", "info@example.com"))
        conn.commit()
        parsed = bp.parse_bounce_email(_four_part_dsn().encode("utf-8"))
        result = bp.record_unmatched_dsn(conn, parsed)
        # send_log 无记录，但 leads.email 命中 → 走 record_bounce
        self.assertEqual(result["lead_id"], 20)
        self.assertIsNone(result["matched_send_log_id"])
        bl = conn.execute("SELECT * FROM bounce_log").fetchall()
        self.assertEqual(len(bl), 1)
        self.assertEqual(bl[0][1], 20)
        conn.close()

    def test_self_test_samples_domain_invalid(self):
        conn = _make_conn()
        for i, rec in enumerate(bp._SAMPLE_RECIPIENTS, start=1):
            conn.execute("INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
                         (100 + i, rec.split("@")[0], rec))
        conn.commit()
        parsed_list = [bp.parse_bounce_email(raw.encode("utf-8")) for raw in bp._SAMPLE_DSNS]
        for p in parsed_list:
            bt = bp.classify_bounce(p["diagnostic_code"], p["status_code"], p["raw_body"])
            self.assertEqual(bt, "domain_invalid")
        for p in parsed_list:
            bp.record_unmatched_dsn(conn, p)
        # 幂等：再跑一遍
        for p in parsed_list:
            bp.record_unmatched_dsn(conn, p)
        for rec in bp._SAMPLE_RECIPIENTS:
            n = conn.execute("SELECT COUNT(*) FROM bounce_log WHERE email=?", (rec,)).fetchone()[0]
            self.assertEqual(n, 1, f"{rec} 的 bounce_log 应只有 1 条")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM contact_recovery").fetchone()[0], 3)
        conn.close()


class TestBdDbHelpers(unittest.TestCase):
    """验证 bd_db 新增的 4 个辅助函数（monkeypatch DB_PATH 到临时文件，不碰生产库）。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="bd_db_test_")
        self._db_path = os.path.join(self._tmpdir, "test.db")
        conn = sqlite3.connect(self._db_path)
        conn.executescript(_CREATE_SQL)
        conn.commit()
        conn.close()
        self._orig_db_path = bd_db.DB_PATH
        bd_db.DB_PATH = self._db_path

    def tearDown(self):
        bd_db.DB_PATH = self._orig_db_path
        for suffix in ("", "-wal", "-shm"):
            p = self._db_path + suffix
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        try:
            os.rmdir(self._tmpdir)
        except OSError:
            pass

    def test_record_bounce_log_entry_idempotent(self):
        conn = sqlite3.connect(self._db_path)
        conn.execute("INSERT INTO leads (id, store_name, email) VALUES (?, ?, ?)",
                     (1, "Co", "a@b.com"))
        conn.commit()
        conn.close()
        first = bd_db.record_bounce_log_entry(
            1, "a@b.com", "domain_invalid", "type=MX: Host not found", "5.1.1")
        second = bd_db.record_bounce_log_entry(
            1, "a@b.com", "domain_invalid", "type=MX: Host not found", "5.1.1")
        self.assertEqual(first, second)  # 幂等：返回同一行 id
        conn = sqlite3.connect(self._db_path)
        n = conn.execute("SELECT COUNT(*) FROM bounce_log").fetchone()[0]
        conn.close()
        self.assertEqual(n, 1)

    def test_unmatched_dsn_count_and_contact_recovery_helpers(self):
        conn = sqlite3.connect(self._db_path)
        conn.execute("INSERT INTO unmatched_dsn (final_recipient) VALUES (?)", ("x@y.com",))
        conn.execute(
            "INSERT INTO contact_recovery (lead_id, org_name, email, domain, reason, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', 'now', 'now')",
            (1, "Co", "a@b.com", "b.com", "domain_invalid: test"))
        conn.commit()
        conn.close()

        self.assertEqual(bd_db.get_unmatched_dsn_count(), 1)
        pending = bd_db.list_contact_recovery(limit=10)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["email"], "a@b.com")
        self.assertEqual(pending[0]["status"], "pending")

        rec_id = pending[0]["id"]
        bd_db.mark_contact_recovery_resolved(rec_id)
        pending2 = bd_db.list_contact_recovery(limit=10)
        self.assertEqual(len(pending2), 0)  # 已 resolve，不再出现在 pending

    def test_helpers_accept_external_conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.execute("INSERT INTO unmatched_dsn (final_recipient) VALUES (?)", ("z@y.com",))
        conn.commit()
        # get_unmatched_dsn_count 支持外部传入 conn
        self.assertEqual(bd_db.get_unmatched_dsn_count(conn=conn), 1)
        conn.close()


class TestPollerStatus(unittest.TestCase):
    """验证 poller 状态文件写入逻辑（临时文件，不影响真实 output/）。"""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="poller_status_test_")
        self._status_path = os.path.join(self._tmpdir, "status.json")
        self._orig = bp.POLLER_STATUS_FILE
        bp.POLLER_STATUS_FILE = self._status_path

    def tearDown(self):
        bp.POLLER_STATUS_FILE = self._orig
        try:
            os.remove(self._status_path)
            os.rmdir(self._tmpdir)
        except OSError:
            pass

    def test_success_resets_failures_and_preserves_other_keys(self):
        with open(self._status_path, "w", encoding="utf-8") as f:
            f.write('{"status": "alive", "jobs": {"other": {"x": 1}}}')
        bp._write_poller_status(success=True)
        data = json.loads(open(self._status_path, encoding="utf-8").read())
        self.assertEqual(data["status"], "alive")  # 保留既有字段
        self.assertEqual(data["jobs"]["other"]["x"], 1)
        bounce = data["jobs"]["bounce"]
        self.assertIsNotNone(bounce["last_success_at"])
        self.assertIsNone(bounce["error"])
        self.assertEqual(bounce["consecutive_failures"], 0)

    def test_failure_increments_consecutive_failures(self):
        bp._write_poller_status(success=True)
        bp._write_poller_status(success=False, error="boom")
        data = json.loads(open(self._status_path, encoding="utf-8").read())
        bounce = data["jobs"]["bounce"]
        self.assertEqual(bounce["error"], "boom")
        self.assertEqual(bounce["consecutive_failures"], 1)
        # 再失败一次 → 2；成功后归零
        bp._write_poller_status(success=False, error="boom2")
        data = json.loads(open(self._status_path, encoding="utf-8").read())
        self.assertEqual(data["jobs"]["bounce"]["consecutive_failures"], 2)
        bp._write_poller_status(success=True)
        data = json.loads(open(self._status_path, encoding="utf-8").read())
        self.assertEqual(data["jobs"]["bounce"]["consecutive_failures"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
