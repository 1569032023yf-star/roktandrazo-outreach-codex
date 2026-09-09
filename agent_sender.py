"""
Sender Agent — Send from verified A pool only. NO real sending in test mode.
Fixed: robust dedup (status, send_log, suppression, domain, store_name)
"""
import sqlite3, sys, io, os, dns.resolver
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass
sys.path.insert(0, os.path.dirname(__file__))
from bd_template import get_email_for_lead

DB = 'data/bd_leads.db'

def get_config(key):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT value FROM system_config WHERE key=?", (key,))
    r = cur.fetchone()
    conn.close()
    return r[0] if r else None

def domain_of(email):
    return email.split('@')[1].lower() if '@' in email else ''

def check_mx_provider(domain):
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        mx_str = ' '.join([str(x.exchange).lower() for x in answers])
        if 'outlook.com' in mx_str or 'protection.outlook.com' in mx_str or 'microsoft.com' in mx_str:
            return 'exchange_online'
        elif 'google.com' in mx_str or 'googlemail.com' in mx_str:
            return 'google'
        else:
            return 'other'
    except:
        return 'no_mx'

def select_leads_for_send(cap=5, dry_run=True):
    if get_config('send_pause') == 'true' and not dry_run:
        pr = get_config('pause_reason')
        print(f'BLOCKED: send_pause=true ({pr})')
        return []
    
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get all verified A leads with proper source type
    cur.execute("""
        SELECT * FROM leads WHERE
        confidence_score='A'
        AND email IS NOT NULL AND email != ''
        AND email_verified_on_official_site=1
        AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page')
        ORDER BY store_name
    """)
    all_candidates = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    # Load reference data for exclusion
    conn2 = sqlite3.connect(DB)
    cur2 = conn2.cursor()
    cur2.execute("SELECT email FROM suppression_list")
    suppressed_emails = set(r[0].lower() for r in cur2.fetchall())
    
    cur2.execute("SELECT DISTINCT email FROM send_log WHERE status='sent'")
    sent_emails = set(r[0].lower() for r in cur2.fetchall())
    
    cur2.execute("SELECT DISTINCT store_name FROM leads WHERE status='sent'")
    sent_store_names = set(r[0].lower() for r in cur2.fetchall())
    
    cur2.execute("SELECT DISTINCT official_website FROM leads WHERE status='sent'")
    sent_domains = set()
    for r in cur2.fetchall():
        if r[0]:
            d = r[0].lower().replace('https://','').replace('http://','').replace('www.','').split('/')[0]
            sent_domains.add(d)
    
    excluded_statuses = {'bounced', 'delivery_issue', 'unsubscribed', 'do_not_contact', 'bounce_review'}
    cur2.execute("SELECT email FROM leads WHERE status IN ('bounced','delivery_issue','unsubscribed','do_not_contact')")
    excluded_emails = set(r[0].lower() for r in cur2.fetchall() if r[0])
    conn2.close()
    
    filtered = []
    skipped = []
    
    for lead in all_candidates:
        email = lead['email'].lower()
        store = lead['store_name']
        domain = domain_of(email)
        status = lead.get('status', '')
        
        reasons = []
        
        # 1. Status check
        if status == 'sent':
            reasons.append('status=sent')
        elif status in excluded_statuses:
            reasons.append(f'status={status}')
        
        # 2. Suppression check
        if email in suppressed_emails:
            reasons.append('in suppression list')
        if domain in suppressed_emails:
            reasons.append(f'domain@{domain} in suppression')
        
        # 3. Send_log check
        if email in sent_emails:
            reasons.append('email in send_log (sent)')
        
        # 4. Store name already sent
        if store.lower() in sent_store_names:
            reasons.append(f'store \"{store}\" already sent')
        
        # 5. Domain already sent
        ws = lead.get('official_website', '')
        if ws:
            wd = ws.lower().replace('https://','').replace('http://','').replace('www.','').split('/')[0]
            if wd in sent_domains:
                reasons.append(f'domain {wd} already sent')
        
        if reasons:
            skipped.append((store, email, reasons))
            continue
        
        # 6. MX provider check
        provider = check_mx_provider(domain)
        lead['mx_provider'] = provider
        
        if provider == 'exchange_online':
            skipped.append((store, email, ['exchange_online MX']))
            continue
        if provider == 'no_mx':
            skipped.append((store, email, ['no MX']))
            continue
        
        filtered.append(lead)
    
    if dry_run:
        for store, email, reasons in skipped:
            print(f'  [SKIP] {store:35s} | {email:30s} | {"; ".join(reasons)}')
    
    return filtered

def dry_run_send(cap=5):
    print(f'[DRY-RUN] Sender Agent V2 — cap={cap}')
    sp = get_config('send_pause')
    print(f'  send_pause={sp}')
    print()
    
    leads = select_leads_for_send(cap=cap, dry_run=True)
    
    if not leads:
        print('  No leads available for sending.')
        return
    
    selected = leads[:cap]
    print(f'  Selected {len(selected)}/{len(leads)} leads:')
    print()
    
    for i, lead in enumerate(selected, 1):
        email_data = get_email_for_lead(lead)
        sname = lead['store_name']
        semail = lead['email']
        lead_status = lead.get('status', '?')
        mprov = lead['mx_provider']
        stype = lead.get('email_source_type', '?')
        everif = lead.get('email_verified_on_official_site', '?')
        sevid = lead.get('evidence_url', '')
        d = domain_of(semail)
        
        print(f'  [{i}] {sname}')
        print(f'      Email: {semail}')
        print(f'      Status: {lead_status}')
        print(f'      Email Source: {stype} (verified={everif})')
        print(f'      Evidence: {sevid}')
        print(f'      MX Provider: {mprov}')
        print(f'      Domain: {d}')
        print(f'      Previously Sent: NO')
        print(f'      In Suppression: NO')
        print(f'      Why: verified A + valid MX + not Exchange + not sent + not suppressed')
        subj = email_data['subject']
        print(f'      Subject: {subj}')
        print()
    
    print(f'[DRY-RUN COMPLETE]')

if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        dry_run_send(cap=5)
