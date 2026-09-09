#!/usr/bin/env python3
"""BD Manual Review CLI. It never sends email or creates a Final Send Plan."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from review_workflow import apply_review_action

DB_PATH = Path(os.getenv("WORKBUDDY_BD_DB_PATH") or PROJECT_DIR / 'data' / 'bd_leads.db')


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def cmd_list() -> None:
    conn = db()
    rows = conn.execute("""
        SELECT id, store_name, city, state, confidence_score, status, review_status,
               email, next_review_at, review_reason_code
        FROM leads
        WHERE COALESCE(review_status, 'pending') IN ('pending', 'recheck_pending')
           OR (review_status='deferred' AND next_review_at <= datetime('now'))
        ORDER BY COALESCE(next_review_at, review_created_at, collected_at), id LIMIT 50
    """).fetchall()
    conn.close()
    print(f"{'ID':<6} {'Store':<30} {'City, ST':<20} {'Status':<18} {'Review':<16} Email")
    print('-' * 120)
    for row in rows:
        r = dict(row)
        print(f"{r['id']:<6} {(r['store_name'] or '')[:30]:<30} {((r['city'] or '') + ', ' + (r['state'] or ''))[:20]:<20} "
              f"{(r['status'] or ''):<18} {(r['review_status'] or 'pending'):<16} {(r['email'] or 'N/A')[:35]}")


def cmd_show(lead_id: int) -> None:
    conn = db()
    row = conn.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
    conn.close()
    if not row:
        print(f'Not found: {lead_id}')
        return
    for key, value in sorted(dict(row).items()):
        if value not in (None, ''):
            print(f'  {key:30s}: {str(value)[:160]}')


def cmd_action(lead_id: int, action: str, reason: str, next_review_at: str = '') -> None:
    conn = db()
    try:
        with conn:
            result = apply_review_action(
                conn, lead_id, action, reviewer='cli', reason=reason,
                next_review_at=next_review_at,
            )
    finally:
        conn.close()
    if result['ok']:
        print(f"{action}: lead #{lead_id} -> {result['new_status']}")
    else:
        print(f"BLOCKED: {result['error']}")
        if result.get('reasons'):
            print('Hygiene:', ', '.join(result['reasons']))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=[
        'list', 'show', 'approve', 'approve-manual', 'reject', 'defer',
        'recheck-official', 'recheck-facebook',
    ])
    parser.add_argument('lead_id', type=int, nargs='?')
    parser.add_argument('--reason', default='cli review action')
    parser.add_argument('--next-review-at', default='')
    args = parser.parse_args()
    if args.action == 'list':
        cmd_list()
    elif args.action == 'show' and args.lead_id:
        cmd_show(args.lead_id)
    elif args.lead_id:
        action_map = {
            'approve': 'approve_auto', 'approve-manual': 'approve_manual',
            'reject': 'reject', 'defer': 'defer',
            'recheck-official': 'recheck_official', 'recheck-facebook': 'recheck_facebook',
        }
        cmd_action(args.lead_id, action_map[args.action], args.reason, args.next_review_at)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
