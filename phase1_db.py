"""
Roktandrazo 线索收集系统 - 第一阶段
SQLite 数据库，支持新字段：wholesale_or_vendor_page, product_fit, collected_at, last_checked_at
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "phase1_leads.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_name TEXT NOT NULL,
        store_type TEXT,
        city TEXT,
        state TEXT,
        official_website TEXT,
        contact_page TEXT,
        wholesale_or_vendor_page TEXT,
        email TEXT,
        email_type TEXT,
        contact_form_url TEXT,
        evidence_url TEXT,
        source_keyword TEXT,
        fit_reason TEXT,
        product_fit TEXT,
        confidence_score TEXT,
        status TEXT DEFAULT 'new',
        notes TEXT,
        domain_hash TEXT,
        collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(domain_hash)
    )
    """)

    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)
    """)
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(confidence_score)
    """)
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads(domain_hash)
    """)

    conn.commit()
    conn.close()
    print("[DB] Phase 1 数据库初始化完成")


def _domain_hash(website: str) -> str:
    if not website:
        return ""
    domain = website.lower().strip()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.replace("www.", "")
    domain = domain.split("/")[0]
    domain = domain.split("?")[0]
    domain = domain.split("#")[0]
    return domain


def insert_lead(lead: dict) -> int | None:
    """Deprecated compatibility wrapper; all new leads go through bd_db."""
    from bd_db import insert_lead as canonical_insert_lead

    return canonical_insert_lead(lead)


def get_all_leads(limit: int = 500) -> list[dict]:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY confidence_score ASC, collected_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_leads_by_score(score: str) -> list[dict]:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE confidence_score = ? ORDER BY collected_at DESC", (score,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    conn = get_db()
    c = conn.cursor()
    stats = {}
    c.execute("SELECT COUNT(*) FROM leads"); stats["total"] = c.fetchone()[0]
    c.execute("SELECT confidence_score, COUNT(*) FROM leads GROUP BY confidence_score"); stats["by_score"] = dict(c.fetchall())
    c.execute("SELECT product_fit, COUNT(*) FROM leads GROUP BY product_fit"); stats["by_product_fit"] = dict(c.fetchall())
    c.execute("SELECT city, COUNT(*) FROM leads GROUP BY city ORDER BY COUNT(*) DESC"); stats["by_city"] = dict(c.fetchall())
    c.execute("SELECT status, COUNT(*) FROM leads GROUP BY status"); stats["by_status"] = dict(c.fetchall())
    c.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''"); stats["with_email"] = c.fetchone()[0]
    conn.close()
    return stats


if __name__ == "__main__":
    init_db()
