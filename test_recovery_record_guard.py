"""Offline tests for the disabled recovery path's guarded record primitive."""
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from autonomy.cancellation_recovery import _record


class GuardedRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'recovery.sqlite'
        self.decoy = Path(self.temp.name) / 'decoy.sqlite'
        for path in (self.path, self.decoy):
            with closing(sqlite3.connect(path)):
                pass
        info = self.path.stat()
        self.identity = (info.st_dev, info.st_ino)
        self.selected = self.path

    def check(self, db):
        opened = Path(db.execute('PRAGMA database_list').fetchone()[2])
        info = self.selected.stat()
        if (self.selected != self.path or opened.resolve() != self.path.resolve()
                or (info.st_dev, info.st_ino) != self.identity):
            raise RuntimeError('binding changed')

    def record(self, state='PREPARED', fault=lambda _: None):
        return _record(self.path, 'id', {'operation': 'id'}, state, fault,
                       b'lock', check_connection=self.check)

    def test_normal_and_idempotent(self):
        self.assertIsNone(self.record())
        self.assertEqual(self.record(), 'PREPARED')
        self.assertEqual(self.record('COMPLETED'), 'PREPARED')
        self.assertEqual(self.record('COMPLETED'), 'COMPLETED')

    def test_retarget_before_commit_rolls_back(self):
        def change(stage):
            if stage == 'before_prepared_commit':
                self.selected = self.decoy
        with self.assertRaisesRegex(RuntimeError, 'binding changed'):
            self.record(fault=change)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='recoveries'").fetchall(), [])
        with closing(sqlite3.connect(self.decoy)) as db:
            self.assertEqual(db.execute('SELECT name FROM sqlite_master').fetchall(), [])

    def test_after_commit_change_is_detected_and_retry_is_idempotent(self):
        def change(stage):
            if stage == 'after_prepared_commit':
                self.selected = self.decoy
        with self.assertRaisesRegex(RuntimeError, 'binding changed'):
            self.record(fault=change)
        self.selected = self.path
        self.assertEqual(self.record(), 'PREPARED')

    def test_missing_guard_or_file_never_creates_store(self):
        with self.assertRaises(TypeError):
            _record(self.path, 'id', {}, 'PREPARED', lambda _: None, b'lock')
        missing = Path(self.temp.name) / 'missing.sqlite'
        with self.assertRaises(FileNotFoundError):
            _record(missing, 'id', {}, 'PREPARED', lambda _: None, b'lock',
                    check_connection=self.check)
        self.assertFalse(missing.exists())

    def test_file_replaced_before_open_is_rejected(self):
        original = self.path.with_suffix('.original')
        self.path.rename(original)
        self.decoy.rename(self.path)
        with self.assertRaisesRegex(RuntimeError, 'binding changed'):
            self.record()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT name FROM sqlite_master').fetchall(), [])

    def test_process_exit_before_and_after_commit(self):
        code = '''
import os, sys
from autonomy.cancellation_recovery import _record
stage = sys.argv[2]
def fault(value):
    if value == stage: os._exit(71)
_record(sys.argv[1], 'id', {'operation': 'id'}, 'PREPARED', fault, b'lock', check_connection=lambda db: None)
'''
        for phase in ('before_prepared_commit', 'after_prepared_commit'):
            with self.subTest(phase=phase):
                result = subprocess.run([sys.executable, '-c', code, str(self.path), phase],
                                        timeout=15, capture_output=True)
                self.assertEqual(result.returncode, 71, result.stderr)
                expected = None if phase == 'before_prepared_commit' else 'PREPARED'
                self.assertEqual(self.record(), expected)
                # Leave a fresh file for the next phase.
                self.path.unlink()
                with closing(sqlite3.connect(self.path)):
                    pass
                info = self.path.stat()
                self.identity = (info.st_dev, info.st_ino)


if __name__ == '__main__':
    unittest.main()
