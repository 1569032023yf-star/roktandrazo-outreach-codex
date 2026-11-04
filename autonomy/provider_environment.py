"""Pinned provider-only configuration, not dispatch or credential authorization."""
import json
from contextlib import contextmanager
from publisher_channel.install_inputs import InstallInputPins

SCHEMA = 'rokt.provider-environment.v1'
KEYS = frozenset({
    'WORKBUDDY_DISCOVERY_PROVIDER', 'GOOGLE_MAPS_API_KEY',
    'GOOGLE_PLACES_LOCATION_BIAS_JSON', 'GOOGLE_PLACES_LOCATION_RESTRICTION_JSON',
    'BROWSER_MAPS_CACHE_DIR', 'BROWSER_MAPS_MODE', 'BROWSER_MAPS_JSON_FILE',
})


@contextmanager
def pinned_provider_environment(path, expected_sha256):
    # Handles deny input writes/deletion and ancestor renames while parsing.
    # The digest must come from the approved runtime plan, never this file.
    with InstallInputPins() as pins:
        raw = pins.add(path, expected_sha256, limit=65536)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:raise ValueError('PROVIDER_CONFIG_DUPLICATE_KEY')
                result[key] = value
            return result
        value = json.loads(raw, object_pairs_hook=unique)
        if (type(value) is not dict or set(value) != {'schema', 'environment'} or
            value['schema'] != SCHEMA or type(value['environment']) is not dict):
            raise ValueError('PROVIDER_CONFIG_SCHEMA')
        environment = value['environment']
        if not set(environment) <= KEYS or any(type(v) is not str or '\x00' in v for v in environment.values()):
            raise ValueError('PROVIDER_CONFIG_KEYS')
        if environment.get('WORKBUDDY_DISCOVERY_PROVIDER') not in ('google_places', 'browser_maps'):
            raise ValueError('REAL_PROVIDER_REQUIRED')
        if 'BROWSER_MAPS_MODE' in environment and environment['BROWSER_MAPS_MODE'] not in ('file', 'direct', 'auto'):
            raise ValueError('BROWSER_MODE_REJECTED')
        pins.revalidate()
        yield dict(environment)
        pins.revalidate()


def load_pinned_provider_environment(path, expected_sha256):
    with pinned_provider_environment(path, expected_sha256) as environment:
        return dict(environment)


@contextmanager
def pinned_provider_adapter(path, expected_sha256):
    """Construct an existing real adapter without inheriting unapproved settings.

    This binds configuration only; it does not grant dispatch or billing authority.
    The caller must retain this context for the whole adapter lifetime.
    """
    with pinned_provider_environment(path, expected_sha256) as environment:
        name = environment['WORKBUDDY_DISCOVERY_PROVIDER']
        if name == 'google_places':
            from discovery.providers.google_places import GooglePlacesProvider
            def location(key):
                raw = environment.get(key, '').strip()
                if not raw:
                    return None
                value = json.loads(raw)
                if type(value) is not dict:
                    raise ValueError('PROVIDER_LOCATION_OBJECT_REQUIRED')
                return value
            adapter = GooglePlacesProvider(
                api_key=environment.get('GOOGLE_MAPS_API_KEY', ''),
                location_bias=location('GOOGLE_PLACES_LOCATION_BIAS_JSON'),
                location_restriction=location('GOOGLE_PLACES_LOCATION_RESTRICTION_JSON'),
                use_environment=False,
            )
        else:
            from discovery.providers.browser_maps import BrowserMapsProvider
            adapter = BrowserMapsProvider(
                cache_dir=environment.get('BROWSER_MAPS_CACHE_DIR'),
                mode=environment.get('BROWSER_MAPS_MODE', 'file'),
                json_file=environment.get('BROWSER_MAPS_JSON_FILE', ''),
                use_environment=False,
            )
        yield adapter
