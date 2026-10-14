"""Exact-source patch and isolated behavior acceptance / 精确补丁与隔离行为验收。"""
import ast
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from tests import test_phase4a8r_continuous_discovery as legacy
from tests.test_discovery_service import DiscoveryDb, result
from discovery.discovery_service import DiscoveryService
from discovery.models import ProviderPage
from retail_city_queue import activate_next_city

ROOT = Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "patches/production/phase4a8s/continuous_discovery.patch"
spec = importlib.util.spec_from_file_location("phase4a8s_verifier", PATCH_PATH.with_name("verify_production_patch.py"))
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def source_pair():
    # Test fixture extraction only. Production verification NEVER normalizes.
    # 仅用于测试夹具提取；生产核验绝不转换换行。
    after = (ROOT / "bd_orchestrator.py").read_bytes().replace(b"\r\n", b"\n")
    if verifier.sha256(after) != verifier.AFTER_SHA256:
        raise AssertionError("4A.8R development source drift / 开发源码漂移")
    before = verifier.apply_checked(after, PATCH_PATH.read_bytes(), reverse=True)
    return before, after


def stage_function(source):
    tree = ast.parse(source.decode("utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "stage_inventory")
    namespace = dict(legacy.orchestrator.__dict__)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<approved-copy-stage-only>", "exec"), namespace)
    function = namespace["stage_inventory"]
    # Bind the isolated function to the already guarded development globals.
    # 仅绑定已启用护栏的开发全局变量，不执行源文件顶层代码。
    return types.FunctionType(function.__code__, legacy.orchestrator.__dict__,
                              function.__name__, function.__defaults__)


class ExactPatchTests(unittest.TestCase):
    def setUp(self):
        self.before, self.after = source_pair()
        self.patch = PATCH_PATH.read_bytes()

    @contextmanager
    def review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".development-copy").write_text("Offline review / 离线审查", encoding="utf-8")
            source = root / "source.py"
            source.write_bytes(self.before)
            diff = root / "change.patch"
            diff.write_bytes(self.patch)
            yield root, source, diff, root / "rehearsal"

    def test_apply_matches_tested_4a8r_byte_for_byte(self):
        self.assertEqual(verifier.apply_checked(self.before, self.patch), self.after)
        self.assertEqual(len(self.before), 30645)
        self.assertEqual(len(self.after), 31552)
        self.assertEqual(verifier.fingerprint(self.before)["line_endings"], "LF")
        self.assertEqual(verifier.fingerprint(self.after)["line_endings"], "LF")

    def test_reverse_restores_every_original_byte(self):
        self.assertEqual(verifier.apply_checked(self.after, self.patch, reverse=True), self.before)

    def test_source_mutation_refuses_application(self):
        for data in (self.before + b"\n", self.before[:-1], self.before.replace(b"target_met", b"target_zzz")):
            with self.subTest(sha=verifier.sha256(data)), self.assertRaisesRegex(verifier.VerificationError, "SOURCE_SHA_MISMATCH"):
                verifier.apply_checked(data, self.patch)

    def test_crlf_bom_and_mixed_input_are_refused(self):
        for data in (self.before.replace(b"\n", b"\r\n"), b"\xef\xbb\xbf" + self.before,
                     self.before.replace(b"\n", b"\r\n", 1)):
            with self.subTest(style=verifier.fingerprint(data)), self.assertRaisesRegex(verifier.VerificationError, "SOURCE_SHA_MISMATCH"):
                verifier.apply_checked(data, self.patch)

    def test_patch_tampering_and_extra_file_are_refused(self):
        for data in (self.patch.replace(b"discovery_pages", b"unsafe_pages"), self.patch + b"--- a/sender.py\n"):
            with self.subTest(sha=verifier.sha256(data)), self.assertRaisesRegex(verifier.VerificationError, "PATCH_SHA_MISMATCH"):
                verifier.apply_checked(self.before, data)

    def test_repeat_apply_and_reverse_on_wrong_version_are_refused(self):
        with self.assertRaisesRegex(verifier.VerificationError, "SOURCE_SHA_MISMATCH"):
            verifier.apply_checked(self.after, self.patch)
        with self.assertRaisesRegex(verifier.VerificationError, "SOURCE_SHA_MISMATCH"):
            verifier.apply_checked(self.before, self.patch, reverse=True)

    def test_bad_context_and_hunk_counts_are_refused(self):
        with self.assertRaisesRegex(verifier.VerificationError, "PATCH_CONTEXT_MISMATCH"):
            verifier._apply_unified(self.before, self.patch.replace(b" broad =", b" broad_x =", 1))
        with self.assertRaises(verifier.VerificationError):
            verifier._apply_unified(self.before, self.patch.replace(b"-426,9", b"-426,8"))

    def test_other_functions_and_file_bytes_are_unchanged(self):
        ranges = []
        for data in (self.before, self.after):
            tree = ast.parse(data.decode())
            inventory = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "stage_inventory")
            lines = data.splitlines(keepends=True)
            ranges.append((b"".join(lines[:inventory.lineno - 1]), b"".join(lines[inventory.end_lineno:])))
        self.assertEqual(ranges[0], ranges[1])
        self.assertEqual(self.patch.count(b"@@ -"), 3)
        self.assertEqual(self.patch.count(b"--- a/"), 1)

    def test_backup_corruption_refuses_rollback(self):
        verifier.verify_backup(self.before)
        with self.assertRaisesRegex(verifier.VerificationError, "BACKUP_SHA_MISMATCH"):
            verifier.verify_backup(self.before.replace(b"\n", b"\r\n"))

    def test_rehearsal_writes_new_copies_and_preserves_input(self):
        with self.review() as (root, source, diff, output):
            report = verifier.rehearse(source, diff, root, output)
            self.assertTrue(report["PATCH_APPLY_CHECK"])
            self.assertTrue(report["PATCH_ROLLBACK_CHECK"])
            self.assertEqual(source.read_bytes(), self.before)
            self.assertEqual((output / "bd_orchestrator.py").read_bytes(), self.after)
            self.assertEqual((output / "bd_orchestrator.py.rollback").read_bytes(), self.before)
            saved = json.loads((output / "verification.json").read_text(encoding="utf-8"))
            self.assertIn("description_zh", saved)
            self.assertIn("description_en", saved)

    def test_mismatched_source_creates_no_output(self):
        with self.review() as (root, source, diff, output):
            source.write_bytes(self.before + b"\n")
            with self.assertRaisesRegex(verifier.VerificationError, "SOURCE_SHA_MISMATCH"):
                verifier.rehearse(source, diff, root, output)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), self.before + b"\n")

    def test_review_paths_outside_marker_root_are_refused(self):
        with self.review() as (root, source, diff, output):
            with self.assertRaisesRegex(verifier.VerificationError, "OUTSIDE_ROOT"):
                verifier.rehearse(root.parent / "outside.py", diff, root, output)
            with self.assertRaisesRegex(verifier.VerificationError, "OUTSIDE_ROOT"):
                verifier.rehearse(source, diff, root, root.parent / "outside")
            (root / ".development-copy").unlink()
            with self.assertRaisesRegex(verifier.VerificationError, "MARKER_MISSING"):
                verifier.rehearse(source, diff, root, output)

    def test_existing_output_or_input_collision_are_refused(self):
        with self.review() as (root, source, diff, output):
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(verifier.VerificationError, "OUTPUT_EXISTS"):
                verifier.rehearse(source, diff, root, output)
            self.assertEqual(sentinel.read_text(), "keep")
            with self.assertRaisesRegex(verifier.VerificationError, "PATH_COLLISION"):
                verifier.rehearse(source, diff, root, root)


class PatchedSourceBehaviorTests(unittest.TestCase):
    stage = legacy.ContinuousDiscoveryTests.stage

    def setUp(self):
        before, _ = source_pair()
        self.patched = verifier.apply_checked(before, PATCH_PATH.read_bytes())
        self.stage_patch = patch.object(legacy.orchestrator, "stage_inventory", stage_function(self.patched))
        self.stage_patch.start()
        self.addCleanup(self.stage_patch.stop)

    def check_target(self, safe, target):
        with DiscoveryDb() as conn, self.stage(conn, safe=safe, target=target) as (service, finish, _, released, _, _):
            outcome = legacy.orchestrator.stage_inventory("fixture", "2026-10-13", False)
            self.assertEqual(outcome, safe >= target)
            service.run_places_batch.assert_called_once()
            self.assertEqual(service.run_places_batch.call_args.kwargs["max_pages"], 3)
            service.run_website_resolution.assert_called_once()
            service.run_staging_postprocess.assert_called_once()
            service.run_linked_backlog.assert_called_once()
            released.assert_called_once()
            self.assertEqual(finish.call_args.kwargs["gap"], max(0, target - safe))

    def test_safe49_target50(self):
        self.check_target(49, 50)

    def test_safe50_target50(self):
        self.check_target(50, 50)

    def test_safe51_target50(self):
        self.check_target(51, 50)

    def test_safe59_target60(self):
        self.check_target(59, 60)

    def test_safe60_target60(self):
        self.check_target(60, 60)

    def test_dry_run_database_bytes_and_all_write_functions_are_unchanged(self):
        with DiscoveryDb() as conn:
            conn.commit()
            db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
            before = db_path.read_bytes()
            with self.stage(conn) as (service, finish, acquired, released, _, constructor):
                with patch.object(legacy.orchestrator, "set_execution_mode") as mode, \
                     patch.object(legacy.orchestrator, "update_job_run") as update:
                    self.assertTrue(legacy.orchestrator.stage_inventory("fixture", "2026-10-13", True))
                mode.assert_not_called()
                update.assert_not_called()
                finish.assert_not_called()
                acquired.assert_not_called()
                released.assert_not_called()
                constructor.assert_not_called()
                service.run_places_batch.assert_not_called()
            self.assertEqual(db_path.read_bytes(), before)

    def test_actual_provider_calls_stop_at_three_without_send_artifacts(self):
        class PagingProvider:
            provider_name = "mock"
            configured = True
            def __init__(self):
                self.calls = []
            def search_places(self, query, city, state, cursor="", page_size=20):
                self.calls.append(cursor)
                return ProviderPage("mock", query, city, state, cursor,
                                    results=[result(f"Fixture Shop {len(self.calls)}", result_id=f"fixture-{len(self.calls)}",
                                                    address=f"{len(self.calls)} Fixture St, Nashville, TN 37201",
                                                    website=f"https://fixture-{len(self.calls)}.example", email="")],
                                    next_page_cursor=str(len(self.calls)), status="ok", request_count=1)
        with DiscoveryDb() as conn:
            city = activate_next_city(conn, state="TN")
            conn.commit()
            provider = PagingProvider()
            service = DiscoveryService(conn, provider=provider)
            # Continuous cursors force the page limit, not an exhausted fixture.
            # 持续返回 cursor，确保停止由页面预算触发，而非夹具耗尽。
            with self.stage(conn, actual_service=service), \
                 patch.dict(os.environ, {"WORKBUDDY_DISCOVERY_MAX_PAGES": "100"}), \
                 patch.object(service, "run_website_resolution"), \
                 patch.object(service, "run_staging_postprocess"), \
                 patch.object(service, "run_linked_backlog"):
                original_connect = legacy.orchestrator.get_db.side_effect
                def connect():
                    db = original_connect()
                    service.conn = db
                    return db
                legacy.orchestrator.get_db.side_effect = connect
                legacy.orchestrator.stage_inventory("fixture", "2026-10-13", False)
            self.assertEqual(provider.calls, ["", "1", "2"])
            row = conn.execute("SELECT page_cursor FROM lead_discovery_query_state WHERE active_city_id=? AND query_family='toy store'", (city["id"],)).fetchone()
            self.assertEqual(row[0], "3")
            for table in ("final_send_plan", "send_log"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='send_authorizations'").fetchone())

    def test_inherited_failure_lock_retry_and_city_contracts_on_patched_copy(self):
        for name in ("test_provider_exception_stops_and_releases_lock",
                     "test_provider_error_summary_cannot_be_target_success",
                     "test_lock_conflict_never_constructs_provider",
                     "test_page_budget_is_capped_at_three",
                     "test_invalid_budget_fails_before_discovery_execution",
                     "test_real_provider_failure_preserves_cursor_then_resumes",
                     "test_city_advances_only_with_durable_exhaustion"):
            with self.subTest(contract=name):
                getattr(legacy.ContinuousDiscoveryTests, name)(self)


if __name__ == "__main__":
    unittest.main()
