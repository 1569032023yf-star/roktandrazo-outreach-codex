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
        (self.root / 'locks').mkdir()
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
        records = list((self.root / 'locks').glob('run-*.json'))
        self.assertEqual(len(records), 1)
        row = json.loads(records[0].read_text(encoding='utf-8'))
        self.assertEqual(row['status'], 'FAILED')
        self.assertEqual(row['command_outcome'], 'TIMED_OUT')
        self.assertEqual(row['command_returncode'], 124)

    def test_lock_file_and_ancestors_cannot_be_replaced_while_pinned(self):
        c = Coordinator(self.root / 'locks'); self.addCleanup(c.close)
        with c.lock(1):
            for source in (c.path, c.root):
                with self.subTest(source=str(source)), self.assertRaises(OSError):
                    source.rename(source.with_name(source.name + '-replaced'))
        # Closing releases identity pins, without deleting the lock/records.
        c.close()
        c.path.rename(c.path.with_name('released.lock'))

    def test_hardlinked_lock_and_metadata_are_rejected_without_victim_write(self):
        locks = self.root / 'locks'
        victim = self.root / 'victim'; victim.write_text('preserve', encoding='utf-8')
        os.link(victim, locks / 'development.lock')
        with self.assertRaisesRegex(ValueError, 'STOP_AND_PRESERVE_INPUT_MUTABLE_REFERENCE_CHANGED'): Coordinator(locks)
        self.assertEqual(victim.read_text(encoding='utf-8'), 'preserve')
        (locks / 'development.lock').unlink()
        c = Coordinator(locks); self.addCleanup(c.close)
        os.link(victim, locks / 'slot-1.json')
        with self.assertRaisesRegex(ValueError, 'STOP_AND_PRESERVE_INPUT_MUTABLE_REFERENCE_CHANGED'):
            with c.slot(str(uuid.uuid4()), self.work1, 'branch', 'test'): pass
        self.assertEqual(victim.read_text(encoding='utf-8'), 'preserve')

    def test_failed_body_preserves_failed_record_and_releases_slot(self):
        c = Coordinator(self.root / 'locks'); self.addCleanup(c.close)
        run_id = str(uuid.uuid4())
        with self.assertRaisesRegex(RuntimeError, 'body failed'):
            with c.slot(run_id, self.work1, 'branch', 'test'):
                raise RuntimeError('body failed')
        record = self.root / 'locks' / ('run-' + run_id + '.json')
        self.assertEqual(json.loads(record.read_text(encoding='utf-8'))['status'], 'FAILED')
        with c.slot(str(uuid.uuid4()), self.work1, 'branch', 'test'): pass

    def test_unknown_tree_cleanup_blocks_automatic_slot_reuse(self):
        c = Coordinator(self.root / 'locks'); self.addCleanup(c.close)
        error = RuntimeError('cleanup uncertain'); error.cleanup_verified = False
        run_id = str(uuid.uuid4())
        with self.assertRaises(RuntimeError):
            with c.slot(run_id, self.work1, 'branch', 'test'):
                raise error
        row = json.loads((self.root / 'locks' / ('run-' + run_id + '.json')).read_text(encoding='utf-8'))
        self.assertEqual(row['status'], 'STOP_AND_PRESERVE')
        with self.assertRaisesRegex(Busy, 'PRIOR_TREE_CLEANUP_UNVERIFIED'):
            with c.slot(str(uuid.uuid4()), self.work1, 'branch', 'test'): pass

    def test_junction_root_rejected_without_creating_lock(self):
        target = self.root / 'target'; target.mkdir()
        link = self.root / 'junction'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            with self.assertRaisesRegex(ValueError, 'STOP_AND_PRESERVE_INPUT_REPARSE_OR_TYPE'): Coordinator(link)
            self.assertFalse((target / 'development.lock').exists())
        finally:
            link.rmdir()

    def test_cli_git_short_lock_runs_actual_git(self):
        import shutil
        git = shutil.which('git')
        self.assertIsNotNone(git)
        result = subprocess.run([sys.executable, '-B', '-m', 'autonomy.dev_cycle',
            '--root', str(self.root / 'locks'), '--git-lock',
            '--worktree', str(Path.cwd()), '--timeout', '10', '--', git,
            'status', '--porcelain', '--untracked-files=no'], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_supervisor_crash_kills_child_and_grandchild_before_reuse(self):
        from autonomy.lock_recovery import process_identity
        marker = self.root / 'tree.json'
        worker = self.root / 'worker.py'
        worker.write_text(
            'import os,subprocess,sys,time,json\n'
            'from pathlib import Path\n'
            'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\n'
            'Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]))\n'
            'time.sleep(60)\n', encoding='utf-8')
        runner = subprocess.Popen([sys.executable, '-B', '-m', 'autonomy.dev_cycle',
            '--root', str(self.root / 'locks'), '--run-id', str(uuid.uuid4()),
            '--worktree', str(self.work1), '--branch', 'test', '--owner', 'test',
            '--timeout', '60', '--', sys.executable, str(worker), str(marker)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(runner.stdout.close); self.addCleanup(runner.stderr.close)
        self.addCleanup(lambda: runner.kill() if runner.poll() is None else None)
        deadline = time.monotonic() + 10
        while not marker.exists() and runner.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(marker.exists(), 'supervised tree did not start')
        pids = json.loads(marker.read_text(encoding='utf-8'))
        self.assertTrue(all(process_identity(pid) is not None for pid in pids))
        runner.kill(); runner.wait(timeout=10)
        deadline = time.monotonic() + 10
        while any(process_identity(pid) is not None for pid in pids) and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(all(process_identity(pid) is None for pid in pids), 'tree survived coordinator crash')
        c = Coordinator(self.root / 'locks'); self.addCleanup(c.close)
        with c.slot(str(uuid.uuid4()), self.work1, 'branch', 'test'): pass


if __name__ == '__main__':
    unittest.main()
