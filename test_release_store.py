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

    def test_bounded_reads_preserve_exact_size_and_reject_oversize(self):
        from autonomy.release_store import read_file
        path=self.root/'bounded.bin'
        for size in (0,1,65535,65536,65537,131073):
            with self.subTest(size=size):
                data=bytes((n%251 for n in range(size)));path.write_bytes(data)
                self.assertEqual(read_file(path,size),data)
                if size:
                    with self.assertRaisesRegex(ValueError,'FILE_TOO_LARGE'):
                        read_file(path,size-1)

    def test_large_limit_does_not_request_a_large_buffer(self):
        from autonomy.release_store import read_file,MAX_FILE
        path=self.root/'small.bin';path.write_bytes(b'small fixture')
        original=Path.open;requests=[]
        class Reader:
            def __init__(self, inner):self.inner=inner
            def __enter__(self):self.inner.__enter__();return self
            def __exit__(self,*args):return self.inner.__exit__(*args)
            def read(self,size):requests.append(size);return self.inner.read(size)
            def fileno(self):return self.inner.fileno()
            def seek(self,offset):return self.inner.seek(offset)
        def monitored_open(p,*args,**kwargs):
            return Reader(original(p,*args,**kwargs))
        with patch.object(Path,'open',monitored_open):
            self.assertEqual(read_file(path,MAX_FILE),b'small fixture')
        self.assertTrue(requests)
        self.assertLessEqual(max(requests),65536)

    def test_read_file_handles_growth_shrink_and_bounded_retry(self):
        from autonomy.release_store import read_file
        path=self.root/'changing.bin';original=Path.open
        def run_change(initial, changes, limit):
            path.write_bytes(initial);requests=[]
            class Reader:
                def __init__(self, inner):self.inner=inner
                def __enter__(self):self.inner.__enter__();return self
                def __exit__(self,*args):return self.inner.__exit__(*args)
                def fileno(self):return self.inner.fileno()
                def seek(self,offset):return self.inner.seek(offset)
                def read(self,size):
                    requests.append(size)
                    change = changes[len(requests)-1] if len(requests)<=len(changes) else None
                    after = isinstance(change,tuple)
                    if after: change = change[0]
                    if change is not None and not after:
                        # Modify after sizing the open handle but before its read.
                        with original(path,'wb') as writer:writer.write(change)
                    data=self.inner.read(size)
                    if change is not None and after:
                        # Growth after EOF but before the post-read size check.
                        with original(path,'wb') as writer:writer.write(change)
                    return data
            def monitored_open(p,*args,**kwargs):return Reader(original(p,*args,**kwargs))
            with patch.object(Path,'open',monitored_open):
                try:return read_file(path,limit),requests
                finally:self.assertTrue(all(n<=limit+1 for n in requests))
        self.assertEqual(run_change(b'abcd',[b'abcdef'],8)[0],b'abcdef')
        self.assertEqual(run_change(b'abcd',[(b'abcdef',)],8)[0],b'abcdef')
        self.assertEqual(run_change(b'abcd',[b'ab'],8)[0],b'ab')
        with self.assertRaisesRegex(ValueError,'FILE_TOO_LARGE'):
            run_change(b'abcd',[b'abcdefg'],6)
        with self.assertRaisesRegex(ValueError,'FILE_CHANGED_DURING_READ'):
            run_change(b'a',[b'ab',b'abc',b'abcd'],8)
    @unittest.skipUnless(__import__('os').name=='nt','Windows path contract')
    def test_final_sha_layout_rejected_before_staging(self):
        deep=self.root/('x'*60);deep.mkdir();store=ReleaseStore(deep)
        package=self.root/'short-package'
        version=build_bundle(package,{'python/'+('a'*120)+'.py':b'bounded'},'a'*40)
        with self.assertRaisesRegex(ValueError,'WINDOWS_TARGET_PATH_TOO_LONG'):
            store.stage(package,version)
        self.assertFalse((deep/'versions').exists())
        self.assertFalse((deep/'active.json').exists())

    def test_ordinary_rejects_dangling_link_and_inaccessible_inspection(self):
        from autonomy.release_store import ordinary
        link=self.root/'dangling'
        import os,subprocess
        if os.name=='nt':
            target=self.root/'missing';target.mkdir()
            subprocess.run(['cmd.exe','/c','mklink','/J',str(link),str(target)],check=True,capture_output=True)
            target.rmdir()
        else:
            link.symlink_to(self.root/'missing',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'REPARSE_PATH'):
            ordinary(link/'child')
        with patch.object(Path,'lstat',side_effect=PermissionError('inspection denied')):
            with self.assertRaises(PermissionError):ordinary(self.root/'new')
        self.assertEqual(ordinary(self.root/'new'/'child'),self.root/'new'/'child')

    def test_direct_archive_matches_manifest_and_preserves_failed_output(self):
        import zipfile,json
        from autonomy.release_store import build_archive_from_paths,sha,read_file
        source=self.root/'input';source.write_bytes(b'actual payload')
        output=self.root/'install.zip'
        digest=build_archive_from_paths(output,{'app/a.py':source},'a'*40)
        with zipfile.ZipFile(output) as z:
            raw=z.read('manifest.json');self.assertEqual(sha(raw),digest)
            self.assertEqual(z.read('payload/app/a.py'),b'actual payload')
            self.assertEqual(json.loads(raw)['files']['app/a.py'],sha(b'actual payload'))
        with self.assertRaises(FileExistsError):
            build_archive_from_paths(output,{'app/a.py':source},'a'*40)
        failed=self.root/'changed.zip';calls=0
        def changing(path):
            nonlocal calls
            calls+=1
            return b'first' if calls==1 else b'changed'
        with patch('autonomy.release_store.read_file',side_effect=changing):
            with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):
                build_archive_from_paths(failed,{'app/a.py':source},'a'*40)
        self.assertTrue(failed.exists())

    def test_large_file_read_buffers_are_released_between_files_and_passes(self):
        from autonomy.release_store import build_bundle_from_paths, build_archive_from_paths, read_file
        first=self.root/'first';second=self.root/'second'
        first.write_bytes(b'first payload');second.write_bytes(b'second payload')
        sources={'a':first,'b':second};live=[]
        class Tracked(bytes):
            def __new__(cls, value):
                result=super().__new__(cls,value);live.append(id(result));return result
            def __del__(self):live.remove(id(self))
        def tracked(path, limit=256*1024*1024):
            value=read_file(path,limit)
            if value in (b'first payload',b'second payload'):
                self.assertFalse(live,'previous payload still held while reading next')
                return Tracked(value)
            return value
        with patch('autonomy.release_store.read_file',side_effect=tracked):
            folder=self.root/'bundle';version=build_bundle_from_paths(folder,sources,'a'*40)
            self.assertFalse(live)
            build_archive_from_paths(self.root/'bundle.zip',sources,'a'*40)
            self.assertFalse(live)
            self.store._verify(folder,version)
            self.assertFalse(live)
            (folder/'payload/a').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'ARTIFACT_MISMATCH'):
                self.store._verify(folder,version)

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
