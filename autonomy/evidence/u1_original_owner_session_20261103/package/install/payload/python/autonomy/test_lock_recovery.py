"""实例锁真实崩溃与保守恢复 / Process-instance crash and conservative recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from autonomy import lock_recovery as l
from autonomy import supervisor as s


class LockRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.lock = self.runtime / 'supervisor.lock'

    def crash(self, unverified=False):
        code = ('import os;from pathlib import Path;from autonomy.lock_recovery import exclusive_lock,mark_tree;'
                'runtime=Path('+repr(str(self.runtime))+');'
                'ctx=exclusive_lock(runtime);ctx.__enter__();'
                + ("mark_tree('unverified');" if unverified else '') + 'os._exit(7)')
        result = subprocess.run([sys.executable, '-c', code], timeout=5, capture_output=True)
        self.assertEqual(result.returncode, 7)
        return json.loads(self.lock.read_text())

    def test_real_crashed_instance_can_be_explicitly_recovered(self):
        state = self.crash()
        self.assertIsNone(l.process_identity(state['pid']))
        self.assertEqual(state['schema_version'], 2)
        self.assertEqual(state['tree_state'], 'not_started')
        with self.assertRaises(FileExistsError):
            with s.exclusive(self.runtime): pass
        result = l.recover_lock(self.runtime, state['token'])
        self.assertTrue(result['recovered'])
        with s.exclusive(self.runtime):
            self.assertTrue(self.lock.exists())
        self.assertFalse(self.lock.exists())

    def test_exited_process_object_with_retained_handle_is_not_live(self):
        process = subprocess.Popen([sys.executable, '-c', 'pass'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            process.wait(timeout=5)
            self.assertIsNone(l.process_identity(process.pid))
        finally:
            if os.name == 'nt': process._handle.Close()

    def test_live_instance_and_wrong_token_never_removed(self):
        with s.exclusive(self.runtime):
            state = json.loads(self.lock.read_text())
            for token in (state['token'], 'wrong'):
                with self.assertRaises(RuntimeError): l.recover_lock(self.runtime, token)
                self.assertTrue(self.lock.exists())

    def test_unverified_tree_crash_stays_blocked(self):
        state = self.crash(unverified=True)
        with self.assertRaisesRegex(RuntimeError, 'ASSOCIATED_TREE_UNVERIFIED'):
            l.recover_lock(self.runtime, state['token'])
        self.assertTrue(self.lock.exists())

    def test_legacy_or_uncertain_identity_stays_blocked(self):
        self.lock.write_text(json.dumps({'pid': 999999, 'started_at': 'old'}))
        with self.assertRaisesRegex(RuntimeError, 'LOCK_IDENTITY_UNPROVEN'):
            l.recover_lock(self.runtime, 'old')
        state = self.crash_after_removal()
        with patch.object(l, 'process_identity', side_effect=OSError('denied')):
            with self.assertRaises(OSError): l.recover_lock(self.runtime, state['token'])
        self.assertTrue(self.lock.exists())

    def crash_after_removal(self):
        self.lock.unlink()
        return self.crash()

    def test_guard_serializes_acquisition_and_recovery(self):
        with l._guard(self.runtime):
            with self.assertRaises(FileExistsError):
                with s.exclusive(self.runtime): pass
            with self.assertRaises(FileExistsError): l.recover_lock(self.runtime, 'x')
        self.assertFalse(self.lock.exists())

    def test_cleanup_error_never_overwrites_main_failure(self):
        primary = ValueError('main')
        original = Path.unlink
        def deny_lock(path, *args, **kwargs):
            if path == self.lock: raise PermissionError('blocked')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', deny_lock):
            with self.assertRaises(ValueError) as caught:
                with s.exclusive(self.runtime): raise primary
        self.assertIs(caught.exception, primary)
        self.assertIn('LOCK_CLEANUP_FAILED', caught.exception.__notes__)

    def test_process_cleanup_state_persists_in_lock(self):
        with self.assertRaisesRegex(RuntimeError, 'ASSOCIATED_TREE_UNVERIFIED'):
            with s.exclusive(self.runtime): l.mark_tree('unverified')
        self.assertEqual(json.loads(self.lock.read_text())['tree_state'], 'unverified')

    def test_verified_closed_releases_normally(self):
        with s.exclusive(self.runtime):
            l.mark_tree('unverified')
            l.mark_tree('verified_closed')
        self.assertFalse(self.lock.exists())

    def test_runner_timeout_metadata_survives_durable_queue_and_no_rerun(self):
        s.init(self.runtime)
        state = s.read(self.runtime/'queue.json')
        state['tasks'] = state['tasks'][:1]
        s.atomic_json(self.runtime/'queue.json', state)
        error = subprocess.TimeoutExpired('sensitive prompt deliberately excluded', 1)
        error.cleanup_verified = True
        error.cleanup_errors = ('OSError',)
        with patch.object(s.shutil, 'which', return_value='codex'), patch.object(s, 'run_tree', side_effect=error):
            result = s.cycle(self.runtime, runner=s.run_agent)
        self.assertEqual(result['outcome']['reason'], 'AGENT_TIMEOUT')
        self.assertTrue(result['outcome']['cleanup_verified'])
        self.assertEqual(result['outcome']['cleanup_errors'], ['OSError'])
        text = (self.runtime/'queue.json').read_text()
        self.assertNotIn('sensitive prompt', text)
        self.assertTrue(json.loads(text)['tasks'][0]['outcome_unknown'])
        second = s.cycle(self.runtime, runner=lambda *args: self.fail('unknown rerun'))
        self.assertEqual(second['status'], 'idle')


    def test_lock_state_write_failure_keeps_timeout_and_lock_quarantined(self):
        s.init(self.runtime)
        queue = s.read(self.runtime/'queue.json')
        queue['tasks'] = queue['tasks'][:1]
        s.atomic_json(self.runtime/'queue.json', queue)
        error = subprocess.TimeoutExpired('secret excluded', 1)
        error.cleanup_verified = True
        error.cleanup_errors = ('OSError',)
        write_state = l._write_state
        def fail_verified(lock, state):
            if state['tree_state'] == 'verified_closed': raise OSError('synthetic fsync error')
            return write_state(lock, state)
        with patch.object(s.shutil, 'which', return_value='codex'), \
                patch.object(s, 'run_tree', side_effect=error), \
                patch.object(l, '_write_state', side_effect=fail_verified):
            with self.assertRaisesRegex(RuntimeError, 'ASSOCIATED_TREE_UNVERIFIED'):
                s.cycle(self.runtime, runner=s.run_agent)
        result = s.read(self.runtime/'queue.json')['cycles'][-1]['outcome']
        self.assertEqual(result['reason'], 'AGENT_TIMEOUT')
        self.assertTrue(result['cleanup_verified'])
        self.assertEqual(result['cleanup_errors'], ['OSError'])
        self.assertTrue(result['lock_state_update_failed'])
        self.assertEqual(result['lock_state_update_error_type'], 'OSError')
        self.assertEqual(result['result'], 'UNKNOWN')
        self.assertEqual(json.loads(self.lock.read_text())['tree_state'], 'unverified')
        with self.assertRaises(FileExistsError):
            s.cycle(self.runtime, runner=lambda *args: self.fail('must not retry'))

    def test_reader_close_classification_survives_durable_queue(self):
        s.init(self.runtime)
        queue = s.read(self.runtime/'queue.json')
        queue['tasks'] = queue['tasks'][:1]
        s.atomic_json(self.runtime/'queue.json', queue)
        from autonomy.process_job import ProcessCleanupError
        error = ProcessCleanupError('text excluded')
        error.cleanup_verified = False
        error.cleanup_errors = ('OUTPUT_READERS_CLEANUP', 'ProcessCleanupError',
                                'OUTPUT_STREAM_CLOSE_FAILED', 'OSError')
        with patch.object(s.shutil, 'which', return_value='codex'), patch.object(s, 'run_tree', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, 'ASSOCIATED_TREE_UNVERIFIED'):
                s.cycle(self.runtime, runner=s.run_agent)
        outcome = s.read(self.runtime/'queue.json')['cycles'][-1]['outcome']
        self.assertFalse(outcome['cleanup_verified'])
        self.assertIn('OUTPUT_STREAM_CLOSE_FAILED', outcome['cleanup_errors'])
        self.assertIn('OSError', outcome['cleanup_errors'])
        self.assertEqual(outcome['result'], 'UNKNOWN')


if __name__ == '__main__': unittest.main()
