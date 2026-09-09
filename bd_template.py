"""
Roktandrazo BD Outreach - Email Template V5 (LOCKED 2026-08-03)

Templates:
  retail_distributor_v5_locked     — ACTIVE_LOCKED (puzzle/toy/game/book/hobby stores)
  custom_printing_production_v5_locked — ACTIVE_LOCKED (gift/museum/artist/designer/custom production)
  follow_up_v1_locked              — LOCKED_DISABLED (FOLLOW_UP_ENABLED=false)

Routing: route_template_for_lead(lead) → template_key based on store_type.
Manual override from Review Center takes precedence.
"""

SIGNATURE_TEXT = """
Ian
Business Development Specialist
website: roktandrazo.com


If this isn't relevant, just reply "unsubscribe" and I won't follow up.
"""

SIGNATURE_HTML = """<p><strong>Ian</strong><br>
Business Development Specialist</p>
<p>website: <a href="https://roktandrazo.com">roktandrazo.com</a></p>
<hr>
<p><small>If this isn't relevant, just reply "unsubscribe" and I won't follow up.</small></p>
"""

def _subject_for(store_name: str) -> str:
    return f'Premium puzzles & card games for {store_name} (Low MOQ / DDP)'

BODY_TEXT = """Hi {greeting},

I'm Ian from rokt&razo. We are a puzzle and family card game brand with 10+ years of experience in product development, manufacturing, and custom production. In addition to our own branded products, we also support many U.S. brands and independent artists with custom production.

We are currently expanding our U.S. retail and distributor network, and I wanted to see if there may be an opportunity to work together. We offer:

- Low MOQs and DDP pricing for rokt&razo branded products
- Premium jigsaw puzzles and family card games
- Custom and private-label production options
- Supply chain support to help improve cost, quality, and production efficiency

We'd be happy to send a complimentary sample so you can evaluate the product firsthand.

If you're interested, I'd be happy to send over our latest catalogue, including very unique 24-in-1 puzzle series, which has received very positive customer feedback.

If you also have your own branded products, we'd be happy to discuss custom production opportunities as well.

{pixel}

{signature}
"""

BODY_HTML = """<p>Hi {greeting},</p>

<p>I'm Ian from <strong>rokt&amp;razo</strong>. We are a puzzle and family card game brand with 10+ years of experience in product development, manufacturing, and custom production. In addition to our own branded products, we also support many U.S. brands and independent artists with custom production.</p>

<p>We are currently expanding our U.S. retail and distributor network, and I wanted to see if there may be an opportunity to work together. We offer:</p>

<ul>
<li>Low MOQs and DDP pricing for rokt&amp;razo branded products</li>
<li>Premium jigsaw puzzles and family card games</li>
<li>Custom and private-label production options</li>
<li>Supply chain support to help improve cost, quality, and production efficiency</li>
</ul>

<p>We'd be happy to send a complimentary sample so you can evaluate the product firsthand.</p>

<p>If you're interested, I'd be happy to send over our latest catalogue, including very unique 24-in-1 puzzle series, which has received very positive customer feedback.</p>

<p>If you also have your own branded products, we'd be happy to discuss custom production opportunities as well.</p>

{pixel}

{signature}
"""

# ── Custom Printing & Production Template ───────────────
# Independent body (NOT shared with retail_distributor).
# Subject: "Custom Production & Procurement Support for {{Store Name}}"
# Activated 2026-08-03 per user confirmation.

def _subject_custom_printing_for(store_name: str) -> str:
    return f'Custom Production & Procurement Support for {store_name}'

CUSTOM_BODY_TEXT = """Hi {greeting},

I'm Ian from rokt&razo. We are a custom printing and production partner with 10+ years of experience in the industry. We support many U.S. brands, independent artists, designers, and retailers with custom product development, printing, packaging, and sourcing — from small test runs to full-scale production.

We are currently expanding our U.S. production partner network, and I wanted to see if there may be an opportunity to work together. We offer:

- Custom production and private-label development
- Printing, packaging, and assembly services
- Supply chain and procurement support
- Low minimums and flexible production runs

We'd be happy to discuss your current or upcoming production needs.

If you're interested, I'd be happy to send over our latest catalogue and capabilities overview. We've completed projects ranging from custom puzzles and card games to branded merchandise, packaging, and specialty print work.

{pixel}

{signature}
"""

CUSTOM_BODY_HTML = """<p>Hi {greeting},</p>

<p>I'm Ian from <strong>rokt&amp;razo</strong>. We are a custom printing and production partner with 10+ years of experience in the industry. We support many U.S. brands, independent artists, designers, and retailers with custom product development, printing, packaging, and sourcing — from small test runs to full-scale production.</p>

<p>We are currently expanding our U.S. production partner network, and I wanted to see if there may be an opportunity to work together. We offer:</p>

<ul>
<li>Custom production and private-label development</li>
<li>Printing, packaging, and assembly services</li>
<li>Supply chain and procurement support</li>
<li>Low minimums and flexible production runs</li>
</ul>

<p>We'd be happy to discuss your current or upcoming production needs.</p>

<p>If you're interested, I'd be happy to send over our latest catalogue and capabilities overview. We've completed projects ranging from custom puzzles and card games to branded merchandise, packaging, and specialty print work.</p>

{pixel}

{signature}
"""

# ── Template Registry ────────────────────────────────────

import hashlib as _hashlib

_TEMPLATE_REGISTRY = {
    "retail_distributor_v5_locked": {
        "status": "ACTIVE_LOCKED",
        "subject_fn": _subject_for,
        "body_text": BODY_TEXT,
        "body_html": BODY_HTML,
        "signature_text": SIGNATURE_TEXT,
        "signature_html": SIGNATURE_HTML,
        "canonical_subject_prefix": "Premium puzzles & card games for ",
    },
    "custom_printing_production_v5_locked": {
        "status": "ACTIVE_LOCKED",
        "subject_fn": _subject_custom_printing_for,
        "body_text": CUSTOM_BODY_TEXT,
        "body_html": CUSTOM_BODY_HTML,
        "signature_text": SIGNATURE_TEXT,
        "signature_html": SIGNATURE_HTML,
        "canonical_subject_prefix": "Custom Production & Procurement Support for ",
    },
    "follow_up_v1_locked": {
        "status": "LOCKED_DISABLED",
        "subject_fn": None,
        "body_text": None,
        "body_html": None,
        "signature_text": None,
        "signature_html": None,
        "canonical_subject_prefix": None,
    },
}

# Canonical SHA-256 hashes for integrity validation
_TEMPLATE_SHA256 = {}

def _compute_template_hashes():
    """Compute SHA-256 of canonical body texts for send-time validation."""
    for key, tpl in _TEMPLATE_REGISTRY.items():
        if tpl["body_text"] is None:
            _TEMPLATE_SHA256[key] = "DISABLED"
            continue
        content = tpl["body_text"] + "|||" + tpl["body_html"] + "|||" + tpl["signature_text"]
        _TEMPLATE_SHA256[key] = _hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]

_compute_template_hashes()

# ── Store Type → Template Routing ────────────────────────

# Gift shops, museum stores, artists, designers → custom printing
_CUSTOM_PRINTING_TYPES = frozenset({
    "gift_shop", "gift shop",
    "souvenir_store", "souvenir store",
    "museum_store", "museum store",
    "independent_artist", "independent artist",
    "designer",
    "publisher",
    "brand_owner", "brand owner",
    "private_label", "private label",
    "custom_merchandise", "custom merchandise",
    "oem",
})

# Puzzle, toy, game, book, hobby, educational → retail distributor
_RETAIL_DISTRIBUTOR_TYPES = frozenset({
    "puzzle_store", "puzzle store",
    "toy_store", "toy store",
    "game_store", "game store",
    "board_game_store", "board game store",
    "card_store", "card store",
    "hobby_store", "hobby store",
    "bookstore",
    "educational_store", "educational retailer",
    "distributor",
    "wholesaler",
    "comic_store", "comic store",
    "childrens_store", "childrens store",
})


def route_template_for_lead(lead: dict) -> str:
    """Determine which template to use based on store_type.
    
    Manual override (lead['template_override']) takes absolute precedence.
    Default: retail_distributor_v5_locked for mixed/unknown types.
    Gift shops default to custom_printing_production_v5_locked.
    """
    override = (lead.get("template_override") or "").strip()
    if override in _TEMPLATE_REGISTRY:
        return override
    
    store_type = (lead.get("store_type") or "").strip().lower().replace("-", "_")
    
    if store_type in _CUSTOM_PRINTING_TYPES:
        return "custom_printing_production_v5_locked"
    
    # Puzzle/toy/game/book → retail distributor
    if store_type in _RETAIL_DISTRIBUTOR_TYPES:
        return "retail_distributor_v5_locked"
    
    # Heuristic: if store has "gift" or "museum" in store_type or name
    name = (lead.get("store_name") or "").lower()
    if any(kw in name for kw in ["gift", "museum", "artist", "design", "print", "custom", "oem"]):
        return "custom_printing_production_v5_locked"
    
    # Default: retail distributor
    return "retail_distributor_v5_locked"


def get_template_status(template_key: str) -> str:
    """Return the status of a template key. Raises KeyError if not found."""
    return _TEMPLATE_REGISTRY[template_key]["status"]


def get_template_sha256(template_key: str) -> str:
    """Return canonical SHA-256 first 8 chars for integrity check."""
    return _TEMPLATE_SHA256.get(template_key, "UNKNOWN")


import os as _os_followup

# Follow-up 发送开关由系统配置控制（环境变量 BD_FOLLOW_UP_ENABLED，默认关闭）。
# 不在模板模块永久硬编码，业务规则由系统配置/编排层决定。
FOLLOW_UP_ENABLED = _os_followup.environ.get("BD_FOLLOW_UP_ENABLED", "false").lower() == "true"

# ── Forbidden inline phrases (fail-closed) ───────────────
_INLINE_FORBIDDEN_PHRASES = [
    "A catalogue is available on request.",
    "friendly minimums",
    "Ian from Rokt&Razo here.",
    "We produce premium puzzles and card games for independent retailers",
]


def check_inline_forbidden(body_text: str) -> list:
    """Return list of forbidden phrases found in body text. Empty = clean."""
    return [p for p in _INLINE_FORBIDDEN_PHRASES if p in (body_text or "")]


# ── Follow-up Template (V5) ──────────────────────────────
# Does NOT repeat the initial outreach body.
# Open-ended — does NOT force a wholesale-vs-custom choice.

FOLLOWUP_SIGNATURE_TEXT = """Best,
Ian
Business Development Specialist
rokt&razo
website: roktandrazo.com
"""

FOLLOWUP_SIGNATURE_HTML = """<p>Best,<br><strong>Ian</strong><br>
Business Development Specialist<br>
rokt&amp;razo</p>
<p>website: <a href="https://roktandrazo.com">roktandrazo.com</a></p>
"""

FOLLOWUP_BODY_TEXT = """Hi {greeting},

Just wanted to follow up and better understand what would be most useful for your store right now.

Are there any product categories, price points, themes, or production needs that you are currently looking to add, improve, or source more effectively?

We support ready-to-stock games and puzzles, as well as custom and private-label development, printing, packaging, and production support. I'd be happy to prepare information based on what you're actually looking for.

{pixel}

{signature}
"""

FOLLOWUP_BODY_HTML = """<p>Hi {greeting},</p>

<p>Just wanted to follow up and better understand what would be most useful for your store right now.</p>

<p>Are there any product categories, price points, themes, or production needs that you are currently looking to add, improve, or source more effectively?</p>

<p>We support ready-to-stock games and puzzles, as well as custom and private-label development, printing, packaging, and production support. I'd be happy to prepare information based on what you're actually looking for.</p>

{pixel}

{signature}
"""

# ── Tracking configuration (env-driven, default OFF) ──
import os
import re
import secrets
import hashlib
import hmac as _hmac

# ── Tracking configuration (env-driven, default OFF) ──
EMAIL_ENGAGEMENT_PROVIDER = os.environ.get("EMAIL_ENGAGEMENT_PROVIDER", "disabled")
EMAIL_OPEN_TRACKING_ENABLED = os.environ.get("EMAIL_OPEN_TRACKING_ENABLED", "false").lower() == "true"
EMAIL_CLICK_TRACKING_ENABLED = os.environ.get("EMAIL_CLICK_TRACKING_ENABLED", "false").lower() == "true"
PIXEL_TRACKING_ENABLED = EMAIL_OPEN_TRACKING_ENABLED  # alias for backward compat

TRACKING_BASE_URL = os.environ.get(
    "EMAIL_TRACKING_PUBLIC_BASE_URL",
    "https://roktandrazo-email-tracker.1569032023yf.workers.dev"
)
# P7：TRACKING_PEPPER 不再硬编码默认值；优先 BD_TRACKING_PEPPER，
# 兼容旧的 EMAIL_TRACKING_PEPPER；两者都为空时 _hmac 相关函数 fail-closed。
TRACKING_PEPPER = os.environ.get("BD_TRACKING_PEPPER") or os.environ.get("EMAIL_TRACKING_PEPPER") or ""

# Designated test recipients — only these emails get pixel tracking
TRACKING_TEST_EMAILS = set(
    e.strip().lower() for e in
    os.environ.get("EMAIL_TRACKING_TEST_RECIPIENTS", "").split(",")
    if e.strip()
)

PIXEL_HTML = (
    f'<img src="{TRACKING_BASE_URL}/o/{{token}}.gif" '
    'width="1" height="1" alt="" '
    'style="display:block;width:1px;height:1px;border:0;" />'
)
# Label used in UI — NEVER "已阅读" or "confirmed read"
PIXEL_UI_LABEL = "检测到邮件图片加载"


def _make_token_hash(token: str) -> str:
    # P7：pepper 为空 → fail-closed（抛错），不能用空串/硬编码继续工作
    if not TRACKING_PEPPER:
        raise RuntimeError(
            "TRACKING_PEPPER 未配置：请设置环境变量 BD_TRACKING_PEPPER（或 EMAIL_TRACKING_PEPPER），"
            "追踪 token 签名不可用（fail-closed）。"
        )
    return _hmac.new(TRACKING_PEPPER.encode(), token.encode(), hashlib.sha256).hexdigest()


def _make_tracking_message_id(lead_id, plan_entry_id="") -> str:
    return f"prod_{lead_id}_{plan_entry_id or 'no_plan'}"


def prepare_tracking_for_lead(lead: dict, plan_entry_id: str = "") -> dict:
    """Generate tracking token + pixel HTML for one lead. Returns tracking info dict."""
    token = secrets.token_urlsafe(24)
    token_hash = _make_token_hash(token)
    tracking_message_id = _make_tracking_message_id(lead.get("id", 0), plan_entry_id)
    pixel_html = PIXEL_HTML.format(token=token)
    return {
        "token": token,
        "token_hash": token_hash,
        "tracking_message_id": tracking_message_id,
        "pixel_html": pixel_html,
        "lead_id": lead.get("id", 0),
        "organization_key": lead.get("organization_key", ""),
        "plan_entry_id": plan_entry_id,
    }


def _pixel_html_for_email(email: str) -> str:
    """Return pixel HTML only if tracking is enabled for this recipient."""
    if not PIXEL_TRACKING_ENABLED:
        return ""
    # In TEST mode: only track designated test emails
    # In PRODUCTION mode (PIXEL_TRACKING_ENABLED=true + TRACKING_TEST_EMAILS empty): all emails tracked
    if TRACKING_TEST_EMAILS and email.strip().lower() not in TRACKING_TEST_EMAILS:
        return ""
    token = secrets.token_urlsafe(24)
    return PIXEL_HTML.format(token=token)


# ── 排版压缩渲染器（P0：邮件排版恢复）────────────────────
# 大空白根因：{pixel} 占位在追踪关闭时替换为空串留下 4 个空行，
#   SIGNATURE_TEXT 尾部还有 2 个硬编码空行，合计 text/plain 的
#   署名/退订被 6 个空行推挤。此渲染器只对 format 后的成品做排版
#   压缩，不改动任何模板常量（保证 _TEMPLATE_SHA256 不变）。
RENDERER_VERSION = "email_html_compact_v1"
RENDERER_SHA256 = None  # 底部 _compute_renderer_hash() 填充


def _compact_render(body_text: str, body_html: str) -> tuple[str, str]:
    """对 format 后的成品做排版压缩，返回 (压缩后的 text, 压缩后的 html)。

    - text: 用 re.sub(r'\\n{3,}', '\\n\\n', body_text) 把连续 3+ 换行压成
      1 个空行（正文→署名、署名→退订各恰 1 空行），再 strip。
    - html: 用 re.sub(r'\\n{2,}', '\\n', body_html) 压缩空行（HTML 空行
      渲染无影响，但保持源码紧凑），再 strip。
    - 若 html 含 tracking pixel（按 src 特征判定），必须恰好 1 个。
    """
    compact_text = re.sub(r"\n{3,}", "\n\n", body_text).strip()
    compact_html = re.sub(r"\n{2,}", "\n", body_html).strip()

    # tracking pixel 的 src 特征（PIXEL_HTML 的 URL 前缀）
    pixel_src_feature = f"{TRACKING_BASE_URL}/o/"
    if pixel_src_feature in body_html:
        pixel_count = compact_html.count(pixel_src_feature)
        if pixel_count != 1:
            raise ValueError(
                f"RENDERER_REJECTED: tracking pixel count={pixel_count}, "
                f"expected exactly 1 in html body"
            )
    return compact_text, compact_html


def _safety_check(text: str) -> list:
    issues = []
    if "{{" in text or "}}" in text:
        issues.append("Unreplaced template braces {{}}")
    if "undefined" in text.lower():
        issues.append("Contains 'undefined'")
    if "None" in text:
        issues.append("Contains Python 'None'")
    if "null" in text.lower():
        issues.append("Contains 'null'")
    if "&ndash;" in text:
        issues.append("Raw HTML entity &ndash;")
    if "&amp;" in text and "<" not in text:
        issues.append("Raw HTML entity &amp; outside HTML context")
    if "stationary" in text.lower():
        issues.append("stationary typo (should be stationery)")
    return issues


def get_email_for_lead(lead: dict, template_key: str = None, tracking: dict = None) -> dict:
    """Generate email content for a lead. Routes template based on store_type.
    
    If template_key is provided and valid, uses that. Otherwise routes via route_template_for_lead().
    If tracking dict is provided (from prepare_tracking_for_lead), use its pixel_html.
    """
    # Route template
    if not template_key or template_key not in _TEMPLATE_REGISTRY:
        template_key = route_template_for_lead(lead)
    
    tpl = _TEMPLATE_REGISTRY[template_key]
    if tpl["status"] == "LOCKED_DISABLED":
        raise ValueError(f"Template {template_key} is LOCKED_DISABLED. Cannot generate email.")
    
    store_name = (lead.get("store_name") or "").strip()
    if not store_name or store_name.lower() in ("null", "none", "undefined"):
        greeting = "there"
        subject = tpl["subject_fn"]("your store")
    else:
        greeting = f"{store_name} team"
        subject = tpl["subject_fn"](store_name)
    
    email_addr = (lead.get("email") or "").strip()
    if tracking and tracking.get("pixel_html"):
        pixel = tracking["pixel_html"]
    else:
        pixel = _pixel_html_for_email(email_addr)
    
    body_text = tpl["body_text"].format(greeting=greeting, pixel="", signature=tpl["signature_text"])
    body_html = tpl["body_html"].format(greeting=greeting, pixel=pixel, signature=tpl["signature_html"])

    # 排版压缩：消除 {pixel} 空占位 + 署名尾部硬编码空行造成的大空白
    body_text, body_html = _compact_render(body_text, body_html)
    
    for label, content in [("text", body_text), ("html", body_html)]:
        issues = _safety_check(content)
        if issues:
            print(f"  WARNING [{label}]: {'; '.join(issues)}")
    
    # Fail-closed: check for forbidden inline phrases
    forbidden = check_inline_forbidden(body_text)
    if forbidden:
        raise ValueError(
            f"TEMPLATE_REJECTED: forbidden phrase(s) found: {forbidden}. "
            f"Body contains unapproved short template. SMTP blocked."
        )
    
    return {
        "template_key": template_key,
        "template_status": tpl["status"],
        "template_sha256": _TEMPLATE_SHA256[template_key],
        "content_sha256": _TEMPLATE_SHA256[template_key],
        "renderer_version": RENDERER_VERSION,
        "renderer_sha256": RENDERER_SHA256,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "body_html_no_pixel": _compact_render(
            "", tpl["body_html"].format(greeting=greeting, pixel="", signature=tpl["signature_html"])
        )[1],
        "has_pixel": bool(pixel),
        "routing_reason": "manual_override" if lead.get("template_override") else "store_type",
        "store_type": lead.get("store_type", ""),
    }


def get_followup_email_for_lead(lead: dict, original_subject: str = "",
                                 original_message_id: str = "",
                                 tracking: dict = None) -> dict:
    """Generate a follow-up email for a lead that has already received an initial outreach.

    Key design:
      - Open-ended — does NOT force a choice between wholesale and custom.
      - Does NOT repeat the initial outreach body.
      - Subject is "Re: {original_subject}" to maintain the email thread.
      - In-Reply-To and References headers reference the original Message-ID.
      - Fresh tracking token per follow-up (never reuse the initial token).

    Returns a dict with all fields needed by bd_sender.send_one() plus
    extra fields for In-Reply-To / References header injection.
    """
    store_name = (lead.get("store_name") or "").strip()
    if not store_name or store_name.lower() in ("null", "none", "undefined"):
        greeting = "there"
    else:
        greeting = f"{store_name} team"

    email_addr = (lead.get("email") or "").strip()
    if tracking and tracking.get("pixel_html"):
        pixel = tracking["pixel_html"]
    else:
        pixel = _pixel_html_for_email(email_addr)

    # tracking 新 token：绝不复用首封 token。
    # 优先使用调用方 prepare_tracking_for_lead 生成的全新 tracking；
    # 未传入时现场生成全新 token（保证每次 follow-up 独立）。
    if tracking and tracking.get("token"):
        tracking_token = tracking["token"]
        tracking_token_hash = tracking.get("token_hash", "")
        tracking_message_id = tracking.get("tracking_message_id", "")
    else:
        tracking_token = secrets.token_urlsafe(24)
        tracking_token_hash = ""
        tracking_message_id = ""

    # Subject: Re: <original>
    followup_subject = f"Re: {original_subject}" if original_subject else "Following up"

    body_text = FOLLOWUP_BODY_TEXT.format(greeting=greeting, pixel="", signature=FOLLOWUP_SIGNATURE_TEXT)
    body_html = FOLLOWUP_BODY_HTML.format(greeting=greeting, pixel=pixel, signature=FOLLOWUP_SIGNATURE_HTML)

    for label, content in [("text", body_text), ("html", body_html)]:
        issues = _safety_check(content)
        if issues:
            print(f"  WARNING [followup {label}]: {'; '.join(issues)}")

    return {
        "template_key": "premium_puzzles_card_games_v5_followup",
        "subject": followup_subject,
        "body_text": body_text.strip(),
        "body_html": body_html.strip(),
        "body_html_no_pixel": FOLLOWUP_BODY_HTML.format(greeting=greeting, pixel="", signature=FOLLOWUP_SIGNATURE_HTML).strip(),
        "has_pixel": bool(pixel),
        # Threading headers — set by the sender as MIME headers
        "in_reply_to": original_message_id,
        "references": original_message_id,
        # 独立 tracking token（不复用首封）
        "tracking_token": tracking_token,
        "tracking_token_hash": tracking_token_hash,
        "tracking_message_id": tracking_message_id,
        "email_type": "follow_up",
    }


def apply_email_to_lead(lead: dict, template_key: str = None, tracking: dict = None) -> dict:
    email_data = get_email_for_lead(lead, tracking=tracking)
    lead["email_template"] = email_data["template_key"]
    lead["email_subject"] = email_data["subject"]
    lead["email_body"] = email_data["body_text"]
    lead["email_body_html"] = email_data["body_html"]
    lead["email_body_html_no_pixel"] = email_data["body_html_no_pixel"]
    # P0 渲染元数据：供 final_send_plan 落库审计
    lead["template_key"] = email_data["template_key"]
    lead["content_sha256"] = email_data["content_sha256"]
    lead["renderer_version"] = email_data["renderer_version"]
    lead["renderer_sha256"] = email_data["renderer_sha256"]
    if tracking:
        lead["_tracking_token"] = tracking.get("token", "")
        lead["_tracking_token_hash"] = tracking.get("token_hash", "")
        lead["_tracking_message_id"] = tracking.get("tracking_message_id", "")
    lead["pixel_tracking"] = email_data["has_pixel"]
    return lead


def preview_email(lead: dict, conn=None) -> str:
    """Generate a human-readable email preview. Never sends SMTP.

    Usage: python -c "from bd_template import preview_email; print(preview_email({...}))"
    Or:    python bd_template.py --preview <lead_id>
    """
    email_data = get_email_for_lead(lead)
    email_addr = (lead.get("email") or "").strip()
    pixel_active = bool(_pixel_html_for_email(email_addr))

    lines = [
        "=" * 60,
        "EMAIL PREVIEW (no SMTP called)",
        "=" * 60,
        f"Company:   {lead.get('store_name', 'N/A')}",
        f"Contact:   {lead.get('contact_person', 'N/A')}",
        f"Email:     {email_addr}",
        f"City/State: {lead.get('city','')} {lead.get('state','')}",
        f"Org Key:   {lead.get('organization_key', 'N/A')}",
        f"Score:     {lead.get('confidence_score', 'N/A')}",
        f"Status:    {lead.get('status', 'N/A')}",
        f"Auto-Send: {lead.get('auto_sendable', 0)}",
        "-" * 60,
        f"Subject: {email_data['subject']}",
        "-" * 60,
        "--- TEXT BODY ---",
        email_data['body_text'],
        "-" * 60,
        f"Pixel Tracking: {'ENABLED (test only)' if pixel_active else 'DISABLED'}",
        f"Template: {email_data['template_key']}",
    ]

    # Historical context if DB conn provided
    if conn:
        try:
            c = conn.cursor()
            # Check if previously sent
            sent = c.execute(
                "SELECT COUNT(*) FROM send_log WHERE lead_id=? AND status='sent'",
                (lead.get("id", 0),)
            ).fetchone()
            lines.append(f"Previously Sent: {sent[0] if sent else 0} times")

            # Check suppression
            supp = c.execute(
                "SELECT 1 FROM suppression_list WHERE email=?",
                (email_addr,)
            ).fetchone()
            lines.append(f"Suppressed: {'YES' if supp else 'NO'}")

            # Organization first-outreach
            org = lead.get("organization_key", "")
            if org:
                org_sent = c.execute(
                    "SELECT COUNT(*) FROM send_log sl JOIN leads l ON sl.lead_id=l.id WHERE l.organization_key=? AND sl.status='sent' AND sl.message_type='new_outreach'",
                    (org,)
                ).fetchone()
                lines.append(f"Org First-Outreach Sent: {'YES' if org_sent and org_sent[0] > 0 else 'NO'}")

            lines.append(f"Can Send: {'YES' if not supp and not (org_sent and org_sent[0] > 0) and lead.get('auto_sendable', 0) else 'NO (blocked)'}")
        except Exception:
            pass

    lines.append("=" * 60)
    return "\n".join(lines)


# ── Renderer 指纹（模块加载时填充）─────────────────────
def _compute_renderer_hash() -> str:
    """对 _compact_render 字节码算 sha256[:8]；渲染器实现变化时指纹自动变化。"""
    return _hashlib.sha256(_compact_render.__code__.co_code).hexdigest()[:8]


RENDERER_SHA256 = _compute_renderer_hash()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "--preview":
        lead_id = int(sys.argv[2])
        import sqlite3
        conn = sqlite3.connect("file:data/bd_leads.db?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        lead = dict(c.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())
        conn.close()
        conn2 = sqlite3.connect("file:data/bd_leads.db?mode=ro", uri=True)
        print(preview_email(lead, conn=conn2))
        conn2.close()
    elif len(sys.argv) >= 2 and sys.argv[1] == "--template":
        lead = {
            "store_name": "Test Bookstore",
            "email": "test@example.com",
            "city": "Nashville",
            "state": "TN",
            "organization_key": "test_org",
            "status": "new",
            "confidence_score": "A",
            "auto_sendable": 1,
        }
        print(preview_email(lead))
    else:
        print("Usage: python bd_template.py --preview <lead_id>")
        print("       python bd_template.py --template  (show template preview)")
