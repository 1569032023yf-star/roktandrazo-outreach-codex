"""离线drain预检真实持久fixture / Drain preflight over real persisted fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import sqlite3
from contextlib import closing
import unittest
from autonomy.owner_drain_preflight import inspect_owner_drain
from autonomy.growth_ledger import digest
from test_growth_ledger import consumer,signed,T
import test_cancellation_owner_death as fixtures

# Avoid importing a TestCase into module globals: discovery must not duplicate it.



class OwnerDrainPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-drain-preflight-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.helper=fixtures.CancellationOwnerDeathTests()
        self.data=self.helper.prepare(self.root,'unknown')
        self.lock=(self.root/'runtime'/'supervisor.lock').read_bytes()
        self.snapshot=(self.root/'budget.sqlite').read_bytes()
        admission=self.data['admission']['payload']
        self.expected={k:admission[k] for k in ('slots_id','budget_id','backend_id','slot','epoch','owner','run_id','request_id')}
        self.expected.update(old_lock_sha256=hashlib.sha256(self.lock).hexdigest(),
            budget_snapshot_sha256=hashlib.sha256(self.snapshot).hexdigest(),
            claim_token_hash=self.data['receipts']['budget_receipt']['payload']['claim_token_hash'])
        state=json.loads(self.lock)
        self.fields=dict(self.expected,old_lock_token_hash=digest(state['token']),
            old_process_identity_hash=digest(state['process_identity']),external_drained=True,
            scope='isolated_offline',production_execution=False)

    def check(self,fields=None,expected=None,lock=None,snapshot=None,now=T+10):
        return inspect_owner_drain(consumer(),signed('offline_owner_drain',T+10,**(self.fields if fields is None else fields)),
            now=now,expected=self.expected if expected is None else expected,
            lock_bytes=self.lock if lock is None else lock,budget_snapshot=self.snapshot if snapshot is None else snapshot)

    def test_matching_drain_never_authorizes_recovery_or_mutates_files(self):
        before=self.helper.inspect(self.root,self.data)
        r=self.check();self.assertTrue(r['evidence_matches'])
        for key in ('allow_lock_recovery','allow_reconcile','allow_dispatch','allow_cancel_dispatch','production_accepted'):
            self.assertIs(r[key],False)
        self.assertEqual(r['owner_liveness'],'UNKNOWN')
        self.assertEqual(self.helper.inspect(self.root,self.data),before)
        self.assertEqual((self.root/'runtime'/'supervisor.lock').read_bytes(),self.lock)

    def test_signature_binding_and_expiry_fail_closed(self):
        for key in ('old_lock_token_hash','old_process_identity_hash','claim_token_hash','slots_id','budget_id','backend_id'):
            fields=dict(self.fields);fields[key]='wrong'
            self.assertFalse(self.check(fields)['evidence_matches'])
        for value in (False,1,'UNKNOWN',None):
            self.assertFalse(self.check(dict(self.fields,external_drained=value))['evidence_matches'])
        self.assertFalse(self.check(now=T+400)['evidence_matches'])

    def test_changed_lock_snapshot_and_duplicate_json_rejected(self):
        self.assertFalse(self.check(lock=self.lock+b' ')['evidence_matches'])
        self.assertFalse(self.check(snapshot=self.snapshot[:-1])['evidence_matches'])
        duplicate=self.lock[:-1]+b',"pid":1}'
        expected=dict(self.expected,old_lock_sha256=hashlib.sha256(duplicate).hexdigest())
        fields=dict(self.fields,old_lock_sha256=expected['old_lock_sha256'])
        self.assertEqual(self.check(fields,expected,lock=duplicate)['reason'],'LOCK_SCHEMA_REJECTED')

    def test_signed_but_wrong_persisted_claim_rejected(self):
        expected=dict(self.expected,claim_token_hash='a'*64)
        fields=dict(self.fields,claim_token_hash='a'*64)
        self.assertEqual(self.check(fields,expected)['reason'],'PERSISTED_CLAIM_MISMATCH')
        expected=dict(self.expected,request_id='b'*64)
        fields=dict(self.fields,request_id='b'*64)
        self.assertEqual(self.check(fields,expected)['reason'],'PERSISTED_CLAIM_UNRESOLVED_REQUIRED')

    def test_persisted_boolean_epoch_not_equal_to_integer_claim(self):
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(self.snapshot)
            binding=json.loads(db.execute('SELECT binding FROM reservations WHERE id=?',(self.expected['request_id'],)).fetchone()[0])
            binding['epoch']=True
            db.execute('UPDATE reservations SET binding=? WHERE id=?',(json.dumps(binding),self.expected['request_id']))
            db.commit();snapshot=db.serialize()
        expected=dict(self.expected,budget_snapshot_sha256=hashlib.sha256(snapshot).hexdigest())
        fields=dict(self.fields,budget_snapshot_sha256=expected['budget_snapshot_sha256'])
        self.assertEqual(self.check(fields,expected,snapshot=snapshot)['reason'],'PERSISTED_CLAIM_MISMATCH')

    def test_invalid_context_and_legacy_lock_rejected(self):
        self.assertFalse(self.check(expected={})['evidence_matches'])
        self.assertFalse(self.check(expected=dict(self.expected,epoch=True))['evidence_matches'])
        lock=json.loads(self.lock);lock['schema_version']=1
        raw=json.dumps(lock).encode()
        expected=dict(self.expected,old_lock_sha256=hashlib.sha256(raw).hexdigest())
        fields=dict(self.fields,old_lock_sha256=expected['old_lock_sha256'])
        self.assertFalse(self.check(fields,expected,lock=raw)['evidence_matches'])

if __name__=='__main__':unittest.main()
