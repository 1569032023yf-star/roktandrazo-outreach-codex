"""
Website Reachability Audit — B Pool
Checks all B-grade leads' websites, categorizes into B1-B4 and C_invalid
"""
import sqlite3, ssl, urllib.request, urllib.error, socket, re, csv, os, sys, time

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'bd_leads.db')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(OUT, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all B-grade leads with website + email
sent_emails = set(r['email'].lower() for r in cur.execute("SELECT email FROM send_log WHERE status='sent'").fetchall())
supp_emails = set(r['email'].lower() for r in cur.execute("SELECT email FROM suppression_list").fetchall())

cur.execute('''SELECT id, store_name, email, store_type, city, state, official_website,
    evidence_url, contact_form_url, product_fit, fit_reason, notes
FROM leads WHERE status="new" AND confidence_score="B"
AND email IS NOT NULL AND email != ""
AND official_website IS NOT NULL AND official_website != ""
ORDER BY store_name''')
b_raw = [dict(r) for r in cur.fetchall()]
b_valid = [l for l in b_raw if l['email'].lower() not in sent_emails and l['email'].lower() not in supp_emails]

conn.close()

print(f'B pool audit candidates: {len(b_valid)}')
print()

# SSL context
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

results = {
    'b1_contact_form': [],   # Reachable, has contact form, no email
    'b2_guess_candidates': [], # Reachable, store matches, can guess email
    'b3_unreachable': [],     # 403/404/timeout/SSL/DNS errors
    'b4_mismatch': [],        # Site doesn't match store
    'c_invalid': [],          # Domain parking/expired/pure online/closed
}

error_counts = {'200':0, '301/302':0, '403':0, '404':0, 'timeout':0, 'ssl_error':0, 'dns_error':0, 'other':0}
has_contact = 0
has_visible_email = 0
shopify_count = 0

for i, lead in enumerate(b_valid):
    store = lead['store_name']
    url = (lead['official_website'] or '').strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    # Try multiple URL variants
    urls_to_try = [url]
    if url.startswith('https://'):
        urls_to_try.append(url.replace('https://', 'http://'))
    if url.endswith('/'):
        urls_to_try.append(url.rstrip('/'))
    # Also try www if not already
    host = re.sub(r'https?://', '', url).split('/')[0]
    if not host.startswith('www.'):
        urls_to_try.append(url.replace(host, 'www.' + host))
    
    reached = False
    final_url = ''
    status_code = 0
    html = ''
    error_type = ''
    
    for test_url in urls_to_try[:3]:  # Max 3 variants
        try:
            req = urllib.request.Request(test_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            html = resp.read().decode('utf-8', errors='replace')[:20000]
            status_code = resp.status
            final_url = resp.geturl()
            reached = True
            break
        except urllib.error.HTTPError as e:
            status_code = e.code
            if e.code in (403, 404):
                final_url = test_url
                error_type = str(e.code)
                try:
                    body = e.read().decode('utf-8', errors='replace')[:5000]
                    html = body
                except:
                    pass
                break  # Don't retry on 403/404
            # 301/302 handled by urlopen automatically
        except urllib.error.URLError as e:
            err_str = str(e.reason).lower()
            if 'name' in err_str or 'resolve' in err_str:
                error_type = 'dns_error'
            elif 'timed out' in err_str:
                error_type = 'timeout'
            elif 'certificate' in err_str or 'ssl' in err_str:
                error_type = 'ssl_error'
            elif 'connection' in err_str or 'refused' in err_str:
                error_type = 'connection_refused'
            else:
                error_type = 'other_urlerror'
        except socket.timeout:
            error_type = 'timeout'
        except Exception as e:
            error_type = 'other: ' + str(e)[:30]
    
    # Classify
    title = ''
    title_match = False
    is_shopify = False
    has_contact_page = False
    visible_emails = []
    
    if reached and html:
        # Extract title
        t_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if t_match:
            title = t_match.group(1).strip()
            # Check if store name appears in title
            store_words = store.lower().split()[:3]
            title_lower = title.lower()
            title_match = any(w in title_lower for w in store_words if len(w) > 2)
        
        # Shopify detection
        is_shopify = 'shopify' in html.lower() or 'myshopify' in html.lower()
        
        # Contact page detection
        has_contact_page = '/contact' in html.lower() or 'contact us' in html.lower() or 'mailto:' in html.lower()
        
        # Visible emails (not from guesses, actual site content)
        raw_emails = set(re.findall(r'[\w.+-]+@[\w.-]+\.\w{2,}', html))
        skip_doms = {'example.com', 'domain.com', 'yoursite.com', 'shopify.com', 'myshopify.com', 'schema.org'}
        visible_emails = [e for e in raw_emails if not any(s in e.lower() for s in skip_doms)]
        
        if visible_emails:
            has_visible_email += 1
        if has_contact_page:
            has_contact += 1
        if is_shopify:
            shopify_count += 1
    
    if not reached:
        # B3: Unreachable
        results['b3_unreachable'].append(lead)
        if error_type == '403': error_counts['403'] += 1
        elif error_type == '404': error_counts['404'] += 1
        elif error_type == 'timeout': error_counts['timeout'] += 1
        elif error_type == 'ssl_error': error_counts['ssl_error'] += 1
        elif error_type == 'dns_error': error_counts['dns_error'] += 1
        else: error_counts['other'] += 1
    
    elif not title_match and not is_shopify:
        # B4: Possible mismatch
        results['b4_mismatch'].append(lead)
    
    elif is_shopify:
        # B1 or B2 depending on what we found
        if visible_emails:
            lead['found_emails'] = visible_emails[:3]
            results['b2_guess_candidates'].append(lead)
        else:
            results['b1_contact_form'].append(lead)
    
    else:
        # Reachable, title matches or generic
        if visible_emails:
            lead['found_emails'] = visible_emails[:3]
            results['b2_guess_candidates'].append(lead)
        else:
            results['b1_contact_form'].append(lead)
    
    # Progress
    if (i+1) % 30 == 0:
        print(f'  Progress: {i+1}/{len(b_valid)}')
        time.sleep(1)

print(f'\nProgress: {len(b_valid)}/{len(b_valid)}')
print()

reachable = len(b_valid) - len(results['b3_unreachable'])
unreachable = len(results['b3_unreachable'])
b4_count = len(results['b4_mismatch'])
b1_count = len(results['b1_contact_form'])
b2_count = len(results['b2_guess_candidates'])

# Generate report
print('=' * 70)
print('WEBSITE REACHABILITY AUDIT REPORT')
print('=' * 70)
print(f'\n  B pool total:           {len(b_valid)}')
print(f'  Reachable:              {reachable}')
print(f'  Unreachable (B3):       {unreachable}')
print(f'  Site mismatch (B4):     {b4_count}')
print(f'  Contact form (B1):      {b1_count}')
print(f'  Guess candidates (B2):  {b2_count}')
print()
print('  Error breakdown:')
for k, v in error_counts.items():
    if v > 0:
        print(f'    {k}: {v}')
print()
print(f'  Has contact page:       {has_contact}')
print(f'  Has visible email:      {has_visible_email}')
print(f'  Shopify stores:         {shopify_count}')

# Generate B2 CSV for manual review
csv_path_b2 = os.path.join(OUT, 'b2_guess_candidates.csv')
with open(csv_path_b2, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['id','store_name','store_type','city','state','website','domain',
                'guessed_email','product_fit','recommended_action','notes'])
    for lead in results['b2_guess_candidates']:
        email = lead['email']
        domain = email.split('@')[1] if '@' in email else ''
        w.writerow([lead['id'], lead['store_name'], lead.get('store_type',''),
                    lead.get('city',''), lead.get('state',''), lead.get('official_website',''),
                    domain, email, lead.get('product_fit',''), 'review', ''])

# Generate B3 unreachable CSV
csv_path_b3 = os.path.join(OUT, 'b3_unreachable.csv')
with open(csv_path_b3, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['id','store_name','email','website','store_type','action_needed'])
    for lead in results['b3_unreachable']:
        w.writerow([lead['id'], lead['store_name'], lead['email'],
                    lead.get('official_website',''), lead.get('store_type',''),
                    're-check website manually'])

b2_len = len(results['b2_guess_candidates'])
b3_len = len(results['b3_unreachable'])
print(f'\n  B2 CSV: {csv_path_b2} ({b2_len} records)')
print(f'  B3 CSV: {csv_path_b3} ({b3_len} records)')

conn.close()
print()
print('DONE')