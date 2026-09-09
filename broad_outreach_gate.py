"""
Broad Outreach Ready Gate — 广泛匹配可发送层策略。

保留 Strict A0（通过 lead_hygiene_gate.py），新增 Broad Outreach Ready 作为主要批量 New Outreach 发送池。

原则：
- 只要商家与目标行业相关，且 rokt&razo 可能提供批发/定制/印刷/Private Label/生产服务，就允许首次外联。
- 不得把 Broad Outreach Ready 批量改名为 Strict A0。
- 硬安全阻断保留不变。软阻断（CONTACT_ROLE_UNCERTAIN、通用邮箱等）不再阻止 Broad。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlparse

# 统一 Email Hygiene 权威入口（P7）：本地 INVALID_EMAIL_PATTERNS 等为历史副本，
# 仅保留用于向后兼容；主判定一律走 email_hygiene.hygiene_check。
from email_hygiene import hygiene_check


# ═══════════════════════════════════════════════════════════
# 一、商业类别匹配
# ═══════════════════════════════════════════════════════════
BUSINESS_CATEGORIES = frozenset({
    "toy store", "game store", "board game store", "tabletop game store",
    "puzzle store", "card game store", "bookstore", "independent bookstore",
    "gift shop", "independent gift store", "museum gift shop", "museum store",
    "visitor center store", "visitor center gift shop", "tourist gift shop",
    "educational store", "educational supply store", "teacher supply store",
    "children's store", "hobby store", "comic store", "comic book store",
    "local specialty retailer", "specialty retailer", "independent retailer",
    "institution", "original product brand", "custom-product opportunity",
    "family game store", "independent toy store", "local gift shop",
    "book and gift store", "game and hobby store",
})

# ═══════════════════════════════════════════════════════════
# 二、服务机会匹配
# ═══════════════════════════════════════════════════════════
SERVICE_OPPORTUNITIES = frozenset({
    "ready-to-stock wholesale", "wholesale", "puzzles", "family card games",
    "card games", "private label", "custom cards", "custom puzzles",
    "printing", "packaging", "OEM", "production support",
    "board games", "custom game production", "game manufacturing",
})

# ═══════════════════════════════════════════════════════════
# 三、无效/系统邮箱检测
# ═══════════════════════════════════════════════════════════
INVALID_EMAIL_PATTERNS = re.compile(
    r'(example\.com|domain\.com|test\.com|anonymized|'
    r'noreply|no-reply|donotreply|@bot\.|@sentry|@anthropic|'
    r'\.png|\.jpg|\.gif|\.webp|\.jpeg|\.svg|\.css|\.js\b|'
    r'sentry\.io|wix\.com|square\.space|'
    r'@2x\b|\d+x\d+|'          # Image dimensions in email
    r'^www\.'                   # www. prefix in local-part
    r'|^xxx@|@xxx\.'            # placeholder emails xxx@xxx.xxx
    r')',
    re.IGNORECASE
)

# Additional post-regex checks (can't all be done in one regex)
def _has_url_like_local_part(email: str) -> bool:
    """Detect URL-like patterns in email local part (www. prefix, http, slashes)."""
    if not email:
        return False
    local = email.split('@')[0].lower() if '@' in email else email.lower()
    if local.startswith('www.'):
        return True
    if 'http' in local:
        return True
    if '/' in local:
        return True
    return False

def _has_resource_extension_in_email(email: str) -> bool:
    """Detect image/resource extensions anywhere in email."""
    ext_patterns = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.css', '.js', '.bmp', '.ico')
    lower = email.lower()
    return any(ext in lower for ext in ext_patterns)

def _is_hash_like_email(email: str) -> bool:
    """Detect hash/uuid-like local parts (32+ hex chars)."""
    if '@' not in email:
        return False
    local = email.split('@')[0]
    import re as _re
    return bool(_re.match(r'^[a-f0-9]{32,}$', local, _re.I))

SYSTEM_EMAIL_PREFIXES = frozenset({
    "no-reply", "noreply", "privacy", "copyright", "abuse",
    "postmaster", "mailer-daemon", "hostmaster", "webmaster",
})

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


# ═══════════════════════════════════════════════════════════
# 数据类
# ═══���═══════════════════════════════════════════════════════
@dataclass
class BroadOutreachDecision:
    """广泛匹配可发送层资格判定结果"""
    broad_outreach_ready: bool
    broad_fit_reason: str
    contact_source_confidence: str  # high / medium / low
    send_priority: str              # high / normal
    broad_blocked_reason: str = ""
    business_category: str = ""
    service_opportunity: str = ""
    organization_key: str = ""
    # ── 新增分离字段 ──
    broad_business_fit_passed: bool = False
    contact_hygiene_passed: bool = False


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════
def _extract_domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        host = (urlparse(str(url)).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _normalize_name(name: str) -> str:
    """规范化商家名称用于 organization_key fallback"""
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r'[^\w\s-]', '', n)
    n = re.sub(r'\s+', '-', n)
    return n


def _gen_organization_key(lead: Mapping[str, Any]) -> str:
    """为 organization_key 为空的线索生成稳定 fallback。
    
    优先级：
    1. 官方域名
    2. 规范化商家名称
    3. 名称+城市+州
    """
    # 如果已有 key，直接返回
    existing = str(lead.get("organization_key") or "").strip()
    if existing:
        return existing
    
    # 1. 官方域名
    website = str(lead.get("official_website") or "").strip()
    domain = _extract_domain(website)
    if domain:
        return f"org:domain:{domain}"
    
    # 2. 规范化商家名称
    name = str(lead.get("store_name") or "").strip()
    normalized = _normalize_name(name)
    if normalized:
        # 3. 名称+城市+州
        city = str(lead.get("city") or "").strip().lower()
        state = str(lead.get("state") or "").strip().upper()
        if city and state:
            return f"org:name:{normalized}:{city}:{state}"
        if city:
            return f"org:name:{normalized}:{city}"
        return f"org:name:{normalized}"
    
    # 最后兜底 — 不应该到这里，但防止空值
    identity = hashlib.sha256(
        f"{lead.get('id','')}:{lead.get('city','')}:{lead.get('state','')}".encode()
    ).hexdigest()[:16]
    return f"org:fallback:{identity}"


def _match_business_category(store_type: str, store_name: str, 
                             fit_reason: str, product_fit: str,
                             source_keyword: str, notes: str,
                             lead_segment: str, customer_type: str) -> tuple[str, str]:
    """判断商业类别是否与目标行业相关。
    
    Returns: (category, reason) 或 ("", "")
    """
    combined = " ".join(
        str(v or "").lower() 
        for v in (store_type, store_name, fit_reason, product_fit, 
                  source_keyword, notes, lead_segment, customer_type)
    )
    
    for cat in sorted(BUSINESS_CATEGORIES, key=len, reverse=True):
        if cat in combined:
            return cat, f"business_category_matched:{cat}"
    
    return "", ""


def _match_service_opportunity(fit_reason: str, product_fit: str, 
                                notes: str) -> tuple[str, str]:
    """判断是否存在 rokt&razo 服务机会。
    
    Returns: (service, reason) 或 ("", "")
    """
    combined = " ".join(
        str(v or "").lower() 
        for v in (fit_reason, product_fit, notes)
    )
    
    for svc in sorted(SERVICE_OPPORTUNITIES, key=len, reverse=True):
        if svc in combined:
            return svc, f"service_opportunity:{svc}"
    
    return "", ""


def _has_valid_business_email(lead: Mapping[str, Any]) -> tuple[bool, str, str]:
    """检查是否有公开业务联系方式（统一走 email_hygiene 权威入口）。
    
    Returns: (has_email, source_type, contact_source_confidence)
    """
    email = str(lead.get("email") or "").strip().lower()
    if not email:
        return False, "email_missing", "low"

    # 统一 Email Hygiene 权威判定（P7）；本地 regex 副本不再作为主判定
    hygiene = hygiene_check(email)
    if not hygiene["valid"]:
        return False, hygiene["reason"], "low"

    # 判断来源置信度
    source_type = str(lead.get("email_source_type") or "unknown")
    direct_sources = {"official_page_visible", "official_mailto", "wholesale_vendor_page"}
    medium_sources = {"public_directory", "retailer_directory", "social_page", 
                      "google_maps", "website_extracted", "webfetch_google_maps",
                      "website_http_verified", "inventory_website_scan",
                      "inventory_memphis_scan", "paizo_retailer_directory"}
    
    if source_type in direct_sources:
        confidence = "high"
    elif source_type in medium_sources:
        confidence = "medium"
    else:
        confidence = "low"
    
    return True, source_type, confidence


def _is_contact_form_only(lead: Mapping[str, Any]) -> bool:
    """判断是否仅联系表单"""
    if str(lead.get("status") or "") == "contact_form_pool":
        return True
    if lead.get("contact_form_only"):
        return True
    # 有 contact_form_url 但没有 email
    if lead.get("contact_form_url") and not lead.get("email"):
        return True
    return False


# ═══════════════════════════════════════════════════════════
# 硬安全阻断检查（与 send_log / bounce_log / suppression 等交叉）
# ═══════════════════════════════════════════════════════════
def _check_hard_blocks(lead: Mapping[str, Any], 
                        conn=None) -> tuple[bool, str]:
    """检查硬安全阻断。返回 (is_blocked, reason)。
    
    注意：该函数仅读取只读状态；不写 suppression/bounce_log/send_log。
    """
    lead_id = lead.get("id")
    email = str(lead.get("email") or "").strip().lower()
    org_key = lead.get("_computed_org_key", _gen_organization_key(lead))
    domain_hash = lead.get("domain_hash", "")
    
    # 1. invalid email
    if not email or not EMAIL_RE.fullmatch(email):
        return True, "invalid_email"
    if INVALID_EMAIL_PATTERNS.search(email):
        return True, "invalid_email_pattern"
    
    # 2. contact form only
    if _is_contact_form_only(lead):
        return True, "contact_form_only"
    
    # 3. previously sent (from history_status)
    history = str(lead.get("history_status") or "")
    if history == "previously_sent":
        return True, "previously_sent"
    if lead.get("sent_at"):
        return True, "previously_sent"
    
    # 3b. 从 send_log 检查（message_type 为空的历史发送也识别）
    # 注意：此处仅标记逻辑；实际 DB 查询在调用方执行
    # 调用方应在分析前预加载 send_log
    
    # 4. unsubscribed
    if lead.get("unsubscribed_at"):
        return True, "unsubscribed"
    
    # 5. bounced (hard/policy/permanent)
    if lead.get("bounced_at"):
        return True, "bounced"
    
    # 6. rejected / active defer
    status = str(lead.get("status") or "")
    if status in ("rejected", "failed"):
        return True, "rejected_or_failed"
    if lead.get("defer_reason"):
        return True, "active_defer"
    
    # 7. negative reply
    if lead.get("replied_at") and lead.get("notes"):
        notes_lower = str(lead.get("notes") or "").lower()
        neg_keywords = ["stop", "remove", "unsubscribe", "do not contact", 
                        "not interested", "don't contact"]
        if any(k in notes_lower for k in neg_keywords):
            return True, "negative_reply"
    
    # 8. delivery_issue
    if status == "delivery_issue":
        return True, "delivery_issue"
    
    # 9. bounce_review
    if status == "bounce_review":
        return True, "bounce_review_pending"
    
    # 10. exact duplicate — 由 domain_hash UNIQUE 约束保证
    #     (不在此处额外检查)
    
    # 11. organization previously sent
    if lead.get("organization_first_outreach_sent_at"):
        return True, "organization_previously_sent"
    
    # 12. shared-domain history — 通过 domain_hash + sent_at 交叉
    #     调用方应在分析前构建 sent_domains 集合
    
    return False, ""


# ═══════════════════════════════════════════════════════════
# 主判定函数
# ═══════════════════════════════════════════════════════════
def evaluate_broad_outreach(lead: Mapping[str, Any],
                            sent_domains: frozenset | None = None,
                            suppressed_emails: frozenset | None = None,
                            bounced_emails: frozenset | None = None,
                            sent_emails: frozenset | None = None,
                            sent_org_keys: frozenset | None = None,
                            negative_reply_ids: frozenset | None = None,
                            ) -> BroadOutreachDecision:
    """评估一条线索是否符合 Broad Outreach Ready。
    
    参数：
    - lead: 数据库行（Mapping）
    - sent_domains: 已发送过的 domain_hash 集合
    - suppressed_emails: 永久压制邮箱集合
    - bounced_emails: 退信邮箱集合
    - sent_emails: 已发送邮箱集合
    - sent_org_keys: 已发送组织 key 集合
    - negative_reply_ids: 负面回复的 lead_id 集合
    
    返回：BroadOutreachDecision
    """
    sent_domains = sent_domains or frozenset()
    suppressed_emails = suppressed_emails or frozenset()
    bounced_emails = bounced_emails or frozenset()
    sent_emails = sent_emails or frozenset()
    sent_org_keys = sent_org_keys or frozenset()
    negative_reply_ids = negative_reply_ids or frozenset()
    
    email = str(lead.get("email") or "").strip().lower()
    lead_id = lead.get("id")
    domain_hash = str(lead.get("domain_hash") or "")
    
    # ── 预计算 organization_key ──
    org_key = _gen_organization_key(lead)
    
    # ── 硬阻断检查（内联）──
    # Step 1: 基础数据有效性
    if not email:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "email_missing", "", "", org_key
        )
    
    if not EMAIL_RE.fullmatch(email):
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "invalid_email", "", "", org_key
        )
    
    if INVALID_EMAIL_PATTERNS.search(email):
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "invalid_email_pattern", "", "", org_key
        )
    
    local_part = email.split("@")[0].lower()
    if local_part in SYSTEM_EMAIL_PREFIXES:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "system_email", "", "", org_key
        )
    
    # Step 2: contact form only
    if _is_contact_form_only(lead):
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "contact_form_only", "", "", org_key
        )
    
    # Step 3: 历史发送（previously sent）
    if str(lead.get("history_status") or "") == "previously_sent":
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "previously_sent", "", "", org_key
        )
    
    if lead.get("sent_at"):
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "previously_sent", "", "", org_key
        )
    
    # Step 4: send_log 中的历史记录（预加载集合）
    if email in sent_emails:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "previously_sent", "", "", org_key
        )
    
    if domain_hash and domain_hash in sent_domains:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "shared_domain_previously_sent", "", "", org_key
        )
    
    if org_key in sent_org_keys:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "organization_previously_sent", "", "", org_key
        )
    
    # Step 5: suppression / bounce
    if email in suppressed_emails:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "permanently_suppressed", "", "", org_key
        )
    
    if email in bounced_emails:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "hard_bounced", "", "", org_key
        )
    
    # Step 6: unsubscribed / negative reply
    if lead.get("unsubscribed_at"):
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "unsubscribed", "", "", org_key
        )
    
    if lead_id in negative_reply_ids:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "negative_reply", "", "", org_key
        )
    
    # Step 7: 状态相关阻断
    status = str(lead.get("status") or "")
    if status in ("rejected", "failed", "delivery_issue", "bounce_review"):
        return BroadOutreachDecision(
            False, "", "low", "normal",
            f"status_blocked:{status}", "", "", org_key
        )
    
    if lead.get("defer_reason"):
        return BroadOutreachDecision(
            False, "", "low", "normal",
            "active_defer", "", "", org_key
        )
    
    # ── 商业类别匹配 ──
    store_type = str(lead.get("store_type") or "")
    store_name = str(lead.get("store_name") or "")
    fit_reason = str(lead.get("fit_reason") or "")
    product_fit = str(lead.get("product_fit") or "")
    source_keyword = str(lead.get("source_keyword") or "")
    notes = str(lead.get("notes") or "")
    lead_segment = str(lead.get("lead_segment") or "")
    customer_type = str(lead.get("customer_type") or "")
    
    category, cat_reason = _match_business_category(
        store_type, store_name, fit_reason, product_fit,
        source_keyword, notes, lead_segment, customer_type
    )
    
    if not category:
        # 宽松匹配：如果 store_type 或 fit_reason 非空且不为明显不相关的值，允许通过
        # 这处理了"商业匹配较广而不是高度精准"的场景
        store_type_lower = store_type.lower().strip()
        if store_type_lower and store_type_lower not in ("", "none", "unknown", "other"):
            category = f"broad:{store_type_lower}"
            cat_reason = "broad_category_from_store_type"
        else:
            return BroadOutreachDecision(
                False, "", "low", "normal",
                "business_category_not_matched", "", "", org_key
            )
    
    # ── 服务机会匹配 ──
    service, svc_reason = _match_service_opportunity(fit_reason, product_fit, notes)
    
    if not service:
        # 如果有商业类别匹配但没有显式服务机会，给予默认匹配
        # （所有目标行业默认有 wholesale/puzzles/card games 机会）
        if category in BUSINESS_CATEGORIES or category.startswith("broad:"):
            service = "ready-to-stock wholesale"
            svc_reason = "implied_by_business_category"
        else:
            return BroadOutreachDecision(
                False, "", "low", "normal",
                "service_opportunity_not_matched", category, "", org_key
            )
    
    # ── 联系方式检查 ──
    has_email, email_source, contact_confidence = _has_valid_business_email(lead)
    if not has_email:
        return BroadOutreachDecision(
            False, "", "low", "normal",
            f"no_valid_contact:{email_source}", category, service, org_key
        )
    
    # ── 判定 send_priority ──
    # 高优先级：直接来源、高置信度
    if contact_confidence == "high" and category in BUSINESS_CATEGORIES:
        send_priority = "high"
    elif contact_confidence == "high":
        send_priority = "high"
    elif contact_confidence == "medium" and category in BUSINESS_CATEGORIES:
        send_priority = "high"
    else:
        send_priority = "normal"
    
    # ── 构建 fit_reason ──
    fit_parts = []
    if cat_reason:
        fit_parts.append(cat_reason)
    if svc_reason:
        fit_parts.append(svc_reason)
    
    return BroadOutreachDecision(
        broad_outreach_ready=True,
        broad_fit_reason="; ".join(fit_parts),
        contact_source_confidence=contact_confidence,
        send_priority=send_priority,
        broad_blocked_reason="",
        business_category=category,
        service_opportunity=service,
        organization_key=org_key,
        broad_business_fit_passed=True,
        contact_hygiene_passed=True,
    )


# ═══════════════════════════════════════════════════════════
# 批量分析函数
# ═══════════════════════════════════════════════════════════
def analyze_all_leads(conn) -> dict:
    """对全量线索执行 Broad Outreach Ready 分析。
    
    Returns: 包含所有分类计数的字典。
    """
    import sqlite3
    conn.row_factory = sqlite3.Row
    
    # ── 预加载历史数据集 ──
    # 已发送域名
    sent_domain_rows = conn.execute("""
        SELECT DISTINCT l.domain_hash FROM send_log sl
        JOIN leads l ON sl.lead_id = l.id
        WHERE sl.status = 'sent'
    """).fetchall()
    sent_domains = frozenset(
        r["domain_hash"] for r in sent_domain_rows if r["domain_hash"]
    )
    
    # 已发送邮箱
    sent_email_rows = conn.execute("""
        SELECT DISTINCT LOWER(email) as email FROM send_log WHERE status = 'sent'
    """).fetchall()
    sent_emails = frozenset(r["email"] for r in sent_email_rows if r["email"])
    
    # 已发送组织 key
    sent_org_rows = conn.execute("""
        SELECT DISTINCT l.organization_key FROM send_log sl
        JOIN leads l ON sl.lead_id = l.id
        WHERE sl.status = 'sent' AND l.organization_key IS NOT NULL AND l.organization_key != ''
    """).fetchall()
    sent_org_keys = frozenset(r["organization_key"] for r in sent_org_rows if r["organization_key"])
    
    # 压制邮箱
    supp_rows = conn.execute("SELECT LOWER(email) as email FROM suppression_list").fetchall()
    suppressed_emails = frozenset(r["email"] for r in supp_rows if r["email"])
    
    # 退信邮箱（hard bounce — 检查 diagnostic_code 和 bounce_type）
    bounce_rows = conn.execute("""
        SELECT DISTINCT LOWER(email) as email FROM bounce_log
        WHERE LOWER(COALESCE(bounce_type,'')) != 'soft'
    """).fetchall()
    bounced_emails = frozenset(r["email"] for r in bounce_rows if r["email"])
    
    # 负面回复（summary/suggested_action 可能含负面信号）
    neg_rows = conn.execute("""
        SELECT lead_id FROM reply_log 
        WHERE LOWER(COALESCE(summary,'')) LIKE '%stop%' 
           OR LOWER(COALESCE(summary,'')) LIKE '%remove%' 
           OR LOWER(COALESCE(summary,'')) LIKE '%unsubscribe%'
           OR LOWER(COALESCE(summary,'')) LIKE '%do not contact%'
           OR LOWER(COALESCE(summary,'')) LIKE '%not interested%'
           OR LOWER(COALESCE(suggested_action,'')) LIKE '%suppress%'
           OR LOWER(COALESCE(suggested_action,'')) LIKE '%block%'
    """).fetchall()
    negative_reply_ids = frozenset(r["lead_id"] for r in neg_rows if r["lead_id"])
    
    # ── 获取全量线索 ──
    all_leads = conn.execute("SELECT * FROM leads").fetchall()
    
    # ── 分类计数 ──
    results = {
        "total_leads": len(all_leads),
        "strict_a0_locations": 0,
        "strict_a0_organizations": set(),
        "broad_ready_locations": [],
        "broad_ready_organizations": set(),
        "broad_org_opportunities": 0,
        "exception_review": [],
        "contact_recovery": [],
        "contact_form_only": [],
        "permanently_blocked": [],
        "previously_sent": [],
        "blocked_reasons": {},
        "org_key_patched": 0,
        "contact_role_uncertain_unblocked": 0,
        "invalid_email_excluded": 0,
    }
    
    # 先计算 Strict A0
    from lead_hygiene_gate import evaluate_a0
    
    for lead_dict in (dict(r) for r in all_leads):
        lead_id = lead_dict["id"]
        email = str(lead_dict.get("email") or "").strip().lower()
        status = str(lead_dict.get("status") or "")
        org_key_original = str(lead_dict.get("organization_key") or "").strip()
        org_key = _gen_organization_key(lead_dict)
        
        # 记录 org_key 补全
        if not org_key_original and org_key:
            results["org_key_patched"] += 1
            lead_dict["_org_key_patched"] = True
        
        lead_dict["_computed_org_key"] = org_key
        
        # ── Strict A0 判断 ──
        a0_decision = evaluate_a0(lead_dict)
        if a0_decision.a0_eligible:
            results["strict_a0_locations"] += 1
            results["strict_a0_organizations"].add(org_key)
        
        # ── Broad Outreach 判断 ──
        broad = evaluate_broad_outreach(
            lead_dict,
            sent_domains=sent_domains,
            suppressed_emails=suppressed_emails,
            bounced_emails=bounced_emails,
            sent_emails=sent_emails,
            sent_org_keys=sent_org_keys,
            negative_reply_ids=negative_reply_ids,
        )
        
        if broad.broad_outreach_ready:
            results["broad_ready_locations"].append({
                "lead_id": lead_id,
                "organization_key": org_key,
                "store_name": lead_dict.get("store_name", ""),
                "city": lead_dict.get("city", ""),
                "state": lead_dict.get("state", ""),
                "email": email,
                "business_category": broad.business_category,
                "broad_fit_reason": broad.broad_fit_reason,
                "contact_source": lead_dict.get("email_source_type", ""),
                "send_priority": broad.send_priority,
                "contact_source_confidence": broad.contact_source_confidence,
                "prev_sent": False,
                "suppressed": False,
                "bounced": False,
                "negative_reply": False,
                "allow_send": True,
            })
            results["broad_ready_organizations"].add(org_key)
            
            # 之前被 CONTACT_ROLE_UNCERTAIN 阻断的
            a0_reasons = set(a0_decision.reasons)
            if "email_source_not_official" in a0_reasons or "official_site_email_not_verified" in a0_reasons:
                if "email_missing" not in a0_reasons and "email_invalid" not in a0_reasons:
                    results["contact_role_uncertain_unblocked"] += 1
        
        else:
            blocked = broad.broad_blocked_reason
            if blocked:
                results["blocked_reasons"][blocked] = results["blocked_reasons"].get(blocked, 0) + 1
            
            if blocked in ("invalid_email", "invalid_email_pattern", "system_email"):
                results["invalid_email_excluded"] += 1
            
            if blocked == "previously_sent":
                results["previously_sent"].append(lead_dict)
            
            if blocked in ("contact_form_only",):
                results["contact_form_only"].append(lead_dict)
            
            if blocked in ("status_blocked:rejected", "status_blocked:failed",
                          "permanently_suppressed", "hard_bounced", "negative_reply",
                          "active_defer", "organization_previously_sent",
                          "shared_domain_previously_sent", "unsubscribed",
                          "delivery_issue", "bounce_review_pending"):
                results["permanently_blocked"].append(lead_dict)
            
            # Exception Review
            if blocked in ("business_category_not_matched", "service_opportunity_not_matched",
                          "email_missing"):
                results["exception_review"].append(lead_dict)
            
            # Contact Recovery
            if blocked in ("no_valid_contact:email_missing",):
                results["contact_recovery"].append(lead_dict)
    
    # ── 去重后计数 ──
    results["broad_org_opportunities"] = len(results["broad_ready_organizations"])
    results["strict_a0_organizations"] = len(results["strict_a0_organizations"])
    
    # ── 排序 broad 结果 ──
    results["broad_ready_locations"].sort(
        key=lambda x: (0 if x["send_priority"] == "high" else 1, 
                       str(x.get("city", "")), 
                       str(x.get("store_name", "")))
    )
    
    return results
