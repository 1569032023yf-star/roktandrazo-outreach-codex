import hashlib
import hmac
import unittest
from autonomy.host_preparation import EvidenceConsumer, TrustedSource, canonical
from autonomy.rollback_admission import rollback_admission, FLAGS, COUNTS
from autonomy.unattended_policy import INVENTORY

KEY = b'fixture-only-rollback-test-key-0000'

class RollbackAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.consumer = EvidenceConsumer({'fixture': TrustedSource('fixture', 'principal', KEY)})
        self.expected = dict(principal_id='principal', inventory_id=INVENTORY,
            release_sha256='1'*64, ledger_sha256='2'*64, executor_sha256='3'*64,
            ledger_schema=2, previous_epoch=4, authority_epoch=5, exclusive_lock_id='lock-5')
        self.payload = dict(self.expected, source_id='fixture', schema='rokt.host-evidence.v1',
            kind='rollback_readiness', observed_at_epoch=1000, receipt_id='receipt',
            restore_old_database=False)
        self.payload.update(dict.fromkeys(FLAGS, True))
        self.payload.update(dict.fromkeys(COUNTS, 0))

    def envelope(self):
        return dict(payload=dict(self.payload), mac=hmac.new(KEY, canonical(self.payload), hashlib.sha256).hexdigest())

    def check(self, envelope=None, now=1001):
        result = rollback_admission(self.consumer, envelope or self.envelope(), now=now, expected=self.expected)
        self.assertIs(result['allow_dispatch'], False)
        return result['allow_rollback_plan']

    def test_plan_only(self):
        self.assertTrue(self.check())

    def test_tampered_and_wrong_kind(self):
        e = self.envelope(); e['payload']['ledger_schema'] = 3
        self.assertFalse(self.check(e))
        self.payload['kind'] = 'host_readiness'
        self.assertFalse(self.check())

    def test_each_required_fact_and_binding_missing(self):
        for key in list(self.expected) + list(FLAGS) + list(COUNTS) + ['restore_old_database']:
            with self.subTest(key=key):
                value = self.payload.pop(key)
                self.assertFalse(self.check())
                self.payload[key] = value

    def test_old_epoch_and_mismatched_fingerprints(self):
        for key in ('authority_epoch', 'ledger_schema', 'release_sha256', 'ledger_sha256', 'executor_sha256', 'exclusive_lock_id'):
            value = self.payload[key]
            self.payload[key] = 4 if type(value) is int else 'different'
            self.assertFalse(self.check())
            self.payload[key] = value
        self.expected['authority_epoch'] = 4
        self.assertFalse(self.check())

    def test_unresolved_and_non_integer_counts(self):
        for key in COUNTS:
            for value in (1, -1, False, '0', None):
                self.payload[key] = value
                self.assertFalse(self.check())
            self.payload[key] = 0

    def test_incompatible_restore_and_unsafe_facts(self):
        for key in FLAGS:
            self.payload[key] = False
            self.assertFalse(self.check())
            self.payload[key] = True
        self.payload['restore_old_database'] = True
        self.assertFalse(self.check())

    def test_stale_future_and_untrusted_identity(self):
        self.assertFalse(self.check(now=1301))
        self.assertFalse(self.check(now=999))
        self.payload['principal_id'] = 'other'
        self.assertFalse(self.check())

    def test_bool_integer_binding_rejected(self):
        self.expected['ledger_schema'] = True
        self.payload['ledger_schema'] = True
        self.assertFalse(self.check())
        self.expected['ledger_schema'] = 2
        self.payload['authority_epoch'] = True
        self.assertFalse(self.check())

    def test_missing_expected_context(self):
        self.expected.pop('ledger_sha256')
        self.assertFalse(self.check())

if __name__ == '__main__': unittest.main()
