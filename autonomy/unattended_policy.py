"""Offline proposal only. No scheduler, network, credentials or database access.

Decisions are necessary conditions, never authorization to execute production.
The caller must validate fresh evidence and atomically claim the existing lock
and durable slot before any dispatch. This module deliberately cannot dispatch.
"""
from collections.abc import Mapping

INVENTORY = '1784775229336'
GATES = (
    'approved_change', 'dedicated_nonadmin_identity', 'batch_logon_ready',
    'scoped_acl', 'machine_runtime_ready', 'noninteractive_egress_ready',
    'network_ready', 'old_authority_disabled', 'drain_confirmed',
    'unknown_outcomes_reconciled', 'existing_lock_compatible',
    'durable_slot_ledger_ready', 'audit_ready', 'rollback_ready', 'smtp_disabled',
)


def readiness(evidence):
    """Return fixed reason codes; never echo untrusted evidence or secrets."""
    if not isinstance(evidence, Mapping):
        return ('INVALID_EVIDENCE',)
    reasons = []
    if evidence.get('inventory_id') != INVENTORY:
        reasons.append('INVENTORY_MISMATCH')
    reasons.extend('MISSING_' + key.upper() for key in GATES
                   if evidence.get(key) is not True)
    return tuple(reasons)


def slot_action(state, *, due, readiness_errors):
    """No lease expiry or restart can authorize replay of unknown side effects."""
    if state in ('running', 'unknown'):
        return 'RECONCILE_ONLY'
    if state == 'completed':
        return 'NO_REPLAY'
    if state != 'pending':
        return 'INVALID_STATE'
    if due is not True or readiness_errors != ():
        return 'DEFER'
    return 'REQUIRES_ATOMIC_CLAIM'


def budget_reservation(limit, spent, reserved, requested):
    """Integer units only; unknown effects remain reserved until reconciled.

Caller must persist reservations under the same transaction/lock. This helper
does not reserve funds and must not be used as an execution authorization.
"""
    values = (limit, spent, reserved, requested)
    if any(type(v) is not int or v < 0 for v in values):
        return 'INVALID_BUDGET'
    if requested == 0:
        return 'INVALID_BUDGET'
    return 'WITHIN_CAP' if spent + reserved + requested <= limit else 'CAP_REACHED'
