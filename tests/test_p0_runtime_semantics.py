from __future__ import annotations

import sqlite3
import tempfile
import unittest
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import bd_db
import bd_orchestrator
import bd_sender
from daily_session import execute_final_send_plan
from final_send_plan import create_plan
from lead_hygiene_gate import evaluate_a0
from tests.schema_fixture import create_test_database


def snapshot_database(path: Path) -> dict[str, list[tuple]]:
    conn = sqlite3.connect(path)
    try:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        return {table: conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall() for table in tables}
    finally:
        conn.close()


class P0RuntimeSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'runtime.sqlite'
        self.old_db_path = bd_db.DB_PATH
        self.conn = create_test_database(self.path)
        bd_db.DB_PATH = str(self.path)
        send_log_columns = {row[1] for row in self.conn.execute('PRAGMA table_info(send_log)')}
        for name, kind in (
            ('message_id', 'TEXT'), ('template_id', 'TEXT'), ('customer_type', 'TEXT'),
            ('routing_reason', 'TEXT'), ('batch_id', 'TEXT'), ('source_platform', 'TEXT'),
            ('message_type', 'TEXT'), ('outreach_batch_date', 'TEXT'), ('plan_entry_id', 'INTEGER'),
        ):
            if name not in send_log_columns:
                self.conn.execute(f'ALTER TABLE send_log ADD COLUMN {name} {kind}')
        # ICP / Campaign Eligible 相关列（生产库经 migration 存在；测试库动态补齐）
        lead_columns = {row[1] for row in self.conn.execute('PRAGMA table_info(leads)')}
        for name, kind in (
            ('organization_key', 'TEXT'), ('recipient_timezone', 'TEXT'), ('timezone_status', 'TEXT'),
        ):
            if name not in lead_columns:
                self.conn.execute(f'ALTER TABLE leads ADD COLUMN {name} {kind}')
        self.conn.execute("""INSERT INTO leads (
            store_name,store_type,city,state,official_website,email,evidence_url,evidence_snippet,evidence_method,
            email_source_type,email_verified_on_official_site,confidence_score,status,auto_sendable,manual_sendable,
            domain_hash,followup_count,review_status,organization_key,recipient_timezone,timezone_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            'North Store', 'retail', 'Nashville', 'TN', 'https://north.example', 'sales@north.example',
            'https://north.example/contact', 'sales@north.example', 'official_contact_page',
            'official_page_visible', 1, 'A', 'new', 1, 0, 'north', 0, 'hygiene_passed',
            'north', 'America/Chicago', 'RESOLVED',
        ))
        checked_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute("UPDATE leads SET last_checked_at=? WHERE id=1", (checked_at,))
        self.conn.execute(
            "INSERT INTO system_config(key,value,updated_at) VALUES(?,?,?)",
            ("mx_cache_north.example", json.dumps({"status": "ok", "checked_at": checked_at}), checked_at),
        )
        self.conn.commit()
        self.lead = dict(self.conn.execute('SELECT * FROM leads WHERE id=1').fetchone())

    def tearDown(self):
        self.conn.close()
        bd_db.DB_PATH = self.old_db_path
        self.temp.cleanup()

    def _plan(self, message_type: str, batch_date: str = '2026-07-24'):
        lead = dict(self.lead)
        lead.update(email_subject='Hello', email_body='Body', email_body_html='', template_id='test-template')
        with self.conn:
            create_plan(self.conn, [lead], batch_date, message_type)

    def test_dry_run_final_plan_is_zero_write_and_followup_is_previewed(self):
        self.conn.execute("""INSERT INTO send_log (lead_id,email,subject,status,message_type,outreach_batch_date)
                             VALUES (1,'sales@north.example','Hello','sent','new_outreach','2026-07-01')""")
        self.conn.commit()
        self._plan('follow_up')
        before = snapshot_database(self.path)
        result = execute_final_send_plan('2026-07-24', dry_run=True)
        after = snapshot_database(self.path)
        self.assertEqual(before, after)
        self.assertEqual(result['follow_up'], 0)
        self.assertEqual(len(result['preview']), 1)
        self.assertEqual(result['preview'][0]['message_type'], 'follow_up')
        self.assertEqual(result['preview'][0]['result'], 'dry_run')

    def test_dry_inventory_and_pre_send_do_not_change_any_table(self):
        before = snapshot_database(self.path)
        inventory = bd_orchestrator.stage_inventory('dry-inventory', '2026-07-24', dry_run=True)
        self.assertIn('strict_a0', inventory)
        with patch('workbuddy_candidate_modules.follow_up_queue_builder.build_followup_queue', return_value={'queue': []}):
            preview = bd_orchestrator.stage_pre_send('dry-pre-send', '2026-07-24', dry_run=True)
        after = snapshot_database(self.path)
        self.assertEqual(before, after)
        self.assertIn('new_outreach', preview)

    def test_status_is_read_only(self):
        before = snapshot_database(self.path)
        self.assertTrue(bd_orchestrator.stage_status())
        self.assertEqual(before, snapshot_database(self.path))

    def test_outreach_dry_run_is_zero_write_and_ignores_live_window(self):
        self._plan('new_outreach')
        before = snapshot_database(self.path)
        result = bd_orchestrator.stage_outreach('dry-outreach', '2026-07-24', dry_run=True)
        self.assertEqual(before, snapshot_database(self.path))
        self.assertEqual(len(result['preview']), 1)

    def test_follow_up_live_success_updates_count_time_log_and_plan(self):
        self.conn.execute("""INSERT INTO send_log (lead_id,email,subject,status,message_type,outreach_batch_date)
                             VALUES (1,'sales@north.example','Hello','sent','new_outreach','2026-07-01')""")
        self.conn.commit()
        self._plan('follow_up')

        def _fake_send_one(lead, dry_run=False):
            # 模拟真实 send_one 的原子副作用（send_log + FSP sent），
            # 以验证 execute_final_send_plan 的编排；_persist 只递增 followup_count。
            self.conn.execute(
                """INSERT INTO send_log (lead_id,email,subject,status,sent_at,message_type,outreach_batch_date,plan_entry_id)
                   VALUES (?,?,?,?,datetime('now'),?,?,?)""",
                (lead['id'], lead['email'], lead.get('email_subject', 'Hello'), 'sent',
                 lead.get('message_type', 'follow_up'), lead.get('outreach_batch_date'), lead.get('final_plan_entry_id')))
            self.conn.execute(
                "UPDATE final_send_plan SET status='sent', sent_at=datetime('now') WHERE id=?",
                (lead.get('final_plan_entry_id'),))
            self.conn.commit()
            return {'success': True, 'status': 'sent', 'message': 'mock sent'}

        with patch('recipient_scheduler.in_send_window', return_value=True), \
             patch('bd_sender.send_one', side_effect=_fake_send_one), \
             patch('bd_sender.create_send_authorization',
                   return_value={'authorization_id': 'auth_test', 'status': 'approved'}), \
             patch('daily_session.time.sleep', return_value=None):
            result = execute_final_send_plan('2026-07-24', dry_run=False)
        self.assertEqual(result['follow_up'], 1)
        lead = self.conn.execute('SELECT followup_count,last_followup_at,status FROM leads WHERE id=1').fetchone()
        self.assertEqual(lead['followup_count'], 1)
        self.assertTrue(lead['last_followup_at'])
        self.assertEqual(lead['status'], 'new')
        self.assertEqual(self.conn.execute("SELECT message_type FROM send_log ORDER BY id DESC LIMIT 1").fetchone()[0], 'follow_up')
        self.assertEqual(self.conn.execute('SELECT status FROM final_send_plan').fetchone()[0], 'sent')

    def test_deferred_follow_up_is_preview_blocked_then_live_skipped(self):
        self.conn.execute("""INSERT INTO send_log (lead_id,email,subject,status,message_type,outreach_batch_date)
                             VALUES (1,'sales@north.example','Hello','sent','new_outreach','2026-07-01')""")
        self.conn.execute("UPDATE leads SET review_status='deferred' WHERE id=1")
        self.conn.commit()
        self._plan('follow_up')
        before = snapshot_database(self.path)
        preview = execute_final_send_plan('2026-07-24', dry_run=True)
        self.assertEqual(preview['skipped'], 1)
        self.assertEqual(before, snapshot_database(self.path))
        with patch('recipient_scheduler.in_send_window', return_value=True), \
             patch('bd_sender.create_send_authorization',
                   return_value={'authorization_id': 'auth_test', 'status': 'approved'}):
            live = execute_final_send_plan('2026-07-24', dry_run=False)
        self.assertEqual(live['skipped'], 1)
        self.assertEqual(self.conn.execute('SELECT status FROM final_send_plan').fetchone()[0], 'skipped')

    def test_new_outreach_rechecks_live_lead_and_does_not_replace_skipped_entry(self):
        self._plan('new_outreach')
        self.conn.execute("UPDATE leads SET unsubscribed_at='2026-07-24T00:00:00' WHERE id=1")
        self.conn.commit()
        result = execute_final_send_plan('2026-07-24', dry_run=True)
        self.assertEqual(result['preview'], [])
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(self.conn.execute("SELECT status FROM final_send_plan").fetchone()[0], 'planned')

    def test_retail_state_limit_and_custom_production_exception(self):
        base = {
            'email': 'sales@outside.example', 'official_website': 'https://outside.example',
            'evidence_url': 'https://outside.example/contact', 'evidence_snippet': 'sales@outside.example',
            'email_verified_on_official_site': True, 'email_source_type': 'official_page_visible',
            'official_match': True, 'state': 'OH', 'status': 'new',
        }
        self.assertFalse(evaluate_a0(base).a0_eligible)
        self.assertTrue(evaluate_a0({**base, 'lead_segment': 'custom_production'}).a0_eligible)

    def test_smtp_test_mode_only_writes_test_history(self):
        class FakeServer:
            def sendmail(self, *args):
                return None
            def quit(self):
                return None

        lead = {**self.lead, 'email_subject': 'Hello', 'email_body': 'Body', 'email_body_html': '',
                'final_plan_entry_id': 99, 'message_type': 'new_outreach', 'outreach_batch_date': '2026-07-24'}
        with patch.object(bd_sender, 'get_test_config', return_value={'test_mode': True, 'test_email': 'test@local.example'}), \
             patch.object(bd_sender, 'is_configured', return_value=True), \
             patch.object(bd_sender, 'get_sender_info', return_value={'name': 'Tester', 'email': 'sender@local.example'}), \
             patch.object(bd_sender, '_create_connection', return_value=FakeServer()), \
             patch.object(bd_sender, '_save_to_sent', return_value=None):
            result = bd_sender.send_one(lead, dry_run=False)
        self.assertEqual(result['status'], 'test')
        self.assertEqual(self.conn.execute('SELECT status FROM leads WHERE id=1').fetchone()[0], 'new')
        row = self.conn.execute("SELECT lead_id,email,message_type,plan_entry_id FROM send_log").fetchone()
        self.assertEqual(tuple(row), (None, 'test@local.example', 'test', None))


if __name__ == '__main__':
    unittest.main()
