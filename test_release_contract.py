import copy
import hashlib
import hmac
import unittest

from autonomy.host_preparation import EvidenceConsumer, TrustedSource, canonical
from autonomy.release_contract import inspect_release_contract, CAPABILITIES
from autonomy.unattended_policy import INVENTORY

KEY = b'fixture-release-contract-only-000000'


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.consumer = EvidenceConsumer({'fixture': TrustedSource('fixture', 'principal', KEY)})
        self.expected = dict(principal_id='principal', inventory_id=INVENTORY,
            source_commit='a'*40, package_sha256='b'*64, runtime_sha256='c'*64,
            publisher_sha256='d'*64, backend_id='original-inventory',
            exclusive_lock_id='sole-lock', ledger_schema=2,
            files=[dict(path='autonomy/durable_slots.py', source_sha256='e'*64,
                        target_sha256='ABSENT')])
        self.payload = dict(copy.deepcopy(self.expected), schema='rokt.host-evidence.v1',
            source_id='fixture', kind='release_compatibility', observed_at_epoch=1000,
            receipt_id='release-contract', capabilities=dict.fromkeys(CAPABILITIES, True))

    def envelope(self):
        return dict(payload=copy.deepcopy(self.payload),
                    mac=hmac.new(KEY, canonical(self.payload), hashlib.sha256).hexdigest())

    def check(self, envelope=None, now=1001):
        result = inspect_release_contract(self.consumer,
            self.envelope() if envelope is None else envelope, now=now, expected=self.expected)
        self.assertIs(result['allow_install'], False)
        self.assertIs(result['allow_dispatch'], False)
        return result['compatible']

    def test_compatible_is_plan_only(self):
        self.assertTrue(self.check())

    def test_every_capability_unknown_false_or_missing_denies(self):
        for key in CAPABILITIES:
            for value in (False, None, 1, 'true'):
                self.payload['capabilities'][key] = value
                self.assertFalse(self.check(), key)
            self.payload['capabilities'].pop(key)
            self.assertFalse(self.check(), key)
            self.payload['capabilities'][key] = True

    def test_all_bindings_must_match_external_plan(self):
        for key in self.expected:
            saved = self.payload.pop(key)
            self.assertFalse(self.check(), key)
            self.payload[key] = saved
        self.payload['files'][0]['target_sha256'] = 'f'*64
        self.assertFalse(self.check())

    def test_reject_unsigned_tampered_expired_or_other_source(self):
        self.assertFalse(self.check({}))
        e = self.envelope(); e['payload']['backend_id'] = 'other'
        self.assertFalse(self.check(e))
        self.assertFalse(self.check(now=1301))
        self.assertFalse(self.check(now=999))
        self.payload['source_id'] = 'unknown'
        self.assertFalse(self.check())

    def test_unsafe_paths_collisions_and_unapproved_targets(self):
        for path in ('/absolute.py', '../escape.py', 'a/../x', 'a//x', 'a\\x',
                     'C:/x', './x', 'a./x', 'a/x:stream'):
            self.expected['files'][0]['path'] = path
            self.assertFalse(self.check(), path)
        self.expected['files'][0]['path'] = 'autonomy/durable_slots.py'
        self.expected['files'].append(dict(self.expected['files'][0], path='AUTONOMY/durable_slots.py'))
        self.assertFalse(self.check())
        self.expected['files'].pop()
        self.expected['files'][0]['target_sha256'] = 'UNAPPROVED'
        self.assertFalse(self.check())

    def test_bad_context_and_wrong_kind(self):
        self.payload['kind'] = 'host_readiness'
        self.assertFalse(self.check())
        for bad in (None, {}, dict(self.expected, ledger_schema=True), dict(self.expected, files=[])):
            self.assertFalse(inspect_release_contract(self.consumer, self.envelope(),
                now=1001, expected=bad)['compatible'])

    def test_windows_devices_and_file_ancestor_collisions(self):
        for path in ('CON', 'a/NUL.py', 'COM1.txt', 'a/AUX', 'lpt9.json', 'a/PRN.log'):
            self.expected['files'][0]['path'] = path
            self.payload['files'] = copy.deepcopy(self.expected['files'])
            self.assertFalse(self.check(), path)
        for parent, child in (('a', 'a/b.py'), ('A/b.py', 'a')):
            entry = dict(source_sha256='e'*64, target_sha256='ABSENT')
            self.expected['files'] = [dict(entry,path=parent),dict(entry,path=child)]
            self.payload['files'] = copy.deepcopy(self.expected['files'])
            self.assertFalse(self.check())


if __name__ == '__main__':
    unittest.main()
