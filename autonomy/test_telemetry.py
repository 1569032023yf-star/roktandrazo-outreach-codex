"""Synthetic offline fixtures only / 仅本地合成样例，不读取真实 inbox。"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from autonomy import telemetry as t

NOW = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)


def fixture(period='24h', number=1, age=0):
    end = NOW - timedelta(seconds=age)
    stamp = lambda d: d.strftime('%Y-%m-%dT%H:%M:%SZ')
    return {'schema_version': 1, 'snapshot_id': f'00000000-0000-4000-8000-{number:012d}',
            'source': 'fixture', 'collected_at': stamp(end), 'period': period,
            'window_start': stamp(end - timedelta(hours=24 if period == '24h' else 168)),
            'window_end': stamp(end), 'counts': {'new_verified_organizations': 3}}


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.inbox = Path(temp.name)

    def read(self, **kwargs):
        return t.read_inbox(inbox=self.inbox, approved_sources={'fixture'}, now=NOW, **kwargs)

    def write(self, payload, name='one.json'):
        (self.inbox / name).write_text(json.dumps(payload), encoding='utf-8')

    def valid(self, payload):
        return t.validate_snapshot(payload, approved_sources={'fixture'}, now=NOW)

    def test_valid_both_periods_and_detached_counts(self):
        for period in ('24h', '7d'):
            raw = fixture(period)
            clean = self.valid(raw)
            clean['counts'].clear()
            self.assertTrue(raw['counts'])

    def test_missing_empty_invalid_inputs_are_unknown(self):
        self.assertEqual(self.read()['status'], 'UNKNOWN')
        self.assertEqual(t.read_inbox(inbox=self.inbox / 'absent', now=NOW)['status'], 'UNKNOWN')
        self.write({})
        self.assertEqual(self.read()['status'], 'UNKNOWN')

    def test_source_requires_external_approval(self):
        with self.assertRaises(t.InvalidSnapshot):
            t.validate_snapshot(fixture(), now=NOW)
        for source in ('', None, 'unknown', 'a@example.test', 'https://example.test?token=x'):
            raw = fixture()
            raw['source'] = source
            with self.subTest(source=source), self.assertRaises(t.InvalidSnapshot):
                self.valid(raw)

    def test_reject_all_unknown_fields_and_identity_credentials(self):
        for field in ('email', 'customer_id', 'password', 'token', 'credentials', 'approved', 'notes'):
            raw = fixture()
            raw[field] = 'SYNTHETIC_PRIVATE_VALUE'
            self.write(raw)
            result = self.read()
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', json.dumps(result))

    def test_metric_allowlist_excludes_history_totals_and_nested_data(self):
        for counts in ({'safe_total': 56}, {'historical_total': 44}, {'email': 1}, {},
                       {'new_verified_organizations': {'email': 'fixture'}}, []):
            raw = fixture()
            raw['counts'] = counts
            with self.subTest(counts=counts), self.assertRaises(t.InvalidSnapshot):
                self.valid(raw)

    def test_reject_negative_bool_float_string_null_and_overflow(self):
        for count in (-1, True, 1.0, '1', None, 2**63):
            raw = fixture()
            raw['counts']['new_verified_organizations'] = count
            with self.subTest(count=count), self.assertRaises(t.InvalidSnapshot):
                self.valid(raw)
        raw['counts']['new_verified_organizations'] = 0
        self.assertEqual(self.valid(raw)['counts']['new_verified_organizations'], 0)

    def test_future_and_stale_boundary(self):
        for age in (-1, 3601):
            with self.subTest(age=age), self.assertRaises(t.InvalidSnapshot):
                self.valid(fixture(age=age))
        self.valid(fixture(age=3600))

    def test_timestamps_and_exact_intervals(self):
        changes = [('period', 'lifetime'), ('period', []), ('collected_at', '2026-10-20'),
                   ('collected_at', '2026-02-30T00:00:00Z'),
                   ('window_start', '2026-10-18T00:00:00Z'),
                   ('window_end', '2026-10-19T23:59:59Z'),
                   ('window_start', '2026-10-21T00:00:00Z'),
                   ('window_end', '2026-10-20T00:00:01Z')]
        for field, value in changes:
            raw = fixture()
            raw[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(t.InvalidSnapshot):
                self.valid(raw)

    def test_bad_schema_id_and_missing_fields(self):
        for field, value in [('schema_version', True), ('schema_version', 2),
                             ('snapshot_id', 'identity@example.test'), ('snapshot_id', [])]:
            raw = fixture()
            raw[field] = value
            with self.assertRaises(t.InvalidSnapshot):
                self.valid(raw)
        for field in t.FIELDS:
            raw = fixture()
            del raw[field]
            with self.assertRaises(t.InvalidSnapshot):
                self.valid(raw)

    def test_duplicate_ids_reject_all_and_seen_ids_reject_replay(self):
        self.write(fixture())
        self.write(fixture('7d'), 'two.json')
        result = self.read()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['rejected'], {'DUPLICATE_SNAPSHOT': 2})
        (self.inbox / 'two.json').unlink()
        self.assertEqual(self.read(seen_ids={fixture()['snapshot_id']})['status'], 'UNKNOWN')

    def test_latest_not_sum_or_missing_metric_fallback(self):
        old = fixture(number=1, age=60)
        old['counts']['new_first_party_emails'] = 44
        self.write(old)
        self.write(fixture(number=2), 'two.json')
        self.write(fixture('7d', number=3), 'three.json')
        result = self.read()
        self.assertEqual(result['status'], 'VALID')
        self.assertEqual(len(result['snapshots']), 2)
        for snapshot in result['snapshots']:
            self.assertEqual(snapshot['counts'], {'new_verified_organizations': 3})

    def test_equal_time_ambiguity_not_arbitrary_winner(self):
        self.write(fixture())
        self.write(fixture(number=2), 'two.json')
        self.assertEqual(self.read()['status'], 'UNKNOWN')

    def test_invalid_json_duplicate_keys_encoding_and_size(self):
        for content in (b'{', b'\xff', b'{"source":"fixture","source":"fixture"}',
                        b' ' * (t.MAX_BYTES + 1), b'[' * 2000):
            (self.inbox / 'one.json').write_bytes(content)
            self.assertEqual(self.read()['status'], 'UNKNOWN')

    def test_unreadable_file_sanitizes_exception(self):
        self.write(fixture())
        with patch.object(Path, 'open', side_effect=OSError('SYNTHETIC_PRIVATE_VALUE')):
            result = self.read()
        self.assertEqual(result['rejected'], {'FILE_UNREADABLE': 1})
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', json.dumps(result))

    def test_reject_directory_as_json_and_no_recursion(self):
        (self.inbox / 'dir.json').mkdir()
        self.write(fixture(), 'dir.json/inside.json')
        self.assertEqual(self.read()['status'], 'UNKNOWN')

    def test_naive_now_is_configuration_error(self):
        with self.assertRaisesRegex(ValueError, 'AWARE_NOW_REQUIRED'):
            t.read_inbox(inbox=self.inbox, now=datetime(2026, 10, 20))

    def test_symlink_file_and_linked_inbox_rejected(self):
        self.write(fixture())
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda p: p.name == 'one.json' or original(p)):
            self.assertEqual(self.read()['rejected'], {'UNSAFE_FILE': 1})
        with patch.object(Path, 'is_symlink', lambda p: p == self.inbox.parent or original(p)):
            self.assertEqual(self.read()['rejected'], {'UNSAFE_INBOX': 1})

    def test_read_does_not_modify_fixture(self):
        self.write(fixture())
        before = {p.name: p.read_bytes() for p in self.inbox.iterdir()}
        self.read()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.inbox.iterdir()})


if __name__ == '__main__':
    unittest.main()
