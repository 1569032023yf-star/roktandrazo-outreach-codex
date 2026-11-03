"""Offline joins of already approved standalone slot/budget/cancel snapshots.

No paths, live locks, scheduler, settlement or execution authority are accepted.
A matching bundle never proves cross-file atomicity or current production facts.
"""
from contextlib import contextmanager, closing
import hashlib
import json
import re
import sqlite3
from autonomy.owner_drain_preflight import inspect_owner_drain, CONTEXT, _unique
from autonomy.growth_ledger import digest, vector, GrowthError
from autonomy.host_preparation import EvidenceError
from autonomy.unattended_policy import INVENTORY

ADDED=frozenset(('slots_snapshot_sha256','journal_snapshot_sha256','runtime_id',
                 'journal_id','cancel_identity','cancel_cost_request_id'))
SLOT_SCHEMA=frozenset((
 'CREATE TABLE authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1), epoch INTEGER NOT NULL, owner TEXT NOT NULL)',
 "CREATE TABLE slots (slot TEXT PRIMARY KEY, inventory TEXT NOT NULL CHECK(inventory='1784775229336'), due INTEGER NOT NULL UNIQUE, state TEXT NOT NULL CHECK(state IN ('pending','claimed','running','completed','failed','unknown','deferred')), epoch INTEGER, owner TEXT, token TEXT, receipt TEXT)",
 'CREATE TABLE audit (seq INTEGER PRIMARY KEY, slot TEXT, event TEXT NOT NULL, epoch INTEGER)'))
JOURNAL_SCHEMA=frozenset(("CREATE TABLE cancellations (identity TEXT PRIMARY KEY, binding TEXT NOT NULL, state TEXT NOT NULL CHECK(state='RESERVED_RECONCILE_ONLY'))",))


def _exact(value,expected):
    return (type(value) is dict and set(value)==set(expected) and
            all(type(value[k]) is type(v) and value[k]==v for k,v in expected.items()))


@contextmanager
def _image(raw,expected_sha,schema,version):
    if type(raw) is not bytes or not 100<=len(raw)<=16*1024*1024:
        raise ValueError('size')
    if hashlib.sha256(raw).hexdigest()!=expected_sha or raw[:16]!=b'SQLite format 3\x00' or raw[18:20]!=b'\x01\x01':
        raise ValueError('image')
    size=int.from_bytes(raw[16:18],'big');size=65536 if size==1 else size
    if not 512<=size<=65536 or size&(size-1) or size*int.from_bytes(raw[28:32],'big')!=len(raw) or raw[24:28]!=raw[92:96]:
        raise ValueError('standalone')
    with closing(sqlite3.connect(':memory:')) as db:
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,16*1024*1024)
        db.deserialize(raw);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF')
        db.set_progress_handler(lambda:1,100000)
        rows=db.execute("SELECT type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchall()
        if (db.execute('PRAGMA user_version').fetchone()!=(version,) or
                len(rows)!=len(schema) or any(t!='table' for t,sql in rows) or {sql for t,sql in rows}!=schema):
            raise ValueError('schema')
        if db.execute('PRAGMA integrity_check(1)').fetchall()!=[('ok',)]:raise ValueError('integrity')
        yield db


def inspect_drain_bundle(consumer,envelope,*,now,expected,lock_bytes,budget_snapshot,
                         slots_snapshot,journal_snapshot):
    denied=dict(evidence_matches=False,bundle_matches=False,allow_lock_recovery=False,
        allow_reconcile=False,allow_dispatch=False,allow_cancel_dispatch=False,
        production_accepted=False,owner_liveness='UNKNOWN',reason='INVALID_BUNDLE_CONTEXT')
    if type(expected) is not dict or set(expected)!=CONTEXT|ADDED:return denied
    if any(type(expected[k]) is not str or re.fullmatch('[0-9a-f]{64}',expected[k]) is None for k in ADDED):return denied
    base=inspect_owner_drain(consumer,envelope,now=now,expected={k:expected[k] for k in CONTEXT},
        lock_bytes=lock_bytes,budget_snapshot=budget_snapshot)
    if base['evidence_matches'] is not True:return dict(denied,reason='OWNER_DRAIN_JOIN_REJECTED')
    try:
        proof=consumer.verify(envelope,kind='offline_owner_drain',now=now)
        if any(type(proof.get(k)) is not str or proof[k]!=expected[k] for k in ADDED):
            return dict(denied,reason='BUNDLE_SIGNATURE_BINDING_MISMATCH')
        common={k:expected[k] for k in ('slot','epoch','owner','run_id','request_id')}
        identity=digest(dict(inventory_id=INVENTORY,**common,claim_token_hash=expected['claim_token_hash']))
        cost_id=digest(dict(cancel_identity=identity,cancel_cost_protocol='rokt.offline-cancel-cost.v1'))
        if expected['cancel_identity']!=identity or expected['cancel_cost_request_id']!=cost_id:
            return dict(denied,reason='CANCELLATION_IDENTITY_MISMATCH')
        with _image(slots_snapshot,expected['slots_snapshot_sha256'],SLOT_SCHEMA,0) as db:
            row=db.execute('SELECT inventory,state,epoch,owner,token FROM slots WHERE slot=?',(common['slot'],)).fetchone()
            authority=db.execute('SELECT singleton,epoch,owner FROM authority').fetchall()
            if (row is None or row[0]!=INVENTORY or row[1] not in ('claimed','running','unknown')
                    or type(row[2]) is not int or row[2]!=common['epoch'] or type(row[3]) is not str or row[3]!=common['owner']
                    or type(row[4]) is not str or not 1<=len(row[4])<=128 or digest(row[4])!=expected['claim_token_hash']
                    or len(authority)!=1 or type(authority[0][1]) is not int
                    or authority[0]!=(1,common['epoch'],common['owner'])):
                return dict(denied,reason='SLOT_CLAIM_OR_AUTHORITY_MISMATCH')
        lock=json.loads(lock_bytes,object_pairs_hook=_unique)
        binding=dict(inventory_id=INVENTORY,**common,
            **{k:expected[k] for k in ('runtime_id','slots_id','budget_id','backend_id','journal_id','claim_token_hash')},
            lock_token_hash=digest(lock['token']),process_identity_hash=digest(lock['process_identity']),
            cancel_protocol='rokt.offline-cancel-journal.v1',scope='isolated_offline',production_execution=False,
            cancel_identity=identity,cancel_cost_protocol='rokt.offline-cancel-cost.v1',
            cancel_cost_request_id=cost_id,original_request_id=common['request_id'])
        binding['request_id']=cost_id
        with _image(journal_snapshot,expected['journal_snapshot_sha256'],JOURNAL_SCHEMA,1) as db:
            row=db.execute('SELECT binding,state FROM cancellations WHERE identity=?',(identity,)).fetchone()
            if row is None or type(row[0]) is not str or row[1]!='RESERVED_RECONCILE_ONLY' or not _exact(json.loads(row[0],object_pairs_hook=_unique),binding):
                return dict(denied,reason='JOURNAL_BINDING_MISMATCH')
        # Budget image was already bounded/schema-checked by owner preflight.
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(budget_snapshot);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF')
            db.set_progress_handler(lambda:1,100000)
            row=db.execute('SELECT run,state,claim_hash,binding,amount,charged FROM reservations WHERE id=?',(cost_id,)).fetchone()
            if (row is None or row[:3]!=(common['run_id'],'reserved',expected['claim_token_hash'])
                    or any(type(row[i]) is not str for i in (3,4,5))
                    or not _exact(json.loads(row[3],object_pairs_hook=_unique),binding)):
                return dict(denied,reason='CANCEL_COST_BINDING_MISMATCH')
            amount=vector(json.loads(row[4],object_pairs_hook=_unique));charged=vector(json.loads(row[5],object_pairs_hook=_unique))
            if amount!=charged or amount['wall_seconds']<=0:
                return dict(denied,reason='CANCEL_COST_NOT_FULLY_RESERVED')
    except (EvidenceError,ValueError,TypeError,KeyError,RecursionError,MemoryError,sqlite3.Error,GrowthError):
        return dict(denied,reason='BUNDLE_IMAGE_OR_EVIDENCE_REJECTED')
    return dict(denied,evidence_matches=True,bundle_matches=True,reason='SNAPSHOT_JOINS_ONLY_NO_RECOVERY_AUTHORITY')
