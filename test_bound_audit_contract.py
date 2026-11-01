"""审计目录持续绑定离线测试 / Continuous audit-directory binding offline tests."""
import os
from pathlib import Path
import tempfile
import unittest

from autonomy.install_contract import exercise_bound_audit_contract_offline
from autonomy.install_journal import STEPS, inspect_install
from test_install_contract import RecordingAdapter


@unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem required')
class BoundAuditContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / 'audit'
        self.root.mkdir()
        self.moved = self.parent / 'moved'

    def run_bound(self, adapter, condition=lambda: True, offline_only=True):
        return exercise_bound_audit_contract_offline(self.root, 'op', 'a'*64,
            'b'*64, adapter, condition, offline_only=offline_only)

    def test_root_cannot_be_renamed_at_each_effect_or_readback(self):
        outer = self
        class Adapter(RecordingAdapter):
            def apply(adapter, step, binding):
                with outer.assertRaises(PermissionError):
                    os.rename(outer.root, outer.moved)
                super().apply(step, binding)
            def readback(adapter, step, binding):
                with outer.assertRaises(PermissionError):
                    os.rename(outer.root, outer.moved)
                return super().readback(step, binding)
        adapter = Adapter(self.root)
        result = self.run_bound(adapter)
        self.assertEqual(adapter.calls, list(STEPS))
        self.assertTrue(result['audit_directory_identity_held'])
        for key in ('allow_install', 'allow_dispatch', 'audit_acl_trust_verified',
                    'formal_lease_verified', 'production_execution'):
            self.assertFalse(result[key])
        os.rename(self.root, self.moved)

    def test_failure_preserves_journal_and_releases_directory_handles(self):
        adapter = RecordingAdapter(self.root, fail_step='PUBLISH')
        with self.assertRaisesRegex(OSError, 'INJECTED_AFTER_EFFECT'):
            self.run_bound(adapter)
        before = (self.root / 'op.jsonl').read_bytes()
        self.assertEqual(inspect_install(self.root / 'op.jsonl')['pending_step'], 'PUBLISH')
        fresh = RecordingAdapter(self.root)
        with self.assertRaises(FileExistsError):
            self.run_bound(fresh)
        self.assertEqual(fresh.calls, [])
        self.assertEqual((self.root / 'op.jsonl').read_bytes(), before)
        os.rename(self.root, self.moved)
        self.assertEqual((self.moved / 'op.jsonl').read_bytes(), before)

    def test_explicit_scope_and_failed_condition_prevent_journal_creation(self):
        adapter = RecordingAdapter(self.root)
        for offline in (False, 1):
            with self.assertRaisesRegex(ValueError, 'WINDOWS_OFFLINE_ONLY'):
                self.run_bound(adapter, offline_only=offline)
        with self.assertRaisesRegex(ValueError, 'OFFLINE_CONTRACT_ONLY'):
            self.run_bound(adapter, lambda: False)
        self.assertEqual(adapter.calls, [])
        self.assertFalse((self.root / 'op.jsonl').exists())
        os.rename(self.root, self.moved)


if __name__ == '__main__':
    unittest.main()
