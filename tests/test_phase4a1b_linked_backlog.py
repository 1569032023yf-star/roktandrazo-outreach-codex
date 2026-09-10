"""Linked-only routing safety / 仅已关联积压的路由安全。"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

import bd_orchestrator
from tests.test_discovery_service import DiscoveryDb, MockFetcher, result
from tests import test_phase3d_existing_linkage as linkage


class LinkedBacklogTests(unittest.TestCase):
    def setup_case(self, conn):
        service, city, row, fetch, lid = linkage.ExistingLinkageTests().setup_case(conn)
        conn.execute("UPDATE leads SET review_reason_code='no_public_email_or_form' WHERE id=?", (lid,))
        conn.execute("UPDATE lead_discovery_results SET official_match=1, validation_status='manual_review_needed' WHERE id=?", (row['id'],))
        return service, city, row, fetch, lid

    def test_visible_link_and_idempotency(self):
        with DiscoveryDb() as conn:
            service, city, row, fetch, lid = self.setup_case(conn)
            first = service.run_linked_backlog(city, Mock(), fetcher=fetch)
            self.assertEqual(first['postprocess_processed'], 1)
            self.assertEqual(first['existing_leads_linked'], 1)
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=fetch)['processed'], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0], 1)
            ev = json.loads(conn.execute('SELECT raw_payload_json FROM lead_discovery_results').fetchone()[0])['official_email_evidence']
            self.assertIn(ev['email'], ev['visible_text_excerpt'])

    def test_network_recovery_retry_and_provenance(self):
        with DiscoveryDb() as conn:
            service, city, row, fetch, lid = self.setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='review_recovery',review_reason_detail='review_recovery=official_site_unavailable'")
            conn.execute("UPDATE lead_discovery_results SET validation_status='review_recovery'")
            service.run_linked_backlog(city, Mock(), fetcher=MockFetcher({}))
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=fetch)['existing_leads_linked'], 1)
            raw = json.loads(conn.execute('SELECT raw_payload_json FROM lead_discovery_results').fetchone()[0])
            self.assertEqual(raw['linked_backlog_retry']['attempts'], 2)

    def test_blocked_status_matrix(self):
        for status in ('sent', 'suppressed', 'bounced', 'rejected', 'review_rejected', 'unsubscribed'):
            with self.subTest(status=status), DiscoveryDb() as conn:
                service, city, row, fetch, lid = self.setup_case(conn)
                conn.execute('UPDATE leads SET status=?', (status,))
                self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=fetch)['processed'], 0)
                self.assertEqual(fetch.requested, [])

    def test_identity_rejection_and_conflicting_email(self):
        for sql in ("UPDATE lead_discovery_results SET rejection_reason='website_resolution:identity_review:'",
                    "UPDATE leads SET email='verified@example-retail.test'",
                    "UPDATE leads SET organization_key='conflicting-org'",
                    "UPDATE leads SET formatted_address='99 Other St'",
                    "UPDATE lead_discovery_results SET website='https://facebook.com/a-store'",
                    "UPDATE leads SET email_source_type='third_party'",
                    "UPDATE leads SET review_reason_code='identity_review'"):
            with self.subTest(sql=sql), DiscoveryDb() as conn:
                service, city, row, fetch, lid = self.setup_case(conn)
                conn.execute(sql)
                before = dict(conn.execute('SELECT * FROM leads').fetchone())
                self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=fetch)['processed'], 0)
                self.assertEqual(dict(conn.execute('SELECT * FROM leads').fetchone()), before)

    def test_hidden_and_failed_tls_not_promoted(self):
        for body in ({'html': 'Nashville Board Game Depot <script>sales@example-retail.test</script>', 'text': ''},
                     {'html': 'Nashville Board Game Depot sales@example-retail.test', 'tls_verified': False}):
            with self.subTest(body=body), DiscoveryDb() as conn:
                service, city, row, fetch, lid = self.setup_case(conn)
                fetch = MockFetcher({row['website']: {'status': 200, 'final_url': row['website'], 'tls_verified': True, **body}})
                service.run_linked_backlog(city, Mock(), fetcher=fetch)
                self.assertFalse(conn.execute('SELECT email FROM leads').fetchone()[0])
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0], 1)
                self.assertEqual(conn.execute('SELECT linked_lead_id FROM lead_discovery_results').fetchone()[0], lid)

    def test_history_logs_block_before_fetch(self):
        for kind in ('send', 'bounce'):
            with self.subTest(kind=kind), DiscoveryDb() as conn:
                service, city, row, fetch, lid = self.setup_case(conn)
                if kind == 'send':
                    conn.execute("INSERT INTO send_log(lead_id,email,status) VALUES (?,'','sent')", (lid,))
                else:
                    conn.execute("INSERT INTO bounce_log(lead_id,email,bounce_type) VALUES (?,'','hard')", (lid,))
                self.assertEqual(service.run_linked_backlog(city,Mock(),fetcher=fetch)['processed'],0)
                self.assertFalse(fetch.requested)

    def test_resolution_network_retry_not_terminal(self):
        with DiscoveryDb() as conn:
            service, city, row, fetch, lid = self.setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='website_lookup_required',official_website=''")
            conn.execute("UPDATE lead_discovery_results SET website='',official_match=0")
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry',error='timeout')
            for _ in range(2):
                self.assertEqual(service.run_linked_backlog(city,resolver,fetcher=fetch)['website_processed'],1)
            self.assertEqual(resolver.resolve.call_count,2)

    def test_exception_preserves_fairness_checkpoint(self):
        with DiscoveryDb() as conn:
            service, city, row, fetch, lid = self.setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='website_lookup_required',official_website=''")
            conn.execute("UPDATE lead_discovery_results SET website='',official_match=0")
            resolver = Mock()
            resolver.resolve.side_effect = RuntimeError('controlled provider failure')
            self.assertEqual(service.run_linked_backlog(city,resolver)['errors'],1)
            retry = json.loads(conn.execute('SELECT raw_payload_json FROM lead_discovery_results').fetchone()[0])['linked_backlog_retry']
            self.assertEqual(retry['last_error_type'],'RuntimeError')
            self.assertEqual(retry['attempts'],1)

    def test_bounded_fairness_and_city_scope(self):
        with DiscoveryDb() as conn:
            service, city, row, fetch, lid = self.setup_case(conn)
            for i in range(4):
                item = result(f'Board Game Store {i}', result_id=f'retry-{i}', email='', website='')
                sid, _ = service._upsert_result(city['id'], 'toy store', item)
                conn.execute("INSERT INTO leads(store_name,city,state,email,status,review_reason_code) VALUES (?,?,?,'','manual_review_needed','website_lookup_required')", (item.business_name,item.city,item.state))
                other = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                conn.execute("UPDATE lead_discovery_results SET linked_lead_id=?,validation_status='manual_review_needed' WHERE id=?", (other,sid))
            conn.execute("UPDATE lead_discovery_results SET city='Other City' WHERE id=(SELECT max(id) FROM lead_discovery_results)")
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='not_found', error='')
            for _ in range(4):
                self.assertEqual(service.run_linked_backlog(city,resolver,max_results=1,fetcher=MockFetcher({}))['processed'],1)
            attempts = [json.loads(r[0]).get('linked_backlog_retry',{}).get('attempts',0) for r in conn.execute('SELECT raw_payload_json FROM lead_discovery_results ORDER BY id')]
            self.assertEqual(attempts,[1,1,1,1,0])

    def test_broad_ready_cannot_complete(self):
        with DiscoveryDb() as conn:
            service, city, row, fetch, lid = self.setup_case(conn)
            conn.commit()
            with patch.object(bd_orchestrator,'get_db',return_value=Mock(wraps=conn)) as getdb, \
                 patch.object(bd_orchestrator,'set_execution_mode'), patch.object(bd_orchestrator,'update_job_run'), \
                 patch.object(bd_orchestrator,'acquire_run_lock',return_value=True), patch.object(bd_orchestrator,'release_run_lock'), \
                 patch.object(bd_orchestrator,'_resolve_active_discovery_state',return_value=('TN',None)), \
                 patch.object(bd_orchestrator,'_count_broad_ready_pool',return_value=34), \
                 patch.object(bd_orchestrator,'_count_safe_ready_pool',return_value=0), \
                 patch('discovery.discovery_service.DiscoveryService.run_linked_backlog',return_value={}), \
                 patch.object(bd_orchestrator,'finish_job_run') as finish:
                # A real connection is needed by the canonical transaction context.
                import sqlite3
                getdb.return_value=sqlite3.connect(service.conn.execute('PRAGMA database_list').fetchone()[2])
                getdb.return_value.row_factory=sqlite3.Row
                self.assertFalse(bd_orchestrator.stage_inventory('test','2026-09-10',False))
                self.assertEqual(finish.call_args.args[1],'partial')
                self.assertEqual(finish.call_args.kwargs['gap'],30)
