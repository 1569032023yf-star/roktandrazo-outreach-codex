#!/usr/bin/env python3
"""
Browser Verifier — Real browser-based email extraction for B pool leads.
Uses Playwright to render JS-heavy sites (Shopify/Wix/Squarespace) and extract
visible email addresses that WebFetch misses.

Usage:
    python browser_verifier.py --test           # Test with 5 leads
    python browser_verifier.py --batch 20       # Verify 20 leads
    python browser_verifier.py --full           # All 216 B pool leads
"""

import sys, os, re, csv, json, time, argparse
from datetime import datetime
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(__file__))
from bd_db import get_db, _domain_hash, get_config, set_config

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("[ERROR] playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

OUT = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(OUT, exist_ok=True)

# Pages to check for email on each website
CONTACT_PAGES = [
    '/',
    '/contact',
    '/contact-us',
    '/pages/contact',
    '/pages/contact-us',
    '/about',
    '/about-us',
    '/pages/about',
    '/wholesale',
    '/vendor',
    '/buyer',
    '/faq',
    '/pages/faq',
]

def extract_emails_from_text(text: str) -> list[tuple[str, str]]:
    """Extract emails from text. Returns [(email, context), ...]"""
    results = []
    # Standard email
    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        email = m.group(0).lower()
        start = max(0, m.start() - 40)
        end = min(len(text), m.end() + 40)
        context = text[start:end].replace('\n', ' ')
        if not any(skip in email for skip in ['example.com', 'yourdomain', 'domain.com', 'youremail']):
            results.append((email, context))
    return results


def verify_website(browser, lead: dict, timeout: int = 15) -> dict:
    """Open a website with real browser and extract visible emails.
    Returns dict with verification results.
    """
    result = {
        'lead_id': lead['id'],
        'store_name': lead.get('store_name', ''),
        'website': lead.get('official_website', ''),
        'emails_found': [],
        'evidence_page': '',
        'evidence_snippet': '',
        'status': 'unverified',
        'pages_checked': [],
        'error': '',
    }

    base_url = (lead.get('official_website') or '').strip()
    if not base_url or not base_url.startswith('http'):
        result['status'] = 'dead'
        result['error'] = 'no_valid_url'
        return result

    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    page = context.new_page()

    try:
        all_emails = []
        checked_urls = []

        for rel_path in CONTACT_PAGES:
            full_url = urljoin(base_url, rel_path)
            if full_url in checked_urls:
                continue
            checked_urls.append(full_url)

            try:
                page.goto(full_url, wait_until='domcontentloaded', timeout=timeout * 1000)
                # Wait a bit for JS to render
                time.sleep(1)
            except PlaywrightTimeout:
                continue
            except Exception:
                continue

            # Get page content
            try:
                body_text = page.inner_text('body')
            except Exception:
                body_text = ''

            # Extract emails
            page_emails = extract_emails_from_text(body_text)
            for email, ctx in page_emails:
                # Filter: skip emails from our own domain or common non-store emails
                if any(skip in email for skip in ['roktandrazo', 'example.com', 'wixpress', 'sentry', 'shopify']):
                    continue
                all_emails.append((email, ctx, rel_path))

            if page_emails:
                result['evidence_page'] = rel_path
                result['evidence_snippet'] = page_emails[0][1][:150] if page_emails else ''
                break  # Found emails, stop checking more pages

        if all_emails:
            result['emails_found'] = list(set(e[0] for e in all_emails))
            result['status'] = 'email_found'
            result['evidence_snippet'] = all_emails[0][1][:150]
        else:
            # Check for contact form
            try:
                has_form = page.locator('form').count() > 0
                result['has_contact_form'] = has_form
                result['status'] = 'contact_form_only' if has_form else 'no_email_found'
            except Exception:
                result['status'] = 'no_email_found'

        result['pages_checked'] = len(checked_urls)

    except PlaywrightTimeout:
        result['status'] = 'timeout'
        result['error'] = f'Timeout after {timeout}s'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:200]
    finally:
        context.close()

    return result


def upgrade_to_a0(lead: dict, result: dict):
    """Upgrade a B pool lead to A0 based on browser verification."""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()

    email = result['emails_found'][0] if result['emails_found'] else ''
    if not email:
        conn.close()
        return False

    evidence_url = urljoin(result['website'], result.get('evidence_page', '/'))

    try:
        c.execute("""UPDATE leads SET
            confidence_score='A',
            email=?,
            email_type='business_email',
            email_source_type='official_page_visible',
            email_verified_on_official_site=1,
            evidence_url=?,
            last_checked_at=?,
            notes=COALESCE(notes,'') || ' | Browser verified: ' || ?
        WHERE id=? AND status='new' AND confidence_score='B'""", (
            email, evidence_url, now,
            result.get('evidence_snippet', '')[:200],
            lead['id']
        ))
        conn.commit()
        if c.rowcount != 1:
            print(f"  [SKIP upgrade] {lead['store_name']}: lead is no longer B/new")
            conn.close()
            return False
        print(f"  [A0 UPGRADE] {lead['store_name']:35s} | {email}")
        conn.close()
        return True
    except Exception as e:
        print(f"  [ERR upgrade] {lead['store_name']}: {e}")
        conn.close()
        return False


def persist_non_a0_result(lead: dict, result: dict):
    """Persist browser verification outcomes that should not enter the send pool."""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    status = result.get('status', '')
    note = f" | Browser verified non-A0: {status}"

    if status == 'contact_form_only':
        c.execute("""UPDATE leads SET
            status='contact_form_pool',
            confidence_score='C',
            last_checked_at=?,
            notes=COALESCE(notes,'') || ?
        WHERE id=? AND status='new' AND confidence_score='B'""", (now, note, lead['id']))
    elif status in ('dead', 'error', 'timeout'):
        c.execute("""UPDATE leads SET
            status='verification_failed',
            last_checked_at=?,
            notes=COALESCE(notes,'') || ?
        WHERE id=? AND status='new' AND confidence_score='B'""", (now, note, lead['id']))
    elif status == 'no_email_found':
        c.execute("""UPDATE leads SET
            status='manual_review_needed',
            last_checked_at=?,
            notes=COALESCE(notes,'') || ?
        WHERE id=? AND status='new' AND confidence_score='B'""", (now, note, lead['id']))

    conn.commit()
    conn.close()


def count_today_sent() -> int:
    conn = get_db()
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    sent = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE status='sent' AND date(sent_at)=?",
        (today,)
    ).fetchone()[0]
    conn.close()
    return sent


def record_recovery_check(upgraded: int, auto_recovery_send: bool):
    target = int(get_config('daily_run_target') or get_config('daily_send_target') or '20')
    sent = count_today_sent()
    gap = max(0, target - sent)
    set_config('daily_run_actual', str(sent))
    set_config('daily_run_gap', str(gap))

    if upgraded > 0 and gap > 0:
        set_config('recovery_pending', 'true')
        set_config('root_cause', 'browser_verifier_upgraded_a0')
        set_config('next_window_needed_count', str(gap))
        set_config('daily_run_status', 'recovery_pending')
        set_config('daily_send_status', 'recovery_pending')
        print(f"\n[RECOVERY CHECK] {upgraded} new A0 found; today gap is {gap}.")
        if auto_recovery_send:
            import subprocess
            cmd = [sys.executable, os.path.join(os.path.dirname(__file__), 'daily_operator_auto.py'),
                   '--live', '--target-count', str(target), '--stop-on-risk']
            print("[RECOVERY CHECK] Auto recovery send requested.")
            subprocess.run(cmd, check=False)
        else:
            print("[RECOVERY CHECK] State recorded. Use orchestrator recovery path to send.")
    elif gap == 0:
        set_config('recovery_pending', 'false')
        set_config('daily_run_status', 'completed')
        set_config('daily_send_status', 'completed')


def run_batch(leads: list[dict], batch_size: int = 10, timeout: int = 15):
    """Run browser verification on a batch of leads."""
    results = []
    upgraded = 0
    contact_form = 0
    dead = 0
    no_email = 0

    total = min(batch_size, len(leads))
    print(f"\n[VERIFY] Browser verification starting: {total} leads, timeout={timeout}s")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for i, lead in enumerate(leads[:total]):
            store = lead.get('store_name', '?')
            print(f"  [{i+1}/{total}] {store[:40]}...", end=' ', flush=True)
            result = verify_website(browser, lead, timeout)
            results.append(result)

            status = result['status']
            if status == 'email_found':
                if upgrade_to_a0(lead, result):
                    upgraded += 1
                    print(f"FOUND: {result['emails_found'][:3]}")
            elif status in ('dead', 'error', 'timeout'):
                dead += 1
                persist_non_a0_result(lead, result)
                print(f"DEAD: {result.get('error','')[:50]}")
            elif status == 'contact_form_only':
                contact_form += 1
                persist_non_a0_result(lead, result)
                print("CONTACT FORM")
            else:
                no_email += 1
                persist_non_a0_result(lead, result)
                print("NO EMAIL")

        browser.close()

    print(f"\n[SUMMARY] Upgraded: {upgraded} | Contact form: {contact_form} | Dead: {dead} | No email: {no_email}")
    return results, upgraded, contact_form, dead, no_email


def generate_reports(all_results: list[dict], upgraded: int):
    """Generate B2, D1, and summary CSVs."""
    now_str = datetime.now().strftime('%Y%m%d_%H%M')

    # B2: high-value sites that are live but no email found
    b2_path = os.path.join(OUT, f'b2_browser_manual_{now_str}.csv')
    d1_path = os.path.join(OUT, f'd1_risk_guess_{now_str}.csv')

    b2_items = [r for r in all_results if r['status'] in ('no_email_found', 'contact_form_only')]
    d1_items = [r for r in all_results if r['status'] == 'email_found' and len(r.get('emails_found', [])) > 0]

    with open(b2_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['store_name', 'website', 'status', 'pages_checked', 'manual_decision', 'recommended_action'])
        for r in b2_items[:30]:
            w.writerow([r['store_name'], r['website'], r['status'], r['pages_checked'], '', 'verify_manually'])

    print(f"\n[FILES]")
    print(f"  B2 manual review: {b2_path} ({len(b2_items[:30])} rows)")
    print(f"  A0 upgraded: {upgraded}")
    print(f"  Dead/error: {sum(1 for r in all_results if r['status'] in ('dead','error','timeout'))}")


def main():
    parser = argparse.ArgumentParser(description='Browser Verifier')
    parser.add_argument('--test', action='store_true', help='Test with 5 leads')
    parser.add_argument('--batch', type=int, default=0, help='Batch size (default: all)')
    parser.add_argument('--full', action='store_true', help='Verify all B pool leads')
    parser.add_argument('--timeout', type=int, default=15, help='Page load timeout in seconds')
    parser.add_argument('--auto-recovery-send', action='store_true',
                        help='After A0 upgrades, call daily_operator_auto.py live recovery path')
    args = parser.parse_args()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE status='new' AND confidence_score='B' AND official_website IS NOT NULL AND official_website != '' ORDER BY store_name")
    b_leads = [dict(r) for r in c.fetchall()]
    conn.close()

    batch_size = args.batch or len(b_leads)
    if args.test:
        batch_size = min(5, len(b_leads))

    print(f"[INIT] B pool: {len(b_leads)} leads, verifying {batch_size}")

    results, upgraded, cf, dead, no_email = run_batch(b_leads, batch_size=batch_size, timeout=args.timeout)
    generate_reports(results, upgraded)
    record_recovery_check(upgraded, args.auto_recovery_send)


if __name__ == '__main__':
    main()
