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

from autonomy import lock_recovery
from autonomy.growth_ledger import digest
from autonomy.unattended_policy import INVENTORY, GATES


BACKEND_PROTOCOL = 'rokt.offline-backend.v1'
OPERATION_SCHEMA = 'rokt.offline-operation.v1'


class AdapterError(RuntimeError):
    pass


def path_id(path):
    return hashlib.sha256(os.path.normcase(str(Path(path).resolve(strict=True))).encode()).hexdigest()


@dataclass(frozen=True)
class OfflineTarget:
    runtime: str
    slots_path: str
    budget_path: str
    backend_id: str


class SingleSlotAdapter:
    def __init__(self, slots, budget, *, target=None, consumer=None, backend=None,
                 wall_clock=time.time, monotonic=time.monotonic):
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
        state=self.slots.reconcile(p['slot'],sr['state'],slot_receipt,now=self._now(),epoch=p['epoch'],owner=p['owner'])
        if any(row[2] in ('claimed','running','unknown') for row in self.slots.snapshot()):
            raise AdapterError('OTHER_EXECUTION_UNRESOLVED')
        # A trusted drained receipt, not normal function return, proves cleanup.
        settled=self.budget.settle(budget_receipt,now=self._now())
        # Keep the recovery fence until both durable ledgers acknowledge the
        # receipt. A storage failure must not release an unresolved reservation.
        lock_recovery.mark_tree('verified_closed')
        return {'outcome':sr['state'].upper(),'slot_result':state,'budget_result':settled,'production_execution':False}
