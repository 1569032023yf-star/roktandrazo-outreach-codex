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
    """Disabled until an authenticated native start receipt is available.

    A caller-provided string is not proof of a running agent. No queue state is
    read or changed by this compatibility entry point.
    """
    raise RuntimeError('NATIVE_RECEIPT_VERIFIER_UNAVAILABLE')


def record_result(runtime, task_id, claim_id, *, evidence_sha256, candidate_commit=None):
    """Disabled until actual result provenance can be independently verified.

    A hash and a commit-shaped string alone do not prove that work occurred.
    """
    raise RuntimeError('NATIVE_RECEIPT_VERIFIER_UNAVAILABLE')


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
