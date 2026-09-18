"""Phase 4A.3K: duplicate discovery provenance backfill stays fail-closed."""
from __future__ import annotations

import unittest

from discovery.discovery_service import DiscoveryService
from discovery.models import PlaceSearchResult
from discovery.providers.browser_maps_scraper import _is_external_link
from retail_city_queue import activate_next_city
from tests.test_discovery_service import DiscoveryDb


def browser_result(*, website: str = "", source_url: str = "") -> PlaceSearchResult:
    return PlaceSearchResult(
        provider="browser_maps", provider_result_id="browser-1", place_id="place-1",
        business_name="Backfill Games", formatted_address="1 Main St, Nashville, TN 37201",
        city="Nashville", state="TN", country="US", phone="615-555-1111",
        website=website, business_status="OPERATIONAL", primary_type="store", types=["store"],
        source_query="game store Nashville TN", source_url=source_url,
    )


class DuplicateBackfillTests(unittest.TestCase):
    def _insert_then_replay(self, conn, initial, incoming):
        city = activate_next_city(conn)
        service = DiscoveryService(conn)
        discovery_id, created = service._upsert_result(city["id"], "game store", initial)
        self.assertTrue(created)
        replay_id, created = service._upsert_result(city["id"], "game store", incoming)
        self.assertFalse(created)
        self.assertEqual(replay_id, discovery_id)
        return conn.execute("SELECT website,source_url,normalized_domain FROM lead_discovery_results WHERE id=?", (discovery_id,)).fetchone()

    def test_empty_duplicate_fields_backfill_only_legitimate_browser_maps_assets(self):
        with DiscoveryDb() as conn:
            row = self._insert_then_replay(conn, browser_result(), browser_result(
                website="https://backfill-games.example/contact",
                source_url="https://www.google.com/maps/place/Backfill+Games/data=!4m2",
            ))
            self.assertEqual(row["website"], "https://backfill-games.example/contact")
            self.assertEqual(row["source_url"], "https://www.google.com/maps/place/Backfill+Games/data=!4m2")
            self.assertEqual(row["normalized_domain"], "backfill-games.example")

    def test_nonempty_duplicate_fields_are_never_overwritten(self):
        with DiscoveryDb() as conn:
            row = self._insert_then_replay(conn, browser_result(
                website="https://original-games.example", source_url="https://www.google.com/maps/place/Original+Games"),
                browser_result(website="https://replacement-games.example", source_url="https://www.google.com/maps/place/Replacement+Games"))
            self.assertEqual(row["website"], "https://original-games.example")
            self.assertEqual(row["source_url"], "https://www.google.com/maps/place/Original+Games")
            self.assertEqual(row["normalized_domain"], "original-games.example")

    def test_google_owned_and_non_place_values_are_not_backfilled(self):
        with DiscoveryDb() as conn:
            row = self._insert_then_replay(conn, browser_result(), browser_result(
                website="https://www.google.cn/maps", source_url="https://www.google.com/maps/search/Backfill+Games"))
            self.assertEqual(row["website"], "")
            self.assertEqual(row["source_url"], "")
            self.assertEqual(row["normalized_domain"], "")

    def test_duplicate_backfill_preserves_existing_official_evidence(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            service = DiscoveryService(conn)
            initial = browser_result()
            initial.raw_payload = {"official_email_evidence": {"email": "evidence@merchant.example"}}
            discovery_id, created = service._upsert_result(city["id"], "game store", initial)
            self.assertTrue(created)
            service._upsert_result(city["id"], "game store", browser_result(
                website="https://merchant.example", source_url="https://www.google.com/maps/place/Backfill+Games"))
            payload = conn.execute("SELECT raw_payload_json FROM lead_discovery_results WHERE id=?", (discovery_id,)).fetchone()[0]
            self.assertIn("evidence@merchant.example", payload)

    def test_google_owned_links_rejected_and_legitimate_merchant_link_preserved(self):
        self.assertFalse(_is_external_link("https://www.google.com/maps"))
        self.assertFalse(_is_external_link("https://www.google.cn/maps"))
        self.assertFalse(_is_external_link("https://g.page/redirect"))
        self.assertTrue(_is_external_link("https://merchant.example/contact"))
        self.assertTrue(_is_external_link("https://sites.google.com/view/merchant"))
        self.assertTrue(_is_external_link("https://merchant.business.site"))
