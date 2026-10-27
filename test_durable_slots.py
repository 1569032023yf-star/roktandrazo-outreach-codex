import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from autonomy.durable_slots import DurableSlots, LedgerError, INVENTORY, STATES


def verified(e):
    return dict(e) if e.get('fixture_signature') == 'verified-fixture' else None


def evidence(kind, **kw):
    return dict(kind=kind,inventory=INVENTORY,observed=0,expires=999999,fixture_signature='verified-fixture',**kw)


def idle(slot='s1', epoch=1, owner='owner'):
    return evidence('idle',slot=slot,epoch=epoch,owner=owner,external_state='idle',existing_lock_held=True)


def child(path, mode, gate, output):
    ledger=DurableSlots(path,verify=verified)
    gate.wait(10)
    if mode=='preclaim': os._exit(73)
    if mode in ('before','after'):
        ledger.fault=lambda stage: os._exit(73) if stage==mode+'_commit' else None
    try:
        token=ledger.claim('s1',idle(),now=10,epoch=1,owner='owner')
        if mode=='lost_receipt':
            ledger.start('s1',token,epoch=1,owner='owner')
            Path(path+'.effect').write_text('one')
            os._exit(73)
        output.put(('claimed',token))
    except LedgerError as exc:
        output.put(('blocked',str(exc)))


class DurableTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-slots-')
        self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'isolated.sqlite')
        self.l=DurableSlots(self.path,verify=verified)
        self.l.initialize()
        self.l.switch_authority(0,'owner',evidence('authority',previous_epoch=0,owner='owner',drained=True,old_disabled=True),now=1)
        self.admit('s1',10)

    def admit(self,slot,due,now=None):
        return self.l.admit_due(slot,due,evidence('schedule',slot=slot,next_due=due,epoch=1,owner='owner',latest_due=True),now=due if now is None else now,epoch=1,owner='owner')

    def claim(self):
        return self.l.claim('s1',idle(),now=10,epoch=1,owner='owner')

    def test_signed_missed_slots_cannot_be_omitted(self):
        e=evidence('schedule',slot='s3',next_due=30,epoch=1,owner='owner',latest_due=True,missed=[['s2',20]])
        before=self.l.snapshot()
        with self.assertRaisesRegex(LedgerError,'EVIDENCE_CONFLICT'):
            self.l.admit_due('s3',30,e,now=30,epoch=1,owner='owner')
        self.assertEqual(self.l.snapshot(),before)
        for bad in ((('s2',),), (None,), ('s2',)):
            with self.assertRaisesRegex(LedgerError,'INVALID_MISSED_SLOTS'):
                self.l.admit_due('s3',30,e,now=30,epoch=1,owner='owner',missed=bad)
        self.l.admit_due('s3',30,e,now=30,epoch=1,owner='owner',missed=(('s2',20),))
        self.assertEqual([r[:3] for r in self.l.snapshot()],[('s1',10,'deferred'),('s2',20,'deferred'),('s3',30,'pending')])

    def receipt(self,token,state):
        return evidence('receipt',slot='s1',state=state,epoch=1,owner='owner',external_drained=True,token=token,receipt='receipt1')

    def test_states_terminal_and_receipt_duplicate(self):
        seen={'pending'}
        token=self.claim(); seen.add(self.l.snapshot()[0][2])
        self.l.start('s1',token,epoch=1,owner='owner'); seen.add(self.l.snapshot()[0][2])
        self.l.mark_unknown('s1',token,epoch=1,owner='owner'); seen.add(self.l.snapshot()[0][2])
        receipt=self.receipt(token,'completed')
        self.l.reconcile('s1','completed',receipt,now=20,epoch=1,owner='owner'); seen.add('completed')
        self.assertEqual(self.l.reconcile('s1','completed',receipt,now=21,epoch=1,owner='owner'),'DUPLICATE_RECEIPT')
        with self.assertRaises(LedgerError): self.claim()
        self.assertEqual(seen,STATES-{'failed','deferred'})

    def test_failure_duplicate_and_auth_rejection_recovery(self):
        bad=idle(); bad['fixture_signature']='rejected'
        with self.assertRaises(LedgerError): self.l.claim('s1',bad,now=10,epoch=1,owner='owner')
        self.assertEqual(self.l.snapshot()[0][2],'pending')
        token=self.claim(); receipt=self.receipt(token,'failed')
        self.l.reconcile('s1','failed',receipt,now=11,epoch=1,owner='owner')
        self.assertEqual(self.l.reconcile('s1','failed',receipt,now=12,epoch=1,owner='owner'),'DUPLICATE_RECEIPT')
        with self.assertRaises(LedgerError): self.claim()
        for n in (2,3):
            slot='s'+str(n); due=n*21600
            self.admit(slot,due)
            token=self.l.claim(slot,idle(slot),now=due,epoch=1,owner='owner')
            self.l.start(slot,token,epoch=1,owner='owner')
            r=self.receipt(token,'completed'); r['slot']=slot
            self.l.reconcile(slot,'completed',r,now=due+100,epoch=1,owner='owner')
        self.assertEqual([r[2] for r in self.l.snapshot()],['failed','completed','completed'])

    def test_unknown_receipt_loss_never_replays_after_restart(self):
        token=self.claim(); self.l.start('s1',token,epoch=1,owner='owner')
        # Synthetic external effect, followed by missing receipt; never a Provider call.
        effects=Path(self.temp.name)/'effects'; effects.write_text('one')
        self.l.mark_unknown('s1',token,epoch=1,owner='owner')
        self.l=DurableSlots(self.path,verify=verified)
        for now in (100,800000):
            with self.assertRaises(LedgerError): self.l.claim('s1',idle(),now=now,epoch=1,owner='owner')
            with self.assertRaises(LedgerError): self.l.start('s1',token,epoch=1,owner='owner')
        self.admit('s2',21600)
        with self.assertRaises(LedgerError): self.l.claim('s2',idle('s2'),now=21600,epoch=1,owner='owner')
        self.assertEqual(effects.read_text(),'one')

    def test_multiple_process_atomic_claim(self):
        ctx=mp.get_context('spawn'); gate=ctx.Event(); out=ctx.Queue()
        jobs=[ctx.Process(target=child,args=(self.path,'normal',gate,out)) for _ in range(2)]
        for p in jobs:p.start()
        gate.set()
        results=[out.get(timeout=20) for _ in jobs]
        for p in jobs:p.join(20); self.assertEqual(p.exitcode,0)
        out.close(); out.join_thread()
        self.assertEqual(sum(x[0]=='claimed' for x in results),1)

    def test_process_exit_before_and_after_commit(self):
        ctx=mp.get_context('spawn')
        for mode,expected in [('preclaim','pending'),('before','pending'),('after','claimed')]:
            gate=ctx.Event(); out=ctx.Queue()
            p=ctx.Process(target=child,args=(self.path,mode,gate,out)); p.start(); gate.set(); p.join(20)
            self.assertEqual(p.exitcode,73)
            self.assertEqual(DurableSlots(self.path).snapshot()[0][2],expected)
            out.close(); out.join_thread()
        with self.assertRaises(LedgerError):self.claim()

    def test_verified_payload_only_and_existing_lock(self):
        from autonomy.lock_recovery import exclusive_lock
        with exclusive_lock(Path(self.temp.name)/'locks'):
            verifier=lambda envelope: dict(envelope['verified'])
            ledger=DurableSlots(self.path,verify=verifier)
            outer=dict(idle(),verified=dict(idle(),external_state='running'))
            with self.assertRaises(LedgerError):ledger.claim('s1',outer,now=10,epoch=1,owner='owner')
            outer=dict(external_state='running',verified=idle())
            token=ledger.claim('s1',outer,now=10,epoch=1,owner='owner')
            self.assertTrue(token)
        self.assertFalse((Path(self.temp.name)/'locks'/'supervisor.lock').exists())

    def test_external_effect_process_exit_without_receipt(self):
        ctx=mp.get_context('spawn'); gate=ctx.Event(); out=ctx.Queue()
        p=ctx.Process(target=child,args=(self.path,'lost_receipt',gate,out))
        p.start(); gate.set(); p.join(20); self.assertEqual(p.exitcode,73)
        out.close(); out.join_thread()
        self.assertEqual(self.l.snapshot()[0][2],'running')
        with self.assertRaises(LedgerError):self.claim()
        self.assertEqual(Path(self.path+'.effect').read_text(),'one')

    def test_no_invalid_terminal_transition_or_foreign_receipt(self):
        token=self.claim();r=self.receipt(token,'completed');r['token']='foreign'
        with self.assertRaises(LedgerError):self.l.reconcile('s1','completed',r,now=11,epoch=1,owner='owner')
        with self.assertRaises(LedgerError):self.l.reconcile('s1','pending',r,now=11,epoch=1,owner='owner')
        r=self.receipt(token,'completed')
        self.l.reconcile('s1','completed',r,now=11,epoch=1,owner='owner')
        r['receipt']='different'
        with self.assertRaises(LedgerError):self.l.reconcile('s1','completed',r,now=12,epoch=1,owner='owner')
        with self.assertRaises(LedgerError):self.l.mark_unknown('s1',token,epoch=1,owner='owner')

    def test_storage_fault_before_after_commit_and_readonly(self):
        def fail(stage):
            if stage=='before_commit':raise OSError('secret-disk-full')
        self.l.fault=fail
        with self.assertRaisesRegex(LedgerError,'^STORAGE_OUTCOME_UNVERIFIED$'):self.claim()
        self.assertEqual(self.l.snapshot()[0][2],'pending')
        self.l.fault=lambda stage: None
        def readonly(path,**kw):
            return sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True,**kw)
        ro=DurableSlots(self.path,verify=verified,connect=readonly)
        with self.assertRaisesRegex(LedgerError,'^STORAGE_OUTCOME_UNVERIFIED$'):ro.claim('s1',idle(),now=10,epoch=1,owner='owner')
        def after(stage):
            if stage=='after_commit':raise OSError('secret-receipt-lost')
        self.l.fault=after
        with self.assertRaises(LedgerError):self.claim()
        self.assertEqual(self.l.snapshot()[0][2],'claimed')
        self.l.fault=lambda stage: None
        with self.assertRaises(LedgerError):self.claim()

    def test_epoch_fencing_and_active_drain(self):
        token=self.claim()
        switch=evidence('authority',previous_epoch=1,owner='new',drained=True,old_disabled=True)
        with self.assertRaises(LedgerError):self.l.switch_authority(1,'new',switch,now=10)
        self.l.reconcile('s1','failed',self.receipt(token,'failed'),now=11,epoch=1,owner='owner')
        self.assertEqual(self.l.switch_authority(1,'new',switch,now=12),2)
        with self.assertRaisesRegex(LedgerError,'AUTHORITY_FENCED'):self.l.start('s1',token,epoch=1,owner='owner')
        with self.assertRaises(LedgerError):self.l.switch_authority(1,'new',switch,now=13)
        # Rollback restores old name under a NEW epoch, never epoch reuse.
        self.assertEqual(self.l.switch_authority(2,'owner',evidence('authority',previous_epoch=2,owner='owner',drained=True,old_disabled=True),now=14),3)
        with self.assertRaises(LedgerError):self.claim()

    def test_external_conflicts_and_default_denial(self):
        for k,v in [('inventory','other'),('external_state','running'),('epoch',2),('expires',9),('existing_lock_held',False),('existing_lock_held',1)]:
            e=idle();e[k]=v
            with self.assertRaises(LedgerError):self.l.claim('s1',e,now=10,epoch=1,owner='owner')
        with self.assertRaises(LedgerError):DurableSlots(self.path).claim('s1',idle(),now=10,epoch=1,owner='owner')
        self.assertEqual(self.l.snapshot()[0][2],'pending')

    def test_schedule_gap_no_catchup_duplicate_cross_date(self):
        # Supplied fixture due values, not an inferred production cron.
        # Last completion=0; next due=6h. Observed 18.2h later: 6h/12h missed.
        missed=(('missed6',21600),('missed12',43200))
        e=evidence('schedule',slot='latest18',next_due=64800,epoch=1,owner='owner',latest_due=True,missed=[list(x) for x in missed])
        self.l.admit_due('latest18',64800,e,now=65520,epoch=1,owner='owner',missed=missed)
        self.assertEqual([r[2] for r in self.l.snapshot()],['deferred','deferred','deferred','pending'])
        for slot in ('s1','missed6','missed12'):
            with self.assertRaises(LedgerError):self.l.claim(slot,idle(slot),now=65520,epoch=1,owner='owner')
        self.assertEqual(self.admit('latest18',64800,now=65520),'pending')
        with self.assertRaises(LedgerError):self.admit('retro',50000,now=65520)
        token=self.l.claim('latest18',idle('latest18'),now=65520,epoch=1,owner='owner')
        self.l.start('latest18',token,epoch=1,owner='owner')
        r=self.receipt(token,'completed');r['slot']='latest18'
        self.l.reconcile('latest18','completed',r,now=90000,epoch=1,owner='owner')
        # Explicit completion-anchored next_due, not rounded to midnight.
        self.admit('next',111600)
        self.assertEqual(self.l.snapshot()[-1][1],111600)

if __name__=='__main__':unittest.main()
