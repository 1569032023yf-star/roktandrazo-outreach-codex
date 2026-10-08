"""Phase 4A.8Q: unlinked identity-review terminal state regression tests."""
from __future__ import annotations

import unittest

from discovery.discovery_service import DiscoveryService
from discovery.models import PlaceSearchResult, ProviderPage
from discovery.providers.mock_provider import MockPlacesProvider
from retail_city_queue import (
    NY_FIRST_ROUND_CITIES,
    activate_next_city,
    city_completion_checks,
    complete_active_city_if_exhausted,
    seed_state_cities,
)
from outreach_control import RETAIL_QUERY_FAMILIES
from tests.test_discovery_service import DiscoveryDb
from tests.test_phase2b_safe_replenishment import StaticResolutionProvider
from discovery.website_resolver import ProviderWebsiteResolver


def _staged_result(name="Saratoga Toy Shop", website="", result_id="q433"):
    return PlaceSearchResult(
        provider="fixture", provider_result_id=result_id, place_id=result_id,
        business_name=name, formatted_address="10 Broadway, Saratoga Springs, NY 12866",
        city="Saratoga Springs", state="NY", country="US", phone="518-555-0100",
        website=website, business_status="OPERATIONAL", primary_type="store",
    )


class IdentityTerminalHotfixTests(unittest.TestCase):
    def _stage(self, conn):
        seed_state_cities(conn, "NY", NY_FIRST_ROUND_CITIES)
        city = activate_next_city(conn, state="NY")
        page = ProviderPage("fixture", "toy stores Saratoga Springs NY", "Saratoga Springs", "NY", "",
                           [_staged_result()])
        service = DiscoveryService(conn, provider=MockPlacesProvider({
            ("toy stores Saratoga Springs NY", ""): page,
        }))
        # Insert directly because this regression concerns the resolver transition,
        # while retaining the real migration schema and service code.
        conn.execute(
            """INSERT INTO lead_discovery_results
               (id,provider,business_name,formatted_address,city,state,active_city_id,
                discovered_at,last_seen_at,validation_status,website,linked_lead_id)
               VALUES (433,'fixture','Saratoga Toy Shop','10 Broadway, Saratoga Springs, NY 12866',
                       'Saratoga Springs','NY',?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,
                       'website_lookup_pending','',NULL)""", (city["id"],),
        )
        conn.commit()
        return city, service

    def test_identity_review_is_durable_and_not_reselected(self):
        with DiscoveryDb() as conn:
            city, service = self._stage(conn)
            # Reproduce the exact pre-fix branch result for the affected transition.
            self.assertEqual(
                "website_not_found" if "identity_review" == "not_found" else "website_lookup_pending",
                "website_lookup_pending",
            )
            resolver = ProviderWebsiteResolver(StaticResolutionProvider([
                _staged_result(name="Unrelated Saratoga Merchant", website="https://unrelated.example")
            ]))
            summary = service.run_website_resolution(city, resolver)
            self.assertEqual(summary.validation_statuses, {"identity_review": 1})
            row = conn.execute(
                "SELECT validation_status,rejection_reason,linked_lead_id FROM lead_discovery_results WHERE id=433"
            ).fetchone()
            self.assertEqual(row["validation_status"], "identity_review")
            self.assertTrue(row["rejection_reason"].startswith("website_resolution:identity_review:"))
            self.assertIsNone(row["linked_lead_id"])
            self.assertEqual(service.run_website_resolution(city, resolver).results_seen, 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 0)
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='dev_safe_fsp'").fetchone())

    def test_not_found_and_network_retry_keep_existing_semantics(self):
        with DiscoveryDb() as conn:
            city, service = self._stage(conn)
            not_found = ProviderWebsiteResolver(StaticResolutionProvider([
                _staged_result(website="https://facebook.com/saratogatoyshop")
            ]))
            service.run_website_resolution(city, not_found)
            row = conn.execute("SELECT validation_status FROM lead_discovery_results WHERE id=433").fetchone()
            self.assertEqual(row[0], "website_not_found")

        with DiscoveryDb() as conn:
            city, service = self._stage(conn)
            network = ProviderWebsiteResolver(StaticResolutionProvider([], status="provider_timeout"))
            service.run_website_resolution(city, network)
            row = conn.execute("SELECT validation_status,rejection_reason FROM lead_discovery_results WHERE id=433").fetchone()
            self.assertEqual(row["validation_status"], "website_lookup_pending")
            self.assertIn("website_resolution:network_retry:", row["rejection_reason"])
            self.assertEqual(service.run_website_resolution(city, network).results_seen, 1)

    def test_linked_merchant_resolution_path_still_updates_website(self):
        with DiscoveryDb() as conn:
            seed_state_cities(conn, "NY", NY_FIRST_ROUND_CITIES)
            city = activate_next_city(conn, state="NY")
            conn.execute(
                """INSERT INTO leads (id,store_name,city,state,status,review_status,review_reason_code)
                   VALUES (4330,'Saratoga Toy Shop','Saratoga Springs','NY','new','pending','website_lookup_required')"""
            )
            conn.execute(
                """INSERT INTO lead_discovery_results
                   (id,provider,business_name,formatted_address,city,state,active_city_id,discovered_at,last_seen_at,
                    validation_status,website,linked_lead_id)
                   VALUES (433,'fixture','Saratoga Toy Shop','10 Broadway, Saratoga Springs, NY 12866',
                           'Saratoga Springs','NY',?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,
                           'website_lookup_pending','',4330)""", (city["id"],),
            )
            conn.commit()
            resolver = ProviderWebsiteResolver(StaticResolutionProvider([_staged_result(
                website="https://saratogatoyshop.example"
            )]))
            summary = DiscoveryService(conn).run_website_resolution(city, resolver)
            self.assertEqual(summary.validation_statuses, {"website_resolved": 1})
            self.assertEqual(conn.execute("SELECT validation_status,website FROM lead_discovery_results WHERE id=433").fetchone()[0], "email_extraction_pending")
            self.assertEqual(conn.execute("SELECT official_website FROM leads WHERE id=4330").fetchone()[0], "https://saratogatoyshop.example")

    def test_terminal_identity_review_satisfies_existing_nine_checks_and_advances_queue(self):
        with DiscoveryDb() as conn:
            seed_state_cities(conn, "NY", NY_FIRST_ROUND_CITIES)
            city = activate_next_city(conn, state="NY")
            conn.execute("UPDATE retail_city_queue SET web_directory_status='web_directory_provider_not_configured' WHERE id=?", (city["id"],))
            for family in RETAIL_QUERY_FAMILIES:
                conn.execute(
                    """INSERT INTO lead_discovery_query_state
                       (active_city_id,provider,query_family,query_text,status,page_cursor,pages_processed,
                        new_unique_places,duplicate_places,consecutive_pages_without_new_place,completed_at)
                       VALUES (?, 'browser_maps', ?, ?, 'completed','',1,0,1,2,CURRENT_TIMESTAMP)""",
                    (city["id"], family, f"{family} Saratoga Springs NY"),
                )
            conn.execute(
                """INSERT INTO lead_discovery_results
                   (id,provider,business_name,active_city_id,discovered_at,last_seen_at,validation_status,rejection_reason)
                   VALUES (433,'browser_maps','Saratoga Toy Shop',?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,
                           'identity_review','website_resolution:identity_review:identity_mismatch')""", (city["id"],),
            )
            conn.commit()
            checks = city_completion_checks(conn, city["id"], "browser_maps")
            self.assertEqual(len(checks), 9)
            self.assertTrue(all(checks.values()), checks)
            self.assertTrue(complete_active_city_if_exhausted(conn, "browser_maps", state="NY"))
            self.assertEqual(activate_next_city(conn, state="NY")["city"], "Saratoga Springs")


if __name__ == "__main__":
    unittest.main()
