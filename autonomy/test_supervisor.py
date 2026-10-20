"""Offline failure-path tests / 离线失败路径测试。"""
import json
from pathlib import Path
import tempfile
import sys
import os
import time
import unittest
from unittest.mock import patch
from autonomy import supervisor as s


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)

    def test_queue_survives_restart_without_reexecuting_completed_task(self):
        s.init(self.runtime)
        state = s.read(self.runtime / 'queue.json')
        state['tasks'] = state['tasks'][:1]
        s.atomic_json(self.runtime / 'queue.json', state)
        run = lambda *a: {'ok': True, 'reason': 'fixture'}
        one = s.cycle(self.runtime, runner=run)
        two = s.cycle(self.runtime, runner=lambda *a: self.fail('rerun completed task'))
        self.assertEqual(one['status'], 'completed')
        self.assertEqual(two['status'], 'idle')
        self.assertEqual(len(s.read(self.runtime / 'queue.json')['cycles']), 2)

    def test_lock_excludes_another_worker(self):
        with s.exclusive(self.runtime):
            with self.assertRaises(FileExistsError):
                s.cycle(self.runtime)

    def test_crash_lease_is_quarantined_without_retry(self):
        s.init(self.runtime)
        state = s.read(self.runtime / 'queue.json')
        state['tasks'] = state['tasks'][:1]
        state['tasks'][0].update(status='running', attempts=1)
        s.atomic_json(self.runtime / 'queue.json', state)
        for _ in range(3):
            s.cycle(self.runtime, runner=lambda *a: self.fail('unknown must not run'))
        task = s.read(self.runtime / 'queue.json')['tasks'][0]
        self.assertEqual(task['recovery_reason'], 'PRIOR_CYCLE_INTERRUPTED')
        self.assertEqual(task['status'], 'unknown')
        self.assertEqual(task['attempts'], 1)
        self.assertTrue(task['outcome_unknown'])
        self.assertTrue(task['needs_reassessment'])

    def test_exception_text_never_enters_saved_state(self):
        def fail(*a):
            raise RuntimeError('SECRET_VALUE')
        s.cycle(self.runtime, runner=fail)
        self.assertNotIn('SECRET_VALUE', (self.runtime / 'queue.json').read_text(encoding='utf-8'))

    def test_unknown_task_cannot_inject_commands(self):
        with self.assertRaises(ValueError):
            s.task_prompt({'id': 'run arbitrary shell', 'role': 'developer'})

    def test_developer_success_requires_independent_review(self):
        s.init(self.runtime)
        pairs = {'D-sanitized-telemetry-adapter': 'D-telemetry-independent-review',
                 'D-unknown-outcome-quarantine': 'D-unknown-outcome-review',
                 'B-brand-package-integration': 'B-brand-integration-review'}
        for developer, reviewer in pairs.items():
            with self.subTest(developer=developer):
                state = s.read(self.runtime / 'queue.json')
                state['tasks'] = [{'id': developer, 'role': 'developer',
                                   'status': 'queued', 'attempts': 0}]
                s.atomic_json(self.runtime / 'queue.json', state)
                s.cycle(self.runtime, runner=lambda *a: {'ok': True})
                tasks = s.read(self.runtime / 'queue.json')['tasks']
                self.assertEqual(tasks[0]['status'], 'needs_review')
                self.assertEqual(tasks[1]['id'], reviewer)
                self.assertEqual(tasks[1]['status'], 'queued')

    def test_fixed_task_role_cannot_be_escalated(self):
        with self.assertRaises(ValueError):
            s.task_prompt({'id': 'D-supervisor-independent-review', 'role': 'developer'})

    def test_unattended_claim_never_from_self_labeled_cycles(self):
        self.assertFalse(s.two_unattended_cycles([{'source': 'codex_heartbeat'}] * 2))

    def test_agent_timeout_and_incomplete_turn_are_failures(self):
        task = {'id': 'D-supervisor-independent-review', 'role': 'reviewer'}
        with patch.object(s.shutil, 'which', return_value='codex'), patch.object(s, 'run_tree') as run:
            run.side_effect = s.subprocess.TimeoutExpired('codex', 1)
            self.assertEqual(s.run_agent(task, self.runtime)['reason'], 'AGENT_TIMEOUT')
            run.side_effect = None
            run.return_value = s.subprocess.CompletedProcess([], 0, '{}', '')
            self.assertFalse(s.run_agent(task, self.runtime)['ok'])

    def test_agent_explicit_readonly_never_uses_shell(self):
        task = {'id': 'D-supervisor-independent-review', 'role': 'reviewer'}
        final = {'summary_zh': '通过', 'summary_en': 'pass', 'findings': []}
        events = [{'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(final)}},
                  {'type': 'turn.completed'}]
        with patch.object(s.shutil, 'which', return_value='codex'), patch.object(s, 'run_tree') as run:
            run.return_value = s.subprocess.CompletedProcess([], 0, '\n'.join(map(json.dumps, events)), '')
            self.assertTrue(s.run_agent(task, self.runtime)['ok'])
            args = run.call_args.args[0]
            self.assertIn('read-only', args)
            self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', args)
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_interrupted_last_attempt_blocks_with_reassessment(self):
        s.init(self.runtime)
        state = s.read(self.runtime / 'queue.json')
        state['tasks'] = state['tasks'][:1]
        state['tasks'][0].update(status='running', attempts=3)
        s.atomic_json(self.runtime / 'queue.json', state)
        s.cycle(self.runtime, runner=lambda *a: self.fail('exhausted task must not run'))
        task = s.read(self.runtime / 'queue.json')['tasks'][0]
        self.assertEqual(task['status'], 'unknown')
        self.assertTrue(task['needs_reassessment'])

    def test_missing_cycle_receipt_is_reconstructed_without_rerun(self):
        s.init(self.runtime)
        state = s.read(self.runtime / 'queue.json')
        state['tasks'] = state['tasks'][:1]
        s.atomic_json(self.runtime / 'queue.json', state)
        record = s.cycle(self.runtime, runner=lambda *a: {'ok': True})
        receipt = self.runtime / 'cycles' / (record['cycle_id'] + '.json')
        receipt.unlink()
        s.cycle(self.runtime, runner=lambda *a: self.fail('must not rerun'))
        self.assertEqual(s.read(receipt), record)

    def test_standalone_init_respects_worker_lock(self):
        with s.exclusive(self.runtime):
            with self.assertRaises(FileExistsError):
                s.init(self.runtime)

    def single_task(self):
        s.init(self.runtime)
        state = s.read(self.runtime / 'queue.json')
        state['tasks'] = state['tasks'][:1]
        s.atomic_json(self.runtime / 'queue.json', state)

    def test_unknown_failures_execute_once_and_require_explicit_check(self):
        for failure in ('AGENT_TIMEOUT', 'AGENT_INCOMPLETE', 'INVALID_REVIEW_SCHEMA',
                        'exception', 'malformed'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                self.runtime = Path(tmp)
                self.single_task()
                calls = []
                def runner(*args):
                    calls.append(1)
                    if failure == 'exception':
                        raise RuntimeError('SECRET_VALUE')
                    return None if failure == 'malformed' else {'ok': False, 'reason': failure}
                first = s.cycle(self.runtime, runner=runner)
                self.assertEqual(first['outcome']['result'], 'UNKNOWN')
                for _ in range(3):
                    s.cycle(self.runtime, runner=runner)
                self.assertEqual(len(calls), 1)
                task = s.read(self.runtime / 'queue.json')['tasks'][0]
                self.assertEqual(task['status'], 'unknown')
                self.assertEqual(task['attempts'], 1)
                with self.assertRaises(ValueError):
                    s.recover_unknown(self.runtime, task['id'], lambda t: {'resolution': 'not_executed'})
                self.assertEqual(s.read(self.runtime / 'queue.json')['tasks'][0], task)
                s.recover_unknown(self.runtime, task['id'], lambda t: {
                    'read_only': True, 'resolution': 'completed', 'evidence': 'synthetic artifact hash verified'})
                s.cycle(self.runtime, runner=runner)
                self.assertEqual(len(calls), 1)

    def test_atomic_faults_preserve_old_json_and_primary_exception(self):
        path = self.runtime / 'state.json'
        old = {'old': [1, 2, 3]}
        for stage in ('dump', 'flush', 'fsync', 'replace'):
            with self.subTest(stage=stage):
                s.atomic_json(path, old)
                before = path.read_bytes()
                primary = OSError(28, 'synthetic disk full')
                original = s.os.fdopen
                class Handle:
                    def __enter__(self):
                        self.handle = original_handle.__enter__()
                        return self
                    def __exit__(self, *args):
                        return original_handle.__exit__(*args)
                    def write(self, value):
                        return self.handle.write(value)
                    def flush(self):
                        raise primary
                def fdopen(*args, **kwargs):
                    nonlocal original_handle
                    original_handle = original(*args, **kwargs)
                    return Handle()
                original_handle = None
                target = {'dump': (s.json, 'dump'), 'flush': (s.os, 'fdopen'),
                          'fsync': (s.os, 'fsync'), 'replace': (s.os, 'replace')}[stage]
                kwargs = {'side_effect': fdopen} if stage == 'flush' else {'side_effect': primary}
                with patch.object(*target, **kwargs), patch.object(s.os, 'unlink', side_effect=OSError('cleanup')):
                    with self.assertRaises(OSError) as caught:
                        s.atomic_json(path, {'new': True})
                self.assertIs(caught.exception, primary)
                self.assertIn('TEMP_CLEANUP_FAILED', caught.exception.__notes__)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(s.read(path), old)

    def test_legacy_retry_and_marker_changes_cannot_release_unknown(self):
        self.single_task()
        calls = []
        first = s.cycle(self.runtime, runner=lambda *a: calls.append(1) or {'ok': False})
        state = s.read(self.runtime / 'queue.json')
        state['tasks'][0].update(status='queued', outcome_unknown=False,
                                 needs_reassessment=False)
        state['cycles'][0]['status'] = 'failed'
        s.atomic_json(self.runtime / 'queue.json', state)
        s.cycle(self.runtime, runner=lambda *a: self.fail('legacy retry is unknown'))
        task = s.read(self.runtime / 'queue.json')['tasks'][0]
        self.assertEqual(task['status'], 'unknown')
        self.assertEqual(calls, [1])
        s.recover_unknown(self.runtime, task['id'], lambda t: {
            'read_only': True, 'resolution': 'not_executed', 'evidence': 'fixture confirms no effects'})
        s.cycle(self.runtime, runner=lambda *a: calls.append(1) or {'ok': True})
        self.assertEqual(calls, [1, 1])
        self.assertEqual(s.read(self.runtime / 'queue.json')['tasks'][0]['role'], 'reviewer')

    def test_completion_commit_fault_quarantines_durable_lease(self):
        for stage in ('dump', 'flush', 'fsync', 'replace'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                self.runtime = Path(tmp)
                self.single_task()
                calls = []
                write = s.atomic_json
                lease = []
                def injected(path, value):
                    if path.name == 'queue.json' and calls:
                        lease.append(path.read_bytes())
                        primary = OSError(28, stage)
                        if stage == 'flush':
                            original = s.os.fdopen
                            class Wrapper:
                                def __enter__(self):
                                    self.handle = handle.__enter__()
                                    return self
                                def __exit__(self, *args):
                                    return handle.__exit__(*args)
                                def write(self, text):
                                    return self.handle.write(text)
                                def flush(self):
                                    raise primary
                            handle = None
                            def opened(*args, **kwargs):
                                nonlocal handle
                                handle = original(*args, **kwargs)
                                return Wrapper()
                            with patch.object(s.os, 'fdopen', side_effect=opened):
                                return write(path, value)
                        target = {'dump': (s.json, 'dump'), 'fsync': (s.os, 'fsync'),
                                  'replace': (s.os, 'replace')}[stage]
                        with patch.object(*target, side_effect=primary):
                            return write(path, value)
                    return write(path, value)
                def runner(*args):
                    calls.append(1)
                    return {'ok': True}
                with patch.object(s, 'atomic_json', side_effect=injected):
                    with self.assertRaises(OSError) as caught:
                        s.cycle(self.runtime, runner=runner)
                self.assertIn('QUEUE_COMMIT_FAILED_OUTCOME_UNKNOWN', caught.exception.__notes__)
                self.assertEqual((self.runtime / 'queue.json').read_bytes(), lease[0])
                self.assertEqual(s.read(self.runtime / 'queue.json')['tasks'][0]['status'], 'running')
                self.assertFalse((self.runtime / 'cycles').exists())
                for _ in range(2):
                    s.cycle(self.runtime, runner=runner)
                self.assertEqual(len(calls), 1)
                self.assertEqual(s.read(self.runtime / 'queue.json')['tasks'][0]['status'], 'unknown')

    def test_receipt_failure_repairs_only_missing_or_inconsistent_receipts(self):
        self.single_task()
        write = s.atomic_json
        calls = []
        def injected(path, value):
            if path.parent.name == 'cycles':
                raise OSError(28, 'receipt')
            return write(path, value)
        with patch.object(s, 'atomic_json', side_effect=injected):
            with self.assertRaises(OSError) as caught:
                s.cycle(self.runtime, runner=lambda *a: calls.append(1) or {'ok': True})
        self.assertIn('QUEUE_COMMITTED_RECEIPT_PENDING', caught.exception.__notes__)
        state = s.read(self.runtime / 'queue.json')
        self.assertEqual(state['tasks'][0]['status'], 'completed')
        record = state['cycles'][0]
        receipt = self.runtime / 'cycles' / (record['cycle_id'] + '.json')
        s.cycle(self.runtime, runner=lambda *a: self.fail('receipt failure cannot rerun'))
        self.assertEqual(calls, [1])
        self.assertEqual(s.read(receipt), record)
        with patch.object(s, 'atomic_json', wraps=write) as writes:
            s.reconcile(self.runtime, s.read(self.runtime / 'queue.json'))
            writes.assert_not_called()
        write(receipt, {'wrong': True})
        with patch.object(s, 'atomic_json', wraps=write) as writes:
            s.reconcile(self.runtime, s.read(self.runtime / 'queue.json'))
            writes.assert_called_once_with(receipt, record)

    def test_actual_process_timeout_kills_descendant_before_return(self):
        marker = self.runtime / 'escaped.txt'
        child = 'import time,pathlib;time.sleep(2);pathlib.Path(' + repr(str(marker)) + ').write_text("escaped")'
        parent = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",' + repr(child) + ']);time.sleep(30)'
        with self.assertRaises(s.subprocess.TimeoutExpired):
            s.run_tree([sys.executable, '-c', parent], timeout=0.4)
        time.sleep(2.2)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
