"""Focused Facebook fallback — process leads with no website email but FB links.

Classification:
  approved_manual_send_candidate: FB email + strong match + from official website
  B1_social_verified: FB email but weaker evidence
  C_social_contact: Messenger/contact form only, no email

Safe DB writes. No SMTP. No sends.
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from facebook_enrichment.fb_rate_limiter import FBRateLimiter, RateLimitConfig
from lead_hygiene_gate import evaluate_a0
from production_adapter import build_candidate_from_db_row, build_context

DB_PATH = PROJECT_DIR / "data" / "bd_leads.db"
PROFILE_DIR = Path("D:/BD_BROWSER_PROFILES/facebook_business_enrichment")
BACKUP_DIR = PROJECT_DIR / "backups"

EMAIL_RE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9]\.)*[a-zA-Z]{2,}')
FB_HREF_RE = re.compile(
    r'href=["\']?(https?://(?:www\.)?facebook\.com/(?!login|sharer|share|dialog|plugins|'
    r'tr|ajax|help|policies|privacy|legal|settings|messages|messenger|bookmarks|profile\.php)'
    r'[A-Za-z0-9.\-_/]+(?:\?[^"\'\s<>]*)?)["\']?', re.I
)
PHONE_RE = re.compile(r'(?:\+1[-\s]?)?\(?\d{3}\)?[-\s.]?\d{3}[-\s.]?\d{4}')

ALLOWED_STATES = frozenset({"TN", "AR", "KY"})
UNSAFE_PREFIXES = ('no-reply', 'noreply', 'privacy', 'copyright', 'wordpress', 'shopify', 'wix')
NON_EMAIL = {'sentry.io', '2x.jpg', '3x.jpg', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'css', 'js'}
FREE_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com'}


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
    links, seen = [], set()
    for m in FB_HREF_RE.finditer(html):
        raw = m.group(1).rstrip('/"\'\\[]() ')
        path = urlparse(raw).path.rstrip('/')
        if not path or path == '/':
            continue
        clean = f"https://www.facebook.com{path}"
        if clean not in seen:
            seen.add(clean)
            links.append(clean)
    return links


def find_fb_link(website: str) -> str | None:
    for page in [website, urljoin(website, '/contact'), urljoin(website, '/about')]:
        html = fetch_html(page)
        if html:
            links = extract_fb_links(html)
            if links:
                return links[0]
    return None


def is_safe_email(email: str) -> bool:
    if '@' not in email:
        return False
    prefix = email.split('@')[0].strip().lower()
    domain = email.split('@')[1].strip().lower()
    tld = domain.rsplit('.', 1)[-1] if '.' in domain else ''
    if tld in NON_EMAIL or domain in NON_EMAIL:
        return False
    for up in UNSAFE_PREFIXES:
        if up in prefix:
            return False
    if len(prefix) > 40:
        return False
    if prefix[:3].isdigit() and len(prefix) >= 5 and not any(c.isalpha() for c in prefix[:4]):
        return False
    return True


def check_signals(store: str, city: str, state: str, fb_name: str, fb_website: str, official_website: str) -> tuple[int, list]:
    """Count positive identity signals. Returns (count, signal_names)."""
    st = store.lower().strip()
    fn = fb_name.lower().strip()
    c = city.lower().strip()
    s = state.lower().strip()
    ow = official_website.lower().strip()
    fw = fb_website.lower().strip()
    signals = []
    
    # 1. Name match
    st_tokens = set(st.replace('-',' ').replace("'",'').split())
    fn_tokens = set(fn.replace('-',' ').replace("'",'').split())
    if st_tokens and fn_tokens and (st_tokens & fn_tokens):
        signals.append('name_match')
    else:
        for tok in st_tokens:
            if len(tok) >= 4 and tok in fn:
                signals.append('name_substring')
                break
    
    # 2. City
    if c and c in fn:
        signals.append('city_match')
    
    # 3. Website link-back
    if ow and fw:
        od = urlparse('https://' + ow if '://' not in ow else ow).netloc.lower().replace('www.', '')
        fd = urlparse('https://' + fw if '://' not in fw else fw).netloc.lower().replace('www.', '')
        if od == fd or fd in ow or od in fw:
            signals.append('website_linkback')
    
    # 4. State
    if s and s in fn:
        signals.append('state_match')
    
    return len(signals), signals


def backup_db():
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    d = BACKUP_DIR / f"fb_fallback_{ts}"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB_PATH, d / "bd_leads_backup.db")
    return str(d)


def count_pools(conn):
    a0 = conn.execute("""
        SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A'
        AND email_verified_on_official_site=1
        AND email IS NOT NULL AND email != ''
        AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page','manual_lookup')
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
        AND (mx_provider IS NULL OR mx_provider='' OR (mx_provider NOT LIKE '%exchange%' AND mx_provider NOT LIKE '%outlook%' AND mx_provider NOT LIKE '%microsoft%'))
    """).fetchone()[0]
    
    manual = conn.execute("""
        SELECT COUNT(*) FROM leads WHERE status='approved_manual_send_candidate'
        AND email IS NOT NULL AND email != ''
        AND email NOT IN (SELECT email FROM suppression_list)
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
    """).fetchone()[0]
    
    return {'strict_a0': a0, 'manual_candidate': manual, 'total': a0 + manual}


def main():
    print("=" * 60)
    print("Facebook Fallback Recovery")
    print(f"Pool: strict A0 target = 20")
    print("=" * 60)

    backup_dir = backup_db()
    print(f"\n✓ DB backed up: {backup_dir}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    pools = count_pools(conn)
    print(f"Current: strict A0={pools['strict_a0']}, manual={pools['manual_candidate']}, total={pools['total']}")

    # Select candidates
    rows = conn.execute("""
        SELECT * FROM leads
        WHERE state IN ('TN','AR','KY')
        AND official_website IS NOT NULL AND official_website != ''
        AND (email IS NULL OR email = '' OR email_verified_on_official_site = 0)
        AND status IN ('new','manual_review_needed','contact_form_pool')
        AND email NOT IN (SELECT email FROM suppression_list WHERE email IS NOT NULL)
        AND id NOT IN (SELECT lead_id FROM bounce_log WHERE bounce_type='hard')
        AND id NOT IN (SELECT lead_id FROM send_log WHERE status='sent')
        ORDER BY id ASC
        LIMIT 20
    """).fetchall()

    leads = [dict(r) for r in rows]
    states = {r['state'] for r in leads}
    cities = {r['city'] for r in leads if r['city']}
    print(f"\nCandidates: {len(leads)} leads from {', '.join(sorted(states))}")
    print(f"Cities: {', '.join(sorted(cities)[:8])}")

    # Phase 1: Extract FB links
    print(f"\n--- Phase 1: Extract Facebook Links ---")
    fb_map = {}
    no_fb = 0
    for lead in leads:
        name = lead['store_name'][:30]
        fb = find_fb_link(lead['official_website'])
        if fb:
            fb_map[lead['id']] = (lead, fb)
            print(f"  {name} → FB: {fb}")
        else:
            no_fb += 1
            print(f"  {name} → no FB")

    fb_ready = list(fb_map.items())
    print(f"\nFB links: {len(fb_ready)}/{len(leads)}")

    if not fb_ready:
        print("No FB links found. Nothing to do.")
        conn.close()
        return

    # Phase 2: Open FB pages with limiter
    print(f"\n--- Phase 2: Read Facebook Pages ---")
    
    limiter = FBRateLimiter()
    limiter.start_round()

    from playwright.sync_api import sync_playwright
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR), headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
            viewport={'width': 1280, 'height': 900}, locale='en-US',
        )

        # Check login
        pg = browser.new_page()
        pg.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=15000)
        time.sleep(2)
        if pg.query_selector('input[name="email"], #loginbutton'):
            print("⚠ Not logged in. Auto-waiting...")
            for w in range(60, 360, 60):
                time.sleep(60)
                print(f"  [{w}s] Checking...")
                pg2 = browser.new_page()
                pg2.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=15000)
                time.sleep(1)
                if pg2.query_selector('input[name="email"], #loginbutton') is None:
                    pg2.close()
                    break
                pg2.close()
        pg.close()

        results = {}
        total_a = total_b1 = total_c = total_blocked = 0

        for i, (lid, (lead, fb_url)) in enumerate(fb_ready):
            if limiter.should_stop():
                print(f"  ⚠ LIMITER STOP: {limiter.block_reason}")
                break

            name = lead['store_name'][:30]
            started = time.perf_counter()
            print(f"\n  [{i+1}/{len(fb_ready)}] {name} → {fb_url}")

            limiter.before_page_load()
            
            page = browser.new_page()
            page.goto(fb_url, wait_until='domcontentloaded', timeout=30000)
            
            limiter.after_page_load()

            txt = page.content()[:5000].lower()
            if 'you must log in' in txt:
                limiter.block('facebook_login_required')
                total_blocked += 1
                print(f"    ⚠ Login required")
                page.close()
                break
            if 'confirm your identity' in txt or 'captcha' in txt:
                limiter.block('facebook_captcha')
                total_blocked += 1
                print(f"    ⚠ CAPTCHA")
                page.close()
                break

            # Extract
            fb_name = ''
            try:
                h1 = page.query_selector('h1')
                if h1:
                    fb_name = h1.inner_text().strip()
            except Exception:
                pass

            body_text = ''
            try:
                body = page.query_selector('body')
                if body:
                    body_text = body.inner_text()[:3000]
            except Exception:
                pass

            # Click About
            try:
                about = page.query_selector('a[href*="/about"]')
                if about and about.is_visible():
                    limiter.before_detail()
                    about.click()
                    time.sleep(2)
                    main = page.query_selector('div[role="main"]')
                    if main:
                        body_text += '\n' + main.inner_text()[:2000]
            except Exception:
                pass

            # Extract contacts
            fb_email = ''
            emails = [e for e in EMAIL_RE.findall(body_text) if is_safe_email(e)]
            if emails:
                fb_email = emails[0]

            fb_website = ''
            try:
                for link in page.query_selector_all('a[href*="http"]'):
                    href = (link.get_attribute('href') or '')[:200]
                    if href.startswith('http') and 'facebook.com' not in href and 'l.php' not in href:
                        fb_website = href
                        break
            except Exception:
                pass

            # Signals
            sig_count, sig_names = check_signals(
                lead['store_name'], lead.get('city',''), lead.get('state',''),
                fb_name, fb_website, lead['official_website']
            )

            # Classify
            now = datetime.now().isoformat()
            elapsed = time.perf_counter() - started
            
            if fb_email:
                # Has real email
                if sig_count >= 2:
                    # Strong: approved_manual_send_candidate
                    results[lid] = {
                        'lead': lead, 'classification': 'approved_manual_send_candidate',
                        'fb_email': fb_email, 'fb_name': fb_name, 'fb_website': fb_website,
                        'signals': sig_count, 'signal_names': sig_names,
                        'fb_url': fb_url, 'evidence_snippet': body_text[:300],
                    }
                    total_a += 1
                    print(f"    → approved_manual_send: {fb_email[:3]}*** (signals={sig_count}: {sig_names}) {elapsed:.1f}s")
                else:
                    results[lid] = {
                        'lead': lead, 'classification': 'B1_social_verified',
                        'fb_email': fb_email, 'fb_name': fb_name, 'signals': sig_count,
                        'fb_url': fb_url, 'evidence_snippet': body_text[:300],
                    }
                    total_b1 += 1
                    print(f"    → B1: {fb_email[:3]}*** (signals={sig_count}) {elapsed:.1f}s")
            else:
                results[lid] = {
                    'lead': lead, 'classification': 'C_social_contact',
                    'fb_name': fb_name, 'fb_url': fb_url,
                }
                total_c += 1
                print(f"    → C (no email) {elapsed:.1f}s")

            limiter.after_page(fb_url)
            page.close()

        browser.close()

    # Phase 3: Write to DB
    print(f"\n--- Phase 3: Write Results ---")
    write_conn = sqlite3.connect(DB_PATH)
    write_conn.row_factory = sqlite3.Row
    now = datetime.now().isoformat()

    written_a = written_b1 = written_c = 0

    for lid, r in results.items():
        if r['classification'] == 'approved_manual_send_candidate':
            social_data = json.dumps({
                'social_email': r['fb_email'],
                'social_evidence_url': r['fb_url'],
                'social_evidence_snippet': r.get('evidence_snippet', '')[:300],
                'facebook_source_url': r['lead']['official_website'],
                'social_match_signals': r.get('signal_names', []),
                'classified_at': now,
            }, ensure_ascii=False)
            
            write_conn.execute("""
                UPDATE leads SET
                    email = ?, manual_found_email = ?,
                    manual_note = ?, manual_decision = 'pending',
                    status = 'approved_manual_send_candidate',
                    evidence_url = ?, evidence_snippet = ?,
                    evidence_method = 'official_facebook_page',
                    evidence_checked_at = ?, last_checked_at = ?,
                    domain_hash = ?
                WHERE id = ?
            """, (
                r['fb_email'], r['fb_email'],
                social_data,
                r['fb_url'], r['evidence_snippet'][:500],
                now, now,
                hashlib.sha256(r['fb_email'].split('@')[1].encode() if '@' in r['fb_email'] else b'').hexdigest(),
                lid,
            ))
            write_conn.commit()
            written_a += 1
            
        elif r['classification'] == 'B1_social_verified':
            social_data = json.dumps({
                'social_email': r['fb_email'],
                'social_evidence_url': r['fb_url'],
                'social_evidence_snippet': r.get('evidence_snippet', '')[:300],
                'facebook_source_url': r['lead']['official_website'],
                'classified_at': now,
            }, ensure_ascii=False)
            
            write_conn.execute("""
                UPDATE leads SET
                    manual_found_email = ?, manual_note = ?,
                    status = 'manual_review_needed',
                    evidence_checked_at = ?, last_checked_at = ?
                WHERE id = ?
            """, (r['fb_email'], social_data, now, now, lid))
            write_conn.commit()
            written_b1 += 1
            
        elif r['classification'] == 'C_social_contact':
            write_conn.execute("""
                UPDATE leads SET
                    contact_form_url = COALESCE(contact_form_url, ?),
                    status = 'contact_form_pool',
                    evidence_checked_at = ?, last_checked_at = ?
                WHERE id = ?
            """, (r.get('fb_url', ''), now, now, lid))
            write_conn.commit()
            written_c += 1

    write_conn.close()

    # Final pool counts
    final = count_pools(conn)
    conn.close()

    gap = max(0, 20 - final['total'])

    print()
    print("=" * 60)
    print("Facebook Fallback — Complete")
    print("=" * 60)
    print(f"States:            {', '.join(sorted(states))}")
    print(f"Cities:            {', '.join(sorted(cities)[:10])}")
    print(f"FB pages checked:  {len(fb_ready)}")
    print(f"FB emails found:   {total_a + total_b1}")
    print(f"  approved_manual: {total_a}")
    print(f"  B1:              {total_b1}")
    print(f"  C (no email):    {total_c}")
    print(f"  blocked/captcha: {total_blocked}")
    print(f"Written A:         {written_a}")
    print(f"Written B1:        {written_b1}")
    print(f"Written C:         {written_c}")
    print(f"-----------------------------")
    print(f"strict A0:         {final['strict_a0']}")
    print(f"manual candidate:  {final['manual_candidate']}")
    print(f"total sendable:    {final['total']}")
    print(f"Gap to 20:         {gap}")
    limiter_stats = limiter.stats()
    print(f"FB avg time/page:  {limiter_stats.get('total_wait_seconds',0)/max(limiter_stats.get('pages_processed',1),1):.1f}s wait")
    print(f"Email sent:        No")
    print("=" * 60)

    if gap > 0:
        print(f"\nStill {gap} short of 20. Next: New Lead Factory (TN/AR/KY collection).")


if __name__ == '__main__':
    main()
