"""Pinned provider-only configuration, not dispatch or credential authorization."""
import json
from publisher_channel.install_inputs import InstallInputPins

SCHEMA = 'rokt.provider-environment.v1'
KEYS = frozenset({
    'WORKBUDDY_DISCOVERY_PROVIDER', 'GOOGLE_MAPS_API_KEY',
    'GOOGLE_PLACES_LOCATION_BIAS_JSON', 'GOOGLE_PLACES_LOCATION_RESTRICTION_JSON',
    'BROWSER_MAPS_CACHE_DIR', 'BROWSER_MAPS_MODE', 'BROWSER_MAPS_JSON_FILE',
})


def load_pinned_provider_environment(path, expected_sha256):
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
        return dict(environment)
