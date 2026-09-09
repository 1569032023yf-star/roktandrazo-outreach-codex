"""
Roktandrazo BD Outreach - Database (Closed-Loop Version + Manual Fields)
支持完整闭环：收集 → 草稿 → 审核 → 发送 → 回复/退信/退订 → 状态更新
v2.0: 新增 manual_ 字段、approved_manual_send 池、发送前检查
"""

import sqlite3
import os
import re as _re
import hashlib
from datetime import datetime
from history_crosscheck import cross_check

if os.path.exists(os.path.join(os.path.dirname(__file__), ".development-copy")):
    from development_safety import install as _install_development_safety
    _install_development_safety()

DB_PATH = os.getenv("WORKBUDDY_BD_DB_PATH") or os.path.join(os.path.dirname(__file__), "data", "bd_leads.db")


def get_db():
    uri = str(DB_PATH).startswith("file:")
    if os.getenv("ROKT_DEVELOPMENT_ONLY") == "1":
        from development_safety import assert_safe_database_path
        safe_path = assert_safe_database_path(DB_PATH)
        if safe_path is not None and not uri:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        parent = os.path.dirname(DB_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, uri=uri)
    conn.row_factory = sqlite3.Row
    if not (uri and "mode=ro" in str(DB_PATH)):
        conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ---- 主线索表（CREATE 用于新库，ALTER 向下兼容旧库） ----
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
        email_subject TEXT,
        email_body TEXT,
        collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_checked_at TIMESTAMP,
        sent_at TIMESTAMP,
        replied_at TIMESTAMP,
        bounced_at TIMESTAMP,
        unsubscribed_at TIMESTAMP,
        last_followup_at TIMESTAMP,
        followup_count INTEGER DEFAULT 0,
        notes TEXT,
        error_message TEXT,
        domain_hash TEXT,
        email_source_type TEXT DEFAULT 'unknown',
        email_verified_on_official_site INTEGER DEFAULT 0,
        mx_provider TEXT DEFAULT '',
        campaign TEXT DEFAULT '',
        template_id TEXT DEFAULT '',
        priority TEXT DEFAULT 'normal',
        UNIQUE(domain_hash)
    )
    """)

    # --- 安全迁移：添加 manual_ 列（如果不存在） ---
    _migrate_manual_columns(c)

    c.execute("""
    CREATE TABLE IF NOT EXISTS suppression_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        reason TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS send_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        email TEXT,
        subject TEXT,
        status TEXT,
        error_message TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bounce_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        email TEXT,
        domain TEXT,
        campaign TEXT,
        bounce_received_at TEXT,
        status_code TEXT,
        diag TEXT,
        bounce_type TEXT DEFAULT 'unknown',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
        "CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(confidence_score)",
        "CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads(domain_hash)",
        "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)",
        "CREATE INDEX IF NOT EXISTS idx_send_log_lead ON send_log(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_suppression_email ON suppression_list(email)",
        "CREATE INDEX IF NOT EXISTS idx_bounce_email ON bounce_log(email)",
    ]:
        try:
            c.execute(idx)
        except Exception:
            pass

    # ---- v3.1: system_state table ----
    c.execute("""
    CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---- v3.1: job_runs table ----
    c.execute("""
    CREATE TABLE IF NOT EXISTS job_runs (
        run_id TEXT PRIMARY KEY,
        stage TEXT NOT NULL,
        business_date TEXT NOT NULL,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP,
        status TEXT DEFAULT 'running',
        target INTEGER DEFAULT 0,
        actual INTEGER DEFAULT 0,
        gap INTEGER DEFAULT 0,
        current_step TEXT,
        stop_reason TEXT,
        error TEXT,
        process_id INTEGER,
        dry_run INTEGER DEFAULT 1
    )
    """)
    for jidx in [
        "CREATE INDEX IF NOT EXISTS idx_job_runs_date ON job_runs(business_date)",
        "CREATE INDEX IF NOT EXISTS idx_job_runs_stage ON job_runs(stage, business_date)",
    ]:
        try:
            c.execute(jidx)
        except Exception:
            pass

    ensure_default_state(conn)
    conn.commit()
    conn.close()
    print("[DB] Database initialized (v3.1 with system_state + job_runs)")


def _migrate_manual_columns(c):
    """Add manual_ columns if they don't already exist (safe migration)."""
    c.execute("PRAGMA table_info(leads)")
    existing = {row[1] for row in c.fetchall()}
    manual_cols = [
        ("manual_found_email", "TEXT"),
        ("manual_email_source_url", "TEXT"),
        ("manual_email_source_type", "TEXT"),
        ("manual_decision", "TEXT"),
        ("manual_note", "TEXT"),
        ("manual_verified_by", "TEXT DEFAULT 'user'"),
        ("manual_verified_at", "TIMESTAMP"),
    ]
    for col_name, col_type in manual_cols:
        if col_name not in existing:
            try:
                c.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
                print(f"  [MIGRATE] Added column: {col_name}")
            except Exception as e:
                print(f"  [MIGRATE] Warning adding {col_name}: {e}")
    c.execute("PRAGMA table_info(leads)")
    final_cols = {row[1] for row in c.fetchall()}
    all_manual = [c for c in final_cols if c.startswith("manual_")]
    print(f"  [MIGRATE] Manual columns present: {all_manual}")


def _domain_hash(website: str) -> str:
    if not website:
        return ""
    domain = website.lower().strip()
    domain = domain.replace("https://", "").replace("http://", "").replace("www.", "")
    domain = domain.split("/")[0].split("?")[0].split("#")[0]
    return domain


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def _identity_hash(lead: dict) -> str:
    raw = "|".join(str(lead.get(k, "") or "").strip().lower() for k in ("store_name", "city", "state", "official_website"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _domain_identity_key(domain: str, lead: dict) -> str:
    if not domain:
        return f"{lead.get('store_name', '').lower().strip()}_{lead.get('city', '').lower().strip()}"
    if lead.get("allow_same_domain_locations"):
        name = _re.sub(r"\W+", "", str(lead.get("store_name", "")).lower())
        city = _re.sub(r"\W+", "", str(lead.get("city", "")).lower())
        state = _re.sub(r"\W+", "", str(lead.get("state", "")).lower())
        return f"{domain}|{name}|{city}|{state}"
    return domain


def insert_lead(lead: dict, conn: sqlite3.Connection | None = None) -> int | None:
    owns_conn = conn is None
    conn = conn or get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    website = lead.get("official_website", "")
    domain = lead.get("domain_hash") or _domain_identity_key(_domain_hash(website), lead)
    try:
        history = cross_check(conn, {**lead, "domain_hash": domain})

        # Allow new locations of same organization and related locations through.
        # Contact form pool leads can be created even if previously sent
        # (they carry history_status in notes, not eligible for auto-send)
        ALLOW_INSERT = {'new_candidate', 'same_organization_new_location', 'related_location'}
        is_contact_form = lead.get('status') == 'contact_form_pool'

        if history['result'] not in ALLOW_INSERT and not (is_contact_form and history['result'] == 'previously_sent'):
            related = history.get('related_leads', [])
            if related:
                # Preserve the existing lead and attach review context; do not create a second sender.
                existing_id = related[0]['id']
                updates = ["last_checked_at=?", "notes=COALESCE(notes,'') || ?"]
                values: list[object] = [
                    datetime.now().isoformat(),
                    f" [history_crosscheck:{history['result']} candidate_email={lead.get('email','')}]",
                ]
                lead_cols = _columns(conn, "leads")
                if history["result"] == "identity_duplicate_new_email":
                    if "review_status" in lead_cols:
                        updates.append("review_status=?")
                        values.append("identity_review")
                    if "review_reason_code" in lead_cols:
                        updates.append("review_reason_code=?")
                        values.append("identity_duplicate_new_email")
                    if "status" in lead_cols:
                        updates.append("status=?")
                        values.append("manual_review_needed")
                values.append(existing_id)
                c.execute(f"UPDATE leads SET {', '.join(updates)} WHERE id=?", values)
                if owns_conn:
                    conn.commit()
            return None
        table_cols = _columns(conn, "leads")
        values_by_col = {
            "store_name": lead.get("store_name"),
            "store_type": lead.get("store_type"),
            "city": lead.get("city"),
            "state": lead.get("state"),
            "official_website": lead.get("official_website"),
            "formatted_address": lead.get("formatted_address"),
            "normalized_address": lead.get("normalized_address"),
            "phone": lead.get("phone"),
            "normalized_phone": lead.get("normalized_phone"),
            "contact_page": lead.get("contact_page"),
            "wholesale_or_vendor_page": lead.get("wholesale_or_vendor_page"),
            "email": lead.get("email"),
            "email_type": lead.get("email_type"),
            "contact_form_url": lead.get("contact_form_url"),
            "evidence_url": lead.get("evidence_url"),
            "source_keyword": lead.get("source_keyword"),
            "source_platform": lead.get("source_platform"),
            "fit_reason": lead.get("fit_reason"),
            "product_fit": lead.get("product_fit"),
            "confidence_score": lead.get("confidence_score"),
            "status": lead.get("status", "new"),
            "notes": lead.get("notes"),
            "domain_hash": domain,
            "lead_identity_hash": lead.get("lead_identity_hash") or _identity_hash(lead),
            "email_source_type": lead.get("email_source_type", "unknown"),
            "email_verified_on_official_site": int(bool(lead.get("email_verified_on_official_site", 0))),
            "evidence_snippet": lead.get("evidence_snippet", ""),
            "evidence_method": lead.get("evidence_method", ""),
            "review_status": lead.get("review_status", "pending"),
            "review_reason_code": lead.get("review_reason_code", ""),
            "review_reason_detail": lead.get("review_reason_detail", ""),
            "auto_sendable": int(bool(lead.get("auto_sendable", 0))),
            "manual_sendable": int(bool(lead.get("manual_sendable", 0))),
            "organization_key": lead.get("organization_key", ""),
            "recipient_timezone": lead.get("recipient_timezone", ""),
            "timezone_status": lead.get("timezone_status", "TIMEZONE_UNRESOLVED"),
            "collected_at": lead.get("collected_at") or datetime.now().isoformat(),
            "last_checked_at": lead.get("last_checked_at") or datetime.now().isoformat(),
        }
        insert_cols = [col for col in values_by_col if col in table_cols]
        placeholders = ", ".join("?" for _ in insert_cols)
        c.execute(
            f"INSERT OR IGNORE INTO leads ({', '.join(insert_cols)}) VALUES ({placeholders})",
            tuple(values_by_col[col] for col in insert_cols),
        )
        if owns_conn:
            conn.commit()
        if c.lastrowid and c.rowcount > 0:
            print(f"  [+] {lead.get('store_name')} ({lead.get('city')}, {lead.get('state')})")
            return c.lastrowid
        return None
    except sqlite3.IntegrityError:
        return None
    finally:
        if owns_conn:
            conn.close()


def get_leads_by_status(status: str, limit: int = 100) -> list[dict]:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE status = ? ORDER BY confidence_score ASC, collected_at DESC LIMIT ?", (status, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_approved_leads(limit: int = 5) -> list[dict]:
    """Get leads ready to send (approved, has email, not suppressed, not already sent)"""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT * FROM leads
    WHERE status = 'approved'
    AND email IS NOT NULL AND email != ''
    AND email NOT IN (SELECT email FROM suppression_list)
    AND id NOT IN (SELECT lead_id FROM send_log WHERE status = 'sent')
    ORDER BY confidence_score ASC
    LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_lead_status(lead_id: int, status: str, **kwargs):
    """Update lead status and optional fields"""
    conn = get_db()
    c = conn.cursor()
    fields = ["status = ?", "last_checked_at = ?"]
    values = [status, datetime.now().isoformat()]

    for key in ["email_subject", "email_body", "sent_at", "replied_at",
                "bounced_at", "unsubscribed_at", "last_followup_at",
                "followup_count", "error_message", "notes"]:
        if key in kwargs:
            fields.append(f"{key} = ?")
            values.append(kwargs[key])

    values.append(lead_id)
    c.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def add_to_suppression(email: str, reason: str = "unsubscribed"):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO suppression_list (email, reason) VALUES (?, ?)", (email, reason))
    conn.commit()
    conn.close()


def is_suppressed(email: str) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM suppression_list WHERE email = ?", (email,))
    result = c.fetchone()[0] > 0
    conn.close()
    return result


def log_send(lead_id: int, email: str, subject: str, status: str, error_message: str = None,
             message_id: str = None, template_id: str = None, customer_type: str = None,
             routing_reason: str = None, batch_id: str = None, source_platform: str = None,
             message_type: str = None, outreach_batch_date: str = None, plan_entry_id: int = None):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    INSERT INTO send_log (lead_id, email, subject, status, error_message,
                          message_id, template_id, customer_type, routing_reason, batch_id, source_platform,
                          message_type, outreach_batch_date, plan_entry_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (lead_id, email, subject, status, error_message,
           message_id, template_id, customer_type, routing_reason, batch_id, source_platform,
           message_type, outreach_batch_date, plan_entry_id))
    conn.commit()
    conn.close()


def get_stats() -> dict:
    conn = get_db()
    c = conn.cursor()
    stats = {}
    c.execute("SELECT COUNT(*) FROM leads"); stats["total"] = c.fetchone()[0]
    c.execute("SELECT status, COUNT(*) FROM leads GROUP BY status"); stats["by_status"] = dict(c.fetchall())
    c.execute("SELECT confidence_score, COUNT(*) FROM leads GROUP BY confidence_score"); stats["by_score"] = dict(c.fetchall())
    c.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''"); stats["with_email"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM suppression_list"); stats["suppressed"] = c.fetchone()[0]
    c.execute("SELECT status, COUNT(*) FROM send_log GROUP BY status"); stats["send_log"] = dict(c.fetchall())
    conn.close()
    return stats


# ============================================================
# 新增: approved_manual_send 池查询
# ============================================================

def get_approved_manual_send_leads(limit: int = 5) -> list[dict]:
    """Get leads in approved_manual_send status, ready for sending.
    Includes all safety checks: suppression, sent_log, bounce_log.
    """
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    SELECT * FROM leads
    WHERE status = 'approved_manual_send'
    AND email IS NOT NULL AND email != ''
    AND email NOT IN (SELECT email FROM suppression_list)
    AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent', 'bounced'))
    AND id NOT IN (SELECT lead_id FROM bounce_log)
    ORDER BY manual_verified_at ASC, collected_at ASC
    LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sendable_leads(limit: int = 20, exclude_ids: list = None, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Get automatic-send candidates only.
    Includes full safety chain: auto_sendable / suppression / sent_log / bounce / unsubscribe / manual queue.
    Returns up to `limit` leads.
    """
    owns_conn = conn is None
    conn = conn or get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    lead_cols = _columns(conn, "leads")
    required = {
        "status", "confidence_score", "auto_sendable", "email_verified_on_official_site",
        "email_source_type", "email", "official_website", "evidence_url",
        "evidence_snippet", "evidence_method", "unsubscribed_at",
    }
    if not required.issubset(lead_cols):
        if owns_conn:
            conn.close()
        return []

    clauses = [
        "status = 'new'",
        "confidence_score = 'A'",
        "COALESCE(auto_sendable,0) = 1",
        "COALESCE(email_verified_on_official_site,0) = 1",
        "email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page')",
        "email IS NOT NULL AND TRIM(email) != ''",
        "official_website IS NOT NULL AND TRIM(official_website) != ''",
        "evidence_url IS NOT NULL AND TRIM(evidence_url) != ''",
        "evidence_snippet IS NOT NULL AND TRIM(evidence_snippet) != ''",
        "evidence_method IS NOT NULL AND TRIM(evidence_method) != ''",
        "unsubscribed_at IS NULL",
    ]
    params: list[object] = []
    if exclude_ids:
        clauses.append(f"id NOT IN ({','.join('?' for _ in exclude_ids)})")
        params.extend(exclude_ids)
    if _table_exists(conn, "suppression_list"):
        clauses.append("NOT EXISTS (SELECT 1 FROM suppression_list sl WHERE lower(sl.email)=lower(leads.email))")
    if _table_exists(conn, "manual_send_queue"):
        clauses.append("NOT EXISTS (SELECT 1 FROM manual_send_queue mq WHERE mq.lead_id=leads.id AND COALESCE(mq.status,'') NOT IN ('rejected','cancelled','consumed'))")
    if _table_exists(conn, "bounce_log"):
        bounce_cols = _columns(conn, "bounce_log")
        bounce_match = []
        if "lead_id" in bounce_cols:
            bounce_match.append("b.lead_id=leads.id")
        if "email" in bounce_cols:
            bounce_match.append("lower(b.email)=lower(leads.email)")
        if bounce_match:
            if "bounce_type" in bounce_cols:
                clauses.append(
                    f"""NOT EXISTS (
                        SELECT 1 FROM bounce_log b
                        WHERE ({' OR '.join(bounce_match)})
                        AND lower(COALESCE(b.bounce_type,'')) IN ('hard','policy','permanent')
                    )"""
                )
            else:
                clauses.append(f"NOT EXISTS (SELECT 1 FROM bounce_log b WHERE ({' OR '.join(bounce_match)}))")
    if _table_exists(conn, "send_log"):
        send_cols = _columns(conn, "send_log")
        send_match = []
        if "lead_id" in send_cols:
            send_match.append("s.lead_id=leads.id")
        if "email" in send_cols:
            send_match.append("lower(s.email)=lower(leads.email)")
        if send_match:
            message_type_clause = "AND COALESCE(s.message_type,'new_outreach')='new_outreach'" if "message_type" in send_cols else ""
            clauses.append(
                f"""NOT EXISTS (
                    SELECT 1 FROM send_log s
                    WHERE s.status='sent' AND ({' OR '.join(send_match)})
                    {message_type_clause}
                )"""
            )
    if "bounced_at" in lead_cols:
        clauses.append("bounced_at IS NULL")
    if "mx_provider" in lead_cols:
        clauses.append(
            "(mx_provider IS NULL OR mx_provider = '' OR "
            "(mx_provider NOT LIKE '%exchange%' AND mx_provider NOT LIKE '%outlook%' AND mx_provider NOT LIKE '%microsoft%'))"
        )

    params.append(limit)
    sql = f"""
        SELECT * FROM leads
        WHERE {' AND '.join(clauses)}
        ORDER BY collected_at ASC
        LIMIT ?
    """
    result = [dict(r) for r in c.execute(sql, params).fetchall()]
    if owns_conn:
        conn.close()
    return result


# ============================================================
# 发送前安全检查
# ============================================================

def check_sent_log(email: str) -> bool:
    """Check if an email has already been sent (based on send_log)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM send_log WHERE email = ? AND status = 'sent'", (email,))
    result = c.fetchone()[0] > 0
    conn.close()
    return result


def check_domain_sent(domain: str) -> bool:
    """Check if any email from this domain has already been sent."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM send_log WHERE email LIKE ? AND status = 'sent'", (f'%@{domain}',))
    result = c.fetchone()[0] > 0
    conn.close()
    return result


def check_bounce_history(email: str) -> dict:
    """Check bounce history for an email. Returns {'hard': bool, 'policy': bool, 'detail': str}."""
    conn = get_db()
    c = conn.cursor()
    result = {"hard": False, "policy": False, "detail": ""}
    c.execute("SELECT bounce_type, diagnostic_code FROM bounce_log WHERE email = ? ORDER BY bounce_received_at DESC LIMIT 1", (email,))
    row = c.fetchone()
    if row:
        result["hard"] = row[0] == 'hard'
        result["policy"] = row[0] == 'policy'
        result["detail"] = row[1] or ""
    conn.close()
    return result


def check_mx_provider(domain: str) -> str:
    """Check MX provider category for a domain.
    Returns: 'exchange' / 'google' / 'other' / 'no_mx'
    Falls back to empty string if DNS lookup fails (non-blocking).
    """
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX')
        mx_str = ' '.join([str(x.exchange).lower() for x in answers])
        if any(k in mx_str for k in ['outlook', 'protection.outlook', 'microsoft', 'exchange']):
            return 'exchange'
        elif 'google' in mx_str:
            return 'google'
        return 'other'
    except Exception:
        return 'no_mx'


def is_exchange_mx(email: str) -> bool:
    """Check if the email's MX is Exchange / Microsoft 365 (high bounce risk)."""
    domain = email.split('@')[1] if '@' in email else ''
    if not domain:
        return False
    mx = check_mx_provider(domain)
    return mx == 'exchange'


def update_manual_approval(lead_id: int, manual_fields: dict):
    """Update manual approval fields for a lead. Safe to call multiple times."""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    fields = ["last_checked_at = ?"]
    values = [now]
    for key in ["manual_found_email", "manual_email_source_url", "manual_email_source_type",
                 "manual_decision", "manual_note", "manual_verified_by", "manual_verified_at"]:
        if key in manual_fields:
            fields.append(f"{key} = ?")
            values.append(manual_fields[key])
    if "manual_verified_at" not in manual_fields and "manual_decision" in manual_fields:
        fields.append("manual_verified_at = ?")
        values.append(now)
    values.append(lead_id)
    c.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_config(key: str) -> str | None:
    """Get a value from system_config table."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM system_config WHERE key = ?", (key,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None


def set_config(key: str, value: str):
    """Set a value in system_config table."""
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, datetime('now'))",
              (key, value))
    conn.commit()
    conn.close()


# ============================================================
# v3.0: Independent State Model — Risk Circuit Breaker Fix
# ============================================================

def get_execution_mode() -> str:
    """Get current execution mode. Defaults to 'status_query'."""
    return get_config('execution_mode') or 'status_query'

def set_execution_mode(mode: str):
    """Set execution mode for current run.
    Valid: status_query, inventory_recovery, shadow_run, daily_outreach, manual_live.
    This is per-run, NOT persistent across sessions.
    """
    valid_modes = {'status_query', 'inventory_recovery', 'shadow_run', 'daily_outreach', 'manual_live'}
    if mode not in valid_modes:
        raise ValueError(f"Invalid execution_mode: {mode}. Must be one of {valid_modes}")
    set_config('execution_mode', mode)

def get_standing_authorization() -> bool:
    """Check if standing daily outreach authorization is active."""
    return get_config('standing_authorization') == 'true'

def set_standing_authorization(enabled: bool):
    """Set standing authorization. Only the USER can change this.
    Automation must NEVER set this to false.
    """
    set_config('standing_authorization', 'true' if enabled else 'false')
    if not enabled:
        set_config('manual_pause', 'true')

def get_manual_pause() -> bool:
    """Check if USER has manually paused the scheduler."""
    return get_config('manual_pause') == 'true'

def set_manual_pause(paused: bool, reason: str = ''):
    """Set manual pause. Only the USER can set this to true.
    Automation must NEVER call this with paused=True.
    """
    set_config('manual_pause', 'true' if paused else 'false')
    if reason:
        set_config('manual_pause_reason', reason)

def get_scheduler_enabled() -> bool:
    """Check if the scheduler is enabled. This is the production authority."""
    return get_config('scheduler_enabled') != 'false'

def set_scheduler_enabled(enabled: bool):
    """Enable or disable the production scheduler."""
    set_config('scheduler_enabled', 'true' if enabled else 'false')

def get_risk_gate() -> dict:
    """Get current risk gate state.
    Returns dict with keys: status, reason, created_at, cooldown_until.
    status values: 'clear', 'temporary_block', 'permanent_block'
    """
    return {
        'status': get_config('risk_gate_status') or 'clear',
        'reason': get_config('risk_gate_reason') or '',
        'created_at': get_config('risk_gate_created_at') or '',
        'cooldown_until': get_config('risk_cooldown_until') or '',
    }

def set_risk_gate(status: str, reason: str, cooldown_hours: int = 20):
    """Set a temporary risk block. Does NOT pause the scheduler.
    status: 'temporary_block' or 'clear'
    cooldown_hours: default 20h (covers until next day's 08:30 risk review).
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    cooldown = now + timedelta(hours=cooldown_hours)
    set_config('risk_gate_status', status)
    set_config('risk_gate_reason', reason)
    set_config('risk_gate_created_at', now.strftime('%Y-%m-%d %H:%M:%S'))
    set_config('risk_cooldown_until', cooldown.strftime('%Y-%m-%d %H:%M:%S'))

def clear_risk_gate():
    """Clear the risk gate. Called by auto-recovery or user action."""
    set_config('risk_gate_status', 'clear')
    set_config('risk_gate_reason', '')
    set_config('risk_gate_created_at', '')
    set_config('risk_cooldown_until', '')

def is_risk_gate_active() -> bool:
    """Check if risk gate is currently blocking sends."""
    gate = get_risk_gate()
    if gate['status'] != 'temporary_block':
        return False
    # Check cooldown
    if gate['cooldown_until']:
        from datetime import datetime
        try:
            cooldown = datetime.strptime(gate['cooldown_until'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() >= cooldown:
                # Cooldown expired, auto-clear
                clear_risk_gate()
                return False
        except ValueError:
            pass
    return True

def can_send_live() -> tuple[bool, str]:
    """Comprehensive check: can we send emails right now?
    Returns (can_send, block_reason).
    Checks: manual_pause, risk_gate, send_pause, standing_authorization.
    """
    if get_manual_pause():
        return False, 'manual_pause_active'
    if is_risk_gate_active():
        gate = get_risk_gate()
        return False, f'risk_gate_{gate["status"]}: {gate["reason"]}'
    if get_config('send_pause') == 'true':
        return False, f'send_pause: {get_config("pause_reason") or "unknown"}'
    if not get_standing_authorization():
        return False, 'standing_authorization_disabled'
    return True, ''

# ============================================================
# Run Lock — prevent duplicate daily_outreach runs
# ============================================================

def check_run_lock(date_str: str = None) -> tuple[bool, str]:
    """Check if a daily_outreach run is already active for today.
    Returns (locked, lock_holder).
    """
    if date_str is None:
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
    lock_key = f'run_lock:daily_outreach:{date_str}'
    existing = get_config(lock_key)
    if existing and existing not in ('', 'released'):
        return True, existing
    return False, ''

def acquire_run_lock(date_str: str = None, holder: str = 'daily_operator', stale_after_seconds: int = 7200) -> bool:
    """Atomically acquire a named run lock using UTC timestamps."""
    from datetime import datetime, timezone
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    lock_key = f'run_lock:daily_outreach:{date_str}'
    acquired_key = f'{lock_key}_acquired_at'
    conn = get_db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT value FROM system_config WHERE key=?", (lock_key,)).fetchone()
        existing = row[0] if row else ''
        stamp_row = conn.execute("SELECT value FROM system_config WHERE key=?", (acquired_key,)).fetchone()
        stale = False
        if existing and existing != 'released':
            try:
                acquired_at = datetime.strptime(stamp_row[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                stale = (datetime.now(timezone.utc) - acquired_at).total_seconds() > stale_after_seconds
            except (TypeError, ValueError, IndexError):
                stale = False
            if not stale:
                conn.rollback()
                return False
        now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        upsert = "INSERT INTO system_config(key,value,updated_at) VALUES(?,?,datetime('now')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at"
        conn.execute(upsert, (lock_key, holder))
        conn.execute(upsert, (acquired_key, now_utc))
        conn.commit()
        if stale:
            print(f"[LOCK] Overrode stale UTC lock (holder={existing})")
        return True
    finally:
        conn.close()

def release_run_lock(date_str: str = None, holder: str | None = None) -> bool:
    """Release only a lock owned by ``holder``; return whether it changed."""
    if date_str is None:
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
    lock_key = f'run_lock:daily_outreach:{date_str}'
    if not holder:
        return False
    conn = get_db()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE system_config SET value='released',updated_at=datetime('now') WHERE key=? AND value=?",
                (lock_key, holder),
            )
        return cur.rowcount == 1
    finally:
        conn.close()

# ============================================================
# Unified Daily Send Fact Source
# ============================================================

def get_today_sent_asia_shanghai() -> int:
    """Get today's actually-sent count from send_log.
    Uses Asia/Shanghai day boundary (UTC+8).
    This is the SINGLE SOURCE OF TRUTH for daily send count.
    """
    from outreach_control import outreach_batch_date
    today_shanghai = outreach_batch_date()
    conn = get_db()
    c = conn.cursor()
    # New outreach is counted by the 23:00 batch date, not the calendar date.
    sent = c.execute(
        "SELECT COUNT(*) FROM send_log WHERE outreach_batch_date = ? AND status = 'sent' AND message_type = 'new_outreach'",
        (today_shanghai,)
    ).fetchone()[0]
    conn.close()
    return sent

def get_daily_target() -> int:
    """Get the daily send target."""
    target = get_config('daily_run_target') or '40'
    return int(target)

def get_daily_gap() -> int:
    """Get the gap between target and actual sends today."""
    sent = get_today_sent_asia_shanghai()
    target = get_daily_target()
    return max(0, target - sent)


def get_batch_send_counts(batch_date: str) -> dict:
    """Return successful sends split by message type for one immutable outreach batch."""
    conn = get_db()
    rows = conn.execute("""
        SELECT message_type, COUNT(*) AS count FROM send_log
        WHERE status='sent' AND outreach_batch_date=?
        GROUP BY message_type
    """, (batch_date,)).fetchall()
    conn.close()
    counts = {row['message_type']: row['count'] for row in rows}
    return {'new_outreach': counts.get('new_outreach', 0), 'follow_up': counts.get('follow_up', 0)}

def get_scheduler_state() -> dict:
    """Get complete scheduler state for reporting."""
    return {
        'scheduler_enabled': get_scheduler_enabled(),
        'manual_pause': get_manual_pause(),
        'manual_pause_reason': get_config('manual_pause_reason') or '',
        'standing_authorization': get_standing_authorization(),
        'execution_mode': get_execution_mode(),
        'risk_gate': get_risk_gate(),
        'send_pause': get_config('send_pause') or 'false',
        'pause_reason': get_config('pause_reason') or '',
        'daily_run_date': get_config('daily_run_date') or '',
        'daily_run_status': get_config('daily_run_status') or 'not_started',
        'daily_run_target': get_daily_target(),
        'daily_run_actual': get_today_sent_asia_shanghai(),
        'daily_run_gap': get_daily_gap(),
        'production_scheduler_authority': get_config('production_scheduler_authority') or 'workbuddy_automation',
    }

# ============================================================
# System State — persistent production state
# ============================================================

def set_state(key: str, value: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, datetime('now'))",
              (key, str(value)))
    conn.commit()
    conn.close()

def get_state(key: str, default: str = '') -> str:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM system_state WHERE key = ?", (key,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else default

# ============================================================
# Job Runs — audit trail for every orchestrator execution
# ============================================================

def start_job_run(
    run_id: str,
    stage: str,
    business_date: str,
    target: int = 0,
    dry_run: bool = True,
    *,
    stale_after_seconds: int = 7200,
    now_utc=None,
) -> bool:
    """Atomically replace a stale active run or reject a fresh duplicate.

    Stale cleanup and replacement insertion deliberately share one
    ``BEGIN IMMEDIATE`` transaction.  ``now_utc`` is a test seam only; normal
    callers always use the current UTC clock.
    """
    import os as _os
    from datetime import datetime, timezone

    clock = now_utc or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    else:
        clock = clock.astimezone(timezone.utc)
    conn = get_db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        c = conn.cursor()
        existing = c.execute(
            "SELECT run_id, started_at FROM job_runs WHERE stage=? AND business_date=? AND status='running'",
            (stage, business_date),
        ).fetchone()
        if existing:
            started = existing[1]
            if not started:
                conn.rollback()
                return False
            try:
                started_utc = datetime.strptime(started, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                conn.rollback()
                return False
            if (clock - started_utc).total_seconds() <= int(stale_after_seconds):
                conn.rollback()
                return False
            c.execute(
                "UPDATE job_runs SET status='failed', stop_reason='stale_cleanup', finished_at=? WHERE run_id=?",
                (clock.strftime('%Y-%m-%d %H:%M:%S'), existing[0]),
            )
        c.execute(
            """INSERT INTO job_runs
               (run_id, stage, business_date, started_at, status, target, current_step, process_id, dry_run)
               VALUES (?, ?, ?, ?, 'running', ?, 'starting', ?, ?)""",
            (
                run_id,
                stage,
                business_date,
                clock.strftime('%Y-%m-%d %H:%M:%S'),
                target,
                _os.getpid(),
                1 if dry_run else 0,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    set_state('current_execution_mode', stage)
    set_state('current_run_id', run_id)
    return True

def update_job_run(run_id: str, **kwargs):
    """Update fields on a job run (current_step, status, actual, gap, stop_reason, error, etc.)."""
    allowed = {'current_step', 'status', 'actual', 'gap', 'stop_reason', 'error', 'target', 'finished_at'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    if 'status' in updates and updates['status'] in ('completed', 'failed', 'stopped', 'partial'):
        updates['finished_at'] = 'datetime("now")'
    conn = get_db()
    c = conn.cursor()
    set_clauses = []
    values = []
    for k, v in updates.items():
        if k == 'finished_at':
            set_clauses.append("finished_at = datetime('now')")
        else:
            set_clauses.append(f"{k} = ?")
            values.append(v)
    values.append(run_id)
    c.execute(f"UPDATE job_runs SET {', '.join(set_clauses)} WHERE run_id = ?", values)
    conn.commit()
    conn.close()

def finish_job_run(run_id: str, status: str, actual: int = 0, gap: int = 0, stop_reason: str = '', error: str = ''):
    """Mark a job run as completed/failed/stopped/partial."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE job_runs SET status=?, finished_at=datetime('now'), actual=?, gap=?, stop_reason=?, error=?
        WHERE run_id=?
    """, (status, actual, gap, stop_reason, error, run_id))
    conn.commit()
    conn.close()

def get_last_successful_run(stage: str) -> str | None:
    """Get the last successful run's timestamp for a stage."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT MAX(finished_at) FROM job_runs WHERE stage=? AND status='completed'", (stage,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

# ============================================================
# Initialize default state explicitly
# ============================================================

def ensure_default_state(conn: sqlite3.Connection | None = None):
    """Ensure the state model has sensible defaults when explicitly initialized."""
    owns_conn = conn is None
    conn = conn or get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    defaults = {
        'standing_authorization': 'true',
        'manual_pause': 'false',
        'scheduler_enabled': 'true',
        'execution_mode': 'status_query',
        'risk_gate_status': 'clear',
    }
    for key, default_value in defaults.items():
        row = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                (key, default_value),
            )
    # Also seed system_state table (safe if table doesn't exist yet)
    state_defaults = {
        'scheduler_enabled': 'true',
        'standing_authorization': 'true',
        'manual_pause': 'false',
        'risk_gate_status': 'clear',
    }
    for key, default_value in state_defaults.items():
        try:
            row = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
            if row is None or not row[0]:
                conn.execute(
                    "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                    (key, default_value),
                )
        except Exception:
            pass  # Table may not exist yet — init_db will create it
    if owns_conn:
        conn.commit()
        conn.close()

# ============================================================
# P0 退信自动回流 —— bounce_pipeline 配套辅助函数
# ============================================================

def record_bounce_log_entry(lead_id, email, bounce_type, diagnostic_code,
                            status_code=None, raw_subject=None,
                            recommended_action=None):
    """幂等插入 bounce_log（同 email + 同 diagnostic_code 不重复插）。

    返回插入行的 id；若已存在则返回既有行的 id。
    """
    conn = get_db()
    c = conn.cursor()
    email = (email or "").strip().lower()
    domain = email.split("@", 1)[1] if "@" in email else ""

    existing = c.execute(
        "SELECT id FROM bounce_log WHERE email = ? "
        "AND diagnostic_code IS NOT DISTINCT FROM ?",
        (email, diagnostic_code),
    ).fetchone()
    if existing:
        conn.close()
        return existing[0]

    now = datetime.now().astimezone().isoformat()
    c.execute(
        """
        INSERT INTO bounce_log (lead_id, email, domain, campaign, bounce_received_at,
                                status_code, diagnostic_code, bounce_type,
                                raw_message_subject, recommended_action, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (lead_id, email, domain, None, now, status_code, diagnostic_code,
         bounce_type, raw_subject, recommended_action, now),
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def get_unmatched_dsn_count(conn=None):
    """返回 unmatched_dsn 表行数。conn 可选，缺省使用默认连接。"""
    owns = conn is None
    conn = conn or get_db()
    try:
        row = conn.execute("SELECT COUNT(*) FROM unmatched_dsn").fetchone()
        return int(row[0]) if row else 0
    finally:
        if owns:
            conn.close()


def list_contact_recovery(limit=50):
    """返回 contact_recovery 表中 status='pending' 的行，按创建时间倒序。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM contact_recovery WHERE status = 'pending' "
            "ORDER BY created_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_contact_recovery_resolved(rec_id):
    """把 contact_recovery 某条记录标记为 resolved，并刷新 updated_at。"""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE contact_recovery SET status = 'resolved', "
            "updated_at = ? WHERE id = ?",
            (datetime.now().astimezone().isoformat(), int(rec_id)),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
