"""Offline checks of real adapter contract integration, with no service calls."""
import tempfile
import unittest
from discovery.providers.base import load_provider
from discovery.providers.browser_maps import BrowserMapsProvider
from discovery.providers.google_places import GooglePlacesProvider
from discovery.providers.serpapi_maps import SerpApiMapsProvider


class ProviderContractTests(unittest.TestCase):
    def test_google_uses_existing_adapter_with_missing_billing(self):
        provider = load_provider("google_places")
        self.assertIsInstance(provider, GooglePlacesProvider)
        self.assertEqual(provider.contract.authentication, "X-Goog-Api-Key")
        self.assertEqual(provider.contract.status, "CONTRACT_MISSING")
        self.assertFalse(provider.contract.authoritative_cost_available)
        self.assertFalse(provider.contract.supports_operation_lookup)
        self.assertFalse(provider.contract.supports_idempotent_submit)
        self.assertIn("billed_amount_currency_credits", provider.contract.missing_fields)

    def test_file_adapter_does_not_claim_network_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = BrowserMapsProvider(cache_dir=directory, mode="file")
            self.assertEqual(provider.contract.transport, "local_file")
            self.assertIn("browser_request_receipt", provider.contract.missing_fields)
            self.assertFalse(provider.contract.supports_cancel)

    def test_serpapi_disabled_even_with_key(self):
        provider = SerpApiMapsProvider(api_key="offline-test-value")
        self.assertFalse(provider.configured)
        self.assertEqual(provider.contract.status, "DISABLED")
        result = provider.search_places("q", "c", "s")
        self.assertEqual(result.request_count, 0)
        self.assertEqual(result.status, "experimental_disabled")


if __name__ == "__main__":
    unittest.main()
