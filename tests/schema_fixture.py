"""Canonical development test database contract / 统一开发测试数据库契约。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import bd_db
from dev_fsp import ensure_schema as ensure_dev_fsp_schema
from migrations.migrate_city_outreach_40 import migrate as migrate_city_outreach
from migrations.migrate_email_tracking import migrate as migrate_email_tracking

SCHEMA_CONTRACT_VERSION = 1

REQUIRED_TABLES = {
    "leads", "send_log", "bounce_log", "suppression_list", "reply_log",
    "system_config", "system_state", "job_runs", "retail_city_queue",
    "lead_discovery_results", "lead_discovery_hits", "lead_discovery_query_state",
    "final_send_plan", "send_authorizations", "send_authorization_entries",
    "email_tracking_messages", "dev_safe_fsp", "test_schema_contract",
}

REQUIRED_COLUMNS = {
    "leads": {
        "organization_key", "recipient_timezone", "timezone_status", "official_website",
        "email", "evidence_url", "evidence_snippet", "evidence_method",
        "email_source_type", "email_verified_on_official_site", "auto_sendable",
    },
    "lead_discovery_results": {
        "business_name", "website", "normalized_domain", "validation_status",
        "evidence_url", "evidence_snippet", "evidence_method", "official_match",
        "linked_lead_id",
    },
    "job_runs": {"run_id", "stage", "business_date", "status"},
    "system_config": {"key", "value", "updated_at"},
    "dev_safe_fsp": {"run_id", "lead_id", "organization_key", "email", "v2_result_json"},
}


def _ensure_runtime_support_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS reply_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER, email TEXT, reply_received_at TEXT, reply_type TEXT,
        summary TEXT, suggested_action TEXT, raw_subject TEXT, processed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS unmatched_dsn (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_message_id TEXT, final_recipient TEXT, original_recipient TEXT,
        x_failed_recipients TEXT, diagnostic_code TEXT, status_code TEXT,
        original_message_id TEXT, original_subject TEXT, original_sent_at TEXT,
        detected_at TEXT, processed_at TEXT, matched_send_log_id INTEGER, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS send_authorizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        authorization_id TEXT UNIQUE, plan_id TEXT, outreach_batch_date TEXT,
        plan_entries_hash TEXT, approved_entry_count INTEGER, database_sha256 TEXT,
        preflight_status TEXT, approved_at TEXT, expires_at TEXT, approved_by TEXT,
        consumed_at TEXT, status TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS send_authorization_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        authorization_id TEXT, plan_entry_id INTEGER, lead_id INTEGER,
        recipient_email TEXT, entry_hash TEXT, consumed_at TEXT, status TEXT,
        UNIQUE(authorization_id, plan_entry_id)
    );
    CREATE TABLE IF NOT EXISTS test_schema_contract (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        version INTEGER NOT NULL
    );
    """)
    conn.execute(
        "INSERT INTO test_schema_contract(singleton,version) VALUES(1,?) "
        "ON CONFLICT(singleton) DO UPDATE SET version=excluded.version",
        (SCHEMA_CONTRACT_VERSION,),
    )
    bounce_columns = {r[1] for r in conn.execute("PRAGMA table_info(bounce_log)")}
    if "diagnostic_code" not in bounce_columns:
        conn.execute("ALTER TABLE bounce_log ADD COLUMN diagnostic_code TEXT")


def assert_schema_contract(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT version FROM test_schema_contract WHERE singleton=1"
    ).fetchone()
    actual_version = None if row is None else int(row[0])
    if actual_version != SCHEMA_CONTRACT_VERSION:
        raise AssertionError(
            f"STALE_TEST_DB_SCHEMA: expected contract {SCHEMA_CONTRACT_VERSION}, got {actual_version}"
        )
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    missing_tables = sorted(REQUIRED_TABLES - tables)
    if missing_tables:
        raise AssertionError(f"STALE_TEST_DB_SCHEMA: missing tables {missing_tables}")
    for table, expected in REQUIRED_COLUMNS.items():
        actual = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        missing = sorted(expected - actual)
        if missing:
            raise AssertionError(f"STALE_TEST_DB_SCHEMA: {table} missing columns {missing}")


def create_test_database(path: str | Path) -> sqlite3.Connection:
    """Create the current isolated schema without using any copied production DB."""
    db_path = Path(path).resolve()
    old_path = bd_db.DB_PATH
    try:
        bd_db.DB_PATH = str(db_path)
        bd_db.init_db()
        migrate_city_outreach(db_path)
    finally:
        bd_db.DB_PATH = old_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_email_tracking(conn)
    ensure_dev_fsp_schema(conn)
    _ensure_runtime_support_tables(conn)
    conn.commit()
    assert_schema_contract(conn)
    return conn
