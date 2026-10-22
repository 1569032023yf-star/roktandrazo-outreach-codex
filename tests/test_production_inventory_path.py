"""Exact production-byte AST diagnosis / 精确生产字节AST隔离诊断。

Synthetic evidence only: never proves an actual production invocation.
仅合成路径证据，不证明真实生产执行；不导入业务模块、不访问数据库或网络。
"""
import ast
from contextlib import contextmanager
import os
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

from tools.reconstruct_production_orchestrator import reconstruct, SOURCE_SHA256


def isolated_functions():
    tree = ast.parse(reconstruct().decode("utf-8"))
    names = {"US_STATE_CODES", "_resolve_active_discovery_state", "stage_inventory"}
    body = [node for node in tree.body if
            isinstance(node, ast.FunctionDef) and node.name in names or
            isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    namespace = {"os": os}
    exec(compile(ast.Module(body=body, type_ignores=[]),
                 "<git-production-" + SOURCE_SHA256 + ">", "exec"), namespace)
    return namespace


@contextmanager
def fixture(*, state="NY", safe=56, summary_status="query_completed", error=None):
    ns = isolated_functions()
    calls = []
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = [0]
    service = Mock()
    service.provider.provider_name = "fixture"
    for method in ("run_places_batch", "run_website_resolution", "run_staging_postprocess", "run_linked_backlog"):
        def invoke(*args, _method=method, **kwargs):
            calls.append((_method, args, kwargs))
            if error and _method == "run_places_batch":
                raise error
            return types.SimpleNamespace(status=summary_status, provider_errors=0,
                                         error="", results_seen=0, new_unique_places=0)
        getattr(service, method).side_effect = invoke
    queue = types.ModuleType("retail_city_queue")
    queue.seed_default_queue = Mock()
    queue.complete_active_city_if_exhausted = Mock(return_value=False)
    queue.activate_next_city = Mock(side_effect=lambda connection, *, state:
                                   {"city": "Fixture " + state, "state": state, "id": 1})
    discovery = types.ModuleType("discovery.discovery_service")
    discovery.DiscoveryService = Mock(return_value=service)
    resolver = types.ModuleType("discovery.website_resolver")
    resolver.ProviderWebsiteResolver = Mock()
    db = types.ModuleType("bd_db")
    db.get_config = Mock(return_value=state)
    ns.update({"inventory_target_for_date": Mock(return_value=50),
               "get_db": Mock(return_value=conn),
               "_count_safe_ready_pool": Mock(return_value=safe),
               "_count_broad_ready_pool": Mock(return_value=0),
               "get_sendable_leads": Mock(return_value=[]),
               **{name: Mock() for name in ("header", "log", "set_execution_mode", "update_job_run",
                                           "finish_job_run", "release_run_lock")},
               "acquire_run_lock": Mock(return_value=True)})
    modules = {"retail_city_queue": queue, "discovery.discovery_service": discovery,
               "discovery.website_resolver": resolver, "bd_db": db}
    with patch.dict("sys.modules", modules), patch.dict(os.environ,
            {"WORKBUDDY_DISCOVERY_MAX_PAGES": "3", "WORKBUDDY_WEBSITE_RESOLUTION_MAX": "20",
             "WORKBUDDY_STAGING_POSTPROCESS_MAX": "20"}):
        yield ns, calls, queue, service, conn


class ProductionInventoryPathTests(unittest.TestCase):
    def test_safe_56_still_calls_every_discovery_lane_in_order(self):
        with fixture() as (ns, calls, queue, service, conn):
            self.assertTrue(ns["stage_inventory"]("fixture-run", "2026-10-22", False))
            self.assertEqual([call[0] for call in calls], ["run_places_batch", "run_website_resolution",
                                                         "run_staging_postprocess", "run_linked_backlog"])
            self.assertEqual(calls[0][2]["max_pages"], 3)
            self.assertEqual(queue.complete_active_city_if_exhausted.call_count, 2)
            self.assertEqual(ns["finish_job_run"].call_args.kwargs["stop_reason"], "target_met")
            self.assertEqual(ns["finish_job_run"].call_args.kwargs["actual"], 56)
            conn.close.assert_called_once()
            ns["release_run_lock"].assert_called_once()

    def test_non_ny_active_state_is_passed_to_activation_and_completion(self):
        with fixture(state="TN") as (ns, calls, queue, service, _):
            ns["stage_inventory"]("fixture-run", "2026-10-22", False)
            queue.activate_next_city.assert_called_once()
            self.assertEqual(queue.activate_next_city.call_args.kwargs["state"], "TN")
            self.assertTrue(all(call.kwargs["state"] == "TN"
                                for call in queue.complete_active_city_if_exhausted.call_args_list))
            self.assertTrue(all(call[1][0]["state"] == "TN" for call in calls))

    def test_missing_or_invalid_active_state_stops_before_database_and_discovery(self):
        for state, reason in (("", "ACTIVE_STATE_NOT_SET"), ("ZZ", "ACTIVE_STATE_INVALID")):
            with self.subTest(state=state), fixture(state=state) as (ns, calls, _, _, _):
                self.assertFalse(ns["stage_inventory"]("fixture-run", "2026-10-22", False))
                ns["get_db"].assert_not_called()
                self.assertEqual(calls, [])
                self.assertEqual(ns["finish_job_run"].call_args.kwargs["stop_reason"], reason)
                ns["release_run_lock"].assert_called_once()

    def test_programming_exception_is_stopped_and_reraised_not_target_met(self):
        with fixture(error=ValueError("fixture-programming-error")) as (ns, calls, _, _, conn):
            with self.assertRaisesRegex(ValueError, "fixture-programming-error"):
                ns["stage_inventory"]("fixture-run", "2026-10-22", False)
            self.assertEqual([call[0] for call in calls], ["run_places_batch"])
            self.assertEqual(ns["finish_job_run"].call_args.kwargs["stop_reason"],
                             "linked_backlog_error:ValueError")
            ns["release_run_lock"].assert_called_once()
            conn.close.assert_called_once()

    def test_error_summary_stops_even_when_safe_target_is_met(self):
        with fixture(summary_status="configuration_blocked") as (ns, calls, _, _, _):
            self.assertFalse(ns["stage_inventory"]("fixture-run", "2026-10-22", False))
            self.assertEqual([call[0] for call in calls], ["run_places_batch"])
            self.assertEqual(ns["finish_job_run"].call_args.kwargs["stop_reason"],
                             "discovery_provider_error:configuration_blocked")

    def test_lock_conflict_runs_no_discovery_or_unlock(self):
        with fixture() as (ns, calls, queue, _, _):
            ns["acquire_run_lock"].return_value = False
            self.assertFalse(ns["stage_inventory"]("fixture-run", "2026-10-22", False))
            self.assertEqual(calls, [])
            queue.activate_next_city.assert_not_called()
            ns["release_run_lock"].assert_not_called()

    def test_dry_run_does_not_activate_city_or_acquire_lock(self):
        with fixture() as (ns, calls, queue, _, _):
            value = ns["stage_inventory"]("fixture-run", "2026-10-22", True)
            self.assertEqual(value["safe_ready_unique_orgs"], 56)
            self.assertEqual(calls, [])
            queue.activate_next_city.assert_not_called()
            ns["acquire_run_lock"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
