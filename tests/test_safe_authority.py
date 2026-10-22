"""SAFE authority failure-path tests / SAFE 权威消费失败路径测试。"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest

from autonomy.safe_authority import consume_safe_authority, RULE_HASHES


NOW = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)


def fixture():
    return {'http_status': 200, 'observed_at': '2026-10-22T09:59:00+00:00', 'response': {
        'schema': 'rokt.safe_authority.v1', 'operation': 'safe', 'verdict': 'ok',
        'authoritative_route': '/v1/safe', 'available': True, 'fresh': True,
        'measurement_complete': True, 'mx_probe_ok': True, 'reading_agreement': True,
        'failure_reason': None, 'measured_at': '2026-10-22T07:49:52+00:00',
        'finished_at': '2026-10-22T07:56:46+00:00', 'generated_at': '2026-10-22T09:58:00+00:00',
        'rule_version': {'name': 'V1_V2_MX_HISTORY_SUPPRESSION_BUSINESS_FIT',
                         'entrypoint': 'campaign_eligible_v2.select_candidates_for_plan_v2',
                         'mx_probe': 'preflight_gate.query_mx',
                         'code': {name: {'sha256': sha} for name, sha in RULE_HASHES.items()}},
        'method': 'select_candidates_for_plan_v2 on a mode=ro connection; SAFE = distinct organization_key over the returned candidate rows',
        'source': 'bd_leads.db (read-only)',
        'db_identity': {'quick_check': 'ok', 'sha256': 'a' * 64},
        'mx_positive_control': {'mx_status': 'ok', 'checked_at': '2026-10-22T07:49:54+00:00', 'domain': 'control.invalid'},
        'mx_negative_control': {'mx_status': 'nxdomain', 'checked_at': '2026-10-22T07:49:55+00:00'},
        'safe_unique_orgs': 56,
        'readings': [
            {'reading': 1, 'sampling_time': '2026-10-22T07:52:56+00:00', 'candidate_rows': 56, 'unique_organizations': 56},
            {'reading': 2, 'sampling_time': '2026-10-22T07:56:45+00:00', 'candidate_rows': 56, 'unique_organizations': 56}],
        'new_customer_funnel': {'h24': {'window_hours': 24, 'unique_organizations_discovered': 8,
                                       'new_first_party_official_emails': 4}},
        'safe_net_growth': {'h24': 100, 'd7': 100},
    }}


class SafeAuthorityTests(unittest.TestCase):
    def consume(self, receipt=None, **kwargs):
        return consume_safe_authority(fixture() if receipt is None else receipt,
                                      approved_channel='rokt-deploy-channel', now=NOW, **kwargs)

    def rejects(self, mutate):
        receipt = fixture()
        mutate(receipt)
        with self.assertRaises(ValueError):
            self.consume(receipt)

    def test_valid_projection_and_no_input_mutation(self):
        receipt = fixture()
        original = deepcopy(receipt)
        result = self.consume(receipt)
        self.assertEqual(result['current_safe'], 56)
        self.assertTrue(result['safe_authority_connected'])
        self.assertEqual(receipt, original)
        result['rule_sha256'].clear()
        self.assertEqual(len(RULE_HASHES), 2)

    def test_json_self_assertion_is_not_authorization(self):
        receipt = fixture()
        receipt['response']['channel_id'] = 'rokt-deploy-channel'
        with self.assertRaisesRegex(ValueError, 'UNAPPROVED_SOURCE'):
            consume_safe_authority(receipt, now=NOW)

    def test_failed_transport_and_shape(self):
        for value in [None, [], {}, {'http_status': 500}, {'http_status': True}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.consume(value if value is not None else [])

    def test_flags_must_be_real_boolean(self):
        for key in ['available', 'fresh', 'measurement_complete', 'mx_probe_ok', 'reading_agreement']:
            for value in [False, 1, 'true', None]:
                with self.subTest(key=key, value=value):
                    self.rejects(lambda r: r['response'].__setitem__(key, value))

    def test_wrong_schema_route_and_rules_rejected(self):
        for key, value in [('schema', 'rokt.telemetry.v1'), ('operation', 'refresh'),
                           ('authoritative_route', '/v1/safe-snapshot'), ('verdict', 'OK'),
                           ('failure_reason', 'MX_FAIL')]:
            self.rejects(lambda r: r['response'].__setitem__(key, value))
        self.rejects(lambda r: r['response']['rule_version']['code']['campaign_eligible_v2.py'].__setitem__('sha256', 'b' * 64))
        self.rejects(lambda r: r['response']['rule_version'].__setitem__('entrypoint', 'other'))
        self.rejects(lambda r: r['response'].__setitem__('method', 'count leads'))
        self.rejects(lambda r: r['response'].__setitem__('source', 'arbitrary DB'))

    def test_database_and_control_evidence_required(self):
        self.rejects(lambda r: r['response']['db_identity'].__setitem__('quick_check', 'corrupt'))
        self.rejects(lambda r: r['response']['db_identity'].__setitem__('sha256', 'not-a-hash'))
        self.rejects(lambda r: r['response']['mx_positive_control'].__setitem__('mx_status', 'timeout'))
        self.rejects(lambda r: r['response']['mx_negative_control'].__setitem__('mx_status', 'ok'))

    def test_readings_are_independent_and_agree(self):
        self.rejects(lambda r: r['response'].__setitem__('readings', r['response']['readings'][:1]))
        self.rejects(lambda r: r['response']['readings'][1].__setitem__('unique_organizations', 55))
        self.rejects(lambda r: r['response']['readings'][1].__setitem__('candidate_rows', 55))
        self.rejects(lambda r: r['response']['readings'][1].__setitem__('sampling_time', r['response']['readings'][0]['sampling_time']))
        self.rejects(lambda r: r['response']['readings'][0].__setitem__('reading', True))
        for value in [True, -1, 56.0, '56', 2**63]:
            self.rejects(lambda r: r['response'].__setitem__('safe_unique_orgs', value))

    def test_stale_and_future_evidence_rejected_independently_of_fresh_flag(self):
        self.rejects(lambda r: r['response'].__setitem__('measured_at', '2026-10-22T03:59:59+00:00'))
        self.rejects(lambda r: r['response'].__setitem__('generated_at', '2026-10-22T08:59:59+00:00'))
        self.rejects(lambda r: r.__setitem__('observed_at', '2026-10-22T10:00:01+00:00'))
        self.rejects(lambda r: r['response'].__setitem__('finished_at', '2026-10-22T07:50:00+00:00'))
        self.rejects(lambda r: r['response'].__setitem__('measured_at', '2026-10-22T07:49:52'))
        self.rejects(lambda r: r['response']['mx_positive_control'].__setitem__('checked_at', '2026-10-22T08:00:00+00:00'))
        with self.assertRaises(ValueError):
            consume_safe_authority(fixture(), approved_channel='rokt-deploy-channel', now=NOW.replace(tzinfo=None))

    def test_discovery_is_not_verified_organization_and_growth_is_unknown(self):
        result = self.consume()
        self.assertEqual(result['rolling_24h']['unique_organizations_discovered'], 8)
        self.assertEqual(result['rolling_24h']['new_first_party_official_emails'], 4)
        self.assertEqual(result['new_verified_organizations_24h'], 'UNKNOWN')
        self.assertEqual(result['safe_net_growth_24h'], 'UNKNOWN')
        self.assertEqual(result['safe_net_growth_7d'], 'UNKNOWN')

    def test_malformed_funnel_is_unknown_not_zero(self):
        receipt = fixture()
        receipt['response']['new_customer_funnel']['h24']['new_first_party_official_emails'] = True
        self.assertEqual(self.consume(receipt)['rolling_24h']['new_first_party_official_emails'], 'UNKNOWN')
        receipt['response']['new_customer_funnel']['h24']['window_hours'] = 168
        self.assertEqual(self.consume(receipt)['rolling_24h']['unique_organizations_discovered'], 'UNKNOWN')

    def test_untrusted_extra_fields_and_control_domains_not_exposed(self):
        receipt = fixture()
        receipt['response']['business_name'] = 'SECRET_VALUE'
        receipt['response']['payload'] = {'email': 'SECRET_VALUE'}
        result = json.dumps(self.consume(receipt))
        self.assertNotIn('SECRET_VALUE', result)
        self.assertNotIn('control.invalid', result)
        self.assertNotIn('payload', result)


if __name__ == '__main__':
    unittest.main()
