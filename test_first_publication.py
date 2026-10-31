import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from autonomy.first_publication import publish_first_directory_offline

MANIFEST = {'host.bin': hashlib.sha256(b'candidate').hexdigest()}


@unittest.skipUnless(os.name == 'nt', 'Windows no-replace rename contract')
class FirstPublicationTests(unittest.TestCase):
    def prepare(self, root, name='staged'):
        path = Path(root) / name; path.mkdir()
        (path / 'host.bin').write_bytes(b'candidate')
        return path

    def publish(self, source, target):
        return publish_first_directory_offline(source, target, MANIFEST, offline_only=True)

    def test_actual_rename_and_existing_empty_target_not_replaced(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.prepare(root); target = Path(root) / 'published'
            result = self.publish(source, target)
            self.assertFalse(source.exists())
            self.assertEqual((target / 'host.bin').read_bytes(), b'candidate')
            self.assertFalse(result['allow_install'])
        with tempfile.TemporaryDirectory() as root:
            source = self.prepare(root); target = Path(root) / 'published'; target.mkdir()
            with self.assertRaises(FileExistsError): self.publish(source, target)
            self.assertTrue(source.exists()); self.assertEqual(list(target.iterdir()), [])

    def test_competing_target_created_at_rename_is_preserved(self):
        real_rename = os.rename
        with tempfile.TemporaryDirectory() as root:
            source = self.prepare(root); target = Path(root) / 'published'

            def competitor(src, dst):
                target.mkdir()
                return real_rename(src, dst)

            with patch('autonomy.first_publication.os.rename', side_effect=competitor):
                with self.assertRaises(OSError): self.publish(source, target)
            self.assertTrue(source.exists()); self.assertEqual(list(target.iterdir()), [])

    def test_exact_files_hashes_and_no_subdirectories(self):
        for mode in ('extra', 'changed', 'directory'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                source = self.prepare(root); target = Path(root) / 'published'
                if mode == 'extra': (source / 'extra').write_bytes(b'x')
                elif mode == 'changed': (source / 'host.bin').write_bytes(b'wrong')
                else:
                    (source / 'host.bin').unlink(); (source / 'host.bin').mkdir()
                with self.assertRaises(ValueError): self.publish(source, target)
                self.assertTrue(source.exists()); self.assertFalse(target.exists())

    def test_readback_mismatch_preserves_published_tree(self):
        real_rename = os.rename
        with tempfile.TemporaryDirectory() as root:
            source = self.prepare(root); target = Path(root) / 'published'

            def changed(src, dst):
                real_rename(src, dst)
                (target / 'host.bin').write_bytes(b'changed-after-rename')

            with patch('autonomy.first_publication.os.rename', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'FILE_HASH'): self.publish(source, target)
            self.assertTrue(target.exists()); self.assertFalse(source.exists())

    def test_crash_after_real_rename_requires_status_not_replay(self):
        code = '''import os,sys
from autonomy.first_publication import publish_first_directory_offline
from test_first_publication import MANIFEST
publish_first_directory_offline(sys.argv[1],sys.argv[2],MANIFEST,offline_only=True)
os._exit(23)
'''
        with tempfile.TemporaryDirectory() as root:
            source = self.prepare(root); target = Path(root) / 'published'
            child = subprocess.run([sys.executable, '-B', '-c', code, str(source), str(target)], timeout=20)
            self.assertEqual(child.returncode, 23)
            self.assertEqual((target / 'host.bin').read_bytes(), b'candidate')
            with self.assertRaises(FileExistsError): self.publish(source, target)

    def test_hardlinks_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            source = self.prepare(root); target = Path(root) / 'published'
            os.link(source / 'host.bin', Path(root) / 'alias')
            with self.assertRaisesRegex(ValueError, 'HARDLINK'): self.publish(source, target)
            with self.assertRaises(ValueError): self.publish(source, Path(root).parent / 'outside')
            with self.assertRaises(ValueError):
                publish_first_directory_offline(source, target, {'../bad': 'a'*64}, offline_only=True)

    def test_driver_journal_retains_pending_publish_after_rename_crash(self):
        from autonomy.install_journal import inspect_install
        from autonomy.install_contract import exercise_install_contract
        from test_install_contract import RecordingAdapter
        code = '''import os,sys
from pathlib import Path
from test_install_contract import RecordingAdapter
from test_first_publication import MANIFEST
from autonomy.first_publication import publish_first_directory_offline
from autonomy.install_contract import exercise_install_contract
class PublicationAdapter(RecordingAdapter):
 def apply(self,step,binding):
  super().apply(step,binding)
  if step=='PUBLISH':
   publish_first_directory_offline(self.root/'staged',self.root/'published',MANIFEST,offline_only=True)
 def readback(self,step,binding):
  if step=='PUBLISH': os._exit(29)
  return super().readback(step,binding)
exercise_install_contract(sys.argv[1],'op','a'*64,'b'*64,PublicationAdapter(sys.argv[1]),lambda:True)
'''
        with tempfile.TemporaryDirectory() as root:
            self.prepare(root)
            child = subprocess.run([sys.executable, '-B', '-c', code, root], timeout=20)
            self.assertEqual(child.returncode, 29)
            observed = inspect_install(Path(root) / 'op.jsonl')
            self.assertEqual(observed['completed_steps'], 1)
            self.assertEqual(observed['pending_step'], 'PUBLISH')
            self.assertEqual(observed['observed'], 'UNKNOWN')
            self.assertEqual((Path(root) / 'published' / 'host.bin').read_bytes(), b'candidate')
            adapter = RecordingAdapter(root)
            with self.assertRaises(FileExistsError):
                exercise_install_contract(root, 'op', 'a'*64, 'b'*64, adapter, lambda: True)
            self.assertEqual(adapter.calls, [])


if __name__ == '__main__': unittest.main()
