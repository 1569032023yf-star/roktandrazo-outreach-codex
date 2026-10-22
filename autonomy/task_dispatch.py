"""Event-driven canonical queue adapter / 事件驱动的唯一队列适配器。

No task execution, network or new scheduler. The existing real heartbeat calls
reconcile_queue(root, events=...) after independently validating evidence.
不创建自动化、不启动生产任务；已验证证据由总控传入。
"""
from copy import deepcopy
from datetime import datetime
import re

from autonomy.network_recovery import READ_ONLY_OPERATIONS, utc

EVENT_TYPES = frozenset({'HANDOFF_VALIDATED', 'ISSUE_HANDOFF_VALIDATED',
    'TELEMETRY_CHANGED', 'INVENTORY_RUN_RECORDED', 'RELEASE_REGISTERED',
    'REVIEW_APPROVED', 'NETWORK_RESTORED', 'AUTHORIZATION_UPDATED',
    'CONFLICT_RESOLVED', 'DEPENDENCY_SATISFIED'})
WAITING = frozenset({'blocked', 'blocked_external', 'awaiting_external_evidence',
    'awaiting_independent_reconciliation', 'deferred_network'})
CHECKPOINT_FIELDS = ('task_id', 'parent_goal', 'branch', 'worktree', 'input_commit',
    'current_commit', 'last_verified_step', 'test_receipt', 'review_receipt',
    'release_id', 'operation_id', 'known_side_effects', 'next_action',
    'next_retry_at', 'blocked_reason', 'completion_evidence')


def checkpoint(task, **updates):
    """Complete the persistence shape without inventing evidence."""
    result = deepcopy(task)
    result.update(updates)
    for key in CHECKPOINT_FIELDS:
        result.setdefault(key, [] if key == 'known_side_effects' else None)
    result['task_id'] = result.get('task_id') or result.get('id')
    if not result['task_id']:
        raise ValueError('TASK_ID_REQUIRED')
    return result


def _stamp(value):
    if type(value) is not str:
        raise ValueError('INVALID_EVENT_TIME')
    return utc(datetime.fromisoformat(value))


def _event(event, now):
    if type(event) is not dict or event.get('type') not in EVENT_TYPES or event.get('verified') is not True:
        raise ValueError('UNVERIFIED_EVENT')
    if not re.fullmatch(r'[0-9a-f]{64}', str(event.get('evidence_sha256', ''))):
        raise ValueError('EVENT_EVIDENCE_HASH_REQUIRED')
    stamp = _stamp(event.get('observed_at'))
    if stamp > now:
        raise ValueError('FUTURE_EVENT')
    deps = event.get('satisfies', [])
    if type(deps) is not list or not deps or len(deps) > 32 or any(
        type(dep) is not str or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', dep) for dep in deps):
        raise ValueError('INVALID_DEPENDENCIES')
    return {'type': event['type'], 'evidence_sha256': event['evidence_sha256'],
            'observed_at': stamp.isoformat(), 'satisfies': deps}


def plan_queue(state, *, events=(), now):
    """Reevaluate only validated dependencies; never clear unknown side effects.

    Status changes do not execute work. Per-task seen evidence hashes prevent
    the same cached handoff or telemetry response from granting retry budgets.
    """
    now = utc(now)
    result = deepcopy(state)
    if type(result.get('tasks')) is not list or len(events) > 64:
        raise ValueError('INVALID_QUEUE_OR_EVENTS')
    clean = [_event(event, now) for event in events]
    changes = []
    for task in result['tasks']:
        lease = task.get('lease_cycle_id')
        prior = next((cycle for cycle in result.get('cycles', []) if cycle.get('cycle_id') == lease), None) if lease else None
        unreconciled_lease = (prior and prior.get('status') in {'running', 'failed', 'interrupted', 'unknown'}
                             and task.get('reconciliation', {}).get('lease_cycle_id') != lease)
        if task.get('outcome_unknown') or task.get('blocked_reason') in {
            'UNKNOWN_SIDE_EFFECT', 'UNKNOWN_OUTCOME', 'NEEDS_RECONCILIATION'} or unreconciled_lease:
            continue
        deps = task.get('depends_on', [])
        satisfied = set(task.get('satisfied_dependencies', []))
        seen = task.setdefault('dependency_evidence', {})
        new_types = set()
        for event in clean:
            relevant = set(deps).intersection(event['satisfies'])
            if not relevant:
                continue
            # Reject out-of-order evidence; a stale cached bundle cannot restore
            # a task that a later failure has deferred.
            for dep in relevant:
                prior = seen.get(dep)
                if prior and (_stamp(prior['observed_at']) >= _stamp(event['observed_at']) or
                              prior['evidence_sha256'] == event['evidence_sha256']):
                    continue
                seen[dep] = event
                satisfied.add(dep)
                new_types.add(event['type'])
        task['satisfied_dependencies'] = sorted(satisfied)
        if task.get('status') not in WAITING or not deps or not set(deps).issubset(satisfied):
            continue
        reason = task.get('blocked_reason')
        if reason == 'SOURCE_POLICY_BLOCKED':
            continue
        if reason == 'AUTH_FAILED' and 'AUTHORIZATION_UPDATED' not in new_types:
            continue
        if reason == 'GITHUB_CONFLICT' and 'CONFLICT_RESOLVED' not in new_types:
            continue
        retry = task.get('network_recovery')
        if retry:
            if retry.get('operation') not in READ_ONLY_OPERATIONS or retry.get('action') == 'RECONCILE_STATUS':
                continue
            if retry.get('action') == 'BLOCKED' and not (
                reason == 'AUTH_FAILED' and 'AUTHORIZATION_UPDATED' in new_types):
                continue
            due = task.get('next_retry_at') or retry.get('next_retry_at')
            if due and _stamp(due) > now:
                continue
            if retry.get('budget_exhausted') and not new_types:
                continue
        # An ordinary dependency-blocked task must receive genuinely new evidence.
        # Merely calling the heartbeat again does not make it runnable.
        if not new_types and not (retry and retry.get('action') == 'READ_ONLY_RETRY'):
            continue
        previous = task['status']
        task.update(status='queued', needs_reassessment=False, blocked_reason=None,
                    next_retry_at=None, last_verified_step='DEPENDENCIES_REVALIDATED')
        if retry:
            task['network_recovery'] = {**retry, 'action': 'READY',
                'attempt_count': 0 if retry.get('budget_exhausted') or reason == 'AUTH_FAILED' else retry['attempt_count'],
                'budget_exhausted': False, 'automatic_replay': False, 'next_retry_at': None}
        changes.append({'task_id': task.get('id') or task.get('task_id'),
                        'from_status': previous, 'to_status': 'queued'})
    result['dependency_dispatch'] = {'schema': 'rokt.dependency-dispatch.v1',
        'observed_at': now.isoformat(), 'changes': changes,
        'summary_zh': '仅重评已验证依赖，不执行任务或生产副作用。',
        'summary_en': 'Reevaluate verified dependencies only; execute no task or production effect.'}
    return result


def reconcile_queue(root, *, events=(), now):
    """Use the existing queue lock and atomic writer, never a competing queue."""
    from pathlib import Path
    from autonomy.supervisor import exclusive, read, atomic_json
    runtime = Path(root).resolve() / 'autonomy' / 'runtime'
    with exclusive(runtime):
        path = runtime / 'queue.json'
        state = read(path)
        if state is None:
            raise ValueError('CANONICAL_QUEUE_REQUIRED')
        result = plan_queue(state, events=events, now=now)
        atomic_json(path, result)
    return result['dependency_dispatch']
