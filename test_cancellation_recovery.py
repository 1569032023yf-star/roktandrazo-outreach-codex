"""Offline durable cancellation recovery, including real exited owner processes."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from autonomy import lock_recovery
from autonomy.cancellation_recovery import recover_cancellation, PROTOCOL, _hash
from autonomy.cancellation_terminal import PROTOCOL as TERMINAL
from autonomy.growth_ledger import digest, GrowthLedger
from autonomy.single_slot_adapter import AdapterError, SingleSlotAdapter, CancellationJournal, OfflineTarget
from autonomy.durable_slots import DurableSlots
from autonomy.ledger_evidence import LedgerEvidenceVerifier
from test_growth_ledger import signed, amounts, T, consumer
from types import SimpleNamespace
import test_cancellation_cost as fixtures


def authorization(c, data, path):
    terminal,sr,br,cr,binding=data
    fixed=dict(binding_hash=digest(binding),receipts_hash=digest([x['payload'] for x in (terminal,sr,br,cr)]),
        recovery_id=_hash(os.path.normcase(str(path.resolve())).encode()),protocol=PROTOCOL)
    context=dict(fixed,**c.adapter.ids,scope='isolated_offline',production_execution=False,
        old_lock_sha256=_hash((c.runtime/'supervisor.lock').read_bytes()),
        recovery_process_identity_hash=digest(lock_recovery.process_identity(os.getpid())))
    return signed('offline_cancel_recovery',T+10,**context)


def prepare(fixture):
    c=fixture.case
    admission,journal,fields,cost,cost_id=fixture.prepare()
    c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
    binding=cost['payload']['claim_binding']
    proof=dict(binding,cancel_terminal_protocol=TERMINAL,cancel_outcome='already_completed',
        external_drained=True,terminal_confirmed=True);proof.pop('inventory_id')
    fee=dict(binding,outcome='known',externally_reconciled=True,actual=amounts(0));fee.pop('inventory_id')
    return (signed('offline_cancel_terminal',T+10,**proof),c.backend.receipts['slot_receipt'],
        c.backend.receipts['budget_receipt'],signed('budget_receipt',T+10,**fee),binding)


def worker_initial(destination):
    f=fixtures.CancellationCostTests();f.setUp();c=f.case
    with lock_recovery.exclusive_lock(c.runtime):
        data=prepare(f)
        payload=dict(root=str(c.root),runtime=str(c.runtime),slots=c.slots.path,
            budget=c.budget.path,journal=str(c.adapter.cancellation_journal.path),data=data)
        Path(destination).write_text(json.dumps(payload),encoding='utf-8')
        os._exit(73)


def reopen(destination):
    p=json.loads(Path(destination).read_text(encoding='utf-8'));trust=consumer()
    c=SimpleNamespace(root=Path(p['root']),runtime=Path(p['runtime']),trust=trust)
    c.slots=DurableSlots(p['slots'],verify=LedgerEvidenceVerifier(trust,lambda:T+10))
    c.budget=GrowthLedger(p['budget'],consumer=trust)
    c.target=OfflineTarget(str(c.runtime),p['slots'],p['budget'],'synthetic-backend')
    # No backend at all: recovery cannot accidentally dispatch or cancel.
    c.adapter=SingleSlotAdapter(c.slots,c.budget,target=c.target,consumer=trust,
        wall_clock=lambda:T+10,cancellation_journal=CancellationJournal(p['journal']))
    return c,p['data']


def worker_resume(destination,phase):
    c,data=reopen(destination);path=c.root/'recovery.sqlite'
    def fault(stage):
        if stage==phase:os._exit(73)
    recover_cancellation(c.adapter,authorization(c,data,path),*data[:4],recovery_path=path,fault=fault)
    raise RuntimeError('EXPECTED_PROCESS_EXIT_NOT_REACHED')


class CancellationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.CancellationCostTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.c=self.f.case;self.path=self.c.root/'recovery.sqlite'

    def run_recovery(self,data,fault=None):
        return recover_cancellation(self.c.adapter,authorization(self.c,data,self.path),*data[:4],
            recovery_path=self.path,fault=fault)

    def test_changed_ledger_paths_rejected_before_any_write(self):
        import shutil
        c=self.c
        with lock_recovery.exclusive_lock(c.runtime):
            data=prepare(self.f)
            proof=authorization(c,data,self.path)
            original_lock=(c.runtime/'supervisor.lock').read_bytes()
            for ledger in (c.slots,c.budget):
                original=ledger.path
                copy=c.root/(Path(original).name+'.copy')
                shutil.copyfile(original,copy)
                before=copy.read_bytes()
                ledger.path=str(copy)
                try:
                    with self.assertRaisesRegex(AdapterError,'LEDGER_TARGET_MISMATCH'):
                        recover_cancellation(c.adapter,proof,*data[:4],recovery_path=self.path)
                finally:ledger.path=original
                self.assertEqual(copy.read_bytes(),before)
                self.assertEqual((c.runtime/'supervisor.lock').read_bytes(),original_lock)
                self.assertFalse(self.path.exists())
            self.assertEqual(self.run_recovery(data)['outcome'],'COMPLETED')

    def test_success_duplicate_and_journal_immutable(self):
        c=self.c
        with lock_recovery.exclusive_lock(c.runtime):
            data=prepare(self.f);before=c.adapter.cancellation_journal.path.read_bytes()
            result=self.run_recovery(data)
            self.assertEqual(result['outcome'],'COMPLETED')
            self.assertFalse(result['allow_dispatch']);self.assertFalse(result['allow_cancel_dispatch'])
            self.assertEqual(self.run_recovery(data)['outcome'],'DUPLICATE_COMPLETED')
            self.assertEqual(c.adapter.cancellation_journal.path.read_bytes(),before)
            self.assertEqual(c.backend.calls,1)

    def test_faults_reopen_all_ledgers_keep_fence_until_complete(self):
        for phase in ('before_prepared_commit','after_prepared','after_cost_settled','after_original_settled',
                      'after_completed_commit','before_verified_closed'):
            with self.subTest(phase=phase):
                f=fixtures.CancellationCostTests();f.setUp();c=f.case
                try:
                    with lock_recovery.exclusive_lock(c.runtime):
                        data=prepare(f);path=c.root/'recovery.sqlite'
                        def fault(stage):
                            if stage==phase:raise OSError('fixture-secret')
                        result=recover_cancellation(c.adapter,authorization(c,data,path),*data[:4],recovery_path=path,fault=fault)
                        self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
                        self.assertEqual(json.loads((c.runtime/'supervisor.lock').read_bytes())['tree_state'],'unverified')
                        with self.assertRaisesRegex(AdapterError,'RECOVERY_ONLY_NO_DISPATCH'):
                            c.adapter.reconcile({},*data[1:3])
                        with self.assertRaisesRegex(AdapterError,'RECOVERY_ONLY_NO_DISPATCH'):
                            c.adapter.execute({}, {}, {}, {})
                        c.slots=DurableSlots(c.slots.path,verify=c.slots.verify)
                        c.budget=GrowthLedger(c.budget.path,consumer=c.trust)
                        c.adapter=SingleSlotAdapter(c.slots,c.budget,target=c.target,consumer=c.trust,
                            backend=c.backend,wall_clock=lambda:T+10,cancellation_journal=CancellationJournal(c.root/'cancel.sqlite'))
                        recovered=recover_cancellation(c.adapter,authorization(c,data,path),*data[:4],recovery_path=path)
                        self.assertIn(recovered['outcome'],('COMPLETED','DUPLICATE_COMPLETED'))
                        self.assertEqual(json.loads((c.runtime/'supervisor.lock').read_bytes())['tree_state'],'verified_closed')
                        self.assertEqual(c.backend.calls,1)
                finally:f.doCleanups()

    def test_wrong_signature_and_changed_terminal_are_not_replayed(self):
        c=self.c
        with lock_recovery.exclusive_lock(c.runtime):
            data=prepare(self.f)
            bad=authorization(c,data,self.path);bad['mac']='0'*64
            with self.assertRaises(AdapterError):recover_cancellation(c.adapter,bad,*data[:4],recovery_path=self.path)
            self.assertFalse(self.path.exists())
            self.run_recovery(data)
            changed=list(data);changed[2]=signed('budget_receipt',T+10,**dict(c.common,
                claim_token_hash=data[4]['claim_token_hash'],outcome='known',externally_reconciled=True,actual=amounts(0)))
            with self.assertRaisesRegex(AdapterError,'RECOVERY_RECEIPT_CONFLICT'):self.run_recovery(changed)
            self.assertEqual(c.backend.calls,1)
            self.assertEqual(json.loads((c.runtime/'supervisor.lock').read_bytes())['tree_state'],'unverified')
            self.assertEqual(self.run_recovery(data)['outcome'],'DUPLICATE_COMPLETED')

    def test_explicit_authority_cannot_substitute_original_lock_identity(self):
        c=self.c
        with lock_recovery.exclusive_lock(c.runtime) as owned:
            data=prepare(self.f);saved=dict(owned)
            for changes,error in ((dict(token='different-token'),'ORIGINAL_LOCK_TOKEN_MISMATCH'),
                    (dict(process_identity='different-process'),'ORIGINAL_PROCESS_IDENTITY_MISMATCH'),
                    (dict(recovery_only=True,recovery_required=False),'LOCK_CONTEXT_REJECTED')):
                with self.subTest(changes=tuple(changes)):
                    try:
                        owned.update(changes)
                        lock_recovery._write_state(c.runtime/'supervisor.lock',owned)
                        # Even a fresh signed authority over the changed raw lock
                        # cannot substitute it for the persisted journal identity.
                        with self.assertRaisesRegex(AdapterError,error):self.run_recovery(data)
                        self.assertFalse(self.path.exists())
                    finally:
                        owned.clear();owned.update(saved)
                        lock_recovery._write_state(c.runtime/'supervisor.lock',owned)
            self.assertEqual(c.backend.calls,1)
            self.assertEqual(self.run_recovery(data)['outcome'],'COMPLETED')

    def test_real_process_exit_recovery_and_recovery_only_claim_denial(self):
        for phase in ('after_prepared_commit','after_cost_settled'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix='u1-recovery-process-') as temp:
                base=Path(temp);descriptor=base/'descriptor.json'
                env=dict(os.environ,TEMP=temp,TMP=temp,PYTHONUTF8='1')
                def launch(code):
                    process=subprocess.Popen([sys.executable,'-B','-c',code,str(descriptor),phase],
                        cwd=str(Path(__file__).resolve().parent),env=env,stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    try:out,err=process.communicate(timeout=20)
                    except BaseException:
                        process.kill();process.communicate(timeout=10);raise
                    self.assertEqual(process.returncode,73,err.decode(errors='replace')[:200])
                launch('import sys;from test_cancellation_recovery import worker_initial;worker_initial(sys.argv[1])')
                c,data=reopen(descriptor)
                self.assertTrue(c.root.resolve().is_relative_to(base.resolve()))
                journal=c.adapter.cancellation_journal.path.read_bytes()
                launch('import sys;from test_cancellation_recovery import worker_resume;worker_resume(sys.argv[1],sys.argv[2])')
                c,data=reopen(descriptor);path=c.root/'recovery.sqlite'
                self.assertEqual(json.loads((c.runtime/'supervisor.lock').read_bytes())['tree_state'],'unverified')
                def assert_no_dispatch(stage):
                    if stage=='after_prepared':
                        with self.assertRaisesRegex(AdapterError,'RECOVERY_ONLY_NO_DISPATCH'):
                            c.adapter.execute({}, {}, {}, {})
                        from autonomy.growth_ledger import GrowthError
                        with self.assertRaisesRegex(GrowthError,'RECOVERY_ONLY_NO_DISPATCH'):
                            c.budget.reserve_then_claim({},c.slots,'other',{},now=T+10,epoch=1,owner='owner')
                result=recover_cancellation(c.adapter,authorization(c,data,path),*data[:4],
                    recovery_path=path,fault=assert_no_dispatch)
                self.assertEqual(result['outcome'],'COMPLETED')
                self.assertEqual(c.adapter.cancellation_journal.path.read_bytes(),journal)
                state=json.loads((c.runtime/'supervisor.lock').read_bytes())
                self.assertTrue(state['recovery_only']);self.assertEqual(state['tree_state'],'verified_closed')
                with closing(sqlite3.connect(path)) as db:
                    self.assertEqual(db.execute('SELECT state FROM recoveries').fetchall(),[('COMPLETED',)])
                    self.assertGreaterEqual(db.execute('SELECT count(*) FROM handoffs').fetchone()[0],1)

    def test_live_owner_unknown_guard_and_schema_rejected(self):
        c=self.c
        with lock_recovery.exclusive_lock(c.runtime):
            data=prepare(self.f)
            raw=(c.runtime/'supervisor.lock').read_bytes()
            lease=lock_recovery._ACTIVE_LEASE.set(None)
            try:
                with self.assertRaisesRegex(AdapterError,'STILL_ALIVE'):self.run_recovery(data)
            finally:lock_recovery._ACTIVE_LEASE.reset(lease)
            self.assertEqual((c.runtime/'supervisor.lock').read_bytes(),raw)
            self.run_recovery(data)
            with closing(sqlite3.connect(self.path)) as db:
                db.execute('PRAGMA user_version=2');db.commit()
            with self.assertRaisesRegex(AdapterError,'RECOVERY_SCHEMA_REJECTED'):self.run_recovery(data)
            lock_recovery.mark_tree('verified_closed')
        with tempfile.TemporaryDirectory(prefix='u1-old-guard-') as temp:
            guard=Path(temp)/'supervisor.recovery.lock';guard.write_bytes(b'')
            with self.assertRaisesRegex(RuntimeError,'LEGACY_OR_UNKNOWN'):
                with lock_recovery._guard(Path(temp)):pass
            self.assertEqual(guard.read_bytes(),b'')

    def test_concurrent_guard_initialization_publishes_complete_marker(self):
        code="""import sys,time
from pathlib import Path
from autonomy.lock_recovery import _guard
root=Path(sys.argv[1]);gate=root/'gate';deadline=time.monotonic()+10
while not gate.exists():
 if time.monotonic()>deadline:raise RuntimeError('gate timeout')
 time.sleep(.005)
while True:
 try:
  with _guard(root):
   counter=root/'counter';n=int(counter.read_text()) if counter.exists() else 0
   time.sleep(.01);counter.write_text(str(n+1))
  break
 except OSError:
  if time.monotonic()>deadline:raise
  time.sleep(.005)
"""
        with tempfile.TemporaryDirectory(prefix='u1-guard-concurrent-') as temp:
            root=Path(temp);children=[]
            try:
                for _ in range(4):
                    children.append(subprocess.Popen([sys.executable,'-B','-c',code,temp],
                        cwd=str(Path(__file__).resolve().parent),stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)))
                (root/'gate').write_text('go')
                for child in children:
                    out,err=child.communicate(timeout=15)
                    self.assertEqual(child.returncode,0,err.decode(errors='replace')[:200])
                self.assertEqual((root/'counter').read_text(),'4')
                self.assertEqual((root/'supervisor.recovery.lock').read_bytes(),b'rokt.recovery-guard.v2\n')
            finally:
                for child in children:
                    if child.poll() is None:child.kill();child.communicate(timeout=10)


if __name__=='__main__':unittest.main()
