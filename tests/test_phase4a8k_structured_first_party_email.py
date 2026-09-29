"""Phase 4A.8K structured first-party email extraction safeguards."""
from __future__ import annotations

import hashlib
import unittest

from campaign_eligible import _is_official_evidence
from discovery.discovery_service import (
    _email_source_type,
    _enrichment_telemetry,
    _extract_email_evidence,
    _fetch_official_pages,
)


def page(html: str, text: str = "Example Hobby Shop") -> dict:
    return {
        "url": "https://shop.example/contact",
        "requested_url": "https://shop.example/contact",
        "final_url": "https://shop.example/contact",
        "method": "official_contact_page",
        "html": html,
        "text": text,
        "http_status": 200,
        "http_success": True,
        "tls_success": True,
        "fetched_at": "2026-09-29T00:00:00+00:00",
        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }


def jsonld(payload: str) -> str:
    return f'<script type="application/ld+json">{payload}</script>'


class StructuredFirstPartyEmailTests(unittest.TestCase):
    def extract(self, payload: str, *, text: str = "Example Hobby Shop") -> dict:
        return _extract_email_evidence([page(jsonld(payload), text)], "Example Hobby Shop")

    def test_organization_email_is_explicit_structured_evidence(self):
        evidence = self.extract('{"@context":"https://schema.org","@type":"Organization","name":"Example Hobby Shop","email":"hello@shop.example"}')
        self.assertEqual(evidence["email"], "hello@shop.example")
        self.assertEqual(evidence["method"], "first_party_structured_data")
        self.assertEqual(evidence["evidence"]["email_source_type"], "first_party_structured_data")
        self.assertIn("hello@shop.example", evidence["snippet"])

    def test_contact_point_email_and_array_are_supported(self):
        payload = '{"@type":"LocalBusiness","name":"Example Hobby Shop","contactPoint":[{"@type":"ContactPoint","email":"support@shop.example"},{"email":"sales@shop.example"}]}'
        evidence = self.extract(payload)
        self.assertIn(evidence["email"], {"support@shop.example", "sales@shop.example"})

    def test_nested_graph_organization_is_supported(self):
        payload = '{"@context":"https://schema.org","@graph":[{"@type":"WebSite","name":"Other"},{"@type":"Organization","name":"Example Hobby Shop","email":"contact@shop.example"}]}'
        self.assertEqual(self.extract(payload)["email"], "contact@shop.example")

    def test_malformed_non_business_and_identity_mismatch_are_rejected(self):
        self.assertEqual(self.extract('{broken json'), {})
        self.assertEqual(self.extract('{"@type":"Person","name":"Example Hobby Shop","email":"person@shop.example"}'), {})
        self.assertEqual(self.extract('{"@type":"Organization","name":"Unrelated Vendor","email":"other@vendor.example"}'), {})

    def test_multiple_blocks_dedupe_and_invalid_email_are_rejected(self):
        html = jsonld('{"@type":"Organization","name":"Example Hobby Shop","email":"sales@shop.example"}') + jsonld('{"@type":"Store","name":"Example Hobby Shop","email":"sales@shop.example"}')
        self.assertEqual(_extract_email_evidence([page(html)], "Example Hobby Shop")["email"], "sales@shop.example")
        self.assertEqual(self.extract('{"@type":"Organization","name":"Example Hobby Shop","email":"not-an-email"}'), {})

    def test_script_email_is_not_visible_evidence_and_visible_wins_when_both_exist(self):
        html = jsonld('{"@type":"Organization","name":"Example Hobby Shop","email":"structured@shop.example"}')
        structured = _extract_email_evidence([page(html, "Example Hobby Shop")], "Example Hobby Shop")
        self.assertEqual(structured["source"], "structured")
        both = _extract_email_evidence([page(html, "Contact sales@shop.example Example Hobby Shop")], "Example Hobby Shop")
        self.assertEqual(both["email"], "sales@shop.example")
        self.assertEqual(both["source"], "visible")

    def test_mailto_source_and_official_evidence_allowlist_are_explicit(self):
        html = '<a href="mailto:info@shop.example">Email us</a>'
        evidence = _extract_email_evidence([page(html, "Email us info@shop.example Example Hobby Shop")], "Example Hobby Shop")
        self.assertTrue(evidence["mailto"])
        self.assertEqual(_email_source_type(evidence["method"], evidence["snippet"]), "official_mailto")
        self.assertTrue(_is_official_evidence({"email_source_type": "first_party_structured_data"}, "x@gmail.com", "https://shop.example"))

    def test_cross_party_final_url_is_rejected_before_parser(self):
        class Fetcher:
            def fetch(self, _url):
                return {
                    "html": jsonld('{"@type":"Organization","name":"Example Hobby Shop","email":"x@shop.example"}'),
                    "text": "Example Hobby Shop",
                    "status": 200,
                    "final_url": "https://directory.example/listing",
                    "tls_success": True,
                }
        self.assertEqual(_fetch_official_pages("https://shop.example", Fetcher()), [])

    def test_telemetry_distinguishes_static_browser_and_no_email(self):
        class Fetcher:
            last_site_telemetry = {"PAGES_ATTEMPTED": 4}
            _site_static_failed = True
            _site_static_access_failure = True
            _site_browser_attempted = True
            last_site_automation_recovery_exhausted = False
        telemetry = _enrichment_telemetry([page("", "Example Hobby Shop")], Fetcher())
        self.assertTrue(telemetry["STATIC_FETCH_SUCCESS"])
        self.assertTrue(telemetry["STATIC_FETCH_FAILED"])
        self.assertTrue(telemetry["BROWSER_FALLBACK_ATTEMPTED"])
        self.assertTrue(telemetry["BROWSER_FALLBACK_FAILED"])
        self.assertEqual(telemetry["PAGES_ATTEMPTED"], 4)


if __name__ == "__main__":
    unittest.main()
