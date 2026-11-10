"""Offline tests: the log pin does not authorize cancellation recovery."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from autonomy.cancellation_recovery import _record, recover_cancellation
from autonomy.recovery_log_binding import pinned_recovery_log
from autonomy.single_slot_adapter import AdapterError


@unittest.skipUnless(os.name == 'nt', 'Windows file pin required')
class RecoveryLogBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / 'recovery.sqlite'
        self.other = self.root / 'slots.sqlite'
        for path in (self.log, self.other):
            with closing(sqlite3.connect(path)):
                pass
        stat = self.log.stat()
        self.expected = (stat.st_dev, stat.st_ino)

    def guard(self):
        return pinned_recovery_log(self.log, expected_identity=self.expected, protected=[self.other])

    def record(self, guard, fault=lambda _: None):
        return _record(self.log, 'id', {'id': 'id'}, 'PREPARED', fault, b'lock',
                       check_connection=guard)

    def test_real_connection_and_wrong_connection(self):
        with self.guard() as check:
            self.assertIsNone(self.record(check))
            self.assertEqual(self.record(check), 'PREPARED')
            with closing(sqlite3.connect(self.other)) as wrong:
                with self.assertRaisesRegex(AdapterError, 'CONNECTION_REJECTED'):
                    check(wrong)
        self.assertEqual(recover_cancellation(None, None, None, None, None, None,
                         recovery_path=self.log)['outcome'], 'UNKNOWN_RECONCILE_ONLY')

    def test_alias_sidecars_and_hardlinks_are_rejected(self):
        for path in (self.other, Path(str(self.other) + '-wal'),
                     Path(str(self.other) + '-journal'), Path(str(self.other) + '-shm')):
            if not path.exists(): path.touch()
            stat = path.stat()
            with self.subTest(path=path.name), self.assertRaisesRegex(AdapterError, 'ALIAS_REJECTED'):
                with pinned_recovery_log(path, expected_identity=(stat.st_dev, stat.st_ino),
                                         protected=[self.other]):
                    self.fail('alias accepted')
        link = self.root / 'hardlink.sqlite'
        os.link(self.other, link)
        stat = link.stat()
        with self.assertRaisesRegex(AdapterError, 'ALIAS_REJECTED'):
            with pinned_recovery_log(link, expected_identity=(stat.st_dev, stat.st_ino),
                                     protected=[self.other]):
                self.fail('hardlink accepted')

    def test_replacement_rejected_before_and_during_pin(self):
        replacement = self.root / 'replacement.sqlite'
        with closing(sqlite3.connect(replacement)):
            pass
        with self.guard() as check:
            with self.assertRaises(OSError):
                os.replace(replacement, self.log)
            self.assertIsNone(self.record(check))
        os.replace(replacement, self.log)
        with self.assertRaisesRegex(AdapterError, 'IDENTITY_CHANGED'):
            with self.guard():
                self.fail('replacement accepted')

    def test_process_exit_before_and_after_commit(self):
        code = '''
import os,sys
from autonomy.cancellation_recovery import _record
from autonomy.recovery_log_binding import pinned_recovery_log
path,other,phase=sys.argv[1:]
info=os.stat(path)
def fault(stage):
    if stage == phase: os._exit(71)
with pinned_recovery_log(path, expected_identity=(info.st_dev,info.st_ino), protected=[other]) as check:
    _record(path,'id',{'id':'id'},'PREPARED',fault,b'lock',check_connection=check)
'''
        for stage in ('before_prepared_commit', 'after_prepared_commit'):
            with self.subTest(stage=stage):
                run = subprocess.run([sys.executable, '-B', '-c', code, str(self.log),
                                      str(self.other), stage], timeout=15, capture_output=True)
                self.assertEqual(run.returncode, 71, run.stderr)
                with self.guard() as check:
                    self.assertEqual(self.record(check), None if stage.startswith('before') else 'PREPARED')
                self.log.unlink()
                with closing(sqlite3.connect(self.log)):
                    pass
                stat = self.log.stat()
                self.expected = (stat.st_dev, stat.st_ino)


if __name__ == '__main__':
    unittest.main()
