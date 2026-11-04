import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from autonomy.provider_environment import pinned_provider_adapter
from discovery.providers.browser_maps import BrowserMapsProvider, _save_cache, _cache_key
from discovery.models import ProviderPage, PlaceSearchResult


class AdapterBindingTests(unittest.TestCase):
    def config(self, root, environment):
        path = root / 'provider.json'
        raw = json.dumps({'schema': 'rokt.provider-environment.v1', 'environment': environment}).encode()
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def test_google_approved_absence_never_inherits_credentials_or_location(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest = self.config(Path(directory), {'WORKBUDDY_DISCOVERY_PROVIDER': 'google_places'})
            with patch.dict(os.environ, {'GOOGLE_MAPS_API_KEY': 'unapproved', 'GOOGLE_PLACES_LOCATION_BIAS_JSON': '{"circle":{}}'}):
                before = dict(os.environ)
                with pinned_provider_adapter(path, digest) as provider:
                    self.assertFalse(provider.configured)
                    self.assertIsNone(provider.location_bias)
                    self.assertEqual(provider.contract.status, 'CONTRACT_MISSING')
                    with self.assertRaises(OSError):
                        path.write_bytes(b'changed')
                self.assertEqual(dict(os.environ), before)

    def test_invalid_location_fails_before_adapter_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest = self.config(Path(directory), {'WORKBUDDY_DISCOVERY_PROVIDER': 'google_places', 'GOOGLE_PLACES_LOCATION_BIAS_JSON': '[]'})
            with self.assertRaisesRegex(ValueError, 'OBJECT_REQUIRED'):
                with pinned_provider_adapter(path, digest):
                    self.fail('invalid configuration yielded adapter')

    def test_instance_cache_isolation_and_readonly_construction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = BrowserMapsProvider(str(root/'first'), 'file', use_environment=False)
            second = BrowserMapsProvider(str(root/'second'), 'file', use_environment=False)
            self.assertFalse(first._cache_dir.exists())
            self.assertFalse(second._cache_dir.exists())
            page = ProviderPage(provider='browser_maps', query='shop', city='City', state='ST', page_cursor='0', results=[PlaceSearchResult(provider='browser_maps', business_name='First', provider_result_id='fixture', place_id='', formatted_address='', city='City', state='ST')])
            _save_cache(page, cache_dir=first._cache_dir)
            with patch('discovery.providers.browser_maps.CACHE_DIR', root/'wrong'):
                self.assertEqual(first.search_places('shop', 'City', 'ST').results[0].business_name, 'First')
                self.assertEqual(second.search_places('shop', 'City', 'ST').status, 'no_data_available')
            self.assertFalse((root/'wrong').exists())

    def test_approved_browser_does_not_inherit_json_or_direct_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, digest = self.config(root, {'WORKBUDDY_DISCOVERY_PROVIDER': 'browser_maps', 'BROWSER_MAPS_CACHE_DIR': str(root/'cache')})
            with patch.dict(os.environ, {'BROWSER_MAPS_MODE': 'direct', 'BROWSER_MAPS_JSON_FILE': str(root/'unapproved.json')}), patch('discovery.providers.browser_maps._scrape_direct', side_effect=AssertionError('network forbidden')):
                with pinned_provider_adapter(path, digest) as provider:
                    self.assertEqual(provider.search_places('shop','City','ST').status, 'no_data_available')
                    self.assertFalse((root/'cache').exists())

    def test_direct_result_saved_to_instance_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = BrowserMapsProvider(str(root/'instance'), 'direct', use_environment=False)
            page = ProviderPage(provider='browser_maps', query='shop', city='City', state='ST', page_cursor='')
            with patch('discovery.providers.browser_maps._scrape_direct', return_value=page), patch('discovery.providers.browser_maps.CACHE_DIR', root/'wrong'):
                provider.search_places('shop','City','ST')
            self.assertTrue((root/'instance'/_cache_key('shop','City','ST','')).is_file())
            self.assertFalse((root/'wrong').exists())
