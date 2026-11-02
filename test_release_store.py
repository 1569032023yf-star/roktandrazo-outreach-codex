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
    @unittest.skipUnless(__import__('os').name=='nt','Windows path contract')
    def test_final_sha_layout_rejected_before_staging(self):
        deep=self.root/('x'*60);deep.mkdir();store=ReleaseStore(deep)
        package=self.root/'short-package'
        version=build_bundle(package,{'python/'+('a'*120)+'.py':b'bounded'},'a'*40)
        with self.assertRaisesRegex(ValueError,'WINDOWS_TARGET_PATH_TOO_LONG'):
            store.stage(package,version)
        self.assertFalse((deep/'versions').exists())
        self.assertFalse((deep/'active.json').exists())

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
    def assert_fenced(self, version, transaction):
        for action in (
            lambda: self.store.activate(version,expected_current=version),
            lambda: self.store.rollback(transaction,expected_current=version),
            lambda: self.store.delete_inactive(version),
            lambda: self.store.stage(self.root/'one',version)):
            with self.assertRaisesRegex(ValueError,'STOP_AND_PRESERVE'): action()

    def test_failed_pointer_commit_is_inspect_only_and_all_writers_fenced(self):
        version=self.package('one',{'app/a.py':b'one'})
        with patch('autonomy.release_store.os.replace',side_effect=OSError('fault')):
            with self.assertRaises(OSError):self.store.activate(version,expected_current=None)
        before={str(p):p.read_bytes() for p in (self.root/'store').rglob('*') if p.is_file()}
        result=self.store.recovery_status();item=result['pending'][0]
        self.assertEqual(item['pointer_relation'],'SOURCE_CURRENT')
        self.assertEqual(item['observed'],'UNKNOWN');self.assertFalse(result['allow_replay'])
        self.assert_fenced(version,item['transaction'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in (self.root/'store').rglob('*') if p.is_file()})

    def test_process_exit_after_real_commit_keeps_unknown_and_does_not_replay(self):
        import subprocess,sys
        version=self.package('one',{'app/a.py':b'one'})
        code="""import os,sys
from autonomy.release_store import ReleaseStore
replace=os.replace
def commit_then_die(*args):
 replace(*args)
 os._exit(23)
os.replace=commit_then_die
ReleaseStore(sys.argv[1]).activate(sys.argv[2],expected_current=None)
"""
        run=subprocess.run([sys.executable,'-B','-c',code,str(self.root/'store'),version],timeout=15)
        self.assertEqual(run.returncode,23)
        self.assertEqual(self.store.status()['version'],version)
        result=self.store.recovery_status();item=result['pending'][0]
        self.assertEqual(item['pointer_relation'],'TARGET_CURRENT')
        self.assertEqual(item['observed'],'UNKNOWN')
        self.assert_fenced(version,item['transaction'])

    def test_torn_intent_blocks_publication_without_clearing_evidence(self):
        version=self.package('one',{'app/a.py':b'one'})
        transactions=self.root/'store/transactions';transactions.mkdir()
        marker=transactions/(('a'*32)+'.pending.json');marker.write_bytes(b'{')
        status=self.store.recovery_status()
        self.assertEqual(status['pending'][0]['pointer_relation'],'UNKNOWN')
        self.assert_fenced(version,'a'*32)
        self.assertEqual(marker.read_bytes(),b'{')

    def test_namespace_paths_rejected(self):
        for name in ['../a','/root','app/CON.py','app/a.','app//a']:
            with self.assertRaises(ValueError):build_bundle(self.root/'bad',{name:b'x'},'a'*40)

if __name__=='__main__':unittest.main()
