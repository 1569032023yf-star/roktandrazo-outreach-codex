"""真实子进程费用/意图退出恢复 / Real child-process cost/intent exit recovery."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from contextlib import closing
from autonomy.lock_recovery import exclusive_lock
from autonomy.single_slot_adapter import CancellationJournal
import test_cancellation_cost as fixtures


WORKER = r'''
import json,os,sys,time,sqlite3
from pathlib import Path
from contextlib import closing
from autonomy.growth_ledger import GrowthLedger
from autonomy.single_slot_adapter import CancellationJournal
from test_growth_ledger import consumer,T
path,phase,gate=sys.argv[1:]
data=json.loads(Path(path).read_text(encoding='utf-8'))
limit=time.monotonic()+10
while not Path(gate).exists():
    if time.monotonic()>limit:sys.exit(72)
    time.sleep(0.01)
def cost_fault(stage):
    if phase=='cost_'+stage:os._exit(73)
ledger=GrowthLedger(data['budget'],consumer=consumer(),fault=cost_fault)
reserved=ledger.reserve_cancellation_cost(data['cost'],now=T+10,
    binding=data['binding'],claim_token_hash=data['claim'])
def journal_fault(stage):
    with closing(sqlite3.connect(data['budget'])) as db:
        row=db.execute('SELECT state,claim_hash FROM reservations WHERE id=?',(data['cost_id'],)).fetchone()
    assert row==('reserved',data['claim'])
    if phase=='journal_'+stage:os._exit(73)
result=CancellationJournal(data['journal'],fault=journal_fault).reserve(
    data['identity'],data['binding'],protected=(data['budget'],))
assert result['allow_cancel_dispatch'] is False
assert result['production_execution'] is False
print(json.dumps(dict(cost=reserved,**result)),flush=True)
'''


class CancellationCostProcessTests(unittest.TestCase):
    def setUp(self):
        self.helper=fixtures.CancellationCostTests();self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.case=self.helper.case
        self.children=[]
        self.addCleanup(self.close_children)

    def close_children(self):
        for child in self.children:
            if child.poll() is None:child.kill()
            child.communicate(timeout=10)

    def prepare(self):
        admission,journal,fields,cost,cost_id=self.helper.prepare()
        binding=cost['payload']['claim_binding']
        data=dict(budget=self.case.budget.path,journal=str(journal.path),cost=cost,
            binding=binding,cost_id=cost_id,claim=fields['claim_token_hash'],identity=binding['cancel_identity'])
        path=self.case.root/'worker.json'
        path.write_text(json.dumps(data),encoding='utf-8')
        return admission,journal,fields,cost,cost_id,path

    def launch(self,path,phase,gate):
        child=subprocess.Popen([sys.executable,'-B','-c',WORKER,str(path),phase,str(gate)],
            cwd=Path(__file__).resolve().parent,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,
            creationflags=0x08000000 if os.name=='nt' else 0)
        self.children.append(child)
        return child

    def finish(self,child,code=0):
        try:out,err=child.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            child.kill();child.communicate(timeout=10)
            self.fail('bounded worker timed out')
        self.assertEqual(child.returncode,code,err.decode(errors='replace'))
        self.assertEqual(err,b'')
        if code:
            self.assertEqual(out,b'');return None
        return json.loads(out)

    def snapshot(self):
        with closing(sqlite3.connect(self.case.budget.path)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(),('ok',))
            return db.execute('SELECT id,state,amount,charged,claim_hash FROM reservations ORDER BY id').fetchall()

    def exit_case(self,phase):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id,path=self.prepare()
            gate=c.root/'gate';gate.write_text('go')
            self.finish(self.launch(path,phase,gate),73)
            rows=self.snapshot()
            self.assertEqual(len(rows),1 if phase=='cost_before_commit' else 2)
            for row in rows:self.assertEqual(row[2],row[3])
            expected_intents=1 if phase=='journal_after_commit' else 0
            if journal.path.exists():
                with closing(sqlite3.connect(journal.path)) as db:
                    exists=db.execute("SELECT count(*) FROM sqlite_master WHERE name='cancellations'").fetchone()[0]
                    actual=db.execute('SELECT count(*) FROM cancellations').fetchone()[0] if exists else 0
                    self.assertEqual(actual,expected_intents)
            else:self.assertEqual(expected_intents,0)
            resumed=self.finish(self.launch(path,'none',gate))
            self.assertEqual(resumed['cost'],'RESERVED_NOT_DISPATCHED' if phase=='cost_before_commit' else 'NO_REPLAY')
            self.assertEqual(resumed['outcome'],'DUPLICATE_RESERVED' if expected_intents else 'RESERVED_RECONCILE_ONLY')
            before=self.snapshot()
            result=c.adapter.reserve_cancellation(admission,fixtures.signed('offline_cancel_request',fixtures.T+10,**fields),cost_request=cost)
            self.assertEqual(result['outcome'],'DUPLICATE_RESERVED')
            self.assertEqual(self.snapshot(),before)
            self.assertEqual(c.backend.calls,1)
            c.adapter.reconcile(admission,**c.backend.receipts)
            row=next(r for r in self.snapshot() if r[0]==cost_id)
            self.assertEqual(row[1],'reserved')
            self.assertEqual(row[2],row[3])

    def test_cost_exit_before_commit(self):self.exit_case('cost_before_commit')
    def test_cost_exit_after_commit(self):self.exit_case('cost_after_commit')
    def test_journal_exit_before_commit(self):self.exit_case('journal_before_commit')
    def test_journal_exit_after_commit(self):self.exit_case('journal_after_commit')

    def test_four_workers_charge_once_and_keep_one_intent(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id,path=self.prepare()
            gate=c.root/'gate'
            children=[self.launch(path,'none',gate) for _ in range(4)]
            gate.write_text('go')
            results=[self.finish(child) for child in children]
            self.assertEqual(sum(r['cost']=='RESERVED_NOT_DISPATCHED' for r in results),1)
            self.assertEqual(sum(r['cost']=='NO_REPLAY' for r in results),3)
            self.assertEqual(sum(r['outcome']=='RESERVED_RECONCILE_ONLY' for r in results),1)
            self.assertEqual(sum(r['outcome']=='DUPLICATE_RESERVED' for r in results),3)
            self.assertEqual(len(self.snapshot()),2)
            with closing(sqlite3.connect(journal.path)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM cancellations').fetchone()[0],1)
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone(),('ok',))
            self.assertEqual(c.backend.calls,1)
            c.adapter.reconcile(admission,**c.backend.receipts)


if __name__=='__main__':unittest.main()
