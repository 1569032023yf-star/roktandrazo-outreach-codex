"""Phase 4A.7: fail-closed city terminalization and next-city activation."""
from __future__ import annotations

import ast
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

from outreach_control import RETAIL_QUERY_FAMILIES
from retail_city_queue import (
    NY_FIRST_ROUND_CITIES,
    activate_next_city,
    city_completion_checks,
    complete_active_city_if_exhausted,
    seed_state_cities,
)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("city_migration", ROOT / "migrations" / "migrate_city_outreach_40.py")
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(migration)


class CityQueueAdvancementTests(unittest.TestCase):
    provider = "browser_maps"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "phase4a7.db"
        conn = sqlite3.connect(self.db)
        conn.execute("""CREATE TABLE leads (
            id INTEGER PRIMARY KEY, email TEXT, status TEXT, review_status TEXT,
            review_reason_code TEXT, review_reason_detail TEXT
        )""")
        conn.execute("CREATE TABLE send_log (id INTEGER PRIMARY KEY, status TEXT)")
        conn.commit()
        conn.close()
        migration.migrate(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        seed_state_cities(self.conn, "NY", NY_FIRST_ROUND_CITIES)
        self.city = activate_next_city(self.conn, state="NY")
        self.conn.execute(
            "UPDATE retail_city_queue SET web_directory_status='web_directory_provider_not_configured' WHERE id=?",
            (self.city["id"],),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def _complete_query_matrix(self):
        for family in RETAIL_QUERY_FAMILIES:
            self.conn.execute(
                """INSERT INTO lead_discovery_query_state
                   (active_city_id, provider, query_family, query_text, status, completed_at)
                   VALUES (?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)""",
                (self.city["id"], self.provider, family, f"{family} Ithaca NY"),
            )
        self.conn.commit()

    def _record_three_empty_batches(self):
        for _ in range(3):
            self.conn.execute(
                """INSERT INTO provider_request_audit
                   (active_city_id, provider, status, result_count, request_count, requested_at)
                   VALUES (?, ?, 'ok', 0, 1, CURRENT_TIMESTAMP)""",
                (self.city["id"], self.provider),
            )
        self.conn.commit()

    def _insert_discovery(self, status: str, rejection_reason: str = "", linked_lead_id: int | None = None):
        self.conn.execute(
            """INSERT INTO lead_discovery_results
               (provider, business_name, active_city_id, discovered_at, last_seen_at,
                validation_status, rejection_reason, linked_lead_id)
               VALUES (?, 'Queue Test Shop', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?)""",
            (self.provider, self.city["id"], status, rejection_reason, linked_lead_id),
        )
        self.conn.commit()

    def test_productive_active_city_stays_active(self):
        # No completed matrix is durable evidence of outstanding productive work.
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))
        self.assertEqual(activate_next_city(self.conn, state="NY")["city"], "Ithaca")

    def test_pending_query_family_prevents_completion(self):
        self._complete_query_matrix()
        self.conn.execute(
            """UPDATE lead_discovery_query_state SET status='pending'
               WHERE active_city_id=? AND query_family=?""",
            (self.city["id"], RETAIL_QUERY_FAMILIES[0]),
        )
        self.conn.commit()
        self.assertFalse(city_completion_checks(self.conn, self.city["id"], self.provider)["all_query_families"])
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))

    def test_retryable_network_row_prevents_completion(self):
        self._complete_query_matrix()
        self._insert_discovery("lead_created", "website_resolution:network_retry:TimeoutError")
        checks = city_completion_checks(self.conn, self.city["id"], self.provider)
        self.assertFalse(checks["no_unprocessed_candidates"])
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))

    def test_unprocessed_staging_row_prevents_completion(self):
        self._complete_query_matrix()
        self._insert_discovery("email_extraction_pending")
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))

    def test_linked_backlog_retry_prevents_completion_without_lead_mutation(self):
        self._complete_query_matrix()
        self.conn.execute(
            """INSERT INTO leads (id, email, status, review_status, review_reason_code, review_reason_detail)
               VALUES (9001, '', 'manual_review_needed', 'pending',
                       'review_recovery', 'review_recovery=official_site_unavailable')"""
        )
        self.conn.commit()
        self._insert_discovery("manual_review_needed", linked_lead_id=9001)
        lead_before = tuple(self.conn.execute("SELECT id, email FROM leads WHERE id=9001").fetchone())
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))
        self.assertEqual(tuple(self.conn.execute("SELECT id, email FROM leads WHERE id=9001").fetchone()), lead_before)

    def test_terminal_manual_review_does_not_pin_exhausted_city(self):
        self._complete_query_matrix()
        self._record_three_empty_batches()
        self.conn.execute(
            """INSERT INTO leads (id, email, status, review_reason_code)
               VALUES (9002, 'already-checked@example.test', 'manual_review_needed', 'hygiene_failed')"""
        )
        self._insert_discovery("manual_review_needed", linked_lead_id=9002)
        checks = city_completion_checks(self.conn, self.city["id"], self.provider)
        self.assertTrue(checks["all_candidates_classified"])
        self.assertTrue(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))

    def test_last_three_empty_batches_is_independent_persisted_evidence(self):
        self._complete_query_matrix()
        before = city_completion_checks(self.conn, self.city["id"], self.provider)
        self.assertTrue(before["all_query_families"])
        self.assertTrue(before["two_empty_pages"])
        self.assertFalse(before["last_three_batches_empty"])
        self._record_three_empty_batches()
        self.assertTrue(city_completion_checks(self.conn, self.city["id"], self.provider)["last_three_batches_empty"])

    def test_genuinely_exhausted_city_terminalizes_then_next_ny_city_activates(self):
        self._complete_query_matrix()
        self._record_three_empty_batches()
        self.assertTrue(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))
        terminal = self.conn.execute("SELECT status, completion_reason FROM retail_city_queue WHERE id=?", (self.city["id"],)).fetchone()
        self.assertEqual(tuple(terminal), ("search_matrix_exhausted", "search_matrix_exhausted"))
        self.assertEqual(activate_next_city(self.conn, state="NY")["city"], "Saratoga Springs")

    def test_inventory_wires_existing_completion_before_and_after_work(self):
        tree = ast.parse((ROOT / "bd_orchestrator.py").read_text(encoding="utf-8"))
        stage = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "stage_inventory")
        calls = [node for node in ast.walk(stage) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "complete_active_city_if_exhausted"]
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
