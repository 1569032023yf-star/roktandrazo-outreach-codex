import json
import tempfile
import unittest
from pathlib import Path

from discovery.discovery_service import DiscoveryService
from discovery.models import ProviderPage
from discovery.providers.browser_maps import BrowserMapsProvider
from discovery.providers.mock_provider import MockPlacesProvider
from retail_city_queue import activate_next_city
from tests.test_discovery_service import DiscoveryDb, result


class SearchPaginationTruthfulnessTests(unittest.TestCase):
    def test_two_distinct_batches_count_requests_and_new_places(self):
        query = 'toy store Nashville TN'
        first = ProviderPage('mock', query, 'Nashville', 'TN', '', [result('First', result_id='first')], next_page_cursor='next', request_count=1)
        second = ProviderPage('mock', query, 'Nashville', 'TN', 'next', [result('Second', result_id='second')], request_count=1)
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            service = DiscoveryService(conn, provider=MockPlacesProvider({(query, ''): first, (query, 'next'): second}))
            summary = service.run_places_batch(city, max_pages=2)
            self.assertEqual((summary.requests_made, summary.batches_processed, summary.new_unique_places, summary.duplicate_places), (2, 2, 2, 0))
            self.assertEqual(summary.status, 'query_completed')
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM lead_discovery_results').fetchone()[0], 2)

    def test_cache_sample_cannot_be_reused_for_another_cursor(self):
        query = 'toy store Nashville TN'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.json'
            record = result('First', result_id='first').to_record()
            path.write_text(json.dumps({'query': query, 'city': 'Nashville', 'state': 'TN', 'page_cursor': '', 'next_page_cursor': '20', 'request_count': 1, 'status': 'ok', 'results': [record]}), encoding='utf-8')
            provider = BrowserMapsProvider(cache_dir=tmp, mode='file', use_environment=False)
            sample = provider.search_places(query, 'Nashville', 'TN', '')
            self.assertTrue(sample.ok)
            self.assertEqual((sample.request_count, sample.next_page_cursor, sample.coverage, sample.from_cache), (0, '', 'sample', True))
            self.assertEqual(provider.search_places(query, 'Nashville', 'TN', '20').status, 'no_data_available')
            with DiscoveryDb() as conn:
                city = activate_next_city(conn)
                service = DiscoveryService(conn, provider=provider)
                summary = service.run_places_batch(city)
                self.assertEqual((summary.status, summary.requests_made, summary.batches_processed, summary.cached_batches), ('sample_finished', 0, 1, 1))
                again = service.run_places_batch(city)
                self.assertEqual((again.status, again.requests_made, again.batches_processed), ('sample_finished', 0, 0))
                self.assertEqual(conn.execute("SELECT status FROM lead_discovery_query_state WHERE query_family='toy store'").fetchone()[0], 'sample_finished')


if __name__ == '__main__':
    unittest.main()
