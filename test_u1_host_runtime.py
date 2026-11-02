"""实际HTTP与发布版本集成 / Real HTTP and release integration."""
import http.client
import tempfile
from pathlib import Path
import threading
import time
import unittest
from autonomy.release_store import ReleaseStore,build_bundle,sha
from autonomy.u1_host_runtime import open_host

class HostRuntimeTests(unittest.TestCase):
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
