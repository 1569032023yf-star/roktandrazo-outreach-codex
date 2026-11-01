"""命名空间检查故障合同 / Namespace revalidation fault contracts."""
import ctypes
import os
import unittest
from unittest.mock import patch

import test_source_binding_experiment as experiment


@unittest.skipUnless(os.name == 'nt', 'Actual Windows filesystem required')
class NamespaceRevalidationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = experiment.SourceBindingExperimentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def replace(self):
        f = self.fixture
        os.rename(f.source / 'host.bin', f.root / 'original')
        (f.source / 'host.bin').write_bytes(b'candidate')

    def test_replacement_during_hash_is_rejected_by_second_named_check(self):
        with self.fixture.guard() as guard:
            real = guard._hash
            def hash_then_replace(handle, size):
                result = real(handle, size)
                self.replace()
                return result
            with patch.object(guard, '_hash', side_effect=hash_then_replace):
                with self.assertRaisesRegex(ValueError, 'NAMED_SOURCE_IDENTITY_MISMATCH'):
                    guard.revalidate()

    def test_replacement_after_return_is_not_claimed_immutable(self):
        with self.fixture.guard() as guard:
            snapshot = guard.revalidate()
            self.assertFalse(snapshot['namespace_immutable_verified'])
            self.assertFalse(snapshot['allow_install'])
            self.replace()
            with self.assertRaisesRegex(ValueError, 'NAMED_SOURCE_IDENTITY_MISMATCH'):
                guard.revalidate()
            # The prior snapshot is not revoked or a future lock guarantee.
            self.assertFalse(snapshot['namespace_immutable_verified'])

    def test_named_close_failure_is_retained_and_guard_cannot_be_reused(self):
        guard = self.fixture.guard()
        guard.__enter__()
        held = set(guard._handles.values()) | set(guard._directory._handles)
        real = guard._api.CloseHandle
        def close(handle):
            if handle not in held:
                ctypes.set_last_error(5)
                return 0
            return real(handle)
        try:
            with patch.object(guard._api, 'CloseHandle', side_effect=close):
                with self.assertRaises(OSError):
                    guard.revalidate()
            self.assertIn('__named_host.bin', guard._handles)
            with self.assertRaisesRegex(ValueError, 'NO_ACTIVE_SOURCE_HANDLES'):
                guard.revalidate()
        finally:
            guard.close()
        self.assertFalse(guard._handles)


if __name__ == '__main__':
    unittest.main()
