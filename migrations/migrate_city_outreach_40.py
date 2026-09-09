"""Idempotent migration for City Outreach 40. Run only against an explicit database path."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


LEAD_COLUMNS = [
    ("evidence_snippet", "TEXT"),
    ("formatted_address", "TEXT"),
    ("normalized_address", "TEXT"),
    ("phone", "TEXT"),
    ("normalized_phone", "TEXT"),
    ("organization_key", "TEXT"),
    ("recipient_timezone", "TEXT"),
    ("timezone_status", "TEXT"),
]
REVIEW_LEAD_COLUMNS = [
    ("review_reason_code", "TEXT"), ("review_reason_detail", "TEXT"),
    ("review_status", "TEXT DEFAULT 'pending'"), ("review_priority", "TEXT"),
    ("review_created_at", "TEXT"), ("review_updated_at", "TEXT"),
    ("auto_sendable", "INTEGER NOT NULL DEFAULT 0"),
    ("manual_sendable", "INTEGER NOT NULL DEFAULT 0"),
    ("defer_reason", "TEXT"), ("next_review_at", "TEXT"),
    ("recheck_pending", "TEXT"),
    ("evidence_method", "TEXT"), ("primary_outreach_email", "TEXT"),
]
SEND_LOG_COLUMNS = [
    ("message_type", "TEXT"), ("outreach_batch_date", "TEXT"),
    ("plan_entry_id", "INTEGER"),
]
RETAIL_CITY_QUEUE_COLUMNS = [
    ("active_provider", "TEXT"),
    ("pages_processed", "INTEGER NOT NULL DEFAULT 0"),
    ("results_seen", "INTEGER NOT NULL DEFAULT 0"),
    ("new_unique_places", "INTEGER NOT NULL DEFAULT 0"),
    ("duplicate_places", "INTEGER NOT NULL DEFAULT 0"),
    ("provider_errors", "INTEGER NOT NULL DEFAULT 0"),
    ("consecutive_pages_without_new_place", "INTEGER NOT NULL DEFAULT 0"),
    ("last_success_at", "TEXT"),
    ("last_error", "TEXT"),
    ("resume_state", "TEXT"),
    ("web_directory_status", "TEXT"),
]
DISCOVERY_RESULT_COLUMNS = [
    ("country", "TEXT"),
    ("evidence_url", "TEXT"),
    ("evidence_snippet", "TEXT"),
    ("evidence_method", "TEXT"),
    ("contact_form_url", "TEXT"),
    ("official_match", "INTEGER DEFAULT 0"),
    ("location_status", "TEXT"),
]


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def check(conn: sqlite3.Connection) -> dict:
    return {
        "leads": sorted(columns(conn, "leads")),
        "send_log": sorted(columns(conn, "send_log")),
        "retail_city_queue_exists": bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='retail_city_queue'").fetchone()),
        "final_send_plan_exists": bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='final_send_plan'").fetchone()),
        "review_log_exists": bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_log'").fetchone()),
        "manual_send_queue_exists": bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='manual_send_queue'").fetchone()),
        "manual_email_submission_exists": bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='manual_email_submission'").fetchone()),
        "lead_discovery_results_exists": bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lead_discovery_results'").fetchone()),
        "lead_discovery_query_state_exists": bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lead_discovery_query_state'").fetchone()),
    }


def migrate(db_path: Path) -> tuple[dict, dict]:
    conn = sqlite3.connect(db_path)
    before = check(conn)
    try:
        with conn:
            for name, kind in LEAD_COLUMNS:
                if name not in columns(conn, "leads"):
                    conn.execute(f"ALTER TABLE leads ADD COLUMN {name} {kind}")
            for name, kind in REVIEW_LEAD_COLUMNS:
                if name not in columns(conn, "leads"):
                    conn.execute(f"ALTER TABLE leads ADD COLUMN {name} {kind}")
            for name, kind in SEND_LOG_COLUMNS:
                if name not in columns(conn, "send_log"):
                    conn.execute(f"ALTER TABLE send_log ADD COLUMN {name} {kind}")
            conn.execute("""CREATE TABLE IF NOT EXISTS retail_city_queue (
                id INTEGER PRIMARY KEY, city TEXT NOT NULL, state TEXT NOT NULL, priority INTEGER NOT NULL,
                timezone TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', started_at TEXT, completed_at TEXT,
                active_query_family TEXT, active_source TEXT, page_cursor TEXT, discovered_count INTEGER NOT NULL DEFAULT 0,
                unique_domain_count INTEGER NOT NULL DEFAULT 0, official_site_count INTEGER NOT NULL DEFAULT 0,
                public_email_count INTEGER NOT NULL DEFAULT 0, strict_a0_count INTEGER NOT NULL DEFAULT 0,
                manual_review_count INTEGER NOT NULL DEFAULT 0, contact_form_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0, rejected_count INTEGER NOT NULL DEFAULT 0,
                last_new_domain_at TEXT, completion_reason TEXT, UNIQUE(city, state))""")
            for name, kind in RETAIL_CITY_QUEUE_COLUMNS:
                if name not in columns(conn, "retail_city_queue"):
                    conn.execute(f"ALTER TABLE retail_city_queue ADD COLUMN {name} {kind}")
            conn.execute("""CREATE TABLE IF NOT EXISTS final_send_plan (
                id INTEGER PRIMARY KEY, plan_id TEXT NOT NULL, lead_id INTEGER NOT NULL, recipient_email TEXT NOT NULL,
                company_name TEXT NOT NULL, customer_type TEXT, lead_segment TEXT, template_id TEXT,
                source_city TEXT, source_state TEXT, evidence_url TEXT NOT NULL, hygiene_passed_at TEXT NOT NULL,
                message_type TEXT NOT NULL CHECK(message_type IN ('new_outreach','follow_up')),
                outreach_batch_date TEXT NOT NULL, planned_sequence INTEGER NOT NULL, subject TEXT NOT NULL,
                body_text TEXT NOT NULL, body_html TEXT, status TEXT NOT NULL DEFAULT 'planned',
                skip_reason TEXT, sent_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plan_id, planned_sequence), UNIQUE(plan_id, lead_id))""")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_send_log_sent_plan_entry ON send_log(plan_entry_id) WHERE status='sent' AND plan_entry_id IS NOT NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_send_log_batch_type ON send_log(outreach_batch_date, message_type, status)")
            conn.execute("""CREATE TABLE IF NOT EXISTS review_log (
                action_id TEXT PRIMARY KEY, lead_id INTEGER NOT NULL, previous_status TEXT, new_status TEXT,
                decision TEXT NOT NULL, reviewer TEXT NOT NULL, reason_code TEXT, reason_detail TEXT,
                reviewed_at TEXT NOT NULL, hygiene_result TEXT, request_id TEXT NOT NULL,
                evidence_url TEXT, source_channel TEXT, whether_auto_sendable INTEGER NOT NULL DEFAULT 0,
                whether_manual_sendable INTEGER NOT NULL DEFAULT 0
            )""")
            for name, kind in [
                ("evidence_url", "TEXT"), ("source_channel", "TEXT"),
                ("whether_auto_sendable", "INTEGER NOT NULL DEFAULT 0"),
                ("whether_manual_sendable", "INTEGER NOT NULL DEFAULT 0"),
            ]:
                if name not in columns(conn, "review_log"):
                    conn.execute(f"ALTER TABLE review_log ADD COLUMN {name} {kind}")
            conn.execute("""CREATE TABLE IF NOT EXISTS manual_send_queue (
                id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL UNIQUE, status TEXT NOT NULL,
                approved_at TEXT NOT NULL, reviewer TEXT NOT NULL, reason TEXT, consumed_at TEXT,
                action_id TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS lead_email_history (
                id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL, email TEXT, email_status TEXT NOT NULL,
                role TEXT, evidence_url TEXT, evidence_snippet TEXT, evidence_method TEXT,
                replaced_at TEXT NOT NULL, replaced_by TEXT, replacement_reason TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS manual_email_submission (
                id TEXT PRIMARY KEY, lead_id INTEGER NOT NULL, previous_email TEXT, submitted_email TEXT NOT NULL,
                submitted_by TEXT NOT NULL, submitted_at TEXT NOT NULL, evidence_url TEXT, evidence_snippet TEXT,
                evidence_method TEXT, contact_role TEXT, notes TEXT, history_match_result TEXT, hygiene_result TEXT,
                final_status TEXT NOT NULL, failure_reason TEXT, promoted_to_a0_at TEXT
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS lead_discovery_results (
                id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL,
                provider_result_id TEXT,
                place_id TEXT,
                business_name TEXT NOT NULL,
                normalized_business_name TEXT,
                formatted_address TEXT,
                normalized_address TEXT,
                city TEXT,
                state TEXT,
                postal_code TEXT,
                phone TEXT,
                normalized_phone TEXT,
                website TEXT,
                normalized_domain TEXT,
                business_status TEXT,
                primary_type TEXT,
                raw_types_json TEXT,
                source_query TEXT,
                query_family TEXT,
                source_url TEXT,
                raw_payload_json TEXT,
                active_city_id INTEGER NOT NULL,
                discovered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                validation_status TEXT NOT NULL DEFAULT 'validation_pending',
                history_crosscheck_result TEXT,
                linked_lead_id INTEGER,
                rejection_reason TEXT,
                country TEXT,
                evidence_url TEXT,
                evidence_snippet TEXT,
                evidence_method TEXT,
                contact_form_url TEXT,
                official_match INTEGER DEFAULT 0,
                location_status TEXT,
                created_lead_via TEXT DEFAULT 'bd_db.insert_lead'
            )""")
            for name, kind in DISCOVERY_RESULT_COLUMNS:
                if name not in columns(conn, "lead_discovery_results"):
                    conn.execute(f"ALTER TABLE lead_discovery_results ADD COLUMN {name} {kind}")
            conn.execute("""CREATE TABLE IF NOT EXISTS lead_discovery_hits (
                id INTEGER PRIMARY KEY,
                discovery_result_id INTEGER NOT NULL,
                query_family TEXT NOT NULL,
                source_query TEXT,
                provider TEXT NOT NULL,
                provider_result_id TEXT,
                seen_at TEXT NOT NULL,
                UNIQUE(discovery_result_id, query_family, provider, provider_result_id)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS lead_discovery_query_state (
                id INTEGER PRIMARY KEY,
                active_city_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                query_family TEXT NOT NULL,
                query_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                page_cursor TEXT DEFAULT '',
                pages_processed INTEGER NOT NULL DEFAULT 0,
                results_seen INTEGER NOT NULL DEFAULT 0,
                new_unique_places INTEGER NOT NULL DEFAULT 0,
                duplicate_places INTEGER NOT NULL DEFAULT 0,
                provider_errors INTEGER NOT NULL DEFAULT 0,
                consecutive_pages_without_new_place INTEGER NOT NULL DEFAULT 0,
                last_success_at TEXT,
                last_error TEXT,
                resume_state TEXT,
                started_at TEXT,
                completed_at TEXT,
                UNIQUE(active_city_id, provider, query_family)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS provider_request_audit (
                id INTEGER PRIMARY KEY,
                active_city_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                query_family TEXT,
                source_query TEXT,
                page_cursor TEXT,
                next_page_cursor TEXT,
                status TEXT NOT NULL,
                error TEXT,
                result_count INTEGER NOT NULL DEFAULT 0,
                request_count INTEGER NOT NULL DEFAULT 0,
                cost_units INTEGER NOT NULL DEFAULT 0,
                requested_at TEXT NOT NULL
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS city_discovery_reports (
                id INTEGER PRIMARY KEY,
                active_city_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                totals_json TEXT,
                generated_at TEXT NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_review_status ON leads(review_status, next_review_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_review_log_lead_time ON review_log(lead_id, reviewed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_manual_send_queue_status ON manual_send_queue(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_manual_email_lead_time ON manual_email_submission(lead_id, submitted_at)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_retail_city_only_one_active ON retail_city_queue(status) WHERE status='active'")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_discovery_provider_result ON lead_discovery_results(provider, provider_result_id) WHERE provider_result_id IS NOT NULL AND provider_result_id != ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discovery_city_status ON lead_discovery_results(active_city_id, validation_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discovery_identity ON lead_discovery_results(normalized_business_name, normalized_address, city, state)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discovery_query_state ON lead_discovery_query_state(active_city_id, provider, status)")
            conn.executemany("""INSERT OR IGNORE INTO retail_city_queue (city, state, priority, timezone, status)
                VALUES (?, ?, ?, ?, 'pending')""", [
                ('Nashville', 'TN', 1, 'America/Chicago'), ('Memphis', 'TN', 2, 'America/Chicago'),
                ('Knoxville', 'TN', 3, 'America/New_York'), ('Little Rock', 'AR', 10, 'America/Chicago'),
                ('Fayetteville', 'AR', 11, 'America/Chicago'), ('Louisville', 'KY', 20, 'America/New_York'),
                ('Lexington', 'KY', 21, 'America/New_York'),
            ])
        after = check(conn)
        return before, after
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        conn = sqlite3.connect(args.db)
        try: print(check(conn))
        finally: conn.close()
        return
    before, after = migrate(args.db)
    print({"before": before, "after": after})


if __name__ == "__main__":
    main()
