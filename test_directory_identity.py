import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from autonomy.directory_identity import DirectoryIdentityGuard
from autonomy.first_publication import publish_first_directory_offline
from test_first_publication import MANIFEST


@unittest.skipUnless(os.name == 'nt', 'Windows handles required')
class DirectoryIdentityTests(unittest.TestCase):
    def test_real_directory_rename_blocked_until_handles_close(self):
        with tempfile.TemporaryDirectory() as root:
            original = Path(root) / 'parent'; original.mkdir()
            renamed = Path(root) / 'renamed'
            guard = DirectoryIdentityGuard(original, offline_only=True)
            with guard:
                before = guard.revalidate()
                self.assertEqual(len(before['file_id_128']), 32)
                with self.assertRaises(PermissionError): os.rename(original, renamed)
                self.assertEqual(guard.revalidate(), before)
                # No content/ACL freeze is claimed: children remain writable.
                (original / 'child').write_bytes(b'allowed-in-sandbox')
            with self.assertRaises(ValueError): guard.revalidate()
            os.rename(original, renamed)
            self.assertTrue(renamed.exists())

    def test_other_process_cannot_replace_bound_parent(self):
        code = '''import os,sys
try: os.rename(sys.argv[1],sys.argv[2])
except PermissionError: sys.exit(0)
sys.exit(7)
'''
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / 'parent'; parent.mkdir()
            with DirectoryIdentityGuard(parent, offline_only=True):
                result = subprocess.run([sys.executable, '-B', '-c', code,
                    str(parent), str(Path(root) / 'foreign')], timeout=20)
                self.assertEqual(result.returncode, 0)
            self.assertTrue(parent.exists())

    def test_failed_open_releases_already_acquired_ancestors(self):
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / 'parent'; parent.mkdir()
            guard = DirectoryIdentityGuard(parent / 'missing', offline_only=True)
            with self.assertRaises(OSError): guard.__enter__()
            self.assertEqual(guard._handles, [])
            os.rename(parent, Path(root) / 'renamed')

    def test_reparse_or_information_failure_closes_handles(self):
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / 'parent'; parent.mkdir()
            guard = DirectoryIdentityGuard(parent, offline_only=True)
            with patch.object(guard, '_identity', side_effect=ValueError('REPARSE')):
                with self.assertRaises(ValueError): guard.__enter__()
            self.assertEqual(guard._handles, [])
            os.rename(parent, Path(root) / 'renamed')

    def test_parent_is_held_at_publication_boundary_and_released_after_failure(self):
        with tempfile.TemporaryDirectory() as root:
            parent = Path(root) / 'parent'; parent.mkdir()
            staged = parent / 'staged'; staged.mkdir()
            (staged / 'host.bin').write_bytes(b'candidate')
            target = parent / 'published'

            # Patch the underlying function only for the publish call. Use the
            # unpatched primitive for the competing parent rename.
            real_rename = os.rename

            def interrupted(src, dst):
                with self.assertRaises(PermissionError):
                    real_rename(parent, Path(root) / 'foreign')
                raise OSError('BEFORE_RENAME_EFFECT')

            with patch('autonomy.first_publication.os.rename', side_effect=interrupted):
                with self.assertRaises(OSError):
                    publish_first_directory_offline(staged, target, MANIFEST, offline_only=True)
            self.assertTrue(staged.exists()); self.assertFalse(target.exists())
            real_rename(parent, Path(root) / 'released')

    def test_offline_scope_and_device_or_relative_paths_rejected(self):
        for path in ('relative', r'\\server\share\path', r'\\?\C:\path', r'C:\parent\..\other', r'C:\parent\bad.'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                DirectoryIdentityGuard(path, offline_only=True)
        with self.assertRaises(ValueError): DirectoryIdentityGuard('C:\\', offline_only=1)


if __name__ == '__main__': unittest.main()
