from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from campaign_eligible import review_campaign_eligible
from discovery.discovery_service import DiscoveryService
from discovery.models import ProviderPage
from discovery.providers.mock_provider import MockPlacesProvider
from retail_city_queue import activate_next_city

_spec = importlib.util.spec_from_file_location('discovery_fixture', Path(__file__).with_name('test_discovery_service.py'))
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)


class BusinessFitPipelineTests(unittest.TestCase):
    def test_official_evidence_flows_into_candidate_and_final_gate(self):
        cases = [
            ('toy', 'We sell board games, toys and jigsaw puzzles.', 'matched', 'lead_created'),
            ('industrial', 'We sell industrial bearings and fasteners.', 'unsuitable', 'manual_review_needed'),
            ('unknown', 'Welcome to Nashville Example Store.', 'unknown', 'manual_review_needed'),
            ('custom', 'We make custom printed merchandise for businesses.', 'matched', 'lead_created'),
        ]
        for label, description, expected_fit, expected_stage in cases:
            with self.subTest(label=label), _fixture.DiscoveryDb() as conn:
                conn.execute('ALTER TABLE leads ADD COLUMN business_evidence_url TEXT')
                conn.execute('ALTER TABLE leads ADD COLUMN business_evidence_snippet TEXT')
                city = activate_next_city(conn)
                website = 'https://nashvilleexample.example'
                found = _fixture.result('Nashville Example Store', result_id=label, website=website, email='')
                page = ProviderPage('mock', 'toy store Nashville TN', 'Nashville', 'TN', '', [found])
                service = DiscoveryService(conn, provider=MockPlacesProvider({('toy store Nashville TN', ''): page}))
                service.run_places_batch(city)
                pages = {website: 'Nashville Example Store. ' + description,
                         website + '/contact': 'Nashville Example Store contact: sales@nashvilleexample.example'}
                post = service.run_staging_postprocess(city, fetcher=_fixture.MockFetcher(pages))
                self.assertEqual(post.validation_statuses.get(expected_stage), 1, (label, post.validation_statuses))
                row = dict(conn.execute('SELECT * FROM leads').fetchone())
                row.update(recipient_timezone='America/Chicago', timezone_status='RESOLVED', organization_key=label)
                # Isolate this gate from unrelated email and broad-readiness checks.
                with patch('campaign_eligible.is_broad_outreach_ready', return_value={'ready': True}), \
                     patch('campaign_eligible.hygiene_check', return_value={'valid': True}):
                    review = review_campaign_eligible(row, {'conn': conn})
                self.assertEqual(review['checks']['business_fit']['detail']['status'], expected_fit)
                self.assertEqual(review['eligible'], expected_fit == 'matched', review['blockers'])
                if expected_fit == 'unknown':
                    self.assertEqual(review['pool'], 'NEEDS_MANUAL_REVIEW')
                if expected_fit == 'matched':
                    self.assertIn(description, row['business_evidence_snippet'])
                    self.assertEqual(row['business_evidence_url'], website)

    def test_search_keywords_and_untrusted_pages_are_not_product_proof(self):
        from business_fit import classify_business_fit, evidence_from_official_pages
        lead = {'official_website': 'https://shop.example', 'source_keyword': 'toy store',
                'product_fit': 'retail_games_gifts', 'email': 'sales@shop.example'}
        self.assertEqual(classify_business_fit(lead)['status'], 'unknown')
        lead.update(business_evidence_url='https://other.example', business_evidence_snippet='We sell toys.')
        self.assertEqual(classify_business_fit(lead)['status'], 'unknown')
        lead.update(business_evidence_url='https://shop.example', business_evidence_snippet='We sell industrial bearings for toy manufacturers.')
        self.assertNotEqual(classify_business_fit(lead)['status'], 'matched')
        lead['business_evidence_snippet'] = 'Toys are not sold here; we sell industrial bearings.'
        self.assertNotEqual(classify_business_fit(lead)['status'], 'matched')
        self.assertEqual(evidence_from_official_pages('https://shop.example', [
            {'url': 'https://shop.example', 'http_success': True, 'tls_success': False, 'text': 'We sell toys.'}]), {})


if __name__ == '__main__':
    unittest.main()
