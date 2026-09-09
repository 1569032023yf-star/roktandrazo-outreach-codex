"""Migration: add email tracking tables (idempotent).

Run: python migrations/migrate_email_tracking.py
Or: python migrations/migrate_email_tracking.py --conn /path/to/db

Tables added:
  - email_tracking_messages  (one row per sent email with tracking)
  - email_engagement_events  (open/click/bounce/reply/complaint/unsubscribe events)
  - email_tracking_link_registry (click target URLs with link_id mapping)

Columns added to existing tables:
  - leads: engagement_score, first_open_signal_at, last_open_signal_at, open_signal_count
  - send_log: tracking_token_hash (nullable)

All operations are IF NOT EXISTS / idempotent.
"""

import os
import sqlite3
import sys


def migrate(conn: sqlite3.Connection) -> dict:
    """Run migration. Returns dict of {table: created/already_exists}."""
    c = conn.cursor()
    results = {}

    # ── email_tracking_messages ────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS email_tracking_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_token_hash TEXT NOT NULL,
                lead_id INTEGER,
                organization_key TEXT DEFAULT '',
                plan_entry_id TEXT DEFAULT '',
                plan_id TEXT DEFAULT '',
                send_log_id INTEGER DEFAULT 0,
                smtp_message_id TEXT DEFAULT '',
                message_type TEXT DEFAULT 'new_outreach',
                provider TEXT DEFAULT 'local_first_party',
                tracking_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT '',
                activated_at TEXT DEFAULT '',
                expires_at TEXT DEFAULT '',
                disabled_at TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                is_test INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracking_token_hash
            ON email_tracking_messages(tracking_token_hash)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracking_lead_id
            ON email_tracking_messages(lead_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracking_plan_entry
            ON email_tracking_messages(plan_entry_id)
        """)
        results["email_tracking_messages"] = "created"
    except Exception as e:
        results["email_tracking_messages"] = f"error: {e}"

    # ── email_engagement_events ────────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS email_engagement_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_message_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_at TEXT NOT NULL,
                provider TEXT DEFAULT '',
                source_classification TEXT DEFAULT 'direct_or_unknown',
                user_agent_family TEXT DEFAULT '',
                ip_hash TEXT DEFAULT '',
                target_link_id INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}',
                dedupe_key TEXT UNIQUE,
                is_test INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (tracking_message_id) REFERENCES email_tracking_messages(id)
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_message_id
            ON email_engagement_events(tracking_message_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON email_engagement_events(event_type)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_at
            ON email_engagement_events(event_at)
        """)
        results["email_engagement_events"] = "created"
    except Exception as e:
        results["email_engagement_events"] = f"error: {e}"

    # ── email_tracking_link_registry ────────────────────────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS email_tracking_link_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_message_id INTEGER NOT NULL,
                original_url TEXT NOT NULL,
                link_hash TEXT NOT NULL,
                link_label TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                FOREIGN KEY (tracking_message_id) REFERENCES email_tracking_messages(id)
            )
        """)
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_link_registry_hash
            ON email_tracking_link_registry(tracking_message_id, link_hash)
        """)
        results["email_tracking_link_registry"] = "created"
    except Exception as e:
        results["email_tracking_link_registry"] = f"error: {e}"

    # ── plunk_poc_events (isolated, never production) ─────
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS plunk_poc_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_token_hash TEXT NOT NULL,
                lead_id INTEGER DEFAULT 0,
                organization_key TEXT DEFAULT '',
                plan_entry_id TEXT DEFAULT '',
                plan_id TEXT DEFAULT '',
                send_log_id INTEGER DEFAULT 0,
                smtp_message_id TEXT DEFAULT '',
                message_type TEXT DEFAULT 'new_outreach',
                provider TEXT DEFAULT 'plunk_poc',
                tracking_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT '',
                activated_at TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                is_test INTEGER NOT NULL DEFAULT 1,
                last_event_type TEXT DEFAULT '',
                last_event_at TEXT DEFAULT '',
                event_count INTEGER DEFAULT 0
            )
        """)
        results["plunk_poc_events"] = "created"
    except Exception as e:
        results["plunk_poc_events"] = f"error: {e}"

    # ── Alter existing tables (safe, idempotent) ────────────
    alter_columns = {
        "leads": [
            ("engagement_score", "INTEGER DEFAULT 0"),
            ("first_open_signal_at", "TEXT DEFAULT ''"),
            ("last_open_signal_at", "TEXT DEFAULT ''"),
            ("open_signal_count", "INTEGER DEFAULT 0"),
            ("first_click_at", "TEXT DEFAULT ''"),
            ("last_click_at", "TEXT DEFAULT ''"),
            ("click_count", "INTEGER DEFAULT 0"),
        ],
        "send_log": [
            ("tracking_token_hash", "TEXT DEFAULT ''"),
        ],
    }

    for table, columns in alter_columns.items():
        existing = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
        for col_name, col_def in columns:
            if col_name not in existing:
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    results[f"{table}.{col_name}"] = "added"
                except Exception as e:
                    results[f"{table}.{col_name}"] = f"error: {e}"
            else:
                results[f"{table}.{col_name}"] = "already exists"

    conn.commit()
    return results


def verify(conn: sqlite3.Connection) -> bool:
    """Run integrity check and verify all tables exist."""
    c = conn.cursor()
    ic = c.execute("PRAGMA integrity_check").fetchone()
    if ic[0] != "ok":
        print(f"INTEGRITY FAIL: {ic}")
        return False

    required = [
        "email_tracking_messages",
        "email_engagement_events",
        "email_tracking_link_registry",
        "plunk_poc_events",
    ]
    existing = {
        row[0] for row in
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = [t for t in required if t not in existing]
    if missing:
        print(f"MISSING TABLES: {missing}")
        return False

    # Verify leads columns
    lead_cols = {row[1] for row in c.execute("PRAGMA table_info(leads)")}
    required_cols = {
        "engagement_score", "first_open_signal_at", "last_open_signal_at",
        "open_signal_count", "tracking_token_hash",
    }
    # tracking_token_hash is in send_log, not leads
    send_log_cols = {row[1] for row in c.execute("PRAGMA table_info(send_log)")}
    send_req = {"tracking_token_hash"}

    lead_missing = {"engagement_score", "first_open_signal_at", "last_open_signal_at", "open_signal_count"} - lead_cols
    send_missing = send_req - send_log_cols

    if lead_missing:
        print(f"MISSING LEAD COLS: {lead_missing}")
        return False
    if send_missing:
        print(f"MISSING SEND_LOG COLS: {send_missing}")
        return False

    return True


if __name__ == "__main__":
    db_path = None
    if "--conn" in sys.argv:
        idx = sys.argv.index("--conn")
        db_path = sys.argv[idx + 1]
    else:
        # Default to production path
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base, "data", "bd_leads.db")

    print(f"Migrating: {db_path}")
    conn = sqlite3.connect(db_path)
    results = migrate(conn)

    for k, v in sorted(results.items()):
        print(f"  {k}: {v}")

    ok = verify(conn)
    print(f"\nVerification: {'PASS' if ok else 'FAIL'}")
    conn.close()
