"""Real subprocess to durable admission integration / 真实子进程与持久准入集成。"""
import hashlib,json,sqlite3,sys,time,unittest
from contextlib import closing
from pathlib import Path
from autonomy.process_backend import ProcessBackend,ExecutionUnknown,consume_existing_inventory_event
from autonomy.lock_recovery import exclusive_lock
from autonomy.growth_ledger import digest
from autonomy.single_slot_adapter import BACKEND_PROTOCOL,OPERATION_SCHEMA
from autonomy.unattended_policy import INVENTORY
import test_single_slot_adapter as fixtures

class BackendTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.SingleSlotTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.worker=self.f.root/'worker.py';self.marker=self.f.root/'calls'
  self.worker.write_text('import sys,json\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(Path.cwd()))+')\nfrom test_growth_ledger import signed,T,amounts\nfrom autonomy.growth_ledger import digest\no=json.load(sys.stdin)\nPath('+repr(str(self.marker))+').open("a").write("called\\n")\nc={k:o[k] for k in ("slot","epoch","owner","run_id","request_id")}\nprint(json.dumps(dict(slot_receipt=signed("receipt",T+10,**c,token=o["token"],state="completed",receipt="isolated-child",external_drained=True),budget_receipt=signed("budget_receipt",T+10,**c,claim_token_hash=digest(o["token"]),outcome="known",actual=amounts(),externally_reconciled=True))))',encoding='utf-8')
 def backend(self):
  return ProcessBackend(self.f.root/'backend.sqlite',python=sys.executable,python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),worker=str(self.worker),worker_sha256=hashlib.sha256(self.worker.read_bytes()).hexdigest(),backend_id='synthetic-backend',offline_only=True)
 def operation(self):
  o=dict(schema=OPERATION_SCHEMA,scope='isolated_offline',production_execution=False,inventory_id=INVENTORY,backend_protocol=BACKEND_PROTOCOL,backend_id='synthetic-backend',max_wall_seconds=1)
  o['idempotency_key']=digest(o);return o
 def test_actual_child_receipts_settle_existing_ledgers(self):
  from unittest.mock import Mock
  b=self.backend();tracked=Mock(wraps=b.execute_once);b.execute_once=tracked
  self.f.adapter.backend=b;self.f.adapter.monotonic=time.monotonic
  with exclusive_lock(self.f.runtime):
   event=dict(inventory_id=INVENTORY,admission=self.f.admission(),schedule=self.f.plan,idle=self.f.idle,budget_request=self.f.request)
   r=consume_existing_inventory_event(self.f.adapter,event)
   self.assertEqual(r['outcome'],'COMPLETED');self.assertFalse(r['production_execution'])
  self.assertEqual(self.marker.read_text(),'called\n')
  cached=self.backend().execute_once(tracked.call_args.args[0],deadline_monotonic=time.monotonic()+.8)
  self.assertEqual(set(cached),{'slot_receipt','budget_receipt'});self.assertEqual(self.marker.read_text(),'called\n')
  # Reopen transport and replay its exact recorded input: cached output only.
  c=sqlite3.connect(self.f.root/'backend.sqlite');self.assertEqual(c.execute('select state from executions').fetchone()[0],'OUTPUT_RECORDED');c.close()
 def test_inflight_after_reopen_never_enters_child(self):
  b=self.backend();o=self.operation()
  binding=digest(dict(operation=o,python_sha256=b.hashes[0],worker_sha256=b.hashes[1]))
  with closing(sqlite3.connect(b.path)) as c:
   c.execute('insert into executions values (?,?,?,NULL)',(o['idempotency_key'],binding,'IN_FLIGHT'));c.commit()
  with self.assertRaises(ExecutionUnknown):self.backend().execute_once(o,deadline_monotonic=time.monotonic()+.8)
  self.assertFalse(self.marker.exists())
  status=self.backend().status(o['idempotency_key']);self.assertEqual(status['transport_state'],'IN_FLIGHT');self.assertFalse(status['replay_authorized'])
 def test_lost_or_invalid_receipt_blocks_retry(self):
  self.worker.write_text('import sys\nsys.stdin.read()\nprint("{}")')
  b=self.backend();o=self.operation()
  with self.assertRaises(ExecutionUnknown):b.execute_once(o,deadline_monotonic=time.monotonic()+.8)
  with self.assertRaisesRegex(ExecutionUnknown,'UNKNOWN_NO_REPLAY'):self.backend().execute_once(o,deadline_monotonic=time.monotonic()+.8)
  self.assertEqual(self.backend().status(o['idempotency_key'])['outcome'],'UNKNOWN')
 def test_timeout_kills_child_and_no_replay(self):
  self.worker.write_text('import time,sys\nsys.stdin.read()\ntime.sleep(60)')
  b=self.backend();o=self.operation()
  import subprocess
  with self.assertRaises(subprocess.TimeoutExpired) as caught:b.execute_once(o,deadline_monotonic=time.monotonic()+.15)
  self.assertTrue(caught.exception.cleanup_verified)
  with self.assertRaisesRegex(ExecutionUnknown,'UNKNOWN_NO_REPLAY'):self.backend().execute_once(o,deadline_monotonic=time.monotonic()+.8)
  self.assertEqual(self.backend().status(o['idempotency_key'])['outcome'],'UNKNOWN')
 def test_foreign_inventory_and_no_lease_rejected(self):
  with self.assertRaises(ValueError):consume_existing_inventory_event(self.f.adapter,dict(inventory_id='other'))
  event=dict(inventory_id=INVENTORY,admission={},schedule={},idle={},budget_request={})
  with self.assertRaisesRegex(RuntimeError,'EXPECTED_LOCK_REQUIRED'):consume_existing_inventory_event(self.f.adapter,event)

if __name__=='__main__':unittest.main()
