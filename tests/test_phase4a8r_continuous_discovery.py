"""Continuous bounded discovery / 库存达标后的有界持续发现。"""
from contextlib import ExitStack, contextmanager
import os
import sqlite3
import unittest
from unittest.mock import Mock, patch

import bd_orchestrator as orchestrator
from discovery.discovery_service import DiscoveryRunSummary, DiscoveryService
from discovery.models import ProviderPage
from discovery.providers.mock_provider import MockPlacesProvider
from tests.test_discovery_service import DiscoveryDb
from tests import test_phase4a7_city_queue_advancement as city_tests


class ContinuousDiscoveryTests(unittest.TestCase):
    @contextmanager
    def stage(self, conn, safe=50, target=50, lock=True, summary=None, error=None,
              state="TN", actual_service=None):
        path = conn.execute("PRAGMA database_list").fetchone()[2]
        def connect():
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            return db
        service = actual_service or Mock()
        if actual_service is None:
            service.provider.provider_name = "browser_maps"
            service.run_places_batch.return_value = summary or DiscoveryRunSummary(status="query_completed")
            service.run_places_batch.side_effect = error
            service.run_website_resolution.return_value = DiscoveryRunSummary(status="completed")
            service.run_staging_postprocess.return_value = DiscoveryRunSummary(status="completed")
            service.run_linked_backlog.return_value = {}
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"WORKBUDDY_DISCOVERY_MAX_PAGES": "3"}))
            stack.enter_context(patch.object(orchestrator, "get_db", side_effect=connect))
            stack.enter_context(patch.object(orchestrator, "inventory_target_for_date", return_value=target))
            stack.enter_context(patch.object(orchestrator, "_count_safe_ready_pool", return_value=safe))
            stack.enter_context(patch.object(orchestrator, "_count_broad_ready_pool", return_value=0))
            stack.enter_context(patch.object(orchestrator, "get_sendable_leads", return_value=[]))
            stack.enter_context(patch.object(orchestrator, "_resolve_active_discovery_state", return_value=(state, None)))
            for name in ("set_execution_mode", "update_job_run", "header"):
                stack.enter_context(patch.object(orchestrator, name))
            acquired = stack.enter_context(patch.object(orchestrator, "acquire_run_lock", return_value=lock))
            released = stack.enter_context(patch.object(orchestrator, "release_run_lock"))
            finish = stack.enter_context(patch.object(orchestrator, "finish_job_run"))
            logs = stack.enter_context(patch.object(orchestrator, "log"))
            constructor = stack.enter_context(patch("discovery.discovery_service.DiscoveryService", return_value=service))
            # Resolver construction cannot contact a provider; all lanes are fixtures.
            stack.enter_context(patch("discovery.website_resolver.ProviderWebsiteResolver"))
            yield service, finish, acquired, released, logs, constructor

    def test_inventory_targets_never_skip_discovery(self):
        for safe, target in ((49, 50), (50, 50), (51, 50), (59, 60), (60, 60)):
            with self.subTest(safe=safe, target=target), DiscoveryDb() as conn:
                with self.stage(conn, safe=safe, target=target) as (service, finish, _, released, logs, _):
                    outcome = orchestrator.stage_inventory("fixture", "2026-10-13", False)
                    self.assertEqual(outcome, safe >= target)
                    service.run_places_batch.assert_called_once()
                    self.assertEqual(service.run_places_batch.call_args.kwargs["max_pages"], 3)
                    service.run_website_resolution.assert_called_once()
                    service.run_staging_postprocess.assert_called_once()
                    service.run_linked_backlog.assert_called_once()
                    self.assertTrue(service.run_website_resolution.call_args.kwargs["unlinked_only"])
                    self.assertTrue(service.run_staging_postprocess.call_args.kwargs["unlinked_only"])
                    self.assertEqual(finish.call_args.kwargs["gap"], max(0, target - safe))
                    self.assertEqual(finish.call_args.args[1], "completed" if safe >= target else "partial")
                    released.assert_called_once()
                    messages = [call.args[0] for call in logs.call_args_list]
                    self.assertTrue(any("DISCOVERY_PATH_EXECUTED=true" in message for message in messages))
                    self.assertTrue(any(f"INVENTORY_TARGET_MET={str(safe >= target).lower()}" in message for message in messages))

    def test_provider_exception_stops_and_releases_lock(self):
        with DiscoveryDb() as conn, self.stage(conn, error=TimeoutError("fixture")) as (service, finish, _, released, _, _):
            with self.assertRaises(TimeoutError):
                orchestrator.stage_inventory("fixture", "2026-10-13", False)
            self.assertEqual(finish.call_args.args[1], "stopped")
            released.assert_called_once()
            service.run_website_resolution.assert_not_called()

    def test_provider_error_summary_cannot_be_target_success(self):
        for status in ("provider_timeout", "configuration_blocked", "quota_exceeded", "unknown_provider_status"):
            with self.subTest(status=status), DiscoveryDb() as conn:
                summary = DiscoveryRunSummary(status=status, provider_errors=1, error="fixture")
                with self.stage(conn, summary=summary) as (service, finish, _, released, _, _):
                    self.assertFalse(orchestrator.stage_inventory("fixture", "2026-10-13", False))
                    self.assertEqual(finish.call_args.args[1], "stopped")
                    self.assertEqual(finish.call_args.kwargs["stop_reason"], f"discovery_provider_error:{status}")
                    service.run_website_resolution.assert_not_called()
                    service.run_linked_backlog.assert_not_called()
                    released.assert_called_once()

    def test_lock_conflict_never_constructs_provider(self):
        with DiscoveryDb() as conn, self.stage(conn, lock=False) as (service, finish, _, released, _, constructor):
            self.assertFalse(orchestrator.stage_inventory("fixture", "2026-10-13", False))
            constructor.assert_not_called()
            service.run_places_batch.assert_not_called()
            released.assert_not_called()
            self.assertEqual(finish.call_args.kwargs["stop_reason"], "lock_conflict")

    def test_dry_run_never_constructs_provider_or_acquires_lock(self):
        with DiscoveryDb() as conn, self.stage(conn) as (service, finish, acquired, released, _, constructor):
            result = orchestrator.stage_inventory("fixture", "2026-10-13", True)
            self.assertEqual(result["gap"], 0)
            constructor.assert_not_called()
            service.run_places_batch.assert_not_called()
            acquired.assert_not_called()
            released.assert_not_called()
            finish.assert_not_called()

    def test_page_budget_is_capped_at_three(self):
        for value, expected in (("1", 1), ("3", 3), ("100", 3), ("0", 1)):
            with self.subTest(value=value), DiscoveryDb() as conn, self.stage(conn) as (service, *_):
                with patch.dict(os.environ, {"WORKBUDDY_DISCOVERY_MAX_PAGES": value}):
                    orchestrator.stage_inventory("fixture", "2026-10-13", False)
                service.run_places_batch.assert_called_once()
                self.assertEqual(service.run_places_batch.call_args.kwargs["max_pages"], expected)

    def test_invalid_budget_fails_before_discovery_execution(self):
        with DiscoveryDb() as conn, self.stage(conn) as (service, finish, _, released, logs, _):
            with patch.dict(os.environ, {"WORKBUDDY_DISCOVERY_MAX_PAGES": "invalid"}):
                with self.assertRaises(ValueError):
                    orchestrator.stage_inventory("fixture", "2026-10-13", False)
            service.run_places_batch.assert_not_called()
            self.assertEqual(finish.call_args.args[1], "stopped")
            released.assert_called_once()
            self.assertFalse(any("DISCOVERY_PATH_EXECUTED=true" in call.args[0] for call in logs.call_args_list))

    def test_real_provider_failure_preserves_cursor_then_resumes(self):
        with DiscoveryDb() as conn:
            from retail_city_queue import activate_next_city
            city = activate_next_city(conn, state="TN")
            query = "toy store Nashville TN"
            page = ProviderPage("mock", query, "Nashville", "TN", "resume-token",
                                status="provider_timeout", error="fixture")
            provider = MockPlacesProvider({(query, "resume-token"): page})
            service = DiscoveryService(conn, provider=provider)
            conn.execute("""INSERT INTO lead_discovery_query_state
                (active_city_id, provider, query_family, query_text, status, page_cursor)
                VALUES (?, 'mock', 'toy store', ?, 'running', 'resume-token')""", (city["id"], query))
            conn.commit()
            with self.stage(conn, actual_service=service) as (_, finish, *_):
                self.assertFalse(orchestrator.stage_inventory("fixture", "2026-10-13", False))
                self.assertEqual(finish.call_args.args[1], "stopped")
            row = conn.execute("SELECT status,page_cursor FROM lead_discovery_query_state WHERE active_city_id=? AND query_family='toy store'", (city["id"],)).fetchone()
            self.assertEqual(tuple(row), ("provider_timeout", "resume-token"))
            self.assertNotEqual(conn.execute("SELECT status FROM retail_city_queue WHERE id=?", (city["id"],)).fetchone()[0], "search_matrix_exhausted")
            page.status, page.error = "ok", ""
            with patch.object(provider, "search_places", wraps=provider.search_places) as search:
                resumed = service.run_places_batch(city, max_pages=3)
                self.assertEqual(resumed.status, "query_completed")
                self.assertEqual(search.call_args.args[3], "resume-token")

    def test_city_advances_only_with_durable_exhaustion(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                fixture = city_tests.CityQueueAdvancementTests()
                fixture.setUp()
                try:
                    if completed:
                        fixture._complete_query_matrix()
                    with self.stage(fixture.conn, state="NY") as (service, *_):
                        orchestrator.stage_inventory("fixture", "2026-10-13", False)
                        self.assertEqual(service.run_places_batch.call_args.args[0]["city"],
                                         "Saratoga Springs" if completed else "Ithaca")
                finally:
                    fixture.tearDown()
