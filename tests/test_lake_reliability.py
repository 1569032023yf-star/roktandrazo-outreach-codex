from datetime import timedelta
import json
import unittest
from tests.test_acceleration_pipeline import NOW, event, task
from tests.test_safe_authority import fixture
from autonomy.network_recovery import recovery_plan
from autonomy.task_dispatch import plan_queue
from autonomy.safe_authority import diagnose_safe_readings, consume_safe_authority

class ReliabilityRegressionTests(unittest.TestCase):
    def test_local_backoff_cap_and_server_minimum(self):
        for jitter in (0, 0.5, 1):
            for retry_after, expected in ((None, 60), (120, 120)):
                result = recovery_plan(operation='runtime', error_code='NETWORK_TIMEOUT',
                    attempt_count=3, now=NOW, max_seconds=60, jitter=jitter, retry_after=retry_after)
                self.assertEqual(result['next_retry_at'], (NOW + timedelta(seconds=expected)).isoformat())

    def test_unrecognized_lease_outcome_never_reactivated(self):
        for status in (None, 'timeout', 'cancelled', 'partial', 'UNKNOWN'):
            state = {'tasks': [task(lease_cycle_id='old')],
                     'cycles': [{'cycle_id': 'old', 'status': status}]}
            for _ in range(3):
                state = plan_queue(state, events=[event()], now=NOW)
                self.assertEqual(state['tasks'][0]['status'], 'blocked_external')
                self.assertNotIn('dependency_evidence', state['tasks'][0])

    def test_completed_lease_remains_eligible(self):
        state = {'tasks': [task(lease_cycle_id='old')],
                 'cycles': [{'cycle_id': 'old', 'status': 'completed'}]}
        self.assertEqual(plan_queue(state, events=[event()], now=NOW)['tasks'][0]['status'], 'queued')

    def diagnose(self, data):
        return diagnose_safe_readings(data, approved_channel='rokt-deploy-channel')

    def test_safe_delta_is_not_growth_or_root_cause(self):
        data = fixture()
        data['response']['readings'][0].update(candidate_rows=57, unique_organizations=55)
        data['response']['reading_agreement'] = False
        result = self.diagnose(data)
        self.assertEqual(result['candidate_rows_delta'], -1)
        self.assertEqual(result['unique_organizations_delta'], 1)
        self.assertEqual(result['duplicate_row_excess_delta'], -2)
        self.assertEqual(result['root_cause'], 'UNKNOWN')
        self.assertEqual(result['safe_net_growth'], 'UNKNOWN')
        self.assertEqual(result['current_safe'], 'UNKNOWN')
        with self.assertRaises(ValueError):
            consume_safe_authority(data, approved_channel='rokt-deploy-channel', now=NOW)

    def test_equal_counts_do_not_establish_acceptance(self):
        result = self.diagnose(fixture())
        self.assertEqual(result['signals'], [])
        self.assertEqual(result['current_safe'], 'UNKNOWN')

    def test_diagnostic_redaction_and_conflicting_flag(self):
        data = fixture()
        secret = 'sensitive-synthetic-canary'
        data['response']['failure_reason'] = secret
        data['response']['readings'][1]['customer'] = secret
        data['response']['reading_agreement'] = False
        result = self.diagnose(data)
        self.assertNotIn(secret, json.dumps(result))
        self.assertIn('DECLARED_AGREEMENT_CONFLICT', result['signals'])

    def test_malformed_diagnostics_rejected(self):
        for value in (True, -1, 1.5, '56', 2**63):
            data = fixture()
            data['response']['readings'][0]['unique_organizations'] = value
            with self.assertRaises(ValueError):
                self.diagnose(data)
        with self.assertRaisesRegex(ValueError, 'UNAPPROVED_SOURCE'):
            diagnose_safe_readings(fixture())
        data = fixture()
        data['response']['readings'][1]['sampling_time'] = data['response']['readings'][0]['sampling_time']
        with self.assertRaisesRegex(ValueError, 'INVALID_READINGS_ORDER'):
            self.diagnose(data)
