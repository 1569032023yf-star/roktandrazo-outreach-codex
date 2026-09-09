"""Development coordinator for Discovery → Website → Evidence → V2/MX → Dev FSP."""
from __future__ import annotations

import sqlite3
from typing import Any

from dev_fsp import materialize_dev_fsp


def run_development_funnel(
    conn: sqlite3.Connection,
    service: Any,
    city_row: dict,
    website_resolver: Any,
    fetcher: Any,
    mx_lookup: dict[str, str],
    run_id: str,
    *,
    max_pages: int = 1,
    max_results: int = 20,
) -> dict:
    """Run an idempotent, no-send development replenishment funnel."""
    discovery = service.run_places_batch(city_row, max_pages=max_pages)
    websites = service.run_website_resolution(city_row, website_resolver, max_results=max_results)
    evidence = service.run_staging_postprocess(city_row, max_results=max_results, fetcher=fetcher)
    lead_ids = [
        row[0] for row in conn.execute(
            """SELECT DISTINCT linked_lead_id FROM lead_discovery_results
               WHERE active_city_id=? AND linked_lead_id IS NOT NULL
                 AND validation_status='lead_created'""",
            (int(city_row["id"]),),
        ).fetchall()
    ]
    dev_fsp = materialize_dev_fsp(conn, lead_ids, mx_lookup, run_id)
    conn.commit()
    counts = dict(conn.execute(
        """SELECT
             COUNT(*) AS discovered,
             SUM(CASE WHEN COALESCE(website,'')!='' THEN 1 ELSE 0 END) AS website_found,
             SUM(CASE WHEN COALESCE(evidence_snippet,'')!='' AND official_match=1 THEN 1 ELSE 0 END) AS official_evidence
           FROM lead_discovery_results WHERE active_city_id=?""",
        (int(city_row["id"]),),
    ).fetchone())
    return {
        "run_id": run_id,
        "discovery": discovery.__dict__,
        "website_resolution": websites.__dict__,
        "evidence": evidence.__dict__,
        "funnel": {**counts, "v2_mx_evaluated": dev_fsp["evaluated"], "safe_fsp": dev_fsp["eligible"]},
        "dev_fsp": dev_fsp,
        "smtp_calls": 0,
    }
