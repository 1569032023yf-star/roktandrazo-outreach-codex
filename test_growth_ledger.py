import hashlib
import hmac
import multiprocessing as mp
import sqlite3
from pathlib import Path
import tempfile
import unittest
from autonomy.growth_ledger import GrowthLedger,GrowthError,DIMENSIONS,business_day,day_start
from autonomy.host_preparation import EvidenceConsumer,TrustedSource,canonical
from autonomy.unattended_policy import INVENTORY

KEY=b'synthetic-offline-key-not-production-0001'
T=day_start('2026-10-26')

def oid(x):return hashlib.sha256(x.encode()).hexdigest()

def consumer():return EvidenceConsumer({'fixture':TrustedSource('fixture','fixture-user',KEY)})

def signed(kind,now,**data):
    p=dict(schema='rokt.host-evidence.v1',source_id='fixture',principal_id='fixture-user',inventory_id=INVENTORY,kind=kind,observed_at_epoch=now,expires_at_epoch=now+100,receipt_id='fixture-receipt',**data)
    return dict(payload=p,mac=hmac.new(KEY,canonical(p),hashlib.sha256).hexdigest())

def amounts(n=1):return dict.fromkeys(DIMENSIONS,n)

def request(name,now=T+10,amount=None,run='run',cache=False):
    return signed('budget_request',now,request_id=oid(name),run_id=oid(run),day=business_day(now),amount=amount if amount is not None else amounts(),cache_hit=cache)

def worker(path,name,gate,out):
    l=GrowthLedger(path,consumer=consumer());gate.wait(10)
    try:out.put(l.reserve(request(name,amount=amounts(6)),now=T+10))
    except GrowthError as e:out.put(str(e))

class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-growth-');self.addCleanup(self.temp.cleanup)
        self.path=str(Path(self.temp.name)/'growth.sqlite');self.l=GrowthLedger(self.path,consumer=consumer());self.l.initialize()

    def history(self):
        self.l.import_history(signed('growth_history',T,as_of=T-100,rule=oid('rule'),event_id=oid('history'),all_history_complete=True,organizations=[dict(id=oid('old'),qualified=False),dict(id=oid('prior'),qualified=True)],sites=[oid('oldsite')],emails=[oid('oldemail')]),now=T)

    def observe(self,n,orgs=(),*,stamp=None,rule='rule',safe=(2,2),complete=True,historical=False,sites=(),emails=()):
        stamp=T+n if stamp is None else stamp
        return self.l.observe(signed('growth_observation',stamp,measured_at=stamp,rule=oid(rule),snapshot=oid('snap'+str(n)),event_id=oid('event'+str(n)),complete=complete,historical_import=historical,organizations=[dict(id=oid(x),qualified=q) for x,q in orgs],sites=[oid(x) for x in sites],emails=[oid(x) for x in emails],safe_readings=list(safe)),now=stamp)

    def caps(self,day='2026-10-26',n=10,wall=20):
        return self.l.approve_budget(signed('budget_approval',T,day=day,limits=amounts(n),run_wall_limit=wall),now=T)

    def settle(self,name,now=T+20,outcome='known',actual=None):
        return self.l.settle(signed('budget_receipt',now,request_id=oid(name),run_id=oid('run'),outcome=outcome,actual=amounts() if actual is None else actual,externally_reconciled=True),now=now)

    def test_wrong_run_cannot_release_budget_after_reopen(self):
        self.caps(n=6)
        self.l.reserve(request('a',amount=amounts(6)),now=T+10)
        for run in (None,oid('wrong-run'),True):
            receipt=signed('budget_receipt',T+20,request_id=oid('a'),run_id=run,
                outcome='known',actual=amounts(0),externally_reconciled=True)
            with self.assertRaisesRegex(GrowthError,'RECEIPT_RUN_MISMATCH'):
                self.l.settle(receipt,now=T+20)
        self.l=GrowthLedger(self.path,consumer=consumer())
        with self.assertRaisesRegex(GrowthError,'CAP_REACHED'):
            self.l.reserve(request('b',amount=amounts(6)),now=T+20)
        with self.l.tx() as c:
            row=c.execute('SELECT state,charged FROM reservations').fetchone()
            self.assertEqual(row['state'],'reserved')
            self.assertEqual(__import__('json').loads(row['charged']),amounts(6))
        self.assertEqual(self.settle('a',actual=amounts(0)),'SETTLED')
        self.assertEqual(self.l.reserve(request('b',amount=amounts(6)),now=T+20),'RESERVED_NOT_DISPATCHED')

    def test_bound_settlement_requires_exact_claim_and_operation(self):
        from autonomy.growth_ledger import digest
        from autonomy.lock_recovery import exclusive_lock
        self.caps();ledger,e,se=self.slot_fixture()
        with exclusive_lock(Path(self.temp.name)/'lock'):
            token=self.l.reserve_then_claim(e,ledger,'slot',se,now=T+10,epoch=1,owner='owner')
        binding=dict(e['payload']['claim_binding'])
        binding.pop('inventory_id') # signed() supplies the fixed Inventory.
        good=dict(binding,claim_token_hash=digest(token),outcome='known',actual=amounts(0),externally_reconciled=True)
        for field in ('slot','epoch','owner','claim_token_hash'):
            for value in (None,'wrong'):
                bad=dict(good,**{field:value})
                with self.assertRaisesRegex(GrowthError,'CLAIM_RECEIPT_CONFLICT'):
                    self.l.settle(signed('budget_receipt',T+20,**bad),now=T+20)
        # Missing claim acknowledgement also preserves the entire reservation.
        with self.l.tx() as c:c.execute('UPDATE reservations SET claim_hash=NULL')
        with self.assertRaisesRegex(GrowthError,'CLAIM_RECEIPT_CONFLICT'):
            self.l.settle(signed('budget_receipt',T+20,**good),now=T+20)
        with self.l.tx() as c:
            self.assertEqual(c.execute('SELECT state FROM reservations').fetchone()[0],'reserved')
            c.execute('UPDATE reservations SET claim_hash=?',(digest(token),))
        receipt=signed('budget_receipt',T+20,**good)
        self.assertEqual(self.l.settle(receipt,now=T+20),'SETTLED')
        self.assertEqual(self.l.settle(receipt,now=T+20),'DUPLICATE')

    def test_business_day_baseline_freeze_restart(self):
        self.assertEqual(business_day(T-1),'2026-10-25');self.assertEqual(business_day(T),'2026-10-26')
        self.history();self.observe(5)
        first=self.l.report('2026-10-26',now=T+5)
        self.l=GrowthLedger(self.path,consumer=consumer());self.observe(10)
        second=self.l.report('2026-10-26',now=T+10)
        self.assertEqual(first['baseline_id'],second['baseline_id']);self.assertTrue(second['partial_day'])

    def test_new_qualified_existing_conversion_assets_dedup(self):
        self.history();self.observe(0)
        self.observe(10,[('new',True),('old',True),('prior',False)],sites=['site','oldsite'],emails=['email','oldemail'])
        self.observe(20,[('new',True),('old',True),('prior',True)],sites=['site'],emails=['email'])
        r=self.l.report('2026-10-26',now=T+20)
        for k in ('NEW_UNIQUE_ORGANIZATIONS','NEW_QUALIFIED_NEW_ORGANIZATIONS','EXISTING_ORGANIZATIONS_NEWLY_QUALIFIED','NEW_VERIFIED_OFFICIAL_SITES','NEW_FIRST_PARTY_EMAILS'):self.assertEqual(r[k],1,k)
        self.assertEqual(r['SAFE_NET_CHANGE'],0)

    def test_import_and_merge_do_not_manufacture_growth(self):
        self.history();self.observe(0)
        self.observe(10,[('imported',True)],historical=True)
        r=self.l.report('2026-10-26',now=T+10)
        self.assertEqual(r['NEW_UNIQUE_ORGANIZATIONS'],0);self.assertEqual(r['EXISTING_ORGANIZATIONS_NEWLY_QUALIFIED'],0)
        self.observe(20,[('alias',True)])
        self.l.merge(signed('growth_merge',T+21,event_id=oid('merge'),source=oid('alias'),target=oid('prior')),now=T+21)
        r=self.l.report('2026-10-26',now=T+21)
        self.assertEqual(r['NEW_UNIQUE_ORGANIZATIONS'],'UNKNOWN');self.assertIn('MERGE',r['reason'])
        self.observe(30,[('alias',True)])
        self.observe(40,stamp=T+86400)
        self.assertEqual(self.l.report('2026-10-27',now=T+86400)['NEW_UNIQUE_ORGANIZATIONS'],0)

    def test_safe_conflict_rule_change_incomplete_history(self):
        self.observe(0);self.observe(10,[('new',True)],safe=(2,3))
        r=self.l.report('2026-10-26',now=T+10)
        self.assertEqual(r['reason'],'BASELINE_MISSING')

    def test_rule_change_no_false_requalification(self):
        self.history();self.observe(0);self.observe(10,[('prior',True)],rule='changed')
        r=self.l.report('2026-10-26',now=T+10)
        self.assertEqual(r['NEW_QUALIFIED_NEW_ORGANIZATIONS'],'UNKNOWN');self.assertEqual(r['SAFE_NET_CHANGE'],'UNKNOWN')

    def test_signed_evidence_tamper_default_deny_no_raw_addresses(self):
        e=request('x');e['payload']['amount']=amounts(0)
        with self.assertRaises(GrowthError):self.l.reserve(e,now=T+10)
        with self.assertRaises(GrowthError):GrowthLedger(self.path).reserve(request('x'),now=T+10)
        with self.assertRaises(GrowthError):self.l.observe(signed('growth_observation',T,measured_at=T,rule=oid('rule'),snapshot=oid('s'),event_id=oid('e'),complete=True,historical_import=False,organizations=[dict(id='customer@example.invalid',qualified=True)],safe_readings=[1,1]),now=T)

    def test_unknown_budget_restart_no_duplicate_or_reset(self):
        self.caps(n=6)
        self.l.reserve(request('a',amount=amounts(6)),now=T+10)
        self.settle('a',outcome='unknown')
        self.l=GrowthLedger(self.path,consumer=consumer())
        self.assertEqual(self.l.reserve(request('a',amount=amounts(6)),now=T+10),'NO_REPLAY')
        with self.assertRaisesRegex(GrowthError,'CAP_REACHED'):self.l.reserve(request('b'),now=T+10)
        self.settle('a',now=T+30,actual=amounts(2))
        self.assertEqual(self.l.reserve(request('b',now=T+31),now=T+31),'RESERVED_NOT_DISPATCHED')

    def test_missing_caps_crossday_request_and_run_wall(self):
        with self.assertRaisesRegex(GrowthError,'APPROVED_CAP_MISSING'):self.l.reserve(request('a'),now=T+10)
        self.caps(n=100,wall=2);self.l.reserve(request('a',amount=amounts(2)),now=T+10)
        with self.assertRaisesRegex(GrowthError,'RUN_WALL'):self.l.reserve(request('b'),now=T+10)
        self.caps(day='2026-10-27',n=100,wall=2)
        with self.assertRaisesRegex(GrowthError,'RUN_WALL'):self.l.reserve(request('c',now=T+86410),now=T+86410)
        self.assertEqual(self.l.reserve(request('d',now=T+86410,run='other'),now=T+86410),'RESERVED_NOT_DISPATCHED')

    def test_cache_and_persistent_retryafter(self):
        self.caps();a=amounts(0);a['wall_seconds']=1
        self.l.reserve(request('cache',amount=a,cache=True),now=T+10)
        with self.assertRaises(GrowthError):self.l.reserve(request('badcache',cache=True),now=T+10)
        self.l.retry_after(signed('budget_rate_limit',T+10,http_status=429,retry_after_epoch=T+100),now=T+10)
        self.l=GrowthLedger(self.path,consumer=consumer())
        with self.assertRaisesRegex(GrowthError,'RETRY_AFTER_ACTIVE'):self.l.reserve(request('network'),now=T+10)
        self.assertEqual(self.l.reserve(request('network',now=T+100),now=T+100),'RESERVED_NOT_DISPATCHED')

    def test_multiprocess_budget_cap(self):
        self.caps();ctx=mp.get_context('spawn');gate=ctx.Event();out=ctx.Queue()
        jobs=[ctx.Process(target=worker,args=(self.path,str(n),gate,out)) for n in range(2)]
        for p in jobs:p.start()
        gate.set();results=[out.get(timeout=20) for p in jobs]
        for p in jobs:p.join(20);self.assertEqual(p.exitcode,0)
        out.close();out.join_thread()
        self.assertEqual(sorted(results),['CAP_REACHED','RESERVED_NOT_DISPATCHED'])

    def test_overrun_and_settlement_duplicate(self):
        self.caps();self.l.reserve(request('a'),now=T+10)
        self.assertEqual(self.settle('a',actual=amounts(2)),'OVERRUN')
        self.assertEqual(self.settle('a',actual=amounts(2)),'DUPLICATE')
        with self.assertRaisesRegex(GrowthError,'ACTUAL_COST_OVERRUN'):self.l.reserve(request('b'),now=T+10)
        with self.assertRaises(GrowthError):self.settle('a',now=T+21,actual=amounts(0))

    def slot_fixture(self,slot='slot',name='a'):
        from autonomy.durable_slots import DurableSlots
        from autonomy.growth_ledger import digest
        from autonomy.ledger_evidence import LedgerEvidenceVerifier
        verify = LedgerEvidenceVerifier(consumer(), lambda: T+10)
        ledger=DurableSlots(str(Path(self.temp.name)/'slots.sqlite'),verify=verify)
        ledger.initialize()
        ledger.switch_authority(0,'owner',signed('authority',T+10,previous_epoch=0,owner='owner',drained=True,old_disabled=True),now=T+10)
        ledger.admit_due(slot,T+10,signed('schedule',T+10,slot=slot,next_due=T+10,epoch=1,owner='owner',latest_due=True),now=T+10,epoch=1,owner='owner')
        binding=dict(inventory_id=INVENTORY,slot=slot,epoch=1,owner='owner')
        run=digest(binding);binding.update(run_id=run,request_id=oid(name))
        e=signed('budget_request',T+10,request_id=oid(name),run_id=run,day=business_day(T+10),amount=amounts(),cache_hit=False,claim_binding=binding)
        se=signed('idle',T+10,slot=slot,epoch=1,owner='owner',run_id=run,request_id=oid(name),external_state='idle',existing_lock_held=True)
        return ledger,e,se

    def test_real_slot_bound_reserve_before_claim(self):
        from autonomy.lock_recovery import exclusive_lock
        from autonomy.growth_ledger import digest
        self.caps(n=1);ledger,e,se=self.slot_fixture()
        with self.assertRaisesRegex(GrowthError,'EXISTING_LOCK_REQUIRED'):
            self.l.reserve_then_claim(e,ledger,'slot',se,now=T+10,epoch=1,owner='owner')
        with exclusive_lock(Path(self.temp.name)/'lock'):
            for field,value in [('slot','different'),('owner','other'),('epoch',2),('run_id',oid('unrelated'))]:
                payload=dict(e['payload']);payload['claim_binding']=dict(payload['claim_binding'],**{field:value})
                bad=dict(payload=payload,mac=hmac.new(KEY,canonical(payload),hashlib.sha256).hexdigest())
                with self.assertRaisesRegex(GrowthError,'CLAIM_BINDING_MISMATCH'):
                    self.l.reserve_then_claim(bad,ledger,'slot',se,now=T+10,epoch=1,owner='owner')
            from autonomy.durable_slots import LedgerError
            for field,value in [('run_id',oid('wrong')),('request_id',oid('wrong-request'))]:
                payload=dict(se['payload'],**{field:value})
                bad=dict(payload=payload,mac=hmac.new(KEY,canonical(payload),hashlib.sha256).hexdigest())
                with self.assertRaises(LedgerError):self.l.reserve_then_claim(e,ledger,'slot',bad,now=T+10,epoch=1,owner='owner')
            token=self.l.reserve_then_claim(e,ledger,'slot',se,now=T+10,epoch=1,owner='owner')
            self.assertEqual(ledger.snapshot()[0][2],'claimed')
            with self.l.tx() as c:
                row=c.execute('SELECT claim_hash,binding FROM reservations').fetchone()
                self.assertEqual(row['claim_hash'],digest(token));self.assertIn('slot',row['binding'])
            with self.assertRaises(GrowthError):self.l.reserve_then_claim(e,ledger,'slot',se,now=T+10,epoch=1,owner='owner')

    def test_real_claim_failure_keeps_budget(self):
        from autonomy.lock_recovery import exclusive_lock
        from autonomy.durable_slots import LedgerError
        self.caps(n=1);ledger,e,se=self.slot_fixture()
        # A preexisting claim conflicts with the new preparation; D reserves
        # first and cannot refund automatically after the conflict.
        with exclusive_lock(Path(self.temp.name)/'lock'):
            ledger.claim('slot',se,now=T+10,epoch=1,owner='owner')
            with self.assertRaises(LedgerError):self.l.reserve_then_claim(e,ledger,'slot',se,now=T+10,epoch=1,owner='owner')
            with self.assertRaises(GrowthError):self.l.reserve_then_claim(e,ledger,'slot',se,now=T+10,epoch=1,owner='owner')
            with self.assertRaisesRegex(GrowthError,'CAP_REACHED'):self.l.reserve(request('b'),now=T+10)

    def test_incomplete_interval_cannot_be_repaired_by_next_sample(self):
        self.history();self.observe(0)
        self.observe(10,[('partial',True)],complete=False)
        for n in (10,20):
            if n==20:self.observe(n)
            r=self.l.report('2026-10-26',now=T+n)
            self.assertEqual(r['NEW_UNIQUE_ORGANIZATIONS'],'UNKNOWN')
            self.assertEqual(r['SAFE_NET_CHANGE'],'UNKNOWN')
        with self.l.tx() as c:self.assertEqual([r[0] for r in c.execute('SELECT complete FROM measurements ORDER BY observed')],[1,0,1])

    def test_incomplete_first_does_not_freeze_or_block_history(self):
        self.observe(0,[('untrusted-prefix',True)],complete=False)
        self.assertEqual(self.l.report('2026-10-26',now=T)['reason'],'BASELINE_MISSING')
        self.history();self.observe(10,[('verified',False)])
        first=self.l.report('2026-10-26',now=T+10)
        self.assertEqual(first['baseline_id'],oid('event10'));self.assertTrue(first['partial_day'])
        self.observe(20,[('new',True)])
        self.assertEqual(self.l.report('2026-10-26',now=T+20)['NEW_UNIQUE_ORGANIZATIONS'],1)

    def test_freshness_and_baseline_lower_bound(self):
        self.history();self.observe(5)
        r=self.l.report('2026-10-26',now=T+21605)
        self.assertEqual(r['SAFE_LATEST'],'UNKNOWN');self.assertEqual(r['SAFE_NET_CHANGE'],'UNKNOWN')
        self.assertEqual(r['SAFE_HISTORICAL_VALUE'],2)
        r=self.l.report('2026-10-26',now=T+4)
        self.assertEqual(r['SAFE_LATEST'],'UNKNOWN');self.assertEqual(r['SAFE_NET_CHANGE'],'UNKNOWN')
        with self.assertRaises(GrowthError):self.l.report('2026-10-26',now=T+5,max_age_seconds=21600)

    def test_rule_aba_stays_incomparable(self):
        self.history();self.observe(0);self.observe(10,rule='B');self.observe(20,safe=(3,3))
        r=self.l.report('2026-10-26',now=T+20)
        self.assertEqual(r['SAFE_NET_CHANGE'],'UNKNOWN');self.assertEqual(r['NEW_UNIQUE_ORGANIZATIONS'],'UNKNOWN')

    def test_merge_events_persist_across_days(self):
        self.history();self.observe(0);self.observe(10,[('alias',True),('alias2',False)])
        self.l.merge(signed('growth_merge',T+11,event_id=oid('m1'),source=oid('alias'),target=oid('prior')),now=T+11)
        self.l.merge(signed('growth_merge',T+86411,event_id=oid('m2'),source=oid('alias2'),target=oid('old')),now=T+86411)
        r=self.l.report('2026-10-26',now=T+20)
        self.assertEqual(r['reason'],'IDENTITY_MERGE_REQUIRES_REBASELINE')
        with self.l.tx() as c:self.assertEqual(c.execute('SELECT count(*) FROM merge_events').fetchone()[0],2)

    def test_current_qualification_digest_excludes_exited(self):
        from autonomy.growth_ledger import digest
        self.history();self.observe(0,[('prior',False)])
        with self.l.tx() as c:
            self.assertEqual(c.execute('SELECT qualified_hash FROM baselines').fetchone()[0],digest([]))
            row=c.execute('SELECT qualified_at,current_qualified FROM organizations WHERE id=?',(oid('prior'),)).fetchone()
            self.assertIsNotNone(row[0]);self.assertEqual(row[1],0)
        self.observe(10,[('prior',True)])
        self.assertEqual(self.l.report('2026-10-26',now=T+10)['EXISTING_ORGANIZATIONS_NEWLY_QUALIFIED'],0)

    def test_schema_rejects_legacy_tampered_and_overflow_time(self):
        self.l.initialize()
        legacy=str(Path(self.temp.name)/'legacy.sqlite')
        c=sqlite3.connect(legacy);c.execute('CREATE TABLE organizations(id TEXT)');c.commit();c.close()
        with self.assertRaisesRegex(GrowthError,'INCOMPATIBLE_SCHEMA'):GrowthLedger(legacy).initialize()
        c=sqlite3.connect(self.path);c.execute('ALTER TABLE measurements ADD COLUMN unexpected TEXT');c.commit();c.close()
        with self.assertRaisesRegex(GrowthError,'INCOMPATIBLE_SCHEMA'):self.l.report('2026-10-26',now=T)
        with self.assertRaisesRegex(GrowthError,'INVALID_TIMESTAMP'):business_day(2**53)

    def test_real_slot_not_claimed_when_budget_denied(self):
        from autonomy.lock_recovery import exclusive_lock
        ledger,e,se=self.slot_fixture()
        with exclusive_lock(Path(self.temp.name)/'lock'):
            with self.assertRaisesRegex(GrowthError,'APPROVED_CAP_MISSING'):
                self.l.reserve_then_claim(e,ledger,'slot',se,now=T+10,epoch=1,owner='owner')
        self.assertEqual(ledger.snapshot()[0][2],'pending')

    def test_rejected_safe_first_measurement_defers_baseline(self):
        self.history();self.observe(0,safe=(2,3));self.observe(10)
        r=self.l.report('2026-10-26',now=T+10)
        self.assertEqual(r['baseline_id'],oid('event10'))
        self.assertTrue(r['partial_day'])

    def test_commit_ack_lost_no_repeated_charge(self):
        self.caps()
        def fail(phase):
            if phase=='after_commit':raise OSError('synthetic-ack-loss')
        self.l.fault=fail
        with self.assertRaises(GrowthError):self.l.reserve(request('a'),now=T+10)
        self.l.fault=lambda phase:None
        self.assertEqual(self.l.reserve(request('a'),now=T+10),'NO_REPLAY')

if __name__=='__main__':unittest.main()
