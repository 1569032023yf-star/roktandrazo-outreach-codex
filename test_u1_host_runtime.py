"""实际HTTP与发布版本集成 / Real HTTP and release integration."""
import http.client
import tempfile
from pathlib import Path
import threading
import time
import unittest
from autonomy.release_store import ReleaseStore,build_bundle,sha
from autonomy.u1_host_runtime import open_host,original_owner_reader

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
