"""Facebook contact enrichment batch runner — single browser session.

Usage:
    python fb_batch_runner.py

The script:
1. Opens a persistent headed browser for first-time Facebook login
2. Reads candidate leads from production DB (read-only)
3. For each lead: scans website for FB links, opens FB page, extracts contacts
4. Classifies: A0_redirect, B1_social_verified, C_social_contact, blocked
5. Saves checkpoint after each lead, final audit JSON at end

Browser profile: D:\BD_BROWSER_PROFILES\facebook_business_enrichment
No DB writes. No email sends.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# --- Paths ---
PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "data" / "bd_leads.db"
PROFILE_DIR = Path("D:/BD_BROWSER_PROFILES/facebook_business_enrichment")
OUTPUT_DIR = Path(__file__).resolve().parent

# --- Patterns ---
FB_RE = re.compile(
    r'href=["\']?(https?://(?:www\.)?facebook\.com/(?!login|sharer|share|dialog|plugins|'
    r'tr|ajax|help|policies|privacy|legal|settings|messages|messenger|bookmarks|profile\.php)'
    r'[A-Za-z0-9.\-_/]+(?:\?[^"\'\s<>]*)?)["\']?', re.I
)
EMAIL_RE = re.compile(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+')
PHONE_RE = re.compile(r'(?:\+1[-\s]?)?\(?\d{3}\)?[-\s.]?\d{3}[-\s.]?\d{4}')
WEBSITE_RE = re.compile(r'(?:Website|Web|Visit|Site)[:\s]*(https?://[^\s<>"\']+)', re.I)

MAX_LEADS = 12


@dataclass
class LeadResult:
    lead_id: int
    store_name: str
    website: str
    fb_found: bool = False
    fb_url: str = ""
    fb_name: str = ""
    match_score: float = 0.0
    email: str = ""
    website_from_fb: str = ""
    phone: str = ""
    classification: str = ""
    reason: str = ""
    error: str = ""
    elapsed: float = 0.0


def fetch_html(url: str, timeout: int = 12) -> str | None:
    try:
        import httpx
        r = httpx.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }, timeout=timeout, follow_redirects=True, verify=False)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def extract_fb_links(html: str) -> list[str]:
    links = []
    seen = set()
    for m in FB_RE.finditer(html):
        raw = m.group(1).rstrip('/"\'\\[]() ')
        parsed = urlparse(raw)
        path = parsed.path.rstrip('/')
        if not path or path == '/':
            continue
        clean = f"https://www.facebook.com{path}"
        if clean not in seen:
            seen.add(clean)
            links.append(clean)
    return links


def scan_website(url: str) -> list[str]:
    """Scan website homepage + /contact for Facebook links."""
    for page in [url, url.rstrip('/') + '/contact', url.rstrip('/') + '/about']:
        html = fetch_html(page)
        if html:
            links = extract_fb_links(html)
            if links:
                return links
    return []


def match_score(store: str, fb_name: str, city: str = "", state: str = "") -> float:
    st = store.lower().strip()
    fb = fb_name.lower().strip()
    st_tokens = set(st.split())
    fb_tokens = set(fb.split())
    score = 0.0
    if st_tokens and fb_tokens:
        overlap = st_tokens & fb_tokens
        score += len(overlap) / max(len(st_tokens), len(fb_tokens)) * 0.6
    if city.lower() in fb:
        score += 0.2
    if state.lower() in fb:
        score += 0.1
    if st in fb or fb in st:
        score = max(score, 0.7)
    return min(score, 1.0)


def ensure_fb_login(page) -> bool:
    """Check if logged into Facebook. Returns True if logged in."""
    try:
        page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=15000)
        page.wait_for_timeout(2000)
        login = page.query_selector('input[name="email"], #loginbutton, [data-testid="royal_login_form"]')
        return login is None
    except Exception:
        return False


def read_fb_page(page, fb_url: str) -> dict:
    """Read a Facebook page's public contact info. Reuses existing browser page."""
    result = {'name': '', 'email': '', 'website': '', 'phone': '', 'about': '', 'error': ''}
    try:
        page.goto(fb_url, wait_until='domcontentloaded', timeout=25000)
        page.wait_for_timeout(3000)

        # Check blocks
        text = page.content()[:5000].lower()
        if 'you must log in' in text:
            result['error'] = 'facebook_login_required'
            return result
        if 'confirm your identity' in text:
            result['error'] = 'facebook_captcha'
            return result

        # Page name
        try:
            h1 = page.query_selector('h1')
            if h1:
                result['name'] = h1.inner_text().strip()
        except Exception:
            pass

        # Full page text
        try:
            body = page.query_selector('body')
            if body:
                result['about'] = body.inner_text()[:4000]
        except Exception:
            pass

        full = result['about']

        # Email
        emails = EMAIL_RE.findall(full)
        if emails:
            result['email'] = emails[0]

        # Phone
        phones = PHONE_RE.findall(full)
        if phones:
            result['phone'] = phones[0]

        # Website from text
        ws = WEBSITE_RE.findall(full)
        if ws:
            result['website'] = ws[0]

        # Website from links
        if not result['website']:
            try:
                for link in page.query_selector_all('a[href*="http"]'):
                    href = (link.get_attribute('href') or '')[:200]
                    if href.startswith('http') and 'facebook.com' not in href and 'l.php' not in href:
                        result['website'] = href
                        break
            except Exception:
                pass

    except Exception as e:
        result['error'] = str(e)[:100]

    return result


def main():
    import httpx
    from playwright.sync_api import sync_playwright

    # --- Load candidates ---
    conn = sqlite3.connect(f"file:{DB_PATH.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, store_name, city, state, official_website
        FROM leads
        WHERE state IN ('TN','AR','KY')
        AND official_website IS NOT NULL AND official_website != ''
        AND (email IS NULL OR email = '' OR email_source_type IN ('guessed_email','no_contact_found','unknown')
             OR email_verified_on_official_site = 0)
        AND status NOT IN ('sent','bounced','unsubscribed','delivery_issue')
        AND email NOT IN (SELECT email FROM suppression_list WHERE email IS NOT NULL)
        AND id NOT IN (SELECT lead_id FROM bounce_log WHERE bounce_type='hard')
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status='sent')
        LIMIT ?
    """, (MAX_LEADS,)).fetchall()
    conn.close()

    leads = [dict(r) for r in rows]
    print(f"Loaded {len(leads)} candidate leads from TN/AR/KY")
    print(f"Browser profile: {PROFILE_DIR}")
    print()

    # --- Phase 1: Website scan (no browser) ---
    print("Phase 1: Scanning websites for Facebook links...")
    fb_mapping = {}
    no_fb = []
    fetch_failed = []

    for i, lead in enumerate(leads):
        name = lead['store_name'][:30]
        url = lead['official_website']
        links = scan_website(url)
        if links:
            fb_mapping[lead['id']] = (lead, links[0])
            print(f"  [{i+1}/{len(leads)}] {name} → FB: {links[0]}")
        else:
            no_fb.append(lead)
            print(f"  [{i+1}/{len(leads)}] {name} → No FB link")

    print(f"\nFB links found: {len(fb_mapping)}/{len(leads)}")
    print(f"No FB link: {len(no_fb)}")

    if not fb_mapping:
        print("No leads with Facebook links. Nothing to enrich.")
        return

    # --- Phase 2: Facebook enrichment (browser) ---
    print(f"\nPhase 2: Opening Facebook pages ({len(fb_mapping)} leads)...")
    print("A browser window will open. Please log into Facebook if prompted.")
    print("Profile will be saved for future runs.")
    print()

    results: list[LeadResult] = []

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
            viewport={'width': 1280, 'height': 900},
            locale='en-US',
        )

        page = browser.new_page()

        # One-time login check with auto-wait (avoids input() being eaten by PowerShell)
        if not ensure_fb_login(page):
            print("\n⚠ Facebook login required!")
            print("  A browser window is open. Please log into Facebook.")
            print("  Waiting up to 5 minutes for login (checking every 60s)...\n")

            logged_in = False
            for wait_sec in range(60, 360, 60):
                time.sleep(60)
                print(f"  [{wait_sec}s] Checking login status...", end=" ")
                if ensure_fb_login(page):
                    print("✓ Logged in!")
                    logged_in = True
                    break
                print("still waiting...")

            if not logged_in:
                print("\n  Still not logged in after 5 minutes. Cannot proceed.")
                print("  Run the script again after logging into Facebook in this profile.")
                browser.close()
                return
            print()

        # Process each lead
        for i, (lid, (lead, fb_url)) in enumerate(fb_mapping.items()):
            started = time.perf_counter()
            r = LeadResult(
                lead_id=lid,
                store_name=lead['store_name'],
                website=lead['official_website'],
                fb_found=True,
                fb_url=fb_url,
            )
            name = lead['store_name'][:30]

            print(f"  [{i+1}/{len(fb_mapping)}] {name} → {fb_url}")

            fb_data = read_fb_page(page, fb_url)
            r.elapsed = time.perf_counter() - started

            if fb_data.get('error'):
                r.error = fb_data['error']
                r.classification = fb_data['error']
                r.reason = fb_data['error']
                print(f"    ⚠ {fb_data['error']} ({r.elapsed:.1f}s)")
                results.append(r)
                continue

            r.fb_name = fb_data.get('name', '')
            r.email = fb_data.get('email', '')
            r.website_from_fb = fb_data.get('website', '')
            r.phone = fb_data.get('phone', '')
            r.match_score = match_score(
                lead['store_name'], r.fb_name,
                lead.get('city', ''), lead.get('state', '')
            )

            # Classify
            if r.website_from_fb:
                r.classification = 'A0_redirect'
                r.reason = f'FB page links to: {r.website_from_fb}'
            elif r.email:
                if r.match_score >= 0.3:
                    r.classification = 'B1_social_verified'
                    r.reason = f'public FB email (match={r.match_score:.2f})'
                else:
                    r.classification = 'B1_social_verified_low_match'
                    r.reason = f'FB email, low match ({r.match_score:.2f})'
            elif fb_data.get('about'):
                r.classification = 'C_social_contact'
                r.reason = 'page found, no public email/website'
            else:
                r.classification = 'facebook_no_contact_info'
                r.reason = 'no contact info found'

            status = r.classification
            extra = f" email: {r.email[:3]}***" if r.email else f" web: {r.website_from_fb}" if r.website_from_fb else ""
            print(f"    → {status}{extra} ({r.elapsed:.1f}s)")

            results.append(r)

            # Rate limit: 3-5s between page loads to avoid FB anti-bot detection
            if i < len(fb_mapping) - 1:
                delay = 3 + (time.perf_counter() * 1000 % 2000) / 1000  # 3-5s jitter
                time.sleep(delay)

            # Checkpoint
            ckpt = {
                'done': f'{i+1}/{len(fb_mapping)}',
                'results': [{'id': rr.lead_id, 'name': rr.store_name,
                             'classification': rr.classification, 'reason': rr.reason}
                            for rr in results],
            }
            (OUTPUT_DIR / 'checkpoint.json').write_text(json.dumps(ckpt, indent=2))

        browser.close()

    # --- Summary ---
    counts = {}
    for r in results:
        key = r.classification or 'unknown'
        counts[key] = counts.get(key, 0) + 1

    total_time = sum(r.elapsed for r in results)
    websites_found = sum(1 for r in results if r.website_from_fb)
    emails_found = sum(1 for r in results if r.email)
    errors = sum(1 for r in results if r.error)

    print()
    print("=" * 60)
    print("Facebook Enrichment — Results")
    print("=" * 60)
    print(f"Total websites scanned:   {len(leads)}")
    print(f"Facebook links found:     {len(fb_mapping)}")
    print(f"Pages successfully open:  {len(fb_mapping) - errors}")
    print(f"New websites found (A0):  {websites_found}")
    print(f"Public emails found:      {emails_found}")
    for cls, cnt in sorted(counts.items()):
        print(f"  {cls}: {cnt}")
    if results:
        print(f"Avg time per lead:        {total_time/len(results):.1f}s")
    print("=" * 60)

    # Audit JSON
    audit = {
        'summary': {
            'total_scanned': len(leads),
            'fb_found': len(fb_mapping),
            'pages_opened': len(fb_mapping) - errors,
            'websites_found': websites_found,
            'emails_found': emails_found,
            'counts': counts,
            'avg_seconds': total_time / len(results) if results else 0,
        },
        'results': [
            {
                'lead_id': r.lead_id,
                'store': r.store_name,
                'website': r.website,
                'fb_url': r.fb_url,
                'fb_name': r.fb_name,
                'match': r.match_score,
                'email': r.email[:3] + '***' if r.email else '',
                'website_from_fb': r.website_from_fb,
                'classification': r.classification,
                'reason': r.reason,
                'error': r.error,
                'elapsed': r.elapsed,
            }
            for r in results
        ],
    }
    audit_path = OUTPUT_DIR / 'fb_audit.json'
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"\nAudit saved: {audit_path}")


if __name__ == '__main__':
    main()
