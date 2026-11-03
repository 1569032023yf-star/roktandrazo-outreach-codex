"""Read-only terminal proofs joined to authenticated standalone ledger images.

No snapshot freshness, cross-file atomicity or recovery authority is implied.
"""
import json
import sqlite3
from autonomy.drain_bundle_preflight import inspect_drain_bundle, _image, JOURNAL_SCHEMA
from autonomy.owner_drain_preflight import _unique
from autonomy.cancellation_terminal import inspect_cancellation_terminal
from autonomy.host_preparation import EvidenceError


def inspect_cancellation_terminal_bundle(consumer, drain, terminal, original_receipt,
        cost_receipt, *, now, expected, lock_bytes, budget_snapshot,
        slots_snapshot, journal_snapshot):
    denied = dict(evidence_matches=False, bundle_matches=False,
        allow_reconcile=False, allow_lock_recovery=False, allow_dispatch=False,
        allow_cancel_dispatch=False, production_accepted=False,
        owner_liveness='UNKNOWN', reason='PERSISTED_BUNDLE_REJECTED')
    base = inspect_drain_bundle(consumer, drain, now=now, expected=expected,
        lock_bytes=lock_bytes, budget_snapshot=budget_snapshot,
        slots_snapshot=slots_snapshot, journal_snapshot=journal_snapshot)
    if base['bundle_matches'] is not True:
        return dict(denied, bundle_reason=base['reason'])
    try:
        # Use the actual binding from the already authenticated, schema-checked
        # journal image. Never let the terminal receipt supply its own context.
        with _image(journal_snapshot, expected['journal_snapshot_sha256'], JOURNAL_SCHEMA, 1) as db:
            row = db.execute('SELECT binding FROM cancellations WHERE identity=?',
                             (expected['cancel_identity'],)).fetchone()
            binding = json.loads(row[0], object_pairs_hook=_unique)
        proof = inspect_cancellation_terminal(consumer, terminal, original_receipt,
            cost_receipt, now=now, expected=binding)
    except (EvidenceError, ValueError, TypeError, KeyError, IndexError,
            RecursionError, MemoryError, sqlite3.Error):
        return dict(denied, reason='JOURNAL_OR_TERMINAL_REJECTED')
    if proof['evidence_matches'] is not True:
        return dict(denied, reason='PERSISTED_TERMINAL_JOIN_REJECTED', terminal_reason=proof['reason'])
    return dict(denied, evidence_matches=True, bundle_matches=True,
                reason='SNAPSHOT_TERMINAL_MATCH_ONLY_NO_SETTLEMENT_AUTHORITY')
