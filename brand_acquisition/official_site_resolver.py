"""Resolve explicit official-site URL evidence without inventing domains."""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from .pipeline_types import MARKETPLACE_HOSTS

_OFFICIAL_LABELS = ("official website", "official site", "brand website", "brand site",
                    "visit website", "visit site", "website", "web site")


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _safe_candidate_url(value: str) -> str:
    try:
        parsed = urlsplit(str(value or "").strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return ""
        if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            return ""
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return ""
        if any(host == domain or host.endswith("." + domain) for domain in MARKETPLACE_HOSTS):
            return ""
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return ""
        except ValueError:
            pass
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
    except (ValueError, TypeError):
        return ""


def resolve_official_site_candidates(candidate, evidence_sources) -> dict:
    """Collect only explicitly stated website links; never infer brandname.tld.

    Output candidates are leads for the existing official identity verifier. This
    resolver performs no DNS, HTTP, TLS, ownership, or authenticity checks.
    """
    name = str(_get(candidate, "brand_name", "") or "").strip()
    collected: dict[str, dict] = {}

    def add(raw_url, source_url, method, label="", relation="", signal=""):
        url = _safe_candidate_url(raw_url)
        if not url:
            return
        key = url.casefold()
        entry = collected.setdefault(key, {"website": url, "candidate_source_urls": [],
            "candidate_discovery_methods": [], "candidate_identity_signals": []})
        if source_url:
            entry["candidate_source_urls"].append(str(source_url))
        entry["candidate_discovery_methods"].append(method)
        entry["candidate_identity_signals"].append({"signal": signal or "explicit_link",
            "anchor_text": str(label or ""), "relation": str(relation or ""),
            "brand_name_context": name})

    existing = str(_get(candidate, "official_website", "") or "")
    source_url = str(_get(candidate, "discovery_source_url", "") or "")
    if not source_url:
        urls = _get(candidate, "source_urls", []) or []
        source_url = str(urls[0]) if urls else ""
    if existing:
        add(existing, source_url, "explicit_candidate_website_field", signal="candidate_field_explicit")

    sources = list(evidence_sources or [])
    for evidence in (_get(candidate, "product_evidence", []) or []):
        sources.append(evidence)
    for evidence in (_get(candidate, "product_or_listing_evidence", []) or []):
        sources.append(evidence)
    for evidence in sources:
        evidence_url = str(_get(evidence, "source_url", "") or _get(evidence, "url", "") or "")
        for field in ("official_website", "brand_website", "website_url"):
            raw = _get(evidence, field, "")
            if raw:
                add(raw, evidence_url, "explicit_" + field, signal=field)
        for link in (_get(evidence, "links", []) or []):
            href = _get(link, "url", "") or _get(link, "href", "")
            label = " ".join(str(_get(link, "label", "") or _get(link, "text", "") or "").casefold().split())
            relation = str(_get(link, "rel", "") or _get(link, "relation", "")).casefold()
            role = str(_get(link, "role", "") or "").casefold()
            if relation == "official" or role == "official_site" or any(term in label for term in _OFFICIAL_LABELS):
                add(href, evidence_url, "explicit_official_link", label, relation,
                    "official_relation" if relation == "official" else "official_link_label")

    candidates = list(collected.values())
    for entry in candidates:
        entry["candidate_source_urls"] = list(dict.fromkeys(entry["candidate_source_urls"]))
        entry["candidate_discovery_methods"] = list(dict.fromkeys(entry["candidate_discovery_methods"]))
    return {
        "brand_name": name,
        "candidate_websites": candidates,
        "candidate_source_urls": list(dict.fromkeys(url for item in candidates for url in item["candidate_source_urls"])),
        "candidate_discovery_methods": list(dict.fromkeys(method for item in candidates for method in item["candidate_discovery_methods"])),
        "candidate_identity_signals": [signal for item in candidates for signal in item["candidate_identity_signals"]],
        "resolution_status": "OFFICIAL_SITE_CANDIDATES_FOUND" if candidates else "OFFICIAL_SITE_UNRESOLVED",
    }
