"""Phase 4A.8F HTTPS-first official-site recovery / HTTPS 优先官网恢复。"""
import unittest
from urllib.parse import urlsplit
from urllib.error import HTTPError
from unittest.mock import Mock

from discovery.discovery_service import (
    BrowserFallbackWebsiteFetcher,
    MAX_FIRST_PARTY_PAGES_PER_SITE,
    _extract_email_evidence,
    _fetch_official_pages,
    _fixed_first_party_urls,
)


def page(url, html, *, final_url=None, status=200, tls=True):
    from discovery.discovery_service import _visible_text_from_html
    return {
        "text": _visible_text_from_html(html), "html": html, "status": status,
        "final_url": final_url or url, "tls_verified": tls,
        "fetched_at": "2026-09-22T00:00:00+00:00",
    }


class RecordingFetcher:
    def __init__(self, responses):
        self.responses = responses
        self.requested = []

    def fetch(self, url):
        self.requested.append(url)
        value = self.responses.get(url)
        if isinstance(value, Exception):
            raise value
        return value or page(url, "", status=404)


class HttpsUpgradeTests(unittest.TestCase):
    def test_explicit_https_probe_order_is_unchanged(self):
        urls = _fixed_first_party_urls("https://shop.example/path")
        self.assertEqual(urls[0], ("https://shop.example", "official_homepage"))
        self.assertFalse(any(method == "official_http_fallback" for _url, method in urls))

    def test_explicit_http_probes_same_host_path_over_https_then_http(self):
        urls = _fixed_first_party_urls("http://www.shop.example/catalog/item?ref=official")
        self.assertEqual(urls[:2], [
            ("https://www.shop.example/catalog/item?ref=official", "official_https_upgrade_homepage"),
            ("http://www.shop.example/catalog/item?ref=official", "official_http_fallback"),
        ])
        self.assertEqual(urlsplit(urls[0][0]).netloc, urlsplit(urls[1][0]).netloc)
        self.assertEqual(urlsplit(urls[0][0]).path, urlsplit(urls[1][0]).path)
        self.assertLessEqual(len(urls), MAX_FIRST_PARTY_PAGES_PER_SITE)

    def test_successful_https_visible_email_never_downgrades_to_http(self):
        https = "https://shop.example"
        http = "http://shop.example"
        fetcher = RecordingFetcher({https: page(https, "Contact info@shop.example")})
        evidence = _extract_email_evidence(_fetch_official_pages(http, fetcher))
        self.assertEqual(evidence["email"], "info@shop.example")
        self.assertEqual(fetcher.requested[0], https)
        self.assertNotIn(http, fetcher.requested)

    def test_https_failure_falls_back_to_original_http_path(self):
        https = "https://shop.example/path"
        http = "http://shop.example/path"
        fetcher = RecordingFetcher({
            https: page(https, "", status=400),
            http: page(http, "Contact info@shop.example"),
        })
        evidence = _extract_email_evidence(_fetch_official_pages(http, fetcher))
        self.assertEqual(fetcher.requested[:2], [https, http])
        self.assertEqual(evidence["email"], "info@shop.example")

    def test_cross_party_https_redirect_is_rejected_before_http_fallback(self):
        https = "https://shop.example"
        http = "http://shop.example"
        fetcher = RecordingFetcher({
            https: page(https, "info@evil.example", final_url="https://evil.example/contact"),
            http: page(http, "Contact info@shop.example"),
        })
        evidence = _extract_email_evidence(_fetch_official_pages(http, fetcher))
        self.assertEqual(fetcher.requested[:2], [https, http])
        self.assertEqual(evidence["email"], "info@shop.example")

    def test_upgraded_https_http_400_uses_browser_without_access_unreachable_marker(self):
        url = "https://shop.example"

        class Static400:
            timeout_seconds = 12

            def fetch(self, _url):
                raise HTTPError(url, 400, "bad request", {}, None)

        fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=Static400())
        fetcher._browser_fetch = Mock(return_value=page(url, "Contact info@shop.example"))
        pages = _fetch_official_pages("http://shop.example", fetcher)
        self.assertEqual(_extract_email_evidence(pages)["email"], "info@shop.example")
        fetcher._browser_fetch.assert_called_once_with(url)
        self.assertFalse(fetcher.last_site_automation_recovery_exhausted)

    def test_no_sciencenter_special_case_exists(self):
        import inspect
        import discovery.discovery_service as service
        self.assertNotIn("sciencenter", inspect.getsource(service).lower())


if __name__ == "__main__":
    unittest.main()
