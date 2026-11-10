"""Offline tests for fail-closed controller claims and interruption handling."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from autonomy import u1_controller_claim as claims
from autonomy import supervisor


class ControllerClaimTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.task_id = 'A-u1-owner-intent-status-review-20261108'
        self.task = dict(id=self.task_id, workstream='A', role='developer',
            status='pending', executor='not_started', attempts=0,
            outcome_unknown=False, production_execution=False, allow_dispatch=False,
            source_commit='a' * 40)
        self.write([self.task])

    def write(self, tasks):
        (self.runtime / 'queue.json').write_text(json.dumps({'tasks': tasks, 'cycles': []}), encoding='utf-8')

    def saved(self):
        return json.loads((self.runtime / 'queue.json').read_text(encoding='utf-8'))['tasks'][0]

    def test_claim_is_durable_not_execution_and_cannot_be_claimed_twice(self):
        claim = claims.claim_next(self.runtime, 'A')
        self.assertFalse(claim['execution_started'])
        self.assertEqual(self.saved()['status'], 'controller_claimed')
        self.assertIsNone(claims.claim_next(self.runtime, 'A'))

    def test_forged_start_and_result_never_change_any_state(self):
        claim = claims.claim_next(self.runtime, 'A')
        before = (self.runtime / 'queue.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'NATIVE_RECEIPT_VERIFIER_UNAVAILABLE'):
            claims.acknowledge_started(self.runtime, self.task_id, claim['claim_id'], '/root/fake')
        with self.assertRaisesRegex(RuntimeError, 'NATIVE_RECEIPT_VERIFIER_UNAVAILABLE'):
            claims.record_result(self.runtime, self.task_id, claim['claim_id'],
                                 evidence_sha256='b'*64, candidate_commit='c'*40)
        self.assertEqual((self.runtime / 'queue.json').read_bytes(), before)
        # An older in-flight marker also cannot promote a forged result.
        task = self.saved()
        task.update(status='controller_running', executor='native_subagent', attempts=1)
        task['controller_claim']['execution_started'] = True
        self.write([task])
        before = (self.runtime / 'queue.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'NATIVE_RECEIPT_VERIFIER_UNAVAILABLE'):
            claims.record_result(self.runtime, self.task_id, claim['claim_id'],
                                 evidence_sha256='b'*64, candidate_commit='c'*40)
        self.assertEqual((self.runtime / 'queue.json').read_bytes(), before)

    def test_blocked_unknown_unregistered_or_duplicate_never_claimed(self):
        for change in ({'outcome_unknown': True}, {'needs_reassessment': True},
                       {'blocked_reason': 'UNKNOWN_OUTCOME'}, {'attempts': 1},
                       {'lease_cycle_id': 'prior'}, {'depends_on': ['EVIDENCE']},
                       {'allow_dispatch': True}, {'id': 'unregistered'}):
            with self.subTest(change=change):
                self.write([dict(self.task, **change)])
                self.assertIsNone(claims.claim_next(self.runtime, 'A'))
        self.write([self.task, dict(self.task)])
        with self.assertRaisesRegex(ValueError, 'TASK_ID_NOT_UNIQUE'):
            claims.claim_next(self.runtime, 'A')

    def test_existing_supervisor_lock_prevents_claim(self):
        with supervisor.exclusive(self.runtime):
            with self.assertRaises(FileExistsError):
                claims.claim_next(self.runtime, 'A')
        self.assertEqual(self.saved()['status'], 'pending')

    def test_interrupted_claim_or_running_state_remains_unknown_without_replay(self):
        for running in (False, True):
            with self.subTest(running=running):
                self.write([self.task])
                claim = claims.claim_next(self.runtime, 'A')
                if running:
                    task = self.saved()
                    task.update(status='controller_running', executor='native_subagent', attempts=1)
                    task['controller_claim']['execution_started'] = True
                    self.write([task])
                with self.assertRaisesRegex(ValueError, 'CLAIM_MISMATCH'):
                    claims.quarantine_interrupted(self.runtime, self.task_id, 'wrong')
                result = claims.quarantine_interrupted(self.runtime, self.task_id, claim['claim_id'])
                self.assertEqual(result['execution_state'], 'UNKNOWN')
                self.assertFalse(result['retry_allowed'])
                self.assertEqual(self.saved()['status'], 'controller_unknown')
                self.assertTrue(self.saved()['outcome_unknown'])
                self.assertIsNone(claims.claim_next(self.runtime, 'A'))
                record = supervisor.cycle(self.runtime, runner=lambda *_: self.fail('must not run'))
                self.assertEqual(record['status'], 'idle')
                with self.assertRaises(ValueError):
                    supervisor.recover_unknown(self.runtime, self.task_id, lambda _: self.fail('must not run'))

    def test_real_process_exit_after_claim_keeps_durable_fence(self):
        code = "from autonomy.u1_controller_claim import claim_next; import os,sys; claim_next(sys.argv[1], 'A'); os._exit(73)"
        result = subprocess.run([sys.executable, '-B', '-c', code, str(self.runtime)],
                                timeout=15, capture_output=True)
        self.assertEqual(result.returncode, 73, result.stderr)
        task = self.saved()
        self.assertEqual(task['status'], 'controller_claimed')
        self.assertFalse(task['controller_claim']['execution_started'])
        self.assertIsNone(claims.claim_next(self.runtime, 'A'))
        claims.quarantine_interrupted(self.runtime, self.task_id, task['controller_claim']['id'])
        self.assertEqual(self.saved()['status'], 'controller_unknown')
        self.assertIsNone(claims.claim_next(self.runtime, 'A'))


if __name__ == '__main__':
    unittest.main()
