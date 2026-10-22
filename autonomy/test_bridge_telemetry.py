"""Adversarial aggregate-consumer tests / 聚合消费边界测试。"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomy.telemetry import consume_bridge_receipt, InvalidSnapshot

NOW = datetime(2026, 10, 22, 1, 10, tzinfo=timezone.utc)


def fixture():
    return {'http_status': 200, 'response': {
        'schema': 'rokt.telemetry.v1', 'channel_id': 'rokt-deploy-channel',
        'test_mode': False, 'verdict': 'OK', 'generated_at': '2026-10-22T09:01:39+08:00',
        'discovery': {'leads_total': 1213, 'leads_with_email': 652, 'provider_requests_24h': 0},
        'safe': {'available': True, 'safe_unique_orgs': 56, 'mx_probe_ok': True},
        'inventory': {'lock_value': 'released', 'running_inventory_24h_window': 0,
                      'recent_runs': [{'run_id': 'inventory:2026-10-22:03b70e7a',
                                       'stage': 'inventory', 'status': 'completed',
                                       'actual': 56, 'stop_reason': 'target_met'}]},
        'automations': {'active_inventory_count': 1},
        'guardrails': {'smtp_enabled': '0'}, 'sends': {'sent_today': 0, 'total_sent': 517},
        'city': {'active': [{'city': 'Cooperstown', 'status': 'active'},
                            {'city': 'Little Rock', 'status': 'QUEUED'}]},
    }}


class BridgeTelemetryTests(unittest.TestCase):
    def consume(self, value):
        return consume_bridge_receipt(value, approved_channel='rokt-deploy-channel', now=NOW)

    def test_lifetime_and_run_actual_never_become_safe_or_growth(self):
        result = self.consume(fixture())
        self.assertEqual(result['historical_totals']['leads_total'], 1213)
        self.assertEqual(result['last_inventory_run']['actual_historical_run_count'], 56)
        self.assertEqual(result['current_safe'], 'UNKNOWN')
        self.assertFalse(result['safe_authority_connected'])
        self.assertEqual(result['rolling_24h']['new_verified_organizations'], 'UNKNOWN')
        self.assertEqual(result['rolling_7d']['safe_net_growth'], 'UNKNOWN')

    def test_authenticated_caller_policy_required(self):
        with self.assertRaisesRegex(InvalidSnapshot, 'UNAPPROVED_SOURCE'):
            consume_bridge_receipt(fixture(), now=NOW)

    def test_reject_transport_error_test_mode_schema_and_clock(self):
        cases = [(None, 'http_status', 503), ('response', 'test_mode', True),
                 ('response', 'schema', 'fake'), ('response', 'verdict', 'ERROR'),
                 ('response', 'channel_id', 'other'),
                 ('response', 'generated_at', '2026-10-21T09:01:39+08:00'),
                 ('response', 'generated_at', '2026-10-22T10:01:39+08:00'),
                 ('response', 'generated_at', '2026-10-22T09:01:39'),
                 ('response', 'generated_at', None)]
        for parent, key, value in cases:
            raw = fixture()
            (raw[parent] if parent else raw)[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(InvalidSnapshot):
                self.consume(raw)

    def test_missing_invalid_or_boolean_counts_are_unknown(self):
        for bad in (None, True, -1, 1.5, '0', 2**63):
            raw = fixture(); raw['response']['discovery']['leads_total'] = bad
            with self.subTest(bad=bad):
                self.assertEqual(self.consume(raw)['historical_totals']['leads_total'], 'UNKNOWN')
        raw = fixture(); del raw['response']['sends']
        self.assertEqual(self.consume(raw)['safety']['sent_today'], 'UNKNOWN')

    def test_wrong_labels_and_designated_id_do_not_prove_uniqueness(self):
        result = self.consume(fixture())
        self.assertEqual(result['safety']['duplicate_inventory'], 'UNKNOWN')
        self.assertEqual(result['safety']['running_inventory_last_2h'], 0)
        self.assertNotIn('running_inventory_24h_window', result['safety'])
        self.assertEqual(result['active_cities'][1]['status'], 'QUEUED')

    def test_no_free_text_credentials_customer_data_or_errors_copied(self):
        raw = fixture(); raw['response']['token'] = 'SYNTHETIC_PRIVATE'
        raw['response']['city']['active'].append({'city': 'customer@example.test', 'status': 'active'})
        raw['response']['inventory']['recent_runs'][0]['error'] = 'SYNTHETIC_PRIVATE'
        raw['response']['inventory']['recent_runs'][0]['stop_reason'] = 'SYNTHETIC_PRIVATE'
        raw['response']['sends']['email'] = 'customer@example.test'
        rendered = json.dumps(self.consume(raw))
        self.assertNotIn('SYNTHETIC_PRIVATE', rendered)
        self.assertNotIn('customer@example.test', rendered)

    def test_malformed_nested_status_types_degrade_without_exception(self):
        for bad in ([], {}, None, True):
            raw = fixture()
            raw['response']['city']['active'][0]['status'] = bad
            raw['response']['inventory']['recent_runs'][0]['status'] = bad
            result = self.consume(raw)
            self.assertEqual(result['last_inventory_run'], 'UNKNOWN')
            self.assertNotIn('Cooperstown', json.dumps(result['active_cities']))

    def test_projection_detached_and_no_fake_run_from_untrusted_rows(self):
        raw = fixture(); before = deepcopy(raw); result = self.consume(raw)
        result['active_cities'].clear(); self.assertEqual(raw, before)
        raw['response']['inventory']['recent_runs'][0]['run_id'] = 'private email@example.test'
        self.assertEqual(self.consume(raw)['last_inventory_run'], 'UNKNOWN')

    def test_dashboard_preserves_history_and_replaces_only_live_section(self):
        from autonomy import supervisor
        with tempfile.TemporaryDirectory() as tmp, patch('autonomy.telemetry._now', return_value=NOW):
            root = Path(tmp); (root / 'autonomy').mkdir()
            path = root / 'autonomy/BUSINESS_DAILY_REPORT.md'
            path.write_text('HISTORICAL VERIFIED RECEIPT\n', encoding='utf-8')
            metrics = supervisor.dashboard(root, bridge_receipt=fixture())
            self.assertEqual(metrics['HISTORICAL_LEADS'], 1213)
            self.assertEqual(metrics['ACTIVE_CITY'], 'Cooperstown')
            self.assertEqual(metrics['SAFE_TOTAL_LATEST'], 'UNKNOWN')
            supervisor.dashboard(root, bridge_receipt=fixture())
            report = path.read_text(encoding='utf-8')
            self.assertTrue(report.startswith('HISTORICAL VERIFIED RECEIPT\n'))
            self.assertEqual(report.count('BD_LIVE_OBSERVATION_BEGIN'), 1)

    def test_dashboard_rejects_stale_without_erasing_history(self):
        from autonomy import supervisor
        with tempfile.TemporaryDirectory() as tmp, patch('autonomy.telemetry._now', return_value=NOW):
            root = Path(tmp); (root / 'autonomy').mkdir()
            path = root / 'autonomy/BUSINESS_DAILY_REPORT.md'
            path.write_text('HISTORY\n', encoding='utf-8')
            raw = fixture(); raw['response']['generated_at'] = '2026-10-20T09:00:00+08:00'
            metrics = supervisor.dashboard(root, bridge_receipt=raw)
            self.assertEqual(metrics['HISTORICAL_LEADS'], 'UNKNOWN')
            self.assertTrue(path.read_text(encoding='utf-8').startswith('HISTORY\n'))
            self.assertIn('UNKNOWN / NOT_VALIDATED', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
