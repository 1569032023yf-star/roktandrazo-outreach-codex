"""真实Windows子日志对象/进程合同 / Actual Windows journal object/process contracts."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from autonomy.install_journal import InstallJournal,inspect_install
from autonomy.install_contract import exercise_install_contract
from test_install_contract import RecordingAdapter

@unittest.skipUnless(os.name=='nt','Actual Windows filesystem required')
class JournalIdentityProcessTests(unittest.TestCase):
    def test_named_replacement_denied_while_writer_open_then_released(self):
        with tempfile.TemporaryDirectory() as d:
            journal=InstallJournal(d,'op','a'*64,'b'*64)
            replacement=Path(d)/'replacement';replacement.write_bytes(journal.path.read_bytes())
            original=journal.path.read_bytes()
            try:
                with self.assertRaises(PermissionError):os.replace(replacement,journal.path)
                self.assertEqual(journal.path.read_bytes(),original)
                journal.revalidate()
                journal.intent('STAGE')
            finally:journal.close()
            os.replace(replacement,journal.path)
            self.assertEqual(journal.path.read_bytes(),original)
            self.assertFalse(inspect_install(journal.path)['allow_replay'])

    def test_hardlink_alias_invalidates_writer_even_after_alias_removed(self):
        with tempfile.TemporaryDirectory() as d:
            journal=InstallJournal(d,'op','a'*64,'b'*64);alias=Path(d)/'alias'
            try:
                original=journal.path.read_bytes()
                os.link(journal.path,alias)
                self.assertEqual(journal.path.stat().st_nlink,2)
                with self.assertRaisesRegex(ValueError,'JOURNAL_IDENTITY_CHANGED'):journal.intent('STAGE')
                alias.unlink()
                with self.assertRaisesRegex(ValueError,'STOP_AND_PRESERVE'):journal.intent('STAGE')
                self.assertEqual(journal.path.read_bytes(),original)
            finally:journal.close()

    def test_child_exits_after_detected_corruption_status_unknown_no_replay(self):
        with tempfile.TemporaryDirectory() as d:
            child=r'''import os,sys
from pathlib import Path
from autonomy.install_contract import exercise_install_contract
from test_install_contract import RecordingAdapter
root=Path(sys.argv[1]);path=root/'op.jsonl'
class Adapter(RecordingAdapter):
 def apply(self,step,binding):
  super().apply(step,binding)
  with path.open('ab') as f:
   f.write(b'INJECTED\n');f.flush();os.fsync(f.fileno())
try:exercise_install_contract(root,'op','a'*64,'b'*64,Adapter(root),lambda:True)
except ValueError as e:
 if str(e)=='JOURNAL_CONTENT_CHANGED':os._exit(47)
os._exit(48)
'''
            result=subprocess.run([sys.executable,'-B','-c',child,d],timeout=20)
            self.assertEqual(result.returncode,47)
            path=Path(d)/'op.jsonl';original=path.read_bytes();status=inspect_install(path)
            self.assertEqual(status['observed'],'UNKNOWN');self.assertIsNone(status['pending_step']);self.assertIn(b'INTENT',original)
            self.assertFalse(status['allow_replay']);self.assertFalse(status['allow_install'])
            self.assertTrue((Path(d)/'STAGE.effect').exists());self.assertFalse((Path(d)/'PUBLISH.effect').exists())
            fresh=RecordingAdapter(Path(d))
            with self.assertRaises(FileExistsError):exercise_install_contract(d,'op','a'*64,'b'*64,fresh,lambda:True)
            self.assertEqual(fresh.calls,[]);self.assertEqual(path.read_bytes(),original)

if __name__=='__main__':unittest.main()
