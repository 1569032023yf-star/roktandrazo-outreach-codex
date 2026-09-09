"""Brand Candidate Importer — universal CSV/JSON/URL/brand-name import.

All imported candidates must pass full verification before becoming A0.
Supports: CSV, JSON, URL list, brand name list.
"""
from __future__ import annotations

import csv, hashlib, json, sqlite3, sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
import bd_db

DB_PATH = PROJECT_DIR / "data" / "bd_leads.db"

# Allowed discovery sources
DISCOVERY_SOURCES = {
    "google_public_search", "amazon_public", "kickstarter_public",
    "gamefound_public", "backerkit_public", "etsy_public",
    "independent_site_search", "tiktok_manual_public",
    "fastmoss_optional_import",
}

# TikTok discovery modes
TIKTOK_MODES = {
    "manual_public_discovery": "Free public TikTok Shop pages via Google/search",
    "optional_fastmoss_sprint": "User-provided FastMoss export (short-term paid)",
    "inactive_no_candidate": "No TikTok candidates available",
}


def import_from_csv(path: str, source: str) -> list[dict]:
    """Import candidates from CSV file."""
    if source not in DISCOVERY_SOURCES:
        raise ValueError(f"Unknown discovery source: {source}")
    results = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append({
                "brand_name": row.get("brand_name", row.get("store_name", "")).strip(),
                "store_url": row.get("store_url", row.get("website", "")).strip(),
                "product_name": row.get("product_name", "").strip(),
                "product_category": row.get("product_category", "").strip(),
                "source_platform": row.get("platform", "Unknown"),
                "discovery_source": source,
                "sales_signal": row.get("sales_signal", "").strip(),
                "country_signal": row.get("country_signal", "").strip(),
                "collected_at": datetime.now().isoformat(),
            })
    return results


def import_from_json(path: str, source: str) -> list[dict]:
    """Import candidates from JSON file (expects list of dicts)."""
    if source not in DISCOVERY_SOURCES:
        raise ValueError(f"Unknown discovery source: {source}")
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        data = [data]
    results = []
    for item in data:
        results.append({
            "brand_name": item.get("brand_name", item.get("store_name", "")).strip(),
            "store_url": item.get("store_url", item.get("website", "")).strip(),
            "product_name": item.get("product_name", "").strip(),
            "product_category": item.get("product_category", "").strip(),
            "source_platform": item.get("platform", "Unknown"),
            "discovery_source": source,
            "sales_signal": item.get("sales_signal", "").strip(),
            "country_signal": item.get("country_signal", "").strip(),
            "collected_at": datetime.now().isoformat(),
        })
    return results


def import_from_urls(urls: list[str], source: str, platform: str = "Unknown") -> list[dict]:
    """Import candidates from a list of brand/website URLs."""
    if source not in DISCOVERY_SOURCES:
        raise ValueError(f"Unknown discovery source: {source}")
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        results.append({
            "brand_name": url.split("//")[-1].split("/")[0].replace("www.", ""),
            "store_url": url,
            "product_name": "",
            "product_category": "",
            "source_platform": platform,
            "discovery_source": source,
            "sales_signal": "",
            "country_signal": "",
            "collected_at": datetime.now().isoformat(),
        })
    return results


def import_from_names(names: list[str], source: str, platform: str = "Unknown") -> list[dict]:
    """Import candidates from brand name list (will need URL discovery later)."""
    if source not in DISCOVERY_SOURCES:
        raise ValueError(f"Unknown discovery source: {source}")
    results = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        results.append({
            "brand_name": name,
            "store_url": "",
            "product_name": "",
            "product_category": "",
            "source_platform": platform,
            "discovery_source": source,
            "sales_signal": "",
            "country_signal": "",
            "collected_at": datetime.now().isoformat(),
        })
    return results


def write_to_db(candidates: list[dict]) -> dict:
    """Write candidates to DB. Returns {inserted, skipped_duplicate, skipped_existing}."""
    conn = sqlite3.connect(DB_PATH)
    counts = {"inserted": 0, "skipped_duplicate": 0, "skipped_existing": 0}
    now = datetime.now().isoformat()

    for c in candidates:
        name = c["brand_name"]
        if not name:
            continue

        # Check existing
        exist = conn.execute(
            "SELECT id FROM leads WHERE store_name=? COLLATE NOCASE", (name,)
        ).fetchone()
        if exist:
            counts["skipped_existing"] += 1
            continue

        website = c.get("store_url", "")
        domain = website.split("//")[1].split("/")[0] if "//" in website else ""
        dh = hashlib.sha256(domain.encode()).hexdigest() if domain else None
        identity_str = f"{name.strip().lower()}|{website.lower() or 'no_website'}"
        lih = hashlib.sha256(identity_str.encode()).hexdigest()

        if conn.execute("SELECT 1 FROM leads WHERE lead_identity_hash=?", (lih,)).fetchone():
            counts["skipped_duplicate"] += 1
            continue

        inserted_id = bd_db.insert_lead(
            {
                "store_name": name,
                "store_type": "online_brand",
                "city": "",
                "state": "",
                "official_website": website,
                "email": "",
                "email_source_type": "unknown",
                "email_verified_on_official_site": 0,
                "confidence_score": "B",
                "status": "new",
                "product_fit": c.get("product_category", ""),
                "source_keyword": c.get("discovery_source", ""),
                "source_platform": c.get("source_platform", "Unknown"),
                "collected_at": now,
                "domain_hash": dh,
                "lead_identity_hash": lih,
            },
            conn=conn,
        )
        if inserted_id:
            counts["inserted"] += 1
        else:
            counts["skipped_duplicate"] += 1

    conn.commit()
    conn.close()
    return counts
