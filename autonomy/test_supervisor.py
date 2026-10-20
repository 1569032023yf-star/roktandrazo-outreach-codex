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

    def test_crash_lease_recovers_and_failure_reassesses_then_stops(self):
        s.init(self.runtime)
        state = s.read(self.runtime / 'queue.json')
        state['tasks'][0]['status'] = 'running'
        s.atomic_json(self.runtime / 'queue.json', state)
        for _ in range(3):
            s.cycle(self.runtime, runner=lambda *a: {'ok': False, 'reason': 'timeout'})
        task = s.read(self.runtime / 'queue.json')['tasks'][0]
        self.assertEqual(task['recovery_reason'], 'PRIOR_CYCLE_INTERRUPTED')
        self.assertEqual(task['status'], 'blocked')
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
        state['tasks'][0].update(status='running', attempts=3)
        s.atomic_json(self.runtime / 'queue.json', state)
        s.cycle(self.runtime, runner=lambda *a: self.fail('exhausted task must not run'))
        task = s.read(self.runtime / 'queue.json')['tasks'][0]
        self.assertEqual(task['status'], 'blocked')
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
