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
 def backend(self,**kwargs):
  return ProcessBackend(self.f.root/'backend.sqlite',python=sys.executable,python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),worker=str(self.worker),worker_sha256=hashlib.sha256(self.worker.read_bytes()).hexdigest(),backend_id='synthetic-backend',offline_only=True,**kwargs)
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
  with self.assertRaises(subprocess.TimeoutExpired) as caught:b.execute_once(o,deadline_monotonic=time.monotonic()+.8)
  self.assertTrue(caught.exception.cleanup_verified)
  with self.assertRaisesRegex(ExecutionUnknown,'UNKNOWN_NO_REPLAY'):self.backend().execute_once(o,deadline_monotonic=time.monotonic()+.8)
  self.assertEqual(self.backend().status(o['idempotency_key'])['outcome'],'UNKNOWN')
 def test_ambiguous_worker_receipts_are_unknown_and_never_replayed(self):
  for raw in ('{"slot_receipt":{},"slot_receipt":{},"budget_receipt":{}}',
              '{"slot_receipt":{"state":1,"state":2},"budget_receipt":{}}',
              '{"slot_receipt":{},"budget_receipt":{"actual":NaN}}',
              '{"slot_receipt":{},"budget_receipt":{"actual":1e999}}',
              '{"slot_receipt":{},"budget_receipt":{"actual":-1e999}}'):
   with self.subTest(raw=raw):
    self.worker.write_text('import sys\nsys.stdin.read()\nprint('+repr(raw)+')',encoding='utf-8')
    b=self.backend();o=self.operation();o['case']=raw
    o.pop('idempotency_key');o['idempotency_key']=digest(o)
    with self.assertRaises(ExecutionUnknown):b.execute_once(o,deadline_monotonic=time.monotonic()+.8)
    self.assertEqual(b.status(o['idempotency_key'])['transport_state'],'UNKNOWN')
    with self.assertRaisesRegex(ExecutionUnknown,'UNKNOWN_NO_REPLAY'):
     self.backend().execute_once(o,deadline_monotonic=time.monotonic()+.8)
 def test_foreign_inventory_and_no_lease_rejected(self):
  with self.assertRaises(ValueError):consume_existing_inventory_event(self.f.adapter,dict(inventory_id='other'))
  event=dict(inventory_id=INVENTORY,admission={},schedule={},idle={},budget_request={})
  with self.assertRaisesRegex(RuntimeError,'EXPECTED_LOCK_REQUIRED'):consume_existing_inventory_event(self.f.adapter,event)

 def test_provider_reference_is_pinned_and_passed_without_secret_environment(self):
  import os
  from types import SimpleNamespace
  from unittest.mock import patch
  config=self.f.root/'provider.json'
  config.write_text(json.dumps(dict(schema='rokt.provider-environment.v1',environment=dict(WORKBUDDY_DISCOVERY_PROVIDER='google_places'))))
  expected=hashlib.sha256(config.read_bytes()).hexdigest();before=dict(os.environ)
  b=self.backend(provider_config=str(config),provider_config_sha256=expected);o=self.operation()
  def child(arguments,**kwargs):
   self.assertEqual(arguments[-4:],['--provider-config',str(config),'--provider-config-sha256',expected])
   self.assertEqual(dict(os.environ),before)
   with self.assertRaises(PermissionError):config.write_text('changed')
   return SimpleNamespace(returncode=0,cleanup_verified=True,stdout=b'{"slot_receipt":{},"budget_receipt":{}}')
  with patch('autonomy.process_backend.run_tree',side_effect=child):
   b.execute_once(o,deadline_monotonic=time.monotonic()+.8)
  config.write_text('released')
  with self.assertRaises(ValueError):b.execute_once(o,deadline_monotonic=time.monotonic()+.8)
  self.assertEqual(b.status(o['idempotency_key'])['transport_state'],'OUTPUT_RECORDED')
 def test_bad_provider_digest_precedes_execution_intent(self):
  from unittest.mock import patch
  config=self.f.root/'provider.json';config.write_text('{}')
  b=self.backend(provider_config=str(config),provider_config_sha256='a'*64);o=self.operation()
  with patch('autonomy.process_backend.run_tree') as child:
   with self.assertRaises(ValueError):b.execute_once(o,deadline_monotonic=time.monotonic()+.8)
   child.assert_not_called()
  self.assertEqual(b.status(o['idempotency_key'])['transport_state'],'NOT_RECORDED')
 def test_deadline_expired_before_child_is_unknown_without_launch(self):
  from unittest.mock import patch
  b=self.backend();o=self.operation()
  with patch('autonomy.process_backend.time.monotonic',side_effect=[100,101]),patch('autonomy.process_backend.run_tree') as child:
   with self.assertRaisesRegex(ExecutionUnknown,'DEADLINE_EXPIRED'):
    b.execute_once(o,deadline_monotonic=100.5)
   child.assert_not_called()
  self.assertEqual(b.status(o['idempotency_key'])['transport_state'],'UNKNOWN')
 def test_partial_provider_reference_rejected(self):
  with self.assertRaisesRegex(ValueError,'PROVIDER_REFERENCE_PAIR_REQUIRED'):
   self.backend(provider_config=str(self.f.root/'provider.json'))

if __name__=='__main__':unittest.main()
