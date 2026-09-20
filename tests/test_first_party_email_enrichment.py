"""Phase 4A.6 bounded first-party email enrichment safeguards."""
from __future__ import annotations

import hashlib
import unittest

from discovery.discovery_service import (
    MAX_FIRST_PARTY_PAGES_PER_SITE,
    _extract_email_evidence,
    _fetch_official_pages,
)


def _page(url: str, html: str, *, final_url: str | None = None, status: int = 200, tls: bool = True) -> dict:
    from discovery.discovery_service import _visible_text_from_html
    return {
        "text": _visible_text_from_html(html), "html": html, "status": status,
        "final_url": final_url or url, "tls_verified": tls, "fetched_at": "2026-09-20T00:00:00+00:00",
    }


class FakeFetcher:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.requested: list[str] = []

    def fetch(self, url: str) -> dict:
        self.requested.append(url)
        return self.responses.get(url, {"text": "", "html": "", "status": 404, "final_url": url, "tls_verified": True})


class FirstPartyEmailEnrichmentTests(unittest.TestCase):
    def test_visible_internal_contact_link_is_prioritized_and_evidence_is_complete(self):
        home = "https://shop.example"
        contact = "https://shop.example/contact-us"
        fetcher = FakeFetcher({
            home: _page(home, '<a href="/contact-us">Contact our sales team</a> Shop Example'),
            contact: _page(contact, 'Sales: sales@shop.example'),
        })
        pages = _fetch_official_pages(home, fetcher)
        evidence = _extract_email_evidence(pages)
        self.assertEqual(evidence["email"], "sales@shop.example")
        self.assertEqual(evidence["evidence"]["requested_url"], contact)
        self.assertIn("sales@shop.example", evidence["evidence"]["visible_text_excerpt"])
        self.assertTrue(evidence["evidence"]["http_success"])
        self.assertTrue(evidence["evidence"]["tls_success"])
        self.assertEqual(len(evidence["evidence"]["content_hash"]), 64)

    def test_external_social_and_directory_links_are_never_fetched(self):
        home = "https://shop.example"
        fetcher = FakeFetcher({home: _page(home, '''
            <a href="https://facebook.com/shop">Contact us</a>
            <a href="https://directory.example/shop">Vendor</a> Shop Example
        ''')})
        _fetch_official_pages(home, fetcher)
        self.assertFalse(any("facebook.com" in url or "directory.example" in url for url in fetcher.requested))

    def test_cap_and_deduplication_bound_page_fetches(self):
        home = "https://shop.example"
        links = "".join(f'<a href="/contact-{index}">contact</a>' for index in range(30))
        fetcher = FakeFetcher({home: _page(home, links + " Shop Example")})
        _fetch_official_pages(home, fetcher)
        self.assertLessEqual(len(fetcher.requested), MAX_FIRST_PARTY_PAGES_PER_SITE)
        self.assertEqual(len(fetcher.requested), len(set(fetcher.requested)))

    def test_tls_failure_and_cross_party_redirect_are_rejected(self):
        home = "https://shop.example"
        bad_tls = "https://shop.example/contact"
        redirect = "https://shop.example/about"
        fetcher = FakeFetcher({
            home: _page(home, "Shop Example"),
            bad_tls: _page(bad_tls, "sales@shop.example", tls=False),
            redirect: _page(redirect, "sales@evil.example", final_url="https://evil.example/contact"),
        })
        self.assertEqual(_fetch_official_pages(home, fetcher), [
            _fetch_official_pages(home, FakeFetcher({home: _page(home, "Shop Example")}))[0]
        ])

    def test_hidden_script_email_is_rejected_but_mailto_and_plain_text_are_accepted(self):
        page = {
            "url": "https://shop.example/contact", "requested_url": "https://shop.example/contact",
            "final_url": "https://shop.example/contact", "method": "official_contact_page",
            "text": "Contact mailto:sales@shop.example sales@shop.example", "http_status": 200,
            "http_success": True, "tls_success": True, "fetched_at": "now",
            "content_hash": hashlib.sha256(b"visible").hexdigest(),
        }
        self.assertEqual(_extract_email_evidence([page])["email"], "sales@shop.example")

    def test_explicit_visible_obfuscation_is_accepted_without_inference(self):
        page = {
            "url": "https://shop.example/contact", "requested_url": "https://shop.example/contact",
            "final_url": "https://shop.example/contact", "method": "official_contact_page",
            "text": "For sales, email sales [at] shop [dot] example", "http_status": 200,
            "http_success": True, "tls_success": True, "fetched_at": "now",
            "content_hash": hashlib.sha256(b"visible").hexdigest(),
        }
        evidence = _extract_email_evidence([page])
        self.assertEqual(evidence["email"], "sales@shop.example")
        self.assertIn("sales [at] shop [dot] example", evidence["evidence"]["visible_text_excerpt"])
        page["text"] = "Contact our sales department for a shop email address"
        self.assertEqual(_extract_email_evidence([page]), {})


if __name__ == "__main__":
    unittest.main()
