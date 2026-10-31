"""严格SAFE窗口合同 / Strict SAFE window contracts, offline fixtures only."""
import copy
import unittest
from autonomy.handoff_validation import reconcile_safe_growth


class SafeGrowthTests(unittest.TestCase):
    def setUp(self):
        self.old = dict(schema='rokt.safe_authority.v1', measurement_complete=True,
                        available=True, safe_unique_orgs=62,
                        rule_version=dict(name='fixed', code={'module': 'sha'}),
                        method='distinct organization_key; fixed selection',
                        measured_at='2026-10-30T23:43:28+08:00')
        self.new = dict(self.old, safe_unique_orgs=69,
                        measured_at='2026-10-31T15:43:28+00:00')

    def run_growth(self, old=None, hours=24):
        return reconcile_safe_growth(self.new, self.old if old is None else old,
                                     window_hours=hours)

    def test_exact_window_cross_timezone_and_no_authority(self):
        r = self.run_growth()
        self.assertEqual(r['net_growth'], 7)
        self.assertFalse(r['allow_dispatch']); self.assertFalse(r['production_accepted'])
        self.assertEqual(r['business_growth'], 'UNKNOWN')

    def test_missing_baseline_does_not_accept_producer_zero(self):
        self.new['safe_net_growth'] = {'h24': 0}
        self.assertEqual(reconcile_safe_growth(self.new, None, window_hours=24)['net_growth'], 'UNKNOWN')

    def test_actual_published_baseline_labels_are_not_exact_windows(self):
        for at, hours, seconds in [('2026-10-30T22:41:03+08:00',24,90145),
                                   ('2026-10-25T03:03:35+08:00',168,592793)]:
            old = dict(self.old, measured_at=at)
            r = self.run_growth(old, hours)
            self.assertEqual(r['net_growth'], 'UNKNOWN')
            self.assertEqual(r['actual_window_seconds'], seconds)

    def test_rule_or_dedup_changes_fail_closed(self):
        for key, value in [('rule_version', {'name':'other'}), ('method','other'),
                           ('rule_version',{}), ('method','')]:
            self.assertEqual(self.run_growth(dict(self.old, **{key:value}))['net_growth'], 'UNKNOWN')

    def test_boolean_negative_and_incomplete_counts_fail_closed(self):
        for key, value in [('safe_unique_orgs',True), ('safe_unique_orgs',-1),
                           ('safe_unique_orgs',62.0),('measurement_complete',1),('available',False)]:
            self.assertEqual(self.run_growth(dict(self.old, **{key:value}))['net_growth'], 'UNKNOWN')

    def test_invalid_naive_reversed_or_off_by_one_time(self):
        for stamp in ['bad','2026-10-30T23:43:28','2026-11-01T23:43:28+08:00',
                      '2026-10-30T23:43:27+08:00']:
            self.assertEqual(self.run_growth(dict(self.old, measured_at=stamp))['net_growth'], 'UNKNOWN')

    def test_seven_days_and_negative_delta(self):
        self.new['safe_unique_orgs']=60
        r=self.run_growth(dict(self.old, measured_at='2026-10-24T23:43:28+08:00'),168)
        self.assertEqual(r['net_growth'],-2)

    def test_missing_fields_and_unsupported_windows(self):
        for key in self.old:
            old=copy.deepcopy(self.old); del old[key]
            self.assertEqual(self.run_growth(old)['net_growth'],'UNKNOWN')
        for hours in [True,24.0,0,25,167]:
            self.assertEqual(self.run_growth(hours=hours)['net_growth'],'UNKNOWN')

    def test_inputs_not_modified(self):
        before=copy.deepcopy((self.new,self.old))
        self.run_growth()
        self.assertEqual((self.new,self.old),before)


if __name__ == '__main__':
    unittest.main()
