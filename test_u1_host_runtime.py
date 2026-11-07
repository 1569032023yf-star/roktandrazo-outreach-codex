"""实际HTTP与发布版本集成 / Real HTTP and release integration."""
import http.client
import tempfile
from pathlib import Path
import threading
import time
import unittest
from autonomy.release_store import ReleaseStore,build_bundle,sha
from autonomy.u1_host_runtime import open_host,original_owner_reader

class ProviderHostLifetimeTests(unittest.TestCase):
    def test_main_holds_provider_config_without_exporting_credentials(self):
        import hashlib,json,os,sys
        from contextlib import contextmanager
        from unittest.mock import patch
        from autonomy import u1_host_runtime as host
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'provider.json'
            config.write_text(json.dumps({'schema':'rokt.provider-environment.v1','environment':{
                'WORKBUDDY_DISCOVERY_PROVIDER':'google_places','GOOGLE_MAPS_API_KEY':'fixture-only'}}))
            digest=hashlib.sha256(config.read_bytes()).hexdigest()
            from test_recovery_status import RecoveryStatusTests
            snapshot=RecoveryStatusTests().image()
            args=['host','--release-root',directory,'--state-root',directory,'--token-file',str(root/'token'),
                  '--credential-expires-at',str(int(time.time())+120),'--snapshot',str(root/'snapshot'),'--snapshot-sha256',hashlib.sha256(snapshot).hexdigest(),
                  '--provider-config',str(config),'--provider-config-sha256',digest]
            before=dict(os.environ)
            class Server:
                def serve_forever(self,**kwargs):
                    with self_test.assertRaises(OSError):config.write_bytes(b'changed')
                    self_test.assertEqual(dict(os.environ),before)
            self_test=self
            @contextmanager
            def opened(*args,**kwargs):yield Server()
            with patch.object(sys,'argv',args),patch.object(host,'read_file',side_effect=[b'a'*40,snapshot]),patch.object(host,'open_host',opened):
                host.main()
            config.write_bytes(b'released')
            # Invalid digest must fail before snapshot, original owner or listener.
            args[-1]='0'*64
            with patch.object(sys,'argv',args),patch.object(host,'read_file',return_value=b'fixture-token') as read,patch.object(host,'open_host') as opened:
                with self.assertRaises(ValueError):host.main()
                self.assertEqual(read.call_count,1);opened.assert_not_called()


class HostRuntimeTests(unittest.TestCase):
    def test_changed_provisioned_token_rejects_before_listener_or_state(self):
        import hashlib
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);token=root/'token';token.write_bytes(b'b'*40)
            for expected in (hashlib.sha256(b'a'*40).hexdigest(),'invalid'):
                result=subprocess.run([sys.executable,'-I','-B','-c',
                    'import sys;sys.path.insert(0,sys.argv.pop(1));from autonomy.u1_host_runtime import main;main()',
                    str(Path.cwd()),'--release-root',str(root/'release'),'--state-root',str(root/'state'),
                    '--token-file',str(token),'--token-sha256',expected,'--credential-expires-at','12345',
                    '--snapshot',str(root/'absent-snapshot'),'--snapshot-sha256','a'*64],
                    capture_output=True,timeout=15)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(b'APPROVED_TOKEN_',result.stderr)
                self.assertNotIn(b'b'*40,result.stderr)
                self.assertFalse((root/'state').exists())
                self.assertFalse((root/'release').exists())

    def test_invalid_startup_inputs_reject_before_listener_or_owner(self):
        from unittest.mock import patch
        from autonomy import u1_host_runtime as host
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);token=root/'token';token.write_bytes(b'a'*40)
            snapshot=root/'snapshot';snapshot.write_bytes(b'changed')
            base=['--release-root',str(root/'absent-release'),'--state-root',str(root/'absent-state'),
                  '--token-file',str(token),'--snapshot',str(snapshot),'--snapshot-sha256',sha(b'approved'),
                  '--original-owner-db',str(root/'absent-owner')]
            for expiry,reason in ((int(time.time())+60,'APPROVED_SNAPSHOT_CHANGED'),(1,'CREDENTIAL_EXPIRED')):
                with patch.object(host,'open_host') as opened,patch.object(host,'original_owner_reader') as owner:
                    with self.assertRaisesRegex(ValueError,reason):host.main(base+['--credential-expires-at',str(expiry)])
                    opened.assert_not_called();owner.assert_not_called()
            self.assertFalse((root/'absent-state').exists())

    def test_hash_matching_invalid_schema_stops_normal_and_preflight_startup(self):
        from unittest.mock import patch
        from autonomy import u1_host_runtime as host
        from test_recovery_status import RecoveryStatusTests
        images=[b'not sqlite',RecoveryStatusTests().image(extra=True),RecoveryStatusTests().image(wal=True)]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);token=root/'token';token.write_bytes(b'a'*40);snapshot=root/'snapshot'
            for raw in images:
                snapshot.write_bytes(raw)
                for mode in ([],['--preflight']):
                    with patch.object(host,'open_host') as opened,patch.object(host,'original_owner_reader') as owner:
                        with self.assertRaisesRegex(ValueError,'STARTUP_SNAPSHOT_REJECTED'):
                            host.main(['--release-root',str(root/'missing'),'--state-root',str(root/'state'),
                              '--token-file',str(token),'--snapshot',str(snapshot),'--snapshot-sha256',sha(raw),
                              '--credential-expires-at',str(int(time.time())+60),'--original-owner-db',str(root/'owner')]+mode)
                        opened.assert_not_called();owner.assert_not_called()
                self.assertFalse((root/'state').exists())

    def test_real_preflight_has_no_state_or_listener_side_effects(self):
        import io,json
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from autonomy import u1_host_runtime as host
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);release=root/'release';release.mkdir();state=root/'state';state.mkdir()
            files={name:b'# fixture' for name in ('python/autonomy/u1_host_runtime.py',
                'python/autonomy/host_readonly_http.py','python/autonomy/release_store.py')}
            version=build_bundle(root/'bundle',files,'a'*40)
            store=ReleaseStore(release);store.stage(root/'bundle',version);store.activate(version,expected_current=None)
            token=root/'token';token.write_bytes(b'a'*40);snapshot=root/'snapshot'
            from test_recovery_status import RecoveryStatusTests
            raw=RecoveryStatusTests().image();snapshot.write_bytes(raw)
            config=root/'provider.json'
            config.write_text(json.dumps(dict(schema='rokt.provider-environment.v1',environment={
                'WORKBUDDY_DISCOVERY_PROVIDER':'google_places'})),encoding='utf-8')
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            output=io.StringIO()
            with patch.object(host,'open_host') as opened,redirect_stdout(output):
                host.main(['--release-root',str(release),'--state-root',str(state),'--token-file',str(token),
                  '--credential-expires-at',str(int(time.time())+60),'--snapshot',str(snapshot),
                  '--snapshot-sha256',sha(raw),'--provider-config',str(config),
                  '--provider-config-sha256',sha(config.read_bytes()),'--preflight'])
                opened.assert_not_called()
            result=json.loads(output.getvalue());self.assertTrue(result['startup_inputs_verified']);self.assertTrue(result['snapshot_schema_verified'])
            self.assertFalse(result['production_ready']);self.assertFalse(result['live_lock_verified'])
            self.assertTrue(result['provider_adapter_verified']);self.assertEqual(result['provider_name'],'google_places')
            self.assertFalse(result['provider_configured'])
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_provider_adapter_rejected_before_owner_or_state(self):
        import json
        from unittest.mock import patch
        from autonomy import u1_host_runtime as host
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);token=root/'token';token.write_bytes(b'a'*40)
            config=root/'provider.json'
            config.write_text(json.dumps(dict(schema='rokt.provider-environment.v1',environment={
                'WORKBUDDY_DISCOVERY_PROVIDER':'google_places',
                'GOOGLE_PLACES_LOCATION_BIAS_JSON':'[]'})),encoding='utf-8')
            with patch.object(host,'open_host') as opened,patch.object(host,'original_owner_reader') as owner:
                for mode in ([],['--preflight']):
                    with self.assertRaisesRegex(ValueError,'PROVIDER_LOCATION_OBJECT_REQUIRED'):
                        host.main(['--release-root',str(root/'missing'),'--state-root',str(root/'state'),
                            '--token-file',str(token),'--credential-expires-at',str(int(time.time())+60),
                            '--snapshot',str(root/'missing-snapshot'),'--snapshot-sha256','a'*64,
                            '--provider-config',str(config),'--provider-config-sha256',sha(config.read_bytes())]+mode)
                opened.assert_not_called();owner.assert_not_called()
            self.assertFalse((root/'state').exists())

    def test_original_db_bootstrap_is_readonly_and_rejects_replacement(self):
        import sqlite3
        from contextlib import closing
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'original.sqlite'
            with self.assertRaises(FileNotFoundError):original_owner_reader(path)
            self.assertFalse(path.exists())
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('CREATE TABLE proof(value TEXT)');conn.commit()
            connect=original_owner_reader(path)
            with closing(connect()) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM proof').fetchone()[0],0)
                with self.assertRaises(sqlite3.OperationalError):conn.execute("INSERT INTO proof VALUES('write')")
            replacement=path.with_name('replacement.sqlite')
            with closing(sqlite3.connect(replacement)) as conn:
                conn.execute('CREATE TABLE proof(value TEXT)');conn.commit()
            replacement.replace(path)
            with self.assertRaisesRegex(ValueError,'ORIGINAL_DB_REPLACED'):connect()

    def test_uncertain_publication_blocks_host_and_standalone_bootstrap(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);release=root/'release';state=root/'state';release.mkdir();state.mkdir()
            version=build_bundle(root/'package',{'app/main.py':b'pass\n'},'a'*40)
            store=ReleaseStore(release);store.stage(root/'package',version)
            with patch('autonomy.release_store.os.replace',side_effect=OSError('fault')):
                with self.assertRaises(OSError):store.activate(version,expected_current=None)
            with self.assertRaisesRegex(ValueError,'STOP_AND_PRESERVE'):
                with open_host(release,state,'a'*40,int(time.time())+60,b'{}',sha(b'{}'),port=0):pass
            spec=importlib.util.spec_from_file_location('isolated_bootstrap',Path('autonomy/windows/u1_bootstrap.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with self.assertRaisesRegex(ValueError,'STOP_AND_PRESERVE'):
                module.resolve_release(release)
            self.assertFalse((state/'publisher.lock').exists())

    def test_authenticated_listener_and_exclusive_lifetime(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);release=root/'release';state=root/'state';release.mkdir();state.mkdir()
            version=build_bundle(root/'package',{'app/main.py':b'pass\n'},'a'*40)
            store=ReleaseStore(release);store.stage(root/'package',version);store.activate(version,expected_current=None)
            token='a'*40;snapshot=b'not a production database'
            with open_host(release,state,token,int(time.time())+60,snapshot,sha(snapshot),port=0) as server:
                worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01});worker.start()
                try:
                    with self.assertRaises(OSError):
                        with open_host(release,state,token,int(time.time())+60,snapshot,sha(snapshot),port=0):pass
                    for headers,status in [({},401),({'Authorization':'Bearer '+token},200)]:
                        client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                        client.request('GET','/v1/health',headers=headers);reply=client.getresponse()
                        self.assertEqual(reply.status,status);reply.read();client.close()
                finally:server.shutdown();worker.join(3)
            with open_host(release,state,token,int(time.time())+60,snapshot,sha(snapshot),port=0):pass

if __name__=='__main__':unittest.main()
