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
            if active[1].get('tree_state') == 'verified_closed' and not os.path.lexists(lock_recovery._tree_fence(lock)):
                lock_recovery._create_tree_fence(lock,active[1]['token'])
            active[1].update(tree_state='unverified',recovery_only=True,recovery_required=True)
            lock_recovery._write_state(lock,active[1])
        prepare()
        yield
        return
    old=json.loads(raw)
    if (type(old) is not dict or old.get('schema_version')!=3 or
        type(old.get('pid')) is not int or old['pid']<=0 or
        type(old.get('token')) is not str or not old['token'] or
        type(old.get('process_identity')) is not str or not old['process_identity'] or
        old.get('tree_state') not in ('unverified','verified_closed')):
        raise AdapterError('RECOVERY_LOCK_IDENTITY_REJECTED')
    with lock_recovery._guard(adapter.runtime):
        if lock.read_bytes()!=raw:raise AdapterError('RECOVERY_LOCK_CHANGED')
        if lock_recovery.process_identity(old['pid'])==old['process_identity']:
            raise AdapterError('RECOVERY_OWNER_STILL_ALIVE')
        if old['tree_state'] == 'verified_closed' and not os.path.lexists(lock_recovery._tree_fence(lock)):
            lock_recovery._create_tree_fence(lock,old['token'])
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
    # Recovery also mutates a separate recovery log and adopts an owner lock.
    # Until every ledger and both journal identities are bound for that whole
    # cross-store operation, do not consume receipts or alter the existing fence.
    return dict(outcome='UNKNOWN_RECONCILE_ONLY',allow_dispatch=False,
                allow_cancel_dispatch=False,production_execution=False)
