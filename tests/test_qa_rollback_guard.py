"""Exercise rollback identity checks with isolated files only."""
import sys
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "publisher_channel"))
import executor


class RollbackGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.target, self.backup = root / "target.py", root / "backup"
        self.before, self.after = b"before\n", b"after\n"
        self.target.write_bytes(self.after)
        self.backup.write_bytes(self.before)
        b, a = executor.fingerprint(self.before), executor.fingerprint(self.after)
        self.prep = {"target": self.target, "item": {"path": "target.py", "before_sha256": b["sha256"],
                     "before_bytes": b["bytes"], "after_sha256": a["sha256"], "after_bytes": a["bytes"]}}

    def restore(self):
        with patch.object(executor, "copy_dacl"):
            return executor._restore_replaced_file(self.prep, {"backup": str(self.backup)}, "test")

    def test_release_uses_original_date_and_holder(self):
        db = Path(self.tmp.name) / "locks.sqlite"
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("CREATE TABLE system_config (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
            conn.executemany("INSERT INTO system_config(key,value) VALUES(?,?)",
                             [("lock:2026-11-24", "holder"), ("lock:2026-11-25", "holder")])
        cfg = {"lock": {"key_prefix": "lock:"}, "production": {"db_path": str(db)}}
        self.assertFalse(executor.inventory_release(cfg, "holder"))
        self.assertFalse(executor.inventory_release(cfg, "other", lock_key="lock:2026-11-24"))
        self.assertFalse(executor.inventory_release(cfg, "holder", lock_key="lock:invalid"))
        self.assertTrue(executor.inventory_release(cfg, "holder", lock_key="lock:2026-11-24"))
        with closing(sqlite3.connect(db)) as conn:
            self.assertEqual(dict(conn.execute("SELECT key,value FROM system_config")),
                             {"lock:2026-11-24": "released", "lock:2026-11-25": "holder"})

    def test_restores_verified_backup(self):
        self.restore()
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_preserves_changed_target(self):
        self.target.write_bytes(b"external change")
        with self.assertRaises(executor.GateError):
            self.restore()
        self.assertEqual(self.target.read_bytes(), b"external change")

    def test_rejects_changed_backup(self):
        self.backup.write_bytes(b"corrupt")
        with self.assertRaises(executor.GateError):
            self.restore()
        self.assertEqual(self.target.read_bytes(), self.after)

    def test_release_failure_preserves_applied_receipt(self):
        self.target.write_bytes(self.before)
        src = self.prep["item"]
        src.update({"section": b"--- a/target.py\n+++ b/target.py\n@@ -1 +1 @@\n-before\n+after\n", "hunk_count": 1})
        records = {}
        cfg = {"_paths": {"backups": self.tmp.name}, "channel_id": "offline"}
        def record(_cfg, result, caller):
            records[result["operation_id"]] = dict(result)
        with patch.multiple(executor,
                            _assert_seal=lambda cfg: None,
                            get_release=lambda cfg, rid: {},
                            live_gates_multi=lambda *a, **k: {},
                            gates_summary=lambda gates: {"all_pass": True},
                            resolve_targets=lambda cfg, rel: [(src, self.target)],
                            business_date_shanghai=lambda: "2026-11-24",
                            inventory_acquire=lambda cfg, holder: (True, {"holder": holder}),
                            inventory_release=lambda cfg, holder, **kw: False,
                            copy_dacl=lambda src, dst: None,
                            audit=lambda cfg, event: True,
                            _record=record,
                            load_operations=lambda cfg: {"operations": records}):
            result = executor.op_apply_multi(cfg, "offline-release", "test", True)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(records[result["operation_id"]]["state"], "unknown")
        self.assertEqual(self.target.read_bytes(), self.after)

    def test_receipt_read_error_does_not_rollback_or_release(self):
        self.target.write_bytes(self.before)
        item = self.prep["item"]
        item.update({"section": b"--- a/target.py\n+++ b/target.py\n@@ -1 +1 @@\n-before\n+after\n", "hunk_count": 1})
        releases = []
        cfg = {"_paths": {"backups": self.tmp.name}, "channel_id": "offline"}
        def unreadable(_cfg):
            raise ValueError("damaged operation store")
        with patch.multiple(executor,
                            _assert_seal=lambda cfg: None, get_release=lambda cfg, rid: {},
                            live_gates_multi=lambda *a, **k: {}, gates_summary=lambda gates: {"all_pass": True},
                            resolve_targets=lambda cfg, rel: [(item, self.target)],
                            business_date_shanghai=lambda: "2026-11-24",
                            inventory_acquire=lambda cfg, holder: (True, {"holder": holder}),
                            inventory_release=lambda cfg, holder, **kw: (releases.append(holder) or True),
                            copy_dacl=lambda src, dst: None, _record=lambda *a: None, audit=lambda *a: True,
                            load_operations=unreadable):
            result = executor.op_apply_multi(cfg, "offline-release", "test", True)
        self.assertEqual(result["state"], "failed")
        self.assertEqual(self.target.read_bytes(), self.before)
        self.assertEqual(len(releases), 1)

    def test_failure_with_unverified_lock_release_is_unknown(self):
        self.target.write_bytes(self.before)
        item = dict(self.prep["item"])
        item["before_sha256"] = "not-the-current-hash"
        records = {}
        cfg = {"_paths": {"backups": self.tmp.name}, "channel_id": "offline"}
        with patch.multiple(executor,
                            _assert_seal=lambda cfg: None, get_release=lambda cfg, rid: {},
                            live_gates_multi=lambda *a, **k: {}, gates_summary=lambda gates: {"all_pass": True},
                            resolve_targets=lambda cfg, rel: [(item, self.target)],
                            business_date_shanghai=lambda: "2026-11-25",
                            inventory_acquire=lambda cfg, holder: (True, {"holder": holder}),
                            inventory_release=lambda cfg, holder, **kw: False,
                            _record=lambda cfg, result, caller: records.update({result["operation_id"]: dict(result)}),
                            audit=lambda *a: True):
            result = executor.op_apply_multi(cfg, "offline-release", "test", True)
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(result["lock_release"], "unknown")
        self.assertEqual(records[result["operation_id"]]["state"], "unknown")
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_audit_failure_reports_unknown_without_undoing_files(self):
        self.target.write_bytes(self.before)
        item = self.prep["item"]
        item.update({"section": b"--- a/target.py\n+++ b/target.py\n@@ -1 +1 @@\n-before\n+after\n", "hunk_count": 1})
        records = {}
        cfg = {"_paths": {"backups": self.tmp.name}, "channel_id": "offline"}
        def record(_cfg, result, caller):
            records[result["operation_id"]] = dict(result)
        with patch.multiple(executor,
                            _assert_seal=lambda cfg: None, get_release=lambda cfg, rid: {},
                            live_gates_multi=lambda *a, **k: {}, gates_summary=lambda gates: {"all_pass": True},
                            resolve_targets=lambda cfg, rel: [(item, self.target)],
                            business_date_shanghai=lambda: "2026-11-24",
                            inventory_acquire=lambda cfg, holder: (True, {"holder": holder}),
                            inventory_release=lambda cfg, holder, **kw: True,
                            copy_dacl=lambda src, dst: None, _record=record,
                            load_operations=lambda cfg: {"operations": records},
                            audit=lambda cfg, event: False):
            result = executor.op_apply_multi(cfg, "offline-release", "test", True)
        self.assertEqual(result["verdict"], "APPLY_STATUS_UNKNOWN")
        self.assertEqual(records[result["operation_id"]]["state"], "unknown")
        self.assertEqual(self.target.read_bytes(), self.after)
        with patch.object(executor, "load_operations", return_value={"operations": records}), \
                patch.object(executor, "audit", return_value=True):
            status = executor.op_status(cfg, result["operation_id"], "test")
        self.assertEqual(status["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
