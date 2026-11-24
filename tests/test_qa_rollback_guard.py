"""Exercise rollback identity checks with isolated files only."""
import sys
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


if __name__ == "__main__":
    unittest.main()
