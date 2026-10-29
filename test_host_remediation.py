import copy
import hashlib
import hmac
import unittest
from autonomy.host_preparation import EvidenceConsumer, TrustedSource, canonical
from autonomy.host_remediation import CONFIG, GATES, inspect_host_candidate

KEY = b'synthetic-host-contract-key-000000000'

class HostRemediationTests(unittest.TestCase):
    def setUp(self):
        self.consumer = EvidenceConsumer({'fixture': TrustedSource('fixture', 'service-principal', KEY)})
        self.expected = dict(source_commit='a'*40, package_sha256='b'*64,
            runtime_sha256='c'*64, service_wrapper_sha256='d'*64,
            publisher_sha256='e'*64, config_sha256=hashlib.sha256(canonical(CONFIG)).hexdigest(),
            principal_id='service-principal', exclusive_lock_id='sole-lock',
            backend_protocol='rokt.offline-backend.v1', approved_proxy_id='headless-approved')
        self.payload = dict(self.expected, schema='rokt.host-evidence.v1',
            kind='host_remediation', source_id='fixture', inventory_id=CONFIG['inventory_id'],
            observed_at_epoch=1000, expires_at_epoch=1100, receipt_id='fixture-1',
            config=copy.deepcopy(CONFIG), gates=dict.fromkeys(GATES, True))

    def check(self, payload=None, expected=None, now=1001):
        p = self.payload if payload is None else payload
        envelope = dict(payload=p, mac=hmac.new(KEY, canonical(p), hashlib.sha256).hexdigest())
        return inspect_host_candidate(self.consumer, envelope, now=now,
                                      expected=self.expected if expected is None else expected)

    def test_even_complete_signed_fixture_never_grants_any_execution(self):
        r = self.check()
        self.assertTrue(r['compatible'])
        for key in ('allow_install','allow_start','allow_dispatch','allow_cancel_dispatch','production_accepted'):
            self.assertIs(r[key], False)

    def test_each_failure_or_unknown_gate_blocks(self):
        for gate in GATES:
            for value in (False, 'UNKNOWN', 'PENDING', 1, None):
                with self.subTest(gate=gate, value=value):
                    p=copy.deepcopy(self.payload); p['gates'][gate]=value
                    r=self.check(p)
                    self.assertFalse(r['compatible']); self.assertIn(gate,r['missing_gates'])

    def test_unsafe_service_variants_rejected(self):
        for field,value in (('account','LocalSystem'),('service_name','BDExecutionHost'),
                ('start_type','auto'),('runtime',r'C:\Users\user\python.exe'),
                ('network_mode','user_session_7877'),('scheduler_created',1),
                ('allow_dispatch',True),('allow_cancel_dispatch',True),
                ('operations',['shell']),('rollback','restore_old_db')):
            p=copy.deepcopy(self.payload); p['config'][field]=value
            self.assertEqual(self.check(p)['reason'],'UNSAFE_SERVICE_CONFIG')

    def test_no_self_approved_bindings_or_unknown_fields(self):
        for field in self.expected:
            p=copy.deepcopy(self.payload); p[field]='other'
            self.assertFalse(self.check(p)['compatible'])
        p=copy.deepcopy(self.payload); p['config']['shell']='cmd.exe'
        self.assertFalse(self.check(p)['compatible'])
        self.assertEqual(self.check(expected={})['reason'],'INVALID_APPROVED_CONTEXT')

    def test_stale_expired_and_wrong_inventory_rejected(self):
        self.assertFalse(self.check(now=1101)['compatible'])
        self.assertFalse(self.check(now=999)['compatible'])
        p=copy.deepcopy(self.payload); p['inventory_id']='second'
        self.assertFalse(self.check(p)['compatible'])

    def test_config_fingerprint_and_protocol_fail_closed(self):
        expected=dict(self.expected,config_sha256='f'*64)
        p=dict(self.payload,config_sha256='f'*64)
        self.assertEqual(self.check(p,expected)['reason'],'CONFIG_HASH_MISMATCH')
        self.assertEqual(self.check(expected=dict(self.expected,backend_protocol='legacy'))['reason'],
                         'BACKEND_PROTOCOL_MISMATCH')

    def test_invalid_signature_rejected(self):
        r=inspect_host_candidate(self.consumer,dict(payload=self.payload,mac='0'*64),
                                 now=1001,expected=self.expected)
        self.assertEqual(r['reason'],'UNVERIFIED_CONTRACT')

if __name__=='__main__':
    unittest.main()
