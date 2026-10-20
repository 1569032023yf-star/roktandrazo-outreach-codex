"""Offline city timeout recovery / 离线城市超时收敛验收。"""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from discovery.discovery_service import DiscoveryService
from discovery.providers.mock_provider import MockPlacesProvider
from discovery.website_resolver import WebsiteResolution
from outreach_control import RETAIL_QUERY_FAMILIES
from retail_city_queue import (
    NY_FIRST_ROUND_CITIES, seed_state_cities, activate_next_city,
    city_completion_checks, complete_active_city_if_exhausted,
    website_resolution_retry_terminal,
)
from tests import test_discovery_service as fixtures
from tests import test_phase4a1b_linked_backlog as linked_fixtures


class CityTimeoutRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DiscoveryDb()
        self.conn = self.fixture.__enter__()
        seed_state_cities(self.conn, "NY", NY_FIRST_ROUND_CITIES)
        self.conn.execute("UPDATE retail_city_queue SET status='completed' WHERE state='NY' AND priority<3")
        self.city = activate_next_city(self.conn, state="NY")
        self.assertEqual(self.city["city"], "Cooperstown")
        self.conn.execute("UPDATE retail_city_queue SET web_directory_status='not_required' WHERE id=?", (self.city['id'],))
        self.service = DiscoveryService(self.conn, provider=MockPlacesProvider())
        self.provider = self.service.provider.provider_name
        for family in RETAIL_QUERY_FAMILIES:
            self.conn.execute("""INSERT INTO lead_discovery_query_state
                (active_city_id,provider,query_family,query_text,status,page_cursor,pages_processed,completed_at)
                VALUES (?,?,?,?,'completed','',1,CURRENT_TIMESTAMP)""",
                (self.city['id'], self.provider, family, family))
        self.row_id = self.add_row()
        self.resolver = Mock()
        self.resolver.resolve.return_value = WebsiteResolution("network_retry", error="provider_timeout:45028ms")

    def tearDown(self):
        self.fixture.__exit__(None, None, None)

    def add_row(self):
        return self.conn.execute("""INSERT INTO lead_discovery_results
            (provider,business_name,city,state,active_city_id,validation_status,rejection_reason,
             raw_payload_json,discovered_at,last_seen_at)
            VALUES (?,'Offline Shop','Cooperstown','NY',?,'website_lookup_pending',?, ?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
            (self.provider, self.city['id'], 'website_resolution:network_retry:provider_timeout:45028ms',
             json.dumps({'original_provider_evidence': {'result': 'preserved'}}))).lastrowid

    def row(self):
        return dict(self.conn.execute("SELECT * FROM lead_discovery_results WHERE id=?", (self.row_id,)).fetchone())

    def run_at(self, hour, **kwargs):
        with patch('discovery.discovery_service.utc_now', return_value=f'2026-10-20T{hour:02}:00:00+00:00'):
            return self.service.run_website_resolution(self.city, self.resolver, **kwargs)

    def exhaust(self):
        for hour in (1, 2, 3):
            self.run_at(hour)

    def test_timeout_is_retryable_then_durable_manual_terminal_and_city_advances(self):
        self.run_at(1)
        self.assertFalse(all(city_completion_checks(self.conn, self.city['id'], self.provider).values()))
        self.run_at(2)
        self.run_at(3)
        row = self.row()
        self.assertTrue(website_resolution_retry_terminal(row))
        self.assertEqual(row['validation_status'], 'manual_review_needed')
        self.assertFalse(row['website'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM leads').fetchone()[0], 0)
        payload = json.loads(row['raw_payload_json'])
        self.assertEqual(payload['original_provider_evidence'], {'result': 'preserved'})
        retry = payload['website_resolution_retry']
        self.assertEqual(retry['attempts'], 3)
        self.assertEqual(len(retry['failures']), 3)
        self.assertEqual(retry['original_rejection_reason'], 'website_resolution:network_retry:provider_timeout:45028ms')
        self.conn.commit()
        # A new service object reads the persisted budget, not process memory.
        self.service = DiscoveryService(self.conn, provider=MockPlacesProvider())
        self.run_at(4)
        self.assertEqual(self.resolver.resolve.call_count, 3)
        checks = city_completion_checks(self.conn, self.city['id'], self.provider)
        self.assertEqual(len(checks), 9)
        self.assertTrue(all(checks.values()))
        self.assertTrue(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))
        self.assertEqual(activate_next_city(self.conn, state='NY')['city'], 'Lake Placid')

    def test_cooldown_survives_service_restart_and_keeps_city_open(self):
        self.run_at(1)
        self.service = DiscoveryService(self.conn, provider=MockPlacesProvider())
        self.run_at(1)
        self.assertEqual(self.resolver.resolve.call_count, 1)
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))

    def test_transient_recovery_follows_existing_qualification_path(self):
        self.run_at(1)
        self.resolver.resolve.return_value = WebsiteResolution('resolved', website='https://shop.example')
        self.run_at(2)
        self.assertEqual(self.row()['validation_status'], 'email_extraction_pending')
        self.assertFalse(website_resolution_retry_terminal(self.row()))
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM leads').fetchone()[0], 0)

    def test_transport_exception_uses_budget_but_programming_error_does_not(self):
        self.resolver.resolve.side_effect = TimeoutError('offline timeout')
        self.exhaust()
        self.assertTrue(website_resolution_retry_terminal(self.row()))
        self.row_id = self.add_row()
        for failure in (ValueError('implementation bug'), FileNotFoundError('missing local dependency')):
            self.resolver.resolve.side_effect = failure
            with self.assertRaises(type(failure)):
                self.run_at(4)
        self.assertNotIn('website_resolution_retry', json.loads(self.row()['raw_payload_json']))

    def test_terminal_rows_do_not_starve_later_work_under_limit(self):
        self.exhaust()
        self.add_row()
        self.run_at(4, max_results=1)
        self.assertEqual(self.resolver.resolve.call_count, 4)
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))

    def test_other_pending_work_and_query_cursor_still_block(self):
        self.exhaust()
        other = self.add_row()
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))
        self.conn.execute("UPDATE lead_discovery_results SET validation_status='email_extraction_pending', rejection_reason='' WHERE id=?", (other,))
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))
        self.conn.execute("UPDATE lead_discovery_results SET validation_status='identity_review' WHERE id=?", (other,))
        self.conn.execute("UPDATE lead_discovery_query_state SET page_cursor='remaining-page' WHERE active_city_id=?", (self.city['id'],))
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))

    def test_incomplete_or_corrupt_terminal_evidence_stays_fail_closed(self):
        self.exhaust()
        original = self.row()
        for change in ('missing_history', 'wrong_count', 'naive_time', 'too_soon', 'wrong_status', 'wrong_reason'):
            with self.subTest(change=change):
                row = copy.deepcopy(original)
                payload = json.loads(row['raw_payload_json'])
                retry = payload['website_resolution_retry']
                if change == 'missing_history': retry['failures'] = []
                if change == 'wrong_count': retry['attempts'] = 2
                if change == 'naive_time': retry['failures'][0]['at'] = '2026-10-20T01:00:00'
                if change == 'too_soon': retry['failures'][1]['at'] = retry['failures'][0]['at']
                if change == 'wrong_status': row['validation_status'] = 'website_lookup_pending'
                if change == 'wrong_reason': row['rejection_reason'] = 'website_resolution:network_retry:unknown'
                row['raw_payload_json'] = json.dumps(payload)
                self.assertFalse(website_resolution_retry_terminal(row))
                self.conn.execute('UPDATE lead_discovery_results SET raw_payload_json=?, validation_status=?, rejection_reason=? WHERE id=?',
                    (row['raw_payload_json'], row['validation_status'], row['rejection_reason'], self.row_id))
                self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))

    def test_malformed_original_payload_is_preserved_and_blocks(self):
        self.conn.execute("UPDATE lead_discovery_results SET raw_payload_json='broken original evidence' WHERE id=?", (self.row_id,))
        self.run_at(1)
        self.resolver.resolve.assert_not_called()
        self.assertEqual(self.row()['raw_payload_json'], 'broken original evidence')
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state='NY'))

    def test_duplicate_provider_hit_preserves_retry_history_and_terminal_state(self):
        self.conn.execute("UPDATE lead_discovery_results SET provider_result_id='duplicate-timeout' WHERE id=?", (self.row_id,))
        self.exhaust()
        before = json.loads(self.row()['raw_payload_json'])['website_resolution_retry']
        incoming = fixtures.result('Offline Shop', result_id='duplicate-timeout', website='', email='')
        sid, created = self.service._upsert_result(self.city['id'], RETAIL_QUERY_FAMILIES[0], incoming)
        self.assertEqual(sid, self.row_id)
        self.assertFalse(created)
        self.assertEqual(json.loads(self.row()['raw_payload_json'])['website_resolution_retry'], before)
        self.assertTrue(website_resolution_retry_terminal(self.row()))


class LinkedTimeoutRecoveryTests(unittest.TestCase):
    def test_linked_timeout_budget_preserves_lead_and_stops_all_reselection(self):
        with fixtures.DiscoveryDb() as conn:
            service, city, row, fetcher, lid = linked_fixtures.LinkedBacklogTests().setup_case(conn)
            conn.execute("UPDATE lead_discovery_results SET website='',validation_status='website_lookup_pending' WHERE id=?", (row['id'],))
            conn.execute("UPDATE leads SET review_reason_code='website_lookup_required' WHERE id=?", (lid,))
            before = tuple(conn.execute('SELECT * FROM leads WHERE id=?', (lid,)).fetchone())
            resolver = Mock()
            resolver.resolve.return_value = WebsiteResolution('network_retry', error='provider_timeout:45028ms')
            for hour in (1, 2, 3, 4):
                with patch('discovery.discovery_service.utc_now', return_value=f'2026-10-20T{hour:02}:00:00+00:00'):
                    service.run_linked_backlog(city, resolver, fetcher=fetcher)
                    service.run_staging_postprocess(city, fetcher=fetcher)
            self.assertEqual(resolver.resolve.call_count, 3)
            self.assertEqual(tuple(conn.execute('SELECT * FROM leads WHERE id=?', (lid,)).fetchone()), before)
            saved = dict(conn.execute('SELECT * FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone())
            self.assertEqual(saved['linked_lead_id'], lid)
            self.assertTrue(website_resolution_retry_terminal(saved))


if __name__ == '__main__':
    unittest.main()
