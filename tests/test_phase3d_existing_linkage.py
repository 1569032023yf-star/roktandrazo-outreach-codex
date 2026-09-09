"""Existing identity linkage regressions / 已有身份关联回归。"""
import json
import unittest
from datetime import datetime, timezone

from discovery.discovery_service import DiscoveryService
from discovery.providers.mock_provider import MockPlacesProvider
from tests.test_discovery_service import DiscoveryDb, result, MockFetcher
from retail_city_queue import activate_next_city
from dev_fsp import materialize_dev_fsp


class ExistingLinkageTests(unittest.TestCase):
    def setup_case(self, conn):
        city = activate_next_city(conn)
        service = DiscoveryService(conn, provider=MockPlacesProvider())
        item = result('Nashville Board Game Depot', result_id='linkage', email='')
        sid, _ = service._upsert_result(city['id'], 'toy store', item)
        conn.execute("INSERT INTO leads (store_name,city,state,official_website,email,formatted_address,"
                     "status,review_status,review_reason_code) VALUES (?,?,?,?,?,?,?,?,?)",
                     (item.business_name, item.city, item.state, item.website, '', item.formatted_address,
                      'manual_review_needed', 'pending', 'identity_review'))
        lid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.execute('UPDATE lead_discovery_results SET linked_lead_id=? WHERE id=?', (lid,sid))
        row = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?',(sid,)).fetchone())
        fetch = MockFetcher({item.website: item.business_name + ' sales@example-retail.test'})
        return service, city, row, fetch, lid

    def test_same_identity_empty_email_and_replay(self):
        with DiscoveryDb() as conn:
            service,city,row,fetch,lid=self.setup_case(conn)
            self.assertEqual(service._postprocess_staged_result(row,city,fetch),('existing_lead_linked',lid))
            first=dict(conn.execute('SELECT * FROM leads WHERE id=?',(lid,)).fetchone())
            self.assertEqual(first['email'],'sales@example-retail.test')
            self.assertEqual(first['status'],'new')
            ev=json.loads(conn.execute('SELECT raw_payload_json FROM lead_discovery_results').fetchone()[0])
            self.assertIn('official_email_evidence',ev)
            self.assertEqual(materialize_dev_fsp(conn,[lid],{'example-retail.test':'ok'},'replay')['inserted'],1)
            self.assertEqual(service._postprocess_staged_result(row,city,fetch),('existing_lead_linked',lid))
            self.assertEqual(dict(conn.execute('SELECT * FROM leads WHERE id=?',(lid,)).fetchone()),first)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0],1)
            self.assertEqual(materialize_dev_fsp(conn,[lid],{'example-retail.test':'ok'},'replay')['inserted'],0)

    def test_conflicting_email(self):
        with DiscoveryDb() as conn:
            service,city,row,fetch,lid=self.setup_case(conn)
            conn.execute("UPDATE leads SET email='verified@example-retail.test',email_verified_on_official_site=1 WHERE id=?",(lid,))
            self.assertEqual(service._postprocess_staged_result(row,city,fetch)[0],'identity_review')
            lead=conn.execute('SELECT email,review_status FROM leads WHERE id=?',(lid,)).fetchone()
            self.assertEqual(tuple(lead),('verified@example-retail.test','identity_review'))

    def test_review_lane_preserves_hygiene_and_links(self):
        with DiscoveryDb() as conn:
            service,city,row,fetch,lid=self.setup_case(conn)
            fetch=MockFetcher({row['website']:'Nashville Board Game Depot visible-shop@yahoo.com'})
            conn.execute("UPDATE leads SET timezone_status='UNSET',recipient_timezone='America/Chicago' WHERE id=?",(lid,))
            status,linked=service._postprocess_staged_result(row,city,fetch)
            self.assertEqual(linked,lid)
            lead=dict(conn.execute('SELECT * FROM leads WHERE id=?',(lid,)).fetchone())
            self.assertEqual(lead['email'],'visible-shop@yahoo.com')
            self.assertEqual(lead['auto_sendable'],0)
            self.assertEqual(lead['review_reason_code'],'hygiene_failed')
            self.assertEqual(materialize_dev_fsp(conn,[lid],{'yahoo.com':'ok'},'review')['eligible'],1)

    def test_link_failure_rolls_back_email_update(self):
        with DiscoveryDb() as conn:
            service,city,row,fetch,lid=self.setup_case(conn)
            conn.execute("CREATE TRIGGER reject_link BEFORE UPDATE OF validation_status ON lead_discovery_results "
                         "BEGIN SELECT RAISE(ABORT,'fixture_link_failure'); END")
            import sqlite3
            with self.assertRaises(sqlite3.IntegrityError):
                service._postprocess_staged_result(row,city,fetch)
            self.assertEqual(conn.execute('SELECT email FROM leads WHERE id=?',(lid,)).fetchone()[0],'')

    def test_different_organization(self):
        with DiscoveryDb() as conn:
            service,city,row,fetch,lid=self.setup_case(conn)
            conn.execute("UPDATE leads SET organization_key='different-established-org' WHERE id=?",(lid,))
            self.assertEqual(service._postprocess_staged_result(row,city,fetch)[0],'identity_review')
            self.assertEqual(conn.execute('SELECT email FROM leads WHERE id=?',(lid,)).fetchone()[0],'')

    def test_different_location(self):
        with DiscoveryDb() as conn:
            service,city,row,fetch,lid=self.setup_case(conn)
            conn.execute("UPDATE leads SET formatted_address='99 Other St' WHERE id=?",(lid,))
            service._postprocess_staged_result(row,city,fetch)
            self.assertFalse(conn.execute('SELECT email FROM leads WHERE id=?',(lid,)).fetchone()[0])

    def test_history_matrix(self):
        for status in ('sent','suppressed','unsubscribed','hard_bounced','policy_bounced','review_rejected','do_not_contact'):
            with self.subTest(status=status), DiscoveryDb() as conn:
                service,city,row,fetch,lid=self.setup_case(conn)
                conn.execute('UPDATE leads SET status=? WHERE id=?',(status,lid))
                service._postprocess_staged_result(row,city,fetch)
                self.assertEqual(tuple(conn.execute('SELECT email,status FROM leads WHERE id=?',(lid,)).fetchone()),('',status))

    def test_invalid_http_tls(self):
        for change in ({'status':500},{'tls_verified':False}):
            with self.subTest(change=change), DiscoveryDb() as conn:
                service,city,row,fetch,lid=self.setup_case(conn)
                fetch=MockFetcher({row['website']:{'text':'Nashville Board Game Depot sales@example-retail.test',
                    'html':'Nashville Board Game Depot sales@example-retail.test','status':200,
                    'final_url':row['website'],'tls_verified':True,**change}})
                service._postprocess_staged_result(row,city,fetch)
                self.assertFalse(conn.execute('SELECT email FROM leads WHERE id=?',(lid,)).fetchone()[0])

    def test_org_suppression_and_bounce_logs(self):
        for kind in ('suppression','bounce','sent'):
            with self.subTest(kind=kind), DiscoveryDb() as conn:
                service,city,row,fetch,lid=self.setup_case(conn)
                if kind=='suppression':
                    conn.execute("INSERT INTO suppression_list(email) VALUES ('sales@example-retail.test')")
                elif kind=='bounce':
                    conn.execute("INSERT INTO bounce_log(lead_id,email,bounce_type) VALUES (?, '', 'hard')",(lid,))
                else:
                    conn.execute("INSERT INTO send_log(lead_id,email,status) VALUES (?, '', 'sent')",(lid,))
                service._postprocess_staged_result(row,city,fetch)
                self.assertFalse(conn.execute('SELECT email FROM leads WHERE id=?',(lid,)).fetchone()[0])
