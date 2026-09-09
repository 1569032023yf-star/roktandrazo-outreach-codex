"""Browser-based Google Maps provider — no API key required.

Uses Playwright to search Google Maps in a real browser.
Results are cached as JSON files for idempotent replay.

Provider name: browser_maps

Environment:
    DISCOVERY_PROVIDER=browser_maps
    BROWSER_MAPS_CACHE_DIR=data/browser_maps_cache/

Two operating modes:
  1. FILE mode (default): reads pre-generated JSON from manual scraper runs
  2. DIRECT mode: calls browser scraper inline (requires Playwright + headless browser)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from discovery.models import PlaceSearchResult, ProviderPage, utc_now
from discovery.providers.base import SearchProvider


CACHE_DIR = Path(os.getenv("BROWSER_MAPS_CACHE_DIR", str(PROJECT_DIR / "data" / "browser_maps_cache")))


def _cache_key(query: str, city: str, state: str, page: str) -> str:
    """Generate a cache filename from query parameters."""
    safe = f"{query}_{city}_{state}_{page}".lower().replace(' ', '_').replace('/', '_')
    # Truncate for filesystem safety
    if len(safe) > 180:
        import hashlib
        safe = hashlib.sha256(safe.encode()).hexdigest()[:32]
    return safe + '.json'


def _load_cache(query: str, city: str, state: str, page: str) -> ProviderPage | None:
    """Try to load cached results from a JSON file."""
    cache_path = CACHE_DIR / _cache_key(query, city, state, page)
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        results = []
        for r in raw.get('results', []):
            results.append(PlaceSearchResult(**{
                k: r.get(k, '') if k not in ('types', 'raw_payload') else r.get(k, [])
                for k in PlaceSearchResult.__dataclass_fields__
                if k in r
            }))

        return ProviderPage(
            provider='browser_maps',
            query=query,
            city=city,
            state=state,
            page_cursor=page,
            results=results,
            next_page_cursor=raw.get('next_page_cursor', ''),
            status=raw.get('status', 'ok'),
            error=raw.get('error', ''),
            request_count=raw.get('request_count', 1),
            cost_units=raw.get('cost_units', 0),
            fetched_at=raw.get('collected_at', utc_now()),
        )
    except Exception as e:
        return ProviderPage(
            provider='browser_maps',
            query=query, city=city, state=state,
            page_cursor=page,
            status='cache_read_error',
            error=f'failed to read cache: {e}',
        )


def _save_cache(page: ProviderPage) -> None:
    """Save scraper results to cache JSON."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / _cache_key(page.query, page.city, page.state, page.page_cursor)

    output = {
        'provider': page.provider,
        'query': page.query,
        'city': page.city,
        'state': page.state,
        'page_cursor': page.page_cursor,
        'next_page_cursor': page.next_page_cursor,
        'status': page.status,
        'error': page.error,
        'results': [],
        'request_count': page.request_count,
        'cost_units': page.cost_units,
        'collected_at': page.fetched_at,
    }

    for r in page.results:
        rd = {
            'provider': r.provider,
            'provider_result_id': r.provider_result_id,
            'place_id': r.place_id,
            'business_name': r.business_name,
            'formatted_address': r.formatted_address,
            'city': r.city,
            'state': r.state,
            'country': r.country,
            'postal_code': r.postal_code,
            'phone': r.phone,
            'website': r.website,
            'business_status': r.business_status,
            'primary_type': r.primary_type,
            'types': r.types,
            'source_query': r.source_query,
            'source_url': r.source_url,
            'raw_payload': r.raw_payload,
            'next_page_cursor': r.next_page_cursor,
            'fetched_at': r.fetched_at,
            'location_lat': r.location_lat,
            'location_lng': r.location_lng,
        }
        output['results'].append(rd)

    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def _scrape_direct(query: str, city: str, state: str, max_results: int, headless: bool = True) -> ProviderPage:
    """Direct browser scraping (called inline from discovery pipeline)."""
    try:
        from discovery.providers.browser_maps_scraper import scrape_google_maps

        raw = scrape_google_maps(
            query=query,
            city=city,
            state=state,
            max_results=max_results,
            headless=headless,
        )

        results = []
        for r in raw.get('results', []):
            try:
                results.append(PlaceSearchResult(
                    provider=r.get('provider', 'browser_maps'),
                    provider_result_id=r.get('provider_result_id', ''),
                    place_id=r.get('place_id', ''),
                    business_name=r.get('business_name', ''),
                    formatted_address=r.get('formatted_address', ''),
                    city=r.get('city', city),
                    state=r.get('state', state),
                    country=r.get('country', 'US'),
                    postal_code=r.get('postal_code', ''),
                    phone=r.get('phone', ''),
                    website=r.get('website', ''),
                    business_status=r.get('business_status', ''),
                    primary_type=r.get('primary_type', ''),
                    types=r.get('types', []),
                    source_query=r.get('source_query', query),
                    source_url=r.get('source_url', ''),
                    raw_payload=r.get('raw_payload', {}),
                    next_page_cursor='',
                    fetched_at=r.get('fetched_at', utc_now()),
                    location_lat=r.get('location_lat'),
                    location_lng=r.get('location_lng'),
                ))
            except Exception:
                continue

        return ProviderPage(
            provider='browser_maps',
            query=query, city=city, state=state,
            page_cursor='',
            results=results,
            next_page_cursor=str(len(results)),
            status=raw.get('status', 'ok'),
            error=raw.get('error', ''),
            request_count=1, cost_units=0,
            fetched_at=utc_now(),
        )

    except ImportError as e:
        return ProviderPage(
            provider='browser_maps', query=query, city=city, state=state,
            page_cursor='',
            status='playwright_not_installed',
            error=f'Playwright not available: {e}. Run: pip install playwright && playwright install chromium',
        )
    except Exception as e:
        return ProviderPage(
            provider='browser_maps', query=query, city=city, state=state,
            page_cursor='',
            status='scrape_error',
            error=f'Scrape failed: {e}',
        )


class BrowserMapsProvider(SearchProvider):
    """Google Maps provider using browser automation (no API key).

    Reads from cached JSON files if available.
    Falls back to direct browser scraping if not cached.
    """

    provider_name = "browser_maps"

    def __init__(
        self,
        cache_dir: str | None = None,
        mode: str | None = None,  # env BROWSER_MAPS_MODE, else file
        headless: bool = True,
    ):
        self._cache_dir = Path(cache_dir or os.getenv("BROWSER_MAPS_CACHE_DIR", str(CACHE_DIR)))
        self._mode = mode or os.getenv("BROWSER_MAPS_MODE", "file")
        self._headless = headless
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        """Always configured since no API key is needed.

        Returns False only if Playwright is completely unavailable
        AND no cached data exists.
        """
        if self._mode == "file":
            return True  # File mode always works if we have cached data
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            # Check if we have any cached data as fallback
            return bool(list(self._cache_dir.glob('*.json')))

    def _load_from_json_file(self, json_path: str, query: str, city: str, state: str) -> ProviderPage:
        """Load results from a specific JSON output file."""
        path = Path(json_path)
        if not path.is_absolute():
            path = PROJECT_DIR / json_path

        if not path.exists():
            return ProviderPage(
                provider=self.provider_name, query=query, city=city, state=state,
                page_cursor='',
                status='json_file_not_found',
                error=f'Scraper output not found: {path}. Run browser_maps_scraper.py first.',
            )

        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)

            results = []
            for r in raw.get('results', []):
                try:
                    results.append(PlaceSearchResult(
                        provider=r.get('provider', 'browser_maps'),
                        provider_result_id=r.get('provider_result_id', ''),
                        place_id=r.get('place_id', ''),
                        business_name=r.get('business_name', ''),
                        formatted_address=r.get('formatted_address', ''),
                        city=r.get('city', city),
                        state=r.get('state', state),
                        country=r.get('country', 'US'),
                        postal_code=r.get('postal_code', ''),
                        phone=r.get('phone', ''),
                        website=r.get('website', ''),
                        business_status=r.get('business_status', 'OPERATIONAL'),
                        primary_type=r.get('primary_type', ''),
                        types=r.get('types', []),
                        source_query=r.get('source_query', query),
                        source_url=r.get('source_url', ''),
                        raw_payload=r.get('raw_payload', {}),
                        next_page_cursor='',
                        fetched_at=r.get('fetched_at', utc_now()),
                        location_lat=r.get('location_lat'),
                        location_lng=r.get('location_lng'),
                    ))
                except Exception:
                    continue

            return ProviderPage(
                provider=self.provider_name, query=query, city=city, state=state,
                page_cursor='', results=results,
                next_page_cursor=raw.get('next_page_cursor', ''),
                status=raw.get('status', 'ok'), error=raw.get('error', ''),
                request_count=1, cost_units=0, fetched_at=utc_now(),
            )

        except Exception as e:
            return ProviderPage(
                provider=self.provider_name, query=query, city=city, state=state,
                page_cursor='',
                status='json_read_error',
                error=f'Failed to read JSON: {e}',
            )

    def search_places(
        self,
        query: str,
        city: str,
        state: str,
        page_cursor: str = "",
        page_size: int = 20,
    ) -> ProviderPage:
        """Search Google Maps for business listings.

        Args:
            query: Search query (e.g., "board game store Nashville TN")
            city: Target city
            state: Target state
            page_cursor: Pagination cursor (number of results loaded so far)
            page_size: Max results per page (default 20)

        Returns:
            ProviderPage with results or error status.
        """
        # Try cache first
        cache_key_page = page_cursor or '0'
        cached = _load_cache(query, city, state, cache_key_page)
        if cached and cached.ok and cached.results:
            return cached

        # Check for specific JSON file path
        json_file_env = os.getenv("BROWSER_MAPS_JSON_FILE", "")
        if json_file_env:
            return self._load_from_json_file(json_file_env, query, city, state)

        # Check cache directory for any matching file
        for cache_file in sorted(self._cache_dir.glob('*.json')):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                if (raw.get('query') == query and
                    raw.get('city', '').lower() == city.lower() and
                    raw.get('state', '').upper() == state.upper()):
                    return self._load_from_json_file(str(cache_file), query, city, state)
            except Exception:
                continue

        # Direct mode: scrape now
        if self._mode in ('direct', 'auto'):
            page = _scrape_direct(query, city, state, page_size, headless=self._headless)
            if page.ok:
                _save_cache(page)
            return page

        # No data available
        return ProviderPage(
            provider=self.provider_name,
            query=query, city=city, state=state,
            page_cursor=page_cursor,
            status='no_data_available',
            error=(
                f'No cached results found. '
                f'Run: python discovery/providers/browser_maps_scraper.py '
                f'--query "{query}" --city {city} --state {state} '
                f'--output data/browser_maps_cache/{_cache_key(query, city, state, "0")} '
                f'Or set BROWSER_MAPS_MODE=direct or BROWSER_MAPS_JSON_FILE=/path/to/output.json'
            ),
        )
