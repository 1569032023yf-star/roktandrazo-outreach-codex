"""隔离共享模式实验，非发布适配器 / Isolated sharing experiment, not an installer.

Only this test harness shares child deletion. Production guards stay unchanged.
仅测试夹具改变子文件共享删除；生产原语不变，不授权安装。
"""
import os
from pathlib import Path
import tempfile
import unittest

from autonomy.source_publication import _HeldSource, _rename_handle, _verify_named_objects
from test_first_publication import MANIFEST


class _ReadDeleteSharing:
    def __init__(self, api):
        self.api = api

    def __getattr__(self, name):
        return getattr(self.api, name)

    def CreateFileW(self, path, access, share, security, disposition, flags, template):
        if access == 0x80000000 and share == 1:
            share = 5  # Experimental READ|DELETE; never applied to real adapter.
        return self.api.CreateFileW(path, access, share, security, disposition, flags, template)


class _ExperimentalSource(_HeldSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._api = _ReadDeleteSharing(self._api)


@unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem required')
class SourceBindingExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'staged'
        self.source.mkdir()
        (self.source / 'host.bin').write_bytes(b'candidate')
        self.target = self.root / 'published'

    def guard(self):
        return _ExperimentalSource(self.source, MANIFEST, offline_only=True)

    def test_read_delete_sharing_still_blocks_directory_rename(self):
        with self.guard() as guard:
            before = guard.revalidate()
            with self.assertRaises(PermissionError) as caught:
                _rename_handle(guard, self.target)
            self.assertEqual(caught.exception.winerror, 5)
            self.assertEqual(guard.revalidate(), before)
            _verify_named_objects(guard, before)
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())
            self.assertFalse(before['allow_install'])

    def test_equal_bytes_replacement_evades_held_hash_but_not_named_id(self):
        with self.guard() as guard:
            before = guard.revalidate()
            leaf = self.source / 'host.bin'
            os.rename(leaf, self.root / 'retained-original')
            leaf.write_bytes(b'candidate')
            # Same names + retained object hash are insufficient for namespace trust.
            self.assertEqual(guard.revalidate(), before)
            with self.assertRaisesRegex(ValueError, 'DESTINATION_IDENTITY_MISMATCH'):
                _verify_named_objects(guard, before)
            self.assertEqual((self.root / 'retained-original').read_bytes(), b'candidate')

    def test_write_is_still_blocked_but_child_rename_is_possible(self):
        with self.guard() as guard:
            with self.assertRaises(PermissionError):
                (self.source / 'host.bin').write_bytes(b'foreign')
            os.rename(self.source / 'host.bin', self.root / 'moved')
            with self.assertRaisesRegex(ValueError, 'EXACT_FILE_SET_REQUIRED'):
                guard.revalidate()
            self.assertEqual((self.root / 'moved').read_bytes(), b'candidate')

    def test_competing_target_is_not_overwritten(self):
        with self.guard() as guard:
            self.target.mkdir()
            (self.target / 'foreign').write_bytes(b'foreign')
            with self.assertRaises(OSError):
                _rename_handle(guard, self.target)
            self.assertEqual((self.target / 'foreign').read_bytes(), b'foreign')
            self.assertEqual((self.source / 'host.bin').read_bytes(), b'candidate')


if __name__ == '__main__':
    unittest.main()
