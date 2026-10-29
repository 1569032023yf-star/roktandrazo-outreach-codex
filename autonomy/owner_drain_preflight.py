"""Read-only join of approved exported bytes and authenticated drain evidence.

No path, liveness probe, lock mutation, settlement, refund or dispatch is exposed.
A positive join is never authority to recover an UNKNOWN owner or its effects.
"""
from contextlib import closing
import hashlib
import json
import re
import sqlite3
from autonomy.growth_snapshot import inspect_snapshot
from autonomy.growth_ledger import digest
from autonomy.host_preparation import EvidenceError
from autonomy.unattended_policy import INVENTORY

CONTEXT = frozenset(('old_lock_sha256','budget_snapshot_sha256','slots_id',
    'budget_id','backend_id','slot','epoch','owner','run_id','request_id','claim_token_hash'))


def _unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('duplicate')
        result[k]=v
    return result


def inspect_owner_drain(consumer,envelope,*,now,expected,lock_bytes,budget_snapshot):
    """Expected hashes/identities must be approved outside the examined envelope.

    Snapshot bytes must be a consistent standalone export. A matching digest
    proves byte identity only; no cross-file atomicity or current OS fact follows.
    """
    denied=dict(evidence_matches=False,allow_lock_recovery=False,
        allow_reconcile=False,allow_dispatch=False,allow_cancel_dispatch=False,
        production_accepted=False,owner_liveness='UNKNOWN',
        reason='INVALID_APPROVED_CONTEXT')
    if type(expected) is not dict or set(expected)!=CONTEXT:return denied
    for k,v in expected.items():
        if k=='epoch':
            if type(v) is not int or v<1:return denied
        elif k in ('backend_id','slot','owner'):
            if type(v) is not str or re.fullmatch('[A-Za-z0-9_:-]{1,128}',v) is None:return denied
        elif type(v) is not str or re.fullmatch('[0-9a-f]{64}',v) is None:return denied
    common={k:expected[k] for k in ('slot','epoch','owner','run_id','request_id')}
    if common['run_id']!=digest(dict(inventory_id=INVENTORY,**{k:common[k] for k in ('slot','epoch','owner')})):
        return denied
    if type(lock_bytes) is not bytes or not 1<=len(lock_bytes)<=4096:
        return dict(denied,reason='INVALID_LOCK_BYTES')
    if hashlib.sha256(lock_bytes).hexdigest()!=expected['old_lock_sha256']:
        return dict(denied,reason='LOCK_HASH_MISMATCH')
    try:
        lock=json.loads(lock_bytes.decode('utf-8'),object_pairs_hook=_unique)
        if type(lock) is not dict or set(lock)!={'schema_version','pid','started_at','process_identity','token','tree_state'}:
            raise ValueError('schema')
        if type(lock['schema_version']) is not int or lock['schema_version']!=2:
            raise ValueError('version')
        if type(lock['pid']) is not int or not 0<lock['pid']<=0xffffffff:
            raise ValueError('pid')
        if type(lock['token']) is not str or re.fullmatch('[0-9a-f]{32}',lock['token']) is None:
            raise ValueError('token')
        if any(type(lock[k]) is not str or not 1<=len(lock[k])<=256 for k in ('started_at','process_identity')):
            raise ValueError('identity')
        if lock['tree_state']!='unverified':raise ValueError('state')
    except (ValueError,TypeError,UnicodeError,RecursionError):
        return dict(denied,reason='LOCK_SCHEMA_REJECTED')
    try:
        proof=consumer.verify(envelope,kind='offline_owner_drain',now=now)
    except EvidenceError:
        return dict(denied,reason='DRAIN_EVIDENCE_REJECTED')
    bound=dict(expected,old_lock_token_hash=digest(lock['token']),
        old_process_identity_hash=digest(lock['process_identity']),
        external_drained=True,scope='isolated_offline',production_execution=False)
    if any(type(proof.get(k)) is not type(v) or proof[k]!=v for k,v in bound.items()):
        return dict(denied,reason='DRAIN_BINDING_MISMATCH')
    inspected=inspect_snapshot(budget_snapshot,expected['budget_snapshot_sha256'])
    if inspected['schema_compatible'] is not True:
        return dict(denied,reason='BUDGET_SNAPSHOT_REJECTED')
    try:
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(budget_snapshot)
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF')
            db.set_progress_handler(lambda:1,100000)
            row=db.execute('SELECT state,binding,claim_hash FROM reservations WHERE id=?',
                           (common['request_id'],)).fetchone()
            if row is None or row[0] not in ('reserved','unknown','overrun'):
                return dict(denied,reason='PERSISTED_CLAIM_UNRESOLVED_REQUIRED')
            binding=json.loads(row[1],object_pairs_hook=_unique)
            target=dict(inventory_id=INVENTORY,**common)
            if (row[2]!=expected['claim_token_hash'] or type(binding) is not dict
                    or set(binding)!=set(target) or any(type(binding[k]) is not type(v) or binding[k]!=v for k,v in target.items())):
                return dict(denied,reason='PERSISTED_CLAIM_MISMATCH')
    except (sqlite3.Error,ValueError,TypeError,RecursionError,MemoryError):
        return dict(denied,reason='PERSISTED_CLAIM_REJECTED')
    return dict(denied,evidence_matches=True,reason='DRAIN_JOIN_ONLY_NO_RECOVERY_AUTHORITY')
