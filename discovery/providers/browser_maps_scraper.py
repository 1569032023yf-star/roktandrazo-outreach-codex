#!/usr/bin/env python3
"""
Browser-based Google Maps scraper for Roktandrazo lead discovery.
Uses Playwright to search Google Maps and extract business listings.

PREREQUISITES:
    pip install playwright
    playwright install chromium

USAGE (single query):
    python discovery/providers/browser_maps_scraper.py \
        --query "board game store Nashville TN" \
        --city Nashville --state TN \
        --max-results 20 \
        --output data/browser_maps_nashville_boardgame.json

OUTPUT: JSON file with PlaceSearchResult-compatible records.
NO API key required. Uses your existing Chrome/Chromium browser.

NOTE (2026-08-28 parser rewrite):
    Modern Google Maps renders each business as a `div[role="article"]`
    (class Nv2PK ...). The `a.hfpxzc` inside carries the clean business name
    (aria-label) AND the place detail URL. The website is NOT present in the
    search sidebar — it is read from each place DETAIL page via
    `a[data-item-id="authority"]`. The earlier parser matched the filter
    carousel + "Results" header (UI chrome) instead of real cards, which is
    why it returned junk. This rewrite targets the real card DOM.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))
from discovery.providers.provider_diagnostics import classify, ProviderFailure, ErrorCode


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_scraper_proxy():
    """Resolve an upstream HTTP proxy for the scraper.

    Google Maps must be reached through the local Astrill proxy from CN egress.
    Preference: explicit SCRAPER_PROXY (project convention, see lead_collector.py),
    then fall back to system HTTPS_PROXY/HTTP_PROXY. Returns None if unset.
    """
    for key in ("SCRAPER_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.getenv(key)
        if v:
            return v
    return None


# ── CONFIG ──────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Google Maps search URL template
GMAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}"

# How long to wait for results to load (seconds)
PAGE_LOAD_WAIT = 5
SCROLL_WAIT = 2
RESULT_CARD_WAIT = 3

# Maximum scroll attempts to load more results
MAX_SCROLLS = 10

# Category keywords used to label the primary_type of a discovered business.
CATEGORY_KEYWORDS = re.compile(
    r'\b(game|toy|toys|hobby|hobbies|card|cards|gift|gifts|book|books|'
    r'puzzle|puzzles|craft|crafts|comic|collectible|collectibles|board|'
    r'tabletop|rpg|tcg|hobby)\b', re.IGNORECASE)

# US street-type tokens used to spot an address fragment.
STREET_TYPE = (
    r'St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|'
    r'Hwy|Highway|Pkwy|Parkway|Cir|Circle|Ct|Court|Pl|Place|Way|'
    r'Ter|Terrace|Loop|Trail|Sq|Square'
)


def extract_place_data_from_card(card_element) -> dict | None:
    """Extract business info from a Google Maps result card (div[role=article]).

    Modern Google Maps result cards expose the business name and the place
    detail URL on an anchor:
        <a class="hfpxzc" aria-label="Business Name"
           href="https://www.google.com/maps/place/...">
    The card's inner text has the shape:
        Name | Name | 4.5 | Game store · · 40 Catherwood Rd | Closed · Opens 10 AM · (607) 319-4520
    The website is NOT in the sidebar card — it is read from the place DETAIL
    page (see scrape_google_maps Phase 2). Fail-soft: returns None only if the
    business name cannot be determined.
    """
    try:
        # Primary anchor carries both clean name and the place URL.
        link = card_element.query_selector('a.hfpxzc') or \
            card_element.query_selector('a[href*="maps/place"]')
        if not link:
            return None

        business_name = (link.get_attribute('aria-label') or '').strip()
        maps_url = link.get_attribute('href') or ''

        if not business_name:
            # Fallback: visible name span inside the anchor
            span = card_element.query_selector('span.xxVWCe')
            if span:
                business_name = (span.inner_text() or '').strip()

        if not business_name:
            return None

        if maps_url and not maps_url.startswith('http'):
            maps_url = f'https://www.google.com{maps_url}'

        card_text = card_element.inner_text() if hasattr(card_element, 'inner_text') else ''

        # Rating — first standalone decimal like 4.5
        rating = ''
        rm = re.search(r'(?<![\w.])([0-5](?:\.\d)?)(?![\w.])', card_text)
        if rm:
            rating = rm.group(1)

        # Phone (best-effort from card text; refined on detail page)
        phone = ''
        pm = re.search(r'(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', card_text)
        if pm:
            phone = pm.group(0)

        # Category — first '|' segment that contains a known category keyword
        category = ''
        for seg in card_text.split('|'):
            seg = seg.strip()
            if not seg or seg == business_name:
                continue
            if CATEGORY_KEYWORDS.search(seg):
                # Strip the middle-dot icon separators
                category = re.sub(r'\s*[·•]\s*', ' ', seg).strip()
                break
        if not category:
            category = 'store'

        # Address (best-effort from card text; refined on detail page).
        # NOTE: the real card inner_text uses NEWLINE separators, so we must
        # exclude newlines and skip candidates that contain category words
        # (otherwise the regex starts at the rating's decimal and spans the
        # whole card). The detail page provides the authoritative address.
        address = ''
        ams = re.findall(
            r'\b(\d{1,5}\s+[A-Za-z0-9 .\'-]*?\b(?:' + STREET_TYPE + r')\b[^\n|]*)',
            card_text, re.IGNORECASE)
        for cand in ams:
            if re.search(r'\b(game|toy|toys|gift|gifts|hobby|card|cards|store|shop|rating|review)\b', cand, re.IGNORECASE):
                continue
            address = cand.strip()
            break

        return {
            'business_name': business_name,
            'formatted_address': address,
            'phone': phone,
            'website': '',  # filled in Phase 2 (place detail page)
            'google_maps_url': maps_url,
            'rating': rating,
            'category': category,
            'raw_text': card_text[:500],
        }

    except Exception as e:
        raise ProviderFailure(ErrorCode.RESULT_PARSE_ERROR, "PARSE") from None


def _is_external_link(href: str) -> bool:
    """True if href points to a real business website (not Google internal).

    Excludes Google Maps internal links AND Google-owned "not a real site" URLs
    such as business.google.com/create (the unclaimed-listing claim URL).
    Allows sites.google.com / *.business.site (real, if basic, sites).
    """
    if not href or not href.startswith('http'):
        return False
    netloc = urlparse(href).netloc.lower().rstrip('.')
    # Maps can surface a country-specific Google host (for example google.cn)
    # as an apparent external link. Keep the existing explicitly permitted
    # hosted-site exceptions, but reject Google-owned/internal/redirect hosts.
    permitted_google_host = netloc == 'sites.google.com' or netloc == 'business.site' or netloc.endswith('.business.site')
    google_family = bool(re.fullmatch(r'(?:[a-z0-9-]+\.)*google\.[a-z.]+', netloc))
    google_internal = google_family or netloc in {'goo.gl', 'g.page'} or netloc.endswith('.googleusercontent.com') \
        or netloc.endswith('.googleapis.com') or netloc.endswith('.gstatic.com') or netloc.endswith('.googleadservices.com')
    if google_internal and not permitted_google_host:
        return False
    if 'maps/place' in href or 'google.com/maps' in href or 'google.com/search' in href:
        return False
    return '.' in netloc


def extract_detail_fields(page, maps_url: str) -> dict:
    """Open a place DETAIL page and read website / full address / phone.

    Returns dict with keys website, formatted_address, phone ('' when missing).
    Fail-soft: any error returns empty strings so the scrape never hangs.
    """
    result = {'website': '', 'formatted_address': '', 'phone': ''}
    if not maps_url:
        return result

    try:
        response = page.goto(maps_url, wait_until='domcontentloaded', timeout=15000)
        _check_source(page, response)
    except Exception as exc:
        raise classify(exc, 'DETAIL') from None

    # Give the panel a moment to render the authority (website) link.
    try:
        page.wait_for_selector('a[data-item-id="authority"]', timeout=6000)
    except Exception as exc:
        if classify(exc, 'DETAIL').code != ErrorCode.NETWORK_TIMEOUT:
            raise classify(exc, 'DETAIL') from None
    time.sleep(1.0)

    # Website — authority link preferred (clean business domain)
    try:
        wa = page.query_selector('a[data-item-id="authority"]')
        if wa:
            href = wa.get_attribute('href') or ''
            if _is_external_link(href):
                result['website'] = href.split('?')[0].rstrip('/')
    except Exception as exc:
        raise classify(exc, 'DETAIL') from None

    # Fallback: any external-looking link on the page
    if not result['website']:
        try:
            for a in page.query_selector_all('a[href]'):
                href = a.get_attribute('href') or ''
                if _is_external_link(href):
                    result['website'] = href.split('?')[0].rstrip('/')
                    break
        except Exception as exc:
            raise classify(exc, 'DETAIL') from None

    # Full page text for address / phone fallback.
    try:
        body = page.inner_text('body') if hasattr(page, 'inner_text') else page.content()
    except Exception as exc:
        raise classify(exc, 'DETAIL') from None

    if body:
        # "40 Catherwood Rd, Ithaca, NY 14850" (suite/unit + newline safe)
        am = re.search(
            r'(\d+\s+[^,\n]*?(?:' + STREET_TYPE + r')[^\n,]*[\n,]?\s*[^,\n]+,'
            r'\s*[A-Z]{2}\s*\d{5})',
            body, re.IGNORECASE)
        if am:
            result['formatted_address'] = am.group(1).strip().rstrip(',')

        if not result['phone']:
            pm = re.search(r'(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', body)
            if pm:
                result['phone'] = pm.group(0)

    # Phone via tel: link (most reliable form)
    try:
        for a in page.query_selector_all('a[href^="tel:"]'):
            href = a.get_attribute('href') or ''
            digits = re.sub(r'\D', '', href)
            if len(digits) == 10:
                result['phone'] = f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
                break
    except Exception as exc:
        raise classify(exc, 'DETAIL') from None

    return result


def extract_direct_place_data(page, maps_url: str) -> dict | None:
    """Read an already-loaded Maps place panel without entering list-result waits.

    A search URL can render a single place panel while retaining `/maps/search/`
    in the address bar.  This deliberately returns nothing unless a concrete
    merchant title and at least one identity field are present.
    """
    try:
        title = (page.query_selector('h1').inner_text() or '').strip() if page.query_selector('h1') else ''
        address_el = page.query_selector('[data-item-id="address"]')
        phone_el = page.query_selector('[data-item-id^="phone"]')
        address = (address_el.inner_text() or '').strip() if address_el else ''
        phone = (phone_el.inner_text() or '').strip() if phone_el else ''
        authority = page.query_selector('a[data-item-id="authority"]')
        href = authority.get_attribute('href') if authority else ''
        website = href.split('?')[0].rstrip('/') if _is_external_link(href or '') else ''
        if not title or not (address or phone or website):
            return None
        return {
            'business_name': title, 'formatted_address': address, 'phone': phone,
            'website': website, 'google_maps_url': maps_url, 'rating': '',
            'category': 'store', 'raw_text': title[:500],
        }
    except Exception as exc:
        raise classify(exc, 'PARSE') from None


def _check_source(page, response=None):
    status = getattr(response, 'status', None)
    if status == 429:
        raise ProviderFailure(ErrorCode.SOURCE_RATE_LIMITED, "SOURCE_CHECK")
    if status in (401, 403):
        raise ProviderFailure(ErrorCode.SOURCE_ACCESS_RESTRICTED, "SOURCE_CHECK")
    text = page.inner_text('body') if hasattr(page, 'inner_text') else page.content()
    # Explicit challenge markup or provider challenge phrase, not generic words
    # like "robot"/"verify" which may legitimately appear in merchant names.
    challenge = page.query_selector('iframe[src*="recaptcha"], form[action*="/sorry/"]')
    if challenge or 'our systems have detected unusual traffic' in text.lower():
        raise ProviderFailure(ErrorCode.SOURCE_VERIFICATION_REQUIRED, "SOURCE_CHECK")
    if status is not None and status >= 400:
        raise ProviderFailure(ErrorCode.UNKNOWN_PROVIDER_ERROR, "SOURCE_CHECK")
    return text


def _enrich(results, query, city, state, search_url):
    enriched = []
    for i, r in enumerate(results):
        result_city, result_state = city, state
        addr = r.get('formatted_address', '')
        if addr:
            match = re.search(r'\b(TN|Tennessee|NY|New York)\b', addr, re.IGNORECASE)
            if match:
                result_state = match.group(1).upper() if len(match.group(1)) == 2 else 'TN'
            match = re.match(r'^[^,]+,\s*([A-Za-z .]+),', addr)
            if match:
                result_city = match.group(1).strip()
        enriched.append({
            'provider': 'browser_maps',
            'provider_result_id': f"browser_maps_{query.replace(' ','_')}_{i}",
            'place_id': f"gmaps_{r['business_name'].lower().replace(' ','_').replace('-','_')}",
            'business_name': r['business_name'], 'formatted_address': addr,
            'city': result_city, 'state': result_state, 'country': 'US',
            'postal_code': '', 'phone': r.get('phone', ''), 'website': r.get('website', ''),
            'business_status': 'OPERATIONAL', 'primary_type': r.get('category') or 'store',
            'types': [r['category'].lower()] if r.get('category') else [],
            'source_query': query, 'source_url': r.get('google_maps_url', search_url),
            'raw_payload': {'raw_text': r.get('raw_text', ''), 'rating': r.get('rating', '')},
            'next_page_cursor': '', 'fetched_at': utc_now(),
            'location_lat': None, 'location_lng': None,
        })
    return enriched


def scrape_google_maps(query: str, city: str = '', state: str = '',
                       max_results: int = 20, headless: bool = True,
                       output_file: str | None = None, *, playwright_factory=None,
                       sleep=None) -> dict:
    """Bounded scrape with injected offline browser and allowlisted diagnostics.

    Failure results are observational only: DiscoveryService never consumes a
    non-ok page or advances its cursor. No challenge bypass or automatic retry.
    """
    results_data, errors = [], []
    browser = context = page = None
    stage = 'IMPORT'
    search_url = GMAPS_SEARCH_URL.format(query=query.replace(' ', '+'))
    sleep = sleep or time.sleep
    try:
        if playwright_factory is None:
            from playwright.sync_api import sync_playwright
            playwright_factory = sync_playwright
        with playwright_factory() as pw:
            try:
                stage = 'LAUNCH'
                launch_kwargs = dict(headless=headless, args=['--no-sandbox', '--disable-dev-shm-usage'])
                proxy = _resolve_scraper_proxy()
                if proxy:
                    launch_kwargs['proxy'] = {'server': proxy}
                browser = pw.chromium.launch(**launch_kwargs)
                stage = 'CONTEXT'
                context = browser.new_context(user_agent=USER_AGENT,
                    viewport={'width': 1280, 'height': 900}, locale='en-US',
                    timezone_id='America/Chicago')
                page = context.new_page()
                stage = 'NAVIGATION'
                response = page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                sleep(PAGE_LOAD_WAIT)
                stage = 'SOURCE_CHECK'
                text = _check_source(page, response)
                if 'No results found' not in text:
                    stage = 'PARSE'
                    direct = extract_direct_place_data(page, page.url)
                    if direct:
                        results_data.append(direct)
                    else:
                        stage = 'DOM'
                        try:
                            page.wait_for_selector('div[role="article"]', timeout=15000)
                        except Exception as exc:
                            # A timeout alone does not prove a layout change.
                            # The known Results feed with no expected cards does.
                            if page.query_selector('[role="feed"]'):
                                raise ProviderFailure(ErrorCode.DOM_LAYOUT_CHANGED, 'DOM') from None
                            raise classify(exc, 'DOM') from None
                        seen, scroll_attempts, last_count = set(), 0, 0
                        while len(results_data) < max_results and scroll_attempts <= MAX_SCROLLS:
                            stage = 'DOM'
                            cards = page.query_selector_all('div[role="article"]')
                            if not cards and not results_data:
                                raise ProviderFailure(ErrorCode.DOM_LAYOUT_CHANGED, 'DOM')
                            for card in cards:
                                if len(results_data) >= max_results:
                                    break
                                stage = 'PARSE'
                                data = extract_place_data_from_card(card)
                                if not data or not data['business_name']:
                                    raise ProviderFailure(ErrorCode.DOM_LAYOUT_CHANGED, 'PARSE')
                                key = data['business_name'].lower().strip()
                                if key not in seen:
                                    seen.add(key)
                                    results_data.append(data)
                            if len(results_data) >= max_results:
                                break
                            if len(results_data) > last_count:
                                last_count, scroll_attempts = len(results_data), 0
                            else:
                                scroll_attempts += 1
                            stage = 'SCROLL'
                            panel = page.query_selector('[role="feed"]') or page.query_selector('.m6QErb.DxyBCb.kA9KIf.dS8AEf')
                            if panel:
                                panel.evaluate('el => el.scrollTop = el.scrollHeight')
                            sleep(SCROLL_WAIT)
                        for result in results_data:
                            url = result.get('google_maps_url', '')
                            if url:
                                stage = 'DETAIL'
                                details = extract_detail_fields(page, url)
                                _check_source(page)
                                for field in ('website', 'formatted_address', 'phone'):
                                    if details.get(field):
                                        result[field] = details[field]
            finally:
                # Attempt every close even if an earlier close fails. Keep the
                # primary error if one exists; never log exception contents.
                for resource in (page, context, browser):
                    if resource is not None:
                        try:
                            resource.close()
                        except Exception as exc:
                            errors.append(str(classify(exc, 'CLEANUP')))
    except Exception as exc:
        errors.insert(0, str(classify(exc, stage)))
    try:
        enriched = _enrich(results_data, query, city, state, search_url)
    except Exception:
        errors.insert(0, str(ProviderFailure(ErrorCode.RESULT_PARSE_ERROR, 'PARSE')))
        enriched = []
    output = {
        'provider': 'browser_maps', 'query': query, 'city': city, 'state': state,
        'page_cursor': '', 'next_page_cursor': str(len(enriched)) if not errors and enriched else '',
        'status': ('partial' if enriched else 'scrape_error') if errors else 'ok',
        'error': errors[0] if errors else '', 'results': enriched,
        'request_count': 1, 'cost_units': 0, 'errors': errors, 'collected_at': utc_now(),
    }
    if output_file:
        try:
            out_path = Path(output_file)
            if not out_path.is_absolute():
                out_path = PROJECT_DIR / output_file
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open('w', encoding='utf-8') as handle:
                json.dump(output, handle, indent=2, ensure_ascii=False)
        except Exception as exc:
            output.update(status='scrape_error', error=str(classify(exc, 'CACHE_WRITE')), next_page_cursor='')
    return output


def main():
    parser = argparse.ArgumentParser(description='Browser-based Google Maps scraper')
    parser.add_argument('--query', required=True, help='Search query (e.g. "board game store Nashville TN")')
    parser.add_argument('--city', required=True, help='Target city')
    parser.add_argument('--state', required=True, help='Target state (2-letter code)')
    parser.add_argument('--max-results', type=int, default=20, help='Maximum results (default 20)')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window (for debugging)')
    args = parser.parse_args()

    result = scrape_google_maps(
        query=args.query,
        city=args.city,
        state=args.state,
        max_results=args.max_results,
        headless=not args.no_headless,
        output_file=args.output,
    )

    # Summary
    n = len(result.get('results', []))
    with_websites = sum(1 for r in result.get('results', []) if r.get('website'))
    with_phones = sum(1 for r in result.get('results', []) if r.get('phone'))
    with_address = sum(1 for r in result.get('results', []) if r.get('formatted_address'))

    print(f"\n{'='*60}")
    print(f"SCRAPE COMPLETE")
    print(f"  Total results:      {n}")
    print(f"  With website:       {with_websites}")
    print(f"  With phone:         {with_phones}")
    print(f"  With address:       {with_address}")
    print(f"{'='*60}")

    return result


if __name__ == '__main__':
    main()
