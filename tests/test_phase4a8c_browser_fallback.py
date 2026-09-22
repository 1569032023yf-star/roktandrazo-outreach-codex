"""Phase 4A.8C browser fallback safety / 浏览器回退安全。"""
import http.client
import time
import urllib.error
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from discovery.discovery_service import (
    BrowserFallbackWebsiteFetcher,
    _extract_email_evidence,
    _fetch_official_pages,
)


def page(url="https://shop.example.com", text="Example Shop"):
    return {"status": 200, "final_url": url, "tls_verified": True,
            "html": f"<title>{text}</title>", "text": text,
            "fetched_at": "2026-09-22T00:00:00+00:00", "fetch_transport": "browser_fallback"}


class RaisingFetcher:
    def __init__(self, exc):
        self.exc = exc

    def fetch(self, _url):
        raise self.exc


class BrowserFallbackTests(unittest.TestCase):
    def test_successful_static_fetch_never_starts_browser(self):
        static = Mock()
        static.fetch.return_value = page()
        fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=static)
        fetcher._browser_fetch = Mock()
        self.assertEqual(fetcher.fetch("https://shop.example.com")["fetch_transport"], "browser_fallback")
        fetcher._browser_fetch.assert_not_called()

    def test_http_403_and_timeout_can_use_bounded_browser_fallback(self):
        for exc in (urllib.error.HTTPError("https://shop.example.com", 403, "forbidden", {}, None), TimeoutError("timeout")):
            with self.subTest(exc=type(exc).__name__):
                fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=RaisingFetcher(exc))
                fetcher._browser_fetch = Mock(return_value=page())
                self.assertEqual(fetcher.fetch("https://shop.example.com")["status"], 200)
                fetcher._browser_fetch.assert_called_once()

    def test_expired_site_deadline_prevents_static_and_browser_work(self):
        static = Mock()
        fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=static, site_timeout_seconds=1)
        fetcher._site_deadline = time.monotonic() - 0.01
        fetcher._browser_fetch = Mock()
        with self.assertRaises(TimeoutError):
            fetcher.fetch("https://shop.example.com")
        static.fetch.assert_not_called()
        fetcher._browser_fetch.assert_not_called()

    def test_external_redirect_and_failed_render_cannot_be_official_evidence(self):
        fallback = BrowserFallbackWebsiteFetcher(static_fetcher=RaisingFetcher(
            urllib.error.HTTPError("https://shop.example.com", 403, "forbidden", {}, None)
        ))
        fallback._browser_fetch = Mock(return_value=page("https://directory.example.net/contact", "shop@example.com"))
        self.assertEqual(_fetch_official_pages("https://shop.example.com", fallback), [])
        failed = BrowserFallbackWebsiteFetcher(static_fetcher=RaisingFetcher(http.client.RemoteDisconnected("closed")))
        failed._browser_fetch = Mock(side_effect=TimeoutError("browser page timeout"))
        self.assertEqual(_fetch_official_pages("https://shop.example.com", failed), [])

    def test_visible_browser_text_is_accepted_but_hidden_script_text_is_not(self):
        visible = [{"url": "https://shop.example.com/contact", "requested_url": "https://shop.example.com/contact",
                    "final_url": "https://shop.example.com/contact", "method": "browser_fallback:official_contact_page",
                    "text": "Email sales@shop.example.com for wholesale", "html": "<p>Email sales@shop.example.com</p>",
                    "http_status": 200, "http_success": True, "tls_success": True,
                    "fetched_at": "2026-09-22T00:00:00+00:00", "content_hash": "a" * 64}]
        self.assertEqual(_extract_email_evidence(visible)["email"], "sales@shop.example.com")
        hidden = [{**visible[0], "text": "Contact us", "html": "<script>sales@shop.example.com</script>"}]
        self.assertEqual(_extract_email_evidence(hidden), {})

    def test_no_public_email_requires_a_successful_first_party_render(self):
        fallback = BrowserFallbackWebsiteFetcher(static_fetcher=RaisingFetcher(
            urllib.error.HTTPError("https://shop.example.com", 403, "forbidden", {}, None)
        ))
        fallback._browser_fetch = Mock(return_value=page("https://shop.example.com/contact", "Example Shop contact"))
        pages = _fetch_official_pages("https://shop.example.com", fallback)
        self.assertTrue(pages)
        self.assertEqual(_extract_email_evidence(pages), {})

    def test_browser_child_job_is_closed_after_a_completed_page(self):
        class Pipe:
            def __init__(self): self.closed = False
            def poll(self): return True
            def recv(self): return "ok", page()
            def close(self): self.closed = True
        class Process:
            pid = 777
            def start(self): pass
            def join(self, _seconds): pass
            def is_alive(self): return False
            def terminate(self): raise AssertionError("completed process must not terminate")
        parent, child = Pipe(), Pipe()
        context = SimpleNamespace(Process=lambda **_kwargs: Process())
        fetcher = BrowserFallbackWebsiteFetcher(page_timeout_seconds=1, site_timeout_seconds=1)
        with patch("discovery.discovery_service.multiprocessing.Pipe", return_value=(parent, child)), \
             patch("discovery.discovery_service.multiprocessing.get_context", return_value=context), \
             patch("discovery.website_resolver._attach_kill_on_close_job", return_value="job") as attach, \
             patch("discovery.website_resolver._close_kill_job") as close:
            self.assertEqual(fetcher._browser_fetch("https://shop.example.com")["status"], 200)
        attach.assert_called_once_with(777)
        close.assert_called_once_with("job")
        self.assertTrue(parent.closed)
        self.assertTrue(child.closed)

    def test_hung_browser_child_is_hard_stopped_at_deadline(self):
        class Pipe:
            def poll(self): return False
            def close(self): pass
        class Process:
            pid = 778
            killed = False
            def start(self): pass
            def join(self, _seconds): pass
            def is_alive(self): return not self.killed
            def kill(self): self.killed = True
        parent, child = Pipe(), Pipe()
        process = Process()
        context = SimpleNamespace(Process=lambda **_kwargs: process)
        fetcher = BrowserFallbackWebsiteFetcher(page_timeout_seconds=0.01, site_timeout_seconds=1)
        with patch("discovery.discovery_service.multiprocessing.Pipe", return_value=(parent, child)), \
             patch("discovery.discovery_service.multiprocessing.get_context", return_value=context), \
             patch("discovery.website_resolver._attach_kill_on_close_job", return_value="job"), \
             patch("discovery.website_resolver._close_kill_job"):
            with self.assertRaises(TimeoutError):
                fetcher._browser_fetch("https://shop.example.com")
        self.assertTrue(process.killed)
