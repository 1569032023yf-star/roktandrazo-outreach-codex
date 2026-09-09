"""Facebook Contact Enrichment — Official Website to Facebook Page Bridge.

Flow:
1. Scan official website for Facebook page links
2. Open Facebook page in dedicated persistent browser profile
3. Extract publicly visible contact info (email, website, phone, address)
4. Classify: A0_redirect, B1_social_verified, C_social_contact, blocked

Uses persistent browser profile at D:\\BD_BROWSER_PROFILES\\facebook_business_enrichment\\
No DB writes. No email sends. Read-only.
"""
from __future__ import annotations

import json
import re
import sys
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

# Project setup
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

BROWSER_PROFILE = Path("D:/BD_BROWSER_PROFILES/facebook_business_enrichment")
CACHE_FILE = PROJECT_DIR / "facebook_enrichment" / "page_cache.json"

# ============================================================
# Facebook link extraction pattern
# ============================================================

# Only match actual Facebook business/page links, not login/share/messenger
FB_PAGE_RE = re.compile(
    r'https?://(?:www\.)?facebook\.com/'
    r'(?!login|sharer|share|sharer\.php|dialog|plugins|tr|ajax|help|policies|privacy|legal|about|settings|messages|messenger|bookmarks|groups/feed|events)'
    r'([A-Za-z0-9.\-_]+/?[A-Za-z0-9.\-_]*)(?:\?[^"\s<>]*)?'
    r'(?:"|\'|\s|>|$)',
    re.I,
)

# Known false-positive patterns
FB_EXCLUDE_PATTERNS = [
    re.compile(r'facebook\.com/sharer', re.I),
    re.compile(r'facebook\.com/login', re.I),
    re.compile(r'facebook\.com/dialog', re.I),
    re.compile(r'facebook\.com/plugins', re.I),
    re.compile(r'facebook\.com/profile\.php\?id=\d+', re.I),  # Personal profile
]

# Facebook About/Info selectors
FB_ABOUT_SELECTORS = [
    'div[data-pagelet="PageAbout"]',
    'div[data-pagelet="ProfileTabs"] + div',
    'div[role="main"] div[class*="about"]',
    'div.x1lliihq',  # Generic container
]

# Contact info extraction patterns
EMAIL_RE = re.compile(r'[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+')
PHONE_RE = re.compile(r'(?:\+1[-\s]?)?\(?\d{3}\)?[-\s.]?\d{3}[-\s.]?\d{4}')
WEBSITE_RE = re.compile(r'(?:website|web|visit|site)[:\s]+(https?://[^\s<>"\']+)', re.I)


@dataclass
class EnrichmentResult:
    lead_id: int
    store_name: str
    official_website: str
    facebook_links_found: list[str] = field(default_factory=list)
    facebook_page_url: str = ""
    facebook_source_url: str = ""
    facebook_link_confidence: str = ""
    facebook_match_score: float = 0.0
    extracted_email: str = ""
    extracted_website: str = ""
    extracted_phone: str = ""
    extracted_address: str = ""
    about_text: str = ""
    classification: str = ""
    classification_reason: str = ""
    elapsed_seconds: float = 0.0
    error: str = ""


# ============================================================
# 1. Website Facebook Link Extraction
# ============================================================

def extract_facebook_links(html: str, page_url: str) -> list[dict]:
    """Extract Facebook business page links from website HTML.

    Returns list of {url, raw_url, source_tag, confidence}.
    Excludes login, share, messenger, personal profile, and generic facebook.com.
    """
    results = []
    seen = set()

    # Method 1: href attributes
    href_matches = re.finditer(
        r'href=["\']?(https?://(?:www\.)?facebook\.com/[^"\'\s<>]+)["\']?',
        html, re.I
    )
    for m in href_matches:
        raw_url = m.group(1).rstrip('/')
        if _is_valid_fb_page(raw_url):
            clean = _clean_fb_url(raw_url)
            if clean and clean not in seen:
                seen.add(clean)
                results.append({
                    'url': clean,
                    'raw_url': raw_url,
                    'source': f'href: {m.group(0)[:50]}',
                    'confidence': 'high',
                })

    # Method 2: text content (bare URLs in body)
    text_matches = FB_PAGE_RE.finditer(html)
    for m in text_matches:
        raw_url = m.group(0).rstrip('/')
        if _is_valid_fb_page(raw_url):
            clean = _clean_fb_url(raw_url)
            if clean and clean not in seen:
                seen.add(clean)
                results.append({
                    'url': clean,
                    'raw_url': raw_url,
                    'source': 'text: body content',
                    'confidence': 'medium',
                })

    return results


def _is_valid_fb_page(url: str) -> bool:
    """Check if a Facebook URL looks like a business page (not login/share/profile)."""
    lowered = url.lower()
    for pat in FB_EXCLUDE_PATTERNS:
        if pat.search(lowered):
            return False
    # Must have a path component beyond facebook.com/
    path = urlparse(url).path.strip('/')
    if not path or path == 'facebook.com':
        return False
    # Exclude common non-page paths
    excluded_paths = ('login', 'sharer', 'share', 'sharer.php', 'dialog', 'plugins',
                       'tr', 'ajax', 'help', 'policies', 'privacy', 'legal',
                       'about', 'settings', 'messages', 'messenger', 'bookmarks')
    first_segment = path.split('/')[0].lower()
    if first_segment in excluded_paths:
        return False
    if 'profile.php' in lowered:
        return False
    return True


def _clean_fb_url(url: str) -> str:
    """Normalize Facebook URL: remove tracking params, trailing garbage, ensure standard format."""
    # Remove trailing quote marks, brackets, spaces
    url = url.rstrip('"\'\\]\\[) ')
    # Remove query params and fragments
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    if not path or path == '/':
        return ""
    return f"https://www.facebook.com{path}"


# ============================================================
# 2. Website Fetcher (httpx)
# ============================================================

def fetch_website(url: str, timeout: int = 15) -> str | None:
    """Fetch a website's HTML. Returns None on failure."""
    try:
        import httpx
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        }
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True, verify=False)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def scan_website_for_facebook(official_website: str) -> list[dict]:
    """Scan a website (homepage + /contact + /about) for Facebook links."""
    all_links = []
    pages = [
        official_website,
        urljoin(official_website, '/contact'),
        urljoin(official_website, '/about'),
        urljoin(official_website, '/about-us'),
    ]

    for page_url in pages[:3]:  # Max 3 pages to avoid overload
        html = fetch_website(page_url)
        if html:
            links = extract_facebook_links(html, page_url)
            for link in links:
                link['discovered_on'] = page_url
            all_links.extend(links)
            if all_links:
                break  # Found Facebook link, stop scanning

    # Deduplicate
    seen = set()
    unique = []
    for link in all_links:
        if link['url'] not in seen:
            seen.add(link['url'])
            unique.append(link)
    return unique


# ============================================================
# 3. Facebook Page Reader (Playwright)
# ============================================================

def _get_browser():
    """Get or create a persistent browser context with Facebook login state."""
    from playwright.sync_api import sync_playwright

    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)

    p = sync_playwright().start()
    browser = p.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE),
        headless=False,  # First run needs headed mode for login
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
        ],
        viewport={'width': 1280, 'height': 900},
        locale='en-US',
    )
    return p, browser


def _check_fb_login(page) -> bool:
    """Check if Facebook is logged in. Returns True if logged in."""
    try:
        page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=15000)
        # If we see login form, not logged in
        login_elements = page.query_selector_all('input[name="email"], #loginbutton, [data-testid="royal_login_form"]')
        if login_elements:
            return False
        return True
    except Exception:
        return False


def read_facebook_page(fb_url: str, timeout: int = 30) -> dict[str, Any]:
    """Open a Facebook page and extract publicly visible contact information.

    Returns dict with: email, website, phone, address, about_text, name, error.
    """
    result = {
        'email': '', 'website': '', 'phone': '', 'address': '',
        'about_text': '', 'name': '', 'error': '',
    }

    from playwright.sync_api import sync_playwright

    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE),
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
            viewport={'width': 1280, 'height': 900},
            locale='en-US',
        )

        try:
            page = browser.new_page()

            # Check login state on first page
            test_page = browser.new_page()
            test_page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=15000)
            login_form = test_page.query_selector('input[name="email"], #loginbutton')
            test_page.close()

            if login_form:
                result['error'] = 'facebook_login_required'
                print(f"  ⚠ Facebook login required. Please log in manually, then press Enter to continue...")
                input()
                # Reload test
                test_page2 = browser.new_page()
                test_page2.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=15000)
                still_login = test_page2.query_selector('input[name="email"], #loginbutton')
                test_page2.close()
                if still_login:
                    result['error'] = 'facebook_login_required'
                    browser.close()
                    return result

            # Navigate to the Facebook page
            page.goto(fb_url, wait_until='domcontentloaded', timeout=timeout * 1000)
            time.sleep(3)  # Let dynamic content load

            # Check for various block states
            page_text = page.content().lower()
            if 'you must log in' in page_text:
                result['error'] = 'facebook_login_required'
                browser.close()
                return result
            if 'confirm your identity' in page_text or 'captcha' in page_text:
                result['error'] = 'facebook_captcha'
                browser.close()
                return result
            if 'this content isn\'t available' in page_text or 'page not found' in page_text:
                result['error'] = 'facebook_page_not_found'
                browser.close()
                return result

            # Extract page name
            try:
                name_el = page.query_selector('h1, [aria-label] span')
                if name_el:
                    result['name'] = name_el.inner_text().strip()
            except Exception:
                pass

            # Extract about text (entire page content, focused)
            try:
                body = page.query_selector('body')
                if body:
                    result['about_text'] = body.inner_text()[:3000]
            except Exception:
                pass

            # Try to click "About" tab if available
            try:
                about_tab = page.query_selector('a[href*="/about"]')
                if about_tab and about_tab.is_visible():
                    about_tab.click()
                    time.sleep(2)
                    about_section = page.query_selector('div[role="main"]')
                    if about_section:
                        result['about_text'] += '\n' + about_section.inner_text()[:2000]
            except Exception:
                pass

            # Extract contact info from page text
            full_text = result['about_text']

            # Email
            emails = EMAIL_RE.findall(full_text)
            if emails:
                result['email'] = emails[0]

            # Website
            websites = WEBSITE_RE.findall(full_text)
            if websites:
                result['website'] = websites[0].strip()

            # Phone
            phones = PHONE_RE.findall(full_text)
            if phones:
                result['phone'] = phones[0]

            # Try to get website from "Info" section
            if not result['website']:
                try:
                    website_links = page.query_selector_all('a[href*="http"]')
                    for link in website_links:
                        href = link.get_attribute('href') or ''
                        if href.startswith('http') and 'facebook.com' not in href and 'l.php' not in href:
                            result['website'] = href
                            break
                except Exception:
                    pass

            browser.close()

        except Exception as e:
            result['error'] = f'browser_error: {str(e)[:100]}'
            try:
                browser.close()
            except Exception:
                pass

    return result


# ============================================================
# 4. Business Name Matching
# ============================================================

def match_score(store_name: str, fb_page_name: str, city: str = "", state: str = "") -> float:
    """Score Facebook page match against known business info. 0.0-1.0."""
    score = 0.0
    sn = store_name.lower().strip()
    fn = fb_page_name.lower().strip()
    c = city.lower().strip()
    s = state.lower().strip()

    # Name similarity: simple token overlap
    sn_tokens = set(sn.split())
    fn_tokens = set(fn.split())
    if sn_tokens and fn_tokens:
        overlap = sn_tokens & fn_tokens
        name_score = len(overlap) / max(len(sn_tokens), len(fn_tokens))
        score += name_score * 0.6

    # City match
    if c and c in fn:
        score += 0.2

    # State match
    if s and s in fn:
        score += 0.1

    # Full name contains/store contains other
    if sn in fn or fn in sn:
        score = max(score, 0.7)

    return min(score, 1.0)


# ============================================================
# 5. Classification
# ============================================================

def classify_result(lead: dict, fb_links: list[dict], fb_data: dict, match_score_val: float) -> dict:
    """Classify the enrichment result.

    Returns: {classification, reason, email, website, phone, address, about}
    """
    if fb_data.get('error'):
        error = fb_data['error']
        if 'login' in error:
            return {'classification': 'facebook_login_required', 'reason': 'Facebook login required'}
        if 'captcha' in error:
            return {'classification': 'facebook_captcha', 'reason': 'CAPTCHA or identity check'}
        if 'page_not_found' in error:
            return {'classification': 'facebook_page_not_found', 'reason': 'Page not found'}
        return {'classification': 'facebook_access_blocked', 'reason': error}

    # Case A: Facebook page has website link → redirect back to website verification
    if fb_data.get('website'):
        return {
            'classification': 'A0_redirect',
            'reason': f"Facebook page has website: {fb_data['website']}",
            'website': fb_data['website'],
        }

    # Case B: Facebook page has public email
    if fb_data.get('email'):
        if match_score_val >= 0.3:
            return {
                'classification': 'B1_social_verified',
                'reason': f'Public Facebook email found (match={match_score_val:.2f})',
                'email': fb_data['email'],
                'match_score': match_score_val,
            }
        else:
            return {
                'classification': 'B1_social_verified_low_match',
                'reason': f'Facebook email found but low match ({match_score_val:.2f})',
                'email': fb_data['email'],
                'match_score': match_score_val,
            }

    # Case C: Only Messenger/Contact button (inferred from no email/website)
    if fb_data.get('about_text'):
        return {
            'classification': 'C_social_contact',
            'reason': 'Facebook page found but no public email/website',
        }

    # Case D: Page exists but no contact info
    return {
        'classification': 'facebook_no_contact_info',
        'reason': 'Page accessible but no contact information found',
    }


# ============================================================
# 6. Main Enrichment Runner
# ============================================================

def enrich_one_lead(lead: dict, max_retries: int = 1) -> EnrichmentResult:
    """Run full enrichment for a single lead."""
    started = time.perf_counter()
    result = EnrichmentResult(
        lead_id=lead['id'],
        store_name=lead.get('store_name', ''),
        official_website=lead.get('official_website', ''),
    )

    # Step 1: Scan website for Facebook links
    fb_links = scan_website_for_facebook(result.official_website)
    result.facebook_links_found = [l['url'] for l in fb_links]

    if not fb_links:
        result.classification = 'no_facebook_link'
        result.classification_reason = 'No Facebook page link found on website'
        result.elapsed_seconds = time.perf_counter() - started
        return result

    # Use the highest confidence link
    best_link = max(fb_links, key=lambda l: 0 if l['confidence'] == 'high' else 1)
    result.facebook_page_url = best_link['url']
    result.facebook_source_url = best_link.get('discovered_on', '')
    result.facebook_link_confidence = best_link['confidence']

    # Step 2: Open Facebook page and extract contacts
    for attempt in range(1 + max_retries):
        fb_data = read_facebook_page(result.facebook_page_url)
        if fb_data.get('error') == 'facebook_login_required' and attempt < max_retries:
            continue
        break

    # Step 3: Match score
    match_s = match_score(
        result.store_name,
        fb_data.get('name', ''),
        lead.get('city', ''),
        lead.get('state', ''),
    )
    result.facebook_match_score = match_s

    # Step 4: Extract contact info
    result.extracted_email = fb_data.get('email', '')
    result.extracted_website = fb_data.get('website', '')
    result.extracted_phone = fb_data.get('phone', '')
    result.extracted_address = fb_data.get('address', '')
    result.about_text = (fb_data.get('about_text', '') or '')[:500]

    # Step 5: Classify
    classification = classify_result(lead, fb_links, fb_data, match_s)
    result.classification = classification.get('classification', 'unknown')
    result.classification_reason = classification.get('reason', '')
    result.error = fb_data.get('error', '')

    result.elapsed_seconds = time.perf_counter() - started
    return result


def run_enrichment_batch(leads: list[dict], max_retries: int = 1) -> list[EnrichmentResult]:
    """Run enrichment for a batch of leads. Sequential (concurrency=1)."""
    results = []
    total = len(leads)
    for i, lead in enumerate(leads):
        print(f"[{i+1}/{total}] {lead.get('store_name', '')[:35]} — {lead.get('official_website', '')[:50]}")
        result = enrich_one_lead(lead, max_retries=max_retries)
        results.append(result)
        status = result.classification or result.error or 'ok'
        print(f"  → {status} ({result.elapsed_seconds:.1f}s) {'email:' + result.extracted_email[:30] if result.extracted_email else ''}")
        # Checkpoint after each lead
        _save_checkpoint(results, i + 1, total)
    return results


def _save_checkpoint(results: list[EnrichmentResult], done: int, total: int):
    """Save intermediate results as JSON checkpoint."""
    data = {
        'checkpoint': f'{done}/{total}',
        'results': [
            {
                'lead_id': r.lead_id,
                'store_name': r.store_name,
                'classification': r.classification,
                'extracted_email': r.extracted_email[:5] + '***' if r.extracted_email else '',
                'error': r.error,
            }
            for r in results
        ],
    }
    checkpoint_path = PROJECT_DIR / "facebook_enrichment" / "checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ============================================================
# 7. CLI
# ============================================================

def main():
    import sqlite3

    db_path = PROJECT_DIR / "data" / "bd_leads.db"
    conn = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Get test candidates
    rows = conn.execute("""
        SELECT id, store_name, city, state, official_website, email, email_source_type, status
        FROM leads
        WHERE state IN ('TN', 'AR', 'KY')
        AND official_website IS NOT NULL AND official_website != ''
        AND (email IS NULL OR email = '' OR email_source_type IN ('guessed_email','no_contact_found','unknown')
             OR email_verified_on_official_site = 0)
        AND status NOT IN ('sent', 'bounced', 'unsubscribed', 'delivery_issue')
        AND email NOT IN (SELECT email FROM suppression_list WHERE email IS NOT NULL)
        AND id NOT IN (SELECT lead_id FROM bounce_log WHERE bounce_type = 'hard')
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status = 'sent')
        LIMIT 15
    """).fetchall()

    leads = [dict(r) for r in rows]
    print(f"Starting Facebook enrichment for {len(leads)} leads...")
    print(f"Browser profile: {BROWSER_PROFILE}")
    print()

    results = run_enrichment_batch(leads)
    conn.close()

    # Summary
    counts = {}
    for r in results:
        key = r.classification or r.error or 'unknown'
        counts[key] = counts.get(key, 0) + 1

    total_time = sum(r.elapsed_seconds for r in results)
    fb_found = sum(1 for r in results if r.facebook_page_url)
    emails_found = sum(1 for r in results if r.extracted_email)
    websites_found = sum(1 for r in results if r.extracted_website)

    print()
    print("=" * 60)
    print("Facebook 增强测试完成")
    print(f"检查官网：{len(leads)}")
    print(f"发现 Facebook Page：{fb_found}")
    print(f"成功打开 Page：{sum(1 for r in results if r.error == '' and r.facebook_page_url)}")
    print(f"找到公开邮箱：{emails_found}")
    print(f"找到新官网链接：{websites_found}")
    for cls, cnt in sorted(counts.items()):
        print(f"  {cls}: {cnt}")
    print(f"平均每条耗时：{total_time/len(results):.1f}s" if results else "N/A")
    print("=" * 60)

    # Save full audit JSON
    audit = {
        'summary': {
            'total': len(results),
            'fb_found': fb_found,
            'emails_found': emails_found,
            'websites_found': websites_found,
            'avg_seconds': total_time / len(results) if results else 0,
            'counts': counts,
        },
        'results': [
            {
                'lead_id': r.lead_id,
                'store_name': r.store_name,
                'official_website': r.official_website,
                'facebook_page_url': r.facebook_page_url,
                'facebook_link_confidence': r.facebook_link_confidence,
                'extracted_email': r.extracted_email[:3] + '***' if r.extracted_email else '',
                'extracted_website': r.extracted_website,
                'classification': r.classification,
                'classification_reason': r.classification_reason,
                'error': r.error,
                'elapsed_seconds': r.elapsed_seconds,
            }
            for r in results
        ],
    }
    audit_path = PROJECT_DIR / "facebook_enrichment" / "audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"\nAudit saved: {audit_path}")


if __name__ == "__main__":
    main()
