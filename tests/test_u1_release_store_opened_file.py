import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from autonomy import release_store


class ReleaseStoreOpenedFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_normal_content_and_limit(self):
        path=self.root/'file';path.write_bytes(b'abc')
        self.assertEqual(release_store.read_file(path,3),b'abc')
        with self.assertRaisesRegex(ValueError,'FILE_TOO_LARGE'):
            release_store.read_file(path,2)

    def test_replacement_with_hardlink_between_path_check_and_open(self):
        path=self.root/'source';path.write_bytes(b'safe')
        target=self.root/'target';target.write_bytes(b'other')
        replacement=self.root/'replacement'
        try: os.link(target,replacement)
        except OSError as e: self.skipTest(f'hardlink creation unavailable: {e}')
        original=release_store.ordinary
        def race(value):
            checked=original(value)
            os.replace(replacement,path)
            return checked
        with mock.patch.object(release_store,'ordinary',side_effect=race):
            with self.assertRaisesRegex(ValueError,'HARDLINK_REJECTED'):
                release_store.read_file(path)

    def test_final_symlink_replacement_after_path_check(self):
        path=self.root/'source';path.write_bytes(b'safe')
        target=self.root/'target';target.write_bytes(b'other')
        replacement=self.root/'replacement'
        try: os.symlink(target,replacement)
        except OSError as e: self.skipTest(f'symlink creation unavailable: {e}')
        original=release_store.ordinary
        def race(value):
            checked=original(value)
            os.replace(replacement,path)
            return checked
        with mock.patch.object(release_store,'ordinary',side_effect=race):
            with self.assertRaises((ValueError,OSError)):
                release_store.read_file(path)
