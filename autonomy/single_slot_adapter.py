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
            for reserved in (other, *(Path(str(other)+suffix) for suffix in ('-journal','-wal','-shm'))):
                if path==reserved or (path.exists() and reserved.exists() and os.path.samefile(path,reserved)):
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
                if stored!=owned or stored.get('schema_version')!=3:
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
    def _tree_binding(common):
        return digest(dict(inventory_id=INVENTORY, **common))

    def _begin_tree(self, common):
        lock_recovery.begin_bound_tree(self._tree_binding(common))

    def _bind_tree_claim(self, common, token):
        lock_recovery.bind_tree_claim(self._tree_binding(common), digest(token))

    def _mark_tree(self, state, common=None, token=None):
        lock_recovery.mark_tree(state, binding=self._tree_binding(common), claim_hash=digest(token))

    def _protected_paths(self):
        return (self.slots.path, self.budget.path, self.runtime/'supervisor.lock')

    def prepare_event(self, event):
        """Legacy isolated transport has no original DB event join."""

    def _claim(self, budget_request, slot, idle, epoch, owner):
        return self.budget.reserve_then_claim(budget_request,self.slots,slot,idle,
            now=self._now(),epoch=epoch,owner=owner)

    def _operation_binding(self):
        return {}

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

    def request_status(self, admission):
        """Read the bound local request without dispatch, settlement or replay.
        只读查询绑定请求；不代表正式 Provider 回执或货币费用。
        """
        from autonomy.business_request_status import request_status
        return request_status(self, admission)

    def _stale_schedule_preflight(self, common, due):
        """Read-only rejection hint; never closes a fence or proves prior history."""
        from autonomy.durable_slots import DurableSlots
        if type(self) is not SingleSlotAdapter or type(self.slots) is not DurableSlots or due < 0:
            return False
        try:
            active=lock_recovery._ACTIVE_LEASE.get()
            if active is None:
                return False
            lock,owned=active
            with lock_recovery._guard(self.runtime):
                stored=json.loads(Path(lock).read_bytes())
                if (Path(lock).resolve(strict=True)!=self.runtime/'supervisor.lock'
                        or stored!=owned or stored.get('schema_version')!=3
                        or stored.get('pid')!=os.getpid()
                        or lock_recovery.process_identity(os.getpid())!=stored.get('process_identity')
                        or stored.get('tree_state') not in ('not_started','verified_closed')
                        or stored.get('recovery_only',False) is not False
                        or stored.get('recovery_required',False) is not False
                        or stored.get('tree_binding')==self._tree_binding(common)
                        or os.path.lexists(lock_recovery._tree_fence(Path(lock)))):
                    return False
                path=Path(self.target.slots_path).resolve(strict=True)
                if path_id(path)!=self.ids['slots_id']:
                    return False
                # Do not use an injected slots connection or ledger method.
                with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1,isolation_level=None)) as db:
                    db.execute('BEGIN')
                    authority=db.execute('SELECT epoch,owner FROM authority WHERE singleton=1').fetchone()
                    existing=db.execute('SELECT 1 FROM slots WHERE slot=?',(common['slot'],)).fetchone()
                    newer=db.execute('SELECT 1 FROM slots WHERE due>=? LIMIT 1',(due,)).fetchone()
                    return authority==(common['epoch'],common['owner']) and existing is None and newer is not None
        except Exception:
            # Unavailable or racing snapshots take the original fail-closed path.
            return False

    def _guarded_admit_due(self, common, due, schedule, missed):
        """Fence and admit under guard -> SQLite write lock, without dispatch.

        This optimization is restricted to the ordinary local ledger path. The
        two persisted stores are not atomic: any uncertain fence or commit
        outcome remains fenced and is handled as UNKNOWN by the caller.
        """
        from autonomy.durable_slots import DurableSlots
        now=self._now()
        lease=lock_recovery._ACTIVE_LEASE.get()
        if lease is None or Path(lease[0]).resolve(strict=True)!=self.runtime/'supervisor.lock':
            raise AdapterError('EXPECTED_LOCK_REQUIRED')
        binding=self._tree_binding(common)
        with lock_recovery._guard(self.runtime):
            stat=self.runtime.stat()
            if (stat.st_dev,stat.st_ino)!=self.runtime_identity or path_id(self.slots.path)!=self.ids['slots_id']:
                raise AdapterError('LEDGER_TARGET_MISMATCH')
            lock_recovery._bound_lease_locked(binding,action='validate_begin')
            def begin():
                if lock_recovery._ACTIVE_LEASE.get() is not lease:
                    raise AdapterError('LOCK_INSTANCE_CHANGED')
                lock_recovery._bound_lease_locked(binding,action='begin')
            outcome=DurableSlots.admit_due(self.slots,common['slot'],due,schedule,now=now,
                epoch=common['epoch'],owner=common['owner'],missed=missed,
                _reject_stale=True,_before_admit=begin)
            if lock_recovery._ACTIVE_LEASE.get() is not lease:
                raise AdapterError('LOCK_INSTANCE_CHANGED')
            return outcome

    def execute(self,admission,schedule,idle,budget_request):
        """At most one backend call. All failures after preparation block replay."""
        p,common=self._admission(admission)
        budget=self._verify(budget_request,'budget_request')
        self._bound(budget,{'run_id':common['run_id'],'request_id':common['request_id']})
        provider_request = None
        if 'provider_request' in p:
            from discovery.providers.contracts import bound_search_request
            provider_request = bound_search_request(p['provider_request'])
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
            from autonomy.durable_slots import DurableSlots
            if (type(self) is SingleSlotAdapter and type(self.slots) is DurableSlots
                    and self.slots.connect is sqlite3.connect
                    and getattr(self.slots._tx,'__func__',None) is DurableSlots._tx):
                outcome=self._guarded_admit_due(common,due,schedule,missed)
                if outcome=='STALE_SCHEDULE_PRECHECK_REJECTED':
                    return {'outcome':outcome,'production_execution':False}
            else:
                if self._stale_schedule_preflight(common,due):
                    return {'outcome':'STALE_SCHEDULE_PRECHECK_REJECTED','production_execution':False}
                self._begin_tree(common)
                self.slots.admit_due(p['slot'],due,schedule,now=self._now(),epoch=p['epoch'],owner=p['owner'],missed=missed)
            token=self._claim(budget_request,p['slot'],idle,p['epoch'],p['owner'])
            self._bind_tree_claim(common, token)
            self._admission(admission) # Recheck signed lifetime and exact lease.
            self.slots.start(p['slot'],token,epoch=p['epoch'],owner=p['owner'])
            self._lock()
            self._mark_tree('unverified', common, token)
            started=self.monotonic()
            if type(started) not in (int,float) or not 0<=started<float('inf'):
                raise AdapterError('CLOCK_UNAVAILABLE')
            operation=dict(common,inventory_id=INVENTORY,token=token,scope='isolated_offline',
                schema=OPERATION_SCHEMA,backend_protocol=BACKEND_PROTOCOL,max_wall_seconds=wall,production_execution=False,
                **self.ids,**self._lock(),**self._operation_binding())
            if provider_request is not None:
                operation['provider_request'] = provider_request
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
        protected=self._protected_paths()
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
            row=c.execute('SELECT claim_hash,binding,state,receipt_hash FROM reservations WHERE id=?',(common['request_id'],)).fetchone()
            expected=dict(inventory_id=INVENTORY,**common)
            if row is None or row['claim_hash']!=digest(token) or json.loads(row['binding'])!=expected:
                raise AdapterError('CLAIM_RECEIPT_CONFLICT')
        self._lock()
        # A new lease may inspect an already settled old request without
        # reopening or mutating its unrelated execution tree.
        active=lock_recovery._ACTIVE_LEASE.get()
        if (type(self) is SingleSlotAdapter and active is not None and
                active[1].get('tree_state') == 'not_started' and 'tree_binding' not in active[1]):
            mapped=self.slots._evidence(slot_receipt,kind='receipt',now=self._now(),
                slot=common['slot'],state=sr['state'],epoch=common['epoch'],owner=common['owner'],external_drained=True)
            with closing(sqlite3.connect(Path(self.slots.path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
                slot=db.execute('SELECT state,epoch,owner,token,receipt FROM slots WHERE slot=?',(common['slot'],)).fetchone()
                unresolved=db.execute("SELECT 1 FROM slots WHERE state IN ('claimed','running','unknown') LIMIT 1").fetchone()
            if (slot == (sr['state'],common['epoch'],common['owner'],token,digest(mapped)) and
                    unresolved is None and row['state']=='settled' and row['receipt_hash']==digest(br)):
                return {'outcome':sr['state'].upper(),'slot_result':'DUPLICATE_RECEIPT',
                        'budget_result':'DUPLICATE','production_execution':False}
            raise AdapterError('PRIOR_LEASE_RECEIPT_UNPROVEN')
        self._mark_tree('unverified', common, token)
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
        self._mark_tree('verified_closed', common, token)
        return {'outcome':sr['state'].upper(),'slot_result':state,'budget_result':settled,'production_execution':False}


class OriginalOwnerSlotAdapter(SingleSlotAdapter):
    """Offline protocol under the original DB authority; no replacement lease.

    This is an integration seam, not a production backend or a dispatch grant.
    The event, claim, budget and receipt checks remain identical to the existing
    isolated protocol. Only identity and the durable tree fence use the original
    owner's database, so supervisor.lock cannot impersonate that owner.
    """
    def __init__(self, *args, original_owner, **kwargs):
        from autonomy.original_inventory_owner import OriginalOwnerAuthority
        if type(original_owner) is not OriginalOwnerAuthority:
            raise AdapterError('EXACT_ORIGINAL_OWNER_REQUIRED')
        self.original_owner = original_owner
        super().__init__(*args, **kwargs)

    def _lock(self):
        try:
            if self.runtime is None:
                raise AdapterError('TARGET_NOT_CONFIGURED')
            stat = self.runtime.stat()
            if (stat.st_dev, stat.st_ino) != self.runtime_identity:
                raise AdapterError('LOCK_RUNTIME_CHANGED')
            return self.original_owner.check()
        except Exception:
            raise AdapterError('ORIGINAL_OWNER_LOST') from None

    def _terminal_tree_closed(self, common, claim_hash):
        if type(self) is not OriginalOwnerSlotAdapter:
            return False
        try:
            return self.original_owner.claim_tree_closed(dict(common, claim_token_hash=claim_hash))
        except Exception:
            raise AdapterError('ORIGINAL_OWNER_LOST') from None

    def _begin_tree(self, common):
        self._lock()  # prepare_event already fenced this exact original owner.

    def _bind_tree_claim(self, common, token):
        pass  # _claim has bound the complete claim in the original owner DB.

    def _mark_tree(self, state, common=None, token=None):
        self.original_owner.mark_tree(state)

    def _protected_paths(self):
        return (self.slots.path, self.budget.path, self.original_owner.database_path)

    def prepare_event(self, event):
        if (type(event) is not dict or
                set(event) != {'inventory_id','admission','schedule','idle','budget_request'} or
                event['inventory_id'] != INVENTORY or
                any(type(event[k]) is not dict for k in ('admission','schedule','idle','budget_request'))):
            raise AdapterError('EXACT_ORIGINAL_EVENT_REQUIRED')
        self._admission(event['admission'])
        from autonomy.release_store import canonical
        if len(canonical(event)) > 65536:
            raise AdapterError('ORIGINAL_EVENT_TOO_LARGE')
        self.original_owner.prepare_event(digest(event))

    def execute(self, admission, schedule, idle, budget_request):
        event = dict(inventory_id=INVENTORY,admission=admission,schedule=schedule,
                     idle=idle,budget_request=budget_request)
        if self.original_owner.event_binding()['original_event_digest'] != digest(event):
            raise AdapterError('ORIGINAL_OWNER_EVENT_MISMATCH')
        return super().execute(admission,schedule,idle,budget_request)

    def _claim(self, budget_request, slot, idle, epoch, owner):
        token = self.budget.reserve_then_claim(budget_request,self.slots,slot,idle,
            now=self._now(),epoch=epoch,owner=owner,original_owner=self.original_owner)
        budget = self._verify(budget_request,'budget_request')
        self.original_owner.bind_claim(dict(slot=slot,epoch=epoch,owner=owner,
            run_id=budget['run_id'],request_id=budget['request_id'],claim_token_hash=digest(token)))
        return token

    def _operation_binding(self):
        result = self.original_owner.receipt_binding()
        return {k:v for k,v in result.items() if k not in ('lock_token_hash','process_identity_hash')}

    def reconcile(self, admission, slot_receipt, budget_receipt):
        p, common = self._admission(admission,require_backend=False)
        sr=self._verify(slot_receipt,'receipt'); br=self._verify(budget_receipt,'budget_receipt')
        token=sr.get('token')
        if type(token) is not str or not token:
            raise AdapterError('INVALID_TERMINAL_RECEIPT')
        expected=self.original_owner.receipt_binding(dict(common,claim_token_hash=digest(token)))
        self._bound(sr,expected); self._bound(br,expected)
        return super().reconcile(admission,slot_receipt,budget_receipt)
