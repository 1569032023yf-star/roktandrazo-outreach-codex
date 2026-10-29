"""真实持久跨快照关联 / Real persisted cross-snapshot joins."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from autonomy.drain_bundle_preflight import inspect_drain_bundle
from test_growth_ledger import consumer,signed,T
import test_owner_drain_preflight as fixtures

class DrainBundlePreflightTests(unittest.TestCase):
    def setUp(self):
        self.base=fixtures.OwnerDrainPreflightTests();self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        b=self.base
        self.slots=(b.root/'slots.sqlite').read_bytes()
        self.journal=Path(b.data['journal']).read_bytes()
        cost=b.data['cost']['payload']['claim_binding']
        self.expected=dict(b.expected,
            slots_snapshot_sha256=hashlib.sha256(self.slots).hexdigest(),
            journal_snapshot_sha256=hashlib.sha256(self.journal).hexdigest(),
            **{k:cost[k] for k in ('runtime_id','journal_id','cancel_identity','cancel_cost_request_id')})
        self.fields=dict(b.fields,**{k:self.expected[k] for k in self.expected if k not in b.expected})

    def check(self,**changes):
        fields=changes.pop('fields',self.fields)
        args=dict(now=T+10,expected=self.expected,lock_bytes=self.base.lock,
            budget_snapshot=self.base.snapshot,slots_snapshot=self.slots,journal_snapshot=self.journal)
        args.update(changes)
        return inspect_drain_bundle(consumer(),signed('offline_owner_drain',T+10,**fields),**args)

    def mutate(self,raw,sql,args=()):
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(raw);db.execute(sql,args);db.commit();return db.serialize()

    def changed(self,kind,raw):
        key={'slots':'slots_snapshot_sha256','journal':'journal_snapshot_sha256','budget':'budget_snapshot_sha256'}[kind]
        expected=dict(self.expected,**{key:hashlib.sha256(raw).hexdigest()})
        fields=dict(self.fields,**{key:expected[key]})
        return self.check(expected=expected,fields=fields,**{kind+'_snapshot':raw})

    def test_full_join_never_grants_recovery_and_preserves_files(self):
        before=self.base.helper.inspect(self.base.root,self.base.data)
        r=self.check();self.assertTrue(r['bundle_matches'])
        for key in ('allow_lock_recovery','allow_reconcile','allow_dispatch','allow_cancel_dispatch','production_accepted'):
            self.assertIs(r[key],False)
        self.assertEqual(r['owner_liveness'],'UNKNOWN')
        self.assertEqual(self.base.helper.inspect(self.base.root,self.base.data),before)
        self.assertEqual((self.base.root/'runtime'/'supervisor.lock').read_bytes(),self.base.lock)

    def test_missing_truncated_or_wal_images_rejected(self):
        for raw in (None,b'',self.slots[:-1]):
            self.assertFalse(self.check(slots_snapshot=raw)['bundle_matches'])
        raw=bytearray(self.slots);raw[18:20]=b'\x02\x02'
        self.assertFalse(self.changed('slots',bytes(raw))['bundle_matches'])
        self.assertFalse(self.check(journal_snapshot=None)['bundle_matches'])

    def test_signed_extra_context_and_identity_mismatch(self):
        self.assertFalse(self.check(fields=dict(self.fields,runtime_id='a'*64))['bundle_matches'])
        expected=dict(self.expected,cancel_identity='b'*64)
        fields=dict(self.fields,cancel_identity='b'*64)
        self.assertEqual(self.check(expected=expected,fields=fields)['reason'],'CANCELLATION_IDENTITY_MISMATCH')

    def test_wrong_slot_claim_or_authority_rejected(self):
        for sql,args in (("UPDATE slots SET token=?",('wrong-claim',)),
                         ("UPDATE authority SET owner=?",('wrong-owner',)),
                         ("UPDATE slots SET state=?",('completed',))):
            raw=self.mutate(self.slots,sql,args)
            self.assertEqual(self.changed('slots',raw)['reason'],'SLOT_CLAIM_OR_AUTHORITY_MISMATCH')

    def test_journal_wrong_original_request_or_boolean_epoch_rejected(self):
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(self.journal)
            original=json.loads(db.execute('SELECT binding FROM cancellations').fetchone()[0])
        for change in ({'original_request_id':'a'*64},{'epoch':True}):
            binding=dict(original,**change)
            raw=self.mutate(self.journal,'UPDATE cancellations SET binding=?',(json.dumps(binding),))
            self.assertEqual(self.changed('journal',raw)['reason'],'JOURNAL_BINDING_MISMATCH')

    def test_missing_settled_and_zero_charged_cost_rejected(self):
        cost_id=self.expected['cancel_cost_request_id']
        for sql,args in (("DELETE FROM reservations WHERE id=?",(cost_id,)),
                         ("UPDATE reservations SET state='settled' WHERE id=?",(cost_id,))):
            raw=self.mutate(self.base.snapshot,sql,args)
            self.assertEqual(self.changed('budget',raw)['reason'],'CANCEL_COST_BINDING_MISMATCH')
        charged={k:0 for k in self.base.data['cost']['payload']['amount']}
        raw=self.mutate(self.base.snapshot,'UPDATE reservations SET charged=? WHERE id=?',(json.dumps(charged),cost_id))
        self.assertEqual(self.changed('budget',raw)['reason'],'CANCEL_COST_NOT_FULLY_RESERVED')

    def test_unapproved_schema_and_signed_wrong_journal_lock_rejected(self):
        raw=self.mutate(self.slots,'CREATE TABLE unexpected (value TEXT)')
        self.assertEqual(self.changed('slots',raw)['reason'],'BUNDLE_IMAGE_OR_EVIDENCE_REJECTED')
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(self.journal)
            binding=json.loads(db.execute('SELECT binding FROM cancellations').fetchone()[0])
        binding['lock_token_hash']='a'*64
        raw=self.mutate(self.journal,'UPDATE cancellations SET binding=?',(json.dumps(binding),))
        self.assertEqual(self.changed('journal',raw)['reason'],'JOURNAL_BINDING_MISMATCH')

if __name__=='__main__':unittest.main()
