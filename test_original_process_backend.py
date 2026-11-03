"""Actual original functions -> HTTP -> Windows process tree -> durable ledgers.

Original DB functions are AST-loaded to avoid importing environment/bootstrap
side effects. All DBs, workers, signatures and business counts are test fixtures.
"""
import ast
from contextlib import closing,contextmanager
import hashlib
from pathlib import Path
import sqlite3
import sys
import threading
import time
import unittest
from unittest.mock import patch

from autonomy import inventory_maintenance as maintenance
from autonomy.inventory_event_bridge import ExistingOwnerBridge
from autonomy.original_inventory_owner import OriginalOwnerAuthority
from autonomy.original_stage_event import OriginalStageEvent
from autonomy.process_backend import ProcessBackend
from autonomy.release_store import ReleaseStore,build_bundle,sha
from autonomy.single_slot_adapter import OriginalOwnerSlotAdapter
from autonomy.u1_host_runtime import open_host
from autonomy.unattended_policy import INVENTORY
from tests.test_inventory_stage_trace import Harness,ROOT
from test_growth_ledger import T
import test_process_backend as backend_fixtures


class OriginalProcessBackendTests(unittest.TestCase):
    def setUp(self):
        self.bf=backend_fixtures.BackendTests('runTest');self.bf.setUp();self.addCleanup(self.bf.doCleanups)
        self.f=self.bf.f
        self.path=self.f.root/'original.sqlite'
        def connect():
            conn=sqlite3.connect(self.path,timeout=2)
            conn.row_factory=sqlite3.Row
            return conn
        self.connect=connect
        self.ro=lambda:sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True,timeout=2)
        with closing(self.connect()) as conn:
            conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)')
            conn.execute('CREATE TABLE job_runs(run_id TEXT PRIMARY KEY,stage TEXT,business_date TEXT,status TEXT,dry_run INTEGER,finished_at TEXT,actual INTEGER,gap INTEGER,stop_reason TEXT,error TEXT)')
            conn.execute("INSERT INTO job_runs(run_id,stage,business_date,status,dry_run) VALUES('original-run','inventory','2026-11-03','running',0)")
            conn.commit()
        tree=ast.parse((ROOT/'bd_db.py').read_text(encoding='utf-8'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('acquire_run_lock','release_run_lock')]
        self.db=dict(get_db=self.connect)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-original-db-functions>','exec'),self.db)
        self.captured=self.db['acquire_run_lock']('inventory:2026-11-03','original-run',capture_owner=True)
        self.authority=OriginalOwnerAuthority(self.connect)
        code=self.bf.worker.read_text(encoding='utf-8')
        marker='c={k:o[k] for k in ("slot","epoch","owner","run_id","request_id")}\n'
        assert code.count(marker)==1
        self.bf.worker.write_text(code.replace(marker,marker+'c.update({k:o[k] for k in ("lock_token_hash","process_identity_hash","original_event_digest","original_claim_digest")})\n'),encoding='utf-8')
        self.backend=self.make_backend()
        self.f.adapter=OriginalOwnerSlotAdapter(self.f.slots,self.f.budget,original_owner=self.authority,
            target=self.f.target,consumer=self.f.trust,backend=self.backend,
            wall_clock=lambda:T+10,monotonic=time.monotonic)

    def make_backend(self, original=True):
        return ProcessBackend(self.f.root/'backend.sqlite',python=sys.executable,
            python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            worker=str(self.bf.worker),worker_sha256=sha(self.bf.worker.read_bytes()),
            backend_id='synthetic-backend',offline_only=True,
            original_owner=self.authority if original else None)

    def event(self):
        return dict(inventory_id=INVENTORY,admission=self.f.admission(),schedule=self.f.plan,
                    idle=self.f.idle,budget_request=self.f.request)

    @contextmanager
    def host(self):
        release=self.f.root/'release';state=self.f.root/'state';release.mkdir();state.mkdir()
        version=build_bundle(self.f.root/'package',{'app/main.py':b'pass\n'},'a'*40)
        store=ReleaseStore(release);store.stage(self.f.root/'package',version);store.activate(version,expected_current=None)
        token='original_process_'+('a'*40)
        with open_host(release,state,token,int(time.time())+60,b'fixture',sha(b'fixture'),
                       port=0,original_owner_connect=self.ro) as server:
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});thread.start()
            try:yield ExistingOwnerBridge(self.f.adapter,port=server.server_port,token=token)
            finally:server.shutdown();thread.join(3)

    def test_actual_stage_host_child_settlement_and_atomic_job_release(self):
        with self.host() as bridge:
            execution=OriginalStageEvent(bridge,self.event(),captured_owner=self.captured)
            h=Harness(path=ROOT/'bd_orchestrator.py',safe=50)
            h.ns.update(get_db=self.connect,release_run_lock=self.db['release_run_lock'],
                        acquire_run_lock=lambda *a,**k:self.fail('second acquisition'))
            with patch.dict('sys.modules',h.modules):
                self.assertTrue(h.ns['stage_inventory']('original-run','2026-11-03',False,event_execution=execution))
        self.assertEqual(self.bf.marker.read_text(),'called\n')
        self.assertEqual(h.business,[])
        with closing(self.connect()) as conn:
            self.assertEqual(tuple(conn.execute('SELECT status,actual,gap FROM job_runs').fetchone()),('completed',50,0))
            self.assertEqual(conn.execute('SELECT value FROM system_config WHERE key=?',
                (maintenance.INVENTORY_PREFIX+'2026-11-03',)).fetchone()[0],'released')
        with self.f.budget.tx() as conn:
            self.assertEqual(conn.execute('SELECT state FROM reservations').fetchone()[0],'settled')
        with closing(sqlite3.connect(self.backend.path)) as conn:
            self.assertEqual(conn.execute('SELECT state FROM executions').fetchone()[0],'OUTPUT_RECORDED')

    def test_original_context_cannot_use_unbound_legacy_transport(self):
        self.f.adapter.backend=self.make_backend(original=False)
        event=self.event();self.f.adapter.prepare_event(event)
        self.assertEqual(self.f.run_one(event['admission'])['outcome'],'UNKNOWN_RECONCILE_ONLY')
        self.assertFalse(self.bf.marker.exists())
        self.assertFalse(self.db['release_run_lock']('inventory:2026-11-03','original-run',expected_owner=self.captured))

    def test_live_owner_loss_kills_actual_child_and_preserves_unknown(self):
        code=self.bf.worker.read_text(encoding='utf-8')
        self.bf.worker.write_text(code.replace('print(json.dumps','import time;time.sleep(60)\nprint(json.dumps'),encoding='utf-8')
        self.backend=self.make_backend();self.f.adapter.backend=self.backend
        changed=threading.Event();errors=[]
        def lose_authority():
            try:
                limit=time.monotonic()+5
                while not self.bf.marker.exists():
                    if time.monotonic()>limit:raise TimeoutError('child marker not observed')
                    time.sleep(.01)
                with closing(self.connect()) as conn:
                    conn.execute('INSERT INTO system_config VALUES(?,?,NULL)',(maintenance.KEY,'injected unknown maintenance'))
                    conn.commit()
                changed.set()
            except Exception as exc:errors.append(exc)
        writer=threading.Thread(target=lose_authority);writer.start()
        observed=[]
        from autonomy.process_job import run_tree
        def track(*args,**kwargs):
            try:return run_tree(*args,**kwargs)
            except BaseException as exc:
                observed.append(exc);raise
        event=self.event();self.f.adapter.prepare_event(event)
        with patch('autonomy.process_backend.run_tree',side_effect=track):
            result=self.f.run_one(event['admission'])
        writer.join(6)
        self.assertFalse(errors,errors);self.assertTrue(changed.is_set())
        self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
        self.assertEqual(len(observed),1)
        self.assertTrue(getattr(observed[0],'cleanup_verified',False))
        self.assertEqual(self.bf.marker.read_text(),'called\n')
        with closing(sqlite3.connect(self.backend.path)) as conn:
            self.assertEqual(conn.execute('SELECT state FROM executions').fetchone()[0],'UNKNOWN')
        self.assertFalse(self.db['release_run_lock']('inventory:2026-11-03','original-run',expected_owner=self.captured))


if __name__=='__main__':unittest.main()
