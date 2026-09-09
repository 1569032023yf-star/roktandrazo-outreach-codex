"""email_hygiene.py — Unified Business Email Validation Module
==============================================================
Single source of truth for all email validation.
All entry points (discovery, staging, manual, Broad, Strict A0,
Pre-Send, Outreach) MUST call this module.

Exports:
  hygiene_check()                    — ★ 权威入口，返回 {valid, reason}
  validate_business_email()          — full validation, returns (bool, reason, confidence)
  validate_contact_business_association() — checks email actually belongs to business
  normalize_email()                  — canonical normalization
  classify_email_failure()           — maps failure code to user-facing category
  check_mx_cached()                  — DNS MX check with caching
"""
import re
import sqlite3
import time
from typing import Optional, Tuple, Dict

# ═══════════════════════════════════
# Constants
# ═══════════════════════════════════

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

# Patterns that ALWAYS indicate an invalid business email
# 注意: example/domain/test.com 需要前后非 [\w-]，否则会误伤 business-domain.com 等真实域名
INVALID_PATTERNS = re.compile(
    r'((?<![\w-])example\.com(?![\w-])|(?<![\w-])domain\.com(?![\w-])|(?<![\w-])test\.com(?![\w-])|anonymized|'
    r'noreply|no-reply|donotreply|@bot\.|@sentry|@anthropic|'
    r'\.png|\.jpg|\.gif|\.webp|\.jpeg|\.svg|\.css|\.js\b|'
    r'sentry\.io|wix\.com|square\.space|'
    r'@2x\b|\d+x\d+|'          # Image dimensions
    r'^www\.|'                  # www. prefix
    r'^xxx@|@xxx\.'             # Placeholder
    r')',
    re.IGNORECASE
)

SYSTEM_PREFIXES = frozenset({
    "no-reply", "noreply", "privacy", "copyright", "abuse",
    "postmaster", "mailer-daemon", "hostmaster", "webmaster",
})

DIRECTORY_DOMAINS = frozenset({
    "yelp.com", "yellowpages.com", "tripadvisor.com", "facebook.com",
    "instagram.com", "twitter.com", "linkedin.com", "pinterest.com",
    "maps.google.com", "google.com/maps",
})

# Free public email providers (not blocked, but classified differently)
FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com", "outlook.com",
    "live.com", "msn.com", "aol.com", "ymail.com", "mail.com",
    "protonmail.com", "proton.me", "icloud.com", "me.com",
    "comcast.net", "verizon.net", "att.net", "bellsouth.net",
    "earthlink.net", "sbcglobal.net", "charter.net",
})

# Direct business sources (high confidence)
DIRECT_SOURCES = frozenset({
    "official_page_visible", "official_mailto", "wholesale_vendor_page",
    "website_extracted", "website_http_verified",
})

MEDIUM_SOURCES = frozenset({
    "public_directory", "retailer_directory", "social_page",
    "google_maps", "webfetch_google_maps",
    "inventory_website_scan", "inventory_memphis_scan",
    "paizo_retailer_directory", "chamber_directory",
    "tourism_directory", "main_street_directory",
    "manual_lookup", "web_search", "manual_seed",
})

# MX cache (in-memory, per-session)
_mx_cache: Dict[str, dict] = {}

MX_CACHE_TTL = 3600  # 1 hour

# ═══════════════════════════════════
# Helper functions
# ═══════════════════════════════════

def _has_resource_extension(email: str) -> bool:
    ext = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.css', '.js', '.bmp', '.ico')
    return any(e in email.lower() for e in ext)

def _has_url_like_local(email: str) -> bool:
    if '@' not in email:
        return True
    local = email.split('@')[0].lower()
    return local.startswith('www.') or 'http' in local or '/' in local

def _is_hash_like(email: str) -> bool:
    if '@' not in email:
        return False
    local = email.split('@')[0]
    return bool(re.match(r'^[a-f0-9]{32,}$', local, re.I))

def _is_directory_domain(domain: str) -> bool:
    return domain.lower() in DIRECTORY_DOMAINS

def _is_placeholder_domain(domain: str) -> bool:
    """example/test/localhost 等占位域名 → 非真实业务邮箱，必须 FAIL。

    同时覆盖常见占位域名变体（example.org / test.org / yourdomain 等）。
    """
    d = (domain or "").lower().rstrip(".")
    if not d:
        return True
    if d in ("example.com", "example.org", "example.net", "example.edu",
             "test.com", "test.org", "test.net", "localhost", "domain.com",
             "yourdomain.com", "yourdomain", "yourdomain.net", "email.com",
             "company.com", "website.com", "sample.com", "demo.com",
             "youremail.com", "yoursite.com", "yourmail.com"):
        return True
    for prefix in ("example.", "test.", "demo.", "sample.", "yourdomain"):
        if d.startswith(prefix):
            return True
    return False

# ═══════════════════════════════════
# ★ 权威入口: hygiene_check
# ═══════════════════════════════════

def hygiene_check(email: str) -> dict:
    """统一 Email Hygiene 权威入口（P7）。全生产树只允许这一套判定。

    返回: {"valid": bool, "reason": str}

    必须 FAIL:
      - 空 / 无 @ / 格式非法（invalid_format）
      - 图片/资源伪邮箱（.png/.jpg/.gif 等资源扩展名、@2x、像素尺寸，如
        tbs_rev_hz_type_110x@2x.png、certificate1_235x235@2x.jpg）
      - www. 前缀 local-part（如 www.kll@toystoreandgifts.com）
      - sentry.io / hash 系统地址（hash_like_email / sentry_system_address）
      - example / test / localhost 占位地址（placeholder_domain）
    必须 PASS:
      - 泛邮箱（info/hello/contact/sales/orders 等）不是 blocker
      - Gmail 等免费邮箱（hygiene 层面放行；是否发送由业务规则决定）

    注意: third-party association mismatch（如 store 是 A 公司但邮箱来自
    B 域）由调用方按 business association 规则阻断，hygiene 本身不管。
    """
    email = str(email or "").strip().lower()

    if not email or "@" not in email:
        return {"valid": False, "reason": "invalid_format"}

    if not EMAIL_RE.fullmatch(email):
        return {"valid": False, "reason": "invalid_format"}

    # 以下顺序刻意先于 INVALID_PATTERNS，以便返回更精确的 reason：
    # 图片/资源伪邮箱、www. 前缀、hash、系统前缀、sentry、占位域。
    if _has_resource_extension(email):
        return {"valid": False, "reason": "resource_extension_in_email"}

    if _has_url_like_local(email):
        return {"valid": False, "reason": "url_like_local_part"}

    if _is_hash_like(email):
        return {"valid": False, "reason": "hash_like_email"}

    local_part, domain = email.split("@", 1)

    if local_part in SYSTEM_PREFIXES:
        return {"valid": False, "reason": "system_email_address"}

    # sentry / 错误跟踪系统地址（local 或 domain 含 sentry）
    if "sentry" in domain or "sentry" in local_part:
        return {"valid": False, "reason": "sentry_system_address"}

    if _is_placeholder_domain(domain):
        return {"valid": False, "reason": "placeholder_domain"}

    if INVALID_PATTERNS.search(email):
        return {"valid": False, "reason": "invalid_email_pattern"}

    return {"valid": True, "reason": "ok"}


# ═══════════════════════════════════
# Primary Export: validate_business_email
# ═══════════════════════════════════

def validate_business_email(lead: dict) -> Tuple[bool, str, str]:
    """Validate a business contact email comprehensively.
    
    Returns: (is_valid, failure_reason_or_source_type, confidence: high|medium|low)
    
    Checks (in order):
      1. Not empty
      2. RFC format (EMAIL_RE.fullmatch)
      3. Not matching INVALID_PATTERNS
      4. No resource extension in email
      5. No URL-like local part (www., http, /)
      6. No hash-like local part (32+ hex chars)
      7. Not a system prefix (noreply, abuse, etc.)
      8. Source confidence classification
    """
    email = str(lead.get("email") or "").strip().lower()
    
    if not email:
        return False, "email_missing", "low"
    
    if not EMAIL_RE.fullmatch(email):
        return False, "email_invalid_format", "low"
    
    if INVALID_PATTERNS.search(email):
        return False, "invalid_email_pattern", "low"
    
    if _has_resource_extension(email):
        return False, "resource_extension_in_email", "low"
    
    if _has_url_like_local(email):
        return False, "url_like_local_part", "low"
    
    if _is_hash_like(email):
        return False, "hash_like_email", "low"
    
    local_part = email.split("@")[0].lower()
    if local_part in SYSTEM_PREFIXES:
        return False, "system_email_address", "low"
    
    # Source confidence
    source_type = str(lead.get("email_source_type") or "unknown").strip()
    
    if source_type in DIRECT_SOURCES:
        confidence = "high"
    elif source_type in MEDIUM_SOURCES:
        confidence = "medium"
    else:
        confidence = "low"
    
    return True, source_type, confidence


# ═══════════════════════════════════
# validate_contact_business_association
# ═══════════════════════════════════

def validate_contact_business_association(lead: dict) -> Tuple[bool, str]:
    """Check that contact email actually belongs to the business.
    
    Returns: (is_associated, reason)
    
    Checks:
      - Directory domains (yelp, facebook etc.) → not a direct business contact
      - Third-party email domain mismatch (email@news-site.com for a toy store)
      - Can be extended with more checks
    """
    email = str(lead.get("email") or "").strip().lower()
    website = str(lead.get("official_website") or "").strip().lower()
    org_key = str(lead.get("organization_key") or "").strip()
    store_name = str(lead.get("store_name") or "").strip().lower()
    notes = str(lead.get("notes") or "").strip().lower()
    
    if not email or '@' not in email:
        return False, "no_valid_email"
    
    email_domain = email.split('@')[1].lower()
    
    # Directory domain check
    if _is_directory_domain(email_domain):
        return False, f"directory_domain:{email_domain}"
    
    # Extract website domain
    website_domain = ""
    if website:
        m = re.search(r'https?://(?:www\.)?([^/]+)', website)
        if m:
            website_domain = m.group(1).lower()
    
    # If email domain matches website domain → high confidence
    if website_domain and email_domain == website_domain:
        return True, "domain_match"
    
    # Free email → allowed but flagged
    if email_domain in FREE_EMAIL_DOMAINS:
        return True, "free_email_allowed"
    
    # News/media domains → likely third party
    news_patterns = ['sevendaysvt.com', 'newspaper', 'news.', 'magazine.', 'radio.', 'tv.', 'press.']
    if any(p in email_domain for p in news_patterns):
        # Check if store_name appears in the domain context
        if store_name and not any(w in notes for w in store_name.split()[:2]):
            return False, f"news_media_domain:{email_domain}"
    
    # Sentry/error-tracking → definitely not business
    if 'sentry' in email_domain:
        return False, "sentry_domain"
    
    # Domain doesn't match but is real → still acceptable
    return True, "domain_mismatch_accepted"


# ═══════════════════════════════════
# normalize_email
# ═══════════════════════════════════

def normalize_email(value: str) -> str:
    """Normalize email: lowercase, strip whitespace, validate format."""
    value = str(value or '').strip().lower()
    if any(ch.isspace() for ch in value) or ',' in value or ';' in value:
        return ''
    if not EMAIL_RE.fullmatch(value):
        return ''
    return value


# ═══════════════════════════════════
# classify_email_failure
# ═══════════════════════════════════

def classify_email_failure(reason: str) -> str:
    """Map internal failure reason to user-facing category."""
    if reason in ("email_missing", "email_invalid_format"):
        return "malformed_or_missing"
    if reason in ("invalid_email_pattern", "resource_extension_in_email",
                  "url_like_local_part", "hash_like_email", "system_email_address"):
        return "invalid_resource_or_system"
    if reason.startswith("directory_domain") or reason.startswith("news_media"):
        return "third_party_contact_mismatch"
    if reason.startswith("sentry"):
        return "invalid_resource_or_system"
    return reason


# ═══════════════════════════════════
# MX/DNS check with caching
# ═══════════════════════════════════

def check_mx_cached(domain: str) -> dict:
    """Check MX records for a domain, with caching.
    
    Returns: {
        'has_mx': bool,
        'provider': 'google'|'exchange'|'other'|'no_mx'|'nxdomain'|'dns_timeout',
        'checked_at': timestamp,
        'error': str or None,
    }
    """
    now = int(time.time())
    
    # Check cache
    cached = _mx_cache.get(domain)
    if cached and (now - cached.get('checked_at', 0)) < MX_CACHE_TTL:
        return cached
    
    result = {
        'has_mx': False,
        'provider': 'no_mx',
        'checked_at': now,
        'error': None,
    }
    
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX')
        result['has_mx'] = True
        mx_str = ' '.join([str(x.exchange).lower() for x in answers])
        if any(k in mx_str for k in ['outlook', 'protection.outlook', 'microsoft', 'exchange']):
            result['provider'] = 'exchange'
        elif 'google' in mx_str:
            result['provider'] = 'google'
        else:
            result['provider'] = 'other'
    except dns.resolver.NXDOMAIN:
        result['provider'] = 'nxdomain'
        result['error'] = 'NXDOMAIN'
    except dns.resolver.NoAnswer:
        result['provider'] = 'no_mx'
        result['error'] = 'NoAnswer'
    except dns.resolver.Timeout:
        result['provider'] = 'dns_timeout'
        result['error'] = 'Timeout'
    except Exception as e:
        result['provider'] = 'dns_error'
        result['error'] = str(e)[:100]
    
    _mx_cache[domain] = result
    return result


def validate_email_mx(email: str) -> Tuple[bool, str]:
    """Check MX for an email's domain. Returns (passes, reason).
    
    - domain NXDOMAIN → blocked
    - no MX → blocked
    - MX exists → passes
    - DNS timeout → retry_pending (not blocked)
    - Free email (Gmail etc) → passes (skip MX check)
    """
    if '@' not in email:
        return False, "invalid_format"
    
    email = email.lower().strip()
    domain = email.split('@')[1]
    
    # Free email providers always pass MX
    if domain in FREE_EMAIL_DOMAINS:
        return True, "free_email_skip_mx"
    
    mx = check_mx_cached(domain)
    
    if mx['provider'] == 'nxdomain':
        return False, "domain_nxdomain"
    elif mx['provider'] == 'no_mx':
        return False, "domain_no_mx"
    elif mx['provider'] == 'dns_timeout':
        return False, "mx_retry_pending"  # Not permanent — retry later
    elif mx['provider'] == 'dns_error':
        return False, f"mx_error:{mx['error']}"
    elif mx['has_mx']:
        return True, f"mx_ok:{mx['provider']}"
    
    return False, "mx_unknown"
