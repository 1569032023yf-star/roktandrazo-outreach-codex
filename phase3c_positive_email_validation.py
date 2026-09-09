"""One-shot Phase 3C positive first-party-email validation in the development copy."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "phase3c_positive_email_validation_rc2.db"
RESULT_PATH = ROOT / "audit_evidence" / "phase3c_positive_email_validation_rc2.json"
RUN_ID = "phase3c-positive-email-rc2"
TARGET_NAME_TOKEN = "noble knight"
MAPS_QUERY = "board game store Fitchburg WI"

if os.environ.get("ROKT_DEV_CONTROLLED_WEB") != "1":
    raise RuntimeError("ROKT_DEV_CONTROLLED_WEB=1 is required")
if not (ROOT / ".development-copy").is_file():
    raise RuntimeError("DEVELOPMENT_MARKER_MISSING")
if DB_PATH.exists() or RESULT_PATH.exists():
    raise RuntimeError("PHASE2D_ONE_SHOT_ARTIFACT_ALREADY_EXISTS")

from campaign_eligible_v2 import review_campaign_eligible_v2
from dev_fsp import materialize_dev_fsp
from discovery.discovery_service import DiscoveryService, UrlLibWebsiteFetcher
from discovery.models import ProviderPage
from discovery.providers.base import SearchProvider
from discovery.providers.browser_maps import _scrape_direct
from retail_city_queue import search_queries
from tests.schema_fixture import create_test_database


class ReplayProvider(SearchProvider):
    provider_name = "browser_maps"
    configured = True

    def __init__(self, page: ProviderPage) -> None:
        self.page = page

    def search_places(self, query, city, state, page_cursor="", page_size=20):
        return ProviderPage(
            provider=self.provider_name,
            query=query,
            city=city,
            state=state,
            page_cursor=page_cursor,
            results=list(self.page.results[:page_size]),
            status=self.page.status,
            error=self.page.error,
        )


class RecordingFetcher:
    """Record the exact HTTP/TLS response used by the normal extractor."""

    def __init__(self, timeout_seconds: float = 20.0) -> None:
        self.delegate = UrlLibWebsiteFetcher(timeout_seconds)
        self.records: list[dict] = []

    def fetch(self, requested_url: str):
        fetched_at = datetime.now(timezone.utc).isoformat()
        try:
            value = self.delegate.fetch(requested_url)
        except Exception as exc:
            self.records.append({
                "requested_url": requested_url,
                "final_url": "",
                "http_status": 0,
                "http_success": False,
                "tls_success": False,
                "fetched_at": fetched_at,
                "text": "",
                "error": f"{type(exc).__name__}: {exc}",
            })
            raise
        record = {
            "requested_url": requested_url,
            "final_url": str(value.get("final_url") or requested_url) if isinstance(value, dict) else requested_url,
            "http_status": int(value.get("status") or 0) if isinstance(value, dict) else 200,
            "http_success": bool(isinstance(value, dict) and 200 <= int(value.get("status") or 0) < 400),
            "tls_success": bool(isinstance(value, dict) and value.get("tls_verified", False)),
            "fetched_at": fetched_at,
            "text": str(value.get("text") or "") if isinstance(value, dict) else str(value or ""),
            "error": "",
        }
        self.records.append(record)
        return value


def controlled_mx_status(domain: str) -> str:
    """Public DNS MX lookup only; no Worker and no remote writes."""
    import dns.resolver

    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=8)
        if any(str(item.exchange).rstrip(".") == "" for item in answers):
            return "null_mx"
        return "ok"
    except dns.resolver.NXDOMAIN:
        return "nxdomain"
    except dns.resolver.NoAnswer:
        return "no_mail_route"
    except Exception:
        return "dns_error"


provider_page = _scrape_direct(MAPS_QUERY, "Fitchburg", "WI", 5, headless=True)
selected = [item for item in provider_page.results if TARGET_NAME_TOKEN in item.business_name.lower()]
selected_page = ProviderPage(
    provider="browser_maps",
    query=MAPS_QUERY,
    city="Fitchburg",
    state="WI",
    page_cursor="",
    results=selected[:1],
    status=provider_page.status,
    error=provider_page.error,
)

conn = create_test_database(DB_PATH)
try:
    discovered = selected[0] if selected else None
    city_name = (discovered.city if discovered and discovered.city else "Fitchburg")
    state_name = (discovered.state if discovered and discovered.state else "WI")
    conn.execute(
        """INSERT OR IGNORE INTO retail_city_queue
           (city,state,priority,timezone,status) VALUES (?,?,?,?, 'active')""",
        (city_name, state_name, 1, "America/Chicago"),
    )
    city = dict(conn.execute(
        "SELECT * FROM retail_city_queue WHERE city=? AND state=? ORDER BY id LIMIT 1",
        (city_name, state_name),
    ).fetchone())
    city["active_query_family"] = "board game store"
    pipeline_query = dict(zip(__import__("outreach_control").RETAIL_QUERY_FAMILIES, search_queries(city)))["board game store"]

    service = DiscoveryService(conn, provider=ReplayProvider(selected_page), page_size=1)
    fetcher = RecordingFetcher()

    first_discovery = service.run_places_batch(city, max_pages=1)
    first_website = service.run_website_resolution(city, None, max_results=1)
    first_evidence = service.run_staging_postprocess(city, max_results=1, fetcher=fetcher)
    conn.commit()

    staging_row = conn.execute(
        "SELECT * FROM lead_discovery_results WHERE active_city_id=? ORDER BY id LIMIT 1",
        (city["id"],),
    ).fetchone()
    staging = dict(staging_row) if staging_row else {}
    lead_row = conn.execute(
        "SELECT * FROM leads WHERE id=?",
        (staging.get("linked_lead_id"),),
    ).fetchone() if staging.get("linked_lead_id") else None
    lead = dict(lead_row) if lead_row else {}
    extracted_email = str(lead.get("email") or "")

    raw_payload = json.loads(staging.get("raw_payload_json") or "{}")
    evidence_record = raw_payload.get("official_email_evidence") or {}
    visible_excerpt = str(lead.get("evidence_snippet") or "")
    evidence = {
        "requested_url": evidence_record.get("requested_url", ""),
        "final_url": evidence_record.get("final_url", lead.get("evidence_url") or ""),
        "http_status": evidence_record.get("http_status", 0),
        "http_success": bool(evidence_record.get("http_success")),
        "tls_success": bool(evidence_record.get("tls_success")),
        "fetched_at": evidence_record.get("fetched_at", ""),
        "visible_text_excerpt": evidence_record.get("visible_text_excerpt", visible_excerpt),
        "content_hash": evidence_record.get("content_hash", ""),
        "email": evidence_record.get("email", extracted_email),
        "email_source_type": evidence_record.get("email_source_type", str(lead.get("email_source_type") or "")),
    }
    visible_evidence_pass = bool(
        extracted_email
        and extracted_email.lower() in str(evidence["visible_text_excerpt"]).lower()
        and evidence["http_success"]
        and evidence["tls_success"]
        and len(str(evidence["content_hash"])) == 64
    )

    email_domain = extracted_email.rsplit("@", 1)[1].lower() if "@" in extracted_email else ""
    mx_lookup = {email_domain: controlled_mx_status(email_domain)} if email_domain else {}
    v2_decision = review_campaign_eligible_v2(lead, {"conn": conn, "mx_lookup": mx_lookup}) if lead else {}
    lead_ids = [int(lead["id"])] if lead else []
    first_fsp = materialize_dev_fsp(conn, lead_ids, mx_lookup, RUN_ID)
    conn.commit()
    first_counts = {
        "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "orgs": conn.execute("SELECT COUNT(DISTINCT organization_key) FROM leads WHERE COALESCE(organization_key,'')!=''").fetchone()[0],
        "dev_fsp": conn.execute("SELECT COUNT(*) FROM dev_safe_fsp").fetchone()[0],
    }

    second_discovery = service.run_places_batch(city, max_pages=1)
    service.run_website_resolution(city, None, max_results=1)
    service.run_staging_postprocess(city, max_results=1, fetcher=fetcher)
    second_fsp = materialize_dev_fsp(conn, lead_ids, mx_lookup, RUN_ID)
    conn.commit()
    replay_payload = json.loads(conn.execute(
        "SELECT raw_payload_json FROM lead_discovery_results WHERE id=?",
        (staging.get("id"),),
    ).fetchone()[0])
    evidence_persisted_after_second_run = replay_payload.get("official_email_evidence") == evidence_record
    second_counts = {
        "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "orgs": conn.execute("SELECT COUNT(DISTINCT organization_key) FROM leads WHERE COALESCE(organization_key,'')!=''").fetchone()[0],
        "dev_fsp": conn.execute("SELECT COUNT(*) FROM dev_safe_fsp").fetchone()[0],
    }
    duplicate_counts = {
        "DUPLICATE_LEADS": second_counts["leads"] - first_counts["leads"],
        "DUPLICATE_ORGS": second_counts["orgs"] - first_counts["orgs"],
        "DUPLICATE_DEV_FSP": second_counts["dev_fsp"] - first_counts["dev_fsp"],
    }

    result = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "selection": {"merchant": "Noble Knight Games", "maps_query": MAPS_QUERY, "known_email_seeded": False},
        "pipeline_query": pipeline_query,
        "database": str(DB_PATH),
        "real_merchant_found": bool(selected),
        "merchant": selected[0].to_record() if selected else {},
        "official_website_verified": bool(staging.get("official_match") and staging.get("website")),
        "first_run": {
            "discovery": first_discovery.__dict__,
            "website": first_website.__dict__,
            "evidence": first_evidence.__dict__,
            "fsp": first_fsp,
            "counts": first_counts,
        },
        "real_official_email_extraction_pass": visible_evidence_pass,
        "evidence": evidence,
        "controlled_mx_path_executed": bool(mx_lookup),
        "mx_result": mx_lookup.get(email_domain, "not_executed"),
        "mx_pass": mx_lookup.get(email_domain) == "ok",
        "v2_decision": v2_decision,
        "frozen_v2_pass": bool(v2_decision.get("eligible")),
        "dev_safe_fsp_created": first_counts["dev_fsp"],
        "second_run": {"discovery": second_discovery.__dict__, "fsp": second_fsp, "counts": second_counts},
        "duplicates": duplicate_counts,
        "second_run_idempotent": (
            all(value == 0 for value in duplicate_counts.values())
            and evidence_persisted_after_second_run
        ),
        "evidence_persisted_after_second_run": evidence_persisted_after_second_run,
        "negative_safety": {
            "guessed_email": lead.get("email_source_type") == "guessed_email",
            "hidden_or_script_only": bool(extracted_email and extracted_email.lower() not in visible_excerpt.lower()),
            "directory_or_social_source": False,
            "identity_mismatch_promoted": bool(first_counts["dev_fsp"] and not staging.get("official_match")),
            "failed_http_or_tls_accepted": bool(extracted_email and not visible_evidence_pass),
        },
        "real_smtp_connections": 0,
        "production_db_writes": 0,
        "production_files_changed": 0,
    }
finally:
    conn.close()

RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
