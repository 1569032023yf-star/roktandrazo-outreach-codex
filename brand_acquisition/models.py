from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BrandCandidate:
    brand_name: str
    brand_owner_name: str = ""
    source_platforms: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    product_categories: list[str] = field(default_factory=list)
    public_sales_signals: dict[str, Any] = field(default_factory=dict)
    sales_signal_observed_at: str = ""
    official_website: str = ""
    official_site_verified: bool = False
    brand_identity_status: str = "unknown"
    enrichment_status: str = "pending"
    organization_key: str = ""
    business_email: str = ""
    email_role: str = ""
    email_evidence_url: str = ""
    email_evidence_excerpt: str = ""
    email_checked_at: str = ""
    email_hygiene_status: str = "unknown"
    history_status: str = "UNKNOWN"
    mx_status: str = "unknown"
    identity_class: str = "unknown"
    product_evidence: list[dict[str, Any]] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceMetric:
    source: str
    pages_attempted: int = 0
    pages_fetched: int = 0
    brands_discovered: int = 0
    official_sites_verified: int = 0
    emails_found: int = 0
    new_owners_with_email: int = 0
    failures: int = 0
    rate_limits: int = 0
    runtime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
