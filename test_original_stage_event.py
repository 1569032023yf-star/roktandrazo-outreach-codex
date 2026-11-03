"""Actual original stage -> HTTP service -> claim/settlement; temporary DB only."""
from contextlib import closing
import sqlite3
import unittest
from unittest.mock import patch

import bd_db
from autonomy.original_stage_event import OriginalStageEvent
from autonomy.inventory_event_bridge import ExistingOwnerBridge
from autonomy.original_inventory_owner import OriginalOwnerAuthority
from tests.test_inventory_stage_trace import Harness, ROOT
import test_original_inventory_owner as owner_fixtures


class OriginalStageEventTests(unittest.TestCase):
    def setUp(self):
        self.f = owner_fixtures.OriginalOwnerTests('runTest')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        with closing(self.f.connect()) as conn:
            conn.execute('CREATE TABLE job_runs(run_id TEXT PRIMARY KEY,stage TEXT,business_date TEXT,status TEXT,dry_run INTEGER,finished_at TEXT,actual INTEGER,gap INTEGER,stop_reason TEXT,error TEXT)')
            conn.execute("INSERT INTO job_runs(run_id,stage,business_date,status,dry_run) VALUES(?,'inventory','2026-11-03','running',0)",(self.f.holder,))
            conn.commit()

    def job(self):
        with closing(self.f.connect()) as conn:
            return conn.execute('SELECT status,actual,gap,stop_reason FROM job_runs WHERE run_id=?',(self.f.holder,)).fetchone()

    def run_stage(self, execution, *, safe=50, run_id=None, day='2026-11-03', release=None):
        h=Harness(path=ROOT/'bd_orchestrator.py',safe=safe)
        h.ns.update(get_db=self.f.connect, acquire_run_lock=lambda *a,**k: self.fail('event stage reacquired original lock'),
            release_run_lock=bd_db.release_run_lock if release is None else release)
        self.h=h
        with patch.dict('sys.modules',h.modules):
            result=h.ns['stage_inventory'](run_id or self.f.holder,day,False,event_execution=execution)
        return result

    def test_actual_stage_real_http_settles_once_and_reads_inventory_target(self):
        with self.f.host() as bridge:
            execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
            self.assertTrue(self.run_stage(execution))
        self.assertEqual(self.f.f.backend.calls,1)
        self.assertEqual(self.h.business,[])  # No second legacy discovery path.
        self.assertEqual(self.job(),('completed',50,0,'target_met'))
        with self.assertRaises(ValueError):self.f.observe()

    def test_completed_execution_does_not_falsify_inventory_gap(self):
        with self.f.host() as bridge:
            execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
            self.assertFalse(self.run_stage(execution,safe=49))
        self.assertEqual(self.job(),('partial',49,1,'safe_inventory_gap'))
        self.assertEqual(self.h.business,[])
        self.assertEqual(self.f.f.backend.calls,1)

    def test_unknown_backend_keeps_original_lock_without_legacy_fallback(self):
        self.f.f.backend.mode='lost'
        with self.f.host() as bridge:
            execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
            self.assertFalse(self.run_stage(execution))
        self.assertEqual(self.h.finishes[-1][1]['stop_reason'],'inventory_event_unknown_preserved')
        self.assertFalse(self.f.release())
        self.assertEqual(self.f.f.backend.calls,1)
        self.assertEqual(self.h.business,[])

    def test_settled_failure_is_failure_and_may_release(self):
        self.f.f.backend.mode='failed'
        with self.f.host() as bridge:
            execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
            self.assertFalse(self.run_stage(execution))
        self.assertEqual(self.job(),('stopped',0,50,'inventory_event_failed_settled'))
        with self.assertRaises(ValueError):self.f.observe()
        self.assertEqual(self.f.f.backend.calls,1)

    def test_wrong_run_date_database_or_incarnation_never_executes(self):
        bridge=ExistingOwnerBridge(self.f.f.adapter,port=8791,token='a'*40)
        execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
        for kwargs in ({'run_id':'other'},{'day':'2026-11-04'}):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(ValueError,'CONTEXT_MISMATCH'):
                self.run_stage(execution,**kwargs)
        duplicate=self.f.f.root/'copy.sqlite'
        with closing(self.f.connect()) as source,closing(sqlite3.connect(duplicate)) as target:
            source.backup(target)
        with self.assertRaises(ValueError):
            execution.owner_binding(lambda:sqlite3.connect(duplicate),self.f.holder,'2026-11-03')
        self.assertTrue(self.f.release())
        self.assertTrue(bd_db.acquire_run_lock(self.f.day,self.f.holder,capture_owner=True))
        with self.assertRaisesRegex(ValueError,'CONTEXT_MISMATCH'):
            self.run_stage(execution)
        self.assertEqual(self.f.f.backend.calls,0)

    def test_report_ack_loss_preserves_lock_and_cannot_repeat_stage(self):
        with self.f.host() as bridge:
            event=self.f.event()
            execution=OriginalStageEvent(bridge,event,captured_owner=self.f.captured)
            original=bridge.request
            def lose_report(route,value):
                result=original(route,value)
                if route.endswith('/report'):raise ConnectionError('injected lost report ACK')
                return result
            with patch.object(bridge,'request',side_effect=lose_report):
                with self.assertRaises(ConnectionError):self.run_stage(execution)
            self.assertEqual(self.f.authority.check(),self.f.captured)
            with self.assertRaisesRegex(ValueError,'EVENT_REPLAY'):self.run_stage(execution)
        self.assertEqual(self.f.f.backend.calls,1)

    def test_release_failure_cannot_return_success(self):
        with self.f.host() as bridge:
            execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
            with self.assertRaisesRegex(ValueError,'RELEASE_UNVERIFIED'):
                self.run_stage(execution,release=lambda *a,**k:False)
        self.assertEqual(self.f.authority.check(),self.f.captured)
        self.assertEqual(self.f.f.backend.calls,1)
        self.assertEqual(self.job()[0],'running')
        self.assertFalse(any(args[1]=='completed' for args,_ in self.h.finishes))

    def test_job_terminal_write_failure_rolls_back_release(self):
        with closing(self.f.connect()) as conn:
            conn.execute("CREATE TRIGGER fail_terminal BEFORE UPDATE ON job_runs BEGIN SELECT RAISE(ABORT,'injected final write failure'); END")
            conn.commit()
        with self.f.host() as bridge:
            execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
            with self.assertRaisesRegex(sqlite3.IntegrityError,'injected final write'):
                self.run_stage(execution)
        self.assertEqual(self.job()[0],'running')
        self.assertEqual(self.f.authority.check(),self.f.captured)
        self.assertEqual(self.f.f.backend.calls,1)

    def test_event_input_is_frozen_and_arbitrary_consumer_rejected(self):
        bridge=ExistingOwnerBridge(self.f.f.adapter,port=8791,token='a'*40)
        event=self.f.event()
        execution=OriginalStageEvent(bridge,event,captured_owner=self.f.captured)
        before=execution.event
        event['admission']['payload']['owner']='mutated'
        self.assertEqual(before,execution.event)
        with self.assertRaisesRegex(ValueError,'EXACT_ORIGINAL_STAGE_EVENT'):
            self.run_stage(object())
        self.assertEqual(self.f.f.backend.calls,0)

    def test_missing_running_job_rejected_before_event_or_backend(self):
        bridge=ExistingOwnerBridge(self.f.f.adapter,port=8791,token='a'*40)
        execution=OriginalStageEvent(bridge,self.f.event(),captured_owner=self.f.captured)
        with closing(self.f.connect()) as conn:
            conn.execute('DELETE FROM job_runs');conn.commit()
        with self.assertRaisesRegex(ValueError,'RUNNING_JOB_REQUIRED'):self.run_stage(execution)
        self.assertEqual(self.f.session()['tree_state'],'idle')
        self.assertEqual(self.f.f.backend.calls,0)


if __name__=='__main__':unittest.main()
