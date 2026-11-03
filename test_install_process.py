"""Actual Windows Job evidence in isolated SQLite / 隔离数据库中的真实 Windows Job 凭据。"""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from autonomy import inventory_maintenance as authority
from autonomy.process_job import run_tree
from publisher_channel.install_maintenance import InstallMaintenance
from publisher_channel.install_process import InstallProcessEvidence
import test_install_verifier as terminal_fixture


class InstallProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='u1-process-evidence-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.conn=sqlite3.connect(self.root/'authority.db');self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)');self.conn.commit()
        binding=dict(inventory_id='1784775229336',operation_id='a'*64,source_commit='b'*40,manifest_sha256='c'*64,lease_nonce='d'*64)
        self.session=InstallMaintenance(self.conn,binding,target_operation_id='e'*64,action='install')

    def execute(self,code,*,timeout=3,change=None):
        args=[sys.executable,'-c',code];evidence=InstallProcessEvidence(self.session,args)
        self.evidence=evidence
        def installer(session):
            def sink(event):
                result=evidence.record(event)
                if change:change(event)
                return result
            return run_tree(args,timeout=timeout,assert_live=session.process_guard(),lifecycle=sink)
        def verifier(session,result):
            proof=evidence.confirm_stopped(session)
            return dict(context=session.context,outcome='COMMITTED',evidence_sha256=proof['process_identity_sha256'])
        return self.session.execute(installer,verifier)

    def test_actual_identity_and_stop_are_durable_before_release(self):
        self.execute('print("ok")')
        rows,_=self.evidence._records()
        self.assertEqual([r['event']['phase'] for r in rows],['LAUNCH_INTENT','CONTAINED','STOPPED'])
        self.assertGreater(rows[1]['event']['pid'],0);self.assertGreater(rows[1]['event']['creation_filetime'],0)
        self.assertEqual(Path(rows[1]['event']['image']).resolve(),Path(sys.executable).resolve())
        self.assertFalse(authority.blocked(self.conn))

    def test_timeout_records_verified_stop_but_keeps_maintenance(self):
        with self.assertRaises(subprocess.TimeoutExpired) as caught:self.execute('import time;time.sleep(30)',timeout=.2)
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertTrue(self.evidence.confirm_stopped(self.session)['stopped']);self.assertTrue(authority.blocked(self.conn))
        self.assertEqual(self.session._records()[0][-1]['phase'],'UNKNOWN')

    def test_identity_commit_failure_before_resume_cannot_execute(self):
        marker=self.root/'dangerous-action'
        def fail(event):
            if event['phase']=='CONTAINED':raise OSError('injected after identity commit')
        with self.assertRaises(OSError):self.execute('from pathlib import Path;Path('+repr(str(marker))+').touch()',change=fail)
        self.assertFalse(marker.exists());self.assertTrue(authority.blocked(self.conn))
        self.assertTrue(self.evidence.confirm_stopped(self.session)['stopped'])

    def test_launch_intent_without_identity_is_unknown_and_never_replayed(self):
        def fail(event):
            if event['phase']=='LAUNCH_INTENT':raise OSError('injected launch uncertainty')
        with self.assertRaises(OSError):self.execute('print("unreachable")',change=fail)
        with self.assertRaisesRegex(ValueError,'TERMINATION_UNKNOWN'):self.evidence.confirm_stopped(self.session)
        with self.assertRaisesRegex(ValueError,'INSTANCE_UNKNOWN'):self.evidence.reconcile_stopped()
        with self.assertRaisesRegex(ValueError,'REPLAY'):self.session.execute(lambda _:self.fail('replayed'),lambda *_:None)
        self.assertTrue(authority.blocked(self.conn))

    def test_full_coordinator_terminal_verifier_uses_actual_process_evidence(self):
        fixture=terminal_fixture.InstallVerifierTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        previous=None
        for manifest,action in [('a','install'),('b','upgrade'),('b','rollback'),('a','rollback')]:
            session=fixture.session(manifest,action)
            args=[shutil.which('pwsh'),'-NoProfile','-File',str(fixture.host.root/'run.ps1')]
            evidence=InstallProcessEvidence(session,args)
            verifier=fixture.verifier(manifest,previous if manifest=='b' else None)
            verifier.confirm_stopped=evidence.confirm_stopped
            def install(s):
                result=fixture.host.run_coordinator(maintenance_session=s,process_evidence=evidence,
                    manifest=manifest,upgrade=action=='upgrade',rollback=action=='rollback',previous=previous if action=='upgrade' else None)
                self.assertEqual(result.returncode,0,result.stderr+result.stdout)
                return result
            proof=session.execute(install,verifier)
            self.assertEqual(proof['outcome'],'ROLLED_BACK' if action=='rollback' else 'COMMITTED')
            if manifest=='a' and action=='install':previous=terminal_fixture.v.digest((fixture.host.code/'config/installation.json').read_bytes())
        self.assertFalse(fixture.host.code.exists());self.assertFalse(fixture.host.state.exists())

    def test_supervisor_death_reconciles_original_instance_without_relaunch(self):
        marker=self.root/'child-started'
        child="import os,time,subprocess,sys;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);Path("+repr(str(marker))+ ").write_text(str(p.pid));time.sleep(60)"
        args=[sys.executable,'-c',child]
        binding=self.session.binding
        script=self.root/'parent.py'
        script.write_text('''import sqlite3,sys
sys.path.insert(0,'''+repr(str(Path.cwd()))+''')
from publisher_channel.install_maintenance import InstallMaintenance
from publisher_channel.install_process import InstallProcessEvidence
from autonomy.process_job import run_tree
c=sqlite3.connect('''+repr(str(self.root/'authority.db'))+''')
s=InstallMaintenance(c,'''+repr(binding)+''',target_operation_id='''+repr('e'*64)+''',action='install')
s.acquire();s._transition('INSTALL_INTENT')
args='''+repr(args)+'''
e=InstallProcessEvidence(s,args)
run_tree(args,timeout=60,assert_live=s.process_guard(),lifecycle=e.record)
''',encoding='utf-8')
        parent=subprocess.Popen([sys.executable,'-B',str(script)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        self.addCleanup(lambda:parent.kill() if parent.poll() is None else None)
        deadline=time.monotonic()+10
        while not marker.exists() and parent.poll() is None and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue(marker.exists(),'isolated child did not start')
        evidence=InstallProcessEvidence(self.session,args)
        with self.assertRaisesRegex(ValueError,'INSTANCE_STILL_LIVE'):evidence.reconcile_stopped()
        parent.kill();parent.wait(timeout=10);parent.stderr.close()
        deadline=time.monotonic()+10
        while True:
            try:proof=evidence.reconcile_stopped();break
            except ValueError:
                if time.monotonic()>=deadline:raise
                time.sleep(.02)
        self.assertTrue(proof['stopped']);self.assertTrue(authority.blocked(self.conn))
        self.assertTrue(evidence._records()[0][-1]['event']['reconciled'])
        self.assertEqual(self.session._records()[0][-1]['phase'],'INSTALL_INTENT')
        with self.assertRaisesRegex(ValueError,'REPLAY'):self.session.execute(lambda _:self.fail('replayed'),lambda *_:None)


if __name__=='__main__':unittest.main()
