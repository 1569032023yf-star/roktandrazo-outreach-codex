"""Explicit offline cancellation settlement; never a cancellation dispatcher.

The original journal is immutable. A separate FULL-sync recovery log makes
partial cross-database progress resumable with exactly the same signed facts.
"""
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from autonomy import lock_recovery
from autonomy.cancellation_terminal import inspect_cancellation_terminal
from autonomy.growth_ledger import digest, vector
from autonomy.single_slot_adapter import AdapterError, CancellationJournal, CANCEL_SCHEMA, path_id
from autonomy.unattended_policy import INVENTORY

PROTOCOL = 'rokt.offline-cancel-recovery.v1'
SCHEMA = "CREATE TABLE recoveries (identity TEXT PRIMARY KEY, binding TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('PREPARED','COMPLETED')))"
HANDOFF_SCHEMA = "CREATE TABLE handoffs (lock_sha256 TEXT PRIMARY KEY, original_lock TEXT NOT NULL)"


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _db(path):
    return closing(sqlite3.connect(Path(path).resolve(strict=True).as_uri()+'?mode=ro', uri=True))


def _record(path, identity, binding, state, fault, raw):
    with closing(sqlite3.connect(path, timeout=5, isolation_level=None)) as db:
        db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
        try:
            objects=db.execute("SELECT type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' ORDER BY name").fetchall()
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if not objects and version==0:
                db.execute(SCHEMA);db.execute(HANDOFF_SCHEMA);db.execute('PRAGMA user_version=1')
            elif objects != [('table',HANDOFF_SCHEMA),('table',SCHEMA)] or version!=1:
                raise AdapterError('RECOVERY_SCHEMA_REJECTED')
            encoded=json.dumps(binding,sort_keys=True,separators=(',',':'))
            old=db.execute('SELECT binding,state FROM recoveries WHERE identity=?',(identity,)).fetchone()
            if old and old[0]!=encoded:raise AdapterError('RECOVERY_RECEIPT_CONFLICT')
            db.execute('INSERT OR IGNORE INTO handoffs VALUES (?,?)',(_hash(raw),raw.decode('utf-8')))
            if old is None:db.execute('INSERT INTO recoveries VALUES (?,?,?)',(identity,encoded,state))
            elif state=='COMPLETED':db.execute("UPDATE recoveries SET state='COMPLETED' WHERE identity=?",(identity,))
            fault('before_'+state.lower()+'_commit');db.commit();fault('after_'+state.lower()+'_commit')
            return old[1] if old else None
        except BaseException:
            db.rollback();raise


@contextmanager
def _owner(adapter, authorization, raw, expected, prepare):
    """Adopt a dead exact lock only under explicit signed recovery authority.

    No timeout inference or PID-only takeover. Uncertain liveness fails closed.
    The immutable token is retained; this context cannot authorize dispatch.
    """
    lock=adapter.runtime/'supervisor.lock'
    active=lock_recovery._ACTIVE_LEASE.get()
    authority=adapter._verify(authorization,'offline_cancel_recovery')
    adapter._bound(authority,expected)
    if active is not None:
        adapter._lock()
        with lock_recovery._guard(adapter.runtime):
            if lock.read_bytes()!=raw:raise AdapterError('RECOVERY_LOCK_CHANGED')
            active[1].update(tree_state='unverified',recovery_only=True,recovery_required=True)
            lock_recovery._write_state(lock,active[1])
        prepare()
        yield
        return
    old=json.loads(raw)
    if (type(old) is not dict or old.get('schema_version')!=2 or
        type(old.get('pid')) is not int or old['pid']<=0 or
        type(old.get('token')) is not str or not old['token'] or
        type(old.get('process_identity')) is not str or not old['process_identity'] or
        old.get('tree_state') not in ('unverified','verified_closed')):
        raise AdapterError('RECOVERY_LOCK_IDENTITY_REJECTED')
    with lock_recovery._guard(adapter.runtime):
        if lock.read_bytes()!=raw:raise AdapterError('RECOVERY_LOCK_CHANGED')
        if lock_recovery.process_identity(old['pid'])==old['process_identity']:
            raise AdapterError('RECOVERY_OWNER_STILL_ALIVE')
        prepare()
        owned=dict(old,pid=os.getpid(),process_identity=lock_recovery.process_identity(os.getpid()),
                   tree_state='unverified',recovery_only=True,recovery_required=True)
        if not owned['process_identity']:raise AdapterError('RECOVERY_PROCESS_UNAVAILABLE')
        lock_recovery._write_state(lock,owned)
    token=lock_recovery._ACTIVE_LEASE.set((lock,owned))
    try:
        yield
    finally:
        lock_recovery._ACTIVE_LEASE.reset(token)
        # Keep even a completed lock for the existing explicit recover_lock API.
        # A live recovery process cannot be mistaken for an abandoned owner.


def recover_cancellation(adapter, authorization, terminal, original_receipt,
        original_budget_receipt, cost_receipt, *, recovery_path, fault=None):
    """Only isolate-approved, signed reconciliation of an existing operation.

    Valid signatures do not establish real production truth. Production trust,
    backend cancellation and Windows installation are outside this API.
    """
    fault=fault or (lambda phase:None)
    if adapter.target is None or adapter.consumer is None:
        raise AdapterError('OFFLINE_BACKEND_NOT_CONFIGURED')
    if (path_id(adapter.runtime)!=adapter.ids['runtime_id'] or
        path_id(adapter.target.runtime)!=adapter.ids['runtime_id'] or
        path_id(adapter.slots.path)!=adapter.ids['slots_id'] or
        path_id(adapter.target.slots_path)!=adapter.ids['slots_id'] or
        path_id(adapter.budget.path)!=adapter.ids['budget_id'] or
        path_id(adapter.target.budget_path)!=adapter.ids['budget_id']):
        raise AdapterError('LEDGER_TARGET_MISMATCH')
    stat=adapter.runtime.stat()
    if (stat.st_dev,stat.st_ino)!=adapter.runtime_identity:
        raise AdapterError('RUNTIME_IDENTITY_MISMATCH')
    denied=dict(outcome='UNKNOWN_RECONCILE_ONLY',allow_dispatch=False,
                allow_cancel_dispatch=False,production_execution=False)
    if type(adapter.cancellation_journal) is not CancellationJournal:
        raise AdapterError('CANCEL_JOURNAL_NOT_CONFIGURED')
    journal=adapter.cancellation_journal
    protected=(adapter.slots.path,adapter.budget.path,adapter.runtime/'supervisor.lock')
    journal_path=journal.checked_path(protected)
    path=CancellationJournal(recovery_path).checked_path((*protected,journal_path))
    raw=(adapter.runtime/'supervisor.lock').read_bytes()
    # Context is read from durable intent, never supplied by a terminal receipt.
    term=adapter._verify(terminal,'offline_cancel_terminal')
    identity=term.get('cancel_identity')
    with _db(journal_path) as db:
        if (db.execute('PRAGMA user_version').fetchone()[0]!=1 or
            db.execute("SELECT type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchall()!=[('table',CANCEL_SCHEMA)]):
            raise AdapterError('CANCEL_JOURNAL_SCHEMA_REJECTED')
        row=db.execute('SELECT binding,state FROM cancellations WHERE identity=?',(identity,)).fetchone()
    if row is None or row[1]!='RESERVED_RECONCILE_ONLY':raise AdapterError('CANCEL_INTENT_REQUIRED')
    binding=json.loads(row[0])
    adapter._bound(binding,dict(adapter.ids,inventory_id=INVENTORY,
        journal_id=_hash(os.path.normcase(str(journal_path)).encode()),scope='isolated_offline',production_execution=False))
    original_lock=json.loads(raw)
    if (type(original_lock.get('token')) is not str or
            digest(original_lock['token'])!=binding.get('lock_token_hash')):
        raise AdapterError('RECOVERY_ORIGINAL_LOCK_TOKEN_MISMATCH')
    if original_lock.get('recovery_only') is True:
        if original_lock.get('recovery_required') is not True:
            raise AdapterError('RECOVERY_LOCK_CONTEXT_REJECTED')
    elif (type(original_lock.get('process_identity')) is not str or
            digest(original_lock['process_identity'])!=binding.get('process_identity_hash')):
        raise AdapterError('RECOVERY_ORIGINAL_PROCESS_IDENTITY_MISMATCH')
    now=adapter._now()
    proof=inspect_cancellation_terminal(adapter.consumer,terminal,original_receipt,
        cost_receipt,now=now,expected=binding)
    if not proof['evidence_matches']:raise AdapterError('CANCEL_TERMINAL_REJECTED')
    sr=adapter._verify(original_receipt,'receipt')
    br=adapter._verify(original_budget_receipt,'budget_receipt')
    cr=adapter._verify(cost_receipt,'budget_receipt')
    common={k:binding[k] for k in ('slot','epoch','owner','run_id')}
    common['request_id']=binding['original_request_id']
    adapter._bound(br,dict(common,claim_token_hash=binding['claim_token_hash'],
        outcome='known',externally_reconciled=True))
    vector(br['actual'])
    with _db(adapter.slots.path) as db:
        actual=db.execute('SELECT epoch,owner,token FROM slots WHERE slot=?',(common['slot'],)).fetchone()
    if actual!=(common['epoch'],common['owner'],sr['token']):raise AdapterError('RECOVERY_CLAIM_MISMATCH')
    with adapter.budget.tx() as db:
        for rid,expected in ((common['request_id'],dict(inventory_id=INVENTORY,**common)),
                             (binding['cancel_cost_request_id'],binding)):
            r=db.execute('SELECT binding,claim_hash,state FROM reservations WHERE id=?',(rid,)).fetchone()
            if r is None or json.loads(r['binding'])!=expected or r['claim_hash']!=binding['claim_token_hash']:
                raise AdapterError('RECOVERY_BUDGET_MISMATCH')
            if r['state']=='overrun':raise AdapterError('RECOVERY_COST_OVERRUN')
    fixed=dict(binding_hash=digest(binding),receipts_hash=digest([term,sr,br,cr]),
               recovery_id=_hash(os.path.normcase(str(path)).encode()),protocol=PROTOCOL)
    authority=dict(fixed,**adapter.ids,inventory_id=INVENTORY,scope='isolated_offline',
        production_execution=False,old_lock_sha256=_hash(raw),
        recovery_process_identity_hash=digest(lock_recovery.process_identity(os.getpid())))
    old=[]
    def prepare():
        old.append(_record(str(path),identity,fixed,'PREPARED',fault,raw))
    try:
        with _owner(adapter,authorization,raw,authority,prepare):
            try:
                # Fence before any durable progress, including a completed duplicate.
                lock_recovery.mark_tree('unverified')
                fault('after_prepared')
                adapter._lock()
                slot=adapter.slots.reconcile(common['slot'],sr['state'],original_receipt,
                    now=now,epoch=common['epoch'],owner=common['owner'])
                if any(r[2] in ('claimed','running','unknown') for r in adapter.slots.snapshot()):
                    raise AdapterError('OTHER_EXECUTION_UNRESOLVED')
                fee=adapter.budget.settle(cost_receipt,now=now);fault('after_cost_settled')
                original=adapter.budget.settle(original_budget_receipt,now=now);fault('after_original_settled')
                if fee not in ('SETTLED','DUPLICATE') or original not in ('SETTLED','DUPLICATE'):
                    raise AdapterError('RECOVERY_COST_OVERRUN')
                _record(str(path),identity,fixed,'COMPLETED',fault,raw)
                fault('before_verified_closed')
                lock_recovery.mark_tree('verified_closed')
                return dict(denied,outcome='DUPLICATE_COMPLETED' if old[0]=='COMPLETED' else 'COMPLETED',
                            slot_result=slot,cost_result=fee,budget_result=original)
            except Exception:
                return denied
    except (OSError,sqlite3.Error):
        return denied
