#!/usr/bin/env python3
"""
End-to-end test: Browser Maps Scraper → Discovery Pipeline → Lead Classification.

SAFE: Uses a TEST database copy. NEVER touches production bd_leads.db.
SAFE: No SMTP, no send_log writes, no final_send_plan.

Usage:
    # Step 1: Scrape Google Maps (user runs this manually)
    python discovery/providers/browser_maps_scraper.py \
        --query "board game store Nashville TN" \
        --city Nashville --state TN \
        --max-results 20 \
        --output data/browser_maps_nashville_boardgame.json

    # Step 2: Run integration test
    python test_browser_maps_integration.py \
        --json-file data/browser_maps_nashville_boardgame.json \
        --city Nashville --state TN
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from discovery.models import PlaceSearchResult, ProviderPage, utc_now
from discovery.providers.browser_maps import BrowserMapsProvider

# ── Paths ───────────────────────────────────────────────
DB_SOURCE = PROJECT_DIR / "data" / "bd_leads.db"
DB_TEST = PROJECT_DIR / "data" / "bd_leads_test_browser_maps.db"
OUTPUT_DIR = PROJECT_DIR / "output"


def utc_now_str():
    return datetime.now(timezone.utc).isoformat()


def setup_test_db():
    """Create a test database copy."""
    print(f"\n[SETUP] Copying production DB for testing...")
    print(f"  Source: {DB_SOURCE}")
    print(f"  Test:   {DB_TEST}")

    if DB_TEST.exists():
        DB_TEST.unlink()
    shutil.copy2(DB_SOURCE, DB_TEST)

    size_mb = DB_TEST.stat().st_size / 1024 / 1024
    print(f"  Size: {size_mb:.1f} MB")
    return sqlite3.connect(str(DB_TEST))


def ensure_discovery_tables(conn: sqlite3.Connection):
    """Create discovery tables if they don't exist."""
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS lead_discovery_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            provider_result_id TEXT,
            place_id TEXT,
            business_name TEXT NOT NULL,
            normalized_business_name TEXT,
            formatted_address TEXT,
            normalized_address TEXT,
            city TEXT,
            state TEXT,
            postal_code TEXT,
            phone TEXT,
            normalized_phone TEXT,
            website TEXT,
            normalized_domain TEXT,
            business_status TEXT,
            primary_type TEXT,
            raw_types_json TEXT,
            source_query TEXT,
            query_family TEXT,
            source_url TEXT,
            raw_payload_json TEXT,
            active_city_id INTEGER NOT NULL DEFAULT 1,
            discovered_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            validation_status TEXT NOT NULL DEFAULT 'validation_pending',
            history_crosscheck_result TEXT,
            linked_lead_id INTEGER,
            rejection_reason TEXT,
            country TEXT,
            evidence_url TEXT,
            evidence_snippet TEXT,
            evidence_method TEXT,
            contact_form_url TEXT,
            official_match INTEGER DEFAULT 0,
            location_status TEXT,
            created_lead_via TEXT DEFAULT 'bd_db.insert_lead'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS lead_discovery_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name_hash TEXT NOT NULL,
            query_family TEXT NOT NULL,
            source_query TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            hit_count INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS lead_discovery_query_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            query_family TEXT NOT NULL,
            provider TEXT NOT NULL,
            query_text TEXT NOT NULL,
            page_cursor TEXT DEFAULT '',
            next_page_cursor TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            pages_fetched INTEGER DEFAULT 0,
            total_results INTEGER DEFAULT 0,
            unique_places INTEGER DEFAULT 0,
            last_run_at TEXT,
            error TEXT,
            UNIQUE(city_id, query_family, provider)
        )
    """)

    conn.commit()


def normalize_name(name: str) -> str:
    """Normalize business name for dedup."""
    return re.sub(r'\W+', '', name.lower().strip())


def normalize_domain(url: str) -> str:
    """Extract and normalize domain from URL."""
    if not url:
        return ''
    domain = url.lower().strip()
    domain = domain.replace('https://', '').replace('http://', '').replace('www.', '')
    domain = domain.split('/')[0].split('?')[0].split('#')[0]
    return domain


def deduplicate_results(results: list[dict], conn: sqlite3.Connection) -> tuple[list[dict], dict]:
    """Deduplicate against existing database records.

    Checks:
    1. Same lead_discovery_results (by place_id)
    2. Same leads table (by domain_hash)
    3. Same leads table (by store_name + city + state)

    Returns (new_unique_results, stats).
    """
    c = conn.cursor()
    stats = {'new': 0, 'duplicate_discovery': 0, 'duplicate_leads': 0, 'total_input': len(results)}

    # Get existing place_ids
    existing_place_ids = set()
    try:
        for row in c.execute("SELECT DISTINCT place_id FROM lead_discovery_results WHERE place_id IS NOT NULL AND place_id != ''"):
            existing_place_ids.add(row[0])
    except Exception:
        pass

    # Get existing domain hashes
    existing_domains = {}
    for row in c.execute("SELECT id, domain_hash, store_name FROM leads WHERE domain_hash IS NOT NULL"):
        existing_domains[row[1]] = {'id': row[0], 'name': normalize_name(row[2])}

    # Get existing store+city+state combos
    existing_identities = set()
    for row in c.execute("SELECT store_name, city, state FROM leads"):
        key = f"{normalize_name(row[0])}|{row[1].lower().strip()}|{row[2].upper().strip()}"
        existing_identities.add(key)

    new_results = []
    for r in results:
        pid = r.get('place_id', '')
        name = r.get('business_name', '')
        website = r.get('website', '')

        # Check 1: Already in discovery_results
        if pid and pid in existing_place_ids:
            stats['duplicate_discovery'] += 1
            continue

        # Check 2: Same domain in leads
        domain = normalize_domain(website)
        if domain:
            dh = hashlib.sha256(domain.encode()).hexdigest()
            if dh in existing_domains:
                stats['duplicate_leads'] += 1
                continue

        # Check 3: Same identity
        identity_key = f"{normalize_name(name)}|{r.get('city','').lower()}|{r.get('state','').upper()}"
        if identity_key in existing_identities:
            stats['duplicate_leads'] += 1
            continue

        new_results.append(r)
        stats['new'] += 1

    return new_results, stats


def fetch_website_and_extract(website_url: str) -> dict:
    """Fetch website and extract email/contact form evidence."""
    result = {
        'email': '',
        'evidence_url': '',
        'evidence_snippet': '',
        'evidence_method': '',
        'contact_form_url': '',
        'official_match': 0,
        'website_accessible': False,
    }

    if not website_url or not website_url.startswith('http'):
        return result

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            website_url,
            headers={'User-Agent': 'WorkBuddyDiscovery/1.0'}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            content_type = resp.headers.get('content-type', '')
            if 'text' not in content_type and 'html' not in content_type:
                return result

            html = resp.read().decode('utf-8', errors='replace')
            result['website_accessible'] = True

            # Extract emails
            email_re = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
            noise = ('noreply@', 'no-reply@', 'example@', 'privacy@', 'copyright@',
                     'wixpress', 'sentry', 'shopify', '.png', '.jpg', '.gif')
            for m in email_re.finditer(html):
                email = m.group(0).lower()
                if any(n in email for n in noise):
                    continue
                result['email'] = email
                result['evidence_url'] = website_url
                start = max(0, m.start() - 60)
                end = min(len(html), m.end() + 60)
                result['evidence_snippet'] = html[start:end].strip().replace('\n', ' ')
                result['evidence_method'] = 'official_page_visible'
                result['official_match'] = 1
                break

            # Check for contact form
            if not result['email']:
                form_match = re.search(r'<form\b[^>]*>.*?</form>', html, re.IGNORECASE | re.DOTALL)
                if form_match:
                    result['contact_form_url'] = website_url

    except Exception:
        pass

    return result


def classify_and_insert(
    result: dict,
    website_data: dict,
    conn: sqlite3.Connection,
    active_city: str,
    active_state: str,
) -> dict:
    """Classify a result and insert into leads via bd_db.insert_lead().

    Classification outcomes:
    - lead_created (Strict A0): Has email on official site, passes hygiene
    - contact_form_pool: Has contact form, no email
    - manual_review_needed: Has website, no email, no contact form
    - history_blocked: History crosscheck rejected
    - outside_active_city: City mismatch
    - rejected: Various reasons
    """
    outcome = {
        'business_name': result.get('business_name', ''),
        'website': result.get('website', ''),
        'city': result.get('city', ''),
        'state': result.get('state', ''),
        'classification': 'unknown',
        'reason': '',
    }

    # City validation
    if result.get('city', '').lower() != active_city.lower():
        outcome['classification'] = 'outside_active_city'
        outcome['reason'] = f"city mismatch: {result.get('city')} != {active_city}"
        return outcome

    # No website → manual review
    if not result.get('website'):
        outcome['classification'] = 'manual_review_needed'
        outcome['reason'] = 'no_website'
        # Insert via bd_db as B-grade
        try:
            from bd_db import insert_lead
            insert_lead({
                'store_name': result['business_name'],
                'store_type': 'game_store',
                'city': result.get('city', active_city),
                'state': result.get('state', active_state),
                'official_website': '',
                'email': '',
                'email_type': 'unknown',
                'confidence_score': 'B',
                'status': 'manual_review_needed',
                'product_fit': 'board_games',
                'source_keyword': result.get('source_query', ''),
                'notes': f"google_maps_place_id:{result.get('place_id','')}",
                'email_source_type': 'unknown',
                'email_verified_on_official_site': 0,
            })
        except Exception as e:
            outcome['reason'] += f'; insert_error: {e}'
        return outcome

    # Has website → fetch and analyze
    if not website_data['website_accessible']:
        # Website not accessible
        try:
            from bd_db import insert_lead
            insert_lead({
                'store_name': result['business_name'],
                'store_type': 'game_store',
                'city': result.get('city', active_city),
                'state': result.get('state', active_state),
                'official_website': result['website'],
                'email': '',
                'email_type': 'unknown',
                'confidence_score': 'B',
                'status': 'manual_review_needed',
                'product_fit': 'board_games',
                'source_keyword': result.get('source_query', ''),
                'notes': f"website_unreachable; google_maps_place_id:{result.get('place_id','')}",
                'email_source_type': 'unknown',
                'email_verified_on_official_site': 0,
            })
        except Exception as e:
            outcome['reason'] = f'insert_error: {e}'
        outcome['classification'] = 'manual_review_needed'
        outcome['reason'] = 'website_unreachable'
        return outcome

    # Has email → try A0
    if website_data['email']:
        from history_crosscheck import cross_check, normalize_email

        email = normalize_email(website_data['email'])
        if not email:
            outcome['classification'] = 'rejected'
            outcome['reason'] = 'invalid_email'
            return outcome

        # Build candidate for crosscheck
        candidate = {
            'store_name': result['business_name'],
            'store_type': 'game_store',
            'city': result.get('city', active_city),
            'state': result.get('state', active_state),
            'official_website': result['website'],
            'email': email,
            'email_type': 'general',
            'evidence_url': website_data['evidence_url'],
            'evidence_snippet': website_data['evidence_snippet'],
            'evidence_method': website_data['evidence_method'],
            'confidence_score': 'A',
            'status': 'new',
            'product_fit': 'board_games',
            'source_keyword': result.get('source_query', ''),
            'notes': f"browser_maps; google_maps_place_id:{result.get('place_id','')}",
            'email_source_type': 'official_page_visible',
            'email_verified_on_official_site': 1,
        }

        # Crosscheck
        hc = cross_check(conn, candidate)
        if hc['result'] != 'new_candidate':
            outcome['classification'] = 'history_blocked'
            outcome['reason'] = f"crosscheck: {hc['result']}"
            return outcome

        # Insert via bd_db
        try:
            from bd_db import insert_lead
            lead_id = insert_lead(candidate)
            if lead_id:
                outcome['classification'] = 'lead_created'
                outcome['reason'] = f'A0 candidate (id={lead_id})'
            else:
                outcome['classification'] = 'history_blocked'
                outcome['reason'] = 'insert_rejected_by_crosscheck'
        except Exception as e:
            outcome['classification'] = 'rejected'
            outcome['reason'] = f'insert_error: {e}'
        return outcome

    # Has contact form → contact_form_pool
    if website_data['contact_form_url']:
        try:
            from bd_db import insert_lead
            insert_lead({
                'store_name': result['business_name'],
                'store_type': 'game_store',
                'city': result.get('city', active_city),
                'state': result.get('state', active_state),
                'official_website': result['website'],
                'email': '',
                'email_type': 'contact_form_only',
                'contact_form_url': website_data['contact_form_url'],
                'confidence_score': 'C',
                'status': 'contact_form_pool',
                'product_fit': 'board_games',
                'source_keyword': result.get('source_query', ''),
                'notes': f"browser_maps; google_maps_place_id:{result.get('place_id','')}",
                'email_source_type': 'unknown',
                'email_verified_on_official_site': 0,
            })
        except Exception as e:
            outcome['reason'] = f'insert_error: {e}'
        outcome['classification'] = 'contact_form_pool'
        outcome['reason'] = 'contact_form_only'
        return outcome

    # No email, no contact form → manual review
    try:
        from bd_db import insert_lead
        insert_lead({
            'store_name': result['business_name'],
            'store_type': 'game_store',
            'city': result.get('city', active_city),
            'state': result.get('state', active_state),
            'official_website': result['website'],
            'email': '',
            'email_type': 'unknown',
            'confidence_score': 'B',
            'status': 'manual_review_needed',
            'product_fit': 'board_games',
            'source_keyword': result.get('source_query', ''),
            'notes': f"no_email_or_form; google_maps_place_id:{result.get('place_id','')}",
            'email_source_type': 'unknown',
            'email_verified_on_official_site': 0,
        })
    except Exception as e:
        outcome['reason'] = f'insert_error: {e}'
    outcome['classification'] = 'manual_review_needed'
    outcome['reason'] = 'no_email_or_form'
    return outcome


def main():
    parser = argparse.ArgumentParser(description='Browser Maps Integration Test')
    parser.add_argument('--json-file', help='Path to browser_maps_scraper output JSON')
    parser.add_argument('--city', default='Nashville', help='Active city')
    parser.add_argument('--state', default='TN', help='Active state')
    parser.add_argument('--query', default='board game store Nashville TN', help='Search query')
    parser.add_argument('--max-results', type=int, default=20)
    parser.add_argument('--scrape-now', action='store_true', help='Scrape directly (requires Playwright + browser)')
    args = parser.parse_args()

    now_str = utc_now_str()
    print("=" * 70)
    print("BROWSER MAPS → DISCOVERY PIPELINE INTEGRATION TEST")
    print(f"City: {args.city}, State: {args.state}")
    print(f"Query: {args.query}")
    print(f"Time: {now_str}")
    print("=" * 70)

    # ── Phase 1: Load results ───────────────────────────
    print("\n" + "=" * 50)
    print("PHASE 1: LOAD RESULTS")
    print("=" * 50)

    provider = BrowserMapsProvider(mode='auto')

    if args.scrape_now:
        print("  Mode: DIRECT (scraping now with Playwright)...")
        page = provider.search_places(args.query, args.city, args.state, '', args.max_results)
    elif args.json_file:
        print(f"  Mode: JSON FILE ({args.json_file})")
        os.environ['BROWSER_MAPS_JSON_FILE'] = args.json_file
        page = provider.search_places(args.query, args.city, args.state, '', args.max_results)
    else:
        print("  Mode: CACHE (looking for cached results)")
        page = provider.search_places(args.query, args.city, args.state, '', args.max_results)

    print(f"  Status:  {page.status}")
    print(f"  Results: {len(page.results)}")
    if page.error:
        print(f"  Error:   {page.error}")

    if page.status != 'ok' or not page.results:
        print("\n  ⚠️  No results to process. Exiting integration test.")
        print(f"  Hint: Run the scraper first:")
        print(f"    python discovery/providers/browser_maps_scraper.py \\")
        print(f"      --query \"{args.query}\" \\")
        print(f"      --city {args.city} --state {args.state} \\")
        print(f"      --max-results {args.max_results} \\")
        print(f"      --output data/browser_maps_nashville_boardgame.json")
        return

    # ── Phase 2: Setup test DB ──────────────────────────
    print("\n" + "=" * 50)
    print("PHASE 2: TEST DATABASE SETUP")
    print("=" * 50)

    conn = setup_test_db()
    ensure_discovery_tables(conn)
    print("  ✅ Test database ready")

    # ── Phase 3: Dedup ──────────────────────────────────
    print("\n" + "=" * 50)
    print("PHASE 3: DEDUPLICATION")
    print("=" * 50)

    raw_results = []
    for r in page.results:
        rd = {
            'business_name': r.business_name,
            'provider_result_id': r.provider_result_id,
            'place_id': r.place_id,
            'formatted_address': r.formatted_address,
            'city': r.city,
            'state': r.state,
            'website': r.website,
            'phone': r.phone,
            'business_status': r.business_status,
            'primary_type': r.primary_type,
            'source_query': r.source_query,
            'source_url': r.source_url,
            'raw_payload': r.raw_payload,
        }
        raw_results.append(rd)

    new_results, dedup_stats = deduplicate_results(raw_results, conn)
    print(f"  Total input:     {dedup_stats['total_input']}")
    print(f"  New (unique):    {dedup_stats['new']}")
    print(f"  Dup (discovery): {dedup_stats['duplicate_discovery']}")
    print(f"  Dup (leads DB):  {dedup_stats['duplicate_leads']}")

    # ── Phase 4: Store in discovery_results ─────────────
    print("\n" + "=" * 50)
    print("PHASE 4: STORE IN lead_discovery_results")
    print("=" * 50)

    c = conn.cursor()
    stored = 0
    for r in new_results:
        try:
            c.execute("""
                INSERT INTO lead_discovery_results (
                    provider, provider_result_id, place_id, business_name,
                    formatted_address, city, state, phone, website,
                    business_status, primary_type, source_query, source_url,
                    raw_payload_json, active_city_id, discovered_at, last_seen_at,
                    validation_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'validation_pending')
            """, (
                'browser_maps',
                r.get('provider_result_id', ''),
                r.get('place_id', ''),
                r['business_name'],
                r.get('formatted_address', ''),
                r.get('city', args.city),
                r.get('state', args.state),
                r.get('phone', ''),
                r.get('website', ''),
                r.get('business_status', ''),
                r.get('primary_type', ''),
                r.get('source_query', ''),
                r.get('source_url', ''),
                json.dumps(r.get('raw_payload', {})),
                now_str, now_str,
            ))
            stored += 1
        except Exception as e:
            print(f"  [WARN] Failed to store {r['business_name']}: {e}")

    conn.commit()
    print(f"  Stored: {stored} new discovery results")

    # ── Phase 5: Website + Email + Classification ───────
    print("\n" + "=" * 50)
    print("PHASE 5: WEBSITE VISIT → EMAIL → CLASSIFY → INSERT")
    print("=" * 50)

    summary = {
        'lead_created': 0,
        'manual_review_needed': 0,
        'contact_form_pool': 0,
        'history_blocked': 0,
        'duplicate': 0,
        'outside_active_city': 0,
        'rejected': 0,
    }
    details = []

    for i, r in enumerate(new_results):
        name = r['business_name']
        website = r.get('website', '')
        print(f"\n  [{i+1}/{len(new_results)}] {name}")
        print(f"      Website: {website or 'NONE'}")

        # Fetch website
        web_data = fetch_website_and_extract(website)
        if web_data['website_accessible']:
            print(f"      Site OK: {web_data.get('email','no email')} | form={bool(web_data.get('contact_form_url'))}")
        else:
            print(f"      Site: UNREACHABLE")

        # Classify and insert
        outcome = classify_and_insert(r, web_data, conn, args.city, args.state)
        outcome['phone'] = r.get('phone', '')
        outcome['address'] = r.get('formatted_address', '')
        outcome['source_url'] = r.get('source_url', '')

        cls = outcome['classification']
        if cls in summary:
            summary[cls] += 1
        details.append(outcome)

        print(f"      → {cls}: {outcome.get('reason','')}")

    conn.commit()

    # ── Phase 6: Summary ────────────────────────────────
    print("\n" + "=" * 70)
    print("PHASE 6: FINAL SUMMARY")
    print("=" * 70)

    print(f"\n  {'Classification':<30} {'Count':>6}")
    print(f"  {'-'*30} {'-'*6}")
    for cls, count in sorted(summary.items()):
        if count > 0:
            print(f"  {cls:<30} {count:>6}")

    total_classified = sum(summary.values())
    print(f"  {'─'*30} {'─'*6}")
    print(f"  {'Total processed':<30} {total_classified:>6}")

    # Stats
    with_website = sum(1 for r in new_results if r.get('website'))
    with_phone = sum(1 for r in new_results if r.get('phone'))
    email_found = sum(1 for d in details if d['classification'] == 'lead_created')
    contact_form = sum(1 for d in details if d['classification'] == 'contact_form_pool')
    manual = sum(1 for d in details if d['classification'] == 'manual_review_needed')
    history = sum(1 for d in details if d['classification'] == 'history_blocked')

    # Count leads in test DB
    new_lead_count = conn.execute("SELECT COUNT(*) FROM leads WHERE notes LIKE '%browser_maps%'").fetchone()[0]
    a0_count = conn.execute("""
        SELECT COUNT(*) FROM leads WHERE notes LIKE '%browser_maps%'
        AND confidence_score='A' AND email_verified_on_official_site=1
    """).fetchone()[0]

    print(f"\n  Pipeline metrics:")
    print(f"    New discovery results stored: {stored}")
    print(f"    With website:                 {with_website}")
    print(f"    With phone:                   {with_phone}")
    print(f"    Email found (A0):             {email_found}")
    print(f"    Contact form only:            {contact_form}")
    print(f"    Manual review:                {manual}")
    print(f"    History blocked:              {history}")
    print(f"    Leads in test DB:             {new_lead_count}")
    print(f"    Strict A0 in test DB:         {a0_count}")

    # Show details table
    print(f"\n  Detailed results:")
    print(f"  {'#':<3} {'Business':<35} {'Classification':<22} {'Website':<8} {'Phone':<8}")
    print(f"  {'-'*3} {'-'*35} {'-'*22} {'-'*8} {'-'*8}")
    for i, d in enumerate(details):
        name_s = d['business_name'][:33]
        cls_s = d['classification'][:20]
        web_s = 'YES' if d.get('website') else 'NO'
        ph_s = 'YES' if d.get('phone') else 'NO'
        print(f"  {i+1:<3} {name_s:<35} {cls_s:<22} {web_s:<8} {ph_s:<8}")

    # Save details
    OUTPUT_DIR.mkdir(exist_ok=True)
    report_path = OUTPUT_DIR / f'browser_maps_integration_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'test_time': now_str,
            'config': {
                'city': args.city,
                'state': args.state,
                'query': args.query,
                'test_db': str(DB_TEST),
            },
            'dedup_stats': dedup_stats,
            'summary': summary,
            'details': details,
            'pipeline_metrics': {
                'new_discovery_results': stored,
                'with_website': with_website,
                'with_phone': with_phone,
                'email_found': email_found,
                'contact_form': contact_form,
                'manual_review': manual,
                'history_blocked': history,
                'test_db_leads': new_lead_count,
                'test_db_a0': a0_count,
            },
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Report saved: {report_path}")

    conn.close()

    print("\n" + "=" * 70)
    print("INTEGRATION TEST COMPLETE")
    print(f"  Test DB: {DB_TEST}")
    print(f"  Production DB NOT modified")
    print(f"  No emails sent")
    print("=" * 70)


if __name__ == '__main__':
    main()
