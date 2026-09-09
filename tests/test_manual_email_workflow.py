from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from manual_email_workflow import submit_manual_email
from migrations.migrate_city_outreach_40 import migrate


class ManualEmailWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'db.sqlite'
        c = sqlite3.connect(self.path)
        c.executescript("""CREATE TABLE leads (id INTEGER PRIMARY KEY, store_name TEXT, city TEXT, state TEXT, status TEXT,
            confidence_score TEXT, email TEXT, official_website TEXT, evidence_url TEXT, evidence_snippet TEXT,
            email_source_type TEXT, email_verified_on_official_site INTEGER, contact_form_url TEXT, domain_hash TEXT,
            lead_identity_hash TEXT, mx_provider TEXT, sent_at TEXT, manual_decision TEXT, template_id TEXT, store_type TEXT);
            ALTER TABLE leads ADD COLUMN email_type TEXT; ALTER TABLE leads ADD COLUMN manual_found_email TEXT;
            ALTER TABLE leads ADD COLUMN manual_email_source_url TEXT; ALTER TABLE leads ADD COLUMN manual_email_source_type TEXT;
            ALTER TABLE leads ADD COLUMN manual_verified_by TEXT; ALTER TABLE leads ADD COLUMN manual_verified_at TEXT;
            CREATE TABLE send_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, status TEXT);
            CREATE TABLE suppression_list (email TEXT); CREATE TABLE bounce_log (email TEXT, bounce_type TEXT);
            CREATE TABLE reply_log (email TEXT);""")
        c.close(); migrate(self.path)
        self.conn = sqlite3.connect(self.path); self.conn.row_factory = sqlite3.Row

    def tearDown(self): self.conn.close(); self.tmp.cleanup()

    def lead(self, ident=1, **more):
        row = {'id': ident, 'store_name': 'North Store', 'city': 'Nashville', 'state': 'TN', 'status': 'contact_form_pool',
               'confidence_score': 'B', 'email': 'old@north.com', 'official_website': 'https://north.com',
               'evidence_url': '', 'evidence_snippet': '', 'email_source_type': 'contact_form_only',
               'email_verified_on_official_site': 0, 'contact_form_url': 'https://north.com/contact',
               'domain_hash': 'north.com', 'lead_identity_hash': 'north-nashville', 'mx_provider': '', 'sent_at': '',
               'manual_decision': '', 'template_id': 'hybrid_wholesale_custom_v1', 'store_type': 'retail_store'}
        row.update(more)
        self.conn.execute('INSERT INTO leads (%s) VALUES (%s)' % (','.join(row), ','.join('?' * len(row))), tuple(row.values())); self.conn.commit()

    def submit(self, **kwargs):
        values = {'email': 'buyer@north.com', 'evidence_url': 'https://north.com/contact',
                  'evidence_snippet': 'buyer@north.com', 'evidence_method': 'official_contact_page',
                  'page_text': 'Contact buyer@north.com'}
        values.update(kwargs)
        with self.conn:
            return submit_manual_email(self.conn, 1, 'test', **values)

    def test_official_evidence_promotes_contact_form(self):
        self.lead(); result = self.submit()
        self.assertTrue(result['promoted']); self.assertEqual(tuple(self.conn.execute('SELECT email, auto_sendable FROM leads').fetchone()), ('buyer@north.com', 1))

    def test_previously_sent_is_not_new_outreach(self):
        self.lead(); self.conn.execute("INSERT INTO send_log (lead_id,email,status) VALUES (9,'buyer@north.com','sent')"); self.conn.commit()
        self.assertEqual(self.submit()['final_status'], 'previously_sent')

    def test_suppressed_and_hard_bounce_are_blocked(self):
        self.lead(); self.conn.execute("INSERT INTO suppression_list VALUES ('buyer@north.com')"); self.conn.commit(); self.assertEqual(self.submit()['final_status'], 'suppressed')
        self.conn.execute('DELETE FROM suppression_list'); self.conn.execute("INSERT INTO bounce_log VALUES ('buyer@north.com','hard')"); self.conn.commit(); self.assertEqual(self.submit()['final_status'], 'hard_bounced')

    def test_missing_evidence_cannot_promote(self):
        self.lead(); result = self.submit(evidence_url='', page_text='')
        self.assertEqual(result['final_status'], 'pending_official_verification')

    def test_original_email_is_preserved_and_audited(self):
        self.lead(); self.submit()
        self.assertEqual(self.conn.execute('SELECT email FROM lead_email_history').fetchone()[0], 'old@north.com')
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM manual_email_submission").fetchone()[0], 1)


if __name__ == '__main__': unittest.main()
