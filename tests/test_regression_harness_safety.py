"""Fresh-worktree safety and Windows-spawn runner contracts / 隔离工作树及启动回归。"""
from contextlib import redirect_stdout
import io
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

import env_loader
import development_safety


class RegressionHarnessTests(unittest.TestCase):
    def test_runner_import_does_not_execute_suite_or_read_arguments(self):
        with patch('sys.argv', ['spawn-child-with-no-output-argument']), \
                patch('unittest.defaultTestLoader.discover') as discover, \
                redirect_stdout(io.StringIO()) as out:
            runpy.run_path(str(development_safety.ROOT/'tools'/'run_comparable_suite.py'), run_name='__mp_main__')
        discover.assert_not_called()
        self.assertEqual(out.getvalue(), '')

    def test_missing_env_allowed_only_in_marked_development_copy(self):
        with patch.object(env_loader.os.path, 'exists', return_value=False), \
                patch.object(env_loader.os.path, 'isfile', return_value=True):
            env_loader._load_env()
        self.assertEqual(env_loader.get_smtp_config()['host'], '127.0.0.1')
        self.assertEqual(env_loader.get_smtp_config()['port'], 1)

    def test_missing_env_without_development_marker_remains_fail_closed(self):
        with patch.object(env_loader.os.path, 'exists', return_value=False), \
                patch.object(env_loader.os.path, 'isfile', return_value=False), \
                self.assertRaises(FileNotFoundError):
            env_loader._load_env()


if __name__ == '__main__':
    unittest.main()
