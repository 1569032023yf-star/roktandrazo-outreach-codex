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
        self.assertTrue(r['rollback_archive_parity_verified']);self.assertTrue(r['isolated_pointer_rollback_verified'])
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
