import unittest
from autonomy.bridge_acceptance import classify_pair


class BridgeAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.a = dict(call_id='a', boot_id='boot', logon_id='opaque-logon',
                      principal_id='opaque-user', instance_id='process-start-id',
                      observed_at_epoch=100, authenticated=True,
                      post_health_ok=True, interactive_login_present=True)
        self.b = dict(self.a, call_id='b', observed_at_epoch=110)

    def test_independent_session_observations(self):
        self.assertEqual(classify_pair(self.a, self.b), 'SAME_SESSION_TWO_CALLS_OBSERVED')
        self.assertEqual(classify_pair(self.a, self.a), 'NOT_INDEPENDENT_CALLS')
        self.assertEqual(classify_pair(self.b, self.a), 'NOT_ORDERED')

    def test_endpoints_do_not_prove_unattended_persistence(self):
        for change, result in [
            ({'boot_id': 'next'}, 'REBOOT_ENDPOINTS_ONLY'),
            ({'logon_id': 'next'}, 'CROSS_LOGON_ENDPOINTS_ONLY'),
            ({'instance_id': 'next'}, 'PROCESS_RESTARTED'),
            ({'principal_id': 'next'}, 'PRINCIPAL_CHANGED'),
            ({'interactive_login_present': False}, 'LOGIN_STATE_CHANGED'),
        ]:
            self.assertEqual(classify_pair(self.a, dict(self.b, **change)), result)
        a = dict(self.a, interactive_login_present=False)
        b = dict(self.b, interactive_login_present=False)
        self.assertEqual(classify_pair(a, b), 'SAME_SESSION_TWO_CALLS_OBSERVED')

    def test_missing_malformed_and_failed_health(self):
        for key in self.a:
            row = dict(self.a)
            del row[key]
            self.assertIn(classify_pair(row, self.b), ('INVALID_EVIDENCE', 'HEALTH_NOT_ACCEPTED'))
        for key in ('authenticated', 'post_health_ok'):
            for bad in (1, 'true', False, None):
                self.assertEqual(classify_pair(dict(self.a, **{key: bad}), self.b), 'HEALTH_NOT_ACCEPTED')
        self.assertEqual(classify_pair(dict(self.a, observed_at_epoch=True), self.b), 'INVALID_EVIDENCE')
        self.assertEqual(classify_pair(None, self.b), 'INVALID_EVIDENCE')

    def test_untrusted_extras_never_echo(self):
        result = classify_pair(dict(self.a, token='secret', url='sensitive'), self.b)
        self.assertNotIn('secret', result)
        self.assertNotIn('sensitive', result)


if __name__ == '__main__':
    unittest.main()
