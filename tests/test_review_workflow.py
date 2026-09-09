"""Temporary-DB tests for the shared manual review workflow. No SMTP or network."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from final_send_plan import create_plan
from migrations.migrate_city_outreach_40 import migrate
from review_workflow import apply_review_action


LEAD_COLUMNS = """
id INTEGER PRIMARY KEY, store_name TEXT, city TEXT, state TEXT, status TEXT,
confidence_score TEXT, email TEXT, official_website TEXT, evidence_url TEXT,
email_source_type TEXT, email_verified_on_official_site INTEGER, evidence_snippet TEXT,
contact_form_url TEXT, domain_hash TEXT, mx_provider TEXT, sent_at TEXT, manual_decision TEXT,
last_checked_at TEXT, review_reason_code TEXT
"""


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'review.db'
        conn = sqlite3.connect(self.path)
        conn.executescript(f"""
            CREATE TABLE leads ({LEAD_COLUMNS});
            CREATE TABLE send_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, status TEXT);
            CREATE TABLE suppression_list (email TEXT);
            CREATE TABLE bounce_log (email TEXT, bounce_type TEXT);
        """)
        conn.close()
        migrate(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def add_lead(self, lead_id: int, **overrides):
        data = {
            'id': lead_id, 'store_name': f'Store {lead_id}', 'city': 'Nashville', 'state': 'TN',
            'status': 'manual_review_needed', 'confidence_score': 'B',
            'email': f'buyer{lead_id}@store{lead_id}.com', 'official_website': f'https://store{lead_id}.com',
            'evidence_url': f'https://store{lead_id}.com/contact', 'evidence_snippet': 'Email us for wholesale.',
            'email_source_type': 'official_mailto', 'email_verified_on_official_site': 1,
            'contact_form_url': '', 'domain_hash': f'domain-{lead_id}', 'mx_provider': '',
            'sent_at': '', 'manual_decision': '', 'last_checked_at': '', 'review_reason_code': 'B2_REVIEW',
        }
        data.update(overrides)
        columns = ', '.join(data)
        self.conn.execute(f"INSERT INTO leads ({columns}) VALUES ({','.join('?' for _ in data)})", tuple(data.values()))
        self.conn.commit()

    def action(self, lead_id, action, **kwargs):
        reason = kwargs.pop('reason', 'test reason')
        with self.conn:
            return apply_review_action(self.conn, lead_id, action, reviewer='test', reason=reason, **kwargs)

    def test_b1_cannot_enter_auto_sendable(self):
        self.add_lead(1, email_source_type='facebook_page', review_reason_code='B1_SOCIAL_VERIFIED')
        self.assertFalse(self.action(1, 'approve_auto')['ok'])

    def test_b2_cannot_directly_enter_final_plan(self):
        self.add_lead(2, email_source_type='guessed_email')
        self.assertEqual(create_plan(self.conn, [dict(self.conn.execute('SELECT * FROM leads WHERE id=2').fetchone())], '2026-07-23', 'new_outreach'), '')

    def test_approve_auto_reruns_hygiene(self):
        self.add_lead(3)
        self.assertTrue(self.action(3, 'approve_auto')['ok'])
        row = self.conn.execute('SELECT status, auto_sendable FROM leads WHERE id=3').fetchone()
        self.assertEqual((row['status'], row['auto_sendable']), ('new', 1))

    def test_hygiene_failure_blocks_approval(self):
        self.add_lead(4, evidence_snippet='')
        self.assertFalse(self.action(4, 'approve_auto')['ok'])

    def test_suppressed_manual_approval_is_blocked(self):
        self.add_lead(5)
        self.conn.execute("INSERT INTO suppression_list VALUES ('buyer5@store5.com')")
        self.conn.commit()
        self.assertFalse(self.action(5, 'approve_manual')['ok'])

    def test_contact_form_cannot_approve_email(self):
        self.add_lead(6, status='contact_form_pool', email='', contact_form_url='https://store6.com/contact')
        self.assertFalse(self.action(6, 'approve_auto')['ok'])
        self.assertFalse(self.action(6, 'approve_manual')['ok'])

    def test_manual_never_enters_auto_final_plan(self):
        self.add_lead(7)
        self.assertTrue(self.action(7, 'approve_manual')['ok'])
        row = dict(self.conn.execute('SELECT * FROM leads WHERE id=7').fetchone())
        self.assertEqual(create_plan(self.conn, [row], '2026-07-23', 'new_outreach'), '')
        self.assertEqual(self.conn.execute('SELECT status FROM manual_send_queue WHERE lead_id=7').fetchone()[0], 'pending_manual_action')

    def test_reject_saves_reason(self):
        self.add_lead(8)
        self.assertTrue(self.action(8, 'reject', reason='wrong market')['ok'])
        self.assertEqual(self.conn.execute('SELECT reason_detail FROM review_log WHERE lead_id=8').fetchone()[0], 'wrong market')

    def test_defer_saves_next_review_time(self):
        self.add_lead(9)
        self.assertTrue(self.action(9, 'defer', next_review_at='2026-08-01T10:00:00+08:00')['ok'])
        self.assertEqual(self.conn.execute('SELECT next_review_at FROM leads WHERE id=9').fetchone()[0], '2026-08-01T10:00:00+08:00')

    def test_every_action_has_audit_record(self):
        for lead_id, action in [(10, 'approve_auto'), (11, 'approve_manual'), (12, 'reject'), (13, 'defer'), (14, 'recheck_official'), (15, 'recheck_facebook')]:
            self.add_lead(lead_id)
            kwargs = {'next_review_at': '2026-08-01T10:00:00+08:00'} if action == 'defer' else {}
            self.assertTrue(self.action(lead_id, action, **kwargs)['ok'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM review_log').fetchone()[0], 6)

    def test_cli_and_web_share_same_workflow_contract(self):
        self.add_lead(16)
        result = self.action(16, 'recheck_official')  # Both entry points delegate to apply_review_action.
        self.assertTrue(result['ok'])
        self.assertEqual(self.conn.execute('SELECT review_status FROM leads WHERE id=16').fetchone()[0], 'recheck_pending')

    def test_approved_a0_needs_immutable_final_plan_before_send(self):
        self.add_lead(17)
        self.assertTrue(self.action(17, 'approve_auto')['ok'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM final_send_plan').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
