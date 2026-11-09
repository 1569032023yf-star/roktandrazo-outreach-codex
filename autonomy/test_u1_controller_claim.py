"""Isolated canonical-queue claim and quarantine behavior."""
import json
from pathlib import Path
import tempfile
import unittest

from autonomy import u1_controller_claim as claims


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
        (self.runtime / 'queue.json').write_text(json.dumps({'tasks': tasks, 'cycles': []}),
                                                 encoding='utf-8')

    def saved(self):
        return json.loads((self.runtime / 'queue.json').read_text(encoding='utf-8'))['tasks'][0]

    def test_claim_is_not_execution_and_cannot_be_claimed_twice(self):
        claim = claims.claim_next(self.runtime, 'A')
        self.assertFalse(claim['execution_started'])
        self.assertEqual(self.saved()['status'], 'controller_claimed')
        self.assertIsNone(claims.claim_next(self.runtime, 'A'))
        with self.assertRaises(ValueError):
            claims.acknowledge_started(self.runtime, self.task_id, 'wrong', '/root/a')
        self.assertFalse(self.saved()['controller_claim']['execution_started'])

    def test_start_and_result_require_matching_claim_and_review(self):
        claim = claims.claim_next(self.runtime, 'A')
        token = claim['claim_id']
        claims.acknowledge_started(self.runtime, self.task_id, token, '/root/provider')
        self.assertEqual(self.saved()['status'], 'controller_running')
        with self.assertRaises(ValueError):
            claims.record_result(self.runtime, self.task_id, 'wrong', evidence_sha256='b'*64,
                                 candidate_commit='c'*40)
        claims.record_result(self.runtime, self.task_id, token, evidence_sha256='b'*64,
                             candidate_commit='c'*40)
        self.assertEqual(self.saved()['status'], 'needs_review')
        self.assertEqual(self.saved()['review_status'], 'NOT_STARTED')
        self.assertIsNone(claims.claim_next(self.runtime, 'A'))

    def test_unknown_result_is_quarantined_without_replay(self):
        claim = claims.claim_next(self.runtime, 'A')
        claims.acknowledge_started(self.runtime, self.task_id, claim['claim_id'], '/root/provider')
        claims.record_result(self.runtime, self.task_id, claim['claim_id'], evidence_sha256='b'*64)
        self.assertEqual(self.saved()['status'], 'controller_unknown')
        self.assertTrue(self.saved()['outcome_unknown'])
        self.assertIsNone(claims.claim_next(self.runtime, 'A'))

    def test_concurrent_quarantine_cannot_be_cleared_by_receipt(self):
        claim = claims.claim_next(self.runtime, 'A')
        claims.acknowledge_started(self.runtime, self.task_id, claim['claim_id'], '/root/provider')
        state = json.loads((self.runtime / 'queue.json').read_text(encoding='utf-8'))
        state['tasks'][0]['outcome_unknown'] = True
        (self.runtime / 'queue.json').write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CLAIM_MISMATCH'):
            claims.record_result(self.runtime, self.task_id, claim['claim_id'],
                                 evidence_sha256='b'*64, candidate_commit='c'*40)
        self.assertTrue(self.saved()['outcome_unknown'])
        self.assertEqual(self.saved()['status'], 'controller_running')

    def test_changed_source_cannot_acknowledge_prior_claim(self):
        claim = claims.claim_next(self.runtime, 'A')
        state = json.loads((self.runtime / 'queue.json').read_text(encoding='utf-8'))
        state['tasks'][0]['source_commit'] = 'd'*40
        (self.runtime / 'queue.json').write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CLAIM_MISMATCH'):
            claims.acknowledge_started(self.runtime, self.task_id, claim['claim_id'], '/root/provider')
        self.assertFalse(self.saved()['controller_claim']['execution_started'])

    def test_legacy_recovery_cannot_requeue_controller_unknown(self):
        from autonomy.supervisor import recover_unknown
        claim = claims.claim_next(self.runtime, 'A')
        claims.acknowledge_started(self.runtime, self.task_id, claim['claim_id'], '/root/provider')
        claims.record_result(self.runtime, self.task_id, claim['claim_id'], evidence_sha256='b'*64)
        with self.assertRaisesRegex(ValueError, 'TASK_NOT_QUARANTINED'):
            recover_unknown(self.runtime, self.task_id, lambda _: {
                'read_only': True, 'resolution': 'not_executed', 'evidence': 'fixture'})
        self.assertEqual(self.saved()['status'], 'controller_unknown')

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
        from autonomy.supervisor import exclusive
        with exclusive(self.runtime):
            with self.assertRaises(FileExistsError):
                claims.claim_next(self.runtime, 'A')
        self.assertEqual(self.saved()['status'], 'pending')

    def test_legacy_paths_never_replay_controller_receipts(self):
        from autonomy import supervisor
        markers = [{'controller_claim': v} for v in ({}, None, 'malformed')]
        markers += [{'executor': v} for v in ('controller_claimed', 'controller_running',
                                                'controller_unknown', 'native_subagent')]
        for marker in markers:
            with self.subTest(marker=marker):
                self.write([dict(self.task, **marker)])
                self.assertIsNone(claims.claim_next(self.runtime, 'A'))
                self.write([dict(self.task, status='unknown', outcome_unknown=True, **marker)])
                before = (self.runtime / 'queue.json').read_bytes()
                with self.assertRaisesRegex(ValueError, 'CONTROLLER_RECONCILIATION_REQUIRED'):
                    supervisor.recover_unknown(self.runtime, self.task_id,
                                               lambda _: self.fail('checker must not run'))
                self.assertEqual((self.runtime / 'queue.json').read_bytes(), before)
                self.write([dict(self.task, status='queued', **marker)])
                record = supervisor.cycle(self.runtime, runner=lambda *_: self.fail('must not run'))
                self.assertEqual(record['status'], 'idle')
                self.assertEqual(self.saved()['status'], 'queued')

    def test_duplicate_id_never_recovers_or_runs_either_copy(self):
        from autonomy import supervisor
        plain = dict(self.task, status='unknown', outcome_unknown=True)
        marked = dict(plain, controller_claim={})
        for tasks in ([plain, marked], [marked, plain]):
            with self.subTest(first_marked='controller_claim' in tasks[0]):
                self.write(tasks)
                before = (self.runtime / 'queue.json').read_bytes()
                with self.assertRaisesRegex(ValueError, 'TASK_ID_NOT_UNIQUE'):
                    supervisor.recover_unknown(self.runtime, self.task_id,
                                               lambda _: self.fail('checker must not run'))
                self.assertEqual((self.runtime / 'queue.json').read_bytes(), before)
                self.write([dict(t, status='queued', outcome_unknown=False) for t in tasks])
                record = supervisor.cycle(self.runtime, runner=lambda *_: self.fail('must not run'))
                self.assertEqual(record['status'], 'idle')

    def test_controller_states_stay_out_of_legacy_cycle(self):
        from autonomy import supervisor
        for status in ('controller_claimed', 'controller_running', 'controller_unknown'):
            with self.subTest(status=status):
                self.write([dict(self.task, status=status, controller_claim={'id': 'fixture'})])
                record = supervisor.cycle(self.runtime, runner=lambda *_: self.fail('must not run'))
                self.assertEqual(record['status'], 'idle')
                self.assertEqual(self.saved()['status'], status)


if __name__ == '__main__':
    unittest.main()
