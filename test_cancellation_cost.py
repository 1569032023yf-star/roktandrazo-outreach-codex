"""取消费用预留故障合同 / Cancellation-cost reservation fault contracts."""
import json
import sqlite3
import unittest
from contextlib import closing
from autonomy.single_slot_adapter import CANCEL_COST_PROTOCOL, AdapterError, CancellationJournal
from autonomy.growth_ledger import digest, business_day
from autonomy.lock_recovery import exclusive_lock
import test_single_slot_adapter as fixtures
from test_growth_ledger import signed, amounts, T


class CancellationCostTests(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.SingleSlotTests();self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.backend.mode='lost'

    def prepare(self):
        c=self.case
        admission=c.admission()
        self.assertEqual(c.run_one(admission)['outcome'],'UNKNOWN_RECONCILE_ONLY')
        journal,fields=c.cancellation_fixture()
        fields['cancel_cost_protocol']=CANCEL_COST_PROTOCOL
        # Adapter binds journal v1 plus explicitly versioned cost v1.
        from autonomy.unattended_policy import INVENTORY
        identity=digest(dict(inventory_id=INVENTORY,**c.common,claim_token_hash=fields['claim_token_hash']))
        cost_id=digest(dict(cancel_identity=identity,cancel_cost_protocol=CANCEL_COST_PROTOCOL))
        binding=dict(fields)
        binding.pop('cancel_cost_protocol')
        binding.update(inventory_id=INVENTORY,cancel_identity=identity,
            cancel_cost_protocol=CANCEL_COST_PROTOCOL,cancel_cost_request_id=cost_id,
            request_id=cost_id,original_request_id=c.common['request_id'])
        cost=signed('budget_request',T+10,request_id=cost_id,run_id=c.common['run_id'],
            day=business_day(T+10),amount=amounts(),cache_hit=False,
            claim_binding=binding,claim_token_hash=fields['claim_token_hash'])
        return admission,journal,fields,cost,cost_id

    def rows(self):
        with self.case.budget.tx() as db:
            return [dict(r) for r in db.execute('SELECT * FROM reservations ORDER BY id')]

    def test_reserve_before_intent_reopen_duplicate_and_original_settlement(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            def assert_reserved(stage):
                with closing(sqlite3.connect(c.budget.path)) as db:
                    row=db.execute('SELECT state,claim_hash FROM reservations WHERE id=?',(cost_id,)).fetchone()
                self.assertEqual(row,('reserved',fields['claim_token_hash']))
            journal.fault=assert_reserved
            request=signed('offline_cancel_request',T+10,**fields)
            result=c.adapter.reserve_cancellation(admission,request,cost_request=cost)
            self.assertEqual(result['outcome'],'RESERVED_RECONCILE_ONLY')
            self.assertFalse(result['allow_cancel_dispatch'])
            self.assertEqual(len(self.rows()),2)
            before=self.rows()
            c.adapter.cancellation_journal=CancellationJournal(journal.path)
            self.assertEqual(c.adapter.reserve_cancellation(admission,request,cost_request=cost)['outcome'],'DUPLICATE_RESERVED')
            self.assertEqual(self.rows(),before)
            c.adapter.reconcile(admission,**c.backend.receipts)
            row=next(r for r in self.rows() if r['id']==cost_id)
            self.assertEqual(row['state'],'reserved')
            self.assertEqual(row['charged'],row['amount'])
            self.assertEqual(c.backend.calls,1)

    def test_cost_commit_ack_loss_no_intent_then_idempotent_resume(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            request=signed('offline_cancel_request',T+10,**fields)
            # Activate only inside reservation, never preliminary validation.
            original=c.budget.reserve_cancellation_cost
            def lost(*args,**kwargs):
                c.budget.fault=lambda stage: (_ for _ in ()).throw(OSError('fixture')) if stage=='after_commit' else None
                try:return original(*args,**kwargs)
                finally:c.budget.fault=lambda stage:None
            c.budget.reserve_cancellation_cost=lost
            result=c.adapter.reserve_cancellation(admission,request,cost_request=cost)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertFalse(journal.path.exists())
            self.assertEqual(len(self.rows()),2)
            c.budget.reserve_cancellation_cost=original
            self.assertEqual(c.adapter.reserve_cancellation(admission,request,cost_request=cost)['outcome'],'RESERVED_RECONCILE_ONLY')
            self.assertEqual(len(self.rows()),2)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_cost_before_commit_failure_has_no_reservation_or_intent(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            original=c.budget.reserve_cancellation_cost
            def fail(*args,**kwargs):
                c.budget.fault=lambda stage: (_ for _ in ()).throw(OSError('fixture')) if stage=='before_commit' else None
                try:return original(*args,**kwargs)
                finally:c.budget.fault=lambda stage:None
            c.budget.reserve_cancellation_cost=fail
            result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertFalse(journal.path.exists())
            self.assertEqual(len(self.rows()),1)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_cost_counts_against_existing_caps_and_signed_settlement(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            # Original execution already charges one in every dimension.
            # A second request of ten exceeds the existing daily cap of ten.
            payload=dict(cost['payload'])
            for key in ('schema','source_id','principal_id','inventory_id','kind','observed_at_epoch','expires_at_epoch','receipt_id'):payload.pop(key)
            payload['amount']=amounts(10);payload['amount']['wall_seconds']=1
            request=signed('offline_cancel_request',T+10,**fields)
            self.assertEqual(c.adapter.reserve_cancellation(admission,request,cost_request=signed('budget_request',T+10,**payload))['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertFalse(journal.path.exists())
            self.assertEqual(len(self.rows()),1)
            self.assertEqual(c.adapter.reserve_cancellation(admission,request,cost_request=cost)['outcome'],'RESERVED_RECONCILE_ONLY')
            # Settlement must bind cancellation identity, original request,
            # exact cost request and claim, not the original run receipt alone.
            binding=dict(cost['payload']['claim_binding'])
            binding.pop('inventory_id')
            receipt=signed('budget_receipt',T+10,**binding,
                outcome='known',externally_reconciled=True,actual=amounts(0))
            self.assertEqual(c.budget.settle(receipt,now=T+10),'SETTLED')
            with self.assertRaisesRegex(AdapterError,'CANCEL_COST_RECONCILIATION_REQUIRED'):
                c.adapter.reserve_cancellation(admission,request,cost_request=cost)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_journal_failure_preserves_cost_reservation(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            journal.fault=lambda stage: (_ for _ in ()).throw(OSError('fixture')) if stage=='before_commit' else None
            result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            row=next(r for r in self.rows() if r['id']==cost_id)
            self.assertEqual(row['state'],'reserved')
            self.assertEqual(row['charged'],row['amount'])
            with closing(sqlite3.connect(journal.path)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE name='cancellations'").fetchone()[0],0)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_signed_version_identity_amount_conflicts_fail_before_intent(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            request=signed('offline_cancel_request',T+10,**fields)
            with self.assertRaisesRegex(AdapterError,'CANCEL_COST_REQUEST_REQUIRED'):
                c.adapter.reserve_cancellation(admission,request)
            for key,value in [('cancel_cost_protocol','v0'),('claim_token_hash','wrong')]:
                bad=dict(fields);bad[key]=value
                with self.assertRaises(AdapterError):
                    c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**bad),cost_request=cost)
            bad=dict(cost);bad['mac']='0'*64
            with self.assertRaises(AdapterError):c.adapter.reserve_cancellation(admission,request,cost_request=bad)
            self.assertFalse(journal.path.exists())
            self.assertEqual(len(self.rows()),1)
            for key,value in [('request_id','0'*64),('run_id','1'*64),('amount',dict(amounts(),wall_seconds=0))]:
                payload=dict(cost['payload'])
                for meta in ('schema','source_id','principal_id','inventory_id','kind','observed_at_epoch','expires_at_epoch','receipt_id'):payload.pop(meta)
                payload[key]=value
                with self.assertRaises(AdapterError):
                    c.adapter.reserve_cancellation(admission,request,cost_request=signed('budget_request',T+10,**payload))
            self.assertEqual(len(self.rows()),1)
            c.adapter.reserve_cancellation(admission,request,cost_request=cost)
            payload=dict(cost['payload'])
            for key in ('schema','source_id','principal_id','inventory_id','kind','observed_at_epoch','expires_at_epoch','receipt_id'):payload.pop(key)
            payload['amount']=amounts(2)
            result=c.adapter.reserve_cancellation(admission,request,cost_request=signed('budget_request',T+10,**payload))
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(len(self.rows()),2)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_journal_commit_ack_loss_resumes_without_recharging(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            journal.fault=lambda stage: (_ for _ in ()).throw(OSError('fixture')) if stage=='after_commit' else None
            request=signed('offline_cancel_request',T+10,**fields)
            result=c.adapter.reserve_cancellation(admission,request,cost_request=cost)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            before=self.rows()
            with closing(sqlite3.connect(journal.path)) as db:
                saved=db.execute('SELECT * FROM cancellations').fetchall()
            self.assertEqual(len(saved),1)
            c.adapter.cancellation_journal=CancellationJournal(journal.path)
            self.assertEqual(c.adapter.reserve_cancellation(admission,request,cost_request=cost)['outcome'],'DUPLICATE_RESERVED')
            self.assertEqual(self.rows(),before)
            with closing(sqlite3.connect(journal.path)) as db:
                self.assertEqual(db.execute('SELECT * FROM cancellations').fetchall(),saved)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_legacy_intent_upgrade_conflicts_without_rewrite_or_refund(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            legacy=dict(fields);legacy.pop('cancel_cost_protocol')
            result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**legacy))
            self.assertEqual(result['outcome'],'RESERVED_RECONCILE_ONLY')
            with closing(sqlite3.connect(journal.path)) as db:
                before=db.execute('SELECT * FROM cancellations').fetchall()
            request=signed('offline_cancel_request',T+10,**fields)
            for attempt in range(2):
                with self.assertRaisesRegex(AdapterError,'CANCEL_REQUEST_CONFLICT'):
                    c.adapter.reserve_cancellation(admission,request,cost_request=cost)
                self.assertEqual(len(self.rows()),2)
                row=next(r for r in self.rows() if r['id']==cost_id)
                self.assertEqual(row['state'],'reserved')
                self.assertEqual(row['charged'],row['amount'])
                with closing(sqlite3.connect(journal.path)) as db:
                    self.assertEqual(db.execute('SELECT * FROM cancellations').fetchall(),before)
            self.assertEqual(c.backend.calls,1)
            c.adapter.reconcile(admission,**c.backend.receipts)


if __name__=='__main__':unittest.main()
