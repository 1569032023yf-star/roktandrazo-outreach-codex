"""Directory metrics and identity callbacks reuse the established acquisition pipeline."""
from __future__ import annotations

from collections import Counter
from .directory_adapters import DIRECTORY_SOURCES
from .models import BrandCandidate
from .pipeline import AcquisitionPipeline, deduplicate, make_runtime_callbacks


def make_directory_callbacks(fetcher=None):
    callbacks = make_runtime_callbacks(fetcher, strict_name_match=True)
    verify_site = callbacks["official_site_check"]

    def organization(candidate):
        if not candidate.directory_evidence or not verify_site(candidate):
            return False
        # Independently match organization identity on its first-party HTTPS site.
        # Product/owner/buyer-type classification remains a directory hypothesis.
        candidate.owner_verification_evidence.append({"type": "first_party_organization_identity",
            "source_url": candidate.official_site_final_url or candidate.official_website,
            "directory_sources": list(candidate.source_urls), "verified": True,
            "brand_ownership_verified": False, "buyer_intent_verified": False})
        candidate.identity_class = "ORGANIZATION_CONFIRMED"
        return True

    callbacks["organization_identity_check"] = organization
    return callbacks


def directory_metrics(raw, candidates):
    """Separate discovery provenance; imports and fixtures never count as live yield."""
    rows = [c if isinstance(c, BrandCandidate) else BrandCandidate(**c) for c in candidates]
    raw_rows = [c if isinstance(c, BrandCandidate) else BrandCandidate(**c) for c in raw]

    def counts(observations, unique):
        valid = [c for c in unique if c.identity_class != "IDENTITY_CONFLICT"
                 and c.category_filter_status != "excluded"]
        verified = [c for c in valid if c.official_site_verified and c.organization_identity_verified
                    and c.data_origin_label == "LIVE_PUBLIC_CAPTURE"]
        emails = [c for c in verified if c.business_email and c.email_hygiene_status == "ok"
                  and c.email_official_identity_verified and c.email_evidence_url
                  and c.email_evidence_excerpt and c.email_checked_at]
        metrics = {source.upper() + "_RAW_ORGS": sum(source in c.source_platforms for c in observations)
                   for source in DIRECTORY_SOURCES}
        metrics.update({"RAW_ORGANIZATION_RECORDS": len(observations),
            "DEDUPED_CANDIDATE_ORGS": len(unique), "TOTAL_DEDUPED_CANDIDATE_ORGS": len(unique),
            "VERIFIED_UNIQUE_ORGS": len(verified),
            "CROSS_SOURCE_DUPLICATES": sum(max(0, len(set(c.source_platforms)) - 1) for c in unique),
            "RETAIL_BUYER_CANDIDATES": sum(c.organization_type in {"RETAIL_BUYER_CANDIDATE", "DISTRIBUTOR_CANDIDATE"} for c in valid),
            "BRAND_OWNER_CANDIDATES": sum(c.organization_type in {"BRAND_OWNER_CANDIDATE", "PUBLISHER_CANDIDATE"} for c in valid),
            "OFFICIAL_SITE_CANDIDATES": sum(bool(c.official_site_candidates) for c in valid),
            "OFFICIAL_SITES_VERIFIED": len(verified), "FIRST_PARTY_EMAILS_FOUND": len(emails),
            "B2B_EMAILS_FOUND": sum(c.email_role in {"WHOLESALE", "SALES", "PARTNERSHIPS", "TRADE", "BUSINESS", "ORDERS", "GENERAL"} for c in emails),
            "MX_OK": sum(c.mx_status == "ok" for c in emails),
            "HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL": sum(c.mx_status == "ok" and c.history_status == "new_candidate" for c in emails),
            "CATEGORY_EXCLUDED": sum(c.category_filter_status == "excluded" for c in unique),
            "IDENTITY_CONFLICTS": sum(c.identity_class == "IDENTITY_CONFLICT" for c in unique),
            "ORGANIZATION_TYPES": dict(Counter(c.organization_type for c in unique)),
            "FIRST_PARTY_EMAILS_BY_CUSTOMER_TYPE": dict(Counter(c.organization_type for c in emails))})
        return metrics

    origin = lambda c: ("TEST_FIXTURE" if c.data_origin_label in {"TEST_FIXTURE", "KNOWN_TEST_SEED"}
                        else "LIVE_PUBLIC_CAPTURE" if c.data_origin_label == "LIVE_PUBLIC_CAPTURE"
                        else "OFFLINE_IMPORT")
    breakdown = {label: counts([c for c in raw_rows if origin(c) == label],
                              [c for c in rows if origin(c) == label])
                 for label in ("TEST_FIXTURE", "OFFLINE_IMPORT", "LIVE_PUBLIC_CAPTURE")}
    # Business headline quantities are live-only. Offline discovery appears only
    # in its own bucket, even if malicious import metadata asserts verified fields.
    result = dict(breakdown["LIVE_PUBLIC_CAPTURE"])
    result["BY_DATA_ORIGIN"] = breakdown
    result["ALL_DISCOVERY_RECORDS"] = len(raw_rows)
    return result


class DirectoryAcquisitionPipeline(AcquisitionPipeline):
    def enrich(self, candidates, source_metrics=None):
        raw = list(candidates)
        # Keep raw counts before the shared deduplicator mutates evidence lists.
        observations = [BrandCandidate(**c.to_dict()) for c in raw]
        payload = super().enrich(raw, source_metrics)
        # Reconcile identities learned during enrichment across sources.
        unique = deduplicate(BrandCandidate(**c) for c in payload["candidates"])
        for c in unique:
            if c.identity_class == "IDENTITY_CONFLICT":
                c.rejected_business_email = c.business_email or c.rejected_business_email
                c.business_email = ""
                c.enrichment_status = "identity_conflict"
                c.mx_status = "not_eligible_identity_conflict"
        payload["candidates"] = [c.to_dict() for c in unique]
        payload["directory_metrics"] = directory_metrics(observations, unique)
        # Persist the reconciled audit result; retain per-observation checkpoints
        # written by the shared pipeline for safe retry attribution.
        import json
        (self.output_dir / "brand_candidates.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
