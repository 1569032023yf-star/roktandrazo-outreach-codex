import hashlib,json,os,sys,tempfile,unittest,zipfile
from pathlib import Path
from tools.verify_u1_rollback import verify_rollback

@unittest.skipUnless(os.name=='nt','Windows pinning required')
class RollbackArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd());self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.tool=Path('autonomy/release_store.py').read_bytes();self.host=b'host fixture'
        self.manifest={'source_commit':'a'*40,'files':{'python/autonomy/release_store.py':hashlib.sha256(self.tool).hexdigest(),'host/config/host.json':hashlib.sha256(self.host).hexdigest()}}
    def run_archive(self,rows):
        path=self.root/'rollback.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name,data in rows:z.writestr(name,data)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        return verify_rollback(path,digest,self.manifest,sys.executable,self.root)
    def test_actual_isolated_pointer_rollback_and_parity(self):
        r=self.run_archive([('host/config/host.json',self.host),('release_store.py',self.tool)])
        self.assertTrue(r['rollback_host_and_tool_parity_verified']);self.assertTrue(r['isolated_pointer_rollback_verified'])
        self.assertFalse(r['rollback_verified']);self.assertFalse(r['production_ready'])
    def test_missing_host_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'ROLLBACK_HOST_SET_MISMATCH'):self.run_archive([('release_store.py',self.tool)])
    def test_tampered_host_and_tool_are_rejected(self):
        for host,tool in [(b'changed',self.tool),(self.host,self.tool+b'bad')]:
            with self.subTest(host=host):
                with self.assertRaisesRegex(ValueError,'ROLLBACK_CONTENT_MISMATCH'):self.run_archive([('host/config/host.json',host),('release_store.py',tool)])
    def test_traversal_and_duplicate_case_are_rejected(self):
        for extra in [('../escape',b'x'),('HOST/config/host.json',b'x')]:
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):self.run_archive([('host/config/host.json',self.host),('release_store.py',self.tool),extra])
    def test_archive_digest_mismatch_rejected(self):
        path=self.root/'rollback.zip';path.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'DIGEST_MISMATCH'):verify_rollback(path,'0'*64,self.manifest,sys.executable,self.root)

    def test_temporary_script_is_pinned_during_subprocess(self):
        from unittest import mock
        import subprocess
        real=subprocess.run;observed=[]
        def intercept(command,**kwargs):
            script=Path(command[5])
            with self.assertRaises(PermissionError):script.write_bytes(b'tamper')
            with self.assertRaises(PermissionError):script.parent.rename(script.parent.with_name('replaced'))
            observed.append(True)
            return real(command,**kwargs)
        with mock.patch('tools.verify_u1_rollback.subprocess.run',side_effect=intercept):
            self.run_archive([('host/config/host.json',self.host),('release_store.py',self.tool)])
        self.assertEqual(observed,[True])

class RollbackDeliveryLifetimeTests(unittest.TestCase):
    def test_runtime_remains_pinned_until_after_rollback_probe(self):
        from types import SimpleNamespace
        from unittest import mock
        from tools import verify_u1_delivery as delivery
        events=[]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            root=Path(td);p=root/'payload';p.mkdir()
            (p/'DELIVERY.json').write_text(json.dumps(dict(source_commit='a'*40,python_runtime_bundled=True,
                allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,
                production_ready=False,runtime_manifest_sha256='b'*64)),encoding='utf-8')
            args=SimpleNamespace(archive='fixture',archive_sha256='d'*64,output=str(root),manifest_sha256='e'*64,
                source_commit='a'*40,rollback_archive='fixture-rollback',rollback_archive_sha256='f'*64)
            manifest={'source_commit':'a'*40,'files':{'host/manifest.json':'c'*64}}
            host_manifest={'files':[{'path':'runtime/python/U1_RUNTIME_CONTENT.json','sha256':'b'*64}]}
            class Pins:
                active=False
                def __enter__(self):self.active=True;events.append('enter');return self
                def __exit__(self,*args):self.active=False;events.append('exit')
                def revalidate(self):self_check.assertTrue(self.active);events.append('revalidate')
            self_check=self;pins=Pins()
            def rollback(*args):
                self.assertTrue(pins.active);events.append('rollback')
                return {'rollback_verified':False,'installation_verified':False}
            with mock.patch.object(delivery,'extract_checked',return_value=root), \
                 mock.patch.object(delivery,'ReleaseStore') as store, \
                 mock.patch.object(delivery,'InstallInputPins',return_value=pins), \
                 mock.patch.object(delivery,'pin_package',return_value=host_manifest), \
                 mock.patch.object(delivery,'pin_python_runtime'), \
                 mock.patch.object(delivery.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')), \
                 mock.patch('tools.verify_u1_rollback.verify_rollback',side_effect=rollback):
                store.return_value._verify.return_value=manifest
                delivery.verify(args)
            self.assertEqual(events,['enter','rollback','revalidate','exit'])
