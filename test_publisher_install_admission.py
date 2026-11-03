"""Original HTTP/auth/seal and real isolated DB / 原HTTP认证seal与真实隔离DB。

Positive installation/process/verifier callbacks are explicit doubles, never SCM.
"""
from contextlib import closing
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from publisher_channel import bridge
from publisher_channel import install_admission as admission
from publisher_channel import install_command as command
from autonomy import inventory_maintenance as authority
import registry


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-admission-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.releases=self.root/'releases';self.releases.mkdir()
        self.db=self.root/'official-isolated.db'
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)');conn.commit()
        self.approval=dict(source_commit='a'*40,manifest_sha256='b'*64,runtime_plan_sha256='c'*64,
            powershell_sha256='d'*64,generated_files={'config/runtime.json':'e'*64,'config/supervisor.json':'f'*64},
            previous_receipt_sha256=None,allow_install=False,full_chain_review_passed=False,
            allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
        self.cfg=dict(channel_id='isolated-u1',production=dict(db_path=str(self.db)),releases={},
            lock=dict(key_prefix=authority.PREFIX,stale_after_seconds=7200),
            u1_install=dict(inventory_id='1784775229336',approvals=dict(fixed=self.approval)),
            _paths=dict(releases=str(self.releases),state=str(self.root/'state'),audit=str(self.root/'audit.jsonl')))
        (self.releases/'allowed_scope.json').write_text('{"paths":["bd_orchestrator.py"]}',encoding='utf-8')
        self.seal()
        for obj,name,value in ((admission,'RELEASES',self.releases),(command,'RELEASES',self.releases),
                               (bridge,'INFLIGHT',self.root/'inflight.json')):
            p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        self.bridge=bridge.Bridge(self.cfg,'isolated-token');self.completed=threading.Event()
        end=self.bridge.inflight_end
        def ended(op):
            end(op);self.completed.set()
        self.bridge.inflight_end=ended
        self.server=bridge.ThreadingHTTPServer(('127.0.0.1',0),bridge.make_handler(self.bridge))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close_server)
        self.req=dict(release_id='fixed',invocation_id='1'*64,target_operation_id='2'*64,action='install')

    def close_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())

    def seal(self):
        (self.releases/'channel_config.json').write_text(json.dumps({k:v for k,v in self.cfg.items() if not k.startswith('_')}),encoding='utf-8')
        registry.write_seal(self.cfg)

    def post(self,value,token='isolated-token',raw=None):
        self.completed.clear()
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        try:
            conn.request('POST','/v1/u1-install',body=json.dumps(value) if raw is None else raw,
                         headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            response=conn.getresponse();result=(response.status,json.loads(response.read()))
            if raw is None and token=='isolated-token' and value.get('action')!='status':self.assertTrue(self.completed.wait(5))
            return result
        finally:conn.close()

    def rows(self):
        with closing(sqlite3.connect(self.db)) as conn:return conn.execute('SELECT key,value FROM system_config ORDER BY key').fetchall()

    def enable_fixture(self):
        # Isolated sealed-policy fixture, never changes repository/site config.
        self.approval.update(allow_install=True,full_chain_review_passed=True);self.seal()

    def fake_adapter(self,fail=False):
        owner=self
        class Adapter:
            calls=0
            def __init__(self,release_id,approval):command.InstallCommand(release_id,approval)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def __call__(self,session):
                Adapter.calls+=1
                owner.assertTrue(session.process_guard()())
                if fail and session.context['action']!='recover':raise RuntimeError('ISOLATED_INSTALLER_FAILURE')
                return 'isolated-return'
            def verifier(self,session):
                def verify(actual,observed):
                    owner.assertEqual(actual.context,session.context)
                    owner.assertTrue(actual.assert_held(actual.context['target_operation_id'],actual.binding['source_commit'],actual.binding['manifest_sha256'],actual.context['action']))
                    return dict(context=actual.context,outcome='ROLLED_BACK' if actual.context['action'] in ('recover','rollback') else 'COMMITTED',evidence_sha256='3'*64)
                return verify
            def confirm_stopped(self,session):return dict(context=session.context,stopped=True,process_identity_sha256='4'*64)
            def reconcile_stopped(self,session):return self.confirm_stopped(session)
        return Adapter

    def test_original_auth_and_closed_gate_do_not_open_db(self):
        with patch.object(bridge.ex,'rw_existing_conn',side_effect=AssertionError('DB_MUST_NOT_OPEN')):
            code,value=self.post(self.req,token='wrong');self.assertEqual(code,401)
            code,value=self.post(self.req);self.assertEqual(code,400);self.assertIn('INSTALL_GATE_CLOSED',value['error'])
        self.assertEqual(self.rows(),[])

    def test_request_cannot_supply_approvals_paths_or_duplicate_keys(self):
        for key in ('approval','allow_install','manifest_sha256','command','db_path'):
            code,_=self.post(dict(self.req,**{key:True}));self.assertEqual(code,400)
        for release in ('../elsewhere',[],None):
            code,_=self.post(dict(self.req,release_id=release));self.assertEqual(code,400)
        code,_=self.post({},raw='{"action":"status","action":"install"}');self.assertEqual(code,400)
        self.assertEqual(self.rows(),[])

    def test_missing_tampered_and_stale_loaded_seals_refuse(self):
        registry.seal_path(self.cfg).unlink()
        self.assertEqual(self.post(self.req)[0],500)  # Missing receipt preserves; no DB effects.
        self.seal();(self.releases/'allowed_scope.json').write_text('{"paths":[]}',encoding='utf-8')
        code,value=self.post(self.req);self.assertEqual(code,400);self.assertIn('REGISTRY_TAMPERED',value['error'])
        self.seal();self.cfg['production']['db_path']=str(self.root/'other.db')
        code,value=self.post(self.req);self.assertEqual(code,400);self.assertIn('LOADED_CONFIG_CHANGED',value['error'])
        self.assertFalse((self.root/'other.db').exists());self.assertEqual(self.rows(),[])

    def test_live_held_marker_duplicate_and_atomic_release(self):
        self.enable_fixture();adapter=self.fake_adapter()
        with patch.object(admission,'InstallCommand',adapter):
            code,value=self.post(self.req);self.assertEqual(code,200,value);self.assertEqual(value['state'],'COMMITTED')
            after=self.rows();self.assertEqual(dict(after)[authority.KEY],'released')
            code,value=self.post(self.req);self.assertEqual(code,200,value);self.assertEqual(value['state'],'RELEASED')
            self.assertEqual(value['evidence'],'JOURNAL_ONLY');self.assertEqual(adapter.calls,1);self.assertEqual(self.rows(),after)
            code,_=self.post(dict(self.req,target_operation_id='5'*64));self.assertEqual(code,400)

    def test_failure_preserves_and_explicit_compensation_does_not_replay_forward(self):
        self.enable_fixture();adapter=self.fake_adapter(fail=True)
        with patch.object(admission,'InstallCommand',adapter):
            self.assertEqual(self.post(self.req)[0],500)
            self.assertNotEqual(dict(self.rows())[authority.KEY],'released')
            code,value=self.post(self.req);self.assertEqual(code,200);self.assertEqual(value['state'],'UNKNOWN');self.assertEqual(adapter.calls,1)
            recovery=dict(release_id='fixed',invocation_id='1'*64,action='compensate',recovery_path=[],recovery_id='6'*64)
            code,value=self.post(recovery);self.assertEqual(code,200,value);self.assertEqual(value['state'],'ROLLED_BACK')
            self.assertEqual(adapter.calls,2);self.assertEqual(dict(self.rows())[authority.KEY],'released')
            self.assertEqual(self.post(recovery)[0],400);self.assertEqual(adapter.calls,2)

    def test_status_is_read_only_even_with_install_gate_closed(self):
        self.enable_fixture();adapter=self.fake_adapter()
        with patch.object(admission,'InstallCommand',adapter):self.assertEqual(self.post(self.req)[0],200)
        self.approval.update(allow_install=False,full_chain_review_passed=False);self.seal()
        before=self.rows();inflight=(self.root/'inflight.json').read_bytes()
        with patch.object(bridge.ex,'rw_existing_conn',side_effect=AssertionError('NO_DB_WRITE')):
            code,value=self.post(dict(release_id='fixed',invocation_id='1'*64,action='status',recovery_path=[]))
            self.assertEqual(code,200,value);self.assertEqual(value['evidence'],'JOURNAL_ONLY')
        self.assertEqual(self.rows(),before);self.assertEqual((self.root/'inflight.json').read_bytes(),inflight)

    def test_missing_official_db_is_not_created(self):
        self.enable_fixture();self.db.unlink()
        self.assertEqual(self.post(self.req)[0],500);self.assertFalse(self.db.exists())

    def test_bad_body_does_not_clear_another_inflight_operation(self):
        self.bridge.inflight_begin('original-apply')
        before=(self.root/'inflight.json').read_bytes()
        self.assertEqual(self.post({},raw='{"action":"install","action":"status"}')[0],400)
        self.assertEqual((self.root/'inflight.json').read_bytes(),before)

    def test_sole_inventory_and_original_lock_cannot_be_reconfigured_by_admission(self):
        self.cfg['u1_install']['inventory_id']='second-inventory';self.seal()
        code,value=self.post(self.req);self.assertEqual(code,400);self.assertIn('SEALED_POLICY_REQUIRED',value['error'])
        self.cfg['u1_install']['inventory_id']='1784775229336';self.cfg['lock']['key_prefix']='another:';self.seal()
        code,value=self.post(self.req);self.assertEqual(code,400);self.assertIn('ORIGINAL_INVENTORY_LOCK',value['error'])
        self.assertEqual(self.rows(),[])


if __name__=='__main__':unittest.main()
