"""
Roktandrazo BD Outreach - P0 退信自动回流核心模块
====================================================
功能：
  1. parse_bounce_email: 解析 Exmail DSN 邮件（text/plain + text/html +
     message/delivery-status + message/rfc822 四种 MIME part），提取
     final_recipient / original_recipient / x_failed_recipients /
     diagnostic_code / status_code / original_message_id / original_subject /
     original_sent_at。
  2. classify_bounce: 依据 diagnostic_code / status_code / body 关键词分类
     (domain_invalid / mailbox_invalid / policy_bounce / soft_bounce / unresolved)。
  3. record_bounce: 幂等写入 bounce_log 并按类型回写 leads 与 contact_recovery。
  4. record_unmatched_dsn: 写入 unmatched_dsn 兜底表，优先匹配 send_log.email。
  5. scan_bounces: IMAP 扫描收件箱中的退信 DSN 邮件。
  6. run_scan_and_writeback: 扫描 + 回写 system_config 与 poller 状态文件。

命令行：
  python bounce_pipeline.py --once        # 单次扫描 + 回写
  python bounce_pipeline.py --self-test   # 用内置 3 封样本做真实库回归
"""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta

from bd_db import get_db
from env_loader import get_imap_config

# 本文件所在目录（项目根）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLLER_STATUS_FILE = os.path.join(BASE_DIR, "output", "bd_ops_poller_status.json")

# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _rows(conn: sqlite3.Connection, sql: str, params=()):
    """执行参数化查询并返回 [{col: value}, ...]。"""
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params=()):
    rows = _rows(conn, sql, params)
    return rows[0] if rows else None


def _extract_email(value: str | None) -> str | None:
    """从 rfc822; <foo@bar.com> 等格式里提取纯邮箱地址。"""
    if not value:
        return None
    v = value.strip()
    if ";" in v:
        v = v.split(";", 1)[1].strip()
    m = _EMAIL_RE.search(v)
    if m:
        return m.group(0).lower()
    cleaned = v.strip("<> \t").lower()
    return cleaned or None


def _extract_email_list(value: str | None) -> str | None:
    """提取 X-Failed-Recipients 等可能含多个邮箱的字段，逗号分隔。"""
    if not value:
        return None
    found = _EMAIL_RE.findall(value)
    if found:
        return ", ".join(sorted({e.lower() for e in found}))
    return value.strip() or None


# ---------------------------------------------------------------------------
# 1. parse_bounce_email
# ---------------------------------------------------------------------------

def parse_bounce_email(raw_bytes: bytes) -> dict:
    """解析一封 DSN / 退信邮件，返回结构化字典。

    MIME part 覆盖：text/plain, text/html, message/delivery-status, message/rfc822。
    """
    msg = email.message_from_bytes(raw_bytes)
    result = {
        "raw_message_id": msg.get("Message-ID"),
        "final_recipient": None,
        "original_recipient": None,
        "x_failed_recipients": None,
        "diagnostic_code": None,
        "status_code": None,
        "original_message_id": None,
        "original_subject": None,
        "original_sent_at": None,
        "raw_body": "",   # text/plain 拼接，供 classify 使用
        "html_body": "",  # text/html 原文，供关键词兜底
    }

    def _grab(sub: object) -> None:
        for h in ("Final-Recipient", "Original-Recipient", "Diagnostic-Code",
                  "Status", "X-Failed-Recipients", "X-Original-Message-ID"):
            val = sub.get(h)
            if not val:
                continue
            hk = h.lower()
            if hk == "final-recipient":
                result["final_recipient"] = _extract_email(val) or result["final_recipient"]
            elif hk == "original-recipient":
                result["original_recipient"] = _extract_email(val) or result["original_recipient"]
            elif hk == "x-failed-recipients":
                result["x_failed_recipients"] = _extract_email_list(val) or result["x_failed_recipients"]
            elif hk == "diagnostic-code":
                result["diagnostic_code"] = val.strip() or result["diagnostic_code"]
            elif hk == "status":
                result["status_code"] = val.strip() or result["status_code"]
            elif hk == "x-original-message-id":
                result["original_message_id"] = val.strip() or result["original_message_id"]

    for part in msg.walk():
        ctype = part.get_content_type()

        if ctype == "text/plain":
            try:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                result["raw_body"] += payload.decode(charset, errors="replace")
            except Exception:
                result["raw_body"] += str(part.get_payload())

        elif ctype == "text/html":
            try:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                result["html_body"] += payload.decode(charset, errors="replace")
            except Exception:
                result["html_body"] += str(part.get_payload())

        elif ctype == "message/delivery-status":
            subs = part.get_payload()
            if isinstance(subs, list):
                for sub in subs:
                    _grab(sub)
            else:
                _grab(part)

        elif ctype == "message/rfc822":
            payload = part.get_payload()
            original = payload[0] if isinstance(payload, list) else payload
            if isinstance(original, email.message.Message):
                result["original_message_id"] = result["original_message_id"] or original.get("Message-ID")
                result["original_subject"] = original.get("Subject")
                result["original_sent_at"] = original.get("Date")

    # ---- HTML part 兜底：正则扫描邮箱 + MX / Host not found 关键词 ----
    html = result["html_body"]
    if html:
        emails = _EMAIL_RE.findall(html)
        if result["final_recipient"] is None and emails:
            result["final_recipient"] = emails[0].lower()
        if result["original_recipient"] is None and emails:
            result["original_recipient"] = emails[0].lower()
        if result["diagnostic_code"] is None:
            low = html.lower()
            if "host not found" in low or "nxdomain" in low or "mx" in low:
                result["diagnostic_code"] = "type=MX: Host not found (html fallback)"

    return result


# ---------------------------------------------------------------------------
# 2. classify_bounce
# ---------------------------------------------------------------------------

_DOMAIN_INVALID_PATTERNS = [
    r"host\s+not\s+found",
    r"nxdomain",
    r"no\s+mx",
    r"mx\s+record",
    r"no\s+matching\s+record",
    r"domain\s+does\s+not\s+exist",
    r"domain\s+not\s+found",
    r"unknown\s+domain",
    r"invalid\s+domain",
    r"could\s+not\s+resolve",
    r"dns\s+error",
    r"dns\s+resolution",
    r"cannot\s+find\s+the\s+host",
    r"unable\s+to\s+resolve",
    r"name\s+server.*fail",
]
_MAILBOX_INVALID_PATTERNS = [
    r"user\s+unknown",
    r"user\s+not\s+found",
    r"no\s+such\s+user",
    r"mailbox\s+does\s+not\s+exist",
    r"mailbox\s+unavailable",
    r"account\s+not\s+found",
    r"invalid\s+mailbox",
    r"unknown\s+user",
    r"recipient\s+address\s+rejected",
    r"address\s+does\s+not\s+exist",
    r"no\s+such\s+recipient",
    r"does\s+not\s+have\s+an\s+account",
    r"not\s+a\s+valid\s+recipient",
]
_POLICY_BOUNCE_PATTERNS = [
    r"5\.7",
    r"relaying\s+denied",
    r"relay\s+denied",
    r"policy",
    r"rejected\s+by\s+policy",
    r"recipient\s+rejected",
    r"not\s+allowed\s+to\s+relay",
    r"spam",
    r"blocked",
]
_SOFT_BOUNCE_PATTERNS = [
    r"temporar",
    r"try\s+again",
    r"mailbox\s+full",
    r"over\s+quota",
    r"quota",
    r"deferred",
    r"greylist",
    r"throttl",
    r"busy",
    r"4\.2\.2",
    r"4\.4\.1",
    r"4\.5\.1",
    r"connection\s+timed\s+out",
]


def classify_bounce(diagnostic_code: str | None, status_code: str | None,
                    raw_body: str | None = None) -> str:
    """把退信诊断信息分类为五类之一。"""
    diag = (diagnostic_code or "").lower()
    status = (status_code or "").lower()
    body = (raw_body or "").lower()
    haystack = " ".join([diag, status, body])

    if any(re.search(p, haystack) for p in _DOMAIN_INVALID_PATTERNS):
        return "domain_invalid"
    if any(re.search(p, haystack) for p in _MAILBOX_INVALID_PATTERNS):
        return "mailbox_invalid"
    if any(re.search(p, haystack) for p in _POLICY_BOUNCE_PATTERNS):
        return "policy_bounce"
    if any(re.search(p, haystack) for p in _SOFT_BOUNCE_PATTERNS):
        return "soft_bounce"

    # status code 兜底：4.x = 临时，5.1.1 = 邮箱不存在，5.7.x = 策略
    if status.startswith("4."):
        return "soft_bounce"
    if status.startswith("5.7"):
        return "policy_bounce"
    if status.startswith("5.1.1") or status.startswith("5.1.10"):
        return "mailbox_invalid"

    return "unresolved"


# ---------------------------------------------------------------------------
# 3. record_bounce —— 幂等写入 bounce_log 并按类型回写
# ---------------------------------------------------------------------------

def _write_contact_recovery(conn: sqlite3.Connection, lead: dict, email_addr: str,
                            reason: str) -> None:
    """为 domain_invalid / mailbox_invalid 的 lead 写入 contact_recovery（幂等）。"""
    domain = email_addr.split("@", 1)[1] if "@" in email_addr else ""
    now = _now_iso()
    exists = _one(
        conn,
        "SELECT id FROM contact_recovery WHERE email = ? AND reason = ? AND status = 'pending'",
        (email_addr, reason),
    )
    if exists:
        return
    conn.execute(
        """
        INSERT INTO contact_recovery (lead_id, org_name, email, domain, reason,
                                      status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (lead["id"], lead.get("store_name"), email_addr, domain, reason, now, now),
    )


def record_bounce(conn: sqlite3.Connection, lead_id: int, email_addr: str,
                  bounce_type: str, diagnostic_code: str | None,
                  status_code: str | None = None,
                  raw_subject: str | None = None) -> dict:
    """插入 bounce_log（幂等：同 email + 同 diagnostic 不重复插），并按类型回写 leads。

    类型回写规则：
      domain_invalid : email_sendable=0, follow_up_eligible=0,
                       contact_recovery_required=1, status='bounced', bounced_at=now
      mailbox_invalid: email_sendable=0, follow_up_eligible=0, contact_recovery_required=1
      policy_bounce  : delivery_policy_review=1
      soft_bounce    : deferred_until = now + 3 天
    返回 {'inserted': bool, 'bounce_log_id': int, 'lead_id': int}
    """
    email_addr = (email_addr or "").strip().lower()
    if not email_addr:
        raise ValueError("record_bounce 需要非空 email")
    domain = email_addr.split("@", 1)[1] if "@" in email_addr else ""
    now = _now_iso()

    lead = _one(conn, "SELECT * FROM leads WHERE id = ?", (lead_id,))
    if lead is None:
        lead = {"id": lead_id, "store_name": "", "campaign": ""}

    # ---- 幂等插入 bounce_log ----
    existing = _one(
        conn,
        "SELECT id FROM bounce_log WHERE email = ? AND diagnostic_code IS NOT DISTINCT FROM ?",
        (email_addr, diagnostic_code),
    )
    inserted = False
    if existing:
        bounce_log_id = existing["id"]
    else:
        cur = conn.execute(
            """
            INSERT INTO bounce_log (lead_id, email, domain, campaign, bounce_received_at,
                                    status_code, diagnostic_code, bounce_type,
                                    raw_message_subject, recommended_action, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (lead_id, email_addr, domain, lead.get("campaign"), now,
             status_code, diagnostic_code, bounce_type,
             raw_subject, None, now),
        )
        bounce_log_id = cur.lastrowid
        inserted = True

    # ---- 按类型回写 leads ----
    lead_update = None
    recovery_reason = None
    if bounce_type == "domain_invalid":
        lead_update = (
            "UPDATE leads SET email_sendable=0, follow_up_eligible=0, "
            "contact_recovery_required=1, status='bounced', bounced_at=?, "
            "delivery_policy_review=delivery_policy_review, deferred_until=deferred_until "
            "WHERE id=?",
            (now, lead_id),
        )
        recovery_reason = "domain_invalid: MX Host not found / 域名无效"
    elif bounce_type == "mailbox_invalid":
        lead_update = (
            "UPDATE leads SET email_sendable=0, follow_up_eligible=0, "
            "contact_recovery_required=1, "
            "delivery_policy_review=delivery_policy_review, deferred_until=deferred_until "
            "WHERE id=?",
            (lead_id,),
        )
        recovery_reason = "mailbox_invalid: 邮箱不存在"
    elif bounce_type == "policy_bounce":
        lead_update = (
            "UPDATE leads SET delivery_policy_review=1, "
            "email_sendable=email_sendable, follow_up_eligible=follow_up_eligible, "
            "contact_recovery_required=contact_recovery_required "
            "WHERE id=?",
            (lead_id,),
        )
    elif bounce_type == "soft_bounce":
        deferred = (datetime.now() + timedelta(days=3)).astimezone().isoformat()
        lead_update = (
            "UPDATE leads SET deferred_until=? WHERE id=?",
            (deferred, lead_id),
        )

    if lead_update:
        conn.execute(lead_update[0], lead_update[1])

    # ---- contact_recovery（仅 domain_invalid / mailbox_invalid） ----
    if recovery_reason:
        _write_contact_recovery(conn, lead, email_addr, recovery_reason)

    conn.commit()
    return {"inserted": inserted, "bounce_log_id": bounce_log_id, "lead_id": lead_id}


# ---------------------------------------------------------------------------
# 4. record_unmatched_dsn —— unmatched_dsn 兜底 + send_log 匹配
# ---------------------------------------------------------------------------

def _find_lead_by_email(conn: sqlite3.Connection, email_addr: str | None):
    if not email_addr:
        return None
    return _one(conn, "SELECT * FROM leads WHERE email = ? LIMIT 1", (email_addr,))


def record_unmatched_dsn(conn: sqlite3.Connection, dsn_dict: dict) -> dict:
    """写入 unmatched_dsn 表（processed_at=now，永不丢弃）。

    先尝试按 original_recipient / final_recipient / x_failed_recipients 匹配
    send_log.email；匹配到则写 matched_send_log_id 并走 record_bounce。
    若无 send_log 命中，则尝试按 leads.email 匹配以便回写 lead。
    都匹配不到也必须保存（UNMATCHED_DSN 兜底）。
    返回 {'saved': bool, 'duplicate': bool, 'matched_send_log_id': int|None,
          'lead_id': int|None, 'bounce_type': str|None, 'unmatched': bool}
    """
    dsn = dict(dsn_dict)
    raw_message_id = dsn.get("raw_message_id") or dsn.get("original_message_id")
    final_recipient = dsn.get("final_recipient")
    original_recipient = dsn.get("original_recipient")
    x_failed = dsn.get("x_failed_recipients")
    diagnostic_code = dsn.get("diagnostic_code")
    status_code = dsn.get("status_code")

    now = _now_iso()
    matched_send_log_id = None
    lead_id = None

    # ---- 1) 尝试匹配 send_log ----
    candidates = [final_recipient, original_recipient]
    if x_failed:
        candidates += [x.strip() for x in x_failed.split(",")]
    send_log_row = None
    for cand in candidates:
        if not cand:
            continue
        send_log_row = _one(
            conn,
            "SELECT * FROM send_log WHERE email = ? ORDER BY id DESC LIMIT 1",
            (cand,),
        )
        if send_log_row:
            matched_send_log_id = send_log_row["id"]
            lead_id = send_log_row.get("lead_id")
            break

    # ---- 2) send_log 未命中则按 leads.email 匹配（便于回写） ----
    if lead_id is None:
        lead = None
        for cand in candidates:
            if not cand:
                continue
            lead = _find_lead_by_email(conn, cand)
            if lead:
                break
        if lead:
            lead_id = lead["id"]

    # ---- 3) 无论是否匹配，都保存 unmatched_dsn 兜底行（幂等去重） ----
    existing_dsn = _one(
        conn,
        """
        SELECT id FROM unmatched_dsn
        WHERE raw_message_id IS NOT DISTINCT FROM ?
          AND final_recipient IS NOT DISTINCT FROM ?
          AND diagnostic_code IS NOT DISTINCT FROM ?
        """,
        (raw_message_id, final_recipient, diagnostic_code),
    )
    saved = True
    if existing_dsn is None:
        conn.execute(
            """
            INSERT INTO unmatched_dsn (raw_message_id, final_recipient, original_recipient,
                                       x_failed_recipients, diagnostic_code, status_code,
                                       original_message_id, original_subject, original_sent_at,
                                       detected_at, processed_at, matched_send_log_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                raw_message_id,
                final_recipient,
                original_recipient,
                x_failed,
                diagnostic_code,
                status_code,
                dsn.get("original_message_id"),
                dsn.get("original_subject"),
                dsn.get("original_sent_at"),
                now,
                now,
                matched_send_log_id,
                "matched_send_log" if matched_send_log_id else "unmatched_dsn",
            ),
        )
    else:
        saved = False

    # ---- 4) 若能定位 lead，走 record_bounce 回写 ----
    bounce_type = None
    if lead_id is not None:
        bounce_type = classify_bounce(diagnostic_code, status_code, dsn.get("raw_body"))
        record_bounce(
            conn, lead_id,
            final_recipient or original_recipient,
            bounce_type, diagnostic_code, status_code,
            raw_subject=dsn.get("original_subject"),
        )

    conn.commit()
    return {
        "saved": saved,
        "duplicate": not saved,
        "matched_send_log_id": matched_send_log_id,
        "lead_id": lead_id,
        "bounce_type": bounce_type,
        "unmatched": lead_id is None,
    }


# ---------------------------------------------------------------------------
# 5. scan_bounces —— IMAP 扫描
# ---------------------------------------------------------------------------

# 发件人 / 主题过滤关键词
_FROM_PAT = re.compile(r"mailer-daemon|postmaster", re.IGNORECASE)
_SUBJECT_PAT = re.compile(
    r"Delivery Status|Undeliverable|退信|failed to deliver|Delivery failure|Returned mail",
    re.IGNORECASE,
)


def _connect_imap() -> imaplib.IMAP4:
    """连接 Exmail IMAP（993 SSL），配置缺失 / 认证失败抛清晰异常。"""
    cfg = get_imap_config()
    if not cfg.get("user") or not cfg.get("password"):
        raise RuntimeError(
            "IMAP 未配置：.env 缺少 BD_IMAP_USER / BD_IMAP_PASS（env_loader.get_imap_config()）"
        )
    host = cfg.get("host") or "imap.exmail.qq.com"
    port = int(cfg.get("port") or 993)
    try:
        if cfg.get("use_ssl", True):
            conn = imaplib.IMAP4_SSL(host, port)
        else:
            conn = imaplib.IMAP4(host, port)
        conn.login(cfg["user"], cfg["password"])
    except imaplib.IMAP4.error as exc:
        raise RuntimeError(f"IMAP 登录失败（{cfg['user']}@{host}:{port}）: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"IMAP 连接失败（{host}:{port}）: {exc}") from exc
    return conn


def _fetch_bounce_candidates(conn: imaplib.IMAP4, limit: int = 50):
    """取收件箱最近的 limit 封邮件 header 过滤出退信候选。"""
    typ, data = conn.select("INBOX")
    if typ != "OK":
        raise RuntimeError(f"IMAP SELECT INBOX 失败: {data}")
    typ, data = conn.search(None, "ALL")
    if typ != "OK" or not data or not data[0]:
        return []
    ids = data[0].split()
    recent_ids = ids[-limit:]

    candidates = []
    for uid in recent_ids:
        typ, fdata = conn.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        if typ != "OK":
            continue
        try:
            header_bytes = b"\n".join(x[1] for x in fdata if isinstance(x, tuple))
        except Exception:
            continue
        header_msg = email.message_from_bytes(header_bytes)
        frm = header_msg.get("From") or ""
        subj = header_msg.get("Subject") or ""
        if _FROM_PAT.search(frm) or _SUBJECT_PAT.search(subj):
            candidates.append((uid, frm, subj))
    return candidates


def scan_bounces() -> dict:
    """扫描 IMAP 收件箱退信并逐封解析/分类/落库。

    返回 summary: {scanned, matched, domain_invalid, mailbox_invalid,
                   policy_bounce, soft_bounce, unmatched_dsn, errors, dsns}
    """
    conn = _connect_imap()
    summary = {
        "scanned": 0,
        "matched": 0,
        "domain_invalid": 0,
        "mailbox_invalid": 0,
        "policy_bounce": 0,
        "soft_bounce": 0,
        "unmatched_dsn": 0,
        "errors": [],
        "dsns": [],
    }
    try:
        candidates = _fetch_bounce_candidates(conn)
        db = get_db()
        try:
            for uid, _frm, _subj in candidates:
                summary["scanned"] += 1
                typ, bdata = conn.fetch(uid, "(BODY.PEEK[])")
                if typ != "OK":
                    continue
                raw_bytes = None
                for chunk in bdata:
                    if isinstance(chunk, tuple):
                        raw_bytes = chunk[1]
                        break
                if not raw_bytes:
                    continue
                try:
                    parsed = parse_bounce_email(raw_bytes)
                    result = record_unmatched_dsn(db, parsed)
                    bt = result.get("bounce_type")
                    if bt:
                        summary[bt] = summary.get(bt, 0) + 1
                    if result.get("unmatched"):
                        summary["unmatched_dsn"] += 1
                    else:
                        summary["matched"] += 1
                    summary["dsns"].append({
                        "raw_message_id": parsed.get("raw_message_id"),
                        "final_recipient": parsed.get("final_recipient"),
                        "original_recipient": parsed.get("original_recipient"),
                        "diagnostic_code": parsed.get("diagnostic_code"),
                        "status_code": parsed.get("status_code"),
                        "bounce_type": bt,
                        "matched_send_log_id": result.get("matched_send_log_id"),
                        "lead_id": result.get("lead_id"),
                    })
                except Exception as exc:  # 单封失败不中断整轮扫描
                    summary["errors"].append(f"uid={uid}: {exc}")
        finally:
            db.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return summary


# ---------------------------------------------------------------------------
# 6. run_scan_and_writeback —— 扫描 + 系统状态回写
# ---------------------------------------------------------------------------

def _set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO system_config (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                       updated_at = excluded.updated_at
        """,
        (key, value, _now_iso()),
    )


def _write_poller_status(success: bool, error: str | None = None) -> None:
    """更新 output/bd_ops_poller_status.json 里的 jobs.bounce 状态。"""
    data = {}
    if os.path.exists(POLLER_STATUS_FILE):
        try:
            with open(POLLER_STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}

    jobs = data.get("jobs") or {}
    if not isinstance(jobs, dict):
        jobs = {}
    prev = jobs.get("bounce") or {}
    now = _now_iso()
    if success:
        jobs["bounce"] = {
            "last_success_at": now,
            "error": None,
            "consecutive_failures": 0,
        }
    else:
        prev_failures = int(prev.get("consecutive_failures") or 0)
        jobs["bounce"] = {
            "last_success_at": prev.get("last_success_at"),
            "error": error,
            "consecutive_failures": prev_failures + 1,
        }
    data["jobs"] = jobs

    os.makedirs(os.path.dirname(POLLER_STATUS_FILE), exist_ok=True)
    with open(POLLER_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_scan_and_writeback() -> dict:
    """执行一次 IMAP 扫描并回写 system_config 与 poller 状态文件。"""
    db = get_db()
    try:
        summary = scan_bounces()
        _set_config(db, "last_bounce_scan_at", _now_iso())
        _set_config(db, "last_imap_scan_result",
                    json.dumps({k: v for k, v in summary.items() if k not in ("errors", "dsns")},
                               ensure_ascii=False))
        _set_config(db, "last_dsn_scan", json.dumps(summary.get("dsns", []), ensure_ascii=False))
        db.commit()
        _write_poller_status(success=True)
        return summary
    except Exception as exc:
        try:
            _write_poller_status(success=False, error=str(exc))
        except Exception:
            pass
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 7. 内置 3 封模拟 Exmail DSN 样本（--self-test 用）
# ---------------------------------------------------------------------------

_SAMPLE_RECIPIENTS = [
    "info@gameuniverse.com",
    "info@djhobbytoys.com",
    "info@pulpfictioncomics.com",
]


def _sample_dsn(recipient: str, idx: int) -> str:
    """构造一封含 text/plain + message/delivery-status + message/rfc822 的 DSN 邮件。"""
    domain = recipient.split("@", 1)[1]
    return (
        "From: MAILER-DAEMON@exmail.qq.com\r\n"
        "To: ianyf@roktandrazo.com\r\n"
        "Subject: Delivery Status Notification (Failure)\r\n"
        f"Date: Wed, 5 Aug 2026 14:{10 + idx:02d}:00 +0800\r\n"
        f"Message-ID: <dsn-sample-{idx}@exmail.qq.com>\r\n"
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/report; report-type=delivery-status;\r\n'
        f'    boundary="dsn-boundary-{idx}"\r\n'
        "\r\n"
        f"--dsn-boundary-{idx}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Content-Transfer-Encoding: 7bit\r\n"
        "\r\n"
        "This is the mail system at host mx.exmail.qq.com.\r\n"
        "\r\n"
        f"<{recipient}>: host mx.{domain}[1.2.3.4] said:\r\n"
        f"    550 5.1.1 <{recipient}> recipient rejected. type=MX: Host not found\r\n"
        "    (in reply to RCPT TO command)\r\n"
        "\r\n"
        f"--dsn-boundary-{idx}\r\n"
        "Content-Type: message/delivery-status\r\n"
        "\r\n"
        "Reporting-MTA: dns; mx.exmail.qq.com\r\n"
        f"Arrival-Date: Wed, 5 Aug 2026 14:{10 + idx:02d}:00 +0800\r\n"
        "\r\n"
        f"Final-Recipient: rfc822; {recipient}\r\n"
        f"Original-Recipient: rfc822; {recipient}\r\n"
        "Action: failed\r\n"
        "Status: 5.1.1\r\n"
        f"Diagnostic-Code: smtp; 550 5.1.1 <{recipient}> recipient rejected. type=MX: Host not found\r\n"
        "\r\n"
        f"--dsn-boundary-{idx}\r\n"
        "Content-Type: message/rfc822\r\n"
        "\r\n"
        "From: Ian <ianyf@roktandrazo.com>\r\n"
        f"To: {recipient}\r\n"
        f"Subject: Wholesale catalog inquiry for {domain}\r\n"
        "Date: Wed, 5 Aug 2026 14:00:00 +0800\r\n"
        f"Message-ID: <orig-20260805-{idx}@roktandrazo.com>\r\n"
        "\r\n"
        "Hello, we are interested in your store. (original message body)\r\n"
        f"--dsn-boundary-{idx}--\r\n"
    )


_SAMPLE_DSNS = [_sample_dsn(r, i) for i, r in enumerate(_SAMPLE_RECIPIENTS, start=1)]


# ---------------------------------------------------------------------------
# 8. write_back_for_self_test —— 真实库回归
# ---------------------------------------------------------------------------

def write_back_for_self_test(conn: sqlite3.Connection) -> dict:
    """用 3 封内置样本跑「解析 → 分类 → 落库」并断言回归要点。

    验证：
      ① 3 封分类均为 domain_invalid
      ② 对应 leads 的 email_sendable=0, contact_recovery_required=1
      ③ contact_recovery 新增 3 条
      ④ 再次处理同 email 不重复插入 bounce_log（幂等）
    """
    processed = []
    for idx, raw in enumerate(_SAMPLE_DSNS, start=1):
        recipient = _SAMPLE_RECIPIENTS[idx - 1]
        parsed = parse_bounce_email(raw.encode("utf-8"))
        bt = classify_bounce(parsed.get("diagnostic_code"),
                             parsed.get("status_code"), parsed.get("raw_body"))
        assert bt == "domain_invalid", f"样本 {recipient} 应分类为 domain_invalid，实际: {bt}"
        record_unmatched_dsn(conn, parsed)
        processed.append({"recipient": recipient, "bounce_type": bt, "parsed": parsed})

    # ---- ② leads 回写断言 ----
    leads_check = {}
    for item in processed:
        lead = _one(conn, "SELECT * FROM leads WHERE email = ?", (item["recipient"],))
        assert lead is not None, f"leads 表缺少 {item['recipient']}"
        assert lead["email_sendable"] == 0, f"{item['recipient']} email_sendable 应为 0"
        assert lead["contact_recovery_required"] == 1, f"{item['recipient']} contact_recovery_required 应为 1"
        assert lead["status"] == "bounced", f"{item['recipient']} status 应为 bounced"
        leads_check[item["recipient"]] = {
            "id": lead["id"],
            "email_sendable": lead["email_sendable"],
            "contact_recovery_required": lead["contact_recovery_required"],
            "status": lead["status"],
        }

    # ---- ③ contact_recovery 断言（新增 3 条 pending） ----
    recovery_rows = _rows(
        conn,
        "SELECT * FROM contact_recovery WHERE email IN (?, ?, ?) AND status = 'pending'",
        tuple(_SAMPLE_RECIPIENTS),
    )
    assert len(recovery_rows) == 3, f"contact_recovery 应为 3 条 pending，实际 {len(recovery_rows)}"

    # ---- ④ 幂等断言：再次跑一遍，bounce_log 不再新增 ----
    before_counts = {}
    for recipient in _SAMPLE_RECIPIENTS:
        before_counts[recipient] = len(_rows(
            conn, "SELECT id FROM bounce_log WHERE email = ?", (recipient,)))

    for idx, raw in enumerate(_SAMPLE_DSNS, start=1):
        parsed = parse_bounce_email(raw.encode("utf-8"))
        record_unmatched_dsn(conn, parsed)

    for recipient in _SAMPLE_RECIPIENTS:
        after = len(_rows(conn, "SELECT id FROM bounce_log WHERE email = ?", (recipient,)))
        assert after == before_counts[recipient], (
            f"{recipient} 重复处理导致 bounce_log 新增（{before_counts[recipient]} -> {after}）"
        )

    return {
        "classified_domain_invalid": len(processed),
        "contact_recovery_added": len(recovery_rows),
        "leads": leads_check,
        "bounce_log_idempotent": True,
    }


# ---------------------------------------------------------------------------
# 9. __main__
# ---------------------------------------------------------------------------

def _run_self_test() -> int:
    print("=== bounce_pipeline --self-test（真实库回归） ===")
    conn = get_db()
    try:
        result = write_back_for_self_test(conn)
        print(f"  分类 domain_invalid 数量: {result['classified_domain_invalid']}")
        print(f"  contact_recovery 新增: {result['contact_recovery_added']}")
        print(f"  leads 回写: {json.dumps(result['leads'], ensure_ascii=False, indent=2)}")
        print(f"  bounce_log 幂等: {result['bounce_log_idempotent']}")

        unmatched = _rows(conn, "SELECT COUNT(*) AS c FROM unmatched_dsn")
        bounce_total = _rows(conn, "SELECT COUNT(*) AS c FROM bounce_log")
        print(f"  unmatched_dsn 表当前行数: {unmatched[0]['c']}")
        print(f"  bounce_log 表当前行数: {bounce_total[0]['c']}")

        # 逐封打印分类结果，便于人工核对
        for idx, raw in enumerate(_SAMPLE_DSNS, start=1):
            parsed = parse_bounce_email(raw.encode("utf-8"))
            bt = classify_bounce(parsed.get("diagnostic_code"),
                                 parsed.get("status_code"), parsed.get("raw_body"))
            print(f"  样本{idx} {_SAMPLE_RECIPIENTS[idx-1]} -> {bt}")
        print("=== self-test PASS ===")
        return 0
    except AssertionError as exc:
        print(f"=== self-test FAIL: {exc} ===")
        return 1
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return _run_self_test()
    if "--once" in argv:
        summary = run_scan_and_writeback()
        print("=== bounce_pipeline --once ===")
        print(json.dumps({k: v for k, v in summary.items() if k not in ("errors", "dsns")},
                         ensure_ascii=False, indent=2))
        if summary.get("errors"):
            print("errors:", json.dumps(summary["errors"], ensure_ascii=False))
        return 0
    print("用法: python bounce_pipeline.py --once | --self-test")
    return 2


if __name__ == "__main__":
    sys.exit(main())
