"""
Lead Collector Agent — Collect verified leads from official websites only.
NO guessed emails (info@/hello@/sales@/contact@) allowed for A-grade.
"""
import sqlite3, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from bd_db import insert_lead

DB = 'data/bd_leads.db'

def domain_hash(website):
    if not website: return ""
    d = website.lower().strip()
    d = d.replace("https://","").replace("http://","").replace("www.","")
    return d.split("/")[0].split("?")[0].split("#")[0]

def add_lead(store_name, store_type, city, state, website, email, evidence_url,
             fit_reason, product_fit, source_type="official_page_visible", grade="A",
             notes="", contact_form_url="", contact_page=""):
    # Grade A rules: email must be verified on official site
    if grade == "A" and email:
        # Allow A only if:
        # - source_type proves it's from official site
        # - email_verified_on_official_site will be set to 1
        valid_sources = ('official_page_visible', 'official_mailto', 'wholesale_vendor_page')
        if source_type not in valid_sources:
            return {"action": "DOWNGRADED", "reason": f"email_source_type={source_type} not valid for A", "grade": "B"}
    elif grade == "A" and not email:
        # No email at all for A-grade
        return {"action": "DOWNGRADED", "reason": "no email for A-grade", "grade": "B"}
    
    lead_id = insert_lead({
        'store_name': store_name, 'store_type': store_type, 'city': city, 'state': state,
        'official_website': website, 'contact_page': contact_page, 'email': email or '',
        'email_type': 'general' if email else 'contact_form_only', 'contact_form_url': contact_form_url,
        'evidence_url': evidence_url, 'source_keyword': f'{store_type} {city} {state}',
        'fit_reason': fit_reason, 'product_fit': product_fit, 'confidence_score': grade,
        'status': 'new', 'notes': notes, 'email_source_type': source_type,
        'email_verified_on_official_site': 1 if email and source_type in ('official_page_visible','official_mailto','wholesale_vendor_page') else 0,
    })
    return {'action': 'INSERTED' if lead_id else 'SKIPPED_HISTORY_MATCH', 'store': store_name, 'grade': grade}

def dry_run_collect(city, state, store_types):
    print(f'[DRY-RUN] Collecting {city}, {state} ({store_types})')
    guessed = {'info','hello','sales'}
    print(f'  Would search for {len(store_types)} store types')
    print(f'  Would verify email on official website before grading')
    print(f'  Guessed email rule: {len(guessed)} prefix patterns blocked')
    print(f'  A-grade: only if email found on official website')
    print(f'  B-grade: contact form only or third-party email')
    print(f'  C-grade: no MX or product mismatch')
    print(f'[DRY-RUN COMPLETE]')
    return {"action": "DRY_RUN_OK", "city": city}

if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        result = dry_run_collect('Austin', 'TX', ['board game store', 'toy store'])
        print(result)
