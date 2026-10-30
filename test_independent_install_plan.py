import unittest
from autonomy.independent_install_plan import plan_install, recovery_action, STATES


class IndependentInstallPlanTests(unittest.TestCase):
    def args(self):
        return dict(manifest_sha256='a'*64, original_inventory='1784775229336',
                    target_absent=True, state_root_absent=True)

    def test_first_install_records_absence_without_authority(self):
        p=plan_install(**self.args())
        self.assertEqual(p['before'], 'ABSENT')
        for k in ('allow_install','allow_dispatch','production_execution'):
            self.assertIs(p[k], False)

    def test_existing_or_unknown_targets_rejected(self):
        for field in ('target_absent','state_root_absent'):
            for value in (False,None,1,'true'):
                a=self.args(); a[field]=value
                with self.assertRaises(ValueError): plan_install(**a)

    def test_identity_and_hash_rejected(self):
        for field,value in (('manifest_sha256','x'*64),('original_inventory','second')):
            a=self.args(); a[field]=value
            with self.assertRaises(ValueError): plan_install(**a)

    def test_every_crash_boundary_preserves_all_state(self):
        for state in STATES:
            for trusted in (True,False,None,1):
                r=recovery_action(state,receipt_matches=trusted,stopped=True,inventory_lease_valid=True)
                self.assertTrue(r['preserve_state']); self.assertTrue(r['preserve_code'])
                self.assertFalse(r['allow_replay']); self.assertFalse(r['allow_delete'])
                self.assertEqual(r['action'], 'REVIEW_REGISTRATION_ONLY_ROLLBACK' if trusted is True else 'STOP_AND_PRESERVE')

    def test_unknown_or_running_or_missing_lease_stops(self):
        with self.assertRaises(ValueError): recovery_action('UNKNOWN',receipt_matches=True,stopped=True,inventory_lease_valid=True)
        for stopped,lease in ((False,True),(True,False),(True,None)):
            self.assertEqual(recovery_action('PUBLISHED',receipt_matches=True,stopped=stopped,inventory_lease_valid=lease)['action'],'STOP_AND_PRESERVE')
