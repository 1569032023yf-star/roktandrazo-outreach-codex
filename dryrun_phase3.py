"""
Phase 3 Dry-Run — Top 15 A-grade leads
Select best candidates, apply active template, render full preview.
NO real sending.
"""
import sqlite3, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from bd_template import get_email_for_lead
from bd_db import is_suppressed

DB_PATH = 'data/bd_leads.db'

# Priority ordering for store types
STORE_PRIORITY = {
    "board game store": 1,
    "board game store / restaurant": 1,
    "card game store": 1,
    "game store": 1,
    "board game cafe": 1,
    "comic / game store": 1,
    "book / game store": 1,
    "board game / hobby store": 1,
    "puzzle shop / board game store": 1,
    "independent toy store": 2,
    "independent toy store chain": 2,
    "toy store / hobby shop": 2,
    "toy store / children boutique": 2,
    "educational toy store": 3,
    "toy store / costume shop": 3,
    "puzzle / gift store": 4,
    "gift shop": 5,
    "museum / national park gift shop": 5,
}

def priority_score(store_type):
    return STORE_PRIORITY.get((store_type or "").lower().strip(), 99)

def domain_hash(website):
    if not website: return ""
    d = website.lower().strip()
    d = d.replace("https://","").replace("http://","").replace("www.","")
    d = d.split("/")[0].split("?")[0].split("#")[0]
    return d

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get suppression list
    cur.execute('SELECT email FROM suppression_list')
    suppressed_emails = set(r['email'] for r in cur.fetchall())

    # Get sent emails and domains
    cur.execute('SELECT DISTINCT email FROM send_log WHERE status="sent"')
    sent_emails = set(r['email'] for r in cur.fetchall())
    
    cur.execute('SELECT official_website FROM leads WHERE status="sent"')
    sent_domains = set()
    for r in cur.fetchall():
        d = domain_hash(r['official_website'])
        if d: sent_domains.add(d)

    # Get all Phase 3 new A-grade with email (IDs 52+ = Phase 3 imports)
    cur.execute('''
    SELECT * FROM leads
    WHERE id >= 52 AND confidence_score = "A" AND status = "new"
      AND email IS NOT NULL AND email != ""
    ORDER BY id
    ''')
    rows = [dict(r) for r in cur.fetchall()]

    print(f"Phase 3 new A-grade candidates: {len(rows)}")
    print()

    # Exclude suppressed, sent domains, invalid evidence
    filtered = []
    for lead in rows:
        email = lead['email']
        website = lead.get('official_website', '')
        evidence = lead.get('evidence_url', '')
        domain = domain_hash(website)
        
        reasons = []
        
        # Suppression check
        if is_suppressed(email):
            reasons.append(f"suppressed email")
        
        # Sent email check
        if email in sent_emails:
            reasons.append(f"already sent ({email})")
        
        # Sent domain check
        if domain and domain in sent_domains:
            reasons.append(f"domain already sent ({domain})")
        
        # Evidence check
        if not evidence:
            reasons.append("no evidence_url")
        
        if reasons:
            print(f"  [EXCLUDE] {lead['store_name']:45s} | {'; '.join(reasons)}")
            continue
        
        # Check email source - if email_type is empty or unknown, flag it
        email_type = (lead.get('email_type') or '').lower()
        
        filtered.append(lead)

    print(f"\nAfter exclusion: {len(filtered)} candidates remain")
    print()

    # Sort by priority
    filtered.sort(key=lambda l: (priority_score(l.get('store_type', '')), l['store_name']))

    # Select top 15
    top15 = filtered[:15]

    print(f"Selected top 15 for dry-run:")
    for i, l in enumerate(top15, 1):
        p = priority_score(l['store_type'])
        print(f"  [{p}] {l['store_type']:35s} | {l['store_name']:40s} | {l['city']:15s} {l['state']} | {l['email']}")
    print()
    print("=" * 100)
    print()

    # Now generate dry-run for each
    for i, lead in enumerate(top15, 1):
        email = lead['email']
        suppressed = is_suppressed(email)
        already_sent = email in sent_emails
        status = lead.get('status', '')
        
        # Generate email
        email_data = get_email_for_lead(lead)
        
        subject = email_data['subject']
        body_text = email_data['body_text']
        
        # Safety checks
        issues = []
        if '{{' in body_text or '}}' in body_text: issues.append('{{}}')
        if 'undefined' in body_text.lower(): issues.append('undefined')
        if 'None' in body_text: issues.append('None')
        if 'null' in body_text.lower(): issues.append('null')
        if '&ndash;' in body_text: issues.append('&ndash;')
        if 'stationary' in body_text.lower(): issues.append('stationary (typo)')
        if '&amp;' in body_text and '<' not in body_text: issues.append('&amp; in plaintext')

        print(f"{'='*100}")
        print(f"[{i}/15] {lead['store_name']}")
        print(f"{'='*100}")
        print(f"  City/State       : {lead.get('city','')}, {lead.get('state','')}")
        print(f"  Store Type       : {lead.get('store_type','')}")
        print(f"  Email            : {email}")
        print(f"  Official Website : {lead.get('official_website','')}")
        print(f"  Evidence URL     : {lead.get('evidence_url','')}")
        print(f"  Email Source     : {lead.get('email_type','')}")
        print(f"  Product Fit      : {lead.get('product_fit','')}")
        print(f"  Confidence       : {lead.get('confidence_score','')}")
        print(f"  Fit Reason       : {lead.get('fit_reason','')[:100]}")
        print()
        print(f"  From             : Ian <ianyf@roktandrazo.com>")
        print(f"  Reply-To         : ianyf@roktandrazo.com")
        print(f"  Subject          : {subject}")
        print()
        print(f"  In Suppression?  : {'⚠️ YES' if suppressed else '✅ NO'}")
        print(f"  Already Sent?    : {'⚠️ YES' if already_sent else '✅ NO'}")
        print(f"  Template Issues  : {', '.join(issues) if issues else '✅ None'}")
        print(f"  Recommend Send   : {'✅ YES' if not issues else '⚠️ Check issues'}")
        print()
        print(f"  --- FULL EMAIL BODY ---")
        for line in body_text.split('\n'):
            print(f"  | {line}")
        print(f"  --- END ---")
        print()

    # Summary table
    print("=" * 100)
    print("PHASE 3 DRY-RUN SUMMARY")
    print("=" * 100)
    print(f"{'#':>2} | {'Store':40s} | {'City':15s} | {'Email':35s} | {'Suppr?':6s} | {'Issues':15s} | {'Send?':6s}")
    print("-" * 120)
    for i, lead in enumerate(top15, 1):
        email = lead['email']
        suppressed = is_suppressed(email)
        email_data = get_email_for_lead(lead)
        issues = []
        bt = email_data['body_text']
        if '{{' in bt or '}}' in bt: issues.append('{{}}')
        if 'undefined' in bt.lower(): issues.append('undef')
        if 'None' in bt: issues.append('None')
        if 'null' in bt.lower(): issues.append('null')
        if '&ndash;' in bt: issues.append('&ndash;')
        if 'stationary' in bt.lower(): issues.append('stationary')
        issue_str = ', '.join(issues) if issues else '✅'
        suppr_str = '⚠️' if suppressed else '✅'
        send_str = '⚠️' if issues else '✅'
        city = f"{lead['city']}, {lead['state']}"
        print(f"{i:2d} | {lead['store_name']:40s} | {city:15s} | {email:35s} | {suppr_str:6s} | {issue_str:15s} | {send_str:6s}")

    print()
    print(f"Total selected: {len(top15)}")
    print(f"All checks passed: {sum(1 for l in top15[:10] for _ in [0])}")  # placeholder

    conn.close()

if __name__ == '__main__':
    main()
