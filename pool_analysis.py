"""
BD Sending Pool Analysis v2 — A0/A1/approved_manual_send/B/C
Outputs new B pool CSV with manual fields. NEVER puts guessed_email into send pool.
"""
import sqlite3, csv, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bd_db import get_db, check_mx_provider

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'bd_leads.db')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(OUT, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# --- Cache sent / suppressed / bounced ---
sent_emails = set(r['email'].lower() for r in cur.execute("SELECT email FROM send_log WHERE status='sent'").fetchall())
supp_emails = set(r['email'].lower() for r in cur.execute("SELECT email FROM suppression_list").fetchall())
sent_leads = set(r['lead_id'] for r in cur.execute("SELECT lead_id FROM send_log WHERE status='sent'").fetchall())
bounced_emails = set(r['email'].lower() for r in cur.execute("SELECT DISTINCT email FROM bounce_log").fetchall())

def check_mx(domain):
    """Safe MX check wrapper."""
    try:
        return check_mx_provider(domain) if domain else 'unknown'
    except Exception:
        return 'error'

print('=' * 70)
print('BD SENDING POOL ANALYSIS v2')
print('=' * 70)

# ============================================================
# A0: Verified Official Email (non-Exchange)
# ============================================================
print()
print('--- A0: Verified Official Email (auto-send) ---')
cur.execute('''SELECT id, store_name, email, store_type, city, state, evidence_url, email_source_type, mx_provider
FROM leads WHERE status="new" AND confidence_score="A"
AND email_verified_on_official_site=1
AND email_source_type IN ("official_page_visible","official_mailto","wholesale_vendor_page")
AND email IS NOT NULL AND email != ""
ORDER BY store_name''')

a0_candidates = [dict(r) for r in cur.fetchall()]
a0_valid = []
a1_exchange = []
for lead in a0_candidates:
    email = lead['email'].lower()
    if email in sent_emails or email in supp_emails or lead['id'] in sent_leads or email in bounced_emails:
        continue
    domain = email.split('@')[1] if '@' in email else ''
    mx = check_mx(domain)
    if mx in ('exchange', 'exchange_online'):
        a1_exchange.append(lead)
    else:
        a0_valid.append(lead)

print(f'  A0 sendable (non-Exchange): {len(a0_valid)}')
for i, r in enumerate(a0_valid[:10], 1):
    print(f'  {i:2d}. {r["store_name"]:35s} | {r["email"]:35s}')
print(f'  A1 (Exchange, capped): {len(a1_exchange)}')

# ============================================================
# approved_manual_send pool
# ============================================================
print()
print('--- Approved Manual Send Pool ---')
cur.execute('''SELECT id, store_name, email, store_type, city, state, manual_found_email,
    manual_email_source_url, manual_email_source_type, mx_provider
FROM leads WHERE status="approved_manual_send"
AND email IS NOT NULL AND email != ""
ORDER BY manual_verified_at ASC''')
ams_leads = [dict(r) for r in cur.fetchall()]
print(f'  approved_manual_send: {len(ams_leads)}')
for i, r in enumerate(ams_leads[:5], 1):
    print(f'  {i:2d}. {r["store_name"]:35s} | {r["email"]:35s}')

# ============================================================
# B: Guessed Email Pool
# ============================================================
print()
print('--- B: Guessed Email Candidate Pool ---')
cur.execute('''SELECT id, store_name, email, store_type, city, state, official_website,
    evidence_url, contact_form_url, product_fit, fit_reason, notes,
    email_source_type, mx_provider
FROM leads WHERE status IN ("new", "manual_review_needed") AND confidence_score="B"
AND email IS NOT NULL AND email != ""
AND official_website IS NOT NULL AND official_website != ""
ORDER BY store_name''')
b_raw = [dict(r) for r in cur.fetchall()]

# Exclude sent/suppressed/bounced
b_valid = []
for lead in b_raw:
    email = lead['email'].lower()
    if email in sent_emails or email in supp_emails or lead['id'] in sent_leads or email in bounced_emails:
        continue
    b_valid.append(lead)

print(f'  B pool total: {len(b_valid)}')

# ============================================================
# C: Contact Form Pool
# ============================================================
print()
print('--- C: Contact Form Pool ---')
c_count = cur.execute('''SELECT COUNT(*) FROM leads WHERE status IN ("new","contact_form_pool")
AND (email IS NULL OR email = "")
AND contact_form_url IS NOT NULL AND contact_form_url != ""
AND official_website IS NOT NULL AND official_website != ""''').fetchone()[0]
print(f'  C pool: {c_count}')

# ============================================================
# Day 1 Plan (08:30-12:00 Local Time)
# ============================================================
a0_sendable = len(a0_valid)
ams_sendable = len(ams_leads)
need = 20
print()
print('=' * 70)
print('DAY 1 SENDING PLAN (08:30-12:00 Local)')
print('=' * 70)
print(f'  Daily target:                {need} emails')
print(f'  A0 sendable:                 {a0_sendable}')
print(f'  A1 (Exchange, capped):       {len(a1_exchange)}')
print(f'  approved_manual_send:        {ams_sendable}')
print(f'  B available (needs review):  {len(b_valid)}')
print(f'  Shortfall:                   {max(0, need - a0_sendable - ams_sendable)}')
print()
print(f'  Priority chain: A0 ({a0_sendable}) > approved_manual_send ({ams_sendable})')
if a0_sendable >= need:
    print(f'  A0 alone can support 20/day ({a0_sendable} available)')
elif a0_sendable + ams_sendable >= need:
    print(f'  A0 + approved_manual_send can support 20/day')
else:
    from_b = need - a0_sendable - ams_sendable
    print(f'  Need {from_b} approved from B pool to reach 20/day')

# Batch schedule (local time)
print()
print('--- Batch Schedule (Local Time 08:30-12:00) ---')
batches = [('08:40-09:00', 5), ('09:30-09:50', 5), ('10:20-10:40', 5), ('11:10-11:30', 5)]
remaining = need
pool_idx = 0
for i, (bt, size) in enumerate(batches):
    this = min(size, remaining)
    from_a0 = min(this, a0_sendable - pool_idx)
    store_list = []
    for j in range(min(from_a0, len(a0_valid) - pool_idx)):
        store_list.append(a0_valid[pool_idx + j]['store_name'])
    pool_idx += from_a0
    remaining -= this
    display = ', '.join(store_list[:2])
    if len(store_list) > 2:
        display += f' ... +{len(store_list)-2}'
    print(f'  Batch {i+1}: {bt:20s} | {this}emails | A0={from_a0} | {display}')
    if remaining <= 0:
        break

# ============================================================
# Generate NEW B Pool CSV with manual fields
# ============================================================
print()
print('--- Generating B Pool Manual Review CSV ---')
csv_path = os.path.join(OUT, 'b_pool_manual_review.csv')
manual_candidates = b_valid[:30]

# CSV headers: old fields + 7 new manual fields
HEADERS = [
    'id', 'store_name', 'domain', 'store_type', 'city', 'state',
    'official_website', 'guessed_email', 'evidence_url', 'contact_form_url',
    'product_fit', 'mx_status',
    # NEW manual fields (blank, for human to fill)
    'manual_found_email', 'manual_email_source_url', 'manual_email_source_type',
    'manual_decision', 'manual_note', 'manual_verified_by', 'manual_verified_at',
]

with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(HEADERS)
    for lead in manual_candidates:
        email = lead['email']
        domain = email.split('@')[1] if '@' in email else ''
        mx = check_mx(domain)
        w.writerow([
            lead['id'], lead['store_name'], domain, lead.get('store_type', ''),
            lead.get('city', ''), lead.get('state', ''),
            lead.get('official_website', ''), email,
            lead.get('evidence_url', ''), lead.get('contact_form_url', ''),
            lead.get('product_fit', ''), mx,
            # Manual fields (all blank — human fills them)
            '', '', '',  # manual_found_email, source_url, source_type
            '',          # manual_decision (approve/reject/contact_form/review_later)
            '',          # manual_note
            '',          # manual_verified_by (auto-filled on import)
            '',          # manual_verified_at (auto-filled on import)
        ])

print(f'  File: {csv_path}')
print(f'  Records: {len(manual_candidates)} (Top 30 only; full B pool should be browser-verified first)')
print()
print('  How to use:')
print('  1. Run Browser Verification first for the full B pool')
print('  2. Open this Top 30 CSV only for high-value exceptions')
print('  3. If you find a real email, fill manual_found_email + manual_email_source_url')
print('  4. Set manual_decision = approve / reject / contact_form / review_later')
print('  5. Save the CSV')
print('  6. Run: python b_pool_import.py --csv output/b_pool_manual_review.csv --live')
print()

# ============================================================
# Summary
# ============================================================
conn.close()
print()
print('=' * 70)
print('SUMMARY')
print('=' * 70)
print(f'  A0 (auto-send, non-Exchange):         {a0_sendable}')
print(f'  A1 (auto-send, Exchange):             {len(a1_exchange)}')
print(f'  approved_manual_send:                 {ams_sendable}')
print(f'  B  (guessed, browser verification):   {len(b_valid)}')
print(f'  B2 manual exception CSV:              {len(manual_candidates)}')
print(f'  C  (contact form):                    {c_count}')
print(f'  Day 1 target:                         {need}')
print(f'  Day 1 from A0:                        {min(a0_sendable, need)}')
print(f'  Day 1 from approved_manual_send:      {min(ams_sendable, max(0, need - a0_sendable))}')
print(f'  Day 1 from B (if approved):           {max(0, need - a0_sendable - ams_sendable)}')
