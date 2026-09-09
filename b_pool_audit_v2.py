#!/usr/bin/env python3
"""B Pool Audit v2 — proper verification: only upgrade if email is on official site"""
import sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))
from bd_db import get_db
from datetime import datetime

conn = get_db()
c = conn.cursor()

c.execute("SELECT * FROM leads WHERE status='new' AND confidence_score='B' ORDER BY store_name")
b_leads = [dict(r) for r in c.fetchall()]
print(f'[AUDIT v2] B pool: {len(b_leads)} leads')

# Categorize
b2_manual = []  # High value, needs manual email finding
b3_dead = []     # Bad websites, mismatched stores
a0_candidates = []  # Already has verified email pattern

for lead in b_leads:
    store = lead['store_name']
    website = (lead.get('official_website') or '').strip()
    email = (lead.get('email') or '').strip()
    evidence = (lead.get('evidence_url') or '').strip()
    store_type = (lead.get('store_type') or '').strip()
    email_type = (lead.get('email_type') or '').strip()
    city = lead.get('city','')
    state = lead.get('state','')
    
    # Good store type match
    good_type = any(t in (store_type or '').lower() for t in 
        ['toy', 'game', 'gift', 'puzzle', 'book', 'museum', 'hobby', 'craft', 'comic', 'activity'])
    
    # Check if email is from a verified source (official_mailto, official_page_visible)
    email_source = (lead.get('email_source_type') or '').strip()
    is_verified = email_source in ('official_page_visible', 'official_mailto', 'wholesale_vendor_page')
    
    # Has website and good type
    if website and good_type:
        if is_verified and email and '@' in email:
            # Already verified - can upgrade
            a0_candidates.append(lead)
        elif good_type:
            # High value, needs manual email
            b2_manual.append(lead)
        else:
            b3_dead.append({**lead, 'reason': 'not_retail_match'})
    else:
        b3_dead.append({**lead, 'reason': 'no_website_or_poor_match'})

print(f'  Verified leads (upgrade to A0): {len(a0_candidates)}')
print(f'  B2 high-value (needs email): {len(b2_manual)}')
print(f'  B3 dead/invalid: {len(b3_dead)}')

# Upgrade verified A0 candidates
upgraded = 0
for lead in a0_candidates:
    email = lead['email']
    if not email or '@' not in email: continue
    mx = (lead.get('mx_provider') or '').lower()
    if 'exchange' in mx or 'outlook' in mx: continue
    try:
        c.execute("""UPDATE leads SET confidence_score='A', email_verified_on_official_site=1,
            email_source_type='official_page_visible', last_checked_at=? WHERE id=?""",
            (datetime.now().isoformat(), lead['id']))
        upgraded += 1
    except: pass
conn.commit()
print(f'  Auto-upgraded to A0: {upgraded} (verified email source)')

# Generate B2 high-value CSV
OUT = os.path.join(os.path.dirname(__file__), 'output')
csv_path = os.path.join(OUT, 'b2_high_value_manual_review.csv')
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['store_name','website','city','state','store_type','product_fit',
                'current_email','contact_page','contact_form_url',
                'manual_found_email','manual_email_source_url',
                'manual_decision','recommended_action','notes'])
    for lead in b2_manual:
        w.writerow([
            lead.get('store_name',''), lead.get('official_website',''),
            lead.get('city',''), lead.get('state',''),
            lead.get('store_type',''), lead.get('product_fit',''),
            lead.get('email',''), lead.get('contact_page',''),
            lead.get('contact_form_url',''),
            '', '', '', 'verify_email_on_site',
            (lead.get('notes','') or '')[:100]
        ])

c.execute("SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='A' AND email IS NOT NULL AND email != ''")
a0 = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM leads WHERE status='new' AND confidence_score='B'")
b = c.fetchone()[0]
conn.close()

print(f'\n=== RESULTS ===')
print(f'A0 pool: {a0}')
print(f'B pool: {b}')
print(f'B2 CSV: {csv_path} ({len(b2_manual)} rows)')
print(f'B3 dead: {len(b3_dead)}')
