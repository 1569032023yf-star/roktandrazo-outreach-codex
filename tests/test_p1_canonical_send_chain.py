#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1.0 Canonical Send Chain 修复回归测试
=====================================
覆盖：
  A2  build_final_plan_entries 不再把 Strict A0 当唯一池——Broad Ready /
      Campaign Eligible 候选可通过正式 plan builder 进入 Final Send Plan。
  A3  create_send_authorization 创建瞬间 plan_entry_id == 真实 final_send_plan.id
      （禁止 lead_id → 事后 UPDATE 修正）。
  A4  send_one._commit_send_success 原子完成后，上层不得再次 INSERT send_log。
      1 次 SMTP Accepted = 恰好 1 条 send_log。
"""
import os
import sqlite3
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from outreach_control import build_final_plan_entries, is_strict_a0


def _mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE leads (
        id INTEGER PRIMARY KEY, store_name TEXT, email TEXT, state TEXT,
        status TEXT, confidence_score TEXT, auto_sendable INTEGER,
        email_verified_on_official_site INTEGER, email_source_type TEXT,
        official_website TEXT, evidence_url TEXT, evidence_snippet TEXT,
        evidence_method TEXT, unsubscribed_at TEXT, organization_key TEXT,
        recipient_timezone TEXT, timezone_status TEXT, icp_route TEXT,
        icp_priority TEXT, icp_reason TEXT, collected_at TEXT)""")
    return conn


def _lead(number: int = 1, **extra) -> dict:
    base = {
        "id": number, "email": f"contact{number}@example{number}.com",
        "store_name": f"Store {number}", "status": "new",
        "confidence_score": "B", "auto_sendable": 1,
        "email_verified_on_official_site": 1,
        "email_source_type": "official_page_visible",
        "official_website": f"https://example{number}.com",
        "evidence_url": f"https://example{number}.com/contact",
        "evidence_snippet": "contact@example.com",
        "evidence_method": "official_contact_page",
        "email_subject": "Hello", "email_body": "Body",
    }
    base.update(extra)
    return base


class A2PlanBuilderTest(unittest.TestCase):
    """A2: 正式 plan builder 不再把 Strict A0 当唯一池。"""

    def test_broad_ready_candidate_passes_with_eligible_check(self):
        """Campaign Eligible 判定通过时，非 A0 候选也能进入 plan。"""
        eligible_check = lambda lead: lead["store_name"] == "Store 1"
        entries = build_final_plan_entries(
            [_lead(1, confidence_score="B")], "2026-08-13", "new_outreach",
            eligible_check=eligible_check,
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["lead_id"], 1)

    def test_eligible_check_rejects_non_matching(self):
        """eligible_check 拒绝时候选不进 plan。"""
        eligible_check = lambda lead: False
        entries = build_final_plan_entries(
            [_lead(1)], "2026-08-13", "new_outreach", eligible_check=eligible_check,
        )
        self.assertEqual(entries, [])

    def test_without_check_falls_back_to_strict_a0(self):
        """未注入 eligible_check 时保持历史字段级兜底（不降级安全）。"""
        # 非 A0（confidence=B）在无 eligible_check 时被兜底过滤
        self.assertEqual(build_final_plan_entries([_lead(1)], "2026-08-13", "new_outreach"), [])
        # A0 通过
        a0 = _lead(1, confidence_score="A")
        self.assertTrue(is_strict_a0(a0))
        self.assertEqual(len(build_final_plan_entries([a0], "2026-08-13", "new_outreach")), 1)

    def test_follow_up_unaffected(self):
        """follow_up 不受 new_outreach 资格判定影响。"""
        entries = build_final_plan_entries([_lead(2)], "2026-08-13", "follow_up")
        self.assertEqual(len(entries), 1)


class A3AuthorizationTest(unittest.TestCase):
    """A3: create_send_authorization 创建瞬间 plan_entry_id == final_send_plan.id。"""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "test.db")
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
        CREATE TABLE final_send_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id TEXT, lead_id INTEGER,
            recipient_email TEXT, status TEXT, outreach_batch_date TEXT);
        CREATE TABLE send_authorizations (
            authorization_id TEXT PRIMARY KEY, plan_id TEXT, outreach_batch_date TEXT,
            plan_entries_hash TEXT, approved_entry_count INTEGER, database_sha256 TEXT,
            preflight_status TEXT, approved_at TEXT, expires_at TEXT, approved_by TEXT,
            status TEXT);
        CREATE TABLE send_authorization_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, authorization_id TEXT,
            plan_entry_id INTEGER, lead_id INTEGER, recipient_email TEXT,
            entry_hash TEXT, status TEXT, consumed_at TEXT);
        """)
        # 插入真实 fsp.id（显式指定，使 fsp.id 与 lead_id 不同，验证用的是 fsp.id 而非 lead_id）
        for lid, email in [(101, "a@example1.com"), (102, "b@example2.com")]:
            conn.execute(
                "INSERT INTO final_send_plan (id, plan_id, lead_id, recipient_email, status, outreach_batch_date) "
                "VALUES (?, 'plan_x', ?, ?, 'planned', '2026-08-13')",
                (lid - 100, lid, email))
        conn.commit()
        self.conn = conn

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_plan_entry_id_is_real_fsp_id_at_creation(self):
        """创建瞬间 plan_entry_id 必须是真实 final_send_plan.id。"""
        from bd_sender import create_send_authorization

        rows = self.conn.execute("SELECT id, lead_id, recipient_email FROM final_send_plan").fetchall()
        planned_entries = [
            {"lead_id": r[1], "recipient_email": r[2], "message_type": "new_outreach",
             "final_plan_entry_id": r[0]}
            for r in rows
        ]
        auth = create_send_authorization(
            "plan_x", "2026-08-13", planned_entries,
            preflight_passed=True, db_path=self.db_path,
        )
        entries = self.conn.execute(
            "SELECT plan_entry_id, lead_id FROM send_authorization_entries WHERE authorization_id=?",
            (auth["authorization_id"],),
        ).fetchall()
        fsp_ids = {r[0] for r in self.conn.execute("SELECT id FROM final_send_plan").fetchall()}
        for peid, lid in entries:
            self.assertIn(peid, fsp_ids, f"plan_entry_id {peid} is not a real final_send_plan.id")

    def test_missing_real_fsp_id_fails_closed(self):
        """缺少真实 fsp.id 时创建 authorization 必须 fail-closed。"""
        from bd_sender import create_send_authorization
        with self.assertRaises(ValueError):
            create_send_authorization(
                "plan_x", "2026-08-13",
                [{"lead_id": 1, "recipient_email": "a@example1.com",
                  "message_type": "new_outreach"}],  # 缺 final_plan_entry_id
                preflight_passed=True, db_path=self.db_path,
            )


class A4SingleWriteTest(unittest.TestCase):
    """A4: 一次 SMTP Accepted = 恰好一条 send_log。"""

    def test_persist_no_longer_duplicates_send_log(self):
        """_persist_final_plan_success 不再 INSERT send_log（send_one 已原子完成）。"""
        import daily_session
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            conn = sqlite3.connect(db)
            conn.executescript("""
            CREATE TABLE leads (id INTEGER PRIMARY KEY, followup_count INTEGER,
                last_followup_at TEXT, status TEXT);
            CREATE TABLE send_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT,
                subject TEXT, status TEXT, sent_at TEXT, message_type TEXT,
                outreach_batch_date TEXT, plan_entry_id INTEGER);
            CREATE TABLE final_send_plan (id INTEGER PRIMARY KEY, status TEXT,
                skip_reason TEXT, sent_at TEXT);
            """)
            conn.execute("INSERT INTO leads (id, followup_count) VALUES (1, NULL)")
            conn.execute("INSERT INTO final_send_plan (id, status) VALUES (10, 'planned')")
            conn.commit()

            # new_outreach：send_one._commit_send_success 已写 send_log，上层不再写
            daily_session._persist_final_plan_success(conn, {
                "id": 10, "lead_id": 1, "recipient_email": "a@example1.com",
                "subject": "Hi", "message_type": "new_outreach", "outreach_batch_date": "2026-08-13",
            }, {})
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM send_log").fetchone()[0], 0)
            # follow_up：只递增 followup_count，仍不写 send_log
            daily_session._persist_final_plan_success(conn, {
                "id": 10, "lead_id": 1, "recipient_email": "a@example1.com",
                "subject": "Hi", "message_type": "follow_up", "outreach_batch_date": "2026-08-13",
            }, {})
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM send_log").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT followup_count FROM leads WHERE id=1").fetchone()[0], 1)
            conn.close()

    def test_source_no_duplicate_send_log_insert_in_persist(self):
        """静态断言：_persist_final_plan_success 中不再有 INSERT INTO send_log。"""
        src = Path(PROJECT_ROOT, "daily_session.py").read_text(encoding="utf-8")
        fn_body = src.split("def _persist_final_plan_success", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("INSERT INTO send_log", fn_body)

    def test_commit_send_success_is_single_write_authority(self):
        """静态断言：send_log 写入唯一权威仍在 bd_sender._commit_send_success。"""
        src = Path(PROJECT_ROOT, "bd_sender.py").read_text(encoding="utf-8")
        fn_body = src.split("def _commit_send_success", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("INSERT INTO send_log", fn_body)


if __name__ == "__main__":
    unittest.main()
