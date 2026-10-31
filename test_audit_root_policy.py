import copy
import unittest

from autonomy.audit_root_policy import CHAIN, FULL_CONTROL, SCHEMA, evaluate_audit_root


def fixture():
    return dict(schema=SCHEMA, nodes=[dict(path=path, exists=True, directory=True,
        reparse_point=False, protected=True, owner_sid='S-1-5-32-544',
        aces=[dict(sid=sid, type='Allow', rights=FULL_CONTROL, inherit_only=False)
              for sid in ('S-1-5-18', 'S-1-5-32-544')]) for path in CHAIN])


class AuditRootPolicyTests(unittest.TestCase):
    def test_snapshot_match_is_never_live_authority(self):
        result = evaluate_audit_root(fixture())
        self.assertTrue(result['snapshot_policy_match'])
        for flag in ('trusted_handle_verified', 'allow_install', 'allow_dispatch', 'production_execution'):
            self.assertIs(result[flag], False)

    def test_every_ancestor_absent_reparse_or_wrong_path_rejected(self):
        for index in range(3):
            for field, value in (('exists', False), ('directory', False),
                                 ('reparse_point', True), ('reparse_point', None),
                                 ('owner_sid', 'S-1-5-32-545'), ('path', 'C:\\foreign')):
                with self.subTest(index=index, field=field):
                    data = fixture(); data['nodes'][index][field] = value
                    self.assertFalse(evaluate_audit_root(data)['snapshot_policy_match'])

    def test_root_owner_protection_and_admin_access_required(self):
        for field, value in (('owner_sid', 'S-1-5-32-545'), ('protected', False), ('protected', 1), ('aces', [])):
            data = fixture(); data['nodes'][-1][field] = value
            self.assertFalse(evaluate_audit_root(data)['snapshot_policy_match'])
        data = fixture(); data['nodes'][-1]['aces'].pop()
        self.assertFalse(evaluate_audit_root(data)['snapshot_policy_match'])

    def test_each_root_write_bit_and_inherit_only_write_rejected(self):
        for rights in (2, 4, 16, 64, 256, 65536, 262144, 524288):
            for inherit_only in (False, True):
                with self.subTest(rights=rights, inherit_only=inherit_only):
                    data = fixture()
                    data['nodes'][-1]['aces'].append(dict(sid='S-1-5-32-545', type='Allow', rights=rights, inherit_only=inherit_only))
                    self.assertEqual(evaluate_audit_root(data)['reason'], 'UNTRUSTED_WRITE_OR_REPLACE')

    def test_ancestor_replace_rejected_but_creation_alone_not_root_write(self):
        for index in (0, 1):
            for rights in (64, 65536, 262144, 524288):
                data = fixture()
                data['nodes'][index]['aces'].append(dict(sid='S-1-5-32-545', type='Allow', rights=rights, inherit_only=False))
                self.assertFalse(evaluate_audit_root(data)['snapshot_policy_match'])
        data = fixture()
        data['nodes'][1]['aces'].append(dict(sid='S-1-5-32-545', type='Allow', rights=6, inherit_only=False))
        self.assertTrue(evaluate_audit_root(data)['snapshot_policy_match'])

    def test_unknown_ace_deny_and_partial_evidence_fail_closed(self):
        for rights in (-1, True, 'FullControl', 0x10000000):
            data = fixture(); data['nodes'][-1]['aces'][0]['rights'] = rights
            self.assertFalse(evaluate_audit_root(data)['snapshot_policy_match'])
        data = fixture(); data['nodes'][-1]['aces'][0]['type'] = 'Deny'
        self.assertFalse(evaluate_audit_root(data)['snapshot_policy_match'])
        for data in ({}, None, dict(schema=SCHEMA, nodes=fixture()['nodes'][:-1])):
            self.assertFalse(evaluate_audit_root(data)['snapshot_policy_match'])

    def test_evaluation_preserves_input(self):
        data = fixture(); before = copy.deepcopy(data)
        evaluate_audit_root(data)
        self.assertEqual(data, before)


if __name__ == '__main__':
    unittest.main()
