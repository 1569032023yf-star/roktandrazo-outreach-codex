#!/usr/bin/env python3
"""
B Pool CSV Import Script — Roktandrazo BD Outreach

Usage:
    # Dry run (default, no changes)
    python b_pool_import.py --csv output/b_pool_manual_review.csv

    # Live import
    python b_pool_import.py --csv output/b_pool_manual_review.csv --live

Imports manual_decision from the B pool CSV:
  approve       → checks MX/suppression/sent_log/bounce/domain → approved_manual_send
  reject        → status = rejected
  contact_form  → status = contact_form_pool
  review_later  → status = manual_review_needed

--dry-run is the default safety mode if --live is NOT provided.
"""

import argparse
import csv
import os
import sys
from datetime import datetime

# Ensure we can import from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bd_db import (
    get_db, update_lead_status, update_manual_approval, is_suppressed,
    check_sent_log, check_domain_sent, check_bounce_history,
    check_mx_provider, is_exchange_mx, add_to_suppression, log_send
)

# Soft domains (like gmail.com, outlook.com) should skip MX check
SOFT_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
    'icloud.com', 'protonmail.com', 'mail.com', 'zoho.com', 'yandex.com',
    'live.com', 'msn.com', 'qq.com', '163.com', '126.com', 'sina.com',
}

REQUIRED_CSV_COLUMNS = [
    'id', 'store_name', 'guessed_email',
    'manual_found_email', 'manual_email_source_url',
    'manual_email_source_type', 'manual_decision',
]


def load_csv(csv_path: str) -> list[dict]:
    """Load CSV, validate required columns, return list of row dicts."""
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("[ERROR] CSV is empty")
        sys.exit(1)

    # Check required columns
    headers = set(rows[0].keys())
    missing = [c for c in REQUIRED_CSV_COLUMNS if c not in headers]
    if missing:
        print(f"[ERROR] Missing required CSV columns: {missing}")
        print(f"  Found columns: {sorted(headers)}")
        sys.exit(1)

    print(f"[LOAD] Loaded {len(rows)} rows from {csv_path}")
    return rows


def pre_approval_checks(row: dict, dry_run: bool) -> list[str]:
    """Run all pre-approval checks. Returns list of failure reasons.
    If empty, the lead passes all checks.
    """
    lead_id = row.get('id', '').strip()
    store_name = row.get('store_name', '').strip()
    email = row.get('manual_found_email', '').strip().lower()
    domain = email.split('@')[1] if '@' in email else ''
    reasons = []

    if not email or '@' not in email:
        return [f"manual_found_email missing or invalid: '{email}'"]

    if not row.get('manual_email_source_url', '').strip():
        reasons.append("manual_email_source_url missing (required for approve)")

    # 1. Suppression check
    if is_suppressed(email):
        reasons.append(f"SUPPRESSED: {email}")
    if is_suppressed(row.get('guessed_email', '').strip()):
        reasons.append(f"Original guessed email suppressed: {row.get('guessed_email','')}")

    # 2. Sent log check
    if check_sent_log(email):
        reasons.append(f"ALREADY_SENT: {email}")

    # 3. Domain sent check
    if domain and check_domain_sent(domain):
        reasons.append(f"DOMAIN_ALREADY_SENT: {domain}")

    # 4. Bounce history
    bounce = check_bounce_history(email)
    if bounce['hard']:
        reasons.append(f"HARD_BOUNCE: {email} - {bounce['detail']}")
    if bounce['policy']:
        reasons.append(f"POLICY_BOUNCE: {email} - {bounce['detail']}")

    # 5. MX check (skip for known personal email domains)
    if domain and domain not in SOFT_DOMAINS:
        mx = check_mx_provider(domain)
        if mx == 'no_mx':
            reasons.append(f"NO_MX: {domain} (no mail exchange records)")
        elif mx == 'exchange':
            reasons.append(f"EXCHANGE_MX: {domain} (high bounce risk, needs manual approval)")
    elif domain in SOFT_DOMAINS:
        print(f"  [MX] Skipping MX check for personal domain: {domain}")

    return reasons


def import_row(row: dict, dry_run: bool) -> dict:
    """Process a single CSV row. Returns result dict with action taken."""
    lead_id = int(row.get('id', '0').strip())
    store_name = row.get('store_name', '').strip()
    decision = row.get('manual_decision', '').strip().lower()
    result = {
        'lead_id': lead_id,
        'store_name': store_name,
        'decision': decision,
        'approved': False,
        'messages': [],
        'warnings': [],
    }

    if not decision:
        result['messages'].append('No manual_decision, skipped')
        return result

    # Build manual fields dict for database
    manual_fields = {
        'manual_found_email': row.get('manual_found_email', '').strip(),
        'manual_email_source_url': row.get('manual_email_source_url', '').strip(),
        'manual_email_source_type': row.get('manual_email_source_type', '').strip(),
        'manual_decision': decision,
        'manual_note': row.get('manual_note', '').strip(),
        'manual_verified_by': 'user',
        'manual_verified_at': datetime.now().isoformat(),
    }

    if decision == 'approve':
        # Run pre-approval checks
        failures = pre_approval_checks(row, dry_run)

        if failures:
            result['approved'] = False
            result['warnings'] = failures
            result['messages'].append(f"FAILED checks: {'; '.join(failures)}")
            if not dry_run:
                update_lead_status(lead_id, 'approved_checks_failed',
                                   notes=f"Manual approve failed: {'; '.join(failures)}")
                update_manual_approval(lead_id, manual_fields)
        else:
            result['approved'] = True
            result['messages'].append("ALL CHECKS PASSED -> approved_manual_send")
            if not dry_run:
                update_manual_approval(lead_id, manual_fields)
                conn = get_db()
                c = conn.cursor()
                c.execute("""
                UPDATE leads SET
                    email = ?,
                    email_source_type = 'manual_verified_official',
                    email_verified_on_official_site = 1,
                    evidence_url = ?,
                    status = 'approved_manual_send',
                    manual_verified_by = 'user',
                    manual_verified_at = ?
                WHERE id = ?
                """, (
                    row.get('manual_found_email', '').strip(),
                    row.get('manual_email_source_url', '').strip(),
                    datetime.now().isoformat(),
                    lead_id,
                ))
                conn.commit()
                conn.close()
                print(f"  [IMPORT] {store_name}: approved_manual_send (email: {row.get('manual_found_email','').strip()})")

    elif decision == 'reject':
        result['messages'].append('Marked as rejected')
        if not dry_run:
            update_manual_approval(lead_id, manual_fields)
            update_lead_status(lead_id, 'rejected', notes=row.get('manual_note', 'Rejected via B pool import'))
        print(f"  [IMPORT] {store_name}: rejected")

    elif decision == 'contact_form':
        result['messages'].append('Moved to contact_form_pool')
        if not dry_run:
            update_manual_approval(lead_id, manual_fields)
            update_lead_status(lead_id, 'contact_form_pool')
        print(f"  [IMPORT] {store_name}: contact_form_pool")

    elif decision == 'review_later':
        result['messages'].append('Marked as manual_review_needed')
        if not dry_run:
            update_manual_approval(lead_id, manual_fields)
            update_lead_status(lead_id, 'manual_review_needed')
        print(f"  [IMPORT] {store_name}: manual_review_needed")

    else:
        result['messages'].append(f"Unknown decision: '{decision}', skipped")

    return result


def main():
    parser = argparse.ArgumentParser(description='B Pool CSV Import')
    parser.add_argument('--csv', required=True, help='Path to b_pool_manual_review.csv')
    parser.add_argument('--live', action='store_true', help='Actually import (default: dry-run)')
    args = parser.parse_args()

    dry_run = not args.live

    print("=" * 60)
    print("B POOL CSV IMPORT")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE IMPORT'}")
    print()

    rows = load_csv(args.csv)

    # Stats
    stats = {'approve': 0, 'approve_pass': 0, 'approve_fail': 0,
             'reject': 0, 'contact_form': 0, 'review_later': 0, 'skipped': 0}
    results = []

    for i, row in enumerate(rows, 1):
        print(f"\n[{i}/{len(rows)}] Processing: {row.get('store_name', '?'):30s} decision={row.get('manual_decision','?')}")
        result = import_row(row, dry_run)
        results.append(result)

        decision = result['decision']
        if not decision:
            stats['skipped'] += 1
        elif decision == 'approve':
            stats['approve'] += 1
            if result['approved']:
                stats['approve_pass'] += 1
            else:
                stats['approve_fail'] += 1
        elif decision == 'reject':
            stats['reject'] += 1
        elif decision == 'contact_form':
            stats['contact_form'] += 1
        elif decision == 'review_later':
            stats['review_later'] += 1

        if result['warnings']:
            for w in result['warnings']:
                print(f"    [WARN] {w}")

    # Summary
    print()
    print("=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"  Total rows processed:      {len(rows)}")
    print(f"  Approved (all checks pass): {stats['approve_pass']}")
    print(f"  Approved (checks failed):   {stats['approve_fail']}")
    print(f"  Rejected:                   {stats['reject']}")
    print(f"  Contact form:               {stats['contact_form']}")
    print(f"  Review later:               {stats['review_later']}")
    print(f"  Skipped (no decision):      {stats['skipped']}")
    print()
    if dry_run:
        print("[SAFE] DRY RUN — no database changes were made.")
        print("       Add --live to execute the import.")
    else:
        print("[LIVE] Import executed. Check lead statuses in database.")


if __name__ == '__main__':
    main()
