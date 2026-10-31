"""真实Windows隔离目录测试 / Actual Windows isolated-directory contracts."""
import ctypes
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from autonomy.source_identity import SourceIdentityGuard


@unittest.skipUnless(os.name == 'nt', 'Windows handles required')
class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'stage'; self.source.mkdir()
        self.data = b'fixed-source-bytes' * 8000
        self.file = self.source / 'host.bin'; self.file.write_bytes(self.data)
        self.manifest = {'host.bin':hashlib.sha256(self.data).hexdigest()}

    def guard(self, manifest=None):
        return SourceIdentityGuard(self.source, self.manifest if manifest is None else manifest,
                                   offline_only=True)

    def test_opened_file_hash_identity_repeated_and_no_authority(self):
        with self.guard() as guard:
            first = guard.revalidate()
            self.assertEqual(first, guard.revalidate())
            self.assertEqual(first['files']['host.bin']['bytes'],len(self.data))
            self.assertEqual(first['files']['host.bin']['sha256'],self.manifest['host.bin'])
            self.assertEqual(len(first['files']['host.bin']['file_id_128']),32)
            for key in ('allow_install','allow_dispatch','production_execution',
                        'publication_integrated','acl_trust_verified'):
                self.assertFalse(first[key])
        with self.assertRaises(ValueError):guard.revalidate()
        with self.assertRaises(ValueError):guard.__enter__()

    def test_same_and_other_process_writes_deletes_and_renames_blocked(self):
        code = '''import pathlib,os,sys
p=pathlib.Path(sys.argv[1]);q=pathlib.Path(sys.argv[2]);blocked=0
for action in [lambda:p.write_bytes(b'foreign'),lambda:p.unlink(),lambda:os.rename(p,q)]:
 try:action()
 except PermissionError:blocked+=1
sys.exit(0 if blocked==3 else 9)
'''
        with self.guard() as guard:
            with self.assertRaises(PermissionError):self.file.write_bytes(b'foreign')
            with self.assertRaises(PermissionError):os.rename(self.source,self.root/'published')
            r=subprocess.run([sys.executable,'-B','-c',code,str(self.file),str(self.source/'moved')],timeout=15)
            self.assertEqual(r.returncode,0)
            guard.revalidate()
        self.file.write_bytes(b'after-close')
        os.rename(self.source,self.root/'published')

    def test_preexisting_writer_rejected_without_closing_foreign_handle(self):
        guard=self.guard()
        with self.file.open('ab') as writer:
            with self.assertRaises(OSError):guard.__enter__()
            self.assertFalse(guard._handles)
            self.assertFalse(guard._directory._handles)
            writer.write(b'foreign-still-usable')

    def test_wrong_hash_and_partial_acquisition_release_all_handles(self):
        second=self.source/'z.bin';second.write_bytes(b'second')
        manifest=dict(self.manifest,**{'z.bin':'0'*64})
        guard=self.guard(manifest)
        with self.assertRaisesRegex(ValueError,'OPEN_FILE_HASH_MISMATCH'):guard.__enter__()
        self.assertFalse(guard._handles);self.assertFalse(guard._directory._handles)
        self.file.write_bytes(b'free');second.unlink()

    def test_hardlink_and_nonfile_rejected(self):
        alias=self.root/'alias';os.link(self.file,alias)
        with self.assertRaisesRegex(ValueError,'HARDLINK_REJECTED'):
            with self.guard():pass
        alias.unlink();self.file.unlink();self.file.mkdir()
        with self.assertRaises((ValueError,OSError)):
            with self.guard():pass

    def test_changed_name_set_is_not_accepted(self):
        with self.guard() as guard:
            (self.source/'extra').write_bytes(b'not-in-manifest')
            with self.assertRaisesRegex(ValueError,'EXACT_FILE_SET_REQUIRED'):guard.revalidate()
        (self.source/'extra').unlink()

    def test_size_limits_and_invalid_manifests(self):
        for manifest in ({}, {'host.bin':True},{'HOST.bin':'0'*64,'host.bin':'0'*64},
                         {'CON.txt':'0'*64},{'host.':'0'*64},{'a:b':'0'*64}):
            with self.assertRaises(ValueError):self.guard(manifest)
        for limit in ('MAX_FILE_BYTES','MAX_TOTAL_BYTES'):
            guard=self.guard()
            with patch.object(guard,limit,1):
                with self.assertRaisesRegex(ValueError,'SIZE_LIMIT'):guard.__enter__()
            self.assertFalse(guard._handles)
        with self.assertRaises(ValueError):SourceIdentityGuard(self.source,self.manifest)

    def test_read_failure_releases_handles(self):
        guard=self.guard()
        with patch.object(guard._api,'ReadFile',return_value=0):
            ctypes.set_last_error(5)
            with self.assertRaises(OSError):guard.__enter__()
        self.assertFalse(guard._handles);self.assertFalse(guard._directory._handles)
        self.file.write_bytes(b'free')

    def test_close_failure_retains_handle_for_explicit_cleanup(self):
        guard=self.guard();guard.__enter__()
        handle=guard._handles['host.bin'];real=guard._api.CloseHandle
        def close(h):
            if h==handle:
                ctypes.set_last_error(5);return 0
            return real(h)
        try:
            with patch.object(guard._api,'CloseHandle',side_effect=close):
                with self.assertRaises(OSError):guard.close()
            self.assertEqual(guard._handles,{'host.bin':handle})
            with self.assertRaises(ValueError):guard.revalidate()
        finally:guard.close()
        self.file.write_bytes(b'free')

    def test_real_process_exit_releases_handles_without_replay(self):
        ready=self.root/'ready'
        code='''import json,pathlib,sys,time,os
from autonomy.source_identity import SourceIdentityGuard
with SourceIdentityGuard(sys.argv[1],json.loads(sys.argv[2]),offline_only=True) as g:
 g.revalidate();pathlib.Path(sys.argv[3]).write_text('ready')
 while True:time.sleep(.1)
'''
        child=subprocess.Popen([sys.executable,'-B','-c',code,str(self.source),
                                __import__('json').dumps(self.manifest),str(ready)])
        try:
            deadline=time.monotonic()+10
            while not ready.exists() and child.poll() is None and time.monotonic()<deadline:
                time.sleep(.02)
            self.assertTrue(ready.exists())
            with self.assertRaises(PermissionError):self.file.write_bytes(b'during-child')
        finally:
            if child.poll() is None:child.kill()
            child.wait(timeout=10)
        self.assertEqual(self.file.read_bytes(),self.data)
        self.file.write_bytes(b'after-exit')


if __name__ == '__main__':unittest.main()
