"""Offline-only single-slot composition. No scheduler or production backend.

The injected backend must enforce its own bounded execution. A Python callable
cannot be forcibly interrupted here: one-call and late-result rejection are the
only local time guarantees. Default configuration denies all execution.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
import sqlite3
from contextlib import closing

from autonomy import lock_recovery
from autonomy.growth_ledger import digest
from autonomy.unattended_policy import INVENTORY, GATES


BACKEND_PROTOCOL = 'rokt.offline-backend.v1'
OPERATION_SCHEMA = 'rokt.offline-operation.v1'


class AdapterError(RuntimeError):
    pass


def path_id(path):
    return hashlib.sha256(os.path.normcase(str(Path(path).resolve(strict=True))).encode()).hexdigest()


CANCEL_PROTOCOL = 'rokt.offline-cancel-journal.v1'
CANCEL_COST_PROTOCOL = 'rokt.offline-cancel-cost.v1'
CANCEL_SCHEMA = "CREATE TABLE cancellations (identity TEXT PRIMARY KEY, binding TEXT NOT NULL, state TEXT NOT NULL CHECK(state='RESERVED_RECONCILE_ONLY'))"


class CancellationJournal:
    """Reservation only: no cancellation dispatcher, expiry, refund or replay."""
    def __init__(self, path, *, fault=None):
        self.path=Path(path)
        self.fault=fault or (lambda stage: None)

    def checked_path(self, protected):
        path=self.path.resolve(strict=False)
        if not path.parent.is_dir():raise AdapterError('CANCEL_JOURNAL_PATH_REJECTED')
        for item in protected:
            other=Path(item).resolve(strict=True)
            if path==other or (path.exists() and os.path.samefile(path,other)):
                raise AdapterError('CANCEL_JOURNAL_ALIAS_REJECTED')
        return path

    def reserve(self, identity, binding, *, protected):
        path=self.checked_path(protected)
        try:
            with closing(sqlite3.connect(str(path),timeout=5,isolation_level=None)) as c:
                c.execute('PRAGMA synchronous=FULL')
                c.execute('BEGIN IMMEDIATE')
                try:
                    objects=c.execute("SELECT type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchall()
                    version=c.execute('PRAGMA user_version').fetchone()[0]
                    if not objects and version==0:
                        c.execute(CANCEL_SCHEMA);c.execute('PRAGMA user_version=1')
                    elif objects!=[('table',CANCEL_SCHEMA)] or version!=1:
                        raise AdapterError('CANCEL_JOURNAL_SCHEMA_REJECTED')
                    row=c.execute('SELECT binding,state FROM cancellations WHERE identity=?',(identity,)).fetchone()
                    encoded=json.dumps(binding,sort_keys=True,separators=(',',':'))
                    if row is not None:
                        if row!=(encoded,'RESERVED_RECONCILE_ONLY'):
                            raise AdapterError('CANCEL_REQUEST_CONFLICT')
                        outcome='DUPLICATE_RESERVED'
                    else:
                        c.execute('INSERT INTO cancellations VALUES (?,?,?)',(identity,encoded,'RESERVED_RECONCILE_ONLY'))
                        outcome='RESERVED_RECONCILE_ONLY'
                    self.fault('before_commit');c.commit();self.fault('after_commit')
                except BaseException:
                    c.rollback();raise
            return dict(outcome=outcome,allow_cancel_dispatch=False,production_execution=False)
        except (sqlite3.Error,OSError):
            return dict(outcome='UNKNOWN_RECONCILE_ONLY',allow_cancel_dispatch=False,production_execution=False)


@dataclass(frozen=True)
class OfflineTarget:
    runtime: str
    slots_path: str
    budget_path: str
    backend_id: str


class SingleSlotAdapter:
    def __init__(self, slots, budget, *, target=None, consumer=None, backend=None,
                 wall_clock=time.time, monotonic=time.monotonic, cancellation_journal=None):
        self.cancellation_journal=cancellation_journal
        self.slots=slots
        self.budget=budget
        self.target=target
        self.consumer=consumer
        self.backend=backend
        self.wall_clock=wall_clock
        self.monotonic=monotonic
        self.runtime=None
        if target is not None:
            self.runtime=Path(target.runtime).resolve(strict=True)
            stat=self.runtime.stat()
            self.runtime_identity=(stat.st_dev,stat.st_ino)
            self.ids=dict(runtime_id=path_id(self.runtime),slots_id=path_id(target.slots_path),budget_id=path_id(target.budget_path),backend_id=target.backend_id)

    def _now(self):
        value=self.wall_clock()
        if type(value) not in (int,float) or not 0<=value<2**53:
            raise AdapterError('CLOCK_UNAVAILABLE')
        return int(value)

    def _verify(self,envelope,kind):
        try:
            return self.consumer.verify(envelope,kind=kind,now=self._now())
        except Exception:
            raise AdapterError('EVIDENCE_REJECTED') from None

    def _lock(self):
        """Use the existing recovery guard, not a parallel lock implementation."""
        if self.runtime is None:raise AdapterError('TARGET_NOT_CONFIGURED')
        active=lock_recovery._ACTIVE_LEASE.get()
        if active is None:raise AdapterError('EXPECTED_LOCK_REQUIRED')
        path,owned=active
        try:
            if Path(path).resolve(strict=True)!=self.runtime/'supervisor.lock':
                raise AdapterError('LOCK_RUNTIME_MISMATCH')
            stat=self.runtime.stat()
            if (stat.st_dev,stat.st_ino)!=self.runtime_identity:raise AdapterError('LOCK_RUNTIME_CHANGED')
            # Same guard as exclusive_lock/mark_tree/recover_lock serializes the
            # identity check with supported lock mutations and recovery.
            with lock_recovery._guard(self.runtime):
                stored=json.loads(Path(path).read_bytes())
                if stored!=owned or stored.get('schema_version')!=2:
                    raise AdapterError('LOCK_INSTANCE_CHANGED')
                if type(stored.get('pid')) is not int or stored['pid']!=os.getpid():
                    raise AdapterError('LOCK_PROCESS_MISMATCH')
                identity=lock_recovery.process_identity(os.getpid())
                if not identity or identity!=stored.get('process_identity'):
                    raise AdapterError('LOCK_PROCESS_MISMATCH')
                token=stored.get('token')
                if type(token) is not str or not token:raise AdapterError('LOCK_INSTANCE_CHANGED')
                return dict(lock_token_hash=digest(token),process_identity_hash=digest(identity))
        except AdapterError:raise
        except Exception:raise AdapterError('LOCK_IDENTITY_UNAVAILABLE') from None

    @staticmethod
    def _bound(payload,expected):
        if type(payload) is not dict or any(type(payload.get(k)) is not type(v) or payload[k]!=v for k,v in expected.items()):
            raise AdapterError('BINDING_MISMATCH')

    def _admission(self,envelope,*,require_backend=True):
        active=lock_recovery._ACTIVE_LEASE.get()
        if active is not None and (active[1].get('recovery_only') is True or active[1].get('recovery_required') is True):
            raise AdapterError('RECOVERY_ONLY_NO_DISPATCH')
        if self.target is None or self.consumer is None or (require_backend and self.backend is None):
            raise AdapterError('OFFLINE_BACKEND_NOT_CONFIGURED')
        if require_backend and (getattr(self.backend,'backend_id',None)!=self.target.backend_id or not callable(getattr(self.backend,'execute_once',None))):
            raise AdapterError('BACKEND_IDENTITY_MISMATCH')
        if require_backend and (type(getattr(self.backend,'protocol_version',None)) is not str or self.backend.protocol_version != BACKEND_PROTOCOL):
            raise AdapterError('BACKEND_PROTOCOL_UNSUPPORTED')
        if path_id(self.slots.path)!=self.ids['slots_id'] or path_id(self.budget.path)!=self.ids['budget_id']:
            raise AdapterError('LEDGER_TARGET_MISMATCH')
        p=self._verify(envelope,'offline_slot_admission')
        self._bound(p,dict(self.ids,**self._lock(),inventory_id=INVENTORY,scope='isolated_offline',production_execution=False))
        if require_backend:
            self._bound(p,{'backend_protocol':BACKEND_PROTOCOL})
        for k in ('slot','owner'):
            if type(p.get(k)) is not str or not p[k] or len(p[k])>128:raise AdapterError('INVALID_OPERATION')
        if type(p.get('epoch')) is not int or p['epoch']<1:raise AdapterError('INVALID_OPERATION')
        if type(p.get('max_wall_seconds')) is not int or not 0<p['max_wall_seconds']<=3600:
            raise AdapterError('INVALID_OFFLINE_BOUND')
        facts=p.get('gates')
        if type(facts) is not dict or set(facts)!=set(GATES) or any(facts[k] is not True for k in GATES):
            raise AdapterError('HOST_PRECONDITIONS_MISSING')
        common={k:p[k] for k in ('slot','epoch','owner')}
        common['run_id']=digest(dict(inventory_id=INVENTORY,**common))
        common['request_id']=p.get('request_id')
        self._bound(p,common)
        return p,common

    def _unknown(self,p,token):
        if token is not None:
            try:self.slots.mark_unknown(p['slot'],token,epoch=p['epoch'],owner=p['owner'])
            except Exception:pass # Persisted claimed/running also blocks replay.
        return {'outcome':'UNKNOWN_RECONCILE_ONLY','production_execution':False}

    def execute(self,admission,schedule,idle,budget_request):
        """At most one backend call. All failures after preparation block replay."""
        p,common=self._admission(admission)
        budget=self._verify(budget_request,'budget_request')
        self._bound(budget,{'run_id':common['run_id'],'request_id':common['request_id']})
        amount=budget.get('amount')
        if type(amount) is not dict:raise AdapterError('INVALID_RESERVATION')
        wall=amount.get('wall_seconds')
        if type(wall) is not int or not 0<wall<=p['max_wall_seconds']:
            raise AdapterError('WALL_RESERVATION_MISMATCH')
        plan=self._verify(schedule,'schedule')
        self._bound(plan,{k:common[k] for k in ('slot','epoch','owner')})
        due=plan.get('next_due')
        if type(due) is not int:raise AdapterError('INVALID_SCHEDULE')
        missed=plan.get('missed',[])
        if type(missed) is not list or any(type(x) is not list or len(x)!=2 for x in missed):
            raise AdapterError('INVALID_SCHEDULE')
        missed=tuple(tuple(x) for x in missed)
        token=None
        try:
            self.slots.admit_due(p['slot'],due,schedule,now=self._now(),epoch=p['epoch'],owner=p['owner'],missed=missed)
            token=self.budget.reserve_then_claim(budget_request,self.slots,p['slot'],idle,now=self._now(),epoch=p['epoch'],owner=p['owner'])
            self._admission(admission) # Recheck signed lifetime and exact lease.
            self.slots.start(p['slot'],token,epoch=p['epoch'],owner=p['owner'])
            self._lock()
            lock_recovery.mark_tree('unverified')
            started=self.monotonic()
            if type(started) not in (int,float) or not 0<=started<float('inf'):
                raise AdapterError('CLOCK_UNAVAILABLE')
            operation=dict(common,inventory_id=INVENTORY,token=token,scope='isolated_offline',
                schema=OPERATION_SCHEMA,backend_protocol=BACKEND_PROTOCOL,max_wall_seconds=wall,production_execution=False,
                **self.ids,**self._lock())
            operation['idempotency_key']=digest(operation)
            # v1 backend must enforce deadline outside this Python callback and
            # durably deduplicate this exact identity. This is a contract, not
            # proof of capabilities. No cancellation dispatch is implemented.
            result=self.backend.execute_once(operation,deadline_monotonic=started+wall)
            ended=self.monotonic()
            if type(ended) not in (int,float) or not started<=ended<=started+wall:
                raise AdapterError('BACKEND_RESULT_LATE_OR_CLOCK_CHANGED')
            if type(result) is not dict or set(result)!= {'slot_receipt','budget_receipt'}:
                raise AdapterError('RECEIPTS_MISSING')
            return self.reconcile(admission,result['slot_receipt'],result['budget_receipt'])
        except Exception:
            return self._unknown(p,token)

    def reserve_cancellation(self,admission,cancel_request,*,cost_request=None):
        """Persist intent only. Signed cancellation facts do not authorize dispatch."""
        if type(self.cancellation_journal) is not CancellationJournal:
            raise AdapterError('CANCEL_JOURNAL_NOT_CONFIGURED')
        p,common=self._admission(admission,require_backend=False)
        journal=self.cancellation_journal
        protected=(self.slots.path,self.budget.path,self.runtime/'supervisor.lock')
        path=journal.checked_path(protected)
        journal_id=hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()
        request=self._verify(cancel_request,'offline_cancel_request')
        expected=dict(self.ids,**self._lock(),**common,inventory_id=INVENTORY,
            journal_id=journal_id,cancel_protocol=CANCEL_PROTOCOL,scope='isolated_offline',production_execution=False)
        self._bound(request,expected)
        with closing(sqlite3.connect(Path(self.slots.path).resolve().as_uri()+'?mode=ro',uri=True)) as c:
            row=c.execute('SELECT state,epoch,owner,token FROM slots WHERE slot=?',(common['slot'],)).fetchone()
        if row is None or row[0] not in ('claimed','running','unknown') or row[1:3]!=(common['epoch'],common['owner']) or type(row[3]) is not str:
            raise AdapterError('CANCEL_CLAIM_NOT_UNRESOLVED')
        claim_hash=digest(row[3])
        self._bound(request,{'claim_token_hash':claim_hash})
        with self.budget.tx() as c:
            reservation=c.execute('SELECT state,claim_hash,binding FROM reservations WHERE id=?',(common['request_id'],)).fetchone()
            if reservation is None or reservation['state'] not in ('reserved','unknown','overrun') or reservation['claim_hash']!=claim_hash or json.loads(reservation['binding'])!=dict(inventory_id=INVENTORY,**common):
                raise AdapterError('CANCEL_BUDGET_BINDING_MISMATCH')
        # No cross-ledger atomic dispatch claim: only intent is persisted.
        self._lock()
        binding=dict(expected,claim_token_hash=claim_hash)
        identity=digest(dict(inventory_id=INVENTORY,**common,claim_token_hash=claim_hash))
        if cost_request is not None or 'cancel_cost_protocol' in request:
            self._bound(request,{'cancel_cost_protocol':CANCEL_COST_PROTOCOL})
            if cost_request is None:raise AdapterError('CANCEL_COST_REQUEST_REQUIRED')
            cost_id=digest(dict(cancel_identity=identity,cancel_cost_protocol=CANCEL_COST_PROTOCOL))
            cost=self._verify(cost_request,'budget_request')
            cost_binding=dict(binding,cancel_identity=identity,cancel_cost_protocol=CANCEL_COST_PROTOCOL,
                              cancel_cost_request_id=cost_id,request_id=cost_id,
                              original_request_id=common['request_id'])
            self._bound(cost,dict(request_id=cost_id,run_id=common['run_id'],
                                  claim_binding=cost_binding,claim_token_hash=claim_hash))
            # Independent signature binds the complete amount, never a zero-cost
            # assumption. Original and cancellation costs share existing caps.
            amount=cost.get('amount')
            if (type(amount) is not dict or type(amount.get('wall_seconds')) is not int
                    or not 0<amount['wall_seconds']<=p['max_wall_seconds']):
                raise AdapterError('CANCEL_COST_WALL_MISMATCH')
            try:
                self.budget.reserve_cancellation_cost(cost_request,now=self._now(),
                    binding=cost_binding,claim_token_hash=claim_hash)
            except Exception:
                # Lost reservation acknowledgement cannot authorize intent.
                return dict(outcome='UNKNOWN_RECONCILE_ONLY',allow_cancel_dispatch=False,production_execution=False)
            with self.budget.tx() as c:
                cost_row=c.execute('SELECT state,binding,claim_hash FROM reservations WHERE id=?',(cost_id,)).fetchone()
                if (cost_row is None or cost_row['state']!='reserved'
                        or json.loads(cost_row['binding'])!=cost_binding or cost_row['claim_hash']!=claim_hash):
                    raise AdapterError('CANCEL_COST_RECONCILIATION_REQUIRED')
            self._lock()
            binding=cost_binding
        return journal.reserve(identity,binding,protected=protected)

    def reconcile(self,admission,slot_receipt,budget_receipt):
        """Reconcile authenticated receipts without calling the execution backend."""
        p,common=self._admission(admission,require_backend=False)
        sr=self._verify(slot_receipt,'receipt');br=self._verify(budget_receipt,'budget_receipt')
        self._bound(sr,dict(common,external_drained=True))
        self._bound(br,dict(common,externally_reconciled=True,outcome='known'))
        token=sr.get('token')
        if type(token) is not str or not token or sr.get('state') not in ('completed','failed'):
            raise AdapterError('INVALID_TERMINAL_RECEIPT')
        self._bound(br,{'claim_token_hash':digest(token)})
        # Both receipts must join the persisted reservation and exact claim.
        with self.budget.tx() as c:
            row=c.execute('SELECT claim_hash,binding FROM reservations WHERE id=?',(common['request_id'],)).fetchone()
            expected=dict(inventory_id=INVENTORY,**common)
            if row is None or row['claim_hash']!=digest(token) or json.loads(row['binding'])!=expected:
                raise AdapterError('CLAIM_RECEIPT_CONFLICT')
        self._lock()
        lock_recovery.mark_tree('unverified')
        state=self.slots.reconcile(p['slot'],sr['state'],slot_receipt,now=self._now(),epoch=p['epoch'],owner=p['owner'])
        if any(row[2] in ('claimed','running','unknown') for row in self.slots.snapshot()):
            raise AdapterError('OTHER_EXECUTION_UNRESOLVED')
        # A trusted drained receipt, not normal function return, proves cleanup.
        settled=self.budget.settle(budget_receipt,now=self._now())
        with self.budget.tx() as c:
            final=c.execute('SELECT state FROM reservations WHERE id=?',(common['request_id'],)).fetchone()
        if settled not in ('SETTLED','DUPLICATE') or final is None or final['state']!='settled':
            return {'outcome':'UNKNOWN_RECONCILE_ONLY','slot_result':state,'budget_result':settled,'production_execution':False}
        # Keep the recovery fence until both durable ledgers acknowledge the
        # receipt. A storage failure must not release an unresolved reservation.
        lock_recovery.mark_tree('verified_closed')
        return {'outcome':sr['state'].upper(),'slot_result':state,'budget_result':settled,'production_execution':False}
