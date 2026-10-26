import hashlib
import hmac
import multiprocessing as mp
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
    p=dict(schema='rokt.host-evidence.v1',source_id='fixture',principal_id='fixture-user',inventory_id=INVENTORY,kind=kind,observed_at_epoch=now,receipt_id='fixture-receipt',**data)
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
        return self.l.settle(signed('budget_receipt',now,request_id=oid(name),outcome=outcome,actual=amounts() if actual is None else actual,externally_reconciled=True),now=now)

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
        self.assertEqual(r['SAFE_LATEST'],'UNKNOWN');self.assertEqual(r['SAFE_NET_CHANGE'],'UNKNOWN');self.assertEqual(r['NEW_UNIQUE_ORGANIZATIONS'],'UNKNOWN')

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

    def test_reserve_before_claim_failure_keeps_budget(self):
        class ClaimFailure:
            calls=0
            def claim(self,*a,**kw):self.calls+=1;raise RuntimeError('synthetic-claim-failure')
        fake=ClaimFailure();self.caps(n=1)
        with self.assertRaises(RuntimeError):self.l.reserve_then_claim(request('a'),fake,'slot',{},now=T+10,epoch=1,owner='o')
        with self.assertRaises(GrowthError):self.l.reserve_then_claim(request('a'),fake,'slot',{},now=T+10,epoch=1,owner='o')
        self.assertEqual(fake.calls,1)
        with self.assertRaises(GrowthError):self.l.reserve_then_claim(request('b'),fake,'slot',{},now=T+10,epoch=1,owner='o')
        self.assertEqual(fake.calls,1)

    def test_commit_ack_lost_no_repeated_charge(self):
        self.caps()
        def fail(phase):
            if phase=='after_commit':raise OSError('synthetic-ack-loss')
        self.l.fault=fail
        with self.assertRaises(GrowthError):self.l.reserve(request('a'),now=T+10)
        self.l.fault=lambda phase:None
        self.assertEqual(self.l.reserve(request('a'),now=T+10),'NO_REPLAY')

if __name__=='__main__':unittest.main()
