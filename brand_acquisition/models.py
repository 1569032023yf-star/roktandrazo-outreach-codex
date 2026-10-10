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
    official_site_verification_status: str = "unknown"
    official_site_final_url: str = ""
    official_site_checked_at: str = ""
    official_site_candidates: list[dict[str, Any]] = field(default_factory=list)
    official_site_resolution_status: str = "OFFICIAL_SITE_UNRESOLVED"
    owner_verification_evidence: list[dict[str, Any]] = field(default_factory=list)
    brand_identity_status: str = "unknown"
    identity_class: str = "IDENTITY_UNVERIFIED"
    enrichment_status: str = "pending"
    organization_key: str = ""
    discovery_source_url: str = ""
    source_page_fetched_at: str = ""
    brand_claim: str = ""
    product_or_listing_evidence: list[dict[str, Any]] = field(default_factory=list)
    source_acquisition_method: str = ""
    data_origin: str = "unclassified"
    data_origin_label: str = "UNCLASSIFIED"
    source_capture_ids: list[str] = field(default_factory=list)
    fixture_status: str = ""
    business_email: str = ""
    rejected_business_email: str = ""
    email_role: str = ""
    email_evidence_url: str = ""
    email_evidence_excerpt: str = ""
    email_checked_at: str = ""
    email_evidence_source_type: str = ""
    email_http_status: int | None = None
    email_final_url: str = ""
    email_official_identity_verified: bool = False
    email_hygiene_status: str = "unknown"
    history_status: str = "UNKNOWN"
    mx_status: str = "unknown"
    product_evidence: list[dict[str, Any]] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    stage_statuses: dict[str, dict[str, Any]] = field(default_factory=dict)
    email_quality_status: str = "unchecked"

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
    network_failures: int = 0
    access_restricted: int = 0
    parse_empty: int = 0
    fixture_candidates: int = 0
    runtime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
