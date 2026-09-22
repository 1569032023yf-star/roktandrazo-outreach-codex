"""Phase 4A.8D access-unreachable deferment / 自动恢复不可达延后。"""
from __future__ import annotations

import json
import urllib.error
import unittest
from unittest.mock import Mock, patch

from discovery.discovery_service import BrowserFallbackWebsiteFetcher
from retail_city_queue import (
    activate_next_city,
    city_completion_checks,
    complete_active_city_if_exhausted,
)
from tests.test_discovery_service import DiscoveryDb
from tests.test_phase4a1b_linked_backlog import LinkedBacklogTests
from tests.test_phase4a7_city_queue_advancement import CityQueueAdvancementTests


class _ForbiddenStatic:
    timeout_seconds = 1

    def fetch(self, url):
        raise urllib.error.HTTPError(url, 403, "forbidden", {}, None)


class _StaticOnlyFailure:
    last_site_automation_recovery_exhausted = False

    def fetch(self, _url):
        raise urllib.error.HTTPError("https://example.test", 403, "forbidden", {}, None)


class _Http400Static:
    timeout_seconds = 1

    def fetch(self, url):
        raise urllib.error.HTTPError(url, 400, "bad request", {}, None)


def _browser_page(url: str, status: int, text: str) -> dict:
    return {
        "status": status,
        "final_url": url,
        "tls_verified": True,
        "text": text,
        "html": f"<title>Nashville Board Game Depot</title><p>{text}</p>",
        "fetched_at": "2026-09-22T00:00:00+00:00",
        "fetch_transport": "browser_fallback",
    }


class AccessUnreachableRuntimeTests(unittest.TestCase):
    def _case(self, conn):
        service, city, row, _fetch, lead_id = LinkedBacklogTests().setup_case(conn)
        conn.execute(
            "UPDATE leads SET review_reason_code='review_recovery',"
            "review_reason_detail='review_recovery=official_site_unavailable' WHERE id=?", (lead_id,)
        )
        conn.execute("UPDATE lead_discovery_results SET validation_status='review_recovery' WHERE id=?", (row["id"],))
        return service, city, row, lead_id

    def _browser_fetcher(self, row, status=403, text="Access denied"):
        fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=_ForbiddenStatic(), page_timeout_seconds=1, site_timeout_seconds=1)
        fetcher._browser_fetch = Mock(return_value=_browser_page(row["website"], status, text))
        return fetcher

    def test_static_plus_browser_access_failure_is_deferred_not_factual_terminal(self):
        with DiscoveryDb() as conn:
            service, city, row, lead_id = self._case(conn)
            summary = service.run_linked_backlog(city, Mock(), fetcher=self._browser_fetcher(row))
            self.assertEqual(summary["automation_deferred"], 1)
            stored = conn.execute("SELECT validation_status,raw_payload_json FROM lead_discovery_results WHERE id=?", (row["id"],)).fetchone()
            retry = json.loads(stored["raw_payload_json"])["linked_backlog_retry"]
            self.assertEqual(retry["automation_terminal_outcome"], "access_unreachable")
            self.assertIn("automation_terminal_at", retry)
            self.assertEqual(stored["validation_status"], "review_recovery")
            lead = conn.execute("SELECT email,status,email_verified_on_official_site FROM leads WHERE id=?", (lead_id,)).fetchone()
            self.assertEqual(tuple(lead), ("", "manual_review_needed", 0))
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=self._browser_fetcher(row))["processed"], 0)

    def test_canonical_none_fetcher_shares_recovery_state_and_defers(self):
        """The canonical production call must not lose its locally-made fetcher."""
        with DiscoveryDb() as conn:
            service, city, row, lead_id = self._case(conn)
            shared = self._browser_fetcher(row)
            with patch("discovery.discovery_service.BrowserFallbackWebsiteFetcher", return_value=shared) as factory:
                summary = service.run_linked_backlog(city, Mock(), fetcher=None)
                self.assertEqual(factory.call_count, 1)
            self.assertEqual(summary["automation_deferred"], 1)
            retry = json.loads(conn.execute(
                "SELECT raw_payload_json FROM lead_discovery_results WHERE id=?", (row["id"],)
            ).fetchone()[0])["linked_backlog_retry"]
            self.assertEqual(retry["automation_terminal_outcome"], "access_unreachable")
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=None)["processed"], 0)
            lead = conn.execute("SELECT email,status,email_verified_on_official_site FROM leads WHERE id=?", (lead_id,)).fetchone()
            self.assertEqual(tuple(lead), ("", "manual_review_needed", 0))

    def test_transient_and_static_only_failures_remain_automatic_retry_work(self):
        with DiscoveryDb() as conn:
            service, city, row, _lead_id = self._case(conn)
            transient = service.run_linked_backlog(city, Mock(), fetcher=_StaticOnlyFailure())
            self.assertEqual(transient["automation_deferred"], 0)
            retry = json.loads(conn.execute("SELECT raw_payload_json FROM lead_discovery_results WHERE id=?", (row["id"],)).fetchone()[0])["linked_backlog_retry"]
            self.assertNotIn("automation_terminal_outcome", retry)
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=_StaticOnlyFailure())["processed"], 1)

    def test_http400_plus_bounded_compatibility_browser_failure_defers_without_email_fact(self):
        with DiscoveryDb() as conn:
            service, city, row, lead_id = self._case(conn)
            stored_url = "http://www.shop.example"
            conn.execute("UPDATE leads SET official_website=? WHERE id=?", (stored_url, lead_id))
            conn.execute("UPDATE lead_discovery_results SET website=? WHERE id=?", (stored_url, row["id"]))
            fetcher = BrowserFallbackWebsiteFetcher(static_fetcher=_Http400Static(), page_timeout_seconds=1, site_timeout_seconds=1)
            fetcher._browser_fetch = Mock(side_effect=TimeoutError("bounded browser timeout"))
            summary = service.run_linked_backlog(city, Mock(), fetcher=fetcher)
            self.assertEqual(summary["automation_deferred"], 1)
            self.assertGreaterEqual(fetcher._browser_fetch.call_count, 1)
            payload = json.loads(conn.execute(
                "SELECT raw_payload_json FROM lead_discovery_results WHERE id=?", (row["id"],)
            ).fetchone()[0])
            self.assertEqual(payload["linked_backlog_retry"]["automation_terminal_outcome"], "access_unreachable")
            lead = conn.execute("SELECT email,status,email_verified_on_official_site FROM leads WHERE id=?", (lead_id,)).fetchone()
            self.assertEqual(tuple(lead), ("", "manual_review_needed", 0))
            self.assertEqual(service.run_linked_backlog(city, Mock(), fetcher=fetcher)["processed"], 0)

    def test_browser_success_uses_normal_evidence_path_and_is_not_deferred(self):
        with DiscoveryDb() as conn:
            service, city, row, lead_id = self._case(conn)
            fetcher = self._browser_fetcher(row, 200, "Nashville Board Game Depot sales@example-retail.test")
            summary = service.run_linked_backlog(city, Mock(), fetcher=fetcher)
            self.assertEqual(summary["automation_deferred"], 0)
            # The fixture domain intentionally fails downstream hygiene, but
            # browser success must still take the normal evidence path rather
            # than the access-unreachable path.
            payload = json.loads(conn.execute("SELECT raw_payload_json FROM lead_discovery_results WHERE id=?", (row["id"],)).fetchone()[0])
            self.assertEqual(payload["official_email_evidence"]["email"], "sales@example-retail.test")
            retry = payload.get("linked_backlog_retry", {})
            self.assertNotIn("automation_terminal_outcome", retry)


class AccessUnreachableCityCompletionTests(CityQueueAdvancementTests):
    def _deferred_linked_row(self, lead_id: int = 9100):
        self.conn.execute(
            """INSERT INTO leads (id,email,status,review_status,review_reason_code,review_reason_detail)
               VALUES (?, '', 'manual_review_needed', 'pending',
                       'review_recovery', 'review_recovery=official_site_unavailable')""", (lead_id,)
        )
        self._insert_discovery("review_recovery", linked_lead_id=lead_id)
        row_id = self.conn.execute("SELECT max(id) FROM lead_discovery_results").fetchone()[0]
        payload = {"linked_backlog_retry": {
            "attempts": 3,
            "last_attempt_at": "2026-09-22T00:00:00+00:00",
            "automation_terminal_outcome": "access_unreachable",
            "automation_terminal_at": "2026-09-22T00:01:00+00:00",
        }}
        self.conn.execute("UPDATE lead_discovery_results SET raw_payload_json=? WHERE id=?", (json.dumps(payload), row_id))
        self.conn.commit()
        return row_id

    def test_only_deferred_rows_allow_city_completion_and_next_city(self):
        self._complete_query_matrix()
        self._deferred_linked_row()
        checks = city_completion_checks(self.conn, self.city["id"], self.provider)
        self.assertTrue(all(checks.values()))
        self.assertTrue(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))
        self.assertEqual(activate_next_city(self.conn, state="NY")["city"], "Saratoga Springs")
        lead = self.conn.execute("SELECT email,status FROM leads WHERE id=9100").fetchone()
        self.assertEqual(tuple(lead), ("", "manual_review_needed"))

    def test_new_legitimate_retry_still_blocks_city_after_deferment(self):
        self._complete_query_matrix()
        self._deferred_linked_row()
        self._insert_discovery("website_lookup_pending")
        checks = city_completion_checks(self.conn, self.city["id"], self.provider)
        self.assertFalse(checks["review_recovery"])
        self.assertFalse(complete_active_city_if_exhausted(self.conn, self.provider, state="NY"))


if __name__ == "__main__":
    unittest.main()
