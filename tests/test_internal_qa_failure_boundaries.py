"""Offline QA failure-boundary regression / 离线内部试发失败边界回归。"""
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

import bd_sender
import controlled_v6_test as qa


class InternalQaFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.policy = {
            'internal_test_only': True, 'allow_internal_without_postal_address': True,
            'controlled_test_recipients': ['qa@example.invalid'],
            'test_ownership_reference': 'FIXTURE ONLY',
            'authorized_at': datetime.now(timezone.utc).isoformat(),
            'test_run_id': 'FIXTURE-FAILURE', 'verified_from_email': 'sender@example.invalid',
        }
        self.server = Mock()
        self.server.sendmail.return_value = {}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(self.temp.cleanup)
        self.stack.enter_context(patch.object(qa, 'ROOT', self.root))
        self.stack.enter_context(patch.object(qa, 'AUDIT_PATH', self.root/'qa.sqlite'))
        self.policy_loader = self.stack.enter_context(patch.object(qa, 'load_test_policy', return_value=self.policy))
        self.stack.enter_context(patch('env_loader.get_sender_info', return_value={'email': 'sender@example.invalid'}))
        self.connection = self.stack.enter_context(patch.object(bd_sender, '_create_connection', return_value=self.server))

    def assert_reserved_not_accepted(self):
        with closing(sqlite3.connect(self.root/'qa.sqlite')) as conn:
            rows = conn.execute('SELECT smtp_accepted_at FROM internal_tests').fetchall()
        self.assertEqual(rows, [(None,)])

    def test_ambiguous_smtp_timeout_is_reserved_and_never_retried(self):
        self.server.sendmail.side_effect = TimeoutError('FIXTURE ambiguous acceptance')
        with self.assertRaises(TimeoutError):
            qa.send_internal_tests(send=True)
        self.assert_reserved_not_accepted()
        with self.assertRaises(sqlite3.IntegrityError):
            qa.send_internal_tests(send=True)
        self.assertEqual(self.server.sendmail.call_count, 1)
        self.server.quit.assert_called_once()

    def test_recipient_rejection_stops_remaining_templates(self):
        self.server.sendmail.return_value = {'qa@example.invalid': (550, b'FIXTURE')}
        with self.assertRaisesRegex(RuntimeError, 'RECIPIENT_REJECTED'):
            qa.send_internal_tests(send=True)
        self.assert_reserved_not_accepted()
        self.assertEqual(self.server.sendmail.call_count, 1)

    def test_policy_drift_after_reservation_stops_before_transport(self):
        changed = dict(self.policy, test_run_id='UNAPPROVED-CHANGE')
        self.policy_loader.side_effect = [self.policy, changed]
        with self.assertRaisesRegex(ValueError, 'POLICY_CHANGED'):
            qa.send_internal_tests(send=True)
        self.connection.assert_not_called()
        self.assert_reserved_not_accepted()

    def test_audit_failure_prevents_transport(self):
        with patch.object(qa, 'AUDIT_PATH', self.root/'absent'/'qa.sqlite'):
            with self.assertRaises(sqlite3.OperationalError):
                qa.send_internal_tests(send=True)
        self.connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
