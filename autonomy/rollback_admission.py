"""Offline rollback-plan admission. Never authorizes dispatch or performs IO."""
import re
from autonomy.host_preparation import EvidenceError
from autonomy.unattended_policy import INVENTORY

BINDINGS = frozenset(('principal_id', 'inventory_id', 'release_sha256',
    'ledger_sha256', 'ledger_schema', 'previous_epoch', 'authority_epoch',
    'executor_sha256', 'exclusive_lock_id'))
FLAGS = ('identity_approved', 'sole_inventory_verified', 'dispatch_stopped',
    'process_tree_drained', 'formal_reconciliation_complete', 'preserve_ledger',
    'executor_reads_current_ledger', 'executor_supports_schema',
    'executor_supports_authority_epoch', 'exclusive_lock_verified')
COUNTS = ('claimed_slots', 'running_slots', 'unknown_slots', 'unknown_budget', 'reserved_budget', 'overrun_budget')


def rollback_admission(consumer, envelope, *, now, expected):
    """Caller supplies trusted current bindings, never values copied from evidence.

    A verified signed observation is necessary but cannot establish collector truth.
    Positive output permits reviewing a rollback plan only, never executing it.
    """
    denied = dict(allow_rollback_plan=False, allow_dispatch=False,
                  reason='UNKNOWN_OR_INVALID_CONTEXT')
    if type(expected) is not dict or set(expected) != BINDINGS:
        return denied
    for key in ('release_sha256', 'ledger_sha256', 'executor_sha256'):
        if type(expected[key]) is not str or re.fullmatch('[0-9a-f]{64}', expected[key]) is None:
            return denied
    for key in ('principal_id', 'exclusive_lock_id'):
        if type(expected[key]) is not str or re.fullmatch('[A-Za-z0-9_-]{1,100}', expected[key]) is None:
            return denied
    if expected['inventory_id'] != INVENTORY or type(expected['inventory_id']) is not type(INVENTORY):
        return denied
    for key in ('ledger_schema', 'previous_epoch', 'authority_epoch'):
        if type(expected[key]) is not int or expected[key] < 1:
            return denied
    if expected['authority_epoch'] <= expected['previous_epoch']:
        return dict(denied, reason='NEW_AUTHORITY_EPOCH_REQUIRED')
    try:
        p = consumer.verify(envelope, kind='rollback_readiness', now=now)
    except EvidenceError:
        return dict(denied, reason='UNVERIFIED_EVIDENCE')
    if any(key not in p or type(p[key]) is not type(value) or p[key] != value
           for key, value in expected.items()):
        return dict(denied, reason='CONTEXT_MISMATCH')
    if any(p.get(key) is not True for key in FLAGS) or p.get('restore_old_database') is not False:
        return dict(denied, reason='REQUIRED_FACT_UNKNOWN_OR_FALSE')
    if any(type(p.get(key)) is not int or p[key] != 0 for key in COUNTS):
        return dict(denied, reason='UNRESOLVED_EFFECTS')
    return dict(allow_rollback_plan=True, allow_dispatch=False, reason='PLAN_ONLY_ADMITTED')
