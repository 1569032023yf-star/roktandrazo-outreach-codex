from __future__ import annotations

import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import bd_db
from discovery.discovery_service import DiscoveryService
from discovery.models import PlaceSearchResult, ProviderPage
from discovery.providers.google_places import GooglePlacesProvider
from discovery.providers.mock_provider import MockPlacesProvider
from discovery.providers.serpapi_maps import SerpApiMapsProvider
from outreach_control import RETAIL_QUERY_FAMILIES
from retail_city_queue import activate_next_city

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("city_migration", ROOT / "migrations" / "migrate_city_outreach_40.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


def result(
    name: str,
    *,
    result_id: str,
    place_id: str | None = None,
    address: str = "1 Main St, Nashville, TN 37201",
    website: str = "https://example-retail.test",
    email: str = "hello@example-retail.test",
    status: str = "OPERATIONAL",
    primary_type: str = "store",
    types: list[str] | None = None,
) -> PlaceSearchResult:
    return PlaceSearchResult(
        provider="mock",
        provider_result_id=result_id,
        place_id=place_id or result_id,
        business_name=name,
        formatted_address=address,
        city="Nashville",
        state="TN",
        country="US",
        phone="615-555-1111",
        website=website,
        business_status=status,
        primary_type=primary_type,
        types=types or ["store", "point_of_interest"],
        source_query="toy store Nashville TN",
        raw_payload={"email": email, "evidence_snippet": email} if email else {},
    )


class MockFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def fetch(self, url: str) -> dict:
        self.requested.append(url)
        value = self.pages.get(url, "")
        if isinstance(value, dict):
            return {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                **value,
            }
        text = value
        return {
            "text": text,
            "html": text,
            "status": 200 if text else 404,
            "final_url": url,
            "tls_verified": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


class DiscoveryDb:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "discovery.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript(
            """
            CREATE TABLE leads (
                id INTEGER PRIMARY KEY,
                store_name TEXT, store_type TEXT, city TEXT, state TEXT,
                official_website TEXT, contact_page TEXT, wholesale_or_vendor_page TEXT,
                email TEXT, email_type TEXT, contact_form_url TEXT, evidence_url TEXT,
                source_keyword TEXT, source_platform TEXT, fit_reason TEXT, product_fit TEXT,
                confidence_score TEXT, status TEXT, notes TEXT, domain_hash TEXT UNIQUE,
                lead_identity_hash TEXT, email_source_type TEXT,
                email_verified_on_official_site INTEGER DEFAULT 0,
                evidence_snippet TEXT, evidence_method TEXT, review_status TEXT,
                review_reason_code TEXT, review_reason_detail TEXT, auto_sendable INTEGER DEFAULT 0,
                manual_sendable INTEGER DEFAULT 0, unsubscribed_at TEXT, bounced_at TEXT,
                email_subject TEXT, email_body TEXT, collected_at TEXT, last_checked_at TEXT
            );
            CREATE TABLE send_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, status TEXT);
            CREATE TABLE bounce_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, bounce_type TEXT);
            CREATE TABLE suppression_list (id INTEGER PRIMARY KEY, email TEXT, reason TEXT);
            """
        )
        conn.commit()
        conn.close()
        migration.migrate(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        self.conn.close()
        self.temp.cleanup()


class DiscoveryServiceTests(unittest.TestCase):
    def test_mock_provider_stages_nashville_and_saves_cursor_then_resumes(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            service = DiscoveryService(conn, provider=MockPlacesProvider())
            first = service.run_places_batch(city, max_pages=1)
            self.assertEqual(first.status, "paused_by_runtime_limit")
            self.assertEqual(first.next_page_cursor, "page2")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lead_discovery_results").fetchone()[0], 2)
            queue = conn.execute("SELECT active_query_family,page_cursor FROM retail_city_queue WHERE id=?", (city["id"],)).fetchone()
            self.assertEqual(queue["active_query_family"], RETAIL_QUERY_FAMILIES[0])
            self.assertEqual(queue["page_cursor"], "page2")

            resumed_city = activate_next_city(conn)
            second = service.run_places_batch(resumed_city, max_pages=1)
            self.assertEqual(second.status, "query_completed")
            self.assertEqual(conn.execute("SELECT page_cursor FROM lead_discovery_query_state WHERE query_family=?", (RETAIL_QUERY_FAMILIES[0],)).fetchone()[0], "")

    def test_same_place_across_query_families_updates_hits_without_new_subject(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            service = DiscoveryService(conn, provider=MockPlacesProvider())
            service.run_places_batch(city, max_pages=2)
            service.run_places_batch(activate_next_city(conn), max_pages=1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lead_discovery_results").fetchone()[0], 3)
            self.assertTrue(conn.execute("SELECT 1 FROM lead_discovery_hits WHERE query_family=?", (RETAIL_QUERY_FAMILIES[1],)).fetchone())

    def test_new_leads_are_created_only_through_bd_db_insert_lead(self):
        with DiscoveryDb() as conn:
            calls = []
            original = bd_db.insert_lead

            def spy(lead, conn=None):
                calls.append(dict(lead))
                return original(lead, conn=conn)

            bd_db.insert_lead = spy
            try:
                city = activate_next_city(conn)
                page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [result("Spy Toy Store", result_id="spy-1")])
                DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page})).run_places_batch(city)
            finally:
                bd_db.insert_lead = original
            self.assertEqual(len(calls), 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 1)

    def test_history_sent_suppression_and_hard_bounce_block_creation(self):
        cases = [
            ("send_log", "INSERT INTO send_log (email,status) VALUES ('hello@example-retail.test','sent')"),
            ("suppression", "INSERT INTO suppression_list (email,reason) VALUES ('hello@example-retail.test','manual')"),
            ("bounce", "INSERT INTO bounce_log (email,bounce_type) VALUES ('hello@example-retail.test','hard')"),
        ]
        for _, sql in cases:
            with self.subTest(sql=sql), DiscoveryDb() as conn:
                conn.execute(sql)
                city = activate_next_city(conn)
                page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [result("Blocked Toy Store", result_id=sql[:8])])
                DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page})).run_places_batch(city)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT validation_status FROM lead_discovery_results").fetchone()[0], "history_blocked")

    def test_same_business_new_email_goes_to_identity_review(self):
        with DiscoveryDb() as conn:
            conn.execute(
                """INSERT INTO leads (store_name,city,state,official_website,email,status,confidence_score,review_status,domain_hash)
                   VALUES ('Identity Toys','Nashville','TN','https://identity.example','old@identity.example','new','A','pending','identity.example')"""
            )
            city = activate_next_city(conn)
            page = ProviderPage(
                "mock",
                "toy store Nashville TN",
                "Nashville",
                "TN",
                "",
                [result("Identity Toys", result_id="identity-new", website="https://identity.example", email="new@identity.example")],
            )
            DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page})).run_places_batch(city)
            self.assertEqual(conn.execute("SELECT validation_status FROM lead_discovery_results").fetchone()[0], "identity_review")
            row = conn.execute("SELECT status,review_status FROM leads WHERE store_name='Identity Toys'").fetchone()
            self.assertEqual(row["status"], "manual_review_needed")
            self.assertEqual(row["review_status"], "identity_review")

    def test_same_domain_different_locations_are_not_globally_blocked(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            page = ProviderPage(
                "mock",
                "toy store Nashville TN",
                "Nashville",
                "TN",
                "",
                [
                    result("Chain Game Shop", result_id="chain-east", address="10 East St, Nashville, TN", website="https://chain.example", email="east@chain.example"),
                    result("Chain Game Shop", result_id="chain-west", address="20 West St, Nashville, TN", website="https://chain.example", email="west@chain.example"),
                ],
            )
            DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page})).run_places_batch(city)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 2)

    def test_closed_is_rejected_and_no_website_enters_resolution_queue(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            page = ProviderPage(
                "mock",
                "toy store Nashville TN",
                "Nashville",
                "TN",
                "",
                [
                    result("Closed Shop", result_id="closed", status="CLOSED_PERMANENTLY"),
                    result("Website Pending Shop", result_id="no-site", website="", email=""),
                ],
            )
            DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page})).run_places_batch(city)
            statuses = sorted(r[0] for r in conn.execute("SELECT validation_status FROM lead_discovery_results"))
            self.assertEqual(statuses, ["rejected", "website_lookup_pending"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 0)

    def test_provider_not_configured_and_timeout_fail_closed(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            disabled = DiscoveryService(conn, provider=MockPlacesProvider(configured=False)).run_places_batch(city)
            self.assertEqual(disabled.status, "configuration_blocked")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lead_discovery_results").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT status FROM lead_discovery_query_state LIMIT 1").fetchone()[0], "configuration_blocked")

        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            timeout_page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", status="provider_timeout", error="timeout")
            summary = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): timeout_page})).run_places_batch(city)
            self.assertEqual(summary.status, "provider_timeout")
            self.assertEqual(conn.execute("SELECT status FROM retail_city_queue WHERE city='Nashville'").fetchone()[0], "active")

    def test_configuration_blocked_query_resumes_after_provider_configured(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            disabled = DiscoveryService(conn, provider=MockPlacesProvider(configured=False)).run_places_batch(city)
            self.assertEqual(disabled.status, "configuration_blocked")
            resumed_city = activate_next_city(conn)
            page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [result("Resume Toy Store", result_id="resume-1")])
            summary = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page})).run_places_batch(resumed_city)
            self.assertIn(summary.status, {"query_completed", "places_matrix_completed_web_pending"})
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lead_discovery_results").fetchone()[0], 1)

    def test_staged_places_without_email_extracts_official_email_to_a0(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            staged = result(
                "Nashville Board Game Depot",
                result_id="post-a0",
                website="https://nashvilleboardgames.example",
                email="",
            )
            page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [staged])
            service = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page}))
            first = service.run_places_batch(city)
            self.assertEqual(first.validation_statuses.get("email_extraction_pending"), 1)
            fetcher = MockFetcher({
                "https://nashvilleboardgames.example": "<html><title>Nashville Board Game Depot</title></html>",
                "https://nashvilleboardgames.example/contact": "Nashville Board Game Depot contact: sales@nashvilleboardgames.example",
            })
            post = service.run_staging_postprocess(city, fetcher=fetcher)
            self.assertEqual(post.validation_statuses.get("lead_created"), 1)
            row = conn.execute("SELECT status,confidence_score,auto_sendable,email,evidence_url,evidence_method FROM leads").fetchone()
            self.assertEqual(row["status"], "new")
            self.assertEqual(row["confidence_score"], "A")
            self.assertEqual(row["auto_sendable"], 1)
            self.assertEqual(row["email"], "sales@nashvilleboardgames.example")
            self.assertEqual(row["evidence_method"], "official_contact_page")
            staged_row = conn.execute("SELECT id,validation_status,linked_lead_id,evidence_url,raw_payload_json FROM lead_discovery_results").fetchone()
            self.assertEqual(staged_row["validation_status"], "lead_created")
            self.assertTrue(staged_row["linked_lead_id"])
            evidence = json.loads(staged_row["raw_payload_json"])["official_email_evidence"]
            self.assertEqual(set(evidence), {
                "requested_url", "final_url", "http_status", "http_success", "tls_success",
                "fetched_at", "visible_text_excerpt", "content_hash", "email", "email_source_type",
            })
            self.assertEqual(evidence["email"], "sales@nashvilleboardgames.example")
            self.assertIn(evidence["email"], evidence["visible_text_excerpt"])
            self.assertTrue(evidence["http_success"])
            self.assertTrue(evidence["tls_success"])
            self.assertEqual(len(evidence["content_hash"]), 64)
            duplicate_id, created = service._upsert_result(city["id"], "toy store", staged)
            self.assertFalse(created)
            self.assertEqual(duplicate_id, staged_row["id"])
            replayed = json.loads(conn.execute(
                "SELECT raw_payload_json FROM lead_discovery_results WHERE id=?", (duplicate_id,)
            ).fetchone()[0])
            self.assertEqual(replayed["official_email_evidence"], evidence)

    def test_staged_places_contact_form_and_no_email_enter_review_pools(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            pages = ProviderPage(
                "mock",
                "toy store Nashville TN",
                "Nashville",
                "TN",
                "",
                [
                    result("Nashville Puzzle House", result_id="form-1", website="https://nashvillepuzzlehouse.example", email=""),
                    result("Nashville Gift Shelf", result_id="manual-1", website="https://nashvillegiftshelf.example", email=""),
                ],
            )
            service = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): pages}))
            service.run_places_batch(city)
            post = service.run_staging_postprocess(
                city,
                fetcher=MockFetcher({
                    "https://nashvillepuzzlehouse.example": "Nashville Puzzle House",
                    "https://nashvillepuzzlehouse.example/contact": "<form><textarea name='message'></textarea></form>",
                    "https://nashvillegiftshelf.example": "Nashville Gift Shelf official site",
                    "https://nashvillegiftshelf.example/about": "Nashville Gift Shelf family retail store",
                }),
            )
            self.assertEqual(post.validation_statuses.get("contact_form_pool"), 1)
            self.assertEqual(post.validation_statuses.get("manual_review_needed"), 1)
            statuses = sorted(row[0] for row in conn.execute("SELECT status FROM leads"))
            self.assertEqual(statuses, ["contact_form_pool", "manual_review_needed"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads WHERE auto_sendable=1 OR manual_sendable=1").fetchone()[0], 0)
            readable = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE status IN ('manual_review_needed','contact_form_pool') AND review_status='pending'"
            ).fetchone()[0]
            self.assertEqual(readable, 2)
            conn.execute("""CREATE TABLE IF NOT EXISTS fb_enrichment_queue (
                lead_id INTEGER, fb_check_status TEXT, facebook_url TEXT, fb_email TEXT, fb_evidence_url TEXT
            )""")
            conn.commit()
            db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
            import bd_review_server
            old_path = bd_review_server.DB_PATH
            bd_review_server.DB_PATH = db_path
            try:
                payload = json.loads(bd_review_server.api_leads({"status": ["pending"], "per_page": ["10"]}))
            finally:
                bd_review_server.DB_PATH = old_path
            review_statuses = sorted(item["lead_status"] for item in payload["leads"])
            self.assertEqual(review_statuses, ["contact_form_pool", "manual_review_needed"])

    def test_places_location_mismatch_and_missing_address_do_not_store_as_active_city(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            outside = result("Franklin Game Shop", result_id="outside-city", address="1 Main St, Franklin, TN", website="https://franklingames.example")
            outside.city = "Franklin"
            missing = result("Location Missing Shop", result_id="missing-location", website="https://missinglocation.example")
            missing.city = ""
            missing.state = ""
            page = ProviderPage("mock", "toy store Nashville TN", "Nashville", "TN", "", [outside, missing])
            summary = DiscoveryService(conn, provider=MockPlacesProvider({("toy store Nashville TN", ""): page})).run_places_batch(city)
            self.assertEqual(summary.validation_statuses.get("outside_active_city"), 1)
            self.assertEqual(summary.validation_statuses.get("location_review"), 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0], 0)

    def test_google_places_normalizes_actual_address_fields(self):
        provider = GooglePlacesProvider(api_key="test-key")
        place = provider._normalize_place(
            {
                "id": "places/abc",
                "displayName": {"text": "Franklin Game Shop"},
                "formattedAddress": "1 Main St, Franklin, TN 37064, USA",
                "googleMapsUri": "https://maps.google.com/?cid=abc",
                "addressComponents": [
                    {"longText": "Franklin", "shortText": "Franklin", "types": ["locality"]},
                    {"longText": "Tennessee", "shortText": "TN", "types": ["administrative_area_level_1"]},
                    {"longText": "37064", "shortText": "37064", "types": ["postal_code"]},
                    {"longText": "United States", "shortText": "US", "types": ["country"]},
                ],
            },
            "toy store Nashville TN",
            "Nashville",
            "TN",
            "",
        )
        self.assertEqual((place.city, place.state, place.postal_code, place.country), ("Franklin", "TN", "37064", "US"))
        self.assertEqual(place.source_url, "https://maps.google.com/?cid=abc")

    def test_serpapi_maps_is_fail_closed_experimental_disabled(self):
        page = SerpApiMapsProvider(api_key="test").search_places("toy store Nashville TN", "Nashville", "TN")
        self.assertEqual(page.status, "experimental_disabled")
        self.assertFalse(page.ok)

    def test_get_sendable_leads_requires_auto_flag_and_blocks_manual_bounce_suppression_sent(self):
        blockers = [
            ("auto_missing", "UPDATE leads SET auto_sendable=0"),
            ("unsubscribed", "UPDATE leads SET unsubscribed_at='2026-07-23T00:00:00'"),
            ("suppressed", "INSERT INTO suppression_list (email,reason) VALUES ('safe@example-retail.test','manual')"),
            ("manual_queue", "INSERT INTO manual_send_queue (lead_id,status,approved_at,reviewer) VALUES (1,'approved','now','tester')"),
            ("hard_bounce", "INSERT INTO bounce_log (lead_id,email,bounce_type) VALUES (1,'safe@example-retail.test','hard')"),
            ("sent_history", "INSERT INTO send_log (lead_id,email,status,message_type) VALUES (1,'safe@example-retail.test','sent','new_outreach')"),
        ]
        for name, sql in blockers:
            with self.subTest(name=name), DiscoveryDb() as conn:
                conn.execute(
                    """INSERT INTO leads
                       (id,store_name,city,state,official_website,email,status,confidence_score,
                        email_verified_on_official_site,email_source_type,evidence_url,evidence_snippet,
                        evidence_method,auto_sendable,email_subject,email_body,collected_at)
                       VALUES (1,'Safe Store','Nashville','TN','https://example-retail.test',
                        'safe@example-retail.test','new','A',1,'official_page_visible',
                        'https://example-retail.test/contact','safe@example-retail.test',
                        'official_contact_page',1,'Hello','Body','2026-07-23T00:00:00')"""
                )
                self.assertEqual(len(bd_db.get_sendable_leads(limit=10, conn=conn)), 1)
                conn.execute(sql)
                self.assertEqual(bd_db.get_sendable_leads(limit=10, conn=conn), [])

    def test_import_bd_db_does_not_create_or_write_database(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "import_side_effect.db"
            env = os.environ.copy()
            env["WORKBUDDY_BD_DB_PATH"] = str(db_path)
            env["PYTHONPATH"] = str(ROOT)
            proc = subprocess.run(
                [sys.executable, "-c", "import os, pathlib, bd_db; print(pathlib.Path(os.environ['WORKBUDDY_BD_DB_PATH']).exists())"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(proc.stdout.strip(), "False")

    def test_city_does_not_switch_until_current_city_is_complete(self):
        with DiscoveryDb() as conn:
            first = activate_next_city(conn)
            second = activate_next_city(conn)
            self.assertEqual(first["city"], "Nashville")
            self.assertEqual(second["city"], "Nashville")

    def test_places_completed_with_web_provider_missing_is_not_exhausted(self):
        with DiscoveryDb() as conn:
            city = activate_next_city(conn)
            empty_pages = {
                (f"{family} Nashville TN", ""): ProviderPage("mock", f"{family} Nashville TN", "Nashville", "TN", "", [])
                for family in RETAIL_QUERY_FAMILIES
            }
            service = DiscoveryService(conn, provider=MockPlacesProvider(empty_pages))
            for _ in RETAIL_QUERY_FAMILIES:
                service.run_places_batch(activate_next_city(conn))
            status = conn.execute("SELECT status FROM retail_city_queue WHERE city='Nashville'").fetchone()[0]
            self.assertEqual(status, "places_matrix_completed_web_pending")
            self.assertNotEqual(status, "search_matrix_exhausted")

    def test_inventory_stage_has_no_smtp_reference(self):
        text = (ROOT / "bd_orchestrator.py").read_text(encoding="utf-8")
        inventory = text.split("def stage_inventory", 1)[1].split("def stage_end_of_day", 1)[0]
        self.assertNotIn("log_send(", inventory)
        self.assertNotIn("send_email", inventory)

    def test_static_scan_fails_on_unauthorized_direct_lead_inserts(self):
        pattern = re.compile(r"INSERT\s+(?:OR\s+IGNORE\s+|OR\s+REPLACE\s+)?INTO\s+leads\b(?!_)", re.IGNORECASE)
        # 非生产目录（历史/备份/归档/迁移/输出）不参与扫描；生产代码直写 leads 必须走 require_legacy_lead_insert_approval
        non_production_dirs = {"tests", "backup", "backups", "data", "migrations",
                               "output", "_archived_scripts", "_audit_quarantine", "_retired",
                               "audit_evidence", ".workbuddy", "discovery"}
        unauthorized = []
        for path in ROOT.rglob("*.py"):
            rel = path.relative_to(ROOT)
            if rel.parts and rel.parts[0] in non_production_dirs or path.name == "bd_db.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if pattern.search(text) and "require_legacy_lead_insert_approval" not in text:
                unauthorized.append(str(rel))
        self.assertEqual(unauthorized, [])


if __name__ == "__main__":
    unittest.main()
