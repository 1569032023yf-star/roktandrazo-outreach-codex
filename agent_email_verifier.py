"""
Email Verification Agent V2 — 邮箱真实性验证流水线
===============================================
从现有线索中逐个打开官网，验证邮箱是否真实出现在官网页面上。
使用 urllib + SSL 容错 + 多页面扫描。

策略：
1. 先扫描 homepage, /contact, /about, /wholesale
2. 检查 expected_email 是否在页面上
3. 如果在 -> verified A
4. 如果不在但找到同域其他邮箱 -> 修正邮箱
5. 如果完全找不到任何邮箱 -> guessed_email -> 降 B
"""

import sqlite3, sys, os, re, time, json, ssl, urllib.request
from datetime import datetime

# Note: sys.stdout encoding is handled by the caller (Bash tool or runner script)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'bd_leads.db')

# SSL context for sites with cert issues
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

SKIP_DOMAINS = {'example.com', 'domain.com', 'yoursite.com', 'yourdomain.com',
                'shopify.com', 'myshopify.com', 'schema.org', 'google.com',
                'facebook.com', 'twitter.com', 'instagram.com'}


def fetch(url, timeout=10):
    """Fetch a URL and return HTML text"""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            html = resp.read().decode('utf-8', errors='replace')
            return {'status': 'ok', 'html': html, 'url': resp.geturl()}
    except urllib.error.HTTPError as e:
        return {'status': 'http_error', 'code': e.code, 'url': url}
    except urllib.error.URLError as e:
        return {'status': 'url_error', 'error': str(e.reason)[:100], 'url': url}
    except Exception as e:
        return {'status': 'error', 'error': str(e)[:100], 'url': url}


def extract_emails(html, domain_hint=''):
    """从 HTML 中提取所有真实邮箱地址"""
    if not html:
        return []
    # Find all email patterns
    raw_emails = set(re.findall(r'[\w.+-]+@[\w.-]+\.[\w]{2,}', html))
    mailto = set(re.findall(r'mailto:([\w.+-]+@[\w.-]+\.[\w]{2,})', html))
    
    # Normalize domain hint
    dh = domain_hint.lower().replace('https://','').replace('http://','').replace('www.','')
    dh_base = dh.split('.')[0] if dh else ''
    
    results = []
    seen = set()
    for email in raw_emails | mailto:
        e = email.lower().strip()
        if e in seen:
            continue
        seen.add(e)
        
        # Skip junk
        parts = e.split('@')
        if len(parts) != 2:
            continue
        _, edomain = parts
        if edomain in SKIP_DOMAINS:
            continue
        if any(s in edomain for s in SKIP_DOMAINS):
            continue
        
        is_mailto = e in mailto
        domain_match = dh and (dh in edomain or edomain in dh or dh_base in edomain)
        
        results.append({
            'email': e,
            'domain_matches': domain_match,
            'is_mailto': is_mailto
        })
    
    return results


def scan_website(website, expected_email, store_name):
    """扫描官网查找邮箱"""
    if not website:
        return {'status': 'no_website'}
    
    url = website.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    # Extract domain for matching
    m = re.match(r'https?://([^/]+)', url)
    domain = m.group(1) if m else ''
    
    expected = expected_email.lower().strip() if expected_email else ''
    
    # Pages to scan
    pages = [
        url,
        url.rstrip('/') + '/contact',
        url.rstrip('/') + '/contact-us',
        url.rstrip('/') + '/about',
        url.rstrip('/') + '/about-us',
        url.rstrip('/') + '/wholesale',
        url.rstrip('/') + '/vendors',
        url.rstrip('/') + '/pages/contact',
        url.rstrip('/') + '/pages/about',
        url.rstrip('/') + '/pages/contact-us',
    ]
    
    all_emails = []  # list of dicts
    seen_emails = set()
    
    for page in pages:
        result = fetch(page)
        if result['status'] != 'ok':
            continue
        
        html = result['html']
        emails = extract_emails(html, domain)
        
        for e in emails:
            if e['email'] not in seen_emails:
                seen_emails.add(e['email'])
                all_emails.append(e)
        
        # Check if expected email is found
        if expected:
            for e in emails:
                if e['email'] == expected:
                    source_type = 'official_mailto' if e['is_mailto'] else 'official_page_visible'
                    return {
                        'status': 'confirmed',
                        'found_email': expected,
                        'source_type': source_type,
                        'verified': True,
                        'page_url': result['url'],
                        'all_emails': all_emails
                    }
    
    # Expected email NOT found
    # Check if we found any domain-matched email
    domain_matched = [e for e in all_emails if e['domain_matches']]
    other = [e for e in all_emails if not e['domain_matches'] and e['domain_matches'] is not False]
    
    if domain_matched:
        # Found different email on same domain — better than nothing
        best = domain_matched[0]
        return {
            'status': 'found_different',
            'expected': expected,
            'found_email': best['email'],
            'source_type': 'official_page_visible',
            'verified': True,
            'page_url': '',
            'all_emails': all_emails
        }
    elif other:
        # Found email on different domain (e.g., gmail) — questionable
        best = other[0]
        return {
            'status': 'found_other_domain',
            'expected': expected,
            'found_email': best['email'],
            'source_type': 'other',
            'verified': True,
            'page_url': '',
            'all_emails': all_emails
        }
    else:
        # No email found at all
        return {
            'status': 'not_found',
            'expected': expected,
            'source_type': 'guessed_email',
            'verified': False,
            'page_url': '',
            'all_emails': all_emails
        }


def verify_batch(lead_ids):
    """验证一批线索"""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    placeholders = ','.join('?' * len(lead_ids))
    cur.execute(f'SELECT * FROM leads WHERE id IN ({placeholders}) ORDER BY store_name', lead_ids)
    leads = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    results = {
        'confirmed': [],       # ✅ Email confirmed on site
        'corrected': [],       # ✅ Found different (better) email on site
        'other_email': [],     # ⚠️ Found non-domain email (gmail etc)
        'guessed': [],         # [GUESS] No email found — was guessed
        'no_site': [],         # ❌ No website
        'error': [],           # [ERR] Site error
    }
    
    for i, lead in enumerate(leads):
        store = lead['store_name']
        website = lead.get('official_website', '')
        expected = lead.get('email', '')
        
        print(f'\n[{i+1}/{len(leads)}] {store}')
        print(f'    → Website: {website}')
        print(f'    → Expected: {expected}')
        
        if not website:
            results['no_site'].append(lead)
            print(f'    [NO SITE] No website')
            continue
        
        scan = scan_website(website, expected, store)
        
        if scan['status'] == 'confirmed':
            lead['email_source_type'] = scan['source_type']
            lead['email_verified_on_official_site'] = 1
            lead['evidence_url'] = scan.get('page_url', website)
            results['confirmed'].append(lead)
            print(f'    [OK] CONFIRMED: {expected} found on site')
            if scan.get('all_emails'):
                others = ', '.join([e['email'] for e in scan['all_emails'][:3] if e['email'] != expected])
                if others:
                    print(f'    Other emails on site: {others}')
        
        elif scan['status'] == 'found_different':
            lead['email'] = scan['found_email']
            lead['email_source_type'] = scan['source_type']
            lead['email_verified_on_official_site'] = 1
            results['corrected'].append(lead)
            print(f'    [OK] CORRECTED: expected={expected} -> found={scan["found_email"]}')
        
        elif scan['status'] == 'found_other_domain':
            lead['email'] = scan['found_email']
            lead['email_source_type'] = scan['source_type']
            lead['email_verified_on_official_site'] = 1
            results['other_email'].append(lead)
            print(f'    [WARN] OTHER EMAIL: expected={expected} -> found={scan["found_email"]} (different domain)')
        
        elif scan['status'] == 'not_found':
            results['guessed'].append(lead)
            print(f'    [GUESS] {expected} not found anywhere on site')
            if scan.get('all_emails'):
                all_e = ', '.join([e['email'] for e in scan['all_emails'][:5]])
                if all_e:
                    print(f'    Other emails on site: {all_e}')
        
        else:
            results['error'].append(lead)
            print(f'    [ERROR] {scan.get("status","?")}')
    
    # Save to DB
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    for lead in results['confirmed']:
        cur.execute('''UPDATE leads SET 
            email_source_type=?, email_verified_on_official_site=1,
            evidence_url=?,
            confidence_score='A',
            notes=COALESCE(notes||' | ','')||'VERIFIED: email confirmed on '||?
            WHERE id=?''',
            (lead['email_source_type'], lead.get('evidence_url',''),
             lead.get('evidence_url',''), lead['id']))
    
    for lead in results['corrected']:
        cur.execute('''UPDATE leads SET 
            email=?, email_source_type=?, email_verified_on_official_site=1,
            confidence_score='A',
            notes=COALESCE(notes||' | ','')||'VERIFIED: email corrected from guessed to '||?
            WHERE id=?''',
            (lead['email'], lead['email_source_type'], lead['email'], lead['id']))
    
    for lead in results['other_email']:
        cur.execute('''UPDATE leads SET 
            email=?, email_source_type=?, email_verified_on_official_site=1,
            confidence_score='B',
            notes=COALESCE(notes||' | ','')||'VERIFIED: found non-domain email '||?
            WHERE id=?''',
            (lead['email'], lead['email_source_type'], lead['email'], lead['id']))
    
    for lead in results['guessed']:
        guessed_email = lead.get('email', '') or ''
        note_text = 'GUESSED: ' + guessed_email + ' not on site'
        cur.execute('''UPDATE leads SET 
            email_source_type='guessed_email', email_verified_on_official_site=0,
            confidence_score='B',
            notes=COALESCE(notes||' | ','')||?
            WHERE id=?''',
            (note_text, lead['id']))
    
    conn.commit()
    conn.close()
    
    return results


def generate_report(results):
    total = sum(len(v) for v in results.values())
    confirmed = len(results['confirmed'])
    corrected = len(results['corrected'])
    other = len(results['other_email'])
    guessed = len(results['guessed'])
    no_site = len(results['no_site'])
    errors = len(results['error'])
    
    M = '='
    print(f'{M*70}')
    print('Email Verification Report')
    print(f'{M*70}')
    print(f'  Total: {total}')
    print(f'  [OK] verified A (email confirmed on site): {confirmed}')
    print(f'  [OK] email corrected (found real email on site): {corrected}')
    print(f'  [WARN] non-domain email (downgraded to B): {other}')
    print(f'  [GUESS] guessed email (downgraded to B): {guessed}')
    print(f'  [NO SITE] no website (downgraded to C): {no_site}')
    print(f'  [ERROR] site errors: {errors}')
    print(f'  => Available verified A: {confirmed + corrected}')
    
    if results['confirmed']:
        print(f'\n[OK] Verified A list:')
        for i, r in enumerate(results['confirmed'], 1):
            print(f'  {i:2d}. {r["store_name"]:35s} | {r["email"]:30s} | {r.get("store_type","")}')
    
    if results['corrected']:
        print(f'\n[OK] Corrected emails:')
        for i, r in enumerate(results['corrected'], 1):
            print(f'  {i:2d}. {r["store_name"]:35s} | {r["email"]:30s}')
    
    if results['guessed']:
        print(f'\n[GUESS] Guessed emails:')
        for i, r in enumerate(results['guessed'], 1):
            print(f'  {i:2d}. {r["store_name"]:35s} | {r["email"]:30s}')
    
    return {
        'total': total, 'confirmed': confirmed, 'corrected': corrected,
        'guessed': guessed, 'no_site': no_site, 'errors': errors
    }


def select_candidates(limit=100, grade='A'):
    """选择需要验证的候选"""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    if grade == 'A':
        cur.execute('''SELECT id FROM leads 
        WHERE confidence_score="A" AND status="new" AND email IS NOT NULL AND email != ""
        AND official_website IS NOT NULL AND official_website != ""
        AND (email_source_type IS NULL OR email_source_type="")
        ORDER BY store_name LIMIT ?''', (limit,))
    elif grade == 'B':
        cur.execute('''SELECT id FROM leads 
        WHERE confidence_score="B" AND status="new" AND email IS NOT NULL AND email != ""
        AND official_website IS NOT NULL AND official_website != ""
        ORDER BY store_name LIMIT ?''', (limit,))
    else:
        cur.execute('''SELECT id FROM leads 
        WHERE status="new" AND email IS NOT NULL AND email != ""
        AND official_website IS NOT NULL AND official_website != ""
        AND (email_source_type IS NULL OR email_source_type="")
        ORDER BY store_name LIMIT ?''', (limit,))
    
    ids = [r['id'] for r in cur.fetchall()]
    conn.close()
    return ids


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Email Verification Agent')
    parser.add_argument('--grade', default='A', choices=['A', 'B'], help='Grade of leads to verify')
    parser.add_argument('--limit', type=int, default=100, help='Max leads to verify')
    args = parser.parse_args()
    
    print(f'Email Verification Agent V2 (grade={args.grade}, limit={args.limit})')
    print(f'{"="*60}')
    
    candidate_ids = select_candidates(args.limit, args.grade)
    print(f'候选: {len(candidate_ids)} 条 ({args.grade} 级有官网)')
    
    if not candidate_ids:
        print('无候选！')
        return
    
    all_results = {k: [] for k in ['confirmed','corrected','other_email','guessed','no_site','error']}
    
    # Process in batches of 10 (to avoid rate limiting)
    BATCH_SIZE = 10
    for batch_start in range(0, len(candidate_ids), BATCH_SIZE):
        batch = candidate_ids[batch_start:batch_start + BATCH_SIZE]
        label = f'Batch {batch_start//BATCH_SIZE + 1}/{(len(candidate_ids)-1)//BATCH_SIZE + 1}'
        
        print(f'\n{"="*60}')
        print(f'{label} ({len(batch)} leads)')
        print(f'{"="*60}')
        
        results = verify_batch(batch)
        for k in all_results:
            all_results[k].extend(results[k])
        
        if batch_start + BATCH_SIZE < len(candidate_ids):
            print(f'\n[sleep] 3 sec...')
            time.sleep(3)
    
    generate_report(all_results)
    
    total_verified = len(all_results['confirmed']) + len(all_results['corrected'])
    print(f'\n[RESULT] Verification summary:')
    print(f'  Newly verified A: {total_verified}')
    
    # Count total verified A in DB
    import sqlite3
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''SELECT COUNT(*) FROM leads WHERE status="new" AND confidence_score="A" 
    AND email_verified_on_official_site=1
    AND email_source_type IN ("official_page_visible","official_mailto")''')
    db_count = cur.fetchone()[0]
    conn.close()
    print(f'  Total verified A stock (DB): {db_count}')
    print(f'  Target 30: {"REACHED!" if db_count >= 30 else f"need {30-db_count} more"}')
    print(f'  Target 100: {"REACHED!" if db_count >= 100 else f"need {100-db_count} more"}')


if __name__ == '__main__':
    main()
