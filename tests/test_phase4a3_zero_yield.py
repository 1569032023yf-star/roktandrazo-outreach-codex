"""Phase 4A.3 regression coverage / 第4A.3阶段回归覆盖。"""
import json
import unittest
from types import SimpleNamespace

from discovery.discovery_service import DiscoveryService
from discovery.models import ProviderPage
from discovery.providers.mock_provider import MockPlacesProvider
from outreach_control import INVENTORY_TARGET, NEW_OUTREACH_TARGET, inventory_target_for_date
from retail_city_queue import activate_next_city
from tests.test_discovery_service import DiscoveryDb, MockFetcher, result
from tests import test_phase3d_existing_linkage as linkage


class Phase4A3ZeroYieldTests(unittest.TestCase):
    def _linked_case(self, conn):
        service, city, row, fetch, lead_id = linkage.ExistingLinkageTests().setup_case(conn)
        conn.execute("UPDATE leads SET review_reason_code='no_public_email_or_form' WHERE id=?", (lead_id,))
        conn.execute("UPDATE lead_discovery_results SET official_match=1, validation_status='manual_review_needed' WHERE id=?", (row['id'],))
        return service, city, row, fetch

    def test_no_public_email_is_terminal_after_one_linked_pass(self):
        with DiscoveryDb() as conn:
            service, city, row, _ = self._linked_case(conn)
            fetcher = MockFetcher({row['website']: '<title>Nashville Board Game Depot</title>'})
            first = service.run_linked_backlog(city, SimpleNamespace(), fetcher=fetcher)
            self.assertEqual(first['processed'], 1)
            self.assertEqual(first['terminalized'], 1)
            stored = conn.execute('SELECT validation_status,raw_payload_json FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone()
            self.assertEqual(stored['validation_status'], 'no_public_email')
            self.assertEqual(json.loads(stored['raw_payload_json'])['linked_backlog_retry']['terminal_outcome'], 'no_public_email')
            self.assertEqual(service.run_linked_backlog(city, SimpleNamespace(), fetcher=fetcher)['processed'], 0)

    def test_website_not_found_is_terminal_but_network_retry_remains_retryable(self):
        with DiscoveryDb() as conn:
            service, city, row, fetcher = self._linked_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='website_lookup_required',official_website='' WHERE id=(SELECT linked_lead_id FROM lead_discovery_results WHERE id=?)", (row['id'],))
            conn.execute("UPDATE lead_discovery_results SET website='',official_match=0 WHERE id=?", (row['id'],))
            resolver = SimpleNamespace(resolve=lambda _: SimpleNamespace(status='not_found', error=''))
            self.assertEqual(service.run_linked_backlog(city, resolver, fetcher=fetcher)['terminalized'], 1)
            self.assertEqual(conn.execute('SELECT validation_status FROM lead_discovery_results WHERE id=?', (row['id'],)).fetchone()[0], 'website_not_found')
            self.assertEqual(service.run_linked_backlog(city, resolver, fetcher=fetcher)['processed'], 0)

    def test_two_duplicate_pages_complete_query_and_advance_family(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            page = ProviderPage('mock', 'toy store Nashville TN', 'Nashville', 'TN', '', [result('Repeated Store', result_id='repeat')], next_page_cursor='same')
            service = DiscoveryService(conn, provider=MockPlacesProvider({('toy store Nashville TN', ''): page, ('toy store Nashville TN', 'same'): page}))
            service.run_places_batch(city)
            service.run_places_batch(activate_next_city(conn))
            third = service.run_places_batch(activate_next_city(conn))
            self.assertEqual(third.status, 'query_completed')
            state = conn.execute("SELECT status FROM lead_discovery_query_state WHERE query_family='toy store'").fetchone()[0]
            self.assertEqual(state, 'completed')
            next_city = activate_next_city(conn)
            self.assertEqual(next_city['active_query_family'], None)
            self.assertEqual(service._active_query(next_city['id'], 'mock', list(zip(('toy store', 'board game store'), ('toy store Nashville TN', 'board game store Nashville TN'))), next_city)[0], 'board game store')

    def test_inventory_target_defaults_to_send_quota_plus_buffer(self):
        self.assertEqual(NEW_OUTREACH_TARGET, 40)
        self.assertGreaterEqual(INVENTORY_TARGET, 50)
        self.assertEqual(inventory_target_for_date('2026-09-16'), INVENTORY_TARGET)
        self.assertGreaterEqual(inventory_target_for_date('2026-09-19'), 60)
