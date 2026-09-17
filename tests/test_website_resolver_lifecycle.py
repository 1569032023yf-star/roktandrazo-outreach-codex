"""Lifecycle guarantees for bounded provider-backed website resolution."""
from __future__ import annotations

import time
import unittest

from discovery.models import ProviderPage
from discovery.website_resolver import ProviderWebsiteResolver


class HangingProvider:
    provider_name = "hanging"

    def search_places(self, *_args, **_kwargs):
        time.sleep(10)
        return ProviderPage(provider="hanging", query="", city="", state="", page_cursor="")


class EmptyProvider:
    provider_name = "empty"

    def search_places(self, *_args, **_kwargs):
        return ProviderPage(provider="empty", query="", city="", state="", page_cursor="")


SUBJECT = {"business_name": "Lifecycle Test Store", "city": "Ithaca", "state": "NY"}


class WebsiteResolverLifecycleTests(unittest.TestCase):
    def test_hanging_provider_returns_within_deadline(self):
        started = time.monotonic()
        result = ProviderWebsiteResolver(HangingProvider(), timeout_seconds=0.3).resolve(SUBJECT)
        elapsed = time.monotonic() - started
        self.assertEqual(result.status, "network_retry")
        self.assertIn("provider_timeout", result.error)
        self.assertLess(elapsed, 3.0)

    def test_next_lead_runs_after_timeout(self):
        first = ProviderWebsiteResolver(HangingProvider(), timeout_seconds=0.3).resolve(SUBJECT)
        second = ProviderWebsiteResolver(EmptyProvider(), timeout_seconds=1.0).resolve(SUBJECT)
        self.assertEqual(first.status, "network_retry")
        self.assertEqual(second.status, "not_found")

