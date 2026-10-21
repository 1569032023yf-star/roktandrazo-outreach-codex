"""Mock-only admission tests / 纯模拟准入测试，不触碰真实磁盘。"""
import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from autonomy import storage_preflight as s


class StoragePreflightTests(unittest.TestCase):
    def setUp(self):
        self.paths = [Path.cwd() / name for name in ('runtime-target', 'root-target', 'temp-target')]
        self.stat_patch = patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFDIR))
        self.stat_patch.start()
        self.addCleanup(self.stat_patch.stop)
        self.resolve_patch = patch.object(Path, 'resolve', autospec=True, side_effect=lambda p, **kw: p)
        self.resolve_patch.start()
        self.addCleanup(self.resolve_patch.stop)

    def call(self, **kwargs):
        return s.check_storage(*self.paths, **kwargs)

    def test_equal_threshold_all_three_paths_pass(self):
        with patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=272*s.MIB)) as usage:
            result = self.call()
        self.assertTrue(result['allow_start'])
        self.assertFalse(result['space_reserved'])
        self.assertEqual(usage.call_count, 3)
        self.assertEqual([x['target'] for x in result['checks']], ['runtime', 'root', 'temp'])

    def test_each_target_low_space_blocks_and_preserves_all_evidence(self):
        for low_index in range(3):
            with self.subTest(low_index=low_index):
                values = [SimpleNamespace(free=272*s.MIB) for _ in range(3)]
                values[low_index] = SimpleNamespace(free=272*s.MIB-1)
                with patch.object(s.shutil, 'disk_usage', side_effect=values):
                    result = self.call()
                self.assertFalse(result['allow_start'])
                self.assertEqual(result['checks'][low_index]['status'], 'LOW_SPACE')
                self.assertEqual(len(result['checks']), 3)

    def test_each_target_permission_error_does_not_skip_other_checks(self):
        for index in range(3):
            values = [SimpleNamespace(free=300*s.MIB) for _ in range(3)]
            values[index] = PermissionError('not included in evidence')
            with patch.object(s.shutil, 'disk_usage', side_effect=values) as usage:
                result = self.call()
            self.assertFalse(result['allow_start'])
            self.assertEqual(usage.call_count, 3)
            self.assertEqual(result['checks'][index]['error_type'], 'PermissionError')
            self.assertEqual(result['checks'][index]['status'], 'UNKNOWN')
            self.assertNotIn('not included', repr(result))

    def test_nearest_existing_ancestor_is_checked(self):
        leaf = self.paths[0] / 'missing' / 'child'
        def mocked_stat(path):
            if path in (leaf, leaf.parent):
                raise FileNotFoundError()
            return SimpleNamespace(st_mode=stat.S_IFDIR)
        with patch.object(Path, 'stat', new=mocked_stat), \
             patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=300*s.MIB)) as usage:
            result = s.check_storage(leaf, *self.paths[1:])
        self.assertTrue(result['allow_start'])
        self.assertEqual(result['checks'][0]['checked_path'], str(self.paths[0]))
        self.assertEqual(usage.call_args_list[0].args[0], self.paths[0])

    def test_stat_permission_error_is_not_treated_as_missing(self):
        with patch.object(Path, 'stat', side_effect=PermissionError()), \
             patch.object(s.shutil, 'disk_usage') as usage:
            result = self.call()
        self.assertFalse(result['allow_start'])
        usage.assert_not_called()
        self.assertTrue(all(x['error_type'] == 'PermissionError' for x in result['checks']))

    def test_file_is_not_a_directory_target(self):
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG)), \
             patch.object(s.shutil, 'disk_usage') as usage:
            result = self.call()
        usage.assert_not_called()
        self.assertTrue(all(x['error_type'] == 'NotADirectoryError' for x in result['checks']))

    def test_invalid_thresholds_fail_before_any_checks(self):
        for key in ('min_free_bytes', 'commit_reserve_bytes'):
            for value in (0, -1, True, 1.5, None, '256'):
                with self.subTest(key=key, value=value), patch.object(s.shutil, 'disk_usage') as usage:
                    with self.assertRaises(ValueError):
                        self.call(**{key: value})
                    usage.assert_not_called()

    def test_positive_custom_thresholds_are_added(self):
        with patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=7)):
            result = self.call(min_free_bytes=3, commit_reserve_bytes=4)
        self.assertTrue(result['allow_start'])
        self.assertEqual(result['required_free_bytes'], 7)

    def test_default_temp_failure_is_unknown(self):
        with patch.object(s.tempfile, 'gettempdir', side_effect=OSError()), \
             patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=300*s.MIB)):
            result = s.check_storage(*self.paths[:2])
        self.assertFalse(result['allow_start'])
        self.assertEqual(result['checks'][2]['status'], 'UNKNOWN')

    def test_default_temp_directory_is_checked(self):
        with patch.object(s.tempfile, 'gettempdir', return_value=str(self.paths[2])), \
             patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=300*s.MIB)):
            result = s.check_storage(*self.paths[:2])
        self.assertTrue(result['allow_start'])
        self.assertEqual(result['checks'][2]['checked_path'], str(self.paths[2]))

    def test_invalid_disk_result_fails_closed(self):
        for value in (None, -1, True, float('inf')):
            with patch.object(s.shutil, 'disk_usage', return_value=SimpleNamespace(free=value)):
                result = self.call()
            self.assertFalse(result['allow_start'])
            self.assertTrue(all(x['status'] == 'UNKNOWN' for x in result['checks']))


if __name__ == '__main__':
    unittest.main()
