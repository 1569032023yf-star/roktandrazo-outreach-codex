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

    def test_parent_symlink_replaced_after_path_check(self):
        parent=self.root/'parent';parent.mkdir();(parent/'source').write_bytes(b'safe')
        evil=self.root/'evil';evil.mkdir();(evil/'source').write_bytes(b'other')
        probe=self.root/'probe'
        try: os.symlink(evil,probe,target_is_directory=True)
        except OSError as e: self.skipTest(f'directory symlink unavailable: {e}')
        probe.unlink()
        original=release_store.ordinary
        def race(value):
            checked=original(value)
            parent.rename(self.root/'saved')
            os.symlink(evil,parent,target_is_directory=True)
            return checked
        try:
            with mock.patch.object(release_store,'ordinary',side_effect=race):
                with self.assertRaises((ValueError,OSError)):
                    release_store.read_file(parent/'source')
        finally:
            if parent.is_symlink(): parent.unlink()

    @unittest.skipIf(os.name == 'nt', 'FIFO requires POSIX')
    def test_fifo_is_rejected_without_blocking(self):
        import subprocess,sys
        fifo=self.root/'fifo';os.mkfifo(fifo)
        result=subprocess.run([sys.executable,'-c',
            'from autonomy.release_store import read_file;import sys;read_file(sys.argv[1])',str(fifo)],
            capture_output=True,timeout=3)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'ORDINARY_FILE_REQUIRED',result.stderr)

    def test_rollback_tool_runs_in_isolated_python_without_publisher_package(self):
        import json,shutil,subprocess,sys
        tool=self.root/'release_store.py'
        shutil.copy2(Path(release_store.__file__),tool)
        store=self.root/'store';store.mkdir()
        (store/'active.json').write_text(json.dumps(dict(schema=release_store.SCHEMA,
            inventory_id=release_store.INVENTORY,version=None)))
        result=subprocess.run([sys.executable,'-I',str(tool),'--root',str(store),'status'],
            cwd=str(self.root),capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIsNone(json.loads(result.stdout)['version'])
