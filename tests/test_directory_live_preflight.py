"""Live entrypoint policy checks; no real transport in these tests."""
import io
import json
import os
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.run_brand_capture import main


class DirectoryLivePreflightTests(unittest.TestCase):
    def blocked(self, environment, expected):
        with patch.dict(os.environ, environment, clear=False), \
                patch('scripts.run_brand_capture.PublicPageFetcher', side_effect=AssertionError('transport constructed')), \
                patch('scripts.run_brand_capture.load_catalog', side_effect=AssertionError('catalog read')), \
                redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(['--mode', 'capture-public', '--catalog', 'missing.json'], directory=True), 2)
        outcome = json.loads(error.getvalue())
        self.assertEqual(outcome['status'], expected)
        self.assertEqual(outcome['requests_made'], 0)

    def test_development_transport_default_is_reported_before_dns(self):
        self.blocked({'CODEX_SANDBOX_NETWORK_DISABLED': '', 'ROKT_DEVELOPMENT_ONLY': '1',
                      'ROKT_DEV_CONTROLLED_WEB': ''}, 'DEVELOPMENT_TRANSPORT_BLOCKED')

    def test_sandbox_policy_takes_precedence_over_web_opt_in(self):
        self.blocked({'CODEX_SANDBOX_NETWORK_DISABLED': '1', 'ROKT_DEVELOPMENT_ONLY': '1',
                      'ROKT_DEV_CONTROLLED_WEB': '1'}, 'NETWORK_POLICY_BLOCKED')

    def test_invalid_web_opt_in_remains_blocked(self):
        self.blocked({'CODEX_SANDBOX_NETWORK_DISABLED': '', 'ROKT_DEVELOPMENT_ONLY': '1',
                      'ROKT_DEV_CONTROLLED_WEB': 'true'}, 'DEVELOPMENT_TRANSPORT_BLOCKED')

    def test_script_startup_marker_is_gated_before_guard_sets_environment(self):
        with patch('scripts.run_brand_capture.Path.is_file', return_value=True):
            self.blocked({'CODEX_SANDBOX_NETWORK_DISABLED': '', 'ROKT_DEVELOPMENT_ONLY': '',
                          'ROKT_DEV_CONTROLLED_WEB': ''}, 'DEVELOPMENT_TRANSPORT_BLOCKED')

    def test_authorized_web_opt_in_reaches_existing_bounded_runner(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary, \
                patch.dict(os.environ, {'CODEX_SANDBOX_NETWORK_DISABLED': '',
                                       'ROKT_DEVELOPMENT_ONLY': '1', 'ROKT_DEV_CONTROLLED_WEB': '1'}), \
                patch('scripts.run_brand_capture.PublicPageFetcher'), \
                patch('scripts.run_brand_capture._capture_directories', return_value=0) as runner:
            self.assertEqual(main(['--mode', 'capture-public', '--output-dir', temporary], directory=True), 0)
            runner.assert_called_once()
            self.assertIsNone(runner.call_args.kwargs['history_check'])


if __name__ == '__main__':
    unittest.main()
