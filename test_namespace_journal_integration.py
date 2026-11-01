"""源名字复核与真实安装日志离线接合 / Source-name checks joined to real offline journal.

Injected conditions are not formal leases or a production installer.
注入条件不是正式租约或生产安装器，临时文件不是服务安装。
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from autonomy.install_contract import exercise_install_contract
from autonomy.install_journal import InstallJournal, inspect_install
from test_install_contract import RecordingAdapter
import test_source_binding_experiment as experiment


@unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem required')
class NamespaceJournalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = experiment.SourceBindingExperimentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def replace(self):
        os.rename(self.fixture.source / 'host.bin', self.root / 'original')
        (self.fixture.source / 'host.bin').write_bytes(b'candidate')

    def run_contract(self, adapter, condition):
        return exercise_install_contract(self.root, 'op', 'a'*64, 'b'*64,
                                         adapter, condition)

    def assert_preserved(self, pending, completed):
        path = self.root / 'op.jsonl'
        before = path.read_bytes()
        observed = inspect_install(path)
        self.assertEqual(observed['observed'], 'UNKNOWN')
        self.assertEqual(observed['pending_step'], pending)
        self.assertEqual(observed['completed_steps'], completed)
        self.assertFalse(observed['allow_replay'])
        self.assertFalse(observed['allow_install'])
        adapter = RecordingAdapter(self.root)
        with self.assertRaises(FileExistsError):
            self.run_contract(adapter, lambda: True)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(path.read_bytes(), before)

    def test_replacement_after_intent_flush_stops_before_effect(self):
        adapter = RecordingAdapter(self.root)
        real = InstallJournal.intent
        def intent(journal, step):
            real(journal, step)
            self.replace()
        with self.fixture.guard() as guard:
            def condition():
                guard.revalidate()
                return True
            with patch.object(InstallJournal, 'intent', intent):
                with self.assertRaisesRegex(ValueError, 'NAMED_SOURCE_IDENTITY_MISMATCH'):
                    self.run_contract(adapter, condition)
        self.assertEqual(adapter.calls, [])
        self.assertFalse((self.root / 'STAGE.effect').exists())
        self.assert_preserved('STAGE', 0)

    def test_replacement_after_effect_readback_stops_before_receipt(self):
        outer = self
        class Adapter(RecordingAdapter):
            def readback(adapter, step, binding):
                result = super().readback(step, binding)
                outer.replace()
                return result
        adapter = Adapter(self.root)
        with self.fixture.guard() as guard:
            def condition():
                guard.revalidate()
                return True
            with self.assertRaisesRegex(ValueError, 'NAMED_SOURCE_IDENTITY_MISMATCH'):
                self.run_contract(adapter, condition)
        self.assertEqual(adapter.calls, ['STAGE'])
        self.assertTrue((self.root / 'STAGE.effect').exists())
        self.assert_preserved('STAGE', 0)

    def test_injected_lease_condition_loss_keeps_publish_pending(self):
        active = True
        class Adapter(RecordingAdapter):
            def readback(adapter, step, binding):
                nonlocal active
                result = super().readback(step, binding)
                if step == 'PUBLISH':
                    active = False
                return result
        adapter = Adapter(self.root)
        with self.fixture.guard() as guard:
            def condition():
                guard.revalidate()
                return active
            with self.assertRaisesRegex(ValueError, 'OFFLINE_CONDITION_LOST'):
                self.run_contract(adapter, condition)
        self.assertEqual(adapter.calls, ['STAGE', 'PUBLISH'])
        self.assertTrue((self.root / 'PUBLISH.effect').exists())
        self.assert_preserved('PUBLISH', 1)

    def test_real_process_exit_releases_source_handles_without_journal_replay(self):
        code = '''import os,sys
from pathlib import Path
from autonomy.source_identity import SourceIdentityGuard
from autonomy.install_contract import exercise_install_contract
from test_install_contract import RecordingAdapter
from test_first_publication import MANIFEST
root=Path(sys.argv[1])
class Adapter(RecordingAdapter):
 def readback(self,step,binding):
  if step=='STAGE':os._exit(37)
  return super().readback(step,binding)
with SourceIdentityGuard(root/'staged',MANIFEST,offline_only=True) as guard:
 def condition():
  guard.revalidate()
  return True
 exercise_install_contract(root,'op','a'*64,'b'*64,Adapter(root),condition)
'''
        child = subprocess.run([sys.executable, '-B', '-c', code, str(self.root)], timeout=20)
        self.assertEqual(child.returncode, 37)
        self.assertTrue((self.root / 'STAGE.effect').exists())
        self.assert_preserved('STAGE', 0)
        (self.fixture.source / 'host.bin').write_bytes(b'handles-released')


if __name__ == '__main__':
    unittest.main()
