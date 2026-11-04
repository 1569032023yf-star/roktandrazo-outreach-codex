"""Offline transport tests; no provider calls or cost acceptance."""
import unittest
import http.client
import io
import importlib.util
from pathlib import Path
import sys
import urllib.error
from unittest.mock import patch
from discovery.providers.google_places import GooglePlacesProvider


class UnknownTransportTests(unittest.TestCase):
    def test_disconnect_is_not_retried_even_with_retry_budget(self):
        for failure in (urllib.error.URLError("secret-marker"),
                        TimeoutError("secret-marker"),
                        ConnectionResetError("secret-marker"),
                        http.client.RemoteDisconnected("secret-marker"),
                        urllib.error.HTTPError("https://example.invalid", 503, "secret-marker", {}, None)):
            with self.subTest(failure=type(failure).__name__):
                provider = GooglePlacesProvider(api_key="fixture", max_retries=5,
                                                min_interval_seconds=0)
                with patch("discovery.providers.google_places._open_request", side_effect=failure) as request:
                    page = provider.search_places("fixture", "fixture", "TN")
                self.assertEqual(request.call_count, 1)
                self.assertEqual(page.status, "provider_outcome_unknown")
                self.assertFalse(page.ok)
                self.assertEqual(page.request_count, 1)
                self.assertNotIn("secret-marker", page.error)
                self.assertEqual(page.results, [])

    def test_bad_response_after_submission_is_unknown(self):
        for response in (b"not-json", b'{"places":null}', b'{"places":[null]}', b"\xff"):
            with self.subTest(response=response):
                with patch("discovery.providers.google_places._open_request", return_value=io.BytesIO(response)) as request:
                    page = GooglePlacesProvider(api_key="fixture", min_interval_seconds=0).search_places("fixture", "fixture", "TN")
                self.assertEqual(request.call_count, 1)
                self.assertEqual(page.status, "provider_outcome_unknown")
                self.assertEqual(page.results, [])

    def test_persisted_unknown_blocks_new_service_instance(self):
        from tests.test_discovery_service import DiscoveryDb
        # The legacy compatibility suite deliberately replaces this canonical
        # module in sys.modules with a historical production snapshot. Load the
        # actual candidate file under a private name without changing that suite.
        source = Path(__file__).resolve().parents[1] / "discovery/discovery_service.py"
        spec = importlib.util.spec_from_file_location("_u1_current_discovery_service", source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {spec.name: module}):
            spec.loader.exec_module(module)
        DiscoveryService = module.DiscoveryService
        self.assertEqual(Path(module.__file__).resolve(), source.resolve())
        from retail_city_queue import activate_next_city
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            provider = GooglePlacesProvider(api_key="fixture", min_interval_seconds=0)
            with patch("discovery.providers.google_places._open_request", side_effect=urllib.error.URLError("lost")) as request:
                first = DiscoveryService(conn, provider=provider).run_places_batch(city)
                conn.commit()
                resumed = activate_next_city(conn)
                second = DiscoveryService(conn, provider=GooglePlacesProvider(api_key="fixture")).run_places_batch(resumed)
            self.assertEqual(first.status, "provider_outcome_unknown")
            self.assertEqual(second.status, "provider_outcome_unknown")
            self.assertEqual(request.call_count, 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lead_discovery_results").fetchone()[0], 0)

    def test_missing_configuration_does_not_submit(self):
        with patch.dict("os.environ", {}, clear=True), patch("discovery.providers.google_places._open_request") as request:
            page = GooglePlacesProvider().search_places("fixture", "fixture", "TN")
        request.assert_not_called()
        self.assertEqual(page.status, "provider_not_configured")


if __name__ == "__main__":
    unittest.main()
