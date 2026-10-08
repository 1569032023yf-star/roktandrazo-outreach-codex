"""Run focused state-transition regression checks against a supplied module copy."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT))


class Resolver:
    def __init__(self, status):
        self.status = status

    def resolve(self, row):
        return SimpleNamespace(status=self.status, website="https://merchant.example", error="fixture")


def run(module_path: Path):
    spec = importlib.util.spec_from_file_location("isolated_production_discovery_service", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    def exercise(status, linked=False):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE lead_discovery_results (
                id INTEGER PRIMARY KEY, active_city_id INTEGER, website TEXT,
                validation_status TEXT, linked_lead_id INTEGER, rejection_reason TEXT,
                last_seen_at TEXT, normalized_domain TEXT, discovered_at TEXT
            );
            CREATE TABLE leads (id INTEGER PRIMARY KEY, official_website TEXT, last_checked_at TEXT);
        """)
        if linked:
            conn.execute("INSERT " + "INTO leads VALUES (5,'','')")
        conn.execute("INSERT INTO lead_discovery_results VALUES (433,1,'','website_lookup_pending',?,'','', '',CURRENT_TIMESTAMP)",
                     (5 if linked else None,))
        conn.commit()
        service = module.DiscoveryService.__new__(module.DiscoveryService)
        service.conn = conn
        service.provider = SimpleNamespace(provider_name="isolated_fixture")
        city = {"id": 1, "city": "Saratoga Springs", "state": "NY"}
        summary = service.run_website_resolution(city, Resolver(status))
        row = conn.execute("SELECT * FROM lead_discovery_results WHERE id=433").fetchone()
        result = (summary, dict(row), conn)
        return result

    # The pre-fix ternary kept this transition pending.
    assert ("website_not_found" if "identity_review" == "not_found" else "website_lookup_pending") == "website_lookup_pending"
    summary, row, conn = exercise("identity_review")
    assert row["validation_status"] == "identity_review"
    assert row["rejection_reason"].startswith("website_resolution:identity_review:")
    service = module.DiscoveryService.__new__(module.DiscoveryService)
    service.conn, service.provider = conn, SimpleNamespace(provider_name="isolated_fixture")
    assert service.run_website_resolution({"id": 1, "city": "Saratoga Springs", "state": "NY"}, Resolver("identity_review")).results_seen == 0
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0

    _, row, conn = exercise("not_found")
    assert row["validation_status"] == "website_not_found"
    _, row, conn = exercise("network_retry")
    assert row["validation_status"] == "website_lookup_pending"
    assert row["rejection_reason"].startswith("website_resolution:network_retry:")
    _, row, conn = exercise("resolved", linked=True)
    assert row["validation_status"] == "email_extraction_pending"
    assert row["website"] == "https://merchant.example"
    assert conn.execute("SELECT official_website FROM leads WHERE id=5").fetchone()[0] == "https://merchant.example"
    print("production baseline-copy transitions: PASS (identity_review, no reselect, not_found, network_retry, linked resolved)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_production_patch.py PATH_TO_PATCHED_DISCOVERY_SERVICE")
    run(Path(sys.argv[1]).resolve())
