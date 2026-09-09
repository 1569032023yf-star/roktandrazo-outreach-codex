"""
Roktandrazo BD Outreach - Email Sender (Closed-Loop)
通过腾讯企业邮箱 SMTP 发信，从 .env 读取配置
支持 HTML + 纯文本双格式，Reply-To 头

P0 Gate: All production customer sends require a valid send_authorization.
No authorization = SendAuthorizationError raised, SMTP connection count = 0.
"""
import hashlib
import imaplib
import json
import os
import smtplib
import sqlite3
import ssl
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from env_loader import get_smtp_config, get_sender_info, get_sending_limits, get_test_config, get_imap_config, is_configured, mask
from bd_db import update_lead_status, log_send, add_to_suppression, is_suppressed

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'bd_leads.db')
ASIA_SH = timezone(timedelta(hours=8))


class SendAuthorizationError(Exception):
    """Raised when a production customer send lacks a valid authorization."""
    pass


def validate_send_authorization(authorization_id: str = None, plan_entry_id: int = None,
                                 lead_id: int = None, recipient_email: str = None) -> dict:
    """Validate a send authorization before allowing SMTP.
    
    Supports per-entry consumption via send_authorization_entries table.
    Raises SendAuthorizationError if any check fails.
    """
    if not authorization_id:
        raise SendAuthorizationError("No authorization_id provided.")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        auth = conn.execute(
            "SELECT * FROM send_authorizations WHERE authorization_id=? AND status IN ('approved','in_progress')",
            (authorization_id,)
        ).fetchone()
        
        if not auth:
            raise SendAuthorizationError(f"Authorization {authorization_id} not found or not approved")
        
        expires_at = auth['expires_at']
        if expires_at:
            expiry = datetime.fromisoformat(expires_at)
            now = datetime.now(ASIA_SH)
            if now >= expiry.replace(tzinfo=ASIA_SH):
                raise SendAuthorizationError(f"Authorization {authorization_id} expired at {expires_at}")
        
        if auth['preflight_status'] != 'passed':
            raise SendAuthorizationError(f"preflight_status={auth['preflight_status']}")
        
        # Per-entry consumption check
        if plan_entry_id:
            entry = conn.execute(
                "SELECT status, consumed_at, lead_id, recipient_email FROM send_authorization_entries WHERE authorization_id=? AND plan_entry_id=?",
                (authorization_id, plan_entry_id)
            ).fetchone()
            if not entry:
                raise SendAuthorizationError(f"plan_entry_id={plan_entry_id} not in authorization")
            if entry['status'] == 'consumed':
                raise SendAuthorizationError(f"plan_entry_id={plan_entry_id} already consumed at {entry['consumed_at']}")
            if lead_id and entry['lead_id'] != lead_id:
                raise SendAuthorizationError(f"lead_id mismatch: auth has {entry['lead_id']}, requested {lead_id}")
            if recipient_email:
                auth_email = str(entry['recipient_email'] or '').strip().lower()
                req_email = str(recipient_email or '').strip().lower()
                if auth_email != req_email:
                    raise SendAuthorizationError(f"email mismatch: auth has {auth_email}, requested {req_email}")

            # P5 幂等：该 plan_entry_id 在 send_log 已有 sent 记录 → 直接拒绝再发
            sent_row = conn.execute(
                "SELECT id FROM send_log WHERE plan_entry_id=? AND status='sent' LIMIT 1",
                (plan_entry_id,)
            ).fetchone()
            if sent_row:
                raise SendAuthorizationError("entry already sent")
        
        mp = conn.execute("SELECT value FROM system_config WHERE key='manual_pause'").fetchone()
        if mp and mp['value'] == 'true':
            raise SendAuthorizationError("manual_pause is true")
        
        sa = conn.execute("SELECT value FROM system_config WHERE key='standing_authorization'").fetchone()
        if not sa or sa['value'] != 'true':
            raise SendAuthorizationError("standing_authorization is not true")
        
        rg = conn.execute("SELECT value FROM system_config WHERE key='risk_gate_status'").fetchone()
        if not rg or rg['value'] != 'clear':
            raise SendAuthorizationError(f"risk_gate_status={rg['value'] if rg else 'N/A'}")
        
        return dict(auth)
    finally:
        conn.close()


def consume_authorization_entry(authorization_id: str, plan_entry_id: int) -> bool:
    """Mark one plan entry as consumed. Marks batch consumed when all entries done.
    仅当本次 UPDATE 确实把某条 pending entry 置为 consumed（rowcount==1）才算成功；
    rowcount==0 表示该 entry 已被消费或不存在 → 返回 False，防并发重复消费。
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        now = datetime.now(ASIA_SH).isoformat()
        cur = conn.execute(
            "UPDATE send_authorization_entries SET consumed_at=?, status='consumed' WHERE authorization_id=? AND plan_entry_id=? AND status='pending'",
            (now, authorization_id, plan_entry_id)
        )
        if cur.rowcount != 1:
            conn.rollback()
            return False
        pending = conn.execute(
            "SELECT COUNT(*) FROM send_authorization_entries WHERE authorization_id=? AND status='pending'",
            (authorization_id,)
        ).fetchone()[0]
        if pending == 0:
            conn.execute(
                "UPDATE send_authorizations SET consumed_at=?, status='consumed' WHERE authorization_id=? AND status='approved'",
                (now, authorization_id)
            )
        conn.commit()
        return True
    finally:
        conn.close()


def reconcile_consumed_authorizations(db_path: str = None) -> list[str]:
    """Defense-in-depth: close any send_authorizations still status='approved' but
    with ZERO pending entries (so check_stale_objects can never permanently block a
    later preflight on a zombie auth).

    An auth reaches this state when all its entries were consumed (sent, or skipped/
    failed and their slots closed by _close_unsent_auth_entry) yet the parent row was
    never flipped to 'consumed' (e.g. a historical code path, or a partial commit).
    Uses its own connection so it never disturbs the caller's transaction.
    Returns the authorization_ids that were closed.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    try:
        now = datetime.now(ASIA_SH).isoformat()
        rows = conn.execute(
            """SELECT sa.authorization_id FROM send_authorizations sa
               WHERE sa.status='approved' AND sa.consumed_at IS NULL
                 AND NOT EXISTS (SELECT 1 FROM send_authorization_entries e
                                WHERE e.authorization_id=sa.authorization_id AND e.status='pending')"""
        ).fetchall()
        for r in rows:
            conn.execute(
                "UPDATE send_authorizations SET status='consumed', consumed_at=? "
                "WHERE authorization_id=? AND status='approved'",
                (now, r["authorization_id"]),
            )
        if rows:
            conn.commit()
        return [r["authorization_id"] for r in rows]
    finally:
        conn.close()


def _consume_authorization_after_send(authorization_id: str, plan_entry_id: int) -> str:
    """发送成功后的副作用：消费授权条目。返回可选的警告文本（无警告返回空串）。

    仅当 plan_entry_id 存在时才消费；consume 返回 False（无 pending entry）
    或异常都不视为发送失败，只返回警告信息，供 send_one 拼进 message。
    """
    if not plan_entry_id:
        return ""
    try:
        ok = consume_authorization_entry(authorization_id, plan_entry_id)
        if not ok:
            return f"; warning: authorization entry {plan_entry_id} not consumed (no pending entry)"
        return ""
    except Exception as exc:  # 消费失败不得影响已成功的发送结果
        return f"; warning: consume authorization entry {plan_entry_id} failed: {exc}"


def create_send_authorization(plan_id: str, outreach_batch_date: str,
                               planned_entries: list,
                               preflight_passed: bool,
                               db_path: str = None,
                               preflight_passed_status: str = 'passed') -> dict:
    """Create a short-lived send authorization after preflight passes.
    
    preflight_passed_status: 写入 send_authorizations.preflight_status 的值。
      默认 'passed'（向后兼容）。当 run_preflight 失败时，调用方可在
      preflight_passed=True 下传 'failed'，留一条被阻断的审计记录——
      validate_send_authorization() 对 !='passed'（含 'failed'）一律阻断 SMTP。
    preflight_passed=False 仍抛 ValueError（不建授权）。
    
    Returns dict with authorization_id or raises on failure.
    """
    if not preflight_passed:
        raise ValueError("Cannot create authorization: preflight not passed")
    if not planned_entries:
        raise ValueError("Cannot create authorization: no planned entries")
    
    db = db_path or DB_PATH
    conn = sqlite3.connect(db)
    try:
        hash_input = json.dumps(
            sorted([{
                'lead_id': e.get('lead_id'),
                'recipient_email': str(e.get('recipient_email', '')).strip().lower(),
                'message_type': e.get('message_type'),
            } for e in planned_entries], key=lambda x: x['lead_id']),
            sort_keys=True)
        entries_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        db_digest = hashlib.sha256(open(db, 'rb').read()).hexdigest()[:16]
        
        authorization_id = f"auth_{plan_id}_{outreach_batch_date}_{entries_hash}"
        now = datetime.now(ASIA_SH).isoformat()
        expires = (datetime.now(ASIA_SH) + timedelta(minutes=90)).isoformat()
        
        conn.execute("""
            INSERT INTO send_authorizations (
                authorization_id, plan_id, outreach_batch_date,
                plan_entries_hash, approved_entry_count, database_sha256,
                preflight_status, approved_at, expires_at, approved_by, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,'approved')
        """, (
            authorization_id, plan_id, outreach_batch_date,
            entries_hash, len(planned_entries), db_digest,
            preflight_passed_status, now, expires, 'system'
        ))
        
        # Also create per-entry records
        # P1.0: plan_entry_id 必须是真实 final_send_plan.id，从创建瞬间即成立。
        # 禁止用 lead_id 冒充后事后 UPDATE 修正。
        for e in planned_entries:
            lid = e.get('lead_id')
            remail = str(e.get('recipient_email', '')).strip().lower()
            peid = e.get('final_plan_entry_id') or e.get('plan_entry_id')
            if peid is None or not isinstance(peid, int) or isinstance(peid, bool):
                raise ValueError(
                    f"create_send_authorization: planned entry for lead {lid} missing "
                    "real final_send_plan.id (final_plan_entry_id/plan_entry_id must be int)"
                )
            entry_hash = hashlib.sha256(f"{lid}:{remail}".encode()).hexdigest()[:12]
            conn.execute("""
                INSERT OR IGNORE INTO send_authorization_entries
                (authorization_id, plan_entry_id, lead_id, recipient_email, entry_hash, status)
                VALUES (?,?,?,?,?,'pending')
            """, (authorization_id, peid, lid, remail, entry_hash))
        
        conn.commit()
        return {
            'authorization_id': authorization_id,
            'plan_id': plan_id,
            'approved_entry_count': len(planned_entries),
            'plan_entries_hash': entries_hash,
            'expires_at': expires,
            'status': 'approved',
        }
    finally:
        conn.close()


def _activate_tracking(token_hash: str, tracking_message_id: str, lead_id: int):
    """Register tracking token in D1 after SMTP success. Non-blocking — failures are silent."""
    try:
        import subprocess, os, json
        TRACKING_BASE = "https://roktandrazo-email-tracker.1569032023yf.workers.dev"
        # Register via HTTP POST to Worker admin endpoint (or directly via D1 CLI)
        # For now, use D1 CLI as it's the simplest path
        node_path = "C:/Users/15690/.workbuddy/binaries/node/versions/22.22.2"
        env = os.environ.copy()
        env["PATH"] = node_path + ";" + env.get("PATH", "")
        sql = f"UPDATE tracking_messages SET status='active', activated_at=datetime('now') WHERE token_hash='{token_hash}' AND status='prepared'"
        subprocess.run(
            [f"{node_path}/npx.cmd", "wrangler", "d1", "execute", "roktandrazo-email-tracking", "--remote", "--command", sql],
            cwd="cloudflare", env=env, capture_output=True, timeout=15
        )
    except Exception:
        pass  # Tracking failure must not block send


def ensure_standard_email_headers(msg: MIMEMultipart, sender_email: str, reply_to: str = None,
                                  message_id_domain: str = "roktandrazo.com") -> MIMEMultipart:
    """Ensure required RFC-style headers exist before serialization."""
    if "Date" not in msg:
        msg["Date"] = formatdate(localtime=True)
    if "Message-ID" not in msg:
        msg["Message-ID"] = make_msgid(domain=message_id_domain)
    if "MIME-Version" not in msg:
        msg["MIME-Version"] = "1.0"
    if "Reply-To" not in msg:
        msg["Reply-To"] = reply_to or sender_email
    return msg


def _create_connection():
    cfg = get_smtp_config()
    if not cfg["user"] or not cfg["password"]:
        raise ValueError("SMTP credentials not configured. Check .env file.")
    context = ssl.create_default_context()
    server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=30)
    server.ehlo()
    server.login(cfg["user"], cfg["password"])
    return server


def _build_email(to_email: str, subject: str, body_text: str, body_html: str = None) -> MIMEMultipart:
    sender = get_sender_info()
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((sender["name"], sender["email"]))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Reply-To"] = sender["email"]
    ensure_standard_email_headers(msg, sender["email"], sender["email"])

    # Plain text first, then HTML (HTML takes priority in email clients)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    return msg


def _save_to_sent(msg: MIMEMultipart) -> tuple:
    """Save a copy of the sent email to the IMAP Sent folder (已发送).
    返回 (ok, error)。失败不抛出异常，由调用方记录 sender_copy_status。
    """
    try:
        cfg = get_imap_config()
        if not cfg["user"] or not cfg["password"]:
            print("  [IMAP] No IMAP config, skipping sent-folder save")
            return True, ""

        if cfg["use_ssl"]:
            imap = imaplib.IMAP4_SSL(cfg["host"], cfg["port"], timeout=15)
        else:
            imap = imaplib.IMAP4(cfg["host"], cfg["port"], timeout=15)
        imap.login(cfg["user"], cfg["password"])

        raw_bytes = msg.as_bytes()

        # Tencent Exmail: "Sent Messages"
        folder = "Sent Messages"
        try:
            imap.append(folder, "\\Seen", imaplib.Time2Internaldate(time.time()), raw_bytes)
            print(f"  [IMAP] Saved to \"{folder}\"")
        except imaplib.IMAP4.error as e:
            print(f"  [IMAP] Failed to append to \"{folder}\": {e}")
            # Try the UTF-7 encoded parent path
            try:
                imap.append("&UXZO1mWHTvZZOQ-/Sent Messages", "\\Seen", imaplib.Time2Internaldate(time.time()), raw_bytes)
                print(f"  [IMAP] Saved to decoded Sent folder")
            except imaplib.IMAP4.error as e2:
                print(f"  [IMAP] Also failed: {e2}")
                imap.logout()
                return False, f"IMAP append failed: {e2}"

        imap.logout()
        return True, ""
    except Exception as e:
        print(f"  [IMAP] Error: {e}")
        return False, str(e)


def _send_log_has_sent(plan_entry_id: int, db_path: str = None) -> bool:
    """P5 幂等：send_log 是否已有该 plan_entry_id 的 sent 记录。"""
    conn = sqlite3.connect(db_path or DB_PATH)
    try:
        row = conn.execute(
            "SELECT id FROM send_log WHERE plan_entry_id=? AND status='sent' LIMIT 1",
            (plan_entry_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _resolve_real_plan_entry(plan_entry_id, lead_id: int = None, db_path: str = None):
    """P5 校验：plan_entry_id 必须是 final_send_plan 表的真实 id，且 lead_id 与传入 lead 一致。
    返回该行 dict（含 id/lead_id/recipient_email/outreach_batch_date/status），
    不存在或 lead_id 不匹配 → 返回 None。
    """
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, lead_id, recipient_email, outreach_batch_date, status "
            "FROM final_send_plan WHERE id=?",
            (plan_entry_id,)
        ).fetchone()
        if row is None:
            return None
        if lead_id is not None and row["lead_id"] != lead_id:
            return None
        return dict(row)
    finally:
        conn.close()


def _commit_send_success(db_path: str, plan_entry_id: int, lead_id: int,
                         email: str, actual_to: str, subject: str,
                         message_type: str, outreach_batch_date: str,
                         message_id: str, template_id: str, customer_type: str,
                         routing_reason: str, batch_id: str, source_platform: str,
                         authorization_id: str, smtp_accepted_at: str) -> tuple:
    """P5 原子提交：SMTP accepted 后，把 send_log / final_send_plan /
    authorization entry / leads 四类写入放在同一个 sqlite3 事务里。
    任一步失败 → rollback 并返回 (False, error)，不留半提交状态。
    """
    conn = sqlite3.connect(db_path)
    conn.isolation_level = None  # 关闭 sqlite3 隐式事务，显式控制 BEGIN/COMMIT/ROLLBACK
    conn.row_factory = sqlite3.Row
    try:
        # 幂等确保 send_log 有 smtp_accepted_at / authorization_id 列（生产迁移可能缺失）
        cols = {row[1] for row in conn.execute("PRAGMA table_info(send_log)")}
        for _col in ("smtp_accepted_at", "authorization_id"):
            if _col not in cols:
                try:
                    conn.execute(f"ALTER TABLE send_log ADD COLUMN {_col} TEXT")
                except sqlite3.OperationalError:
                    pass

        now = datetime.now(ASIA_SH).isoformat()
        conn.execute("BEGIN")
        # a) send_log INSERT（email 列存真实收件人，便于对账）
        conn.execute(
            """INSERT INTO send_log
               (lead_id, email, subject, status, sent_at, message_id,
                template_id, customer_type, routing_reason, batch_id,
                source_platform, message_type, outreach_batch_date,
                plan_entry_id, authorization_id, smtp_accepted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (lead_id, email, subject, "sent", now, message_id,
             template_id, customer_type, routing_reason, batch_id,
             source_platform, message_type, outreach_batch_date,
             plan_entry_id, authorization_id, smtp_accepted_at),
        )
        # b) final_send_plan → sent（仅 planned/in_progress 可提交）
        cur = conn.execute(
            "UPDATE final_send_plan SET status='sent', sent_at=? WHERE id=? AND status IN ('planned','in_progress')",
            (now, plan_entry_id),
        )
        if cur.rowcount == 0:
            raise RuntimeError(f"final_send_plan id={plan_entry_id} not in planned/in_progress")
        # c) authorization entry → consumed（仅 pending）
        cur = conn.execute(
            "UPDATE send_authorization_entries SET consumed_at=?, status='consumed' "
            "WHERE authorization_id=? AND plan_entry_id=? AND status='pending'",
            (now, authorization_id, plan_entry_id),
        )
        if cur.rowcount == 0:
            raise RuntimeError(f"authorization entry {plan_entry_id} not pending")
        # 批次级：全部条目消费完后标记整个 authorization 为 consumed
        pending = conn.execute(
            "SELECT COUNT(*) FROM send_authorization_entries WHERE authorization_id=? AND status='pending'",
            (authorization_id,),
        ).fetchone()[0]
        if pending == 0:
            conn.execute(
                "UPDATE send_authorizations SET consumed_at=?, status='consumed' "
                "WHERE authorization_id=? AND status='approved'",
                (now, authorization_id),
            )
        # d) leads → sent（仅当前非 sent/bounced）
        conn.execute(
            "UPDATE leads SET status='sent', sent_at=? WHERE id=? AND COALESCE(status,'') NOT IN ('sent','bounced')",
            (now, lead_id),
        )
        conn.commit()
        return True, ""
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def _pre_send_checks(subject: str, body_text: str) -> list[str]:
    """Safety checks before sending"""
    issues = []
    if "{{" in subject or "}}" in subject:
        issues.append(f"Subject contains unreplaced braces: {subject}")
    if "{{" in body_text or "}}" in body_text:
        issues.append("Body contains unreplaced braces {{}}")
    for bad in ["undefined", "None", "null"]:
        if bad in subject:
            issues.append(f"Subject contains '{bad}'")
    return issues


def send_one(lead: dict, dry_run: bool = False) -> dict:
    email = (lead.get("email") or "").strip()
    lead_id = lead.get("id")
    subject = lead.get("email_subject", "")
    body_text = lead.get("email_body", "")
    body_html = lead.get("email_body_html", "")
    plan_entry_id = lead.get("final_plan_entry_id")
    # P5: 禁止接受 lead_id / 旧 plan_entry_id 字段冒充 final_send_plan.id
    message_type = lead.get("message_type")
    outreach_batch_date = lead.get("outreach_batch_date")

    # Validation
    if not email:
        return {"success": False, "message": "No email", "status": "failed"}

    # Production sending is plan-only. A sender must never refill a batch from
    # the candidate pool after pre-send hygiene has frozen the recipient list.
    if not dry_run and (message_type not in ('new_outreach', 'follow_up') or not outreach_batch_date):
        return {"success": False, "message": "Missing immutable final send plan metadata", "status": "failed"}

    if is_suppressed(email):
        return {"success": False, "message": "Email is suppressed", "status": "skipped"}

    if not subject or not body_text:
        return {"success": False, "message": "Missing email_subject or email_body", "status": "failed"}

    # Safety checks
    issues = _pre_send_checks(subject, body_text)
    if issues:
        return {"success": False, "message": f"Safety check failed: {'; '.join(issues)}", "status": "failed"}

    # Dry run
    if dry_run:
        return {
            "success": True,
            "message": f"[DRY RUN] Would send to {email}",
            "status": "dry_run",
            "preview": {"to": email, "subject": subject, "body_text": body_text, "body_html": body_html},
        }

    if not is_configured():
        return {"success": False, "message": "SMTP not configured", "status": "failed"}

    # Test mode: redirect to test email, add [TEST] tag
    test_cfg = get_test_config()
    actual_to = email
    if test_cfg["test_mode"] and test_cfg["test_email"]:
        actual_to = test_cfg["test_email"]
        subject = f"[TEST->{email}] {subject}"

    # ── P0: Send Authorization Gate (fail-closed) ──
    # All production customer sends require a valid authorization.
    # Test mode and dry runs are exempt.
    authorization_id = lead.get("authorization_id", "")
    real_plan = None
    if not test_cfg["test_mode"] and not dry_run:
        # ── P5: final_plan_entry_id 必须是真实 final_send_plan.id ──
        # 禁止用 lead_id / 字符串 id 冒充。空值或非 int → 直接 fail。
        if plan_entry_id is None or not isinstance(plan_entry_id, int) or isinstance(plan_entry_id, bool):
            return {"success": False, "message": "Missing real final_send_plan.id", "status": "failed"}

        # P5 幂等：send_log 已有该 plan_entry_id 的 sent 记录 → 跳过，不再调 SMTP
        if _send_log_has_sent(plan_entry_id):
            return {"success": False, "message": "ALREADY_SENT_SKIP", "status": "skipped"}

        # P5 数据不一致保护：send_log 无记录但 final_send_plan 已 sent → 跳过
        real_plan = _resolve_real_plan_entry(plan_entry_id, lead_id)
        if real_plan is None:
            return {"success": False, "message": "Missing real final_send_plan.id", "status": "failed"}
        if real_plan["status"] == "sent":
            return {"success": False, "message": "ALREADY_SENT_SKIP", "status": "skipped"}

        try:
            validate_send_authorization(authorization_id,
                                          plan_entry_id=plan_entry_id,
                                          lead_id=lead_id,
                                          recipient_email=email)
        except SendAuthorizationError as auth_err:
            return {"success": False, "message": f"SendAuthorizationError: {auth_err}", "status": "blocked"}

        # ── P0: Template assertion ──
        # New Outreach must use locked V5 templates; no auto-shortening or fallback
        if lead.get("message_type") == "new_outreach":
            from bd_template import check_inline_forbidden, _TEMPLATE_REGISTRY
            body = lead.get("email_body", "")
            # 正式链权威字段是 template_id（FSP 冻结字段，preflight check_template 同口径）；
            # template_key 仅为渲染元数据列，leads 表可能不存在 → 回退 template_id。
            template_key = lead.get("template_key") or lead.get("template_id") or ""
            
            # Check forbidden phrases
            forbidden = check_inline_forbidden(body or "")
            if forbidden:
                return {"success": False,
                        "message": f"TEMPLATE_REJECTED: forbidden phrase(s) {forbidden}. SMTP blocked.",
                        "status": "blocked"}
            
            # Check for inline/fallback patterns
            if not template_key or template_key not in _TEMPLATE_REGISTRY:
                return {"success": False,
                        "message": f"TEMPLATE_REJECTED: template_key='{template_key}' not in registry. "
                                   "Only retail_distributor_v5_locked or custom_printing_production_v5_locked allowed.",
                        "status": "blocked"}
            
            tpl = _TEMPLATE_REGISTRY.get(template_key, {})
            if tpl.get("status") != "ACTIVE_LOCKED":
                return {"success": False,
                        "message": f"TEMPLATE_REJECTED: template_key={template_key} status={tpl.get('status')}. Must be ACTIVE_LOCKED.",
                        "status": "blocked"}

    # Build customer MIME (with pixel if tracking) and sender copy (no pixel)
    try:
        msg = _build_email(actual_to, subject, body_text, body_html if body_html else None)
        sender_email = get_sender_info()["email"]

        # Build untracked sender copy if this email has a pixel version
        body_html_no_pixel = lead.get("email_body_html_no_pixel", "")
        has_pixel = lead.get("pixel_tracking", False) and body_html_no_pixel

        server = _create_connection()
        # Send to customer only (tracked MIME)
        server.sendmail(sender_email, [actual_to], msg.as_string())
        server.quit()
        # P5: 记录 SMTP accepted 时刻（UTC ISO）
        smtp_accepted_at = datetime.now(timezone.utc).isoformat()

        # Extract metadata
        message_id = msg.get("Message-ID", "")
        template_id = lead.get("template_id", "")
        customer_type = lead.get("customer_type", "")
        routing_reason = lead.get("routing_reason", "")
        batch_id = lead.get("batch_id", "")
        source_platform = lead.get("source_platform", "")

        if test_cfg["test_mode"] and test_cfg["test_email"]:
            # Redirected test mail must not become customer outreach history or
            # consume the customer's immutable Final Send Plan entry.
            log_send(None, actual_to, subject, "sent",
                     message_id=message_id, template_id=template_id,
                     customer_type=customer_type, routing_reason=routing_reason,
                     batch_id=batch_id, source_platform=source_platform,
                     message_type='test', outreach_batch_date=outreach_batch_date,
                     plan_entry_id=None)
            return {"success": True, "message": f"Test sent to {actual_to}", "status": "test"}

        # ── P5: SMTP accepted 后原子提交（send_log + FSP + auth entry + leads 单事务）──
        # 防御：生产路径 real_plan 必由上方 gate 解析；仅 test_mode 且 test_email 为空等
        # 异常配置才会走到这里且 real_plan 为 None，此时 fail-closed。
        if real_plan is None:
            return {"success": False, "message": "Missing real final_send_plan.id", "status": "failed"}
        commit_ok, commit_err = _commit_send_success(
            db_path=DB_PATH, plan_entry_id=plan_entry_id, lead_id=lead_id,
            email=email, actual_to=actual_to, subject=subject,
            message_type=message_type, outreach_batch_date=outreach_batch_date,
            message_id=message_id, template_id=template_id,
            customer_type=customer_type, routing_reason=routing_reason,
            batch_id=batch_id, source_platform=source_platform,
            authorization_id=authorization_id, smtp_accepted_at=smtp_accepted_at,
        )
        if not commit_ok:
            return {"success": False, "message": f"DB commit failed: {commit_err}", "status": "failed"}

        # ── 提交成功后的 best-effort 副作用（失败不影响客户 SMTP accepted）──
        sender_copy_failures = []
        # IMAP Sent 副本（sender copy 失败不吞错误，仅记录）
        try:
            _sc_ok, _sc_err = _save_to_sent(msg)
            if not _sc_ok:
                sender_copy_failures.append(_sc_err)
        except Exception as _sc_exc:
            sender_copy_failures.append(str(_sc_exc))

        # ── Tracking activation ──────────────────────────
        tracking_hash = lead.get("_tracking_token_hash", "")
        tracking_msg_id = lead.get("_tracking_message_id", "")
        if has_pixel and tracking_hash and tracking_msg_id:
            _activate_tracking(tracking_hash, tracking_msg_id, lead_id)

        # ── Sender copy (untracked, separate MIME) ───────
        if sender_email != actual_to:
            try:
                sc = _build_email(sender_email, subject, body_text, body_html_no_pixel if body_html_no_pixel else None)
                sc["X-Roktandrazo-Type"] = "sender_copy"
                sc_server = _create_connection()
                sc_server.sendmail(sender_email, [sender_email], sc.as_string())
                sc_server.quit()
            except Exception as sce:
                # P5: sender copy 失败不吞错误，写入返回 dict（不影响客户发送结果）
                sender_copy_failures.append(f"sender_copy: {sce}")

        result = {
            "success": True,
            "message": f"Sent to {actual_to}",
            "status": "sent",
            "plan_entry_id": real_plan["id"],
            "plan_lead_id_matched": True,
        }
        if sender_copy_failures:
            result["sender_copy_status"] = "failed"
            result["sender_copy_error"] = "; ".join(sender_copy_failures)
        return result

    except smtplib.SMTPRecipientsRefused as e:
        if test_cfg["test_mode"] and test_cfg["test_email"]:
            return {"success": False, "message": f"Test recipient refused: {e}", "status": "test_failed"}
        update_lead_status(lead_id, "failed", error_message=str(e))
        log_send(lead_id, email, subject, "failed", str(e))
        return {"success": False, "message": f"Recipient refused: {e}", "status": "failed"}

    except smtplib.SMTPDataError as e:
        error_str = str(e)
        if test_cfg["test_mode"] and test_cfg["test_email"]:
            return {"success": False, "message": f"Test SMTP error: {e}", "status": "test_failed"}
        if "550" in error_str or "bounce" in error_str.lower():
            update_lead_status(lead_id, "bounced", bounced_at=datetime.now().isoformat(), error_message=error_str)
            add_to_suppression(email, "bounced")
            log_send(lead_id, email, subject, "bounced", error_str)
            return {"success": False, "message": f"Bounced: {e}", "status": "bounced"}
        update_lead_status(lead_id, "failed", error_message=error_str)
        log_send(lead_id, email, subject, "failed", error_str)
        return {"success": False, "message": f"SMTP error: {e}", "status": "failed"}

    except Exception as e:
        if test_cfg["test_mode"] and test_cfg["test_email"]:
            return {"success": False, "message": f"Test send error: {e}", "status": "test_failed"}
        update_lead_status(lead_id, "failed", error_message=str(e))
        log_send(lead_id, email, subject, "failed", str(e))
        return {"success": False, "message": f"Error: {e}", "status": "failed"}


def batch_send(leads: list[dict], dry_run: bool = False) -> list[dict]:
    limits = get_sending_limits()
    max_send = limits["max_per_batch"]
    delay = limits["delay_seconds"]

    results = []
    sent_count = 0

    for lead in leads:
        if sent_count >= max_send and not dry_run:
            results.append({"lead_id": lead.get("id"), "success": False, "message": "Batch limit reached", "status": "skipped"})
            continue

        result = send_one(lead, dry_run=dry_run)
        result["lead_id"] = lead.get("id")
        result["store_name"] = lead.get("store_name")
        result["email"] = lead.get("email")
        results.append(result)

        if result["success"] and result["status"] == "sent":
            sent_count += 1
            if not dry_run and sent_count < max_send:
                time.sleep(delay)

    return results
