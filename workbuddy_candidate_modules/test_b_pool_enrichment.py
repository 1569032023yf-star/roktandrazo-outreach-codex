import hashlib
import tempfile
import unittest
from pathlib import Path

from app.lead_factory.b_pool_enrichment import (
    build_synthetic_fixture, read_lab_db, run_enrichment, write_synthetic_lab_db,
)


class BPoolEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = build_synthetic_fixture()
        self.results, self.metrics = run_enrichment(
            self.fixture["candidates"], self.fixture["pages"], self.fixture["strict_pool_before"]
        )

    def test_fixture_has_50_synthetic_candidates(self):
        self.assertEqual(50, self.metrics.checked_count)
        self.assertEqual("synthetic_no_customer_data", self.fixture["fixture_kind"])

    def test_expected_stage_outcomes(self):
        self.assertEqual(12, self.metrics.existing_website_verified)
        self.assertEqual(8, self.metrics.website_recovered_from_maps)
        self.assertEqual(14, self.metrics.facebook_pages_checked)
        self.assertEqual(6, self.metrics.websites_found_from_facebook)
        self.assertEqual(8, self.metrics.B1_social_verified_count)
        self.assertEqual(26, self.metrics.official_site_A0_count)
        self.assertEqual(6, self.metrics.C_contact_form_count)
        self.assertEqual(10, self.metrics.rejected_count)

    def test_social_only_never_upgrades_to_a0(self):
        social = [result for result in self.results if result.status == "B1_social_verified"]
        self.assertEqual(8, len(social))
        self.assertTrue(all(result.candidate["social_only"] for result in social))

    def test_no_browser_or_database_path_is_used(self):
        self.assertEqual(0, self.metrics.browser_fallback_count)
        self.assertEqual(36, self.metrics.strict_pool_after_estimate)

    def test_synthetic_lab_db_is_read_only_during_enrichment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "synthetic.db"
            write_synthetic_lab_db(path)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            fixture = read_lab_db(path)
            _, metrics = run_enrichment(fixture["candidates"], fixture["pages"], fixture["strict_pool_before"])
            after = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(before, after)
        self.assertEqual(50, metrics.checked_count)


if __name__ == "__main__":
    unittest.main()