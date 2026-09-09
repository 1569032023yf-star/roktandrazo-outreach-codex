"""Deterministic official-website resolution through a configured provider."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from discovery.normalizer import normalize_business_name, normalize_phone, normalized_domain

NON_OFFICIAL_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "yelp.com", "yellowpages.com",
    "mapquest.com", "wargames.com", "localgamestores.com", "chamberofcommerce.com",
}


@dataclass(frozen=True)
class WebsiteResolution:
    status: str
    website: str = ""
    score: int = 0
    evidence: list[str] = field(default_factory=list)
    error: str = ""


def _official_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    parsed = urlsplit(text)
    domain = normalized_domain(text)
    if not parsed.netloc or any(domain == item or domain.endswith("." + item) for item in NON_OFFICIAL_DOMAINS):
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "", "", ""))


def _name_tokens(value: str) -> set[str]:
    stop = {"the", "and", "store", "shop", "llc", "inc", "company", "co"}
    return {part for part in re.findall(r"[a-z0-9]+", normalize_business_name(value)) if len(part) > 2 and part not in stop}


def score_candidate(subject: dict[str, Any], candidate: Any) -> tuple[int, list[str]]:
    subject_tokens = _name_tokens(subject.get("business_name") or "")
    candidate_tokens = _name_tokens(getattr(candidate, "business_name", ""))
    overlap = len(subject_tokens & candidate_tokens)
    evidence: list[str] = []
    score = 0
    if overlap / max(1, len(subject_tokens)) >= 0.6:
        score += 60
        evidence.append("business_name")
    subject_phone = normalize_phone(subject.get("phone") or "")
    candidate_phone = normalize_phone(getattr(candidate, "phone", "") or "")
    if subject_phone and candidate_phone and subject_phone == candidate_phone:
        score += 35
        evidence.append("phone")
    if (str(subject.get("city") or "").strip().lower() == str(getattr(candidate, "city", "") or "").strip().lower()
            and str(subject.get("state") or "").strip().upper() == str(getattr(candidate, "state", "") or "").strip().upper()):
        score += 20
        evidence.append("city_state")
    return score, evidence


class ProviderWebsiteResolver:
    def __init__(self, provider, minimum_score: int = 80) -> None:
        self.provider = provider
        self.minimum_score = minimum_score

    def resolve(self, subject: dict[str, Any]) -> WebsiteResolution:
        query = " ".join(filter(None, [subject.get("business_name"), subject.get("formatted_address"), subject.get("phone")]))
        page = self.provider.search_places(query, subject.get("city") or "", subject.get("state") or "", "", 10)
        if not page.ok:
            return WebsiteResolution("network_retry", error=page.error or page.status)
        ranked = []
        for candidate in page.results:
            website = _official_url(getattr(candidate, "website", ""))
            if not website:
                continue
            score, evidence = score_candidate(subject, candidate)
            ranked.append((score, normalized_domain(website), website, evidence))
        if not ranked:
            return WebsiteResolution("not_found")
        score, _domain, website, evidence = sorted(ranked, key=lambda item: (-item[0], item[1], item[2]))[0]
        if score < self.minimum_score:
            return WebsiteResolution("identity_review", website=website, score=score, evidence=evidence)
        return WebsiteResolution("resolved", website=website, score=score, evidence=evidence)
