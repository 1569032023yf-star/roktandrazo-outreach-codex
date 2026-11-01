"""失败后单向停用 / Irreversible invalidation after failed source observation."""
import os
import unittest
from unittest.mock import patch

import test_source_binding_experiment as experiment


@unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem required')
class SourceGuardInvalidationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = experiment.SourceBindingExperimentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def assert_inactive(self, guard):
        with self.assertRaisesRegex(ValueError, 'NO_ACTIVE_SOURCE_HANDLES'):
            guard.revalidate()
        with self.assertRaisesRegex(ValueError, 'GUARD_SINGLE_USE'):
            guard.__enter__()

    def test_restored_original_object_does_not_reactivate_failed_context(self):
        f = self.fixture
        with f.guard() as guard:
            leaf = f.source / 'host.bin'
            moved = f.root / 'original'
            os.rename(leaf, moved)
            leaf.write_bytes(b'candidate')
            with self.assertRaisesRegex(ValueError, 'NAMED_SOURCE_IDENTITY_MISMATCH'):
                guard.revalidate()
            leaf.unlink()
            os.rename(moved, leaf)
            self.assert_inactive(guard)
            self.assertTrue(guard._handles)
        self.assertFalse(guard._handles)
        # A new offline context may inspect; no journal/operation is retried.
        with f.guard() as fresh:
            self.assertFalse(fresh.revalidate()['allow_install'])

    def test_removed_extra_name_does_not_reactivate_context(self):
        f = self.fixture
        with f.guard() as guard:
            extra = f.source / 'extra'
            extra.write_bytes(b'foreign')
            with self.assertRaisesRegex(ValueError, 'EXACT_FILE_SET_REQUIRED'):
                guard.revalidate()
            extra.unlink()
            self.assert_inactive(guard)

    def test_read_error_preserves_original_exception_and_retained_handles(self):
        with self.fixture.guard() as guard:
            held = dict(guard._handles)
            error = OSError('INJECTED_READ_FAILURE')
            with patch.object(guard, '_hash', side_effect=error):
                with self.assertRaises(OSError) as caught:
                    guard.revalidate()
            self.assertIs(caught.exception, error)
            self.assertEqual(guard._handles, held)
            self.assert_inactive(guard)

    def test_interrupt_invalidates_without_automatic_close_or_retry(self):
        with self.fixture.guard() as guard:
            with patch.object(guard, '_hash', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    guard.revalidate()
            self.assertTrue(guard._handles)
            self.assert_inactive(guard)
        self.assertFalse(guard._handles)


if __name__ == '__main__':
    unittest.main()
