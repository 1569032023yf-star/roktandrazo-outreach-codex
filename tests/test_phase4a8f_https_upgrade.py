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
    _canonical_same_party_url,
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
        urls = _fixed_first_party_urls("http://shop.example/catalog/item?ref=official")
        self.assertEqual(urls[:2], [
            ("https://shop.example/catalog/item?ref=official", "official_https_upgrade_homepage"),
            ("http://shop.example/catalog/item?ref=official", "official_http_fallback"),
        ])
        self.assertEqual(urlsplit(urls[0][0]).netloc, urlsplit(urls[1][0]).netloc)
        self.assertEqual(urlsplit(urls[0][0]).path, urlsplit(urls[1][0]).path)
        self.assertLessEqual(len(urls), MAX_FIRST_PARTY_PAGES_PER_SITE)

    def test_www_http_adds_only_same_party_apex_alias_between_https_and_http(self):
        urls = _fixed_first_party_urls("http://www.shop.example/contact?x=1")
        self.assertEqual(urls[:3], [
            ("https://www.shop.example/contact?x=1", "official_https_upgrade_homepage"),
            ("https://shop.example/contact?x=1", "official_https_apex_alias"),
            ("http://www.shop.example/contact?x=1", "official_http_fallback"),
        ])
        self.assertLessEqual(len(urls), MAX_FIRST_PARTY_PAGES_PER_SITE)

    def test_unrelated_host_is_rejected_by_existing_same_party_semantics(self):
        self.assertEqual(
            _canonical_same_party_url("https://www.shop.example", "https://unrelated.example/contact", "https://www.shop.example"),
            "",
        )

    def test_successful_https_visible_email_never_downgrades_to_http(self):
        https = "https://shop.example"
        http = "http://shop.example"
        fetcher = RecordingFetcher({https: page(https, "Contact info@shop.example")})
        evidence = _extract_email_evidence(_fetch_official_pages(http, fetcher))
        self.assertEqual(evidence["email"], "info@shop.example")
        self.assertEqual(fetcher.requested[0], https)
        self.assertNotIn(http, fetcher.requested)

    def test_successful_apex_https_avoids_http_downgrade_and_extracts_visible_email(self):
        www_https = "https://www.shop.example"
        apex_https = "https://shop.example"
        http = "http://www.shop.example"
        fetcher = RecordingFetcher({
            www_https: page(www_https, "", status=400),
            apex_https: page(apex_https, "Email sales@shop.example"),
        })
        evidence = _extract_email_evidence(_fetch_official_pages(http, fetcher))
        self.assertEqual(fetcher.requested[:2], [www_https, apex_https])
        self.assertNotIn(http, fetcher.requested)
        self.assertEqual(evidence["email"], "sales@shop.example")

    def test_good_https_www_homepage_does_not_probe_apex_alias(self):
        www_https = "https://www.shop.example"
        apex_https = "https://shop.example"
        fetcher = RecordingFetcher({www_https: page(www_https, "Contact info@shop.example")})
        _fetch_official_pages(www_https, fetcher)
        self.assertEqual(fetcher.requested[0], www_https)
        self.assertNotIn(apex_https, fetcher.requested)

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

    def test_failed_https_compatibility_probe_marks_only_automatic_recovery_exhausted(self):
        root = "https://www.shop.example"
        contact = "https://www.shop.example/contact"

        class StaticFailures:
            timeout_seconds = 12

            def fetch(self, url):
                code = 400 if url == root else 403
                raise HTTPError(url, code, "blocked", {}, None)

        fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=StaticFailures())
        fetcher._browser_fetch = Mock(side_effect=TimeoutError("browser timeout"))
        fetcher.begin_site()
        with self.assertRaises(TimeoutError):
            fetcher.fetch_https_upgrade(root)
        with self.assertRaises(TimeoutError):
            fetcher.fetch(contact)
        fetcher.end_site()
        self.assertTrue(fetcher.last_site_automation_recovery_exhausted)

    def test_plain_http400_without_browser_attempt_stays_retryable(self):
        url = "https://shop.example"

        class Static400:
            timeout_seconds = 12

            def fetch(self, _url):
                raise HTTPError(url, 400, "bad request", {}, None)

        fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=Static400())
        fetcher._browser_fetch = Mock()
        fetcher.begin_site()
        with self.assertRaises(HTTPError):
            fetcher.fetch(url)
        fetcher.end_site()
        fetcher._browser_fetch.assert_not_called()
        self.assertFalse(fetcher.last_site_automation_recovery_exhausted)

    def test_no_sciencenter_special_case_exists(self):
        import inspect
        import discovery.discovery_service as service
        self.assertNotIn("sciencenter", inspect.getsource(service).lower())


if __name__ == "__main__":
    unittest.main()
