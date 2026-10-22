"""Offline policy and actual local queue persistence / 离线策略与本地持久化。"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomy.network_recovery import classify_failure, recovery_plan, git_sync_plan
from autonomy.task_dispatch import checkpoint, plan_queue, reconcile_queue, CHECKPOINT_FIELDS

NOW = datetime(2026, 10, 22, 15, tzinfo=timezone.utc)


def event(kind='HANDOFF_VALIDATED', digest='a' * 64, at=NOW):
    return {'type': kind, 'evidence_sha256': digest, 'observed_at': at.isoformat(),
            'satisfies': ['WB_NEW_EVIDENCE'], 'verified': True}


def task(**values):
    return dict(id='CITY-LEGACY-RETRY-TERMINALIZATION', status='blocked_external',
                depends_on=['WB_NEW_EVIDENCE'], **values)


class NetworkPolicyTests(unittest.TestCase):
    def plan(self, **kwargs):
        args = dict(operation='runtime', error_code='NETWORK_TIMEOUT', attempt_count=1, now=NOW)
        args.update(kwargs)
        return recovery_plan(**args)

    def test_closed_failure_classification(self):
        for code in ['NETWORK_TIMEOUT', 'PROXY_UNAVAILABLE', 'REMOTE_CONNECTION_RESET', 'DNS_FAILURE']:
            self.assertEqual(classify_failure(error_code=code), code)
        self.assertEqual(classify_failure(http_status=401), 'AUTH_FAILED')
        self.assertEqual(classify_failure(http_status=403), 'AUTH_FAILED')
        self.assertEqual(classify_failure(http_status=429), 'HTTP_429_RATE_LIMIT')
        self.assertEqual(classify_failure(http_status=409), 'GITHUB_CONFLICT')
        self.assertEqual(classify_failure(http_status=401, policy_blocked=True), 'SOURCE_POLICY_BLOCKED')
        self.assertEqual(classify_failure(error_code='SECRET arbitrary traceback'), 'UNKNOWN_NETWORK_FAILURE')

    def test_exponential_positive_jitter_and_budget(self):
        one=self.plan(jitter=0); two=self.plan(attempt_count=2,jitter=0)
        self.assertEqual(one['next_retry_at'], (NOW+timedelta(seconds=15)).isoformat())
        self.assertEqual(two['next_retry_at'], (NOW+timedelta(seconds=30)).isoformat())
        self.assertGreater(self.plan(jitter=1)['next_retry_at'],one['next_retry_at'])
        final=self.plan(attempt_count=4)
        self.assertEqual(final['action'],'DEFERRED');self.assertFalse(final['automatic_replay'])

    def test_retry_after_seconds_and_http_date_not_shortened(self):
        for value in ['120', 120, 'Thu, 22 Oct 2026 15:02:00 GMT']:
            result=self.plan(retry_after=value,jitter=0)
            self.assertEqual(result['next_retry_at'], (NOW+timedelta(seconds=120)).isoformat())
        self.assertEqual(self.plan(retry_after=0,jitter=0)['next_retry_at'],(NOW+timedelta(seconds=15)).isoformat())
        with self.assertRaises(ValueError): self.plan(retry_after='not-a-date')

    def test_auth_policy_conflict_unknown_never_retry(self):
        for error in ['AUTH_FAILED','SOURCE_POLICY_BLOCKED','GITHUB_CONFLICT','UNKNOWN_NETWORK_FAILURE']:
            result=self.plan(error_code=error)
            self.assertEqual(result['action'],'BLOCKED');self.assertFalse(result['automatic_replay'])
            self.assertIsNone(result['next_retry_at'])

    def test_all_mutations_need_reconciliation_and_never_replay(self):
        for operation in ['register','apply','rollback','github-push']:
            for error in ['NETWORK_TIMEOUT','AUTH_FAILED','UNKNOWN_SIDE_EFFECT']:
                result=self.plan(operation=operation,error_code=error)
                self.assertEqual(result['action'],'RECONCILE_STATUS');self.assertFalse(result['automatic_replay'])
        self.assertEqual(self.plan(outcome_unknown=True)['action'],'RECONCILE_STATUS')

    def test_invalid_inputs_fail_closed(self):
        for values in [{'attempt_count':True},{'max_attempts':99},{'jitter':-1},
                       {'jitter':float('nan')},{'base_seconds':0},{'operation':'arbitrary-url'},
                       {'now':NOW.replace(tzinfo=None)},{'retry_after':1e20}]:
            with self.assertRaises(ValueError): self.plan(**values)

    def test_git_success_requires_exact_remote_target(self):
        a='a'*40;b='b'*40
        self.assertTrue(git_sync_plan(target_commit=a,remote_head=a)['push_success'])
        p=git_sync_plan(target_commit=a,remote_head=b,remote_is_ancestor=True)
        self.assertEqual(p['action'],'PUSH_FAST_FORWARD_THEN_VERIFY');self.assertFalse(p['push_success'])
        self.assertEqual(git_sync_plan(target_commit=a,remote_head=b,remote_is_ancestor=False)['action'],'CONFLICT_REQUIRES_RECONCILIATION')
        self.assertEqual(git_sync_plan(target_commit=a,remote_head=None)['action'],'FETCH_AND_RECONCILE')
        self.assertFalse(p['force'])


class QueuePolicyTests(unittest.TestCase):
    def test_verified_event_reactivates_stale_blocked(self):
        old={'tasks':[task()], 'cycles':[]}
        new=plan_queue(old,events=[event()],now=NOW)
        self.assertEqual(new['tasks'][0]['status'],'queued')
        self.assertEqual(old['tasks'][0]['status'],'blocked_external')
        self.assertEqual(len(new['dependency_dispatch']['changes']),1)

    def test_no_event_and_cached_event_do_not_reactivate(self):
        state={'tasks':[task()]}
        self.assertEqual(plan_queue(state,now=NOW)['tasks'][0]['status'],'blocked_external')
        state=plan_queue(state,events=[event()],now=NOW)
        state['tasks'][0]['status']='blocked_external'
        self.assertEqual(plan_queue(state,events=[event()],now=NOW)['tasks'][0]['status'],'blocked_external')
        later=event(digest='b'*64,at=NOW+timedelta(seconds=1))
        self.assertEqual(plan_queue(state,events=[later],now=NOW+timedelta(seconds=1))['tasks'][0]['status'],'queued')

    def test_unknown_side_effect_never_reactivated(self):
        for values in [{'outcome_unknown':True},{'blocked_reason':'UNKNOWN_SIDE_EFFECT'},
                       {'blocked_reason':'UNKNOWN_OUTCOME'},{'blocked_reason':'NEEDS_RECONCILIATION'}]:
            state=plan_queue({'tasks':[task(**values)]},events=[event()],now=NOW)
            self.assertEqual(state['tasks'][0]['status'],'blocked_external')

    def test_legacy_interrupted_lease_without_flag_not_reactivated(self):
        state={'tasks':[task(lease_cycle_id='old')], 'cycles':[{'cycle_id':'old','status':'interrupted'}]}
        self.assertEqual(plan_queue(state,events=[event()],now=NOW)['tasks'][0]['status'],'blocked_external')
        state['tasks'][0]['reconciliation']={'lease_cycle_id':'old'}
        self.assertEqual(plan_queue(state,events=[event()],now=NOW)['tasks'][0]['status'],'queued')

    def test_partial_dependencies_not_runnable(self):
        t=task();t['depends_on'].append('REVIEW_APPROVED')
        self.assertEqual(plan_queue({'tasks':[t]},events=[event()],now=NOW)['tasks'][0]['status'],'blocked_external')

    def test_due_retry_preserves_budget_and_exhaustion_needs_new_event(self):
        retry=recovery_plan(operation='runtime',error_code='DNS_FAILURE',attempt_count=2,now=NOW-timedelta(minutes=2),jitter=0)
        t=task(network_recovery=retry,satisfied_dependencies=['WB_NEW_EVIDENCE'])
        result=plan_queue({'tasks':[t]},now=NOW)['tasks'][0]
        self.assertEqual(result['status'],'queued');self.assertEqual(result['network_recovery']['attempt_count'],2)
        retry['action']='DEFERRED';retry['budget_exhausted']=True
        self.assertEqual(plan_queue({'tasks':[t]},now=NOW)['tasks'][0]['status'],'blocked_external')
        self.assertEqual(plan_queue({'tasks':[t]},events=[event('NETWORK_RESTORED')],now=NOW)['tasks'][0]['network_recovery']['attempt_count'],0)

    def test_future_retry_not_eligible_and_mutation_never_scheduled(self):
        retry=recovery_plan(operation='runtime',error_code='DNS_FAILURE',attempt_count=1,now=NOW)
        t=task(network_recovery=retry)
        self.assertEqual(plan_queue({'tasks':[t]},events=[event()],now=NOW)['tasks'][0]['status'],'blocked_external')
        t['network_recovery']=recovery_plan(operation='apply',error_code='DNS_FAILURE',attempt_count=1,now=NOW)
        self.assertEqual(plan_queue({'tasks':[t]},events=[event()],now=NOW)['tasks'][0]['status'],'blocked_external')

    def test_policy_cannot_be_cleared_by_network_or_auth_event(self):
        for kind in ['NETWORK_RESTORED','AUTHORIZATION_UPDATED']:
            result=plan_queue({'tasks':[task(blocked_reason='SOURCE_POLICY_BLOCKED')]},events=[event(kind)],now=NOW)
            self.assertEqual(result['tasks'][0]['status'],'blocked_external')
        state={'tasks':[task(blocked_reason='AUTH_FAILED')]}
        self.assertEqual(plan_queue(state,events=[event('NETWORK_RESTORED')],now=NOW)['tasks'][0]['status'],'blocked_external')
        self.assertEqual(plan_queue(state,events=[event('AUTHORIZATION_UPDATED')],now=NOW)['tasks'][0]['status'],'queued')

    def test_event_validation_and_out_of_order(self):
        for e in [{**event(),'verified':False},{**event(),'evidence_sha256':'none'},event(at=NOW+timedelta(seconds=1))]:
            with self.assertRaises(ValueError): plan_queue({'tasks':[task()]},events=[e],now=NOW)
        state=plan_queue({'tasks':[task()]},events=[event()],now=NOW);state['tasks'][0]['status']='blocked_external'
        older=event(digest='b'*64,at=NOW-timedelta(seconds=1))
        self.assertEqual(plan_queue(state,events=[older],now=NOW)['tasks'][0]['status'],'blocked_external')

    def test_checkpoint_shape_and_unknowns(self):
        t=checkpoint({'id':'C-NETWORK'},parent_goal='BD_FULL_PRODUCTION')
        self.assertTrue(set(CHECKPOINT_FIELDS).issubset(t));self.assertIsNone(t['completion_evidence'])
        self.assertEqual(t['known_side_effects'],[])

    def test_real_canonical_queue_atomic_persistence_and_no_new_scheduler(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'autonomy/runtime';runtime.mkdir(parents=True)
            path=runtime/'queue.json';path.write_text(json.dumps({'tasks':[task()],'cycles':[]}),encoding='utf-8')
            receipt=reconcile_queue(root,events=[event()],now=NOW)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['tasks'][0]['status'],'queued')
            self.assertEqual(len(receipt['changes']),1)
            self.assertEqual(list(runtime.glob('*.json')),[path])

    def test_failed_atomic_write_keeps_original_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'autonomy/runtime';runtime.mkdir(parents=True)
            path=runtime/'queue.json';original=json.dumps({'tasks':[task()],'cycles':[]});path.write_text(original,encoding='utf-8')
            with patch('autonomy.supervisor.atomic_json',side_effect=OSError('synthetic write failure')):
                with self.assertRaises(OSError): reconcile_queue(root,events=[event()],now=NOW)
            self.assertEqual(path.read_text(encoding='utf-8'),original)


if __name__=='__main__':
    unittest.main()
