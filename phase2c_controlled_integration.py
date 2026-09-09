"""One-shot controlled Phase 2C web validation. Never imports or writes production paths."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "phase2c_rc2_validation.db"
RESULT_PATH = ROOT / "audit_evidence" / "phase2c_controlled_integration_rc2.json"
RUN_ID = "phase2c-controlled-rc2"

if os.environ.get("ROKT_DEV_CONTROLLED_WEB") != "1":
    raise RuntimeError("ROKT_DEV_CONTROLLED_WEB=1 is required")
if not (ROOT / ".development-copy").is_file():
    raise RuntimeError("DEVELOPMENT_MARKER_MISSING")
if DB_PATH.exists() or RESULT_PATH.exists():
    raise RuntimeError("PHASE2C_ONE_SHOT_ARTIFACT_ALREADY_EXISTS")

from dev_fsp import materialize_dev_fsp
from discovery.discovery_service import DiscoveryService, UrlLibWebsiteFetcher
from discovery.models import ProviderPage
from discovery.normalizer import normalized_domain
from discovery.providers.base import SearchProvider
from discovery.providers.browser_maps import _scrape_direct
from discovery.website_resolver import NON_OFFICIAL_DOMAINS, ProviderWebsiteResolver, score_candidate
from retail_city_queue import search_queries
from tests.schema_fixture import create_test_database


class ReplayProvider(SearchProvider):
    provider_name = "browser_maps"
    configured = True

    def __init__(self, real_page: ProviderPage) -> None:
        self.real_page = real_page

    def search_places(self, query, city, state, page_cursor="", page_size=20):
        return ProviderPage(
            provider="browser_maps", query=query, city=city, state=state,
            page_cursor=page_cursor, results=list(self.real_page.results[:page_size]),
            next_page_cursor="", status=self.real_page.status,
            error=self.real_page.error, request_count=0, cost_units=0,
        )


def mx_status(domain: str) -> str:
    """Controlled public DNS MX lookup; no Worker or remote writes."""
    try:
        import dns.resolver
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


query = "board game store Nashville TN"
real_page = _scrape_direct(query, "Nashville", "TN", 5, headless=True)
provider_ok = real_page.ok and len(real_page.results) >= 5

conn = create_test_database(DB_PATH)
try:
    city = dict(conn.execute(
        "SELECT * FROM retail_city_queue WHERE city='Nashville' AND state='TN' ORDER BY id LIMIT 1"
    ).fetchone())
    city["active_query_family"] = "board game store"
    expected_query = dict(zip(__import__("outreach_control").RETAIL_QUERY_FAMILIES, search_queries(city)))["board game store"]
    provider = ReplayProvider(real_page)
    service = DiscoveryService(conn, provider=provider, page_size=5)

    first_discovery = service.run_places_batch(city, max_pages=1)
    first_websites = service.run_website_resolution(city, ProviderWebsiteResolver(provider), max_results=5)
    first_evidence = service.run_staging_postprocess(city, max_results=5, fetcher=UrlLibWebsiteFetcher(15))
    conn.commit()

    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM lead_discovery_results WHERE active_city_id=? ORDER BY id LIMIT 5", (city["id"],)
    )]
    email_domains = {
        row["email"].rsplit("@", 1)[1].lower()
        for row in (dict(r) for r in conn.execute("SELECT email FROM leads WHERE COALESCE(email,'')!=''"))
    }
    controlled_mx = {domain: mx_status(domain) for domain in sorted(email_domains)}
    lead_ids = [r[0] for r in conn.execute("SELECT id FROM leads ORDER BY id")]
    first_fsp = materialize_dev_fsp(conn, lead_ids, controlled_mx, RUN_ID)
    conn.commit()

    first_counts = {
        "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "orgs": conn.execute("SELECT COUNT(DISTINCT organization_key) FROM leads WHERE COALESCE(organization_key,'')!=''").fetchone()[0],
        "dev_fsp": conn.execute("SELECT COUNT(*) FROM dev_safe_fsp").fetchone()[0],
    }

    second_discovery = service.run_places_batch(city, max_pages=1)
    service.run_website_resolution(city, ProviderWebsiteResolver(provider), max_results=5)
    service.run_staging_postprocess(city, max_results=5, fetcher=UrlLibWebsiteFetcher(15))
    second_fsp = materialize_dev_fsp(conn, lead_ids, controlled_mx, RUN_ID)
    conn.commit()
    second_counts = {
        "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        "orgs": conn.execute("SELECT COUNT(DISTINCT organization_key) FROM leads WHERE COALESCE(organization_key,'')!=''").fetchone()[0],
        "dev_fsp": conn.execute("SELECT COUNT(*) FROM dev_safe_fsp").fetchone()[0],
    }

    quality_rows = []
    junk_names = directories = guessed = hidden = mismatches = 0
    for row in rows:
        lead = conn.execute("SELECT * FROM leads WHERE id=?", (row.get("linked_lead_id"),)).fetchone() if row.get("linked_lead_id") else None
        lead = dict(lead) if lead else {}
        result = next((item for item in real_page.results if item.provider_result_id == row.get("provider_result_id")), None)
        identity_score, identity_evidence = score_candidate(row, result) if result else (0, [])
        website = row.get("website") or ""
        domain = normalized_domain(website)
        is_directory = any(domain == item or domain.endswith("." + item) for item in NON_OFFICIAL_DOMAINS)
        name = str(row.get("business_name") or "").strip()
        is_junk = not name or name.lower() in {"results", "sponsored", "more places"} or not re.search(r"[A-Za-z0-9]", name)
        email = lead.get("email") or ""
        excerpt = lead.get("evidence_snippet") or row.get("evidence_snippet") or ""
        source_type = lead.get("email_source_type") or ""
        promoted_mismatch = bool(
            row.get("linked_lead_id")
            and not row.get("official_match")
            and conn.execute(
                "SELECT 1 FROM dev_safe_fsp WHERE lead_id=? LIMIT 1",
                (row.get("linked_lead_id"),),
            ).fetchone()
        )
        hidden_email = bool(email and email.lower() not in excerpt.lower())
        junk_names += int(is_junk)
        directories += int(is_directory)
        guessed += int(source_type == "guessed_email")
        hidden += int(hidden_email)
        mismatches += int(promoted_mismatch)
        quality_rows.append({
            "business_name": name,
            "official_website": website,
            "final_url": lead.get("evidence_url") or row.get("evidence_url") or website,
            "identity_evidence": {"score": identity_score, "signals": identity_evidence},
            "email": email,
            "visible_text_excerpt": excerpt,
            "content_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest() if excerpt else "",
            "email_source_type": source_type,
            "validation_status": row.get("validation_status"),
        })

    metrics = {
        "JUNK_BUSINESS_NAMES": junk_names,
        "DIRECTORY_AS_OFFICIAL_SITE": directories,
        "GUESSED_EMAILS": guessed,
        "HIDDEN_SCRIPT_EMAIL_ACCEPTED": hidden,
        "IDENTITY_MISMATCH_PROMOTED": mismatches,
        "DUPLICATE_LEADS": second_counts["leads"] - first_counts["leads"],
        "DUPLICATE_ORGS": second_counts["orgs"] - first_counts["orgs"],
        "DUPLICATE_DEV_FSP": second_counts["dev_fsp"] - first_counts["dev_fsp"],
    }
    result = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "pipeline_query": expected_query,
        "database": str(DB_PATH),
        "provider": {"status": real_page.status, "error": real_page.error, "count": len(real_page.results), "pass": provider_ok},
        "first_run": {
            "discovery": first_discovery.__dict__, "website": first_websites.__dict__,
            "evidence": first_evidence.__dict__, "fsp": first_fsp, "counts": first_counts,
        },
        "second_run": {"discovery": second_discovery.__dict__, "fsp": second_fsp, "counts": second_counts},
        "controlled_mx": controlled_mx,
        "quality_rows": quality_rows,
        "metrics": metrics,
        "real_website_resolution_pass": any(row["official_website"] for row in quality_rows),
        "real_official_email_extraction_pass": any(row["email"] for row in quality_rows),
        "dev_safe_fsp_created": second_counts["dev_fsp"],
        "second_run_idempotent": all(value == 0 for key, value in metrics.items() if key.startswith("DUPLICATE_")),
        "real_smtp_connections": 0,
    }
finally:
    conn.close()

RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
