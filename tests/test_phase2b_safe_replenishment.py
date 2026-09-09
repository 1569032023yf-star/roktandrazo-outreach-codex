from __future__ import annotations

import json
import unittest

from dev_fsp import materialize_dev_fsp
from discovery.discovery_service import DiscoveryService
from discovery.discovery_service import _visible_text_from_html
from discovery.models import PlaceSearchResult, ProviderPage
from discovery.providers.mock_provider import MockPlacesProvider
from discovery.website_resolver import ProviderWebsiteResolver
from retail_city_queue import activate_next_city
from safe_replenishment import run_development_funnel
from tests.test_discovery_service import DiscoveryDb, MockFetcher, result


class StaticResolutionProvider:
    provider_name = "resolution_fixture"

    def __init__(self, results=None, status="ok"):
        self.results = results or []
        self.status = status

    def search_places(self, query, city, state, page_cursor="", page_size=10):
        return ProviderPage(self.provider_name, query, city, state, page_cursor,
                            results=self.results, status=self.status,
                            error="fixture_failure" if self.status != "ok" else "")


def official_result(name="Nashville Board Game Depot", website="https://nashvilleboarddepot.com"):
    return PlaceSearchResult(
        provider="resolution_fixture", provider_result_id="official-1", place_id="official-1",
        business_name=name, formatted_address="1 Main St, Nashville, TN 37201",
        city="Nashville", state="TN", country="US", phone="615-555-1111",
        website=website, business_status="OPERATIONAL", primary_type="store",
    )


class SafeReplenishmentTests(unittest.TestCase):
    def test_hidden_script_email_is_not_visible_evidence(self):
        text = _visible_text_from_html(
            '<html><body><p>Contact sales team</p><script>hidden@example.com</script>'
            '<span style="display:none">also-hidden@example.com</span>'
            '<a href="mailto:visible@example.com">Email us</a></body></html>'
        )
        self.assertNotIn("hidden@example.com", text)
        self.assertNotIn("also-hidden@example.com", text)
        self.assertIn("visible@example.com", text)

    def _discover_without_website(self, conn):
        city = activate_next_city(conn)
        staged = result("Nashville Board Game Depot", result_id="needs-site", website="", email="")
        page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [staged])
        service = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page}))
        summary = service.run_places_batch(city)
        self.assertEqual(summary.validation_statuses.get("website_lookup_pending"), 1)
        return city, service

    def test_discovery_to_official_evidence_to_frozen_v2_dev_fsp(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            staged = result("Nashville Board Game Depot", result_id="needs-site", website="", email="")
            page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [staged])
            service = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page}))
            resolver = ProviderWebsiteResolver(StaticResolutionProvider([official_result()]))
            funnel = run_development_funnel(
                conn, service, city, resolver,
                MockFetcher({
                    "https://nashvilleboarddepot.com": "Nashville Board Game Depot official website",
                    "https://nashvilleboarddepot.com/contact": "Nashville Board Game Depot sales@nashvilleboarddepot.com",
                }),
                {"nashvilleboarddepot.com": "ok"}, "fixture-run",
            )
            self.assertEqual(funnel["website_resolution"]["validation_statuses"], {"website_resolved": 1})
            self.assertEqual(funnel["evidence"]["validation_statuses"].get("lead_created"), 1)
            self.assertEqual(funnel["funnel"]["safe_fsp"], 1)
            self.assertEqual(funnel["smtp_calls"], 0)
            lead = conn.execute("SELECT * FROM leads").fetchone()
            self.assertEqual(lead["email"], "sales@nashvilleboarddepot.com")
            self.assertEqual(lead["evidence_snippet"].lower().count("sales@nashvilleboarddepot.com"), 1)
            self.assertEqual(lead["recipient_timezone"], "America/Chicago")
            self.assertTrue(lead["organization_key"])

            second = materialize_dev_fsp(conn, [lead["id"]], {"nashvilleboarddepot.com": "ok"}, "fixture-run")
            self.assertEqual((second["eligible"], second["inserted"]), (1, 0))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM dev_safe_fsp").fetchone()[0], 1)

    def test_directory_or_social_url_is_not_promoted_to_official_site(self):
        with DiscoveryDb() as conn:
            city, service = self._discover_without_website(conn)
            resolver = ProviderWebsiteResolver(
                StaticResolutionProvider([official_result(website="https://facebook.com/nashvilleboarddepot")])
            )
            result_summary = service.run_website_resolution(city, resolver)
            self.assertEqual(result_summary.validation_statuses, {"not_found": 1})
            row = conn.execute("SELECT website,validation_status FROM lead_discovery_results").fetchone()
            self.assertEqual((row["website"], row["validation_status"]), ("", "website_lookup_pending"))

    def test_identity_mismatch_and_cross_domain_redirect_fail_closed(self):
        with DiscoveryDb() as conn:
            city, service = self._discover_without_website(conn)
            resolver = ProviderWebsiteResolver(StaticResolutionProvider([official_result(name="Unrelated Merchant")]))
            result_summary = service.run_website_resolution(city, resolver)
            self.assertEqual(result_summary.validation_statuses, {"identity_review": 1})

        with DiscoveryDb() as conn:
            city, service = self._discover_without_website(conn)
            resolver = ProviderWebsiteResolver(StaticResolutionProvider([official_result()]))
            service.run_website_resolution(city, resolver)
            post = service.run_staging_postprocess(city, fetcher=MockFetcher({
                "https://nashvilleboarddepot.com": {
                    "text": "Nashville Board Game Depot sales@nashvilleboarddepot.com",
                    "status": 200, "final_url": "https://third-party.example/contact", "tls_verified": True,
                }
            }))
            self.assertEqual(post.validation_statuses.get("review_recovery"), 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM dev_safe_fsp").fetchone()[0] if conn.execute("SELECT 1 FROM sqlite_master WHERE name='dev_safe_fsp'").fetchone() else 0, 0)

        negative_fetches = {
            "http_failure": {"text": "Nashville Board Game Depot sales@nashvilleboarddepot.com", "status": 500,
                             "final_url": "https://nashvilleboarddepot.com/contact", "tls_verified": True},
            "tls_failure": {"text": "Nashville Board Game Depot sales@nashvilleboarddepot.com", "status": 200,
                            "final_url": "https://nashvilleboarddepot.com/contact", "tls_verified": False},
            "hidden_script_only": {"text": "", "html": "<script>sales@nashvilleboarddepot.com</script>", "status": 200,
                                   "final_url": "https://nashvilleboarddepot.com/contact", "tls_verified": True},
        }
        for name, payload in negative_fetches.items():
            with self.subTest(name=name), DiscoveryDb() as conn:
                city, service = self._discover_without_website(conn)
                resolver = ProviderWebsiteResolver(StaticResolutionProvider([official_result()]))
                service.run_website_resolution(city, resolver)
                post = service.run_staging_postprocess(
                    city,
                    fetcher=MockFetcher({"https://nashvilleboarddepot.com": payload}),
                )
                self.assertEqual(post.validation_statuses.get("review_recovery"), 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads WHERE auto_sendable=1").fetchone()[0], 0)
                raw = json.loads(conn.execute("SELECT raw_payload_json FROM lead_discovery_results").fetchone()[0])
                self.assertNotIn("official_email_evidence", raw)


if __name__ == "__main__":
    unittest.main()
