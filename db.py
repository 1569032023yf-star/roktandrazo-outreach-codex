"""
Roktandrazo Outreach - SQLite Database Layer
所有线索数据持久化存储，支持去重、状态追踪、邮件记录
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "leads.db")


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表"""
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
        email TEXT,
        email_type TEXT,          -- business_email / contact_form_only / phone_only / no_contact_found
        contact_form_url TEXT,
        evidence_url TEXT,
        fit_reason TEXT,
        confidence_score TEXT,     -- A / B / C
        source_keyword TEXT,
        status TEXT DEFAULT 'new', -- new / reviewed / drafted / sent / replied / bounced / unsubscribed / do_not_contact
        notes TEXT,
        domain_hash TEXT,          -- 用于去重
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(domain_hash)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        email_type TEXT,           -- initial / followup_1 / followup_2
        subject TEXT,
        body_text TEXT,
        body_html TEXT,
        sent_at TIMESTAMP,
        status TEXT DEFAULT 'draft', -- draft / queued / sent / failed / bounced / opened / replied
        open_count INTEGER DEFAULT 0,
        reply_received INTEGER DEFAULT 0,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS scrape_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT,
        keyword TEXT,
        stores_found INTEGER DEFAULT 0,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        status TEXT DEFAULT 'running'  -- running / completed / failed
    )
    """)

    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)
    """)
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(confidence_score)
    """)
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)
    """)
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_emails_lead ON emails(lead_id)
    """)
    c.execute("""
    CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status)
    """)

    conn.commit()
    conn.close()
    print("[DB] 数据库初始化完成")


def _domain_hash(website: str) -> str:
    """从网址提取域名用于去重"""
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


def get_leads(status: str = None, score: str = None, limit: int = 100) -> list[dict]:
    """查询线索"""
    conn = get_db()
    c = conn.cursor()

    query = "SELECT * FROM leads WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if score:
        query += " AND confidence_score = ?"
        params.append(score)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_lead_status(lead_id: int, status: str, notes: str = None):
    """更新线索状态"""
    conn = get_db()
    c = conn.cursor()
    if notes:
        c.execute("UPDATE leads SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
                   (status, notes, datetime.now().isoformat(), lead_id))
    else:
        c.execute("UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
                   (status, datetime.now().isoformat(), lead_id))
    conn.commit()
    conn.close()


def insert_email(lead_id: int, email_type: str, subject: str, body_text: str, body_html: str = "") -> int:
    """插入邮件记录"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO emails (lead_id, email_type, subject, body_text, body_html, status)
    VALUES (?, ?, ?, ?, ?, 'draft')
    """, (lead_id, email_type, subject, body_text, body_html))
    conn.commit()
    email_id = c.lastrowid
    conn.close()
    return email_id


def update_email_status(email_id: int, status: str, error_message: str = None):
    """更新邮件状态"""
    conn = get_db()
    c = conn.cursor()
    if status == "sent":
        c.execute("UPDATE emails SET status = ?, sent_at = ? WHERE id = ?",
                   (status, datetime.now().isoformat(), email_id))
    elif error_message:
        c.execute("UPDATE emails SET status = ?, error_message = ? WHERE id = ?",
                   (status, error_message, email_id))
    else:
        c.execute("UPDATE emails SET status = ? WHERE id = ?", (status, email_id))
    conn.commit()
    conn.close()


def get_stats() -> dict:
    """获取统计概览"""
    conn = get_db()
    c = conn.cursor()

    stats = {}

    # 线索总数
    c.execute("SELECT COUNT(*) FROM leads")
    stats["total_leads"] = c.fetchone()[0]

    # 按状态
    c.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
    stats["by_status"] = dict(c.fetchall())

    # 按评分
    c.execute("SELECT confidence_score, COUNT(*) FROM leads GROUP BY confidence_score")
    stats["by_score"] = dict(c.fetchall())

    # 按门店类型
    c.execute("SELECT store_type, COUNT(*) FROM leads GROUP BY store_type ORDER BY COUNT(*) DESC")
    stats["by_store_type"] = dict(c.fetchall())

    # 按州
    c.execute("SELECT state, COUNT(*) FROM leads GROUP BY state ORDER BY COUNT(*) DESC")
    stats["by_state"] = dict(c.fetchall())

    # 有邮箱的
    c.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''")
    stats["with_email"] = c.fetchone()[0]

    # 邮件统计
    c.execute("SELECT status, COUNT(*) FROM emails GROUP BY status")
    stats["email_stats"] = dict(c.fetchall())

    conn.close()
    return stats


def get_leads_ready_for_email(limit: int = 50) -> list[dict]:
    """获取可以发邮件的线索 (有邮箱/有contact form + 评分足够 + 未发送)"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT * FROM leads 
    WHERE status IN ('new', 'reviewed', 'drafted')
    AND confidence_score IN ('A', 'B')
    AND (email IS NOT NULL AND email != '' OR contact_form_url IS NOT NULL AND contact_form_url != '')
    AND id NOT IN (SELECT DISTINCT lead_id FROM emails WHERE email_type = 'initial' AND status IN ('sent', 'queued'))
    ORDER BY confidence_score ASC, created_at ASC
    LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_leads_needing_followup(days_since_sent: int = 5) -> list[dict]:
    """获取需要跟进的线索"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT l.*, e.sent_at as last_sent_at, 
           (SELECT COUNT(*) FROM emails WHERE lead_id = l.id AND status = 'sent') as email_count
    FROM leads l
    JOIN emails e ON l.id = e.lead_id
    WHERE l.status = 'sent'
    AND e.status = 'sent'
    AND e.sent_at < datetime('now', ? || ' days')
    AND (SELECT COUNT(*) FROM emails WHERE lead_id = l.id AND status = 'sent') < 3
    AND l.id NOT IN (SELECT DISTINCT lead_id FROM emails WHERE status = 'replied')
    ORDER BY e.sent_at ASC
    """, (f"-{days_since_sent}",))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print("[DB] 数据库就绪")
