"""P0 Dashboard 增强 — 指标计算函数单测。

覆盖核心语义：
  1) SMTP Accepted 不因 bounce 而减少（bounced 邮件 != 从未发送）
  2) Delivery Outcome 分类计数正确（bounce_log 按 bounce_type + unmatched_dsn + reply_log）
  3) Data Freshness 徽章 RED/YELLOW/GREEN 逻辑
  4) Plan/Auth/SMTP/send_log 对账批次解析（output JSON 与 system_config 两种来源）

只测计算函数，不渲染 HTML。
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


def _load_dashboard_module():
    """加载 bd_dashboard_v3.2.py（文件名含点，无法直接 import，用 importlib）。"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'bd_dashboard_v3.2.py')
    spec = importlib.util.spec_from_file_location('bd_dashboard_mod', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['bd_dashboard_mod'] = mod
    spec.loader.exec_module(mod)
    return mod


DASH = _load_dashboard_module()


def _make_mem_db():
    """构造与真实库一致的内存 sqlite（仅本测试用到的表）。"""
    conn = sqlite3.connect(':memory:')
    c = conn.cursor()
    c.execute(
        "CREATE TABLE send_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, "
        "subject TEXT, status TEXT, error_message TEXT, sent_at TEXT, message_id TEXT, "
        "template_id TEXT, customer_type TEXT, routing_reason TEXT, batch_id TEXT, "
        "source_platform TEXT, message_type TEXT, outreach_batch_date TEXT, "
        "plan_entry_id INTEGER, tracking_token_hash TEXT)")
    c.execute(
        "CREATE TABLE bounce_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, "
        "domain TEXT, campaign TEXT, bounce_received_at TEXT, status_code TEXT, "
        "diagnostic_code TEXT, bounce_type TEXT, raw_message_subject TEXT, "
        "recommended_action TEXT, processed_at TEXT)")
    c.execute(
        "CREATE TABLE reply_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, "
        "reply_received_at TEXT, reply_type TEXT, summary TEXT, suggested_action TEXT, "
        "raw_subject TEXT, processed_at TEXT)")
    c.execute(
        "CREATE TABLE unmatched_dsn (id INTEGER PRIMARY KEY, raw_message_id TEXT, "
        "final_recipient TEXT, original_recipient TEXT, x_failed_recipients TEXT, "
        "diagnostic_code TEXT, status_code TEXT, original_message_id TEXT, "
        "original_subject TEXT, original_sent_at TEXT, detected_at TEXT, processed_at TEXT, "
        "matched_send_log_id INTEGER, notes TEXT)")
    c.execute("CREATE TABLE system_config (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


class DeliveryOutcomeTest(unittest.TestCase):
    """SMTP Accepted 与 Delivery Outcome 分类统计。"""

    def setUp(self):
        self.conn = _make_mem_db()

    def tearDown(self):
        self.conn.close()

    def _seed_sent(self, n=5):
        now = DASH.now_cst()
        for i in range(n):
            self.conn.execute(
                "INSERT INTO send_log (lead_id, email, status, sent_at) VALUES (?,?,?,?)",
                (i + 1, f'lead{i + 1}@example.com', 'sent',
                 (now - timedelta(days=1)).isoformat()))
        self.conn.commit()

    def test_smtp_accepted_not_reduced_by_bounce(self):
        """bounce 记录存在时，SMTP Accepted 仍等于 send_log sent 数，不扣除。"""
        self._seed_sent(5)
        # 3 条 bounce，关联到已发送的 lead —— 属于「已发送但投递失败」
        for lid, btype in ((1, 'domain_invalid'), (2, 'hard'), (3, 'policy')):
            self.conn.execute(
                "INSERT INTO bounce_log (lead_id, email, bounce_type) VALUES (?,?,?)",
                (lid, f'lead{lid}@example.com', btype))
        self.conn.commit()

        r = DASH.compute_delivery_outcome(self.conn)
        self.assertEqual(r['smtp_accepted_all'], 5,
                         'SMTP Accepted 不应因 bounce 而减少')
        self.assertEqual(r['domain_invalid'], 1)
        self.assertEqual(r['hard_bounce'], 1)
        self.assertEqual(r['policy_bounce'], 1)
        self.assertEqual(r['outcome_unresolved'], 5 - 3)

    def test_classification_counts(self):
        """各分类计数正确（含历史 bounce_type 兼容与 unmatched_dsn / reply）。"""
        self._seed_sent(10)
        rows = [
            (1, 'domain_invalid'), (2, 'domain'),     # domain_invalid 合计 2（兼容历史 domain）
            (3, 'mailbox_invalid'),                    # mailbox_invalid 1
            (4, 'policy_bounce'), (5, 'policy'),       # policy 合计 2
            (6, 'soft_bounce'),                        # soft 1
            (7, 'hard'),                               # hard 1
            (8, 'unknown'),                            # other 1
        ]
        for lid, btype in rows:
            self.conn.execute(
                "INSERT INTO bounce_log (lead_id, email, bounce_type) VALUES (?,?,?)",
                (lid, f'lead{lid}@example.com', btype))
        # 2 条 unmatched DSN
        for i in range(2):
            self.conn.execute(
                "INSERT INTO unmatched_dsn (raw_message_id, final_recipient) VALUES (?,?)",
                (f'raw-{i}', 'x@example.com'))
        # reply：1 条自动回复（auto_reply_ooo），1 条人工回复
        self.conn.execute(
            "INSERT INTO reply_log (lead_id, email, reply_type) VALUES (?,?,?)",
            (100, 'a@example.com', 'auto_reply_ooo'))
        self.conn.execute(
            "INSERT INTO reply_log (lead_id, email, reply_type) VALUES (?,?,?)",
            (101, 'b@example.com', 'reply_inbound'))
        self.conn.commit()

        r = DASH.compute_delivery_outcome(self.conn)
        self.assertEqual(r['smtp_accepted_all'], 10)
        self.assertEqual(r['domain_invalid'], 2)
        self.assertEqual(r['mailbox_invalid'], 1)
        self.assertEqual(r['policy_bounce'], 2)
        self.assertEqual(r['soft_bounce'], 1)
        self.assertEqual(r['hard_bounce'], 1)
        self.assertEqual(r['other_bounce'], 1)
        self.assertEqual(r['unmatched_dsn'], 2)
        self.assertEqual(r['human_reply'], 1)
        self.assertEqual(r['auto_reply'], 1)

        classified = 2 + 1 + 2 + 1 + 1 + 1 + 2 + 1 + 1  # 全部已分类项
        self.assertEqual(r['classified_total'], classified)
        # unresolved = smtp_accepted - 已分类数（unmatched/reply 可能来自 send_log 之外的邮件，下限 0）
        self.assertEqual(r['outcome_unresolved'], max(0, 10 - classified))

    def test_unmatched_dsn_fallback_to_scan_result(self):
        """unmatched_dsn 表为空时，回退到 system_config.last_imap_scan_result。"""
        self._seed_sent(3)
        self.conn.execute(
            "INSERT INTO system_config (key, value) VALUES (?,?)",
            ('last_imap_scan_result',
             json.dumps({'unmatched_dsn': 4, 'outcome_unresolved': 0})))
        self.conn.commit()
        r = DASH.compute_delivery_outcome(self.conn)
        self.assertEqual(r['unmatched_dsn'], 4)


class FreshnessBadgeTest(unittest.TestCase):
    """Data Freshness 徽章 RED/YELLOW/GREEN 逻辑。"""

    def test_green_below_90min(self):
        now = DASH.now_cst()
        level, label = DASH.freshness_level(
            (now - timedelta(minutes=30)).isoformat(), now)
        self.assertEqual(level, 'green')
        self.assertEqual(label, 'FRESH')

    def test_yellow_between_90min_and_24h(self):
        now = DASH.now_cst()
        level, label = DASH.freshness_level(
            (now - timedelta(hours=2)).isoformat(), now)
        self.assertEqual(level, 'yellow')
        self.assertEqual(label, 'AGING')
        # 23h 仍为 YELLOW
        self.assertEqual(DASH.freshness_level(
            (now - timedelta(hours=23)).isoformat(), now)[0], 'yellow')

    def test_red_after_24h(self):
        now = DASH.now_cst()
        level, label = DASH.freshness_level(
            (now - timedelta(hours=25)).isoformat(), now)
        self.assertEqual(level, 'red')
        self.assertEqual(label, 'DATA STALE')

    def test_red_when_missing(self):
        """时间缺失/空串 -> RED + 'DATA STALE'。"""
        self.assertEqual(DASH.freshness_level(None)[0], 'red')
        self.assertEqual(DASH.freshness_level('', DASH.now_cst())[1], 'DATA STALE')

    def test_compute_data_freshness(self):
        """last_bounce_scan_at 新鲜 -> green；reply/sync 时间回填。"""
        conn = _make_mem_db()
        try:
            now = DASH.now_cst().isoformat()
            conn.execute("INSERT INTO system_config (key, value) VALUES (?,?)",
                         ('last_bounce_scan_at', now))
            conn.execute("INSERT INTO system_config (key, value) VALUES (?,?)",
                         ('sync_0845_last_success_at', now))
            conn.commit()
            r = DASH.compute_data_freshness(conn, None)
            self.assertEqual(r['level'], 'green')
            self.assertIsNotNone(r['last_reply_scan_at'])
            self.assertEqual(r['sync_0845_last_success_at'], now)
        finally:
            conn.close()


class ReconciliationParseTest(unittest.TestCase):
    """对账批次解析：output JSON（verdict/issues）与 system_config（status/issue_counts）。"""

    def test_json_file_verdict_issues(self):
        """post_send_reconciliation_*.json 含 verdict 与 issues -> 解析出 FAILED 与异常计数。"""
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                'verdict': 'FAILED',
                'batch_id': 'batch_001',
                'checked_at': '2026-08-06T09:00:00',
                'total_issues': 3,
                'issues': {
                    'consumed_but_no_send_log': {'count': 1, 'items': [{'lead_id': 1}]},
                    'duplicate_send': {'count': 2, 'items': [{'lead_id': 2}, {'lead_id': 3}]},
                    'tracking_token_missing': {'count': 0, 'items': []},
                },
            }
            fp = os.path.join(tmp, 'post_send_reconciliation_batch_001.json')
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(payload, f)

            conn = _make_mem_db()
            try:
                r = DASH.collect_reconciliation(conn, Path(tmp))
            finally:
                conn.close()
            self.assertTrue(r['any_failed'])
            self.assertEqual(len(r['batches']), 1)
            b = r['batches'][0]
            self.assertEqual(b['status_raw'], 'FAILED')
            self.assertEqual(b['anomalies'].get('consumed_but_no_send_log'), 1)
            self.assertEqual(b['anomalies'].get('duplicate_send'), 2)

    def test_system_config_payload(self):
        """system_config 的 post_send_reconciliation_* 值（status/issue_counts）解析。"""
        conn = _make_mem_db()
        try:
            conn.execute(
                "INSERT INTO system_config (key, value) VALUES (?,?)",
                ('post_send_reconciliation_batch_002',
                 json.dumps({'status': 'PASSED', 'checked_at': '2026-08-06T08:00:00',
                             'total_issues': 0, 'issue_counts': {}})))
            conn.commit()
            r = DASH.collect_reconciliation(conn, None)
            self.assertEqual(len(r['batches']), 1)
            self.assertTrue(r['batches'][0]['passed'])
            self.assertFalse(r['any_failed'])
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
