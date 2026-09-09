"""broad_ready.py — Broad Outreach Ready 统一判定（主发送池，P7）。

定位：
  - Broad Outreach Ready 是主发送池；Strict A0 只是"排序优先层"，不是唯一池。
  - 本模块是唯一权威判定；broad_outreach_gate.evaluate_broad_outreach 为历史实现，
    主判定统一收敛到 is_broad_outreach_ready。

原则：
  - BROAD_BLOCKERS 中的任意命中 → 硬阻断。
  - NON_BLOCKERS 明确不是 blocker（无 named buyer、CONTACT_ROLE_UNCERTAIN、
    Gmail、info/hello/contact/general 泛邮箱、无 strict A0 evidence snippet、
    retail/custom 混合等）。
  - third-party association mismatch 由调用方注入（ctx.association），
    或按 business association 规则（email_hygiene.validate_contact_business_association）判定。

只读：本模块绝不写库、绝不发送。
"""
from __future__ import annotations

import sqlite3
from typing import Any, FrozenSet, Mapping, Optional, Set

from email_hygiene import hygiene_check, normalize_email, validate_contact_business_association
from broad_outreach_gate import _gen_organization_key


# ═══════════════════════════════════════════════════════════
# 一、硬 blocker 集合
# ═══════════════════════════════════════════════════════════
BROAD_BLOCKERS: FrozenSet[str] = frozenset({
    "invalid_email",                 # 无邮箱 / 格式非法
    "image_fake_email",              # 图片/资源伪邮箱（.png/@2x/像素尺寸）
    "sentry_hash_system_address",    # sentry.io / hash 系统地址
    "third_party_mismatch",          # business association 不匹配（如 diane@sevendaysvt.com）
    "previously_sent_email",         # send_log 同 email 已发送
    "previously_sent_org",           # send_log 同 organization_key 已发送
    "shared_domain_org_history",     # 同域名组织已发送历史
    "unsubscribed",                  # 退订
    "suppression",                   # suppression_list 压制
    "hard_policy_permanent_bounce",  # hard/policy/permanent/domain_invalid 退信
    "negative_reply",                # 负面回复（stop/remove/not interested 等）
    "stop_contact",                  # do_not_contact 状态 / 明确要求停止联系
    "active_defer",                  # defer_reason 活跃推迟
    "recheck_pending",               # recheck_pending 待复核
    "duplicate",                     # 重复线索（exact duplicate / identity duplicate）
    "contact_form_only",             # 仅联系表单，无可用邮箱
    "example_test_address",          # example/test/localhost 占位地址
})

# ═══════════════════════════════════════════════════════════
# 二、明确不是 blocker 的信号
# ═══════════════════════════════════════════════════════════
NON_BLOCKERS: FrozenSet[str] = frozenset({
    "no_named_buyer",                # 无具名采购人
    "contact_role_uncertain",        # CONTACT_ROLE_UNCERTAIN
    "gmail",                         # Gmail 等免费邮箱
    "generic_info_mailbox",          # info@
    "generic_hello_mailbox",         # hello@
    "generic_contact_mailbox",       # contact@
    "generic_general_mailbox",       # general@
    "no_strict_a0_evidence_snippet", # 无 strict A0 证据片段（Broad 不强求）
    "retail_custom_mixed",           # retail/custom 混合业态
})

# hygiene reason → Broad blocker 标识
_HYGIENE_REASON_TO_BLOCKER = {
    "invalid_format": "invalid_email",
    "invalid_email_pattern": "invalid_email",
    "resource_extension_in_email": "image_fake_email",
    "url_like_local_part": "invalid_email",
    "hash_like_email": "sentry_hash_system_address",
    "system_email_address": "invalid_email",
    "sentry_system_address": "sentry_hash_system_address",
    "placeholder_domain": "example_test_address",
}

# 退信类型中视为永久性
_HARD_BOUNCE_TYPES = frozenset({"hard", "policy", "permanent", "domain_invalid"})

# 负面回复关键词（与 broad_outreach_gate / history_crosscheck 一致）
_NEGATIVE_KEYWORDS = ("stop", "remove", "unsubscribe", "do not contact",
                      "not interested", "don't contact", "suppress", "block")


# ═══════════════════════════════════════════════════════════
# 三、库查询辅助
# ═══════════════════════════════════════════════════════════

def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


# 公共免费邮箱域名：这些域名被无数互不相关的组织共用，
# 域名本身不能作为"同一组织"的判断依据（完整邮箱去重仍然生效）。
FREE_MAILBOX_DOMAINS: FrozenSet[str] = frozenset({
    "gmail.com", "googlemail.com",
    "yahoo.com", "ymail.com", "rocketmail.com",
    "hotmail.com", "hotmail.co.uk", "live.com", "outlook.com", "msn.com",
    "aol.com", "aim.com",
    "icloud.com", "me.com", "mac.com",
    "protonmail.com", "proton.me",
    "mail.com", "gmx.com", "zoho.com",
    "qq.com", "163.com", "126.com", "sina.com",
})


def _is_free_mailbox_domain(domain: str) -> bool:
    """判断是否为公共免费邮箱域名。"""
    if not domain:
        return False
    d = domain.lower().strip()
    if d in FREE_MAILBOX_DOMAINS:
        return True
    # 子域兜底（如 foo.gmail.com 等罕见场景）
    return any(d == f or d.endswith("." + f) for f in FREE_MAILBOX_DOMAINS)


def _load_db_signals(conn: sqlite3.Connection, email: str, org_key: str,
                     domain_hash: str, lead_id: Any) -> dict:
    """从库中读取发送/压制/退信/回复等信号（只读）。

    Returns: {
      suppressed, hard_bounced, negative_reply, sent_email, sent_org,
      shared_domain_sent, contact_form_only(由 lead 决定, 不入此 dict)
    }
    """
    if conn is None:
        return {"suppressed": False, "hard_bounced": False, "negative_reply": False,
                "sent_email": False, "sent_org": False, "shared_domain_sent": False}

    c = conn.cursor()
    signals = {
        "suppressed": False,
        "hard_bounced": False,
        "negative_reply": False,
        "sent_email": False,
        "sent_org": False,
        "shared_domain_sent": False,
    }
    try:
        if email:
            signals["suppressed"] = bool(
                c.execute("SELECT 1 FROM suppression_list WHERE lower(email)=? LIMIT 1", (email,)).fetchone())
            signals["hard_bounced"] = bool(
                c.execute(
                    "SELECT 1 FROM bounce_log WHERE lower(email)=? "
                    "AND lower(COALESCE(bounce_type,'')) IN ('hard','policy','permanent','domain_invalid') LIMIT 1",
                    (email,)).fetchone())
            signals["sent_email"] = bool(
                c.execute("SELECT 1 FROM send_log WHERE lower(email)=? AND status='sent' LIMIT 1", (email,)).fetchone())
            signals["negative_reply"] = signals["negative_reply"] or bool(
                c.execute(
                    "SELECT 1 FROM reply_log WHERE lower(email)=? AND ("
                    "lower(COALESCE(summary,'')) LIKE '%stop%' OR lower(COALESCE(summary,'')) LIKE '%remove%' "
                    "OR lower(COALESCE(summary,'')) LIKE '%unsubscribe%' OR lower(COALESCE(summary,'')) LIKE '%do not contact%' "
                    "OR lower(COALESCE(summary,'')) LIKE '%not interested%' "
                    "OR lower(COALESCE(suggested_action,'')) LIKE '%suppress%' OR lower(COALESCE(suggested_action,'')) LIKE '%block%'"
                    ") LIMIT 1", (email,)).fetchone())
        if lead_id is not None:
            signals["negative_reply"] = signals["negative_reply"] or bool(
                c.execute(
                    "SELECT 1 FROM reply_log WHERE lead_id=? AND ("
                    "lower(COALESCE(summary,'')) LIKE '%stop%' OR lower(COALESCE(summary,'')) LIKE '%remove%' "
                    "OR lower(COALESCE(summary,'')) LIKE '%unsubscribe%' OR lower(COALESCE(summary,'')) LIKE '%do not contact%' "
                    "OR lower(COALESCE(summary,'')) LIKE '%not interested%' "
                    "OR lower(COALESCE(suggested_action,'')) LIKE '%suppress%' OR lower(COALESCE(suggested_action,'')) LIKE '%block%'"
                    ") LIMIT 1", (lead_id,)).fetchone())
        if org_key:
            signals["sent_org"] = bool(
                c.execute(
                    "SELECT 1 FROM send_log sl JOIN leads l ON sl.lead_id=l.id "
                    "WHERE sl.status='sent' AND l.organization_key=? LIMIT 1", (org_key,)).fetchone())
        if domain_hash:
            signals["shared_domain_sent"] = bool(
                c.execute(
                    "SELECT 1 FROM send_log sl JOIN leads l ON sl.lead_id=l.id "
                    "WHERE sl.status='sent' AND l.domain_hash=? LIMIT 1", (domain_hash,)).fetchone())
        elif email:
            domain = _email_domain(email)
            # Free public mailbox domains (gmail/yahoo/hotmail/aol/outlook/...) are
            # shared by millions of unrelated businesses — the domain alone does NOT
            # identify the same organization. Skip the %@domain history check for them.
            # Dedup for those relies on exact email, organization_key, suppression and
            # send_log history which are all checked separately above.
            if domain and not _is_free_mailbox_domain(domain):
                signals["shared_domain_sent"] = bool(
                    c.execute(
                        "SELECT 1 FROM send_log WHERE lower(email) LIKE ? AND status='sent' LIMIT 1",
                        (f"%@{domain}",)).fetchone())
    except sqlite3.Error:
        # 只读审计：任何库异常都不抛，避免阻断调用方
        pass
    return signals


def _is_contact_form_only(lead: Mapping[str, Any]) -> bool:
    if str(lead.get("status") or "") == "contact_form_pool":
        return True
    if lead.get("contact_form_only"):
        return True
    if lead.get("contact_form_url") and not str(lead.get("email") or "").strip():
        return True
    return False


# ═══════════════════════════════════════════════════════════
# 四、主判定
# ═══════════════════════════════════════════════════════════

def is_broad_outreach_ready(lead: Mapping[str, Any], ctx: Optional[Mapping[str, Any]] = None) -> dict:
    """Broad Outreach Ready 主判定。

    参数：
      lead — 线索行（Mapping），字段与 leads 表一致。
      ctx  — 上下文（可注入，也可让函数内查库）：
        conn               — sqlite3.Connection；提供后函数内查 suppression/bounce/reply/send_log/contact_form
        hygiene            — hygiene_check 结果 dict（可选，缺省函数内调）
        association        — business association 结果 dict {"ok": bool, "reason": str}（可选）
        sent_emails        — 已发送邮箱集合（可选，避免查库）
        sent_org_keys      — 已发送组织 key 集合（可选）
        sent_domains       — 已发送域名集合（domain_hash）（可选）
        suppressed_emails  — 压制邮箱集合（可选）
        bounced_emails     — 永久退信邮箱集合（可选）
        negative_reply_ids — 负面回复 lead_id 集合（可选）
        mx                 — mx_status_from_dns 结果字符串或 {"status": ...}（可选，仅记录）

    返回：{"ready": bool, "blockers": [...], "ready_reason": str}
    """
    ctx = dict(ctx or {})
    conn = ctx.get("conn")

    email = normalize_email(str(lead.get("email") or ""))
    org_key = str(lead.get("organization_key") or "") or _gen_organization_key(lead)
    domain_hash = str(lead.get("domain_hash") or "")
    lead_id = lead.get("id")

    blockers: list[str] = []

    # ── 1. Email Hygiene（权威）──
    if not email:
        blockers.append("invalid_email")
    else:
        hygiene = ctx.get("hygiene") or hygiene_check(email)
        if not hygiene.get("valid"):
            blockers.append(_HYGIENE_REASON_TO_BLOCKER.get(
                str(hygiene.get("reason") or ""), "invalid_email"))

    # ── 2. 仅联系表单 ──
    if _is_contact_form_only(lead):
        blockers.append("contact_form_only")

    # ── 3. 库信号 / 注入集合 ──
    db_signals = _load_db_signals(conn, email, org_key, domain_hash, lead_id) if conn is not None else {}

    suppressed_emails = ctx.get("suppressed_emails") or set()
    bounced_emails = ctx.get("bounced_emails") or set()
    sent_emails = ctx.get("sent_emails") or set()
    sent_org_keys = ctx.get("sent_org_keys") or set()
    sent_domains = ctx.get("sent_domains") or set()
    negative_reply_ids = ctx.get("negative_reply_ids") or set()

    if email:
        if email in suppressed_emails or db_signals.get("suppressed"):
            blockers.append("suppression")
        if email in bounced_emails or db_signals.get("hard_bounced"):
            blockers.append("hard_policy_permanent_bounce")
        if email in sent_emails or db_signals.get("sent_email"):
            blockers.append("previously_sent_email")

    if org_key and (org_key in sent_org_keys or db_signals.get("sent_org")):
        blockers.append("previously_sent_org")
    if (domain_hash and domain_hash in sent_domains) or db_signals.get("shared_domain_sent"):
        blockers.append("shared_domain_org_history")

    if lead_id in negative_reply_ids or db_signals.get("negative_reply"):
        blockers.append("negative_reply")

    # ── 4. lead 内状态字段 ──
    status = str(lead.get("status") or "").lower()
    if status in ("do_not_contact", "stop_contact"):
        blockers.append("stop_contact")
    if lead.get("unsubscribed_at") or status == "unsubscribed":
        blockers.append("unsubscribed")
    if lead.get("defer_reason"):
        blockers.append("active_defer")
    if lead.get("recheck_pending"):
        blockers.append("recheck_pending")

    # 重复线索（history_status / history 注入）
    history_status = str(lead.get("history_status") or "")
    if history_status in ("duplicate", "exact_duplicate", "identity_duplicate_new_email"):
        blockers.append("duplicate")

    # 历史退信/已发送字段（lead 上冗余标记）
    if lead.get("bounced_at"):
        blockers.append("hard_policy_permanent_bounce")
    if lead.get("sent_at"):
        blockers.append("previously_sent_email")
    if lead.get("organization_first_outreach_sent_at"):
        blockers.append("previously_sent_org")

    # ── 5. third-party association mismatch ──
    assoc = ctx.get("association")
    if isinstance(assoc, dict) and not assoc.get("ok"):
        blockers.append("third_party_mismatch")
    elif email:
        ok, reason = validate_contact_business_association(lead)
        if not ok:
            # 仅对明确的第三方/目录/新闻域阻断；domain_mismatch_accepted 不阻断
            if reason.startswith("directory_domain") or reason.startswith("news_media") \
                    or reason.startswith("sentry") or reason == "no_valid_email":
                blockers.append("third_party_mismatch")

    # ── 去重并判定 ──
    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    if ready:
        ready_reason = "broad_outreach_ready"
    else:
        ready_reason = "blocked:" + ",".join(blockers)

    return {"ready": ready, "blockers": blockers, "ready_reason": ready_reason}
