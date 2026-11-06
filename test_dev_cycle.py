import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

from autonomy.dev_cycle import Busy, Coordinator


class DevelopmentCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work1 = self.root / 'a'; self.work1.mkdir()
        self.work2 = self.root / 'b'; self.work2.mkdir()
        self.work3 = self.root / 'c'; self.work3.mkdir()

    def child(self, worktree, run_id=None):
        run_id = run_id or str(uuid.uuid4())
        code = ('import time; from autonomy.dev_cycle import Coordinator; '
                'c=Coordinator(%r); '
                's=c.slot(%r,%r,"branch","child"); s.__enter__(); '
                'print("READY",flush=True); time.sleep(60)' %
                (str(self.root / 'locks'), run_id, str(worktree)))
        child = subprocess.Popen([sys.executable, '-u', '-c', code], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        self.addCleanup(child.stdout.close); self.addCleanup(child.stderr.close)
        self.addCleanup(lambda: child.kill() if child.poll() is None else None)
        self.assertEqual(child.stdout.readline().strip(), 'READY', child.stderr.read() if child.poll() is not None else '')
        return child, run_id

    def test_two_process_slots_exclude_third_and_duplicate_worktree(self):
        a, _ = self.child(self.work1)
        c = Coordinator(self.root / 'locks'); self.addCleanup(c.close)
        with self.assertRaisesRegex(Busy, 'WORKTREE_ALREADY_IN_USE'):
            with c.slot(str(uuid.uuid4()), self.work1, 'other', 'test'): pass
        b, _ = self.child(self.work2)
        with self.assertRaisesRegex(Busy, 'ALL_SLOTS_BUSY'):
            with c.slot(str(uuid.uuid4()), self.work3, 'third', 'test'): pass
        a.kill(); a.wait(timeout=10)
        with c.slot(str(uuid.uuid4()), self.work3, 'third', 'test') as row:
            self.assertIn(row['slot'], (1, 2))
        b.kill(); b.wait(timeout=10)

    def test_abnormal_exit_releases_kernel_lock_but_preserves_record(self):
        child, run_id = self.child(self.work1)
        child.kill(); child.wait(timeout=10)
        record = self.root / 'locks' / ('run-' + run_id + '.json')
        self.assertEqual(json.loads(record.read_text(encoding='utf-8'))['status'], 'RUNNING')
        c = Coordinator(self.root / 'locks'); self.addCleanup(c.close)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_RUN_ID'):
            with c.slot(run_id, self.work1, 'branch', 'test'): pass
        with c.slot(str(uuid.uuid4()), self.work1, 'branch', 'test'): pass
        self.assertEqual(json.loads(record.read_text(encoding='utf-8'))['status'], 'ABANDONED_LOCK_RELEASED')

    def test_git_lock_excludes_other_process(self):
        c = Coordinator(self.root / 'locks'); self.addCleanup(c.close)
        code = ('from autonomy.dev_cycle import Coordinator; '
                'c=Coordinator(%r); s=c.lock(3); s.__enter__(); '
                'print("READY",flush=True); __import__("time").sleep(60)' % str(self.root / 'locks'))
        child = subprocess.Popen([sys.executable, '-u', '-c', code], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.stdout.close)
        self.addCleanup(lambda: child.kill() if child.poll() is None else None)
        self.assertEqual(child.stdout.readline().strip(), 'READY')
        with self.assertRaises(Busy):
            with c.lock(3): pass
        child.kill(); child.wait(timeout=10)
        with c.lock(3): pass

    def test_runner_enforces_timeout(self):
        result = subprocess.run([sys.executable, '-m', 'autonomy.dev_cycle', '--root', str(self.root / 'locks'),
            '--run-id', str(uuid.uuid4()), '--worktree', str(self.work1), '--branch', 'b', '--owner', 'test',
            '--timeout', '1', '--', sys.executable, '-c', 'import time;time.sleep(30)'],
            capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 124, result.stderr)


if __name__ == '__main__':
    unittest.main()
