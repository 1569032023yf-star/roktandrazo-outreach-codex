"""Offline signed cancellation-terminal joins; never settlement authority."""
import re
from autonomy.growth_ledger import digest, vector, GrowthError
from autonomy.host_preparation import EvidenceError
from autonomy.unattended_policy import INVENTORY

PROTOCOL = 'rokt.offline-cancel-terminal.v1'
HASHES = frozenset(('runtime_id','slots_id','budget_id','journal_id',
    'lock_token_hash','process_identity_hash','run_id','request_id','claim_token_hash',
    'cancel_identity','cancel_cost_request_id','original_request_id'))
KEYS = HASHES | {'inventory_id','slot','epoch','owner','backend_id','cancel_protocol',
    'cancel_cost_protocol','scope','production_execution'}


def _bound(payload, expected):
    return all(k in payload and type(payload[k]) is type(v) and payload[k] == v
               for k, v in expected.items())


def inspect_cancellation_terminal(consumer, terminal, original_receipt, cost_receipt,
                                  *, now, expected):
    """Expected is an independently established persisted cost binding, not a receipt.

    This joins supplied evidence only. It does not read a ledger, establish its
    freshness, settle money, mutate a journal, recover a lock or call a backend.
    """
    denied = dict(evidence_matches=False, allow_reconcile=False,
        allow_lock_recovery=False, allow_dispatch=False, allow_cancel_dispatch=False,
        production_accepted=False, reason='INVALID_CONTEXT')
    if type(now) is not int or type(expected) is not dict or set(expected) != KEYS:
        return denied
    if any(type(expected[k]) is not str or re.fullmatch('[0-9a-f]{64}', expected[k]) is None for k in HASHES):
        return denied
    if (type(expected['epoch']) is not int or expected['epoch'] < 1 or
        any(type(expected[k]) is not str or not 1 <= len(expected[k]) <= 128 for k in ('slot','owner','backend_id')) or
        not _bound(expected, dict(inventory_id=INVENTORY, cancel_protocol='rokt.offline-cancel-journal.v1',
            cancel_cost_protocol='rokt.offline-cancel-cost.v1',scope='isolated_offline',production_execution=False))):
        return denied
    common = {k:expected[k] for k in ('slot','epoch','owner','run_id')}
    common['request_id'] = expected['original_request_id']
    identity = digest(dict(inventory_id=INVENTORY, **common, claim_token_hash=expected['claim_token_hash']))
    cost_id = digest(dict(cancel_identity=identity, cancel_cost_protocol=expected['cancel_cost_protocol']))
    if expected['cancel_identity'] != identity or expected['request_id'] != cost_id or expected['cancel_cost_request_id'] != cost_id:
        return denied
    try:
        proof = consumer.verify(terminal, kind='offline_cancel_terminal', now=now)
        original = consumer.verify(original_receipt, kind='receipt', now=now)
        cost = consumer.verify(cost_receipt, kind='budget_receipt', now=now)
        outcome = proof.get('cancel_outcome')
        state = {'cancelled':'failed','already_completed':'completed','already_failed':'failed'}.get(outcome) if type(outcome) is str else None
        if state is None or not _bound(proof, dict(expected, cancel_terminal_protocol=PROTOCOL,
                external_drained=True, terminal_confirmed=True)):
            return dict(denied, reason='TERMINAL_REJECTED')
        if (not _bound(original, dict(common, external_drained=True, state=state)) or
            type(original.get('token')) is not str or not 1 <= len(original['token']) <= 128 or
            digest(original['token']) != expected['claim_token_hash']):
            return dict(denied, reason='ORIGINAL_TERMINAL_REJECTED')
        if not _bound(cost, dict(expected, outcome='known', externally_reconciled=True)):
            return dict(denied, reason='INDEPENDENT_COST_RECEIPT_REQUIRED')
        vector(cost['actual'])
    except (EvidenceError, GrowthError, KeyError, TypeError, ValueError):
        return dict(denied, reason='EVIDENCE_REJECTED')
    return dict(denied, evidence_matches=True, reason='MATCH_ONLY_NO_SETTLEMENT_AUTHORITY')
