"""Bounded recovery and city liveness / 有界恢复与城市推进。"""
import json
import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from discovery.discovery_service import DiscoveryService
from discovery.providers.mock_provider import MockPlacesProvider
from retail_city_queue import (activate_next_city, automatic_recovery_deferred, city_completion_checks,
                               complete_active_city_if_exhausted, NY_FIRST_ROUND_CITIES, seed_state_cities)
from outreach_control import RETAIL_QUERY_FAMILIES
from tests.test_discovery_service import DiscoveryDb, MockFetcher
from tests import test_phase4a1b_linked_backlog as backlog_fixture


class TimeoutFetcher:
    def fetch(self, _url):
        raise TimeoutError('official site timeout')


class CityNetworkRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 22, tzinfo=timezone.utc)
        owner = self
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return owner.now if tz else owner.now.replace(tzinfo=None)
        for module in ('discovery.discovery_service', 'retail_city_queue'):
            clock = patch(module + '.datetime', Clock)
            clock.start()
            self.addCleanup(clock.stop)

    def elapse(self):
        self.now += timedelta(seconds=1801)

    def test_early_duplicate_schedule_waits_then_next_day_resumes(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            resolver = Mock()
            resolver.resolve.side_effect = TimeoutError('transport timeout')
            service.run_website_resolution(city, resolver)
            conn.commit()
            self.assertEqual(service.run_website_resolution(city, resolver).results_seen, 0)
            self.assertEqual(service.run_website_resolution(city, resolver, staging_ids=[row['id']]).results_seen, 0)
            self.assertEqual(resolver.resolve.call_count, 1)
            self.now += timedelta(days=1)
            restarted = DiscoveryService(conn, provider=MockPlacesProvider())
            restarted.run_website_resolution(city, resolver)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertEqual(json.loads(saved['raw_payload_json'])['website_resolution_retry']['attempts'], 2)
            self.assertFalse(automatic_recovery_deferred(saved))

    def test_wrapped_program_errors_do_not_consume_network_budget(self):
        for error in ('RuntimeError:internal bug', 'ModuleNotFoundError:browser', 'provider_process_no_result'):
            with DiscoveryDb() as conn:
                service, city, row, _, _ = self.missing_website(conn)
                resolver = Mock()
                resolver.resolve.return_value = SimpleNamespace(status='network_retry', error=error)
                for _ in range(4):
                    self.elapse()
                    service.run_website_resolution(city, resolver)
                saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
                self.assertNotIn('website_resolution_retry', json.loads(saved['raw_payload_json']))
                self.assertFalse(automatic_recovery_deferred(saved))

    def test_duplicate_provider_hit_preserves_internal_retry_and_rejects_injected_budget(self):
        from tests.test_discovery_service import result
        with DiscoveryDb() as conn:
            service = DiscoveryService(conn, provider=MockPlacesProvider())
            city = activate_next_city(conn)
            item = result('Retry Shop', result_id='retry-test', website='')
            item.raw_payload = {'website_resolution_retry': {'forged': True}}
            row_id, _ = service._upsert_result(city['id'], RETAIL_QUERY_FAMILIES[0], item)
            row = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row_id,)).fetchone())
            self.assertNotIn('website_resolution_retry', json.loads(row['raw_payload_json']))
            payload = {'website_resolution_retry': {'sentinel': 'persist'}, 'linked_backlog_retry': {'sentinel': 'persist'}}
            conn.execute('UPDATE lead_discovery_results SET raw_payload_json=? WHERE id=?', (json.dumps(payload), row_id))
            item.raw_payload = {'website_resolution_retry': {'forged': True}, 'fresh_fact': True}
            saved_id, created = service._upsert_result(city['id'], RETAIL_QUERY_FAMILIES[0], item)
            saved = json.loads(conn.execute('SELECT raw_payload_json FROM lead_discovery_results WHERE id=?', (saved_id,)).fetchone()[0])
            self.assertFalse(created)
            self.assertEqual(saved['website_resolution_retry'], payload['website_resolution_retry'])
            self.assertEqual(saved['linked_backlog_retry'], payload['linked_backlog_retry'])
            self.assertTrue(saved['fresh_fact'])

    def test_linked_cooldown_blocks_duplicate_schedule(self):
        with DiscoveryDb() as conn:
            service, city, row, _, lead_id = backlog_fixture.LinkedBacklogTests().setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='review_recovery',review_reason_detail='review_recovery=official_site_unavailable' WHERE id=?", (lead_id,))
            conn.execute("UPDATE lead_discovery_results SET validation_status='review_recovery' WHERE id=?", (row['id'],))
            service.run_linked_backlog(city, Mock(), fetcher=TimeoutFetcher())
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=TimeoutFetcher())['processed'], 0)
            self.elapse()
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=TimeoutFetcher())['processed'], 1)

    def missing_website(self, conn):
        service, city, row, fetch, lead_id = backlog_fixture.LinkedBacklogTests().setup_case(conn)
        conn.execute("UPDATE leads SET review_reason_code='website_lookup_required',official_website='' WHERE id=?", (lead_id,))
        conn.execute("UPDATE lead_discovery_results SET website='',validation_status='website_lookup_pending',"
                     "raw_payload_json=? WHERE id=?", (json.dumps({'provider_fact': 'preserved'}), row['id']))
        return service, city, row, fetch, lead_id

    def test_resolver_handoff_after_three_failures_survives_restart_and_keeps_evidence(self):
        with DiscoveryDb() as conn:
            service, city, row, _, lead_id = self.missing_website(conn)
            lead_before = dict(conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone())
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='provider_timeout:100ms')
            for attempt in range(1, 4):
                self.elapse()
                service.run_website_resolution(city, resolver)
                saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
                self.assertEqual(automatic_recovery_deferred(saved), attempt == 3)
            self.assertEqual(saved['validation_status'], 'manual_review_needed')
            self.assertTrue(saved['rejection_reason'].startswith('website_resolution:network_retry:'))
            self.assertEqual(json.loads(saved['raw_payload_json'])['provider_fact'], 'preserved')
            conn.commit()
            import sqlite3
            reopened = sqlite3.connect(conn.execute('PRAGMA database_list').fetchone()[2])
            try:
                restarted = DiscoveryService(reopened, provider=MockPlacesProvider())
                self.assertEqual(restarted.run_website_resolution(city, resolver).results_seen, 0)
                self.assertEqual(restarted.run_linked_backlog(city, resolver)['processed'], 0)
            finally:
                reopened.close()
            self.assertEqual(resolver.resolve.call_count, 3)
            self.assertEqual(dict(conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()), lead_before)

    def test_resolution_success_on_third_attempt_uses_normal_enrichment(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            resolver = Mock()
            resolver.resolve.side_effect = [SimpleNamespace(status='network_retry', error='timeout')] * 2 + [
                SimpleNamespace(status='resolved', website='https://confirmed.example')]
            for _ in range(3):
                self.elapse()
                service.run_website_resolution(city, resolver)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertEqual(saved['validation_status'], 'email_extraction_pending')
            self.assertEqual(saved['website'], 'https://confirmed.example')
            self.assertFalse(automatic_recovery_deferred(saved))

    def test_deferred_front_row_does_not_starve_next_candidate_under_limit(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_error', error='timeout')
            for _ in range(3):
                self.elapse()
                service.run_website_resolution(city, resolver, max_results=1)
            conn.execute("INSERT INTO lead_discovery_results(provider,business_name,active_city_id,website,validation_status,discovered_at,last_seen_at) "
                         "VALUES ('mock','Next Shop',?,'','website_lookup_pending',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (city['id'],))
            self.assertEqual(service.run_website_resolution(city, resolver, max_results=1).results_seen, 1)
            self.assertEqual(resolver.resolve.call_args.args[0]['business_name'], 'Next Shop')

    def test_linked_unavailable_scans_handoff_after_three_without_qualifying_email(self):
        with DiscoveryDb() as conn:
            service, city, row, _, lead_id = backlog_fixture.LinkedBacklogTests().setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='review_recovery',"
                         "review_reason_detail='review_recovery=official_site_unavailable' WHERE id=?", (lead_id,))
            conn.execute("UPDATE lead_discovery_results SET validation_status='review_recovery' WHERE id=?", (row['id'],))
            fetcher = TimeoutFetcher()
            for attempt in range(1, 4):
                self.elapse()
                summary = service.run_linked_backlog(city, Mock(), fetcher=fetcher)
                self.assertEqual(summary['automation_deferred'], int(attempt == 3))
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertTrue(automatic_recovery_deferred(saved))
            self.assertEqual(saved['validation_status'], 'review_recovery')
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=fetcher)['processed'], 0)
            self.assertEqual(tuple(conn.execute('SELECT email,status,email_verified_on_official_site FROM leads WHERE id=?',
                                               (lead_id,)).fetchone()), ('', 'manual_review_needed', 0))

    def test_processing_exceptions_do_not_consume_completed_scan_budget(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            resolver = Mock()
            resolver.resolve.side_effect = RuntimeError('processor_failed')
            for _ in range(4):
                self.assertEqual(service.run_linked_backlog(city, resolver)['errors'], 1)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertFalse(automatic_recovery_deferred(saved))
            self.assertEqual(saved['validation_status'], 'website_lookup_pending')

    def test_cooperstown_full_matrix_handoff_advances_lake_placid_without_checkpoint_loss(self):
        with DiscoveryDb() as conn:
            seed_state_cities(conn, 'NY', NY_FIRST_ROUND_CITIES)
            conn.execute("UPDATE retail_city_queue SET status='search_matrix_exhausted' WHERE city IN ('Ithaca','Saratoga Springs')")
            city = activate_next_city(conn, state='NY')
            self.assertEqual(city['city'], 'Cooperstown')
            conn.execute("UPDATE retail_city_queue SET web_directory_status='web_directory_provider_not_configured' WHERE id=?", (city['id'],))
            for family in RETAIL_QUERY_FAMILIES:
                conn.execute("INSERT INTO lead_discovery_query_state(active_city_id,provider,query_family,query_text,status,"
                             "page_cursor,pages_processed,completed_at) VALUES (?,'mock',?,?,'completed','',1,CURRENT_TIMESTAMP)",
                             (city['id'], family, f'{family} Cooperstown NY'))
            conn.execute("INSERT INTO lead_discovery_results(provider,business_name,city,state,active_city_id,website,validation_status,discovered_at,last_seen_at) "
                         "VALUES ('mock','Cooperstown Candidate','Cooperstown','NY',?,'','website_lookup_pending',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (city['id'],))
            checkpoints = [tuple(r) for r in conn.execute('SELECT * FROM lead_discovery_query_state')]
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='provider_timeout')
            for attempt in range(3):
                self.elapse()
                self.assertFalse(complete_active_city_if_exhausted(conn, 'mock', state='NY'))
                DiscoveryService(conn, provider=MockPlacesProvider()).run_website_resolution(city, resolver)
            self.assertTrue(all(city_completion_checks(conn, city['id'], 'mock').values()))
            self.assertTrue(complete_active_city_if_exhausted(conn, 'mock', state='NY'))
            self.assertEqual(activate_next_city(conn, state='NY')['city'], 'Lake Placid')
            self.assertEqual([tuple(r) for r in conn.execute('SELECT * FROM lead_discovery_query_state')], checkpoints)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0], 0)

    def test_incomplete_or_forged_handoff_does_not_suppress_work(self):
        for attempts, status in ((2, 'manual_review_needed'), (3, 'history_check_pending'), (3, 'email_extraction_pending')):
            row = {'validation_status': status, 'raw_payload_json': json.dumps({'website_resolution_retry': {
                'attempts': attempts, 'automation_terminal_outcome': 'network_retry_exhausted', 'automation_terminal_at': 'now'}})}
            self.assertFalse(automatic_recovery_deferred(row))

    def test_unexpected_fetcher_errors_never_consume_transport_retry_budget(self):
        with DiscoveryDb() as conn:
            service, city, row, _, lead_id = backlog_fixture.LinkedBacklogTests().setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='review_recovery',"
                         "review_reason_detail='review_recovery=official_site_unavailable' WHERE id=?", (lead_id,))
            conn.execute("UPDATE lead_discovery_results SET validation_status='review_recovery' WHERE id=?", (row['id'],))
            class BrokenFetcher:
                def fetch(self, _url):
                    raise RuntimeError('internal fetcher bug')
            for _ in range(4):
                service.run_linked_backlog(city, Mock(), fetcher=BrokenFetcher())
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertFalse(automatic_recovery_deferred(saved))
            retry = json.loads(saved['raw_payload_json'])['linked_backlog_retry']
            self.assertEqual(retry.get('unavailable_attempts', 0), 0)

    def test_database_failure_rolls_back_resolver_network_count(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            conn.execute("CREATE TRIGGER reject_resolution_update BEFORE UPDATE OF rejection_reason ON lead_discovery_results "
                         "BEGIN SELECT RAISE(ABORT,'fixture_database_failure'); END")
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='timeout')
            for _ in range(4):
                self.assertEqual(service.run_linked_backlog(city, resolver)['errors'], 1)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertFalse(automatic_recovery_deferred(saved))
            self.assertNotIn('website_resolution_retry', json.loads(saved['raw_payload_json']))

    def test_linked_success_on_third_scan_follows_existing_evidence_gate(self):
        with DiscoveryDb() as conn:
            service, city, row, fetch, lead_id = backlog_fixture.LinkedBacklogTests().setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='review_recovery',"
                         "review_reason_detail='review_recovery=official_site_unavailable' WHERE id=?", (lead_id,))
            conn.execute("UPDATE lead_discovery_results SET validation_status='review_recovery' WHERE id=?", (row['id'],))
            for _ in range(2):
                self.elapse()
                self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=TimeoutFetcher())['automation_deferred'], 0)
            self.elapse()
            summary = service.run_linked_backlog(city, Mock(), fetcher=fetch)
            self.assertEqual(summary['existing_leads_linked'], 1)
            self.assertEqual(summary['automation_deferred'], 0)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertFalse(automatic_recovery_deferred(saved))
            self.assertIn('official_email_evidence', json.loads(saved['raw_payload_json']))

    def test_direct_resolution_database_failure_does_not_leave_partial_retry_count(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            conn.execute("CREATE TRIGGER reject_resolution_update BEFORE UPDATE OF rejection_reason ON lead_discovery_results "
                         "BEGIN SELECT RAISE(ABORT,'fixture_database_failure'); END")
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='timeout')
            import sqlite3
            for _ in range(4):
                with self.assertRaises(sqlite3.IntegrityError):
                    service.run_website_resolution(city, resolver)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertFalse(automatic_recovery_deferred(saved))
            self.assertNotIn('website_resolution_retry', json.loads(saved['raw_payload_json']))
            self.assertEqual(saved['validation_status'], 'website_lookup_pending')

    def test_linked_handoff_requires_completed_scan_counter_not_total_attempts(self):
        row = {'validation_status': 'review_recovery', 'raw_payload_json': json.dumps({'linked_backlog_retry': {
            'attempts': 10, 'unavailable_attempts': 2, 'automation_terminal_outcome': 'network_retry_exhausted',
            'automation_terminal_at': 'now'}})}
        self.assertFalse(automatic_recovery_deferred(row))
        payload = json.loads(row['raw_payload_json'])
        payload['linked_backlog_retry']['unavailable_attempts'] = 3
        row['raw_payload_json'] = json.dumps(payload)
        self.assertFalse(automatic_recovery_deferred(row))  # Count-only metadata is insufficient.

    def test_previous_site_transport_flag_cannot_defer_a_missing_website_row(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='timeout')
            fetcher = MockFetcher({})
            fetcher.last_site_automation_recovery_exhausted = True
            summary = service.run_linked_backlog(city, resolver, fetcher=fetcher)
            self.assertEqual(summary['postprocess_processed'], 0)
            self.assertEqual(summary['automation_deferred'], 0)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertEqual(saved['validation_status'], 'website_lookup_pending')
            self.assertNotIn('automation_terminal_outcome', json.loads(saved['raw_payload_json'])['linked_backlog_retry'])

    def test_direct_resolution_preserves_caller_transaction_and_rollback(self):
        with DiscoveryDb() as conn:
            service, city, row, _, _ = self.missing_website(conn)
            conn.commit()
            before = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            resolver = Mock()
            resolver.resolve.return_value = SimpleNamespace(status='network_retry', error='timeout')
            service.run_website_resolution(city, resolver)
            self.assertTrue(conn.in_transaction)
            conn.rollback()
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertNotIn('website_resolution_retry', json.loads(saved['raw_payload_json']))
            self.assertEqual(saved, before)
