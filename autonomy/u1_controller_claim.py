"""Fail-closed claims for the native controller; this module never launches agents.

The caller must use a real native delegation tool and separately verify its
receipts. Queue data is never interpreted as a command or agent prompt.
"""
import re
import uuid
from pathlib import Path

from autonomy.supervisor import atomic_json, exclusive, now, read

REGISTERED = {
    'A-u1-owner-intent-status-review-20261108': 'A',
    'B-u1-host-cleanup-stage-review-20261108': 'B',
}


def _queue(runtime):
    path = Path(runtime) / 'queue.json'
    state = read(path)
    if not isinstance(state, dict) or not isinstance(state.get('tasks'), list):
        raise ValueError('CANONICAL_QUEUE_REQUIRED')
    return path, state


def _task(state, task_id):
    found = [t for t in state['tasks'] if t.get('id') == task_id]
    if len(found) != 1:
        raise ValueError('TASK_ID_NOT_UNIQUE')
    return found[0]


def _unblocked(task, task_id):
    # A concurrent reconciler may have quarantined the task after our claim.
    # Never clear a new unknown outcome or a newly imposed safety fence.
    return (task.get('id') == task_id and task.get('workstream') == REGISTERED[task_id]
            and task.get('role') == 'developer'
            and task.get('outcome_unknown') is False
            and task.get('needs_reassessment', False) is False
            and not task.get('blocked_reason') and not task.get('depends_on')
            and not task.get('lease_cycle_id')
            and task.get('production_execution') is False
            and task.get('allow_dispatch') is False)


def claim_next(runtime, workstream):
    """Claim one registered never-started task; claiming does not launch it.

    A lost claim remains fenced until explicit reconciliation. No timeout or
    lease expiry here authorizes retry of an unknown execution.
    """
    if workstream not in {'A', 'B'}:
        raise ValueError('WORKSTREAM_REJECTED')
    with exclusive(runtime):
        path, state = _queue(runtime)
        for task in state['tasks']:
            task_id = task.get('id')
            if REGISTERED.get(task_id) != workstream:
                continue
            if _task(state, task_id) is not task:
                raise ValueError('TASK_ID_NOT_UNIQUE')
            if (task.get('workstream') != workstream or task.get('role') != 'developer'
                    or task.get('status') != 'pending'
                    or task.get('executor') != 'not_started'
                    or type(task.get('attempts')) is not int or task['attempts'] != 0
                    or task.get('outcome_unknown') is not False
                    or task.get('needs_reassessment', False) is not False
                    or task.get('blocked_reason') or task.get('depends_on')
                    or task.get('lease_cycle_id') or 'controller_claim' in task
                    or task.get('production_execution') is not False
                    or task.get('allow_dispatch') is not False
                    or not re.fullmatch(r'[0-9a-f]{40}', str(task.get('source_commit', '')))):
                continue
            claim_id = str(uuid.uuid4())
            task.update(status='controller_claimed', executor='controller_claimed',
                        controller_claim={'id': claim_id, 'claimed_at': now(),
                                          'source_commit': task['source_commit'],
                                          'execution_started': False})
            atomic_json(path, state)
            return {'task_id': task_id, 'claim_id': claim_id,
                    'source_commit': task['source_commit'], 'execution_started': False}
        return None


def acknowledge_started(runtime, task_id, claim_id, native_agent_id):
    """Record an independently observed native start; this is not a launcher."""
    if (task_id not in REGISTERED or not isinstance(native_agent_id, str)
            or not re.fullmatch(r'/[a-z0-9_/]{1,200}', native_agent_id)):
        raise ValueError('START_RECEIPT_REJECTED')
    with exclusive(runtime):
        path, state = _queue(runtime)
        task = _task(state, task_id)
        claim = task.get('controller_claim')
        if (not _unblocked(task, task_id) or task.get('status') != 'controller_claimed'
                or task.get('executor') != 'controller_claimed'
                or type(task.get('attempts')) is not int or task['attempts'] != 0
                or not isinstance(claim, dict)
                or claim.get('source_commit') != task.get('source_commit')
                or claim.get('id') != claim_id or claim.get('execution_started') is not False):
            raise ValueError('CLAIM_MISMATCH')
        claim.update(execution_started=True, native_agent_id=native_agent_id, started_at=now())
        task.update(status='controller_running', executor='native_subagent', attempts=1)
        atomic_json(path, state)


def record_result(runtime, task_id, claim_id, *, evidence_sha256, candidate_commit=None):
    """Record a received result, never its review or integration approval.

    Missing candidate commit means unknown outcome and remains quarantined.
    The caller must verify the actual result and hash before passing evidence.
    """
    if (task_id not in REGISTERED or not isinstance(evidence_sha256, str)
            or not re.fullmatch(r'[0-9a-f]{64}', evidence_sha256)
            or (candidate_commit is not None and
                (not isinstance(candidate_commit, str) or
                 not re.fullmatch(r'[0-9a-f]{40}', candidate_commit)))):
        raise ValueError('RESULT_RECEIPT_REJECTED')
    with exclusive(runtime):
        path, state = _queue(runtime)
        task = _task(state, task_id)
        claim = task.get('controller_claim')
        if (not _unblocked(task, task_id) or task.get('status') != 'controller_running'
                or task.get('executor') != 'native_subagent'
                or type(task.get('attempts')) is not int or task['attempts'] != 1
                or not isinstance(claim, dict)
                or claim.get('source_commit') != task.get('source_commit')
                or claim.get('id') != claim_id or claim.get('execution_started') is not True):
            raise ValueError('CLAIM_MISMATCH')
        claim.update(result_received_at=now(), evidence_sha256=evidence_sha256)
        if candidate_commit is None:
            # The legacy supervisor does not register these tasks. Its generic
            # unknown recovery must not requeue them into the legacy runner.
            task.update(status='controller_unknown', outcome_unknown=True, needs_reassessment=True)
        else:
            task.update(status='needs_review', candidate_commit=candidate_commit,
                        review_status='NOT_STARTED', outcome_unknown=False)
        atomic_json(path, state)


def quarantine_interrupted(runtime, task_id, claim_id):
    """Fence a possibly interrupted delegation; never assert it did not run.

    This only changes queue state and does not terminate an agent. Even a claim
    whose start was not acknowledged may have launched before a controller
    crash. A trusted operator must inspect actual processes and receipts before
    any subsequent reconciliation; this function does not authorize retries.
    """
    if task_id not in REGISTERED or not isinstance(claim_id, str):
        raise ValueError('CLAIM_MISMATCH')
    with exclusive(runtime):
        path, state = _queue(runtime)
        task = _task(state, task_id)
        claim = task.get('controller_claim')
        if (not isinstance(claim, dict) or claim.get('id') != claim_id
                or claim.get('source_commit') != task.get('source_commit')
                or task.get('status') not in {'controller_claimed', 'controller_running'}
                or task.get('executor') not in {'controller_claimed', 'native_subagent'}):
            raise ValueError('CLAIM_MISMATCH')
        task.update(status='controller_unknown', executor='controller_unknown',
                    outcome_unknown=True, needs_reassessment=True,
                    recovery_reason='CONTROLLER_INTERRUPTED_EXECUTION_UNCERTAIN')
        claim['quarantined_at'] = now()
        atomic_json(path, state)
        return {'task_id': task_id, 'execution_state': 'UNKNOWN', 'retry_allowed': False}
