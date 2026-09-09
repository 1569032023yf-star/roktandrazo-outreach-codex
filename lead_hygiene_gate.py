"""Pure, side-effect-free A0 eligibility gate for enriched lead candidates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import re
from urllib.parse import urlparse

RETAIL_ALLOWED_STATES = frozenset({"TN", "AR", "KY"})
OFFICIAL_SOURCE_TYPES = frozenset({"official_page_visible", "official_mailto", "wholesale_vendor_page"})
FREE_EMAIL_DOMAINS = frozenset({"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"})
DIRECTORY_DOMAINS = frozenset({"yelp.com", "yellowpages.com", "facebook.com", "google.com"})
ROLE_OR_UNSAFE_PREFIXES = ("no-reply", "noreply", "privacy", "copyright", "support-plugin",
                           "careers", "career", "jobs", "press", "media", "technical", "tech", "developer")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


@dataclass(frozen=True)
class HygieneDecision:
    status: str
    a0_eligible: bool
    reasons: tuple[str, ...]


def normalize_state(value: Any) -> str:
    value = str(value or "").strip().upper()
    aliases = {"TENNESSEE": "TN", "ARKANSAS": "AR", "KENTUCKY": "KY"}
    return aliases.get(value, value)


def email_domain(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text.rsplit("@", 1)[1] if "@" in text else ""


def _website_domain(value: Any) -> str:
    host = (urlparse(str(value or "")).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _is_custom_production(candidate: Mapping[str, Any]) -> bool:
    label = " ".join(str(candidate.get(key) or "").lower() for key in ("lead_segment", "customer_type", "store_type"))
    return "custom" in label or "production" in label


def evaluate_a0(candidate: Mapping[str, Any]) -> HygieneDecision:
    """Classify an already-enriched candidate without network or database access."""
    if candidate.get("social_only") or candidate.get("status") == "B1_social_verified":
        return HygieneDecision("B1_social_verified", False, ("social_only_evidence",))
    if candidate.get("contact_form_only"):
        return HygieneDecision("C_contact_form_or_social_message", False, ("contact_form_only",))

    reasons: list[str] = []
    email = str(candidate.get("email") or "").strip().lower()
    domain = email_domain(email)
    if not email:
        reasons.append("email_missing")
    elif not EMAIL_RE.fullmatch(email):
        reasons.append("email_invalid")
    if not domain:
        reasons.append("email_domain_missing")
    if not str(candidate.get("official_website") or "").strip():
        reasons.append("official_website_missing")
    if not str(candidate.get("evidence_url") or "").strip():
        reasons.append("evidence_url_missing")
    if not str(candidate.get("evidence_snippet") or "").strip():
        reasons.append("evidence_snippet_missing")
    if candidate.get("email_verified_on_official_site") is not True:
        reasons.append("official_site_email_not_verified")
    if str(candidate.get("email_source_type") or "") not in OFFICIAL_SOURCE_TYPES:
        reasons.append("email_source_not_official")
    if candidate.get("official_match") is not True:
        reasons.append("business_identity_not_matched")
    if not _is_custom_production(candidate) and normalize_state(candidate.get("state")) not in RETAIL_ALLOWED_STATES:
        reasons.append("state_out_of_scope")
    for key, reason in (
        ("suppressed", "suppressed"),
        ("bounced", "bounced"),
        ("delivery_issue", "delivery_issue"),
        ("already_sent", "already_sent"),
        ("duplicate_domain", "duplicate_domain"),
        ("guessed_email", "guessed_email"),
        ("third_party_directory", "third_party_directory"),
        ("supplier_email", "supplier_email"),
    ):
        if candidate.get(key):
            reasons.append(reason)
    if domain in DIRECTORY_DOMAINS:
        reasons.append("directory_or_social_domain")
    official_domain = _website_domain(candidate.get("official_website"))
    if domain and official_domain and domain != official_domain and not domain.endswith("." + official_domain):
        reasons.append("third_party_email_domain")
    if email.split("@", 1)[0] in ROLE_OR_UNSAFE_PREFIXES:
        reasons.append("unsafe_role_email")
    if domain in FREE_EMAIL_DOMAINS and not candidate.get("email_verified_on_official_site"):
        reasons.append("unverified_free_email")

    if reasons:
        return HygieneDecision("B2_manual_review", False, tuple(sorted(set(reasons))))
    return HygieneDecision("A0", True, ())


def is_strict_a0(candidate: Mapping[str, Any]) -> bool:
    return evaluate_a0(candidate).a0_eligible
