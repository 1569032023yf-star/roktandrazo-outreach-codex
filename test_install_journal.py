import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from autonomy.install_journal import InstallJournal, STEPS, inspect_install


class InstallJournalTests(unittest.TestCase):
    def test_partial_acl_survives_process_exit_without_replay(self):
        with tempfile.TemporaryDirectory() as root:
            code = '''import os,sys
from autonomy.install_journal import InstallJournal
j=InstallJournal(sys.argv[1],'op','a'*64,'b'*64)
for step in ('STAGE','PUBLISH','REGISTER_DISABLED','CODE_ACL'):
 j.intent(step); j.receipt(step,'c'*64)
j.intent('STATE_ACL')
os._exit(17)
'''
            run = subprocess.run([sys.executable, '-B', '-c', code, root], timeout=20)
            self.assertEqual(run.returncode, 17)
            path = Path(root) / 'op.jsonl'
            before = path.read_bytes()
            result = inspect_install(path)
            self.assertEqual(result['pending_step'], 'STATE_ACL')
            self.assertEqual(result['completed_steps'], 4)
            self.assertEqual(result['observed'], 'UNKNOWN')
            self.assertFalse(result['allow_replay'])
            with self.assertRaises(FileExistsError):
                InstallJournal(root, 'op', 'a'*64, 'b'*64)
            self.assertEqual(before, path.read_bytes())

    def test_order_and_full_receipts_never_authorize(self):
        with tempfile.TemporaryDirectory() as root:
            j = InstallJournal(root, 'op', 'a'*64, 'b'*64)
            with self.assertRaises(ValueError):
                j.intent('PUBLISH')
            for step in STEPS:
                j.intent(step)
                with self.assertRaises(ValueError):
                    j.intent(step)
                j.receipt(step, 'c'*64)
            j.close()
            result = inspect_install(Path(root) / 'op.jsonl')
            self.assertEqual(result['observed'], 'ALL_RECEIPTS_RECORDED')
            self.assertFalse(result['allow_install'])

    def test_flush_failure_poison_writer_and_preserve(self):
        with tempfile.TemporaryDirectory() as root:
            j = InstallJournal(root, 'op', 'a'*64, 'b'*64)
            with patch('autonomy.install_journal.os.fsync', side_effect=OSError('disk')):
                with self.assertRaises(OSError):
                    j.intent('STAGE')
            with self.assertRaises(ValueError):
                j.intent('STAGE')
            j.close()
            self.assertFalse(inspect_install(j.path)['allow_replay'])

    def test_torn_or_invalid_log_is_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'op.jsonl'
            for raw in (b'', b'{', b'[]\n', b'{}\n'):
                path.write_bytes(raw)
                self.assertEqual(inspect_install(path)['observed'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
