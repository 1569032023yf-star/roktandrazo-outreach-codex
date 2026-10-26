import copy
import hashlib
import hmac
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from autonomy.host_preparation import (EvidenceConsumer, TrustedSource, canonical,
    host_admission, bridge_acceptance, runtime_file_check, EvidenceError)
from autonomy.unattended_policy import GATES, INVENTORY

# Synthetic fixture key; not provisioned anywhere and never used for production.
KEY = b'synthetic-offline-fixture-key-00000'


def signed(payload):
    return {'payload': copy.deepcopy(payload), 'mac': hmac.new(KEY, canonical(payload), hashlib.sha256).hexdigest()}


class HostPreparationTests(unittest.TestCase):
    def setUp(self):
        self.consumer = EvidenceConsumer({'fixture': TrustedSource('fixture', 'opaque-principal', KEY)})
        self.base = dict(schema='rokt.host-evidence.v1', kind='host_readiness',
                         source_id='fixture', principal_id='opaque-principal', inventory_id=INVENTORY,
                         observed_at_epoch=1000, receipt_id='receipt-a')

    def test_signed_all_true_never_dispatches(self):
        p = dict(self.base, gates=dict.fromkeys(GATES, True), egress=dict(
            mode='approved_noninteractive', target_principal_id='opaque-principal',
            dns_tls_proxy_probe_ok=True, interactive_session_required=False))
        r = host_admission(self.consumer, signed(p), now=1001)
        self.assertFalse(r['allow_dispatch'])
        self.assertEqual(r['reasons'], ['FORMAL_EXECUTION_ADAPTER_NOT_INSTALLED'])

    def test_user_session_proxy_not_noninteractive(self):
        p = dict(self.base, gates=dict.fromkeys(GATES, True), egress={'mode': 'user_session_7877'})
        self.assertIn('NONINTERACTIVE_EGRESS_NOT_PROVEN', host_admission(self.consumer, signed(p), now=1000)['reasons'])

    def test_bound_receipt_expiry_and_exact_types(self):
        p = dict(self.base, kind='slot_claim', slot='slot-a', epoch=2, owner='owner-a', expires_at_epoch=1010)
        e = signed(p)
        self.assertTrue(self.consumer.verify_bound(e, kind='slot_claim', now=1001,
                                                  expected={'slot': 'slot-a', 'epoch': 2, 'owner': 'owner-a'}))
        for expected in ({}, {'slot': 'slot-b'}, {'epoch': True}, {'owner': 'old'}):
            self.assertFalse(self.consumer.verify_bound(e, kind='slot_claim', now=1001, expected=expected))
        self.assertFalse(self.consumer.verify_bound(e, kind='slot_claim', now=1011, expected={'slot': 'slot-a'}))

    def test_mutation_signature_source_identity_and_time(self):
        e = signed(self.base)
        e['payload']['principal_id'] = 'attacker'
        self.assertEqual(host_admission(self.consumer, e, now=1000)['reasons'], ['INVALID_SIGNATURE'])
        for change, expected in [({'source_id': 'untrusted'}, 'UNTRUSTED_SOURCE'),
                                 ({'principal_id': 'other'}, 'IDENTITY_MISMATCH'),
                                 ({'inventory_id': 'second'}, 'IDENTITY_MISMATCH'),
                                 ({'observed_at_epoch': 1001}, 'STALE_OR_FUTURE_EVIDENCE'),
                                 ({'observed_at_epoch': 1}, 'STALE_OR_FUTURE_EVIDENCE')]:
            r = host_admission(self.consumer, signed(dict(self.base, **change)), now=1000)
            self.assertEqual(r['reasons'], [expected])

    def test_caller_booleans_and_malformed_envelopes_fail_closed(self):
        for bad in ({'gates': dict.fromkeys(GATES, True)}, None, [], {'payload': {}, 'mac': 'secret'}):
            r = host_admission(self.consumer, bad, now=1000)
            self.assertFalse(r['allow_dispatch'])
            self.assertNotIn('secret', str(r))
        with self.assertRaises(EvidenceError):
            EvidenceConsumer({'fixture': TrustedSource('fixture', 'p', b'short')})

    def observations(self):
        a = dict(self.base, kind='bridge_observation', call_id='call-a', boot_id='boot',
                 logon_id='logon', instance_id='process-start', authenticated=True,
                 post_health_ok=True, interactive_login_present=True, method='POST',
                 endpoint='health', hkcu_run_verified=True)
        b = dict(a, call_id='call-b', receipt_id='receipt-b', observed_at_epoch=1001)
        return a, b

    def test_bridge_four_independent_statuses(self):
        a, b = self.observations()
        r = bridge_acceptance(self.consumer, [signed(a), signed(b)], now=1002)
        self.assertEqual(r['HKCU_RUN_CONFIGURED'], 'VERIFIED_AT_OBSERVATION')
        self.assertEqual(r['CROSS_CALL_VERIFIED'], 'VERIFIED_AT_OBSERVATION')
        self.assertEqual(r['CROSS_LOGON_VERIFIED'], 'NOT_VERIFIED')
        self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'], 'NOT_VERIFIED')
        for change in ({'boot_id': 'next'}, {'logon_id': 'next'}, {'instance_id': 'next'}):
            r = bridge_acceptance(self.consumer, [signed(a), signed(dict(b, **change))], now=1002)
            self.assertEqual(r['CROSS_CALL_VERIFIED'], 'NOT_VERIFIED')
            self.assertEqual(r['NO_LOGIN_BOOT_VERIFIED'], 'NOT_VERIFIED')

    def test_bridge_duplicate_and_wrong_post_contract(self):
        a, b = self.observations()
        for rows in (None, [], [signed(a), signed(a)], [signed(a), signed(dict(b, method='GET'))]):
            r = bridge_acceptance(self.consumer, rows, now=1002)
            self.assertEqual(r['CROSS_CALL_VERIFIED'], 'NOT_VERIFIED')

    def test_runtime_hash_probe_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'synthetic-runtime'
            p.write_bytes(b'fixture')
            self.assertEqual(runtime_file_check(p, hashlib.sha256(b'fixture').hexdigest()), 'RUNTIME_HASH_MATCH')
            self.assertEqual(runtime_file_check(p, '0' * 64), 'RUNTIME_HASH_MISMATCH')
            self.assertEqual(p.read_bytes(), b'fixture')

    def test_disabled_task_and_cli_cannot_collect(self):
        ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
        root = ET.parse(Path(__file__).parent / 'autonomy/config/u1_host_disabled.xml').getroot()
        self.assertEqual(root.findtext('t:Settings/t:Enabled', namespaces=ns), 'false')
        self.assertEqual(root.findtext('t:Settings/t:AllowStartOnDemand', namespaces=ns), 'false')
        self.assertEqual(root.findtext('t:Settings/t:MultipleInstancesPolicy', namespaces=ns), 'IgnoreNew')
        self.assertEqual(len(root.find('t:Triggers', ns)), 0)
        self.assertEqual(root.findtext('t:Principals/t:Principal/t:RunLevel', namespaces=ns), 'LeastPrivilege')
        r = subprocess.run([sys.executable, '-B', '-m', 'autonomy.host_preparation'],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 78)
        self.assertIn('FORMAL_EXECUTION_ADAPTER_NOT_INSTALLED', r.stdout)


if __name__ == '__main__':
    unittest.main()
