"""持有源句柄发布失败合同 / Held-source publication failure contracts."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomy.source_publication import attempt_source_publication_offline, _HeldSource, _rename_handle
from test_first_publication import MANIFEST


@unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem required')
class SourcePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'staged';self.source.mkdir()
        (self.source/'host.bin').write_bytes(b'candidate')
        self.target=self.root/'published'

    def attempt(self):
        return attempt_source_publication_offline(self.source,self.target,MANIFEST,offline_only=True)

    def test_actual_child_handle_sharing_blocks_rename_and_preserves_bytes(self):
        # This is a required blocker on the currently tested Windows filesystem,
        # not a simulated successful publication or a production capability claim.
        with patch('autonomy.source_publication._rename_handle',wraps=_rename_handle) as rename:
            with self.assertRaises(PermissionError) as caught:self.attempt()
            self.assertEqual(caught.exception.winerror,5)
            self.assertEqual(rename.call_count,1)
        self.assertEqual((self.source/'host.bin').read_bytes(),b'candidate')
        self.assertFalse(self.target.exists())
        # Handles are closed on the failed attempt, but no automatic retry occurred.
        (self.source/'host.bin').write_bytes(b'after-inspection')

    def test_source_directory_identity_and_files_remain_held_during_attempt(self):
        with _HeldSource(self.source,MANIFEST,offline_only=True) as guard:
            before=guard.revalidate()
            with self.assertRaises(PermissionError):os.rename(self.source,self.root/'foreign')
            with self.assertRaises(PermissionError):_rename_handle(guard,self.target)
            self.assertEqual(guard.revalidate(),before)
            with self.assertRaises(PermissionError):(self.source/'host.bin').unlink()

    def test_existing_empty_or_nonempty_target_preserved(self):
        for nonempty in (False,True):
            with self.subTest(nonempty=nonempty):
                self.target.mkdir()
                if nonempty:(self.target/'foreign').write_bytes(b'foreign')
                with patch('autonomy.source_publication._rename_handle') as rename:
                    with self.assertRaises(FileExistsError):self.attempt()
                    rename.assert_not_called()
                self.assertTrue(self.target.is_dir())
                if nonempty:
                    self.assertEqual((self.target/'foreign').read_bytes(),b'foreign')
                    (self.target/'foreign').unlink()
                self.target.rmdir()

    def test_competing_target_after_precheck_is_preserved(self):
        def race(guard,target):
            target.mkdir();_rename_handle(guard,target)
        with patch('autonomy.source_publication._rename_handle',side_effect=race):
            with self.assertRaises(OSError):self.attempt()
        self.assertTrue(self.target.is_dir())
        self.assertEqual((self.source/'host.bin').read_bytes(),b'candidate')

    def test_hash_failure_never_reaches_rename(self):
        (self.source/'host.bin').write_bytes(b'wrong')
        with patch('autonomy.source_publication._rename_handle') as rename:
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):self.attempt()
            rename.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_invalid_scope_does_not_acquire_source_or_rename(self):
        for target,offline in [(self.target,False),(self.source,True),
                               (self.root.parent/'outside',True),(self.root/'CON.txt',True),
                               (self.root/'trailing.',True)]:
            with patch('autonomy.source_publication._HeldSource') as guard:
                with self.assertRaises(ValueError):
                    attempt_source_publication_offline(self.source,target,MANIFEST,offline_only=offline)
                guard.assert_not_called()

    def test_journal_driver_keeps_publish_unknown_and_rejects_same_operation(self):
        from autonomy.install_contract import exercise_install_contract
        from autonomy.install_journal import inspect_install
        from test_install_contract import RecordingAdapter
        class Adapter(RecordingAdapter):
            def apply(adapter,step,binding):
                super().apply(step,binding)
                if step=='PUBLISH':
                    attempt_source_publication_offline(self.source,self.target,MANIFEST,offline_only=True)
        with self.assertRaises(PermissionError):
            exercise_install_contract(self.root,'op','a'*64,'b'*64,Adapter(self.root),lambda:True)
        observed=inspect_install(self.root/'op.jsonl')
        self.assertEqual(observed['completed_steps'],1)
        self.assertEqual(observed['pending_step'],'PUBLISH')
        self.assertEqual(observed['observed'],'UNKNOWN')
        self.assertFalse(observed['allow_replay']);self.assertFalse(observed['allow_install'])
        adapter=Adapter(self.root)
        with self.assertRaises(FileExistsError):
            exercise_install_contract(self.root,'op','a'*64,'b'*64,adapter,lambda:True)
        self.assertEqual(adapter.calls,[])
        self.assertEqual((self.source/'host.bin').read_bytes(),b'candidate')


if __name__=='__main__':unittest.main()
