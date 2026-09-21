"""Phase 4A.8 deterministic regressions / 第 4A.8 阶段确定性回归。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from discovery.discovery_service import DiscoveryService
from discovery.models import ProviderPage
from discovery.providers import browser_maps
from discovery.providers.mock_provider import MockPlacesProvider
from retail_city_queue import activate_next_city
from tests.test_discovery_service import DiscoveryDb, MockFetcher, result
from tests import test_phase3d_existing_linkage as linkage


class WebsiteLivenessTests(unittest.TestCase):
    def _stage_missing_website(self, conn):
        city = activate_next_city(conn)
        place = result("Nashville Board Game Depot", result_id="phase4a8-missing", website="", email="")
        page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [place])
        service = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page}))
        service.run_places_batch(city)
        return city, service

    def test_not_found_is_terminal_and_not_reselected_by_resolution_or_postprocess(self):
        with DiscoveryDb() as conn:
            city, service = self._stage_missing_website(conn)
            resolver = SimpleNamespace(resolve=lambda _: SimpleNamespace(status="not_found", error="no_candidate"))
            first = service.run_website_resolution(city, resolver)
            self.assertEqual(first.validation_statuses, {"not_found": 1})
            stored = conn.execute("SELECT validation_status,rejection_reason FROM lead_discovery_results").fetchone()
            self.assertEqual(stored["validation_status"], "website_not_found")
            self.assertTrue(stored["rejection_reason"].startswith("website_resolution:not_found:"))
            self.assertEqual(service.run_website_resolution(city, resolver).results_seen, 0)
            self.assertEqual(service.run_staging_postprocess(city, fetcher=MockFetcher({})).results_seen, 0)

    def test_network_retry_remains_pending_and_retryable(self):
        with DiscoveryDb() as conn:
            city, service = self._stage_missing_website(conn)
            resolver = SimpleNamespace(resolve=lambda _: SimpleNamespace(status="network_retry", error="timeout"))
            service.run_website_resolution(city, resolver)
            self.assertEqual(conn.execute("SELECT validation_status FROM lead_discovery_results").fetchone()[0], "website_lookup_pending")
            self.assertEqual(service.run_website_resolution(city, resolver).results_seen, 1)

    def test_linked_not_found_uses_existing_terminal_backlog_path(self):
        with DiscoveryDb() as conn:
            service, city, row, fetcher, lead_id = linkage.ExistingLinkageTests().setup_case(conn)
            conn.execute("UPDATE leads SET review_reason_code='website_lookup_required',official_website='' WHERE id=?", (lead_id,))
            conn.execute("UPDATE lead_discovery_results SET website='',official_match=0 WHERE id=?", (row["id"],))
            resolver = SimpleNamespace(resolve=lambda _: SimpleNamespace(status="not_found", error="no_candidate"))
            summary = service.run_linked_backlog(city, resolver, fetcher=fetcher)
            self.assertEqual(summary["terminalized"], 1)
            self.assertEqual(conn.execute("SELECT validation_status FROM lead_discovery_results WHERE id=?", (row["id"],)).fetchone()[0], "website_not_found")


class BrowserMapsCacheHygieneTests(unittest.TestCase):
    def test_cache_key_handles_private_glyphs_newlines_and_windows_invalid_characters(self):
        query = "Game\ue0c8\nStore<>:\\|?*\ue0b0"
        key = browser_maps._cache_key(query, "Ithaca\r\nNY", "NY", "0")
        self.assertEqual(key, browser_maps._cache_key(query, "Ithaca\r\nNY", "NY", "0"))
        self.assertNotRegex(key, r'[<>:"/\\|?*\r\n]')
        self.assertNotIn("\ue0c8", key)
        self.assertNotIn("\ue0b0", key)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / key
            path.write_text("{}", encoding="utf-8")
            self.assertTrue(path.exists())

    def test_cached_provider_result_text_is_sanitized_before_use(self):
        query = "game store\ue0c8\n"
        city, state, page = "Ithaca", "NY", "0"
        with tempfile.TemporaryDirectory() as directory:
            old_dir = browser_maps.CACHE_DIR
            browser_maps.CACHE_DIR = Path(directory)
            try:
                raw = {
                    "status": "ok",
                    "results": [{
                        "provider": "browser_maps", "provider_result_id": "x", "place_id": "x",
                        "business_name": "Store\ue0c8\nName", "formatted_address": "1 Main\ue0b0\nSt",
                        "city": city, "state": state, "phone": "555\ue0b0\n1212",
                    }],
                }
                (browser_maps.CACHE_DIR / browser_maps._cache_key(query, city, state, page)).write_text(
                    json.dumps(raw), encoding="utf-8"
                )
                loaded = browser_maps._load_cache(query, city, state, page)
            finally:
                browser_maps.CACHE_DIR = old_dir
            self.assertIsNotNone(loaded)
            stored = loaded.results[0]
            self.assertEqual(stored.business_name, "Store Name")
            self.assertEqual(stored.formatted_address, "1 Main St")
            self.assertEqual(stored.phone, "555 1212")


if __name__ == "__main__":
    unittest.main()
