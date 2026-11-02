"""发布器实际文件生命周期 / Actual file publisher lifecycle."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from autonomy.release_store import ReleaseStore, build_bundle

class ReleaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'store').mkdir();self.store=ReleaseStore(self.root/'store')
    def package(self,name,files):
        p=self.root/name;v=build_bundle(p,files,'a'*40);self.store.stage(p,v);return v
    def test_first_install_upgrade_and_complete_pointer_rollback(self):
        v1=self.package('one',{'app/old.py':b'old'});a=self.store.activate(v1,expected_current=None)
        v2=self.package('two',{'app/new.py':b'new','app/other.py':b'other'})
        b=self.store.activate(v2,expected_current=v1);self.assertEqual(self.store.status()['version'],v2)
        self.store.rollback(b['transaction'],expected_current=v2)
        self.assertEqual(self.store.status()['version'],v1)
        self.assertEqual((self.store._version(v1)/'payload/app/old.py').read_bytes(),b'old')
        self.store.rollback(a['transaction'],expected_current=v1)
        self.assertIsNone(self.store.status()['version'])
    def test_failed_commit_keeps_old_pointer_and_backup(self):
        v1=self.package('one',{'app/a.py':b'one'});self.store.activate(v1,expected_current=None)
        v2=self.package('two',{'app/a.py':b'two'})
        with patch('autonomy.release_store.os.replace',side_effect=OSError('fault')):
            with self.assertRaises(OSError):self.store.activate(v2,expected_current=v1)
        self.assertEqual(self.store.status()['version'],v1)
        with self.assertRaises(ValueError):self.store.activate(v2,expected_current=None)
    def test_tamper_refused_and_inactive_delete_preserves_backups(self):
        v1=self.package('one',{'app/a.py':b'one'});self.store.activate(v1,expected_current=None)
        with self.assertRaises(ValueError):self.store.delete_inactive(v1)
        v2=self.package('two',{'app/b.py':b'two'});self.store.delete_inactive(v2)
        self.assertFalse(self.store._version(v2).exists())
        (self.store._version(v1)/'payload/app/a.py').write_bytes(b'bad')
        with self.assertRaises(ValueError):self.store.status()
    def test_namespace_paths_rejected(self):
        for name in ['../a','/root','app/CON.py','app/a.','app//a']:
            with self.assertRaises(ValueError):build_bundle(self.root/'bad',{name:b'x'},'a'*40)

if __name__=='__main__':unittest.main()
