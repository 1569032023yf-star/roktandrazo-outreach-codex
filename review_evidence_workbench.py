"""Read-only review evidence and bounded, on-demand public Facebook inspection.

Nothing in this module approves a lead, writes a lead, or creates a send plan.
"""
from __future__ import annotations

import json
import ipaddress
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from broad_ready import _load_db_signals, is_broad_outreach_ready
from campaign_eligible_v2 import _read_fresh_cached_mx, review_campaign_eligible_v2
from discovery.discovery_service import (
    BrowserFallbackWebsiteFetcher, _extract_email_evidence, _fetch_official_pages,
    _official_identity_match, _fixed_first_party_urls, _verified_official_page,
    UrlLibWebsiteFetcher,
)
from facebook_enrichment.b_pool_recovery_runner import (
    extract_fb_links, read_fb_page_with_limiter,
)
from facebook_enrichment.fb_rate_limiter import FBRateLimiter, RateLimitConfig
from history_crosscheck import host, normalize_email

ROOT = Path(__file__).resolve().parent
HISTORY_BLOCKS = frozenset({
    "previously_sent_email", "previously_sent_org", "shared_domain_org_history",
    "suppression", "hard_policy_permanent_bounce", "unsubscribed",
    "stop_contact", "delivery_issue", "rejected", "already_safe_organization",
})


def _row(conn: sqlite3.Connection, lead_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row) if row else None


def recovery_classification(conn: sqlite3.Connection, lead: dict) -> dict:
    """Classify opportunity before any browser work; a database error fails closed."""
    email = normalize_email(lead.get("email") or "")
    try:
        signals = _load_db_signals(conn, email, str(lead.get("organization_key") or ""),
                                   str(lead.get("domain_hash") or ""), lead.get("id"))
        broad = is_broad_outreach_ready(lead, {"conn": conn})
        blocks = set(broad.get("blockers") or [])
        if signals.get("sent_email"): blocks.add("previously_sent_email")
        if signals.get("sent_org"): blocks.add("previously_sent_org")
        if signals.get("shared_domain_sent"): blocks.add("shared_domain_org_history")
        if signals.get("suppressed"): blocks.add("suppression")
        if signals.get("hard_bounced"): blocks.add("hard_policy_permanent_bounce")
        org = str(lead.get("organization_key") or "")
        if org and conn.execute(
            "SELECT 1 FROM leads WHERE organization_key=? AND id!=? AND "
            "(COALESCE(auto_sendable,0)=1 OR status='sent') LIMIT 1",
            (org, lead.get("id")),
        ).fetchone():
            blocks.add("already_safe_organization")
        if str(lead.get("status") or "").lower() in {"delivery_issue", "rejected", "review_rejected"}:
            blocks.add(str(lead["status"]).lower().replace("review_rejected", "rejected"))
        if str(lead.get("review_status") or "").lower() == "rejected":
            blocks.add("rejected")
        if lead.get("delivery_issue"):
            blocks.add("delivery_issue")
        if lead.get("do_not_contact"):
            blocks.add("stop_contact")
        if lead.get("unsubscribed_at"):
            blocks.add("unsubscribed")
        if lead.get("bounced_at"):
            blocks.add("hard_policy_permanent_bounce")
        if lead.get("auto_sendable"):
            blocks.add("already_safe_organization")
    except sqlite3.Error:
        return {"value": "NONE", "reasons": ["history_check_unavailable"], "eligible_for_browser": False}
    hard = sorted(blocks & HISTORY_BLOCKS)
    if hard:
        return {"value": "NONE", "reasons": hard, "eligible_for_browser": False}
    website = bool(lead.get("official_website"))
    source = str(lead.get("email_source_type") or "").lower()
    reason = str(lead.get("review_reason_code") or "").upper()
    incomplete = not email or source in {"guessed_email", "unknown", "facebook_page"}
    high = website and (incomplete or reason in {
        "WEAK_EVIDENCE", "EMAIL_SOURCE_UNCERTAIN", "DOMAIN_MISMATCH", "CONTACT_FORM_ONLY",
    })
    value = "HIGH" if high else "MEDIUM" if website or lead.get("facebook_url") else "LOW"
    return {"value": value, "reasons": sorted(blocks), "eligible_for_browser": True}


def _telemetry(conn: sqlite3.Connection, lead_id: int) -> dict:
    try:
        rows = conn.execute(
            "SELECT raw_payload_json FROM lead_discovery_results WHERE linked_lead_id=? "
            "ORDER BY id DESC LIMIT 1", (lead_id,),
        ).fetchall()
        raw = json.loads(rows[0][0] or "{}") if rows else {}
        return dict(raw.get("website_enrichment_telemetry") or {})
    except (sqlite3.Error, ValueError, TypeError, AttributeError):
        return {}


def build_review_evidence(conn: sqlite3.Connection, lead_id: int, facebook: dict | None = None) -> dict:
    """Assemble one factual, read-only package; MX uses fresh cache only."""
    lead = _row(conn, lead_id)
    if not lead:
        return {"ok": False, "error": "lead_not_found"}
    recovery = recovery_classification(conn, lead)
    domain = (normalize_email(lead.get("email") or "").split("@")[-1]
              if normalize_email(lead.get("email") or "") else "")
    cached_mx, checked_at = _read_fresh_cached_mx(conn, domain)
    v2 = review_campaign_eligible_v2(lead, {"conn": conn, "mx_lookup": {domain: cached_mx or "dns_error"}})
    checks = dict(v2.get("checks") or {})
    gates = {key: {"state": "PASS" if value.get("pass") else "BLOCK", "detail": value.get("detail")}
             for key, value in checks.items()}
    gates["mx_verification"]["state"] = "UNKNOWN" if not cached_mx else gates["mx_verification"]["state"]
    for key in HISTORY_BLOCKS:
        gates[key] = {"state": "BLOCK" if key in recovery["reasons"] else "PASS", "detail": key}
    try:
        fb_row = conn.execute("SELECT * FROM fb_enrichment_queue WHERE lead_id=?", (lead_id,)).fetchone()
        queued_fb = dict(fb_row) if fb_row else {}
    except sqlite3.Error:
        queued_fb = {}
    try:
        audit = [dict(r) for r in conn.execute(
            "SELECT * FROM review_log WHERE lead_id=? ORDER BY reviewed_at DESC LIMIT 20", (lead_id,)
        )]
    except sqlite3.Error:
        audit = []
    telemetry = _telemetry(conn, lead_id)
    return {
        "ok": True,
        "lead_identity": {k: lead.get(k) for k in ("id", "store_name", "store_type", "city", "state", "formatted_address", "phone")},
        "blocker_summary": {"reason_code": lead.get("review_reason_code"), "detail": lead.get("review_reason_detail"),
                            "status": lead.get("review_status"), "priority": lead.get("review_priority"),
                            "created_at": lead.get("review_created_at"), "recovery": recovery},
        "official_site_evidence": {k: lead.get(k) for k in (
            "official_website", "email", "email_source_type", "email_verified_on_official_site",
            "evidence_url", "evidence_snippet", "evidence_checked_at", "evidence_method",
            "organization_key", "timezone_status", "recipient_timezone", "contact_form_url")},
        "structured_data_evidence": {"present": lead.get("email_source_type") == "first_party_structured_data"},
        "website_enrichment_telemetry": telemetry,
        "facebook_evidence": facebook or {"status": queued_fb.get("fb_check_status") or "not_fetched",
                                           "facebook_page_url": queued_fb.get("facebook_url") or lead.get("facebook_url") or ""},
        "history_state": {"previously_sent": "previously_sent_email" in recovery["reasons"],
                          "organization_history": "previously_sent_org" in recovery["reasons"],
                          "shared_domain_history": "shared_domain_org_history" in recovery["reasons"]},
        "suppression_state": gates["suppression"], "bounce_state": gates["hard_policy_permanent_bounce"],
        "mx_state": {"status": cached_mx or "UNKNOWN", "checked_at": checked_at},
        "v1_state": {"eligible": bool(v2.get("v1_pool") == "CAMPAIGN_ELIGIBLE"), "pool": v2.get("v1_pool")},
        "v2_state": {"eligible": bool(v2.get("eligible")), "pool": v2.get("pool"), "blockers": v2.get("blockers")},
        "organization_state": {"key": lead.get("organization_key")},
        "gate_matrix": gates,
        "reviewer_recommendation_context": {"recovery_value": recovery["value"],
                                            "note": "Evidence review does not authorize sending."},
        "audit_history": audit,
    }


def _fb_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in {
        "facebook.com", "www.facebook.com", "m.facebook.com",
    } and bool(parsed.path.strip("/")) and not parsed.path.startswith((
        "/login", "/sharer", "/share", "/dialog", "/profile.php", "/people/"))


def _normalized_fb(url: str) -> str:
    parsed = urlsplit(url)
    return (parsed.hostname or "").lower().removeprefix("www.") + parsed.path.rstrip("/").lower()


def discover_official_facebook_candidates(lead: dict, fetcher=None) -> dict:
    """Discover business-page links on one canonically verified official homepage.

    This is shared by the review action and the bounded canary. No search and no
    extra crawl beyond the existing first-party page budget.
    """
    website = str(lead.get("official_website") or "").strip()
    if not website:
        return {"status": "official_website_missing", "candidates": [], "selected": "", "source_url": ""}
    fixed = _fixed_first_party_urls(website)
    if not fixed:
        return {"status": "official_website_unverified", "candidates": [], "selected": "", "source_url": ""}
    url, method = fixed[0]
    page = _verified_official_page(url, method, website, fetcher or UrlLibWebsiteFetcher(timeout_seconds=8))
    if not page or not _official_identity_match({"business_name": lead.get("store_name"),
                                                  "website": website}, [page]):
        return {"status": "official_website_unverified", "candidates": [], "selected": "", "source_url": ""}
    candidates: list[str] = []
    seen: set[str] = set()
    for raw in extract_fb_links(page.get("html") or ""):
        parsed = urlsplit(raw)
        candidate = urlunsplit(("https", parsed.netloc, parsed.path.rstrip("/"), "", ""))
        key = _normalized_fb(candidate)
        if _fb_url(candidate) and key not in seen:
            seen.add(key)
            candidates.append(candidate)
    return {"status": "found" if candidates else "official_facebook_link_not_found",
            "candidates": candidates, "selected": candidates[0] if candidates else "",
            "source_url": page.get("final_url") or ""}


def official_linked_facebook(lead: dict, fb_url: str, fetcher=None) -> bool:
    """Claim Tier A only after a canonical, identity-matched official page actually links it."""
    website = str(lead.get("official_website") or "")
    if not website or not _fb_url(fb_url):
        return False
    pages = _fetch_official_pages(website, fetcher or BrowserFallbackWebsiteFetcher())
    if not pages or not _official_identity_match({"business_name": lead.get("store_name"), "website": website}, pages):
        return False
    return any(_normalized_fb(link) == _normalized_fb(fb_url)
               for page in pages for link in extract_fb_links(page.get("html") or ""))


def classify_facebook(lead: dict, rendered: dict, official_linked: bool) -> dict:
    """No social email ever becomes first-party or SAFE in this classifier."""
    text = str(rendered.get("about") or "")
    name = str(rendered.get("name") or "")
    lead_name = str(lead.get("store_name") or "")
    name_tokens = {t for t in re.findall(r"[a-z0-9]+", lead_name.lower()) if len(t) >= 4}
    page_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    signals = {
        "name": bool(name_tokens and name_tokens & page_tokens),
        "phone": bool(lead.get("phone") and re.sub(r"\D", "", str(lead["phone"]))[-10:]
                      == re.sub(r"\D", "", str(rendered.get("phone") or ""))[-10:]
                      and len(re.sub(r"\D", "", str(rendered.get("phone") or ""))) >= 10),
        "address": bool(lead.get("formatted_address") and str(lead["formatted_address"]).lower() in text.lower()),
        "city_state": bool(lead.get("city") and lead.get("state") and
                           str(lead["city"]).lower() in text.lower() and str(lead["state"]).lower() in text.lower()),
        "website_link_back": bool(host(rendered.get("website") or "") and
                                  host(rendered.get("website") or "") == host(lead.get("official_website") or "")),
        "official_site_direct_link": official_linked,
    }
    independent = sum(bool(v) for key, v in signals.items() if key != "official_site_direct_link")
    strong = bool(signals["name"] or signals["phone"] or signals["address"])
    tier = ("TIER_A_OFFICIAL_SITE_LINKED_FACEBOOK" if official_linked and independent >= 1 else
            "TIER_B_STRONGLY_MATCHED_FACEBOOK" if independent >= 2 and strong else
            "TIER_C_WEAK_OR_UNVERIFIED_FACEBOOK")
    email = normalize_email(rendered.get("email") or "")
    visible = bool(email and email.lower() in text.lower())
    email_class = ("CLASS_A_OFFICIAL_LINKED_SOCIAL_EMAIL" if tier.startswith("TIER_A") else
                   "CLASS_B_STRONG_MATCH_SOCIAL_EMAIL" if tier.startswith("TIER_B") else
                   "CLASS_C_WEAK_SOCIAL_EMAIL") if visible else "NONE"
    index = text.lower().find(email.lower()) if visible else -1
    excerpt = text[max(0, index - 80):index + len(email) + 80].strip()[:200] if index >= 0 else ""
    return {"facebook_provenance_tier": tier, "social_email_class": email_class,
            "identity_match_signals": signals, "public_email": email if visible else "",
            "visible_email_excerpt": excerpt, "public_website": rendered.get("website") or "",
            "public_phone": rendered.get("phone") or "", "public_business_address": rendered.get("address") or "",
            "facebook_page_name": name, "about_excerpt": text[:300],
            "facebook_website_recovered": bool(rendered.get("website") and not lead.get("official_website")),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "safe_eligible_from_social": False}


def render_facebook_page(lead: dict, fb_url: str, profile: Path | None = None,
                         official_linked: bool | None = None) -> dict:
    # The explicit web flag is a development harness requirement. The
    # production review server has no development-copy marker and must not
    # depend on a development-only environment variable after review.
    if (ROOT / ".development-copy").exists() and os.getenv("ROKT_DEV_CONTROLLED_WEB") != "1":
        return {"status": "controlled_web_not_enabled"}
    if not _fb_url(fb_url):
        return {"status": "facebook_business_url_invalid"}
    profile = (profile or ROOT / "output" / "runtime" / "facebook_business_enrichment").resolve()
    if not profile.is_relative_to(ROOT):
        return {"status": "unsafe_browser_profile_path"}
    from playwright.sync_api import sync_playwright
    limiter = FBRateLimiter(RateLimitConfig(max_pages_per_round=1))
    limiter.start_round()
    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(str(profile), headless=True)
            try:
                page = context.new_page()
                raw = read_fb_page_with_limiter(page, fb_url, limiter)
                if raw.get("error"):
                    error = str(raw["error"])
                    status = ("facebook_login_required" if "login" in error else
                              "facebook_captcha" if "captcha" in error else
                              "facebook_page_not_found" if "not_found" in error else "facebook_other_error")
                    return {"status": status, "error": error[:150], "facebook_page_url": fb_url}
                if official_linked is None:
                    try:
                        linked = official_linked_facebook(lead, fb_url)
                    except Exception:
                        linked = False
                else:
                    linked = official_linked
                result = classify_facebook(lead, raw, linked)
                result.update({"status": "opened", "facebook_page_url": fb_url})
                return result
            finally:
                context.close()
    except Exception as exc:
        return {"status": "facebook_other_error", "error": type(exc).__name__, "facebook_page_url": fb_url}


def verify_recovered_website(lead: dict, website: str, fetcher=None) -> dict:
    """Read-only handoff to the canonical official-site verifier/extractor."""
    parsed = urlsplit(website)
    hostname = parsed.hostname or ""
    try:
        ipaddress.ip_address(hostname)
        is_ip = True
    except ValueError:
        is_ip = False
    if (parsed.scheme not in {"http", "https"} or not hostname or "." not in hostname
            or is_ip or parsed.username or parsed.password or hostname.endswith((".local", ".internal"))
            or host(website) in {"facebook.com", "google.com"}):
        return {"verified": False, "reason": "invalid_merchant_website"}
    pages = _fetch_official_pages(website, fetcher or BrowserFallbackWebsiteFetcher())
    if not pages or not _official_identity_match({"business_name": lead.get("store_name"), "website": website}, pages):
        return {"verified": False, "reason": "official_identity_or_http_tls_failed"}
    evidence = _extract_email_evidence(pages, str(lead.get("store_name") or ""))
    return {"verified": True, "website": website, "facebook_to_official_site_email_found": bool(evidence),
            "first_party_email_evidence": evidence or {}, "persisted": False,
            "note": "Review evidence only; canonical eligibility and manual submission still required."}
