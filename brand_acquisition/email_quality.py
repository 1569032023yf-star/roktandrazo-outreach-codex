"""Brand-acquisition-only contact quality checks; production eligibility is unchanged."""
from __future__ import annotations

from urllib.parse import urlsplit

from email_hygiene import hygiene_check

PLACEHOLDER_EMAIL_DOMAINS = frozenset({
    "mysite.com", "example.com", "example.org", "example.net", "test.com", "test.org",
    "test.net", "demo.com", "demo.org", "sample.com", "domain.com", "yourdomain.com",
    "yoursite.com", "website.com", "company.com", "email.com", "youremail.com",
})
PLACEHOLDER_LOCAL_PARTS = frozenset({"yourname", "youremail", "name", "email", "test", "example", "placeholder"})


def audit_brand_email(email: str, official_website: str, evidence: dict | None = None) -> dict:
    """Reject template/stale cross-domain contacts; allow evidenced parent domains.

    A cross-domain address is accepted only when a separate affiliation record
    explicitly binds its domain to this brand and cites first-party evidence.
    This is isolated from V1/V2 and does not modify the shared hygiene policy.
    """
    value = str(email or "").strip().casefold()
    evidence = evidence or {}
    base = hygiene_check(value)
    if not base.get("valid"):
        return {"valid": False, "status": "rejected", "reason": base.get("reason", "email_hygiene_failed")}
    local, domain = value.rsplit("@", 1)
    if domain in PLACEHOLDER_EMAIL_DOMAINS or local in PLACEHOLDER_LOCAL_PARTS:
        return {"valid": False, "status": "rejected", "reason": "placeholder_email"}
    site_host = (urlsplit(str(official_website or "")).hostname or "").casefold().removeprefix("www.")
    email_domain = domain.removeprefix("www.")
    if site_host and email_domain != site_host:
        relation = evidence.get("email_domain_affiliation") or {}
        relation_domain = str(relation.get("domain") or "").casefold().removeprefix("www.")
        excerpt = str(relation.get("excerpt") or "")
        source_url = str(relation.get("evidence_url") or "")
        confirmed = bool(relation.get("independently_verified")) and relation_domain == email_domain and value in excerpt.casefold() and source_url.startswith("https://")
        if not confirmed:
            return {"valid": False, "status": "review", "reason": "official_domain_mismatch"}
    return {"valid": True, "status": "accepted", "reason": "official_domain_match" if site_host == email_domain else "independent_domain_affiliation_verified"}
