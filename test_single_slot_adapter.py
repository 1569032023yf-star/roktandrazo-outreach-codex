import tempfile
import unittest
from pathlib import Path
from autonomy.single_slot_adapter import SingleSlotAdapter,OfflineTarget,AdapterError,BACKEND_PROTOCOL,OPERATION_SCHEMA,CancellationJournal,CANCEL_PROTOCOL
from autonomy.durable_slots import DurableSlots
from autonomy.ledger_evidence import LedgerEvidenceVerifier
from autonomy.growth_ledger import GrowthLedger,digest,business_day
from autonomy.lock_recovery import exclusive_lock,mark_tree
from autonomy.unattended_policy import INVENTORY,GATES
from test_growth_ledger import consumer,signed,oid,amounts,T


class FakeBackend:
    backend_id='synthetic-backend'
    protocol_version=BACKEND_PROTOCOL
    def __init__(self,mode='success'):
        self.mode=mode;self.calls=0;self.effects=[];self.receipts=None
    def execute_once(self,operation,*,deadline_monotonic):
        self.operation=operation;self.deadline=deadline_monotonic
        self.calls+=1;self.effects.append(operation['request_id'])
        common={k:operation[k] for k in ('slot','epoch','owner','run_id','request_id')}
        sr=signed('receipt',T+10,**common,token=operation['token'],state='failed' if self.mode=='failed' else 'completed',receipt='fixture-terminal',external_drained=True)
        br=signed('budget_receipt',T+10,**common,claim_token_hash=digest(operation['token']),outcome='known',actual=amounts(),externally_reconciled=True)
        self.receipts=dict(slot_receipt=sr,budget_receipt=br)
        if self.mode=='lost':raise RuntimeError('synthetic-secret-never-echo')
        if self.mode=='missing':return {}
        if self.mode=='cancel_ack':return {'cancel_ack':True}
        if self.mode=='timeout':raise TimeoutError('synthetic-timeout')
        return self.receipts


class SingleSlotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-adapter-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.runtime=self.root/'runtime';self.runtime.mkdir()
        self.trust=consumer()
        verify=LedgerEvidenceVerifier(self.trust,lambda:T+10)
        self.slots=DurableSlots(self.root/'slots.sqlite',verify=verify);self.slots.initialize()
        self.slots.switch_authority(0,'owner',signed('authority',T+10,previous_epoch=0,owner='owner',drained=True,old_disabled=True),now=T+10)
        self.budget=GrowthLedger(self.root/'budget.sqlite',consumer=self.trust);self.budget.initialize()
        self.budget.approve_budget(signed('budget_approval',T+10,day=business_day(T+10),limits=amounts(10),run_wall_limit=10),now=T+10)
        self.target=OfflineTarget(str(self.runtime),self.slots.path,self.budget.path,'synthetic-backend')
        self.backend=FakeBackend()
        self.adapter=SingleSlotAdapter(self.slots,self.budget,target=self.target,consumer=self.trust,backend=self.backend,wall_clock=lambda:T+10,monotonic=lambda:1)
        self.common=dict(slot='one',epoch=1,owner='owner')
        self.common.update(run_id=digest(dict(inventory_id=INVENTORY,**self.common)),request_id=oid('one-request'))
        self.plan=signed('schedule',T+10,slot='one',epoch=1,owner='owner',next_due=T+10,latest_due=True)
        self.idle=signed('idle',T+10,**self.common,external_state='idle',existing_lock_held=True)
        self.request=signed('budget_request',T+10,run_id=self.common['run_id'],request_id=self.common['request_id'],day=business_day(T+10),amount=amounts(),cache_hit=False,claim_binding=dict(inventory_id=INVENTORY,**self.common))
    def admission(self,**changes):
        payload=dict(self.adapter.ids,**self.adapter._lock(),**self.common,scope='isolated_offline',production_execution=False,backend_protocol=BACKEND_PROTOCOL,max_wall_seconds=2,gates=dict.fromkeys(GATES,True))
        payload.update(changes)
        return signed('offline_slot_admission',T+10,**payload)
    def run_one(self,e):return self.adapter.execute(e,self.plan,self.idle,self.request)

    def test_protocol_version_default_deny_before_claim(self):
        with exclusive_lock(self.runtime):
            for value in (None, True, 1, 'v0'):
                self.backend.protocol_version=value
                with self.assertRaisesRegex(AdapterError,'BACKEND_PROTOCOL_UNSUPPORTED'):
                    self.run_one(self.admission())
            self.backend.protocol_version=BACKEND_PROTOCOL
            for value in (None, True, 'v0'):
                with self.assertRaisesRegex(AdapterError,'BINDING_MISMATCH'):
                    self.run_one(self.admission(backend_protocol=value))
        self.assertEqual(self.backend.calls,0)
        self.assertEqual(self.slots.snapshot(),[])

    def test_legacy_admission_missing_version_reconciles_but_cannot_execute(self):
        self.backend.mode='lost'
        with exclusive_lock(self.runtime):
            admission=self.admission()
            self.assertEqual(self.run_one(admission)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            payload=dict(admission['payload'])
            payload.pop('backend_protocol')
            # Re-sign the actual legacy shape; do not substitute None for absence.
            for key in ('schema','source_id','principal_id','inventory_id','kind',
                        'observed_at_epoch','expires_at_epoch','receipt_id'):
                payload.pop(key)
            legacy=signed('offline_slot_admission',T+10,**payload)
            self.assertNotIn('backend_protocol',legacy['payload'])
            with self.assertRaisesRegex(AdapterError,'BINDING_MISMATCH'):
                self.run_one(legacy)
            self.assertEqual(self.backend.calls,1)
            self.assertEqual(self.adapter.reconcile(legacy,**self.backend.receipts)['outcome'],'COMPLETED')

    def test_versioned_operation_identity_and_time_bound(self):
        with exclusive_lock(self.runtime):
            self.run_one(self.admission())
        operation=dict(self.backend.operation)
        identity=operation.pop('idempotency_key')
        self.assertEqual(identity,digest(operation))
        self.assertEqual(operation['schema'],OPERATION_SCHEMA)
        self.assertIs(operation['production_execution'],False)
        self.assertEqual(operation['inventory_id'],INVENTORY)
        self.assertEqual(operation['scope'],'isolated_offline')
        self.assertEqual(operation['backend_protocol'],BACKEND_PROTOCOL)
        self.assertEqual(self.backend.deadline,1+operation['max_wall_seconds'])
        for key in ('token','request_id','lock_token_hash','slots_id','budget_id'):
            changed=dict(operation);changed[key]='different'
            self.assertNotEqual(identity,digest(changed))

    def test_cancel_ack_and_timeout_preserve_unknown_budget_no_replay(self):
        for mode in ('cancel_ack','timeout'):
            case=SingleSlotTests();case.setUp()
            try:
                case.backend.mode=mode
                with exclusive_lock(case.runtime):
                    e=case.admission()
                    self.assertEqual(case.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
                    self.assertEqual(case.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
                    self.assertEqual(case.backend.calls,1)
                    self.assertEqual(case.slots.snapshot()[0][2],'unknown')
                    with case.budget.tx() as c:
                        self.assertEqual(c.execute('SELECT state FROM reservations').fetchone()[0],'reserved')
                    # Only independently signed terminal receipts clear the fence.
                    case.adapter.reconcile(e,**case.backend.receipts)
            finally:case.doCleanups()

    def cancellation_fixture(self):
        import hashlib,os
        journal=CancellationJournal(self.root/'cancel.sqlite')
        self.adapter.cancellation_journal=journal
        journal_id=hashlib.sha256(os.path.normcase(str(journal.path.resolve())).encode()).hexdigest()
        with self.budget.tx() as c:
            claim=c.execute('SELECT claim_hash FROM reservations').fetchone()[0]
        fields=dict(self.adapter.ids,**self.adapter._lock(),**self.common,claim_token_hash=claim,
            journal_id=journal_id,cancel_protocol=CANCEL_PROTOCOL,scope='isolated_offline',production_execution=False)
        return journal,fields

    def test_cancel_intent_reopen_duplicate_and_commit_ack_lost(self):
        self.backend.mode='lost'
        with exclusive_lock(self.runtime):
            e=self.admission();self.run_one(e)
            journal,fields=self.cancellation_fixture()
            def fail(stage):
                if stage=='after_commit':raise OSError('secret-ack-lost')
            journal.fault=fail
            request=signed('offline_cancel_request',T+10,**fields)
            result=self.adapter.reserve_cancellation(e,request)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertFalse(result['allow_cancel_dispatch'])
            self.adapter.cancellation_journal=CancellationJournal(journal.path)
            result=self.adapter.reserve_cancellation(e,request)
            self.assertEqual(result['outcome'],'DUPLICATE_RESERVED')
            self.assertEqual(self.backend.calls,1)
            self.assertEqual(self.slots.snapshot()[0][2],'unknown')
            with self.budget.tx() as c:
                self.assertEqual(c.execute('SELECT state FROM reservations').fetchone()[0],'reserved')
            self.adapter.reconcile(e,**self.backend.receipts)

    def test_cancel_intent_invalid_signature_version_binding_and_alias(self):
        self.backend.mode='lost'
        with exclusive_lock(self.runtime):
            e=self.admission();self.run_one(e)
            with self.assertRaisesRegex(AdapterError,'NOT_CONFIGURED'):
                self.adapter.reserve_cancellation(e,{})
            journal,fields=self.cancellation_fixture()
            for field in ('cancel_protocol','claim_token_hash','journal_id','request_id','lock_token_hash'):
                bad=dict(fields);bad[field]='wrong'
                with self.assertRaises(AdapterError):
                    self.adapter.reserve_cancellation(e,signed('offline_cancel_request',T+10,**bad))
            bad=signed('offline_cancel_request',T+10,**fields);bad['mac']='0'*64
            with self.assertRaisesRegex(AdapterError,'EVIDENCE_REJECTED'):
                self.adapter.reserve_cancellation(e,bad)
            self.adapter.cancellation_journal=CancellationJournal(self.budget.path)
            with self.assertRaisesRegex(AdapterError,'ALIAS'):
                self.adapter.reserve_cancellation(e,signed('offline_cancel_request',T+10,**fields))
            self.assertFalse(journal.path.exists())
            self.adapter.reconcile(e,**self.backend.receipts)

    def test_cancel_intent_before_commit_failure_remains_unknown(self):
        from contextlib import closing
        import sqlite3
        journal=CancellationJournal(self.root/'failed-intent.sqlite',fault=lambda stage: (_ for _ in ()).throw(OSError('secret')) if stage=='before_commit' else None)
        result=journal.reserve('identity',{},protected=(self.slots.path,self.budget.path))
        self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
        self.assertFalse(result['allow_cancel_dispatch'])
        with closing(sqlite3.connect(journal.path)) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM sqlite_master WHERE name='cancellations'").fetchone()[0],0)

    def test_cancel_journal_conflict_schema_and_hardlink(self):
        import sqlite3,os
        journal=CancellationJournal(self.root/'intent.sqlite')
        protected=(self.slots.path,self.budget.path)
        self.assertEqual(journal.reserve('identity',{'a':1},protected=protected)['outcome'],'RESERVED_RECONCILE_ONLY')
        with self.assertRaisesRegex(AdapterError,'CONFLICT'):
            journal.reserve('identity',{'a':2},protected=protected)
        from contextlib import closing
        with closing(sqlite3.connect(journal.path)) as c:
            c.execute('PRAGMA user_version=2');c.commit()
        with self.assertRaisesRegex(AdapterError,'SCHEMA'):
            journal.reserve('other',{},protected=protected)
        alias=self.root/'alias.sqlite';os.link(self.budget.path,alias)
        with self.assertRaisesRegex(AdapterError,'ALIAS'):
            CancellationJournal(alias).reserve('other',{},protected=protected)

    def test_default_deny_and_missing_lock(self):
        empty=SingleSlotAdapter(self.slots,self.budget)
        with self.assertRaisesRegex(AdapterError,'NOT_CONFIGURED'):empty.execute({}, {}, {}, {})
        with self.assertRaisesRegex(AdapterError,'EXPECTED_LOCK'):self.adapter._lock()
        self.assertEqual(self.backend.calls,0)

    def test_signed_missed_slots_are_preserved(self):
        self.plan=signed('schedule',T+10,slot='one',epoch=1,owner='owner',next_due=T+10,latest_due=True,missed=[['missed',T]])
        with exclusive_lock(self.runtime):
            self.assertEqual(self.run_one(self.admission())['outcome'],'COMPLETED')
        self.assertEqual([(r[0],r[2]) for r in self.slots.snapshot()],[('missed','deferred'),('one','completed')])

    def test_success_failure_and_duplicate_no_second_dispatch(self):
        with exclusive_lock(self.runtime):
            e=self.admission();r=self.run_one(e)
            self.assertEqual(r['outcome'],'COMPLETED')
            self.assertEqual(self.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            again=self.adapter.reconcile(e,**self.backend.receipts)
            self.assertEqual(again['budget_result'],'DUPLICATE')
        self.assertEqual(self.backend.calls,1);self.assertEqual(self.slots.snapshot()[0][2],'completed')

    def test_signed_failed_terminal(self):
        self.backend.mode='failed'
        with exclusive_lock(self.runtime):self.assertEqual(self.run_one(self.admission())['outcome'],'FAILED')
        self.assertEqual(self.slots.snapshot()[0][2],'failed')

    def test_old_receipt_cannot_clear_new_unknown_tree(self):
        with self.assertRaisesRegex(RuntimeError,'ASSOCIATED_TREE_UNVERIFIED'):
            with exclusive_lock(self.runtime):
                e=self.admission();self.run_one(e)
                schedule=signed('schedule',T+10,slot='next',epoch=1,owner='owner',next_due=T+11,latest_due=True)
                self.slots.admit_due('next',T+11,schedule,now=T+11,epoch=1,owner='owner')
                idle=signed('idle',T+10,slot='next',epoch=1,owner='owner',external_state='idle',existing_lock_held=True)
                token=self.slots.claim('next',idle,now=T+11,epoch=1,owner='owner')
                self.slots.mark_unknown('next',token,epoch=1,owner='owner')
                mark_tree('unverified')
                with self.assertRaisesRegex(AdapterError,'OTHER_EXECUTION_UNRESOLVED'):
                    self.adapter.reconcile(e,**self.backend.receipts)
        self.assertTrue((self.runtime/'supervisor.lock').exists())

    def test_runtime_and_lock_instance_binding(self):
        other=self.root/'unapproved';other.mkdir()
        with exclusive_lock(other):
            with self.assertRaisesRegex(AdapterError,'RUNTIME_MISMATCH'):self.adapter._lock()
        with exclusive_lock(self.runtime):
            for field in ('runtime_id','slots_id','budget_id','lock_token_hash','process_identity_hash','backend_id'):
                with self.assertRaisesRegex(AdapterError,'BINDING_MISMATCH'):self.run_one(self.admission(**{field:'wrong'}))
        self.assertEqual(self.backend.calls,0)

    def test_production_scope_or_host_boolean_cannot_enable(self):
        with exclusive_lock(self.runtime):
            for change in [dict(scope='production'),dict(production_execution=True),dict(gates=dict.fromkeys(GATES,1))]:
                with self.assertRaises(AdapterError):self.run_one(self.admission(**change))
        self.assertEqual(self.backend.calls,0)

    def test_effect_then_lost_receipt_unknown_no_replay_reconcile(self):
        self.backend.mode='lost'
        with exclusive_lock(self.runtime):
            e=self.admission();result=self.run_one(e)
            self.assertEqual(result,{'outcome':'UNKNOWN_RECONCILE_ONLY','production_execution':False})
            self.assertEqual(self.slots.snapshot()[0][2],'unknown')
            self.assertEqual(self.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.backend.calls,1)
            # Only authenticated explicit reconciliation proves the fake tree closed.
            self.assertEqual(self.adapter.reconcile(e,**self.backend.receipts)['outcome'],'COMPLETED')
        self.assertEqual(len(self.backend.effects),1)

    def test_unknown_without_drained_receipt_preserves_existing_lock(self):
        self.backend.mode='missing'
        with self.assertRaisesRegex(RuntimeError,'ASSOCIATED_TREE_UNVERIFIED'):
            with exclusive_lock(self.runtime):self.assertEqual(self.run_one(self.admission())['outcome'],'UNKNOWN_RECONCILE_ONLY')
        self.assertTrue((self.runtime/'supervisor.lock').exists())
        self.assertEqual(self.slots.snapshot()[0][2],'unknown')

    def test_late_backend_result_rejected_without_retry(self):
        times=iter((1,3));self.adapter.monotonic=lambda:next(times)
        with exclusive_lock(self.runtime):
            e=self.admission();self.assertEqual(self.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.backend.calls,1)
            self.adapter.reconcile(e,**self.backend.receipts)

    def test_budget_failure_does_not_claim_or_call(self):
        def fail(stage):
            if stage=='before_commit':raise OSError('synthetic-storage-failure')
        self.budget.fault=fail
        with exclusive_lock(self.runtime):self.assertEqual(self.run_one(self.admission())['outcome'],'UNKNOWN_RECONCILE_ONLY')
        self.assertEqual(self.backend.calls,0);self.assertEqual(self.slots.snapshot()[0][2],'pending')

    def test_settlement_storage_failure_keeps_recovery_fence(self):
        original=self.budget.settle
        def fail(*args,**kwargs):raise OSError('synthetic-settlement-storage-failure')
        self.budget.settle=fail
        with self.assertRaisesRegex(RuntimeError,'ASSOCIATED_TREE_UNVERIFIED'):
            with exclusive_lock(self.runtime):
                self.assertEqual(self.run_one(self.admission())['outcome'],'UNKNOWN_RECONCILE_ONLY')
                self.assertEqual(self.slots.snapshot()[0][2],'completed')
                with self.budget.tx() as c:
                    self.assertEqual(c.execute('SELECT state FROM reservations').fetchone()[0],'reserved')
        self.assertTrue((self.runtime/'supervisor.lock').exists())
        self.assertEqual(self.backend.calls,1)
        self.budget.settle=original

    def test_late_receipt_survives_adapter_restart_without_replay(self):
        times=iter((1,4));self.adapter.monotonic=lambda:next(times)
        with exclusive_lock(self.runtime):
            e=self.admission()
            self.assertEqual(self.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            # Reopen both durable stores and reconstruct the adapter: no in-memory
            # replay guard or cached receipt may be required for safety.
            slots=DurableSlots(self.slots.path,verify=LedgerEvidenceVerifier(self.trust,lambda:T+10))
            budget=GrowthLedger(self.budget.path,consumer=self.trust)
            restarted=SingleSlotAdapter(slots,budget,target=self.target,consumer=self.trust,
                backend=self.backend,wall_clock=lambda:T+10,monotonic=lambda:1)
            self.assertEqual(restarted.execute(e,self.plan,self.idle,self.request)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.backend.calls,1)
            with budget.tx() as c:
                self.assertEqual(c.execute('SELECT state FROM reservations').fetchone()[0],'reserved')
            self.assertEqual(restarted.reconcile(e,**self.backend.receipts)['outcome'],'COMPLETED')
            self.assertEqual(restarted.reconcile(e,**self.backend.receipts)['budget_result'],'DUPLICATE')
        self.assertEqual(len(self.backend.effects),1)

    def test_real_settlement_transaction_fault_preserves_reservation(self):
        settle=self.budget.settle
        def fail_settlement(*args,**kwargs):
            def fail(stage):
                if stage=='before_commit':raise OSError('synthetic-settlement-commit-failure')
            self.budget.fault=fail
            return settle(*args,**kwargs)
        self.budget.settle=fail_settlement
        with self.assertRaisesRegex(RuntimeError,'ASSOCIATED_TREE_UNVERIFIED'):
            with exclusive_lock(self.runtime):
                self.assertEqual(self.run_one(self.admission())['outcome'],'UNKNOWN_RECONCILE_ONLY')
                self.budget.fault=lambda stage:None
                with self.budget.tx() as c:
                    self.assertEqual(c.execute('SELECT state FROM reservations').fetchone()[0],'reserved')
                self.assertEqual(self.slots.snapshot()[0][2],'completed')
        self.assertTrue((self.runtime/'supervisor.lock').exists())
        self.assertEqual(self.backend.calls,1)

    def test_settlement_commit_ack_lost_keeps_fence_without_replay(self):
        settle=self.budget.settle
        def lost_ack(*args,**kwargs):
            settle(*args,**kwargs)
            raise OSError('synthetic-settlement-ack-lost')
        self.budget.settle=lost_ack
        with exclusive_lock(self.runtime):
            e=self.admission()
            self.assertEqual(self.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.backend.calls,1)
            self.budget.settle=settle
            self.assertEqual(self.adapter.reconcile(e,**self.backend.receipts)['budget_result'],'DUPLICATE')
        self.assertEqual(self.slots.snapshot()[0][2],'completed')

    def test_invalid_completion_clock_requires_explicit_reconciliation(self):
        for ended in (float('nan'),float('inf'),0,True):
            with self.subTest(ended=ended):
                # Each fault needs an independent persistent claim and reservation.
                case=SingleSlotTests();case.setUp()
                try:
                    times=iter((1,ended));case.adapter.monotonic=lambda:next(times)
                    with exclusive_lock(case.runtime):
                        e=case.admission()
                        self.assertEqual(case.run_one(e)['outcome'],'UNKNOWN_RECONCILE_ONLY')
                        self.assertEqual(case.slots.snapshot()[0][2],'unknown')
                        self.assertEqual(case.backend.calls,1)
                        case.adapter.reconcile(e,**case.backend.receipts)
                finally:case.doCleanups()

    def test_start_ack_failure_no_external_effect_no_retry(self):
        old=self.slots.start
        def failed_ack(*a,**kw):
            old(*a,**kw);raise OSError('synthetic-ack-lost')
        self.slots.start=failed_ack
        with exclusive_lock(self.runtime):
            e=self.admission();self.run_one(e);self.run_one(e)
        self.assertEqual(self.backend.calls,0);self.assertEqual(self.slots.snapshot()[0][2],'unknown')

    def test_receipt_wrong_request_never_releases_budget(self):
        self.backend.mode='lost'
        with exclusive_lock(self.runtime):
            e=self.admission();self.run_one(e)
            sr=self.backend.receipts['slot_receipt'];br=self.backend.receipts['budget_receipt']
            p=dict(br['payload']);p.pop('schema');p.pop('source_id');p.pop('principal_id');p.pop('inventory_id');p.pop('kind');p.pop('observed_at_epoch');p.pop('receipt_id');p.pop('expires_at_epoch');p['request_id']=oid('other')
            bad=signed('budget_receipt',T+10,**p)
            with self.assertRaisesRegex(AdapterError,'BINDING_MISMATCH'):self.adapter.reconcile(e,sr,bad)
            self.assertEqual(self.slots.snapshot()[0][2],'unknown')
            with self.budget.tx() as c:self.assertEqual(c.execute('SELECT state FROM reservations').fetchone()[0],'reserved')
            self.adapter.reconcile(e,sr,br)

# Fixed worker source: only temporary fixture paths are supplied as argv.
CANCEL_PROCESS_WORKER = r"""
import json, os, sys, time
from pathlib import Path
from autonomy.single_slot_adapter import CancellationJournal
journal, gate, phase, ready = sys.argv[1:]
Path(ready).write_text('ready')
limit = time.monotonic() + 10
while not Path(gate).exists():
    if time.monotonic() > limit: sys.exit(72)
    time.sleep(0.01)
def fault(stage):
    if stage == phase: os._exit(73)
result = CancellationJournal(journal, fault=fault).reserve(
    'fixture-cancel-identity', {'scope':'isolated_offline'}, protected=())
print(json.dumps(result), flush=True)
"""


class CancellationProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-cancel-process-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.children=[]
        self.addCleanup(self.close_children)

    def close_children(self):
        for child in self.children:
            if child.poll() is None: child.kill()
            child.communicate(timeout=10)

    def launch(self, journal, gate, phase='none'):
        import subprocess,sys,os
        ready=self.root/('ready-'+str(len(self.children)))
        child=subprocess.Popen([sys.executable,'-B','-c',CANCEL_PROCESS_WORKER,
            str(journal),str(gate),phase,str(ready)],cwd=str(Path(__file__).resolve().parent),
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            shell=False,creationflags=0x08000000 if os.name=='nt' else 0)
        self.children.append(child)
        return child,ready

    def finish(self, child, code=0):
        import json,subprocess
        try: out,err=child.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill();child.communicate(timeout=10)
            self.fail('bounded fixture subprocess timed out')
        self.assertEqual(child.returncode,code)
        self.assertEqual(err,b'')
        if code: self.assertEqual(out,b'');return None
        result=json.loads(out)
        self.assertIs(result['allow_cancel_dispatch'],False)
        self.assertIs(result['production_execution'],False)
        return result['outcome']

    def assert_one_row(self,journal):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(journal)) as c:
            self.assertEqual(c.execute('SELECT identity,state FROM cancellations').fetchall(),
                [('fixture-cancel-identity','RESERVED_RECONCILE_ONLY')])
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone(),('ok',))

    def test_four_processes_reserve_one_intent(self):
        import time
        journal=self.root/'journal.sqlite';gate=self.root/'gate'
        children=[self.launch(journal,gate) for _ in range(4)]
        deadline=time.monotonic()+10
        while not all(ready.exists() for _,ready in children):
            if time.monotonic()>deadline:self.fail('worker readiness timeout')
            time.sleep(0.01)
        gate.write_text('go')
        outcomes=[self.finish(child) for child,_ in children]
        self.assertEqual(outcomes.count('RESERVED_RECONCILE_ONLY'),1)
        self.assertEqual(outcomes.count('DUPLICATE_RESERVED'),3)
        self.assert_one_row(journal)

    def test_exit_after_commit_new_process_does_not_replay_intent(self):
        journal=self.root/'journal.sqlite';gate=self.root/'gate';gate.write_text('go')
        child,_=self.launch(journal,gate,'after_commit');self.finish(child,73)
        child,_=self.launch(journal,gate)
        self.assertEqual(self.finish(child),'DUPLICATE_RESERVED')
        self.assert_one_row(journal)

    def test_exit_before_commit_new_process_records_intent_once(self):
        journal=self.root/'journal.sqlite';gate=self.root/'gate';gate.write_text('go')
        child,_=self.launch(journal,gate,'before_commit');self.finish(child,73)
        child,_=self.launch(journal,gate)
        self.assertEqual(self.finish(child),'RESERVED_RECONCILE_ONLY')
        child,_=self.launch(journal,gate)
        self.assertEqual(self.finish(child),'DUPLICATE_RESERVED')
        self.assert_one_row(journal)

if __name__=='__main__':unittest.main()
