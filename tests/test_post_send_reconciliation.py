"""Post-Send Reconciliation 单测。

覆盖 4 种场景：
  1) 完美对账（pass）
  2) consumed_but_no_send_log
  3) SMTP_accepted_but_missing_log
  4) duplicate_send

每个场景都验证 reconcile_batch 识别对应异常，并验证 mark_reconciliation_passed /
mark_reconciliation_failed 正确写入 system_config 与 output JSON。
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

# 允许直接从项目根目录 python tests/test_post_send_reconciliation.py 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import post_send_reconciliation as psr


def _create_schema(conn):
    """构造与真实库一致的测试表结构（仅对账用到的表）。"""
    conn.executescript("""
    CREATE TABLE final_send_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT, lead_id INTEGER, recipient_email TEXT, company_name TEXT,
        customer_type TEXT, lead_segment TEXT, template_id TEXT,
        source_city TEXT, source_state TEXT, evidence_url TEXT,
        hygiene_passed_at TEXT, message_type TEXT, outreach_batch_date TEXT,
        planned_sequence INTEGER, subject TEXT, body_text TEXT, body_html TEXT,
        status TEXT, skip_reason TEXT, sent_at TEXT, created_at TEXT
    );
    CREATE TABLE send_authorizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        authorization_id TEXT, plan_id TEXT, outreach_batch_date TEXT,
        plan_entries_hash TEXT, approved_entry_count INTEGER, database_sha256 TEXT,
        preflight_status TEXT, approved_at TEXT, expires_at TEXT, approved_by TEXT,
        consumed_at TEXT, status TEXT, created_at TEXT
    );
    CREATE TABLE send_authorization_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        authorization_id TEXT, plan_entry_id INTEGER, lead_id INTEGER,
        recipient_email TEXT, entry_hash TEXT, consumed_at TEXT, status TEXT
    );
    CREATE TABLE send_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER, email TEXT, subject TEXT, status TEXT, error_message TEXT,
        sent_at TEXT, message_id TEXT, template_id TEXT, customer_type TEXT,
        routing_reason TEXT, batch_id TEXT, source_platform TEXT,
        message_type TEXT, outreach_batch_date TEXT, plan_entry_id INTEGER,
        tracking_token_hash TEXT
    );
    CREATE TABLE email_tracking_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_message_id TEXT, plan_entry_id TEXT, lead_id INTEGER,
        organization_key TEXT, send_log_id INTEGER, smtp_message_id TEXT,
        token_hash TEXT, status TEXT, tracking_base_url TEXT,
        created_at TEXT, activated_at TEXT, disabled_at TEXT, is_test INTEGER
    );
    CREATE TABLE system_config (
        key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
    );
    """)


class BaseReconciliationTest(unittest.TestCase):
    BATCH = 'batch_001'
    LEADS = [
        (1, 'one@example.com'),
        (2, 'two@example.com'),
        (3, 'three@example.com'),
    ]

    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        _create_schema(self.conn)
        self.tmp = tempfile.TemporaryDirectory()
        self.output_dir = self.tmp.name

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _seed_plan(self, leads):
        """写 final_send_plan：全部 status='sent'。"""
        for i, (lid, email) in enumerate(leads, start=1):
            self.conn.execute(
                "INSERT INTO final_send_plan (plan_id, lead_id, recipient_email, company_name, "
                "message_type, outreach_batch_date, planned_sequence, status, subject, body_text, "
                "body_html, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (f'{self.BATCH}_{i:04d}', lid, email, f'Store {i}',
                 'new_outreach', self.BATCH, i, 'sent', f'Subject {i}', f'Body {i}', '',
                 '2026-08-05T00:00:00')
            )

    def _seed_auth(self, entries):
        """写 send_authorizations + send_authorization_entries。
        entries: [(lead_id, email, status), ...]
        """
        self.conn.execute(
            "INSERT INTO send_authorizations (authorization_id, plan_id, outreach_batch_date, "
            "plan_entries_hash, approved_entry_count, database_sha256, preflight_status, "
            "approved_at, expires_at, approved_by, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f'auth_{self.BATCH}', self.BATCH, self.BATCH, 'hash', len(entries), 'dbhash',
             'passed', '2026-08-05T00:00:00', '2026-08-05T00:15:00', 'system', 'approved')
        )
        for i, (lid, email, status) in enumerate(entries, start=1):
            self.conn.execute(
                "INSERT INTO send_authorization_entries (authorization_id, plan_entry_id, lead_id, "
                "recipient_email, entry_hash, consumed_at, status) VALUES (?,?,?,?,?,?,?)",
                (f'auth_{self.BATCH}', lid, lid, email, f'h{i}',
                 '2026-08-05T00:01:00' if status == 'consumed' else None, status)
            )

    def _seed_log(self, rows, tracking_token=None):
        """写 send_log。rows: [(lead_id, email), ...]，状态均为 sent；带可选 tracking token。"""
        for lid, email in rows:
            self.conn.execute(
                "INSERT INTO send_log (lead_id, email, subject, status, message_id, template_id, "
                "message_type, outreach_batch_date, plan_entry_id, tracking_token_hash) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (lid, email, f'Subject {lid}', 'sent',
                 f'mid-{lid}', 'tpl',
                 'new_outreach', self.BATCH, lid,
                 f'tok-{lid}' if tracking_token else None)
            )

    def _seed_tracking(self, leads):
        """写 email_tracking_messages，token 与 send_log 对应。"""
        for lid, _email in leads:
            self.conn.execute(
                "INSERT INTO email_tracking_messages (tracking_message_id, plan_entry_id, lead_id, "
                "token_hash, status, is_test) VALUES (?,?,?,?,?,?)",
                (f'tm_{lid}', str(lid), lid, f'tok-{lid}', 'active', 0)
            )
        self.conn.commit()

    def _get_config_status(self):
        row = self.conn.execute(
            "SELECT value FROM system_config WHERE key=?",
            (psr._config_key(self.BATCH),)
        ).fetchone()
        if not row:
            return None
        return json.loads(row[0])['status']

    def _report_file(self):
        return os.path.join(self.output_dir, f'post_send_reconciliation_{self.BATCH}.json')


class PerfectReconciliationTest(BaseReconciliationTest):
    """场景 1：三方完全一致，应为 PASSED。"""

    def test_perfect_batch_passes(self):
        leads = self.LEADS
        self._seed_plan(leads)
        self._seed_auth([(lid, email, 'consumed') for lid, email in leads])
        self._seed_log(leads, tracking_token=True)
        self._seed_tracking(leads)

        result = psr.reconcile_batch(self.conn, self.BATCH)

        self.assertEqual(result['verdict'], 'PASSED')
        self.assertEqual(result['total_issues'], 0)
        c = result['counts']
        self.assertEqual(c['plan_total'], 3)
        self.assertEqual(c['auth_total'], 1)
        self.assertEqual(c['consumed_total'], 3)
        self.assertEqual(c['smtp_accepted'], 3)
        self.assertEqual(c['send_log_delta'], 0)
        self.assertEqual(c['message_id_present_count'], 3)
        self.assertEqual(c['tracking_token_present_count'], 3)
        for cat in psr.ISSUE_CATEGORIES:
            self.assertEqual(result['issues'][cat]['count'], 0)

        # mark_reconciliation_passed 写 PASSED 状态与 output JSON
        psr.mark_reconciliation_passed(self.conn, self.BATCH,
                                       result=result, output_dir=self.output_dir)
        self.assertEqual(self._get_config_status(), 'PASSED')
        with open(self._report_file(), encoding='utf-8') as f:
            payload = json.load(f)
        self.assertEqual(payload['verdict'], 'PASSED')


class ConsumedButNoSendLogTest(BaseReconciliationTest):
    """场景 2：auth entry 已 consumed，但 send_log 缺一行。"""

    def test_consumed_but_no_send_log_detected(self):
        leads = self.LEADS
        self._seed_plan(leads)
        self._seed_auth([(lid, email, 'consumed') for lid, email in leads])
        # 只写前两行的 send_log，第三行缺失
        self._seed_log(leads[:2], tracking_token=True)
        self._seed_tracking(leads[:2])

        result = psr.reconcile_batch(self.conn, self.BATCH)

        self.assertEqual(result['verdict'], 'FAILED')
        self.assertEqual(result['issues']['consumed_but_no_send_log']['count'], 1)
        self.assertEqual(result['issues']['SMTP_accepted_but_missing_log']['count'], 1)
        # 现有 send_log 行都带有效 tracking token，故该项为 0
        self.assertEqual(result['issues']['tracking_token_missing']['count'], 0)
        self.assertEqual(result['counts']['send_log_delta'], -1)

        # mark_reconciliation_failed 写 FAILED 状态与 output JSON
        psr.mark_reconciliation_failed(self.conn, self.BATCH, result['issues'],
                                       result=result, output_dir=self.output_dir)
        self.assertEqual(self._get_config_status(), 'FAILED')
        with open(self._report_file(), encoding='utf-8') as f:
            payload = json.load(f)
        self.assertEqual(payload['verdict'], 'FAILED')
        self.assertEqual(payload['issues']['consumed_but_no_send_log']['count'], 1)


class SmtpAcceptedButMissingLogTest(BaseReconciliationTest):
    """场景 3：plan status='sent'，但 send_log 无对应行。"""

    def test_smtp_accepted_but_missing_log_detected(self):
        leads = self.LEADS
        self._seed_plan(leads)
        # 第三条 lead 连 auth entry 都没有（未授权、未消费、无日志）
        self._seed_auth([(lid, email, 'consumed') for lid, email in leads[:2]])
        self._seed_log(leads[:2], tracking_token=True)
        self._seed_tracking(leads[:2])

        result = psr.reconcile_batch(self.conn, self.BATCH)

        self.assertEqual(result['verdict'], 'FAILED')
        self.assertEqual(result['issues']['SMTP_accepted_but_missing_log']['count'], 1)
        # 第三条 plan 已 sent 但无 consumed entry，也计入 unconsumed_after_send
        self.assertEqual(result['issues']['unconsumed_after_send']['count'], 1)
        self.assertEqual(result['issues']['consumed_but_no_send_log']['count'], 0)

        psr.mark_reconciliation_failed(self.conn, self.BATCH, result['issues'],
                                       result=result, output_dir=self.output_dir)
        self.assertEqual(self._get_config_status(), 'FAILED')


class DuplicateSendTest(BaseReconciliationTest):
    """场景 4：同 lead_id+email 在 send_log 出现 >1 次。"""

    def test_duplicate_send_detected(self):
        leads = self.LEADS[:1]  # 只有 1 条 lead
        self._seed_plan(leads)
        self._seed_auth([(lid, email, 'consumed') for lid, email in leads])
        # 同一 lead 发了两次：send_log 两行
        self._seed_log(leads, tracking_token=True)
        self._seed_log(leads, tracking_token=True)
        self._seed_tracking(leads)

        result = psr.reconcile_batch(self.conn, self.BATCH)

        self.assertEqual(result['verdict'], 'FAILED')
        self.assertEqual(result['issues']['duplicate_send']['count'], 1)
        self.assertEqual(result['issues']['duplicate_send']['items'][0]['count'], 2)
        self.assertEqual(result['counts']['smtp_accepted'], 2)
        self.assertEqual(result['counts']['send_log_delta'], 1)

        psr.mark_reconciliation_failed(self.conn, self.BATCH, result['issues'],
                                       result=result, output_dir=self.output_dir)
        self.assertEqual(self._get_config_status(), 'FAILED')


if __name__ == '__main__':
    unittest.main()
