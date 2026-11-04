"""Read-only real staged package, no service operations / 真实暂存包只读验证，无服务操作。"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from autonomy.build_dev_disabled_host import build_development
from publisher_channel import install_command as command
from publisher_channel.install_verifier import digest


class InstallCommandTests(unittest.TestCase):
    def test_v3_packaged_runtime_admission_keeps_install_gate_closed(self):
        from autonomy.disabled_host_package import build_runtime_package,canonical
        runtime=self.root/'runtime-input';runtime.mkdir()
        (runtime/'python.exe').write_bytes(b'fixture-not-executable')
        content=canonical(dict(schema='rokt.u1-runtime-content.v1',python='python.exe',
                               files={'python.exe':digest((runtime/'python.exe').read_bytes())}))
        (runtime/'U1_RUNTIME_CONTENT.json').write_bytes(content)
        # Move only this test's known directory; preserve the original fixture.
        base=self.root/'base-host'
        self.assertTrue(self.package.resolve().is_relative_to(self.root.resolve()))
        self.package.rename(base)
        result=build_runtime_package(self.package,base,self.approval['manifest_sha256'],runtime,digest(content))
        path=self.release/'u1-runtime-plan.json';plan=json.loads(path.read_bytes())
        plan.update(schema='rokt.u1-provision-plan.v3',python=str(self.package/'runtime/python/python.exe'),
                    python_sha256=digest((runtime/'python.exe').read_bytes()),
                    python_runtime_manifest=str(self.package/'runtime/python/U1_RUNTIME_CONTENT.json'),
                    python_runtime_manifest_sha256=digest(content))
        raw=canonical(plan);path.write_bytes(raw)
        approval=dict(self.approval,manifest_sha256=result['manifest_sha256'],runtime_plan_sha256=digest(raw))
        with command.InstallCommand('isolated',approval) as adapter:
            self.assertIn('runtime/python/python.exe',adapter.expected_files)
            with self.assertRaisesRegex(ValueError,'INSTALL_GATE_CLOSED'):adapter(None)
        plan['python']=str(runtime/'python.exe');raw=canonical(plan);path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'PACKAGED_RUNTIME_BINDING'):
            with command.InstallCommand('isolated',dict(approval,runtime_plan_sha256=digest(raw))):pass

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-command-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.releases=self.root/'releases';self.release=self.releases/'isolated'
        (self.release/'payload').mkdir(parents=True)
        self.package=self.release/'payload'/'host'
        build_development(self.package,'a'*40)
        self.token=self.root/'token';self.token.write_bytes(b'isolated-not-a-production-token')
        self.snapshot=self.root/'snapshot';self.snapshot.write_bytes(b'isolated-snapshot')
        self.runtime=self.root/'runtime';self.runtime.mkdir()
        plan=dict(schema='rokt.u1-provision-plan.v1',inventory_id='1784775229336',python=sys.executable,
            python_sha256=digest(Path(sys.executable).read_bytes()),release_root=str(self.runtime),token_file=str(self.token),
            token_sha256=digest(self.token.read_bytes()),credential_expires_at=int(time.time())+600,
            snapshot=str(self.snapshot),snapshot_sha256=digest(self.snapshot.read_bytes()))
        raw=json.dumps(plan,separators=(',',':')).encode();(self.release/'u1-runtime-plan.json').write_bytes(raw)
        shell=command.windows_root()/'System32/WindowsPowerShell/v1.0/powershell.exe'
        self.approval=dict(source_commit='a'*40,manifest_sha256=digest((self.package/'manifest.json').read_bytes()),
            runtime_plan_sha256=digest(raw),powershell_sha256=digest(shell.read_bytes()),generated_files={
                'config/runtime.json':'b'*64,'config/supervisor.json':'c'*64},previous_receipt_sha256=None,
            allow_install=False,full_chain_review_passed=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
        p=patch.object(command,'RELEASES',self.releases);p.start();self.addCleanup(p.stop)

    def test_original_owner_plan_admission_preserves_mutable_database(self):
        import sqlite3
        database=self.root/'original.sqlite'
        connection=sqlite3.connect(database);self.addCleanup(connection.close)
        connection.execute('CREATE TABLE owner(value TEXT)');connection.commit()
        path=self.release/'u1-runtime-plan.json';plan=json.loads(path.read_bytes())
        plan['original_owner_db']=str(database)
        raw=json.dumps(plan,separators=(',',':')).encode();path.write_bytes(raw)
        approval=dict(self.approval,runtime_plan_sha256=digest(raw))
        with command.InstallCommand('isolated',approval) as adapter:
            connection.execute("INSERT INTO owner VALUES('original owner continues writing')");connection.commit()
            self.assertTrue(adapter.pins.revalidate())
            with self.assertRaises(OSError):database.unlink()
            with self.assertRaises(OSError):database.rename(self.root/'replaced.sqlite')
            with self.assertRaisesRegex(ValueError,'INSTALL_GATE_CLOSED'):adapter(None)
        self.assertEqual(connection.execute('SELECT value FROM owner').fetchone()[0],'original owner continues writing')
        connection.close()
        database.rename(self.root/'released.sqlite')
        plan['event_runtime']=str(self.runtime)
        raw=json.dumps(plan,separators=(',',':')).encode();path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'RUNTIME_PLAN'):
            with command.InstallCommand('isolated',dict(approval,runtime_plan_sha256=digest(raw))):pass

    def test_real_runtime_pins_and_closed_install_gate(self):
        with command.InstallCommand('isolated',self.approval) as adapter:
            self.assertTrue(adapter.pins.revalidate())
            self.assertIn('config/runtime.json',adapter.expected_files)
            with self.assertRaises(OSError):self.token.write_bytes(b'replaced')
            with self.assertRaisesRegex(ValueError,'INSTALL_GATE_CLOSED'):adapter(None)
            class Session:
                binding=dict(source_commit='a'*40,manifest_sha256=self.approval['manifest_sha256'])
                context=dict(target_operation_id='d'*64,action='install')
            args=adapter.command(Session())
            self.assertEqual(args[0],str(command.windows_root()/'System32/WindowsPowerShell/v1.0/powershell.exe'))
            self.assertEqual(args[4],str(self.package/'Publisher-InstallHost.ps1'))
            self.assertNotIn('-ExecutionPolicy',args)
        self.token.write_bytes(b'after-close')

    def test_private_entry_without_live_parent_refuses_before_package_access(self):
        script=Path('autonomy/windows/Publisher-InstallHost.ps1').resolve()
        result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-File',str(script),'-PackageRoot',str(self.root/'absent'),
            '-ApprovedManifestSha256','a'*64,'-ApprovedSourceCommit','b'*40,'-RuntimePlan',str(self.root/'absent-plan'),
            '-ApprovedRuntimePlanSha256','c'*64,'-OperationId','d'*64,'-Action','install'],stdin=subprocess.DEVNULL,capture_output=True,timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'U1_MAINTENANCE:',result.stdout)
        self.assertNotIn(b'MANIFEST_HASH_MISMATCH',result.stderr)
        self.assertFalse((self.root/'absent').exists())

    def test_no_arbitrary_release_path_or_dispatch_grant(self):
        for release in ('../elsewhere','C:\\other','/other','x/y'):
            with self.assertRaises(ValueError):command.InstallCommand(release,self.approval)
        with self.assertRaises(ValueError):command.InstallCommand('isolated',dict(self.approval,allow_dispatch=True))

    def test_expired_plan_blocks_forward_but_not_explicit_recovery_authority_check(self):
        path=self.release/'u1-runtime-plan.json';plan=json.loads(path.read_bytes());plan['credential_expires_at']=1
        raw=json.dumps(plan,separators=(',',':')).encode();path.write_bytes(raw)
        # Isolated trusted-policy fixture only. No process or service is launched.
        approval=dict(self.approval,runtime_plan_sha256=digest(raw),allow_install=True,full_chain_review_passed=True)
        class Session:
            binding=dict(source_commit='a'*40,manifest_sha256=approval['manifest_sha256'])
            context=dict(target_operation_id='d'*64,action='install')
            def process_guard(self):raise RuntimeError('LIVE_AUTHORITY_REQUIRED')
        session=Session()
        with command.InstallCommand('isolated',approval) as adapter:
            with self.assertRaisesRegex(ValueError,'CREDENTIAL_EXPIRED'):adapter(session)
            session.context['action']='recover'
            with self.assertRaisesRegex(RuntimeError,'LIVE_AUTHORITY_REQUIRED'):adapter(session)

    def test_pinned_observer_binds_nonce_checks_authority_and_fails_closed(self):
        class Session:
            binding=dict(source_commit='a'*40,manifest_sha256=self.approval['manifest_sha256'])
            context=dict(target_operation_id='d'*64,action='install')
            live=True
            def assert_held(self,*args):
                if not self.live:raise ValueError('MAINTENANCE_LOST')
                return True
        session=Session()
        with command.InstallCommand('isolated',self.approval) as adapter:
            verifier=adapter.verifier(session)
            calls=[]
            def run(args,**options):
                calls.append(args)
                self.assertTrue(options['assert_live']())
                self.assertEqual(args[4],str(self.package/'Observe-HostInstall.ps1'))
                self.assertNotIn('-ExecutionPolicy',args)
                return subprocess.CompletedProcess(args,0,json.dumps(dict(operation_id='d'*64,nonce='e'*64)),'')
            with patch.object(command,'run_tree',run):
                self.assertEqual(verifier.observe('d'*64,'e'*64)['nonce'],'e'*64)
                with self.assertRaisesRegex(ValueError,'OBSERVER_CONTEXT'):verifier.observe('f'*64,'e'*64)
                session.live=False
                with self.assertRaisesRegex(ValueError,'MAINTENANCE_LOST'):verifier.observe('d'*64,'e'*64)
            self.assertEqual(len(calls),1)
            session.live=True
            with patch.object(command,'run_tree',return_value=subprocess.CompletedProcess([],0,'{"nonce":"wrong"}','')):
                with self.assertRaisesRegex(ValueError,'OBSERVER_CONTEXT'):verifier.observe('d'*64,'e'*64)
            with patch.object(command,'run_tree',return_value=subprocess.CompletedProcess([],1,'','execution policy')):
                with self.assertRaisesRegex(ValueError,'OBSERVER_RETURNED_FAILURE'):verifier.observe('d'*64,'e'*64)


if __name__=='__main__':unittest.main()
