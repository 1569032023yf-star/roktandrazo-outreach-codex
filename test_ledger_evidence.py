import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path
from autonomy.host_preparation import EvidenceConsumer, TrustedSource, canonical
from autonomy.ledger_evidence import LedgerEvidenceVerifier
from autonomy.durable_slots import DurableSlots, LedgerError, INVENTORY


class SignedLedgerIntegrationTests(unittest.TestCase):
    def test_signed_lifetime_and_aliases_fail_closed(self):
        key = b'synthetic-test-key-only-not-production' * 2
        consumer = EvidenceConsumer({'fixture': TrustedSource('fixture', 'test', key)})
        clock = [110]
        verify = LedgerEvidenceVerifier(consumer, lambda: clock[0])
        base = dict(schema='rokt.host-evidence.v1', source_id='fixture',
                    principal_id='test', inventory_id=INVENTORY, kind='idle',
                    observed_at_epoch=100, expires_at_epoch=200, receipt_id='r')
        def envelope(payload):
            return {'payload': payload, 'mac': hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()}
        self.assertIsNotNone(verify(envelope(base)))
        for field in ('inventory', 'observed', 'expires'):
            with self.subTest(alias=field):
                self.assertIsNone(verify(envelope(dict(base, **{field: 1}))))
        missing = dict(base)
        del missing['expires_at_epoch']
        self.assertIsNone(verify(envelope(missing)))
        for expiry in (True, 99, 401):
            with self.subTest(expiry=expiry):
                self.assertIsNone(verify(envelope(dict(base, expires_at_epoch=expiry))))
        for stamp in (99, 201):
            clock[0] = stamp
            with self.subTest(now=stamp):
                self.assertIsNone(verify(envelope(base)))
        clock[0] = 110
        for fields in ({'principal_id': 'other'}, {'source_id': 'other'},
                       {'kind': 'budget_request'}, {'inventory_id': 'other'}):
            with self.subTest(fields=fields):
                self.assertIsNone(verify(envelope(dict(base, **fields))))

    def test_signed_claim_and_tamper_rejection(self):
        key = b'synthetic-test-key-only-not-production' * 2
        consumer = EvidenceConsumer({'fixture': TrustedSource('fixture', 'test', key)})
        def signed(kind, **fields):
            p = dict(schema='rokt.host-evidence.v1', source_id='fixture',
                     principal_id='test', inventory_id=INVENTORY, kind=kind,
                     observed_at_epoch=100, expires_at_epoch=200, receipt_id='r', **fields)
            return {'payload': p, 'mac': hmac.new(key, canonical(p), hashlib.sha256).hexdigest()}
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableSlots(Path(directory) / 'isolated.sqlite',
                                  verify=LedgerEvidenceVerifier(consumer, lambda: 110))
            ledger.initialize()
            ledger.switch_authority(0, 'owner', signed('authority', previous_epoch=0,
                owner='owner', drained=True, old_disabled=True), now=110)
            ledger.admit_due('s', 105, signed('schedule', slot='s', next_due=105,
                epoch=1, owner='owner', latest_due=True, missed=[]), now=110, epoch=1, owner='owner')
            e = signed('idle', slot='s', epoch=1, owner='owner',
                       external_state='idle', existing_lock_held=True)
            e['payload']['owner'] = 'tampered'
            with self.assertRaises(LedgerError):
                ledger.claim('s', e, now=110, epoch=1, owner='owner')
            e = signed('idle', slot='s', epoch=1, owner='owner',
                       external_state='idle', existing_lock_held=True)
            token = ledger.claim('s', e, now=110, epoch=1, owner='owner')
            self.assertTrue(token)
            with self.assertRaises(LedgerError):
                ledger.claim('s', e, now=110, epoch=1, owner='owner')


if __name__ == '__main__':
    unittest.main()
