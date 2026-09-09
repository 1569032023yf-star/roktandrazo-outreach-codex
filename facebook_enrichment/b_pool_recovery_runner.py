"""B Pool Recovery Pipeline — website verification + Facebook fallback + Lead Hygiene.

Flow (per lead):
  Stage 1: Scan official website for email → if found, verify evidence
  Stage 2: If no email, extract Facebook link from website
  Stage 3: Open Facebook page (rate-limited) → extract contacts → classify
  Stage 4: Run through production Lead Hygiene Gate

Read-only. No DB writes. No email sends.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from facebook_enrichment.fb_rate_limiter import FBRateLimiter, RateLimitConfig

DB_PATH = PROJECT_DIR / "data" / "bd_leads.db"
PROFILE_DIR = Path("D:/BD_BROWSER_PROFILES/facebook_business_enrichment")
OUTPUT_DIR = Path(__file__).resolve().parent

# --- Patterns ---
EMAIL_RE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9]\.)*[a-zA-Z]{2,}')
FB_HREF_RE = re.compile(
    r'href=["\']?(https?://(?:www\.)?facebook\.com/(?!login|sharer|share|dialog|plugins|'
    r'tr|ajax|help|policies|privacy|legal|settings|messages|messenger|bookmarks|profile\.php)'
    r'[A-Za-z0-9.\-_/]+(?:\?[^"\'\s<>]*)?)["\']?', re.I
)
PHONE_RE = re.compile(r'(?:\+1[-\s]?)?\(?\d{3}\)?[-\s.]?\d{3}[-\s.]?\d{4}')
MAILTO_RE = re.compile(r'mailto:([A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)', re.I)
WEBSITE_LABEL_RE = re.compile(r'(?:Website|Web|Visit|Site)[:\s]*(https?://[^\s<>"\']+)', re.I)

UNSAFE_PREFIXES = ('no-reply', 'noreply', 'privacy', 'copyright', 'support-plugin',
                    'wordpress', 'shopify', 'wix', 'squarespace', 'info@domain')
FREE_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com'}
DIRECTORY_DOMAINS = {'yelp.com', 'yellowpages.com', 'facebook.com', 'google.com'}
NON_EMAIL_DOMAINS = {'sentry.io', '2x.jpg', '3x.jpg', '4x.jpg', 'png', 'jpg', 'jpeg', 'gif',
                     'webp', 'svg', 'css', 'js', 'woff', 'woff2', 'ttf', 'ico', 'mp4', 'mp3'}
UNSAFE_DOMAINS = {'example.com', 'test.com', 'localhost', 'domain.com'}

MAX_LEADS = 50


# ============================================================
# Data structures
# ============================================================

@dataclass
class LeadResult:
    lead_id: int
    store_name: str
    city: str = ""
    state: str = ""
    website: str = ""
    # Stage 1
    website_scanned: bool = False
    website_email_found: str = ""
    website_emails_all: list[str] = field(default_factory=list)
    evidence_url: str = ""
    evidence_snippet: str = ""
    # Stage 2
    fb_link_found: bool = False
    fb_page_url: str = ""
    # Stage 3
    fb_page_opened: bool = False
    fb_page_name: str = ""
    fb_email: str = ""
    fb_website: str = ""
    fb_phone: str = ""
    fb_about: str = ""
    fb_match_score: float = 0.0
    fb_error: str = ""
    # Stage 4
    a0_eligible: bool = False
    gate_reasons: list[str] = field(default_factory=list)
    classification: str = ""
    elapsed: float = 0.0


# ============================================================
# Helpers
# ============================================================

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
    for m in FB_HREF_RE.finditer(html):
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


def extract_emails_from_html(html: str) -> list[str]:
    emails = []
    seen = set()
    # Method 1: mailto
    for m in MAILTO_RE.finditer(html):
        e = m.group(1).strip().strip('"\'<>').lower()
        if e and '@' in e and e not in seen:
            seen.add(e)
            emails.append(e)
    # Method 2: visible text (simple regex, returns full match as group(0))
    for m in EMAIL_RE.finditer(html):
        e = m.group(0).strip().strip('"\'<>').lower()
        if e and '@' in e and e not in seen:
            seen.add(e)
            emails.append(e)
    return emails


def is_safe_email(email: str) -> bool:
    """Check if email is likely a real business contact, not a system/supplier/CDN email."""
    if '@' not in email:
        return False
    prefix = email.split('@')[0].strip().lower()
    domain = email.split('@')[1].strip().lower() if '@' in email else ''

    # Check top-level domain: must not be an image/file extension
    tld = domain.rsplit('.', 1)[-1] if '.' in domain else ''
    if tld in NON_EMAIL_DOMAINS:
        return False
    if domain in NON_EMAIL_DOMAINS:
        return False

    # Unsafe prefixes (system, platform, spam)
    if prefix in UNSAFE_PREFIXES:
        return False
    for up in UNSAFE_PREFIXES:
        if up in prefix:
            return False

    # Directory domains
    if domain in DIRECTORY_DOMAINS:
        return False

    # Unsafe domains
    if domain in UNSAFE_DOMAINS:
        return False

    # Local part looks like a CDN hash or UUID
    if len(prefix) > 40:
        return False
    # Starts with purely numeric sequence (CDN hash)
    if prefix[:3].isdigit() and len(prefix) >= 5 and not any(c.isalpha() for c in prefix[:4]):
        return False

    # Contains www or http (domain confusion)
    if 'www.' in prefix or 'http' in prefix:
        return False

    return True


def _tokenize(name: str) -> set[str]:
    """Break a business/FB name into tokens."""
    name = name.lower().strip().replace('-', ' ').replace('_', ' ').replace("'", '')
    return set(name.split())


def score_match(store: str, fb_name: str, city: str = "", state: str = "", linked_from_official: bool = False) -> float:
    """Score Facebook page match. Official-website-derived link = strong signal."""
    st = store.lower().strip()
    fb = fb_name.lower().strip()
    c = city.lower().strip()
    s = state.lower().strip()

    score = 0.0

    if linked_from_official:
        score += 0.5

    # Token overlap
    st_tokens = _tokenize(store)
    fb_tokens = _tokenize(fb_name)
    if st_tokens and fb_tokens:
        overlap = st_tokens & fb_tokens
        if overlap:
            score += (len(overlap) / max(len(st_tokens), len(fb_tokens))) * 0.3

    # Substring matching: handle fused FB usernames like "smokiesbigfoot"
    # "bigfoot" should be found inside "smokiesbigfoot"
    for tok in st_tokens:
        if len(tok) >= 4 and tok in fb:
            score += 0.15
            break
    for tok in fb_tokens:
        if len(tok) >= 4 and tok in st:
            score += 0.15
            break

    # City match
    if c and c in fb:
        score += 0.1

    # State match  
    if s and s in fb:
        score += 0.05

    if st in fb or fb in st:
        score = max(score, 0.65)

    if st == fb:
        score = 1.0

    return min(score, 1.0)


def is_official_match(store: str, fb_name: str, city: str, state: str, fb_website: str,
                      official_website: str, linked_from_official: bool) -> bool:
    """Determine if Facebook page is the official page for this business.

    A Facebook link directly from the official website is a strong identity signal.
    At least one additional match is required: name, city, phone, address, or website link-back.
    """
    st = store.lower().strip()
    fn = fb_name.lower().strip()
    c = city.lower().strip()
    s = state.lower().strip()
    ow = official_website.lower().strip()
    fw = fb_website.lower().strip()

    # Not from official website → require stronger evidence
    if not linked_from_official:
        return score_match(store, fb_name, city, state, linked_from_official=True) >= 0.6

    # From official website: at least one additional signal
    signals = 0

    # Name similarity (token overlap OR substring match for fused FB usernames)
    st_tokens = set(st.replace('-',' ').replace('_',' ').replace("'",'').split())
    fn_tokens = set(fn.replace('-',' ').replace('_',' ').replace("'",'').split())
    if st_tokens and fn_tokens:
        overlap = st_tokens & fn_tokens
        if len(overlap) >= 1:
            signals += 1
    # Substring match for fused usernames (e.g. "smokiesbigfoot" contains "bigfoot")
    if signals == 0:
        for tok in st_tokens:
            if len(tok) >= 4 and tok in fn:
                signals += 1
                break

    # City match
    if c and c in fn:
        signals += 1

    # State match
    if s and s in fn:
        signals += 1

    # Website link-back
    if ow and fw:
        ow_domain = urlparse('https://' + ow if '://' not in ow else ow).netloc.lower().replace('www.', '')
        fw_domain = urlparse('https://' + fw if '://' not in fw else fw).netloc.lower().replace('www.', '')
        if ow_domain == fw_domain or fw_domain in ow or ow_domain in fw:
            signals += 1

    return signals >= 1


# ============================================================
# Stage 1: Website Verification
# ============================================================

def verify_website(lead: dict) -> tuple[str, str, str, list[str]]:
    """Scan website pages for a real business email.

    Returns: (best_email, evidence_url, evidence_snippet, all_emails)
    """
    url = lead['official_website']
    pages = [
        (url, 'homepage'),
        (urljoin(url, '/contact'), 'contact'),
        (urljoin(url, '/about'), 'about'),
        (urljoin(url, '/about-us'), 'about-us'),
        (urljoin(url, '/wholesale'), 'wholesale'),
        (urljoin(url, '/pages/contact'), 'contact-page'),
    ]

    all_emails = []
    for page_url, label in pages:
        html = fetch_html(page_url)
        if not html:
            continue
        emails = extract_emails_from_html(html)
        for email in emails:
            if is_safe_email(email):
                # Find snippet
                idx = html.lower().find(email)
                if idx >= 0:
                    start = max(0, idx - 80)
                    snippet = ' '.join(html[start:start + 200].split())
                else:
                    snippet = email
                all_emails.append({
                    'email': email,
                    'evidence_url': page_url,
                    'evidence_snippet': snippet[:200],
                    'label': label,
                })

    if not all_emails:
        return '', '', '', []

    # Prefer non-free email domains
    biz = [e for e in all_emails if e['email'].split('@')[1] not in FREE_DOMAINS]
    best = biz[0] if biz else all_emails[0]
    return best['email'], best['evidence_url'], best['evidence_snippet'], [e['email'] for e in all_emails]


# ============================================================
# Stage 2: Facebook Link Extraction
# ============================================================

def find_facebook_link(website: str) -> str | None:
    """Scan website for a Facebook business page link."""
    for page in [website, urljoin(website, '/contact'), urljoin(website, '/about')]:
        html = fetch_html(page)
        if html:
            links = extract_fb_links(html)
            if links:
                return links[0]
    return None


# ============================================================
# Stage 3: Facebook Page Reader
# ============================================================

def read_fb_page_with_limiter(page, fb_url: str, limiter: FBRateLimiter) -> dict:
    """Read a Facebook page respecting rate limits. Single page instance."""
    result = {'name': '', 'email': '', 'website': '', 'phone': '', 'about': '', 'error': ''}

    try:
        # Before navigation
        limiter.before_page_load()

        page.goto(fb_url, wait_until='domcontentloaded', timeout=30000)

        # After page load, wait for content to settle
        limiter.after_page_load()

        # Check for blocks
        text_lower = page.content()[:5000].lower()
        if 'you must log in' in text_lower:
            result['error'] = 'facebook_login_required'
            limiter.block('facebook_login_required')
            return result
        if 'confirm your identity' in text_lower or 'captcha' in text_lower:
            result['error'] = 'facebook_captcha'
            limiter.block('facebook_captcha')
            return result
        if 'this content isn\'t available' in text_lower or 'page not found' in text_lower:
            result['error'] = 'facebook_page_not_found'
            return result

        # Page name
        try:
            h1 = page.query_selector('h1')
            if h1:
                result['name'] = h1.inner_text().strip()
        except Exception:
            pass

        # Initial body text
        try:
            body = page.query_selector('body')
            if body:
                result['about'] = body.inner_text()[:3000]
        except Exception:
            pass

        # Try to click About
        try:
            about_tab = page.query_selector('a[href*="/about"]')
            if about_tab and about_tab.is_visible():
                limiter.before_detail()
                about_tab.click()
                time.sleep(2)
                about_section = page.query_selector('div[role="main"]')
                if about_section:
                    result['about'] += '\n' + about_section.inner_text()[:2000]
        except Exception:
            pass

        full_text = result['about']

        # Extract contacts
        emails = EMAIL_RE.findall(full_text)
        if emails:
            valid = [e for e in emails if is_safe_email(e)]
            if valid:
                result['email'] = valid[0]

        phones = PHONE_RE.findall(full_text)
        if phones:
            result['phone'] = phones[0]

        ws = WEBSITE_LABEL_RE.findall(full_text)
        if ws:
            result['website'] = ws[0]

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


# ============================================================
# Main Pipeline
# ============================================================

def run_b_pool_recovery(leads: list[dict]):
    results: list[LeadResult] = []

    # --- Stage 1: Website Verification ---
    print("=" * 60)
    print("Stage 1: Website Verification")
    print("=" * 60)
    for i, lead in enumerate(leads):
        r = LeadResult(
            lead_id=lead['id'],
            store_name=lead['store_name'],
            city=lead.get('city', ''),
            state=lead.get('state', ''),
            website=lead.get('official_website', ''),
        )
        name = lead['store_name'][:30]

        if not r.website:
            r.classification = 'no_website'
            results.append(r)
            continue

        email, ev_url, ev_snip, all_emails = verify_website(lead)
        r.website_scanned = True
        r.website_emails_all = all_emails

        if email:
            r.website_email_found = email
            r.evidence_url = ev_url
            r.evidence_snippet = ev_snip
            r.classification = 'website_email_found'
            masked = email[:3] + '***@' + email.split('@')[1] if '@' in email else '***'
            print(f"  [{i+1}/{len(leads)}] {name} → email: {masked}")
        else:
            print(f"  [{i+1}/{len(leads)}] {name} → no email")

        results.append(r)

    email_found = sum(1 for r in results if r.website_email_found)
    no_email = sum(1 for r in results if r.website_scanned and not r.website_email_found)
    print(f"\nWebsite emails found: {email_found}")
    print(f"No email on website:  {no_email}")

    # --- Stage 2: Facebook Link Extraction ---
    fb_candidates = [r for r in results if r.website_scanned and not r.website_email_found and r.website]
    print(f"\n{'=' * 60}")
    print(f"Stage 2: Facebook Link Extraction ({len(fb_candidates)} candidates)")
    print("=" * 60)

    for r in fb_candidates:
        name = r.store_name[:30]
        fb_url = find_facebook_link(r.website)
        if fb_url:
            r.fb_link_found = True
            r.fb_page_url = fb_url
            print(f"  {name} → FB: {fb_url}")
        else:
            r.classification = 'no_facebook_link'
            print(f"  {name} → no FB link")

    fb_ready = [r for r in fb_candidates if r.fb_link_found]
    print(f"\nFB links found: {len(fb_ready)}/{len(fb_candidates)}")

    if not fb_ready:
        _finalize(results, leads)
        return

    # --- Stage 3: Facebook Enrichment (with limiter) ---
    print(f"\n{'=' * 60}")
    print(f"Stage 3: Facebook Page Reading ({len(fb_ready)} pages)")
    print("=" * 60)

    limiter = FBRateLimiter()
    limiter.start_round()

    from playwright.sync_api import sync_playwright

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

        # Login check
        if not _check_fb_login(page):
            print("\n⚠ Facebook login not detected. Attempting auto-wait...")
            logged_in = False
            for w in range(60, 360, 60):
                time.sleep(60)
                print(f"  [{w}s] Checking...")
                if _check_fb_login(page):
                    logged_in = True
                    break
            if not logged_in:
                print("Not logged in. Skipping Facebook phase.")
                browser.close()
                _finalize(results, leads)
                return

        for i, r in enumerate(fb_ready):
            if limiter.should_stop():
                break

            started = time.perf_counter()
            name = r.store_name[:30]
            print(f"\n  [{i+1}/{len(fb_ready)}] {name} → {r.fb_page_url}")

            fb_data = read_fb_page_with_limiter(page, r.fb_page_url, limiter)

            r.fb_page_opened = True
            r.fb_page_name = fb_data.get('name', '')
            r.fb_email = fb_data.get('email', '')
            r.fb_website = fb_data.get('website', '')
            r.fb_phone = fb_data.get('phone', '')
            r.fb_about = (fb_data.get('about', '') or '')[:300]
            r.fb_error = fb_data.get('error', '')

            # Match score (linked from official = strong signal)
            r.fb_match_score = score_match(
                r.store_name, r.fb_page_name,
                r.city, r.state, linked_from_official=True
            )

            # Check official match
            is_official = is_official_match(
                r.store_name, r.fb_page_name, r.city, r.state,
                r.fb_website, r.website, linked_from_official=True
            )

            r.elapsed = time.perf_counter() - started

            # Classify FB results
            if r.fb_error:
                if 'login' in r.fb_error:
                    r.classification = 'facebook_login_required'
                elif 'captcha' in r.fb_error:
                    r.classification = 'facebook_captcha'
                else:
                    r.classification = r.fb_error
                print(f"    ⚠ {r.classification}")
            elif r.fb_website:
                r.classification = 'A0_candidate_redirect'
                print(f"    → A0_candidate: website on FB → {r.fb_website[:50]}")
            elif r.fb_email:
                if is_official:
                    r.classification = 'B1_social_verified'
                else:
                    r.classification = 'B1_social_verified_low_match'
                masked = r.fb_email[:3] + '***@' + r.fb_email.split('@')[1] if '@' in r.fb_email else '***'
                print(f"    → {r.classification}: {masked} (match={r.fb_match_score:.2f})")
            elif r.fb_about:
                r.classification = 'C_social_contact'
                print(f"    → C_social_contact (match={r.fb_match_score:.2f})")
            else:
                r.classification = 'facebook_no_contact_info'
                print(f"    → no contact info")

            # After page
            limiter.after_page(r.fb_page_url)

        browser.close()

    # --- Stage 4: Lead Hygiene ---
    print(f"\n{'=' * 60}")
    print("Stage 4: Lead Hygiene Gate")
    print("=" * 60)
    _run_hygiene_gate(results)
    _finalize(results, leads)


def _check_fb_login(page) -> bool:
    try:
        page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=15000)
        time.sleep(2)
        return page.query_selector('input[name="email"], #loginbutton') is None
    except Exception:
        return False


def _run_hygiene_gate(results: list[LeadResult]):
    """Run all A0 candidates through the production Lead Hygiene Gate."""
    from lead_hygiene_gate import evaluate_a0
    from production_adapter import build_candidate_from_db_row, build_context

    conn = sqlite3.connect(f"file:{DB_PATH.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ctx = build_context(conn)

    for r in results:
        if r.classification not in ('website_email_found', 'A0_candidate_redirect'):
            continue

        # Build a synthetic candidate for gate evaluation
        cand = {
            'email': r.website_email_found or r.fb_email,
            'official_website': r.website,
            'evidence_url': r.evidence_url,
            'evidence_snippet': r.evidence_snippet,
            'email_verified_on_official_site': bool(r.website_email_found),
            'email_source_type': 'official_page_visible' if r.website_email_found else 'official_mailto',
            'official_match': True,
            'state': r.state,
        }
        # Social-only: if email came from FB, not website
        if not r.website_email_found and r.fb_email:
            cand['social_only'] = True
            cand['email_verified_on_official_site'] = False
            cand['email_source_type'] = 'facebook_social'

        decision = evaluate_a0(cand)
        r.a0_eligible = decision.a0_eligible
        r.gate_reasons = list(decision.reasons)

        if decision.a0_eligible:
            email = (r.website_email_found or r.fb_email)
            masked = email[:3] + '***@' + email.split('@')[1] if '@' in email else '***'
            print(f"  ✓ A0: {r.store_name[:30]} → {masked}")
        else:
            print(f"  ✗ Rejected: {r.store_name[:30]} → {decision.reasons}")

    conn.close()


def _finalize(results: list[LeadResult], leads: list[dict]):
    counts = {}
    for r in results:
        c = r.classification or 'unknown'
        if r.a0_eligible:
            c = 'A0_passed_gate'
        counts[c] = counts.get(c, 0) + 1

    a0_count = sum(1 for r in results if r.a0_eligible)
    website_email = sum(1 for r in results if r.website_email_found)
    fb_found = sum(1 for r in results if r.fb_link_found)
    fb_pages_opened = sum(1 for r in results if r.fb_page_opened)
    fb_email = sum(1 for r in results if r.fb_email)
    fb_blocked = sum(1 for r in results if 'login' in (r.fb_error or '') or 'captcha' in (r.fb_error or ''))
    total_time = sum(r.elapsed for r in results)

    print()
    print("=" * 60)
    print("B Pool Recovery — Results")
    print("=" * 60)
    print(f"Total processed:          {len(leads)}")
    print(f"Website email found:      {website_email}")
    print(f"FB links found:           {fb_found}")
    print(f"FB pages opened:          {fb_pages_opened}")
    print(f"FB email found:           {fb_email}")
    print(f"A0 eligible (gate):       {a0_count}")
    print(f"FB blocked/captcha:       {fb_blocked}")
    if results:
        print(f"FB avg time/page:         {total_time / max(fb_pages_opened, 1):.1f}s")
    print()
    for cls, cnt in sorted(counts.items()):
        print(f"  {cls}: {cnt}")
    print("=" * 60)

    # Audit JSON
    audit = {
        'summary': {
            'total': len(leads), 'website_email': website_email, 'fb_found': fb_found,
            'fb_pages_opened': fb_pages_opened, 'fb_email': fb_email, 'a0_eligible': a0_count,
            'counts': counts,
        },
        'results': [
            {
                'lead_id': r.lead_id, 'store': r.store_name,
                'website': r.website, 'website_email': r.website_email_found[:3] + '***' if r.website_email_found else '',
                'fb_url': r.fb_page_url, 'fb_name': r.fb_page_name,
                'fb_email': r.fb_email[:3] + '***' if r.fb_email else '',
                'fb_website': r.fb_website, 'fb_match': round(r.fb_match_score, 2),
                'classification': r.classification, 'a0': r.a0_eligible,
                'gate_reasons': r.gate_reasons, 'elapsed': round(r.elapsed, 1),
            }
            for r in results
        ],
    }
    (OUTPUT_DIR / 'b_pool_audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    print(f"\nAudit: {OUTPUT_DIR / 'b_pool_audit.json'}")


def main():
    import sqlite3
    conn = sqlite3.connect(f"file:{DB_PATH.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Select B/B2 candidates: TN/AR/KY, has website, no verified email, not sent
    rows = conn.execute("""
        SELECT id, store_name, city, state, official_website, email, email_source_type, status
        FROM leads
        WHERE state IN ('TN','AR','KY')
        AND official_website IS NOT NULL AND official_website != ''
        AND (email IS NULL OR email = '' OR email_source_type IN ('guessed_email','no_contact_found','unknown','manual_lookup')
             OR email_verified_on_official_site = 0)
        AND status NOT IN ('sent','bounced','unsubscribed','delivery_issue','do_not_contact')
        AND email NOT IN (SELECT email FROM suppression_list WHERE email IS NOT NULL)
        AND id NOT IN (SELECT lead_id FROM bounce_log WHERE bounce_type='hard')
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status='sent')
        ORDER BY official_website IS NOT NULL DESC, id ASC
        LIMIT ?
    """, (MAX_LEADS,)).fetchall()

    leads = [dict(r) for r in rows]
    print(f"Loaded {len(leads)} B/B2 candidates from TN/AR/KY\n")
    conn.close()

    run_b_pool_recovery(leads)


if __name__ == '__main__':
    main()
