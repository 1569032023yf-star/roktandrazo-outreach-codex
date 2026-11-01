"""持源日志跨进程故障 / Held-source journal process boundaries, offline only."""
import os
import subprocess
import sys
import time
import unittest

from autonomy.install_journal import inspect_install
import test_namespace_journal_integration as integration


CHILD = '''import os,sys,time
from pathlib import Path
from autonomy.source_identity import SourceIdentityGuard
from autonomy.install_contract import exercise_install_contract
from autonomy.install_journal import InstallJournal
from test_install_contract import RecordingAdapter
from test_first_publication import MANIFEST
root=Path(sys.argv[1]);mode=sys.argv[2]
real_intent=InstallJournal.intent;real_receipt=InstallJournal.receipt
def intent(journal,step):
 real_intent(journal,step)
 if step=='STAGE' and mode=='intent':os._exit(42)
 if step=='STAGE' and mode=='hold':
  (root/'ready').write_text('ready')
  until=time.monotonic()+10
  while not (root/'release').exists() and time.monotonic()<until:time.sleep(.02)
  os._exit(44)
def receipt(journal,step,digest):
 real_receipt(journal,step,digest)
 if step=='STAGE' and mode=='receipt':os._exit(43)
InstallJournal.intent=intent;InstallJournal.receipt=receipt
with SourceIdentityGuard(root/'staged',MANIFEST,offline_only=True) as guard:
 def condition():
  guard.revalidate()
  return True
 exercise_install_contract(root,'op','a'*64,'b'*64,RecordingAdapter(root),condition)
'''


@unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem required')
class SourceProcessBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = integration.NamespaceJournalIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def run_child(self, mode):
        return subprocess.run([sys.executable, '-B', '-c', CHILD,
                               str(self.root), mode], timeout=20)

    def test_exit_after_intent_preserves_pending_without_effect(self):
        self.assertEqual(self.run_child('intent').returncode, 42)
        self.assertFalse((self.root / 'STAGE.effect').exists())
        self.fixture.assert_preserved('STAGE', 0)
        (self.root / 'staged' / 'host.bin').write_bytes(b'handles-released')

    def test_exit_after_receipt_preserves_completed_prefix_without_replay(self):
        self.assertEqual(self.run_child('receipt').returncode, 43)
        self.assertTrue((self.root / 'STAGE.effect').exists())
        self.assertFalse((self.root / 'PUBLISH.effect').exists())
        self.fixture.assert_preserved(None, 1)
        (self.root / 'staged' / 'host.bin').write_bytes(b'handles-released')

    def test_second_process_cannot_claim_live_operation_or_modify_source(self):
        child = subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(self.root), 'hold'])
        try:
            deadline = time.monotonic() + 8
            while not (self.root / 'ready').exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.root / 'ready').exists())
            before = (self.root / 'op.jsonl').read_bytes()
            with self.assertRaises(PermissionError):
                (self.root / 'staged' / 'host.bin').write_bytes(b'foreign')
            rival = '''import sys
from autonomy.install_contract import exercise_install_contract
from test_install_contract import RecordingAdapter
adapter=RecordingAdapter(sys.argv[1])
try:exercise_install_contract(sys.argv[1],'op','a'*64,'b'*64,adapter,lambda:True)
except FileExistsError:sys.exit(0 if not adapter.calls else 9)
sys.exit(8)
'''
            result = subprocess.run([sys.executable, '-B', '-c', rival, str(self.root)], timeout=15)
            self.assertEqual(result.returncode, 0)
            self.assertEqual((self.root / 'op.jsonl').read_bytes(), before)
            self.assertEqual(inspect_install(self.root / 'op.jsonl')['pending_step'], 'STAGE')
            self.assertFalse((self.root / 'STAGE.effect').exists())
            (self.root / 'release').write_text('release')
            self.assertEqual(child.wait(timeout=15), 44)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=15)
        self.fixture.assert_preserved('STAGE', 0)


if __name__ == '__main__':
    unittest.main()
