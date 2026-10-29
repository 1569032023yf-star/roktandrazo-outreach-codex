"""完整离线适配器所有者退出 / Whole offline adapter-owner process death.

No service/logoff/reboot claims. The owner process holds its own real lock;
there is no surviving parent lease. Synthetic backend never performs IO.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from autonomy.lock_recovery import exclusive_lock, recover_lock
from autonomy.single_slot_adapter import SingleSlotAdapter, OfflineTarget, CancellationJournal, AdapterError
from autonomy.durable_slots import DurableSlots
from autonomy.growth_ledger import GrowthLedger
from autonomy.ledger_evidence import LedgerEvidenceVerifier
from test_growth_ledger import consumer, signed, T
from test_single_slot_adapter import FakeBackend

WORKER = r'''
import json,os,sys
from pathlib import Path
from unittest.mock import patch
from autonomy.lock_recovery import exclusive_lock
from test_growth_ledger import signed,T
import test_cancellation_cost as fixtures
class BorrowedDirectory:
    name=sys.argv[1]
    def cleanup(self):pass
with patch('test_single_slot_adapter.tempfile.TemporaryDirectory',return_value=BorrowedDirectory()):
    helper=fixtures.CancellationCostTests();helper.setUp()
c=helper.case
with exclusive_lock(c.runtime):
    admission,journal,fields,cost,cost_id=helper.prepare()
    result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
    assert result['outcome']=='RESERVED_RECONCILE_ONLY'
    if sys.argv[2]=='drained':
        assert c.adapter.reconcile(admission,**c.backend.receipts)['outcome']=='COMPLETED'
    data=dict(admission=admission,fields=fields,cost=cost,cost_id=cost_id,
              journal=str(journal.path),backend_calls=c.backend.calls)
    (c.root/'state.json').write_text(json.dumps(data),encoding='utf-8')
    os._exit(74)
'''

class CancellationOwnerDeathTests(unittest.TestCase):
    def prepare(self,root,phase):
        result=subprocess.run([sys.executable,'-B','-c',WORKER,str(root),phase],
            cwd=Path(__file__).resolve().parent,stdin=subprocess.DEVNULL,
            capture_output=True,timeout=25,shell=False,
            creationflags=0x08000000 if os.name=='nt' else 0)
        self.assertEqual(result.returncode,74,result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout,b'');self.assertEqual(result.stderr,b'')
        return json.loads((root/'state.json').read_text(encoding='utf-8'))

    def inspect(self,root,data):
        paths=[root/'slots.sqlite',root/'budget.sqlite',Path(data['journal'])]
        hashes=[]
        for path in paths:
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(),('ok',))
                if path.name=='budget.sqlite':
                    rows=db.execute('SELECT id,state,amount,charged FROM reservations').fetchall()
                    cost=next(row for row in rows if row[0]==data['cost_id'])
                    self.assertEqual(len(rows),2)
                    self.assertEqual(cost[1],'reserved');self.assertEqual(cost[2],cost[3])
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        return hashes

    def test_unresolved_dead_owner_cannot_be_recovered_or_replayed(self):
        with tempfile.TemporaryDirectory(prefix='u1-owner-death-') as directory:
            root=Path(directory);data=self.prepare(root,'unknown')
            lock=root/'runtime'/'supervisor.lock'
            state=json.loads(lock.read_text());self.assertEqual(state['tree_state'],'unverified')
            before=self.inspect(root,data);lock_before=lock.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'ASSOCIATED_TREE_UNVERIFIED'):
                recover_lock(root/'runtime',state['token'])
            with self.assertRaises(FileExistsError):
                with exclusive_lock(root/'runtime'):self.fail('must not acquire dead unresolved lease')
            self.assertEqual(lock.read_bytes(),lock_before)
            self.assertEqual(self.inspect(root,data),before)
            self.assertEqual(data['backend_calls'],1)

    def test_drained_owner_recovery_rejects_old_admission_and_keeps_cost(self):
        with tempfile.TemporaryDirectory(prefix='u1-owner-death-') as directory:
            root=Path(directory);data=self.prepare(root,'drained')
            runtime=root/'runtime';state=json.loads((runtime/'supervisor.lock').read_text())
            self.assertEqual(state['tree_state'],'verified_closed')
            before=self.inspect(root,data)
            self.assertTrue(recover_lock(runtime,state['token'])['recovered'])
            trust=consumer()
            slots=DurableSlots(root/'slots.sqlite',verify=LedgerEvidenceVerifier(trust,lambda:T+10))
            budget=GrowthLedger(root/'budget.sqlite',consumer=trust)
            backend=FakeBackend()
            adapter=SingleSlotAdapter(slots,budget,
                target=OfflineTarget(str(runtime),slots.path,budget.path,'synthetic-backend'),
                consumer=trust,backend=backend,wall_clock=lambda:T+10,monotonic=lambda:1)
            adapter.cancellation_journal=CancellationJournal(data['journal'])
            with exclusive_lock(runtime) as new:
                self.assertNotEqual(new['token'],state['token'])
                with self.assertRaisesRegex(AdapterError,'BINDING_MISMATCH'):
                    adapter.reserve_cancellation(data['admission'],
                        signed('offline_cancel_request',T+10,**data['fields']),cost_request=data['cost'])
                self.assertEqual(backend.calls,0)
                self.assertEqual(self.inspect(root,data),before)
            self.assertFalse((runtime/'supervisor.lock').exists())

if __name__=='__main__':unittest.main()
