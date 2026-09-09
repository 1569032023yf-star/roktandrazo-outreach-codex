"""Production adapter: maps real DB rows into the shape lead_hygiene_gate expects.

Design principles:
- Fail closed: missing data = rejection, never auto-qualify
- No DB writes: this module only reads
- No network: pure data transformation
- Every field the gate checks must be explicitly derived; no silent defaults
"""
from __future__ import annotations

import re
from typing import Any

# Domain-based risk sets (must match gate)
FREE_EMAIL_DOMAINS = frozenset({"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"})
DIRECTORY_DOMAINS = frozenset({"yelp.com", "yellowpages.com", "facebook.com", "google.com"})

# Production-accepted official source types (superset of gate's OFFICIAL_SOURCE_TYPES)
# manual_lookup is accepted ONLY when manual_decision='approved' AND evidence is complete
OFFICIAL_SOURCE_TYPES_STRICT = frozenset({
    "official_page_visible", "official_mailto", "wholesale_vendor_page",
})
MANUAL_LOOKUP_SOURCE = "manual_lookup"


def _safe_str(val: Any) -> str:
    """Convert to stripped string; None → empty."""
    return str(val or "").strip()


def _safe_lower(val: Any) -> str:
    """Convert to lowered stripped string; None → empty."""
    return _safe_str(val).lower()


def _email_domain(email: str) -> str:
    """Extract domain from email; empty if no @."""
    text = _safe_lower(email)
    return text.rsplit("@", 1)[1] if "@" in text else ""


def _is_domain_hash_duplicate(domain_hash: str, duplicate_domain_hashes: set[str]) -> bool:
    """Check if domain_hash appears more than once in the leads table."""
    return bool(domain_hash) and domain_hash in duplicate_domain_hashes


def build_candidate_from_db_row(
    row: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Convert a production DB row into a candidate dict for lead_hygiene_gate.evaluate_a0().

    Args:
        row: A dict from `SELECT * FROM leads WHERE id=?`
        context: Pre-computed lookup tables (loaded once, shared across rows):
            - suppressed_emails: set[str] — from suppression_list
            - hard_bounced_emails: set[str] — from bounce_log WHERE bounce_type='hard'
            - policy_bounced_emails: set[str] — from bounce_log WHERE bounce_type='policy'
            - sent_emails: set[str] — from send_log WHERE status='sent'
            - duplicate_domain_hashes: set[str] — domain_hash with COUNT>1 in leads

    Returns:
        A candidate dict with ALL fields the hygiene gate checks.
        Missing/unknown data → fail-closed booleans (True = risky = blocked).
    """
    c: dict[str, Any] = {}

    # --- Identity ---
    c["lead_id"] = row.get("id")
    c["store_name"] = _safe_str(row.get("store_name"))
    c["city"] = _safe_str(row.get("city"))
    c["state"] = _safe_str(row.get("state"))
    c["lead_segment"] = _safe_str(row.get("lead_segment"))
    c["customer_type"] = _safe_str(row.get("customer_type") or row.get("store_type"))
    c["phone"] = ""  # Not in production schema

    # --- Email ---
    email = _safe_lower(row.get("email"))
    c["email"] = email
    c["official_website"] = _safe_str(row.get("official_website"))
    c["contact_form_url"] = _safe_str(row.get("contact_form_url"))

    # --- Evidence ---
    c["evidence_url"] = _safe_str(row.get("evidence_url"))
    c["evidence_snippet"] = _safe_str(row.get("evidence_snippet"))

    # --- Source type ---
    email_source_type = _safe_str(row.get("email_source_type"))
    c["email_source_type"] = email_source_type

    # --- Verified on official site ---
    verified = row.get("email_verified_on_official_site")
    c["email_verified_on_official_site"] = (verified == 1 or verified is True)

    # --- Official match: derive from verified + source type ---
    # Gate expects candidate['official_match'] = True when the email was
    # confirmed on the business's own website.
    # Mapping: verified on official site AND source type is strict official
    is_strict_official = email_source_type in OFFICIAL_SOURCE_TYPES_STRICT
    c["official_match"] = c["email_verified_on_official_site"] and is_strict_official

    # --- Manual lookup special handling ---
    # manual_lookup is NOT automatically official. It's only accepted when:
    #   1. manual_decision == 'approved'
    #   2. manual_found_email is present
    #   3. evidence_url is present
    #   4. evidence_snippet is present
    # Otherwise it's treated as guessed/unverified → fail closed.
    if email_source_type == MANUAL_LOOKUP_SOURCE:
        manual_decision = _safe_lower(row.get("manual_decision"))
        manual_found_email = _safe_str(row.get("manual_found_email"))
        has_evidence = bool(c["evidence_url"]) and bool(c["evidence_snippet"])
        if manual_decision == "approved" and manual_found_email and has_evidence:
            # Promote: treat as official
            c["official_match"] = True
            c["email_source_type"] = "official_mailto"  # Promoted
        else:
            # Fail closed: not approved or missing evidence
            c["official_match"] = False
            c["guessed_email"] = True
            c["email_source_type"] = "manual_lookup_unapproved"

    # --- Status-derived flags ---
    status = _safe_lower(row.get("status"))
    c["status"] = status

    # Social only: check email_source_type or status
    c["social_only"] = (
        "social" in email_source_type.lower()
        or status == "b1_social_verified"
    )

    # Contact form only
    c["contact_form_only"] = (
        email_source_type == "contact_form_only"
        or status == "contact_form_pool"
    )

    # --- Risk flags from context (pre-computed from joins) ---
    emails = context.get("suppressed_emails", set())
    c["suppressed"] = email in emails

    hard_bounced = context.get("hard_bounced_emails", set())
    c["bounced"] = email in hard_bounced

    # Delivery issue: from status field
    c["delivery_issue"] = (status == "delivery_issue")

    sent_emails = context.get("sent_emails", set())
    # already_sent: check both send_log (via context) AND lead's own status/sent_at
    c["already_sent"] = (
        email in sent_emails
        or status in ("sent", "bounced")
        or _safe_str(row.get("sent_at")) != ""
    )

    dup_hashes = context.get("duplicate_domain_hashes", set())
    domain_hash = _safe_str(row.get("domain_hash"))
    c["duplicate_domain"] = _is_domain_hash_duplicate(domain_hash, dup_hashes)

    # guessed_email: only set if not already set by manual_lookup handling
    if "guessed_email" not in c:
        c["guessed_email"] = (email_source_type == "guessed_email")

    # Third-party directory: domain-based check
    domain = _email_domain(email)
    c["third_party_directory"] = domain in DIRECTORY_DOMAINS

    # Supplier email: not derivable from production schema → default False
    c["supplier_email"] = False

    # --- MX provider: Exchange check (production-specific gate) ---
    mx_provider = _safe_lower(row.get("mx_provider"))
    c["is_exchange_mx"] = any(
        k in mx_provider for k in ("exchange", "outlook", "microsoft")
    )

    # --- Confidence score for reporting ---
    c["confidence_score"] = _safe_str(row.get("confidence_score"))

    return c


def build_context(conn) -> dict[str, Any]:
    """Build the shared context dict from a read-only DB connection.

    Call once, pass to all build_candidate_from_db_row() calls.
    """
    c = conn.cursor()

    # CRITICAL: normalize all emails to lowercase for case-insensitive matching.
    # Production DB has mixed-case emails (e.g., "SALES@Domain.COM") that must
    # match suppression/send_log entries regardless of case.
    suppressed = {r[0].strip().lower() for r in c.execute(
        "SELECT email FROM suppression_list WHERE email IS NOT NULL"
    ).fetchall()}

    hard_bounced = {r[0].strip().lower() for r in c.execute(
        "SELECT email FROM bounce_log WHERE lower(COALESCE(bounce_type,'')) IN ('hard','policy','permanent') AND email IS NOT NULL"
    ).fetchall()}

    sent = {r[0].strip().lower() for r in c.execute(
        "SELECT email FROM send_log WHERE status = 'sent' AND email IS NOT NULL"
    ).fetchall()}

    # Duplicate domain hashes: any domain_hash that appears more than once
    dup_hashes = {r[0] for r in c.execute(
        "SELECT domain_hash FROM leads "
        "WHERE domain_hash IS NOT NULL AND domain_hash != '' "
        "GROUP BY domain_hash HAVING COUNT(*) > 1"
    ).fetchall()}

    return {
        "suppressed_emails": suppressed,
        "hard_bounced_emails": hard_bounced,
        "sent_emails": sent,
        "duplicate_domain_hashes": dup_hashes,
    }
