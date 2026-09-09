from __future__ import annotations

import ast
import importlib.util
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from outreach_control import FOLLOW_UP_MAX, NEW_OUTREACH_TARGET, RETAIL_QUERY_FAMILIES, build_final_plan_entries, may_start_smtp_request, outreach_batch_date
from retail_city_queue import activate_next_city, checkpoint, seed_default_queue

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('city_migration', ROOT / 'migrations' / 'migrate_city_outreach_40.py')
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def lead(number: int, **extra):
    base = {'id': number, 'email': f'contact{number}@example{number}.com', 'store_name': f'Store {number}',
            'status': 'new', 'confidence_score': 'A', 'email_verified_on_official_site': 1,
            'auto_sendable': 1,
            'email_source_type': 'official_page_visible', 'evidence_url': 'https://example.com/contact',
            'evidence_snippet': 'Email us at contact@example.com', 'email_subject': 'Hello', 'email_body': 'Body'}
    base.update(extra)
    return base


class CityOutreach40Tests(unittest.TestCase):
    def test_new_outreach_cap_is_40_and_follow_up_cap_is_5(self):
        self.assertEqual(len(build_final_plan_entries([lead(i) for i in range(1, 51)], '2026-07-23', 'new_outreach')), NEW_OUTREACH_TARGET)
        self.assertEqual(len(build_final_plan_entries([lead(i) for i in range(1, 11)], '2026-07-23', 'follow_up')), FOLLOW_UP_MAX)

    def test_b1_b2_and_contact_form_do_not_enter_new_plan(self):
        bad = [lead(1, confidence_score='B'), lead(2, status='manual_review_needed'), lead(3, email_source_type='contact_form')]
        self.assertEqual(build_final_plan_entries(bad, '2026-07-23', 'new_outreach'), [])

    def test_new_plan_requires_auto_sendable_flag(self):
        self.assertEqual(build_final_plan_entries([lead(1, auto_sendable=0)], '2026-07-23', 'new_outreach'), [])

    def test_cross_midnight_uses_previous_outreach_batch_date(self):
        self.assertEqual(outreach_batch_date(datetime(2026, 7, 24, 0, 25)), '2026-07-23')
        self.assertEqual(outreach_batch_date(datetime(2026, 7, 23, 23, 0)), '2026-07-23')

    def test_migration_is_idempotent_and_only_one_active_city(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'test.db'
            conn = sqlite3.connect(db)
            conn.execute('CREATE TABLE leads (id INTEGER PRIMARY KEY)')
            conn.execute('CREATE TABLE send_log (id INTEGER PRIMARY KEY, status TEXT)')
            conn.commit(); conn.close()
            migration.migrate(db); migration.migrate(db)
            conn = sqlite3.connect(db)
            self.assertEqual(conn.execute("SELECT city FROM retail_city_queue ORDER BY priority LIMIT 1").fetchone()[0], 'Nashville')
            conn.execute("UPDATE retail_city_queue SET status='active' WHERE city='Nashville'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE retail_city_queue SET status='active' WHERE city='Memphis'")
            conn.close()

    def test_city_matrix_has_all_required_query_families(self):
        self.assertEqual(len(RETAIL_QUERY_FAMILIES), 20)
        self.assertIn('board game store', RETAIL_QUERY_FAMILIES)

    def test_message_types_are_separate(self):
        new_entries = build_final_plan_entries([lead(1)], '2026-07-23', 'new_outreach')
        followup_entries = build_final_plan_entries([lead(2)], '2026-07-23', 'follow_up')
        self.assertEqual(new_entries[0]['message_type'], 'new_outreach')
        self.assertEqual(followup_entries[0]['message_type'], 'follow_up')

    def test_smtp_cutoff_is_23_59_30(self):
        self.assertTrue(may_start_smtp_request(datetime(2026, 7, 23, 23, 59, 30)))
        self.assertFalse(may_start_smtp_request(datetime(2026, 7, 23, 23, 59, 31)))

    def test_paused_city_resumes_before_other_city(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'queue.db'
            conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
            conn.execute('''CREATE TABLE retail_city_queue (id INTEGER PRIMARY KEY, city TEXT, state TEXT, priority INTEGER,
                timezone TEXT, status TEXT, started_at TEXT, completed_at TEXT, active_query_family TEXT, active_source TEXT,
                page_cursor TEXT, discovered_count INTEGER DEFAULT 0, unique_domain_count INTEGER DEFAULT 0,
                official_site_count INTEGER DEFAULT 0, public_email_count INTEGER DEFAULT 0, strict_a0_count INTEGER DEFAULT 0,
                manual_review_count INTEGER DEFAULT 0, contact_form_count INTEGER DEFAULT 0, duplicate_count INTEGER DEFAULT 0,
                rejected_count INTEGER DEFAULT 0, last_new_domain_at TEXT, completion_reason TEXT)''')
            seed_default_queue(conn)
            first = activate_next_city(conn)
            checkpoint(conn, first['id'], 'toy store', 'Search Engine', 'page=2', paused=True)
            resumed = activate_next_city(conn)
            self.assertEqual(resumed['city'], 'Nashville')
            self.assertEqual(resumed['page_cursor'], 'page=2')
            conn.close()

    def test_inventory_stage_has_no_smtp_sender_reference(self):
        tree = ast.parse((ROOT / 'bd_orchestrator.py').read_text(encoding='utf-8'))
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'stage_inventory')
        self.assertNotIn('bd_sender', ast.unparse(func))

    def test_sender_requires_final_plan_metadata_for_live_mode(self):
        sender_text = (ROOT / 'bd_sender.py').read_text(encoding='utf-8')
        self.assertIn('Missing immutable final send plan metadata', sender_text)

    def test_final_plan_contains_required_audit_fields(self):
        entry = build_final_plan_entries([lead(1)], '2026-07-23', 'new_outreach')[0]
        for key in ('lead_id', 'recipient_email', 'company_name', 'template_id', 'source_city', 'source_state',
                    'evidence_url', 'hygiene_passed_at', 'message_type', 'outreach_batch_date', 'planned_sequence'):
            self.assertIn(key, entry)

    def test_unprocessed_plan_entries_are_not_replaced(self):
        session_text = (ROOT / 'daily_session.py').read_text(encoding='utf-8')
        self.assertIn("load_planned_entries(conn, batch_date)", session_text)
        self.assertNotIn("get_sendable_leads(limit=batch_size)", session_text.split('def execute_final_send_plan', 1)[1].split('def is_in_window', 1)[0])

    def test_dashboard_uses_message_type_and_batch_date(self):
        # Production UI = bd_ops_api.py (Ops Center data source). Old bd_operations_dashboard.py is archived.
        ops_text = (ROOT / 'bd_ops_api.py').read_text(encoding='utf-8')
        self.assertIn("message_type NOT IN ('test','internal_report','acceptance_test','sender_copy')", ops_text)
        self.assertIn('outreach_batch_date', ops_text)

    def test_dashboard_distinguishes_stage_not_run_from_zero(self):
        # Production UI = bd_ops_api.py + bd_review_server.py. Old bd_operations_dashboard.py is archived.
        ops_text = (ROOT / 'bd_ops_api.py').read_text(encoding='utf-8')
        self.assertIn('get_delivery_outcome_summary', ops_text)
        self.assertIn('get_data_freshness', ops_text)

    def test_plan_session_does_not_requery_candidate_pool(self):
        session = ast.parse((ROOT / 'daily_session.py').read_text(encoding='utf-8'))
        func = next(n for n in session.body if isinstance(n, ast.FunctionDef) and n.name == 'execute_final_send_plan')
        names = {n.id for n in ast.walk(func) if isinstance(n, ast.Name)}
        self.assertNotIn('get_sendable_leads', names)
        sender_text = (ROOT / 'bd_sender.py').read_text(encoding='utf-8')
        self.assertIn('final_plan_entry_id', sender_text)
        self.assertIn('plan_entry_id=plan_entry_id', sender_text)


if __name__ == '__main__':
    unittest.main()
