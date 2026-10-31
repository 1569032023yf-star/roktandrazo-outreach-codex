from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from autonomy.install_contract import exercise_install_contract
from autonomy.install_journal import STEPS, inspect_install


class RecordingAdapter:
    offline_only = True

    def __init__(self, root, fail_step=None, mismatch=None):
        self.root = Path(root)
        self.fail_step = fail_step
        self.mismatch = mismatch
        self.calls = []

    def apply(self, step, binding):
        self.calls.append(step)
        # Real isolated file effects make loss after mutation observable.
        (self.root / (step + '.effect')).write_text(binding['operation_id'])
        if step == self.fail_step:
            raise OSError('INJECTED_AFTER_EFFECT')

    def readback(self, step, binding):
        assert (self.root / (step + '.effect')).read_text() == binding['operation_id']
        result = dict(binding, step=step, outcome='OBSERVED_IN_SANDBOX')
        if self.mismatch:
            result[self.mismatch] = 'foreign'
        return result


class InstallContractTests(unittest.TestCase):
    def run_contract(self, root, adapter, condition=lambda: True):
        return exercise_install_contract(root, 'op', 'a'*64, 'b'*64, adapter, condition)

    def test_every_effect_failure_is_preserved_without_replay(self):
        for step in STEPS:
            with self.subTest(step=step), tempfile.TemporaryDirectory() as root:
                adapter = RecordingAdapter(root, fail_step=step)
                with self.assertRaises(OSError):
                    self.run_contract(root, adapter)
                result = inspect_install(Path(root) / 'op.jsonl')
                self.assertEqual(result['pending_step'], step)
                self.assertEqual(result['completed_steps'], STEPS.index(step))
                self.assertEqual(result['observed'], 'UNKNOWN')
                before = list(adapter.calls)
                with self.assertRaises(FileExistsError):
                    self.run_contract(root, adapter)
                self.assertEqual(adapter.calls, before)
                self.assertTrue((Path(root) / (step + '.effect')).exists())

    def test_driver_process_exit_after_second_acl_effect(self):
        code = '''import os,sys
from test_install_contract import RecordingAdapter
from autonomy.install_contract import exercise_install_contract
class ExitAdapter(RecordingAdapter):
 def readback(self,step,binding):
  if step=='STATE_ACL': os._exit(19)
  return super().readback(step,binding)
exercise_install_contract(sys.argv[1],'op','a'*64,'b'*64,ExitAdapter(sys.argv[1]),lambda:True)
'''
        with tempfile.TemporaryDirectory() as root:
            child = subprocess.run([sys.executable, '-B', '-c', code, root], timeout=20)
            self.assertEqual(child.returncode, 19)
            result = inspect_install(Path(root) / 'op.jsonl')
            self.assertEqual(result['pending_step'], 'STATE_ACL')
            self.assertEqual(result['completed_steps'], 4)
            for step in ('CODE_ACL', 'STATE_ACL'):
                self.assertTrue((Path(root) / (step + '.effect')).exists())
            adapter = RecordingAdapter(root)
            with self.assertRaises(FileExistsError):
                self.run_contract(root, adapter)
            self.assertEqual(adapter.calls, [])

    def test_readback_must_match_operation_package_lease_and_step(self):
        for field in ('operation_id', 'manifest_sha256', 'lease_binding', 'step', 'outcome'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                adapter = RecordingAdapter(root, mismatch=field)
                with self.assertRaisesRegex(ValueError, 'READBACK_BINDING'):
                    self.run_contract(root, adapter)
                self.assertEqual(adapter.calls, ['STAGE'])
                self.assertEqual(inspect_install(Path(root) / 'op.jsonl')['pending_step'], 'STAGE')

    def test_intent_flush_failure_prevents_effect(self):
        import os
        real_fsync = os.fsync
        calls = []

        def fail_second(fd):
            calls.append(fd)
            if len(calls) == 2:
                raise OSError('INTENT_FLUSH_FAILED')
            real_fsync(fd)

        with tempfile.TemporaryDirectory() as root:
            adapter = RecordingAdapter(root)
            with patch('autonomy.install_journal.os.fsync', side_effect=fail_second):
                with self.assertRaises(OSError):
                    self.run_contract(root, adapter)
            self.assertEqual(adapter.calls, [])

    def test_receipt_flush_failure_never_advances_to_next_effect(self):
        import os
        real_fsync = os.fsync
        calls = []

        def fail_third(fd):
            calls.append(fd)
            if len(calls) == 3:
                raise OSError('RECEIPT_FLUSH_FAILED')
            real_fsync(fd)

        with tempfile.TemporaryDirectory() as root:
            adapter = RecordingAdapter(root)
            with patch('autonomy.install_journal.os.fsync', side_effect=fail_third):
                with self.assertRaises(OSError):
                    self.run_contract(root, adapter)
            self.assertEqual(adapter.calls, ['STAGE'])
            self.assertTrue((Path(root) / 'STAGE.effect').exists())
            self.assertFalse(inspect_install(Path(root) / 'op.jsonl')['allow_replay'])

    def test_condition_lost_at_each_boundary_stops(self):
        for boundary in (1, 2, 3, 4):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as root:
                adapter = RecordingAdapter(root)
                count = 0

                def condition():
                    nonlocal count
                    count += 1
                    return count < boundary

                with self.assertRaises(ValueError):
                    self.run_contract(root, adapter, condition)
                self.assertEqual(adapter.calls, ['STAGE'] if boundary == 4 else [])

    def test_non_offline_adapter_rejected_and_success_is_not_authority(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = RecordingAdapter(root)
            adapter.offline_only = 1
            with self.assertRaisesRegex(ValueError, 'OFFLINE_CONTRACT_ONLY'):
                self.run_contract(root, adapter)
            self.assertFalse((Path(root) / 'op.jsonl').exists())
            adapter.offline_only = True
            result = self.run_contract(root, adapter)
            self.assertEqual(adapter.calls, list(STEPS))
            self.assertEqual(result['observed'], 'ALL_RECEIPTS_RECORDED')
            for key in ('allow_install', 'allow_dispatch', 'allow_replay', 'production_execution'):
                self.assertIs(result[key], False)


if __name__ == '__main__':
    unittest.main()
