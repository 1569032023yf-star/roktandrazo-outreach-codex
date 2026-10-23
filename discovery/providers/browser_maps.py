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
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from discovery.models import PlaceSearchResult, ProviderPage, utc_now
from discovery.providers.base import SearchProvider
from discovery.providers.provider_diagnostics import classify, safe_error, ProviderFailure, ErrorCode


CACHE_DIR = Path(os.getenv("BROWSER_MAPS_CACHE_DIR", str(PROJECT_DIR / "data" / "browser_maps_cache")))
_RESULT_TEXT_FIELDS = {
    "provider", "provider_result_id", "place_id", "business_name", "formatted_address",
    "city", "state", "country", "postal_code", "phone", "website", "business_status",
    "primary_type", "source_query", "source_url", "next_page_cursor", "fetched_at",
}


def _sanitize_provider_text(value: Any) -> str:
    """Remove display-only control/private-use glyphs from provider fields."""
    value = str(value or "")
    cleaned = "".join(
        " " if ord(char) < 32 or ord(char) == 127 or unicodedata.category(char) == "Co" else char
        for char in value
    )
    return " ".join(cleaned.split())


def _cache_key(query: str, city: str, state: str, page: str) -> str:
    """Generate a cache filename from query parameters."""
    parts = (_sanitize_provider_text(value) for value in (query, city, state, page))
    safe = "_".join(parts).lower()
    safe = re.sub(r'[<>:"/\\|?*]', '_', safe)
    safe = re.sub(r'\s+', '_', safe)
    safe = re.sub(r'_+', '_', safe).strip('._') or 'empty'
    # Truncate for filesystem safety
    if len(safe) > 180:
        import hashlib
        safe = hashlib.sha256(safe.encode()).hexdigest()[:32]
    return safe + '.json'


def _page_from_raw(raw, query, city, state, page='', *, cache=False):
    stage = 'CACHE_READ' if cache else 'PARSE'
    code = ErrorCode.CACHE_READ_ERROR if cache else ErrorCode.RESULT_PARSE_ERROR
    def invalid():
        raise ProviderFailure(code, stage)
    if not isinstance(raw, dict) or not isinstance(raw.get('results'), list):
        invalid()
    if not isinstance(raw.get('status', 'ok'), str) or not isinstance(raw.get('next_page_cursor', ''), str):
        invalid()
    for numeric in ('request_count', 'cost_units'):
        if not isinstance(raw.get(numeric, 1 if numeric == 'request_count' else 0), int) or isinstance(raw.get(numeric), bool) or raw.get(numeric, 0) < 0:
            invalid()
    # Conflicting failure evidence cannot become successful cached data.
    if raw.get('status', 'ok') == 'ok' and (raw.get('error') or raw.get('errors')):
        invalid()
    results = []
    for row in raw['results']:
        if not isinstance(row, dict) or not isinstance(row.get('business_name'), str) or not row['business_name'].strip():
            invalid()
        if any(key in row and not isinstance(row[key], str) for key in _RESULT_TEXT_FIELDS):
            invalid()
        if not isinstance(row.get('types', []), list) or any(not isinstance(x, str) for x in row.get('types', [])) or not isinstance(row.get('raw_payload', {}), dict):
            invalid()
        for key in ('location_lat', 'location_lng'):
            if row.get(key) is not None and (not isinstance(row[key], (int, float)) or isinstance(row[key], bool)):
                invalid()
        values = {key: (_sanitize_provider_text(value) if key in _RESULT_TEXT_FIELDS else value)
                  for key, value in row.items() if key in PlaceSearchResult.__dataclass_fields__}
        for key, default in {'provider': 'browser_maps', 'provider_result_id': '', 'place_id': '',
                             'formatted_address': '', 'city': city, 'state': state}.items():
            values.setdefault(key, default)
        results.append(PlaceSearchResult(**values))
    status = raw.get('status', 'ok')
    if status not in {'ok', 'partial', 'scrape_error'}:
        status = 'scrape_error'
    return ProviderPage(provider='browser_maps', query=query, city=city, state=state,
        page_cursor=page, results=results, next_page_cursor=raw.get('next_page_cursor', '') if status == 'ok' else '',
        status=status, error=safe_error(raw.get('error', ''), stage) if status != 'ok' else '',
        request_count=raw.get('request_count', 1), cost_units=raw.get('cost_units', 0),
        fetched_at=utc_now())


def _load_cache(query, city, state, page, cache_dir=None):
    cache_path = (Path(cache_dir) if cache_dir is not None else CACHE_DIR) / _cache_key(query, city, state, page)
    try:
        if not cache_path.exists():
            return None
        with cache_path.open('r', encoding='utf-8') as handle:
            return _page_from_raw(json.load(handle), query, city, state, page, cache=True)
    except Exception as exc:
        return ProviderPage(provider='browser_maps', query=query, city=city, state=state,
            page_cursor=page, status='cache_read_error', error=str(classify(exc, 'CACHE_READ')))


def _save_cache(page: ProviderPage, cache_dir=None) -> None:
    """Save scraper results to cache JSON."""
    cache_root = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_path = cache_root / _cache_key(page.query, page.city, page.state, page.page_cursor)

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


def _scrape_direct(query, city, state, max_results, headless=True):
    stage = 'IMPORT'
    try:
        from discovery.providers.browser_maps_scraper import scrape_google_maps
        stage = 'UNKNOWN'
        raw = scrape_google_maps(query=query, city=city, state=state,
                                 max_results=max_results, headless=headless)
        return _page_from_raw(raw, query, city, state)
    except Exception as exc:
        return ProviderPage(provider='browser_maps', query=query, city=city, state=state,
            page_cursor='', status='scrape_error', error=str(classify(exc, stage)), request_count=1)


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

    def _load_from_json_file(self, json_path, query, city, state, page_cursor=''):
        path = Path(json_path)
        if not path.is_absolute():
            path = PROJECT_DIR / path
        try:
            with path.open('r', encoding='utf-8') as handle:
                return _page_from_raw(json.load(handle), query, city, state, page_cursor, cache=True)
        except Exception as exc:
            return ProviderPage(provider=self.provider_name, query=query, city=city, state=state,
                page_cursor=page_cursor, status='cache_read_error', error=str(classify(exc, 'CACHE_READ')))

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
        cached = _load_cache(query, city, state, cache_key_page, self._cache_dir)
        if cached is not None:
            return cached

        # Check for specific JSON file path
        json_file_env = os.getenv("BROWSER_MAPS_JSON_FILE", "")
        if json_file_env:
            return self._load_from_json_file(json_file_env, query, city, state, page_cursor)

        # Check cache directory for any matching file
        for cache_file in sorted(self._cache_dir.glob('*.json')):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                if (raw.get('query') == query and
                    raw.get('city', '').lower() == city.lower() and
                    raw.get('state', '').upper() == state.upper() and
                    str(raw.get('page_cursor', '') or '0') == cache_key_page):
                    return self._load_from_json_file(str(cache_file), query, city, state, page_cursor)
            except Exception:
                continue

        # Direct mode: scrape now
        if self._mode in ('direct', 'auto'):
            page = _scrape_direct(query, city, state, page_size, headless=self._headless)
            page.page_cursor = page_cursor
            if page.ok:
                try:
                    # Exact cursor key; use instance-isolated cache, never module global.
                    page.page_cursor = cache_key_page
                    _save_cache(page, self._cache_dir)
                except Exception as exc:
                    page.status = 'cache_write_error'
                    page.error = str(classify(exc, 'CACHE_WRITE'))
                    page.next_page_cursor = ''
                finally:
                    page.page_cursor = page_cursor
            return page

        # No data available
        return ProviderPage(
            provider=self.provider_name,
            query=query, city=city, state=state,
            page_cursor=page_cursor,
            status='no_data_available',
            error=(
                'CACHE_READ_ERROR:CACHE_READ'
            ),
        )
