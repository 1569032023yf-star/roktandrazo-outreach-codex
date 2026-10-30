"""Inventory归因合同 / Inventory attribution contracts."""
import copy
import unittest
from autonomy.handoff_validation import reconcile_inventory_firings

class InventoryAttributionTests(unittest.TestCase):
    def setUp(self):
        self.authority='automation-1784775229336'
        self.s=dict(canonical_automation=dict(id=self.authority),reconciliation_model=dict(tolerance_seconds=600),firings=[dict(firing_id='f1',run_id='inventory:r',executed=True,planned_at='2026-10-30T10:00:00+08:00',triggered_at='2026-10-30T10:01:00+08:00',completed_at='2026-10-30T10:30:00+08:00')])
        self.r=dict(runs=[dict(run_id='inventory:r',stage='inventory',trigger_id=self.authority,status='completed',process_started_at='2026-10-30T02:02:00+00:00',process_finished_at='2026-10-30T02:20:00+00:00')])

    def test_exact_stage_authority_window_and_timezone_join(self):
        result=reconcile_inventory_firings(self.s,self.r)
        self.assertEqual(result['verified_inventory_executions'],1)
        self.assertEqual(result['zero_missed_runs'],'UNKNOWN')
        self.assertFalse(result['allow_dispatch']);self.assertFalse(result['production_accepted'])

    def test_same_window_post_send_or_wrong_authority_is_not_inventory(self):
        for field,value in [('stage','post-send'),('trigger_id','NOT_RECORDED'),('status','running'),('process_started_at','2026-10-30T01:00:00+00:00'),('process_finished_at','2026-10-30T02:31:00+00:00'),('process_started_at','2026-10-30T02:02:00')]:
            with self.subTest(field=field,value=value):
                runtime=copy.deepcopy(self.r);runtime['runs'][0][field]=value
                self.assertEqual(reconcile_inventory_firings(self.s,runtime)['verified_inventory_executions'],0)

    def test_duplicate_missing_or_integer_execution_never_proves_execution(self):
        for runtime in [dict(runs=[]),dict(runs=self.r['runs']*2)]:
            self.assertEqual(reconcile_inventory_firings(self.s,runtime)['verified_inventory_executions'],0)
        self.s['firings'][0]['executed']=1
        self.assertEqual(reconcile_inventory_firings(self.s,self.r)['verified_inventory_executions'],0)

    def test_excess_drift_preserved_separately_from_actual_execution(self):
        self.s['firings'][0]['planned_at']='2026-10-30T09:40:00+08:00'
        result=reconcile_inventory_firings(self.s,self.r)
        self.assertEqual(result['verified_inventory_executions'],1)
        self.assertFalse(result['pairs'][0]['within_declared_tolerance'])
        self.assertEqual(result['zero_missed_runs'],'UNKNOWN')

if __name__=='__main__':unittest.main()
