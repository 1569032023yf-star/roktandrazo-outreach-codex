import hashlib
import json
import unittest
from datetime import datetime, timezone
from autonomy.handoff_validation import verify_document


class HandoffTests(unittest.TestCase):
    def fixture(self, **extra):
        value = dict(schema_version='1.0', generated_at='2026-10-22T15:00:00+00:00', evidence_kind='city', count=2)
        value.update(extra)
        value['payload_sha256'] = hashlib.sha256(json.dumps({'count': 2}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        raw = json.dumps(value).encode()
        return raw, hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

    def check(self, raw, blob, **kwargs):
        return verify_document(raw, blob, now=datetime(2026, 10, 22, 15, 10, tzinfo=timezone.utc), **kwargs)

    def test_valid_is_not_acceptance(self):
        result = self.check(*self.fixture())
        self.assertTrue(result['payload_verified'])
        self.assertFalse(result['production_accepted'])

    def test_bytes_mutation(self):
        raw, blob = self.fixture()
        with self.assertRaisesRegex(ValueError, 'GIT_BLOB'):
            self.check(raw + b'\n', blob)

    def test_payload_mutation(self):
        raw, _ = self.fixture()
        raw = raw.replace(b'"count": 2', b'"count": 3')
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        with self.assertRaisesRegex(ValueError, 'PAYLOAD'):
            self.check(raw, blob)

    def test_stale(self):
        with self.assertRaisesRegex(ValueError, 'STALE'):
            self.check(*self.fixture(generated_at='2026-10-22T12:00:00+00:00'))

    def test_future(self):
        with self.assertRaisesRegex(ValueError, 'STALE'):
            self.check(*self.fixture(generated_at='2026-10-22T16:00:00+00:00'))

    def test_schema(self):
        with self.assertRaisesRegex(ValueError, 'SCHEMA'):
            self.check(*self.fixture(schema_version='2.0'))


if __name__ == '__main__':
    unittest.main()
