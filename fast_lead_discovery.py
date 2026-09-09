#!/usr/bin/env python3
"""
Fast Lead Discovery — HTTP-first email extraction with browser fallback.
Crawlee-like pipeline: HTTP fast scan → page discovery → browser fallback.

Usage:
    python fast_lead_discovery.py --input sample30.json --output results.json
    python fast_lead_discovery.py --from-b2 30 --output results.json
    python fast_lead_discovery.py --from-cities "Asheville,NC;Boise,ID" --output results.json
"""

import sys, os, re, json, time, argparse, hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup

# ============================================================
# CONFIG
# ============================================================

HTTP_TIMEOUT = 5          # seconds per HTTP request
BROWSER_TIMEOUT = 8       # seconds per browser page load
MAX_PAGES_PER_DOMAIN = 5  # max pages to check per domain
MAX_CONCURRENT = 3        # concurrent HTTP requests
EARLY_STOP = True         # stop after first email found

CONTACT_PATHS = [
    '/', '/contact', '/contact-us', '/pages/contact',
    '/about', '/about-us', '/pages/about',
    '/wholesale', '/vendor', '/buyer',
]

# Pages discovered from homepage links
DISCOVERY_KEYWORDS = [
    'contact', 'about', 'wholesale', 'vendor', 'buyer',
    'reach', 'get-in-touch', 'info',
]

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

SKIP_DOMAINS = {
    'facebook.com', 'instagram.com', 'twitter.com', 'yelp.com',
    'google.com', 'amazon.com', 'shopify.com', 'wix.com',
    'squarespace.com', 'etsy.com', 'ebay.com',
}

# ============================================================
# EMAIL EXTRACTION
# ============================================================

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
OBFUSCATED_RE = re.compile(
    r'([a-zA-Z0-9._%+\-]+)\s*[\[\(]\s*at\s*[\]\)]\s*([a-zA-Z0-9.\-]+)\s*[\[\(]\s*dot\s*[\]\)]\s*([a-zA-Z]{2,})',
    re.IGNORECASE
)

def extract_emails(text: str) -> list[tuple[str, str]]:
    """Extract emails from text. Returns [(email, context), ...]"""
    results = []
    # Standard emails
    for m in EMAIL_RE.finditer(text):
        email = m.group(0).lower()
        start = max(0, m.start() - 40)
        end = min(len(text), m.end() + 40)
        context = text[start:end].replace('\n', ' ').strip()
        if not any(skip in email for skip in [
            'example.com', 'yourdomain', 'domain.com', 'youremail',
            'wixpress', 'sentry', 'shopify', 'roktandrazo',
            '.png', '.jpg', '.gif', '.svg',
        ]):
            results.append((email, context))
    # Obfuscated emails: info [at] domain [dot] com
    for m in OBFUSCATED_RE.finditer(text):
        email = f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower()
        context = m.group(0)
        results.append((email, context))
    # Deduplicate
    seen = set()
    deduped = []
    for email, ctx in results:
        if email not in seen:
            seen.add(email)
            deduped.append((email, ctx))
    return deduped

def extract_mailto(soup: BeautifulSoup) -> list[str]:
    """Extract emails from mailto: links."""
    emails = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('mailto:'):
            email = href.replace('mailto:', '').split('?')[0].strip().lower()
            if email and '@' in email:
                emails.append(email)
    return list(set(emails))

# ============================================================
# HTTP FAST SCAN
# ============================================================

def http_fetch(client: httpx.Client, url: str) -> str | None:
    """Fetch a URL via HTTP. Returns text or None."""
    try:
        resp = client.get(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None

def http_scan_page(client: httpx.Client, url: str) -> tuple[list[str], list[str], str]:
    """Scan a single page for emails. Returns (emails, mailto_emails, body_text)."""
    body = http_fetch(client, url)
    if not body:
        return [], [], ''
    
    soup = BeautifulSoup(body, 'lxml')
    
    # Extract visible text
    for tag in soup(['script', 'style', 'noscript', 'img', 'video', 'audio', 'iframe']):
        tag.decompose()
    text = soup.get_text(separator=' ', strip=True)
    
    # Extract emails from text
    emails_ctx = extract_emails(text)
    emails = [e for e, _ in emails_ctx]
    
    # Extract mailto
    mailto = extract_mailto(soup)
    
    # Also check raw HTML for obfuscated patterns
    html_emails_ctx = extract_emails(body)
    for e, _ in html_emails_ctx:
        if e not in emails:
            emails.append(e)
    
    all_emails = list(set(emails + mailto))
    return all_emails, mailto, text

def discover_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Discover contact/about links from homepage."""
    links = []
    base_domain = urlparse(base_url).netloc
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        
        # Only same domain
        if parsed.netloc != base_domain:
            continue
        
        # Check if link text or URL contains contact keywords
        link_text = (a.get_text() or '').lower()
        href_lower = href.lower()
        
        for kw in DISCOVERY_KEYWORDS:
            if kw in link_text or kw in href_lower:
                if full_url not in links:
                    links.append(full_url)
                break
    
    return links[:5]  # max 5 discovered links

def http_fast_scan(client: httpx.Client, base_url: str) -> dict:
    """
    HTTP-first scan: check homepage + contact paths + discovered links.
    Returns result dict.
    """
    result = {
        'emails_found': [],
        'evidence_url': '',
        'evidence_snippet': '',
        'pages_checked': 0,
        'method': 'http',
        'has_contact_form': False,
    }
    
    checked_urls = set()
    pages_checked = 0
    
    # Phase 1: Check fixed contact paths
    for path in CONTACT_PATHS:
        if pages_checked >= MAX_PAGES_PER_DOMAIN:
            break
        
        url = urljoin(base_url, path)
        if url in checked_urls:
            continue
        checked_urls.add(url)
        
        emails, mailto, text = http_scan_page(client, url)
        pages_checked += 1
        
        if emails:
            result['emails_found'] = emails
            result['evidence_url'] = url
            # Find context snippet
            for email in emails:
                for m in EMAIL_RE.finditer(text):
                    if m.group(0).lower() == email:
                        start = max(0, m.start() - 60)
                        end = min(len(text), m.end() + 60)
                        result['evidence_snippet'] = text[start:end].strip()
                        break
                if result['evidence_snippet']:
                    break
            if EARLY_STOP:
                break
        
        # Check for contact form
        if text and ('<form' in text.lower() or 'contact form' in text.lower()):
            result['has_contact_form'] = True
    
    # Phase 2: Discover additional links from homepage
    if not result['emails_found'] and pages_checked < MAX_PAGES_PER_DOMAIN:
        homepage = http_fetch(client, base_url)
        if homepage:
            soup = BeautifulSoup(homepage, 'lxml')
            discovered = discover_links(soup, base_url)
            
            for url in discovered:
                if pages_checked >= MAX_PAGES_PER_DOMAIN:
                    break
                if url in checked_urls:
                    continue
                checked_urls.add(url)
                
                emails, mailto, text = http_scan_page(client, url)
                pages_checked += 1
                
                if emails:
                    result['emails_found'] = emails
                    result['evidence_url'] = url
                    for email in emails:
                        for m in EMAIL_RE.finditer(text):
                            if m.group(0).lower() == email:
                                start = max(0, m.start() - 60)
                                end = min(len(text), m.end() + 60)
                                result['evidence_snippet'] = text[start:end].strip()
                                break
                        if result['evidence_snippet']:
                            break
                    if EARLY_STOP:
                        break
    
    result['pages_checked'] = pages_checked
    return result

# ============================================================
# BROWSER FALLBACK
# ============================================================

def browser_scan(browser, base_url: str) -> dict:
    """Browser fallback: render JS-heavy pages and extract emails."""
    result = {
        'emails_found': [],
        'evidence_url': '',
        'evidence_snippet': '',
        'pages_checked': 0,
        'method': 'browser',
        'has_contact_form': False,
    }
    
    context = browser.new_context(
        user_agent=USER_AGENT,
        # Block images, fonts, videos for speed
        extra_http_headers={
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    )
    
    # Block unnecessary resources
    def route_handler(route):
        resource_type = route.request.resource_type
        if resource_type in ('image', 'font', 'media', 'stylesheet'):
            route.abort()
        else:
            route.continue_()
    
    page = context.new_page()
    page.route('**/*', route_handler)
    
    checked_urls = set()
    pages_checked = 0
    
    try:
        for path in CONTACT_PATHS[:5]:  # Only check top 5 paths for browser
            if pages_checked >= 3:  # Browser is expensive, limit to 3 pages
                break
            
            url = urljoin(base_url, path)
            if url in checked_urls:
                continue
            checked_urls.add(url)
            
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=BROWSER_TIMEOUT * 1000)
                time.sleep(0.5)  # Brief wait for JS
            except Exception:
                continue
            
            pages_checked += 1
            
            try:
                body_text = page.inner_text('body')
            except Exception:
                body_text = ''
            
            emails_ctx = extract_emails(body_text)
            emails = [e for e, _ in emails_ctx]
            
            if emails:
                result['emails_found'] = emails
                result['evidence_url'] = url
                result['evidence_snippet'] = emails_ctx[0][1][:150] if emails_ctx else ''
                break
            
            # Check for contact form
            try:
                if page.locator('form').count() > 0:
                    result['has_contact_form'] = True
            except Exception:
                pass
    
    except Exception as e:
        result['error'] = str(e)[:200]
    finally:
        context.close()
    
    result['pages_checked'] = pages_checked
    return result

# ============================================================
# CLASSIFICATION
# ============================================================

def classify_lead(lead: dict, scan_result: dict) -> dict:
    """Classify a lead based on scan results."""
    emails = scan_result.get('emails_found', [])
    
    if emails:
        # Filter out guessed-pattern emails
        store_domain = urlparse(lead.get('official_website', '')).netloc.replace('www.', '')
        verified_emails = []
        for email in emails:
            email_domain = email.split('@')[1] if '@' in email else ''
            # Accept if email domain matches store domain
            if store_domain and (email_domain == store_domain or email_domain.endswith('.' + store_domain)):
                verified_emails.append(email)
            # Also accept generic business emails (info@, contact@, hello@)
            elif email.startswith(('info@', 'contact@', 'hello@', 'sales@', 'wholesale@')):
                verified_emails.append(email)
        
        if verified_emails:
            return {
                'classification': 'A0',
                'email': verified_emails[0],
                'all_emails': verified_emails,
                'evidence_url': scan_result.get('evidence_url', ''),
                'evidence_snippet': scan_result.get('evidence_snippet', ''),
                'confidence': 'A',
            }
    
    if scan_result.get('has_contact_form'):
        return {
            'classification': 'C_contact_form',
            'reason': 'contact_form_only',
        }
    
    if scan_result.get('pages_checked', 0) == 0:
        return {
            'classification': 'verification_failed',
            'reason': 'website_unreachable',
        }
    
    return {
        'classification': 'B2_manual_review',
        'reason': 'no_email_found',
        'pages_checked': scan_result.get('pages_checked', 0),
    }

# ============================================================
# MAIN PIPELINE
# ============================================================

def process_lead(client: httpx.Client, browser, lead: dict) -> dict:
    """Process a single lead through the pipeline."""
    url = (lead.get('official_website') or '').strip()
    if not url or not url.startswith('http'):
        return {**lead, 'classification': 'Invalid', 'reason': 'no_valid_url'}
    
    domain = urlparse(url).netloc
    if any(skip in domain for skip in SKIP_DOMAINS):
        return {**lead, 'classification': 'Invalid', 'reason': f'skip_domain: {domain}'}
    
    start_time = time.time()
    
    # Step 1: HTTP fast scan
    scan_result = http_fast_scan(client, url)
    
    # Step 2: Browser fallback if HTTP found nothing
    if not scan_result['emails_found'] and browser:
        browser_result = browser_scan(browser, url)
        if browser_result['emails_found']:
            scan_result = browser_result
    
    elapsed = time.time() - start_time
    
    # Step 3: Classify
    classification = classify_lead(lead, scan_result)
    
    return {
        **lead,
        **classification,
        'scan_method': scan_result.get('method', 'unknown'),
        'pages_checked': scan_result.get('pages_checked', 0),
        'scan_time': round(elapsed, 2),
    }

def main():
    parser = argparse.ArgumentParser(description='Fast Lead Discovery')
    parser.add_argument('--input', help='Input JSON file with leads')
    parser.add_argument('--from-b2', type=int, help='Sample N leads from B2 manual_review_needed')
    parser.add_argument('--from-cities', help='Semicolon-separated city,state pairs')
    parser.add_argument('--output', default='fast_discovery_results.json', help='Output JSON file')
    parser.add_argument('--no-browser', action='store_true', help='Disable browser fallback')
    parser.add_argument('--max-leads', type=int, default=30, help='Max leads to process')
    args = parser.parse_args()
    
    # Load leads
    leads = []
    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            leads = json.load(f)
    elif args.from_b2:
        # Load from database
        sys.path.insert(0, os.path.dirname(__file__))
        from bd_db import get_db
        conn = get_db()
        c = conn.cursor()
        c.execute('''SELECT id, store_name, city, state, store_type, official_website
            FROM leads WHERE status='manual_review_needed'
            AND official_website IS NOT NULL AND official_website != ''
            ORDER BY RANDOM() LIMIT ?''', (args.from_b2,))
        leads = [dict(r) for r in c.fetchall()]
        conn.close()
    else:
        print("Error: specify --input, --from-b2, or --from-cities")
        sys.exit(1)
    
    leads = leads[:args.max_leads]
    print(f"\n=== FAST LEAD DISCOVERY ===")
    print(f"Leads to process: {len(leads)}")
    print(f"Browser fallback: {'disabled' if args.no_browser else 'enabled'}")
    print(f"Output: {args.output}")
    print()
    
    # Setup HTTP client
    http_client = httpx.Client(
        headers={'User-Agent': USER_AGENT},
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
    )
    
    # Setup browser if needed
    browser = None
    if not args.no_browser:
        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
        except Exception as e:
            print(f"WARNING: Browser unavailable ({e}), continuing with HTTP only")
    
    # Process leads
    results = []
    start_time = time.time()
    
    for i, lead in enumerate(leads, 1):
        store = lead.get('store_name', '?')
        url = lead.get('official_website', '')
        print(f"  [{i}/{len(leads)}] {store[:40]}...", end=' ', flush=True)
        
        result = process_lead(http_client, browser, lead)
        results.append(result)
        
        cls = result.get('classification', '?')
        method = result.get('scan_method', '?')
        elapsed = result.get('scan_time', 0)
        
        if cls == 'A0':
            print(f"✅ A0 ({elapsed}s, {method})")
        elif cls == 'C_contact_form':
            print(f"📋 C ({elapsed}s, {method})")
        elif cls == 'B2_manual_review':
            print(f"❓ B2 ({elapsed}s, {method})")
        elif cls == 'verification_failed':
            print(f"❌ FAIL ({elapsed}s)")
        else:
            print(f"⚠️  {cls} ({elapsed}s)")
    
    total_time = time.time() - start_time
    
    # Cleanup
    http_client.close()
    if browser:
        browser.close()
        pw.stop()
    
    # Save results
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    classifications = {}
    for r in results:
        cls = r.get('classification', 'unknown')
        classifications[cls] = classifications.get(cls, 0) + 1
    
    avg_time = total_time / len(results) if results else 0
    
    print(f"\n=== SUMMARY ===")
    print(f"Total time: {total_time:.1f}s")
    print(f"Avg per lead: {avg_time:.1f}s")
    print(f"Classifications:")
    for cls, count in sorted(classifications.items()):
        print(f"  {cls}: {count}")
    print(f"\nResults saved to: {args.output}")

if __name__ == '__main__':
    main()
