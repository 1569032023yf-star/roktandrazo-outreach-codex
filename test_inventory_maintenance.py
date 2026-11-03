"""Actual original run-lock integration against isolated DB; no production acceptance."""
import sqlite3
from contextlib import closing
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import bd_db
from autonomy import inventory_maintenance as m


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='u1-maintenance-');self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'authority.db'
        self.conn=sqlite3.connect(self.path);self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)');self.conn.commit()
        self.binding=dict(inventory_id='1784775229336',operation_id='a'*64,source_commit='b'*40,manifest_sha256='c'*64,lease_nonce='d'*64)
        self.patch=patch.object(bd_db,'get_db',lambda:sqlite3.connect(self.path));self.patch.start();self.addCleanup(self.patch.stop)

    def test_original_inventory_blocked_across_dates_until_verified_release(self):
        m.acquire(self.conn,self.binding)
        for day in ('inventory:2026-11-02','inventory:2026-11-03'):
            self.assertFalse(bd_db.acquire_run_lock(day,'original-inventory',stale_after_seconds=-1))
        with self.assertRaisesRegex(ValueError,'FINAL_VERIFICATION'):m.release_verified(self.conn,self.binding)
        m.assert_held(self.conn,self.binding)
        m.release_verified(self.conn,self.binding,final_verified=True)
        self.assertTrue(bd_db.acquire_run_lock('inventory:2026-11-03','original-inventory'))
        with self.assertRaisesRegex(ValueError,'REPLAY'):m.acquire(self.conn,self.binding)

    def test_active_original_lock_rejects_maintenance_even_if_stale(self):
        self.assertTrue(bd_db.acquire_run_lock('inventory:2000-01-01','unknown-original'))
        with self.assertRaisesRegex(ValueError,'NOT_QUIESCENT'):m.acquire(self.conn,self.binding)
        self.assertFalse(m.blocked(self.conn))

    def test_restart_and_wrong_owner_preserve_exclusion(self):
        m.acquire(self.conn,self.binding)
        with closing(sqlite3.connect(self.path)) as restarted:
            m.assert_held(restarted,self.binding)
            other=dict(self.binding,lease_nonce='e'*64)
            with self.assertRaisesRegex(ValueError,'LOST'):m.release_verified(restarted,other,final_verified=True)
            self.assertTrue(m.blocked(restarted))
        self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-04','original'))

    def test_malformed_marker_fails_closed_and_no_tombstone_replay(self):
        self.conn.execute('INSERT INTO system_config VALUES(?,?,NULL)',(m.KEY,'malformed'));self.conn.commit()
        self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-02','original'))
        with self.assertRaisesRegex(ValueError,'PENDING'):m.acquire(self.conn,self.binding)

    def test_commit_failure_does_not_release_existing_marker(self):
        m.acquire(self.conn,self.binding)
        class FailedCommit:
            def execute(_, *a):return self.conn.execute(*a)
            def rollback(_):self.conn.rollback()
            def commit(_):raise OSError('injected commit failure')
        with self.assertRaises(OSError):m.release_verified(FailedCommit(),self.binding,final_verified=True)
        m.assert_held(self.conn,self.binding)

    def test_original_inventory_single_authority_across_dates(self):
        self.assertTrue(bd_db.acquire_run_lock('inventory:2026-11-02','original'))
        self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-03','other'))
        self.assertFalse(bd_db.release_run_lock('inventory:2026-11-02','other'))
        self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-03','other'))
        self.assertTrue(bd_db.release_run_lock('inventory:2026-11-02','original'))
        self.assertTrue(bd_db.acquire_run_lock('inventory:2026-11-03','other'))

    def test_original_inventory_never_reclaims_stale_or_same_holder(self):
        day='inventory:2000-01-01'
        self.assertTrue(bd_db.acquire_run_lock(day,'original'))
        self.assertFalse(bd_db.acquire_run_lock(day,'original',stale_after_seconds=-1))
        self.assertFalse(bd_db.acquire_run_lock(day,'other',stale_after_seconds=-1))

    def test_malformed_inventory_lock_is_unknown_not_idle(self):
        for value in (None,'','malformed'):
            with self.subTest(value=value):
                self.conn.execute('DELETE FROM system_config')
                self.conn.execute('INSERT INTO system_config VALUES(?,?,NULL)',
                    ('run_lock:daily_outreach:inventory:2026-11-02',value))
                self.conn.commit()
                self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-03','original',stale_after_seconds=-1))

    def test_original_inventory_process_exit_preserves_unknown_lock(self):
        import subprocess,sys
        code="""import os,sqlite3,sys
import bd_db
bd_db.get_db=lambda:sqlite3.connect(sys.argv[1])
assert bd_db.acquire_run_lock('inventory:2026-11-02','dead-owner')
os._exit(29)
"""
        result=subprocess.run([sys.executable,'-B','-c',code,str(self.path)],
            cwd=Path(__file__).resolve().parent,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,29,result.stderr.decode(errors='replace'))
        self.assertFalse(bd_db.acquire_run_lock('inventory:2026-11-03','restarted',stale_after_seconds=-1))
        with self.assertRaisesRegex(ValueError,'NOT_QUIESCENT'):m.acquire(self.conn,self.binding)

    def test_concurrent_original_inventory_dates_admit_only_one(self):
        import concurrent.futures,threading
        barrier=threading.Barrier(2)
        def acquire(day):
            barrier.wait(timeout=10)
            return bd_db.acquire_run_lock(day,day)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(acquire,('inventory:2026-11-02','inventory:2026-11-03')))
        self.assertEqual(sum(results),1)

    def test_noninventory_expiry_contract_is_unchanged(self):
        self.assertTrue(bd_db.acquire_run_lock('outreach:2026-11-03','old'))
        self.assertTrue(bd_db.acquire_run_lock('outreach:2026-11-03','new',stale_after_seconds=-1))

    def test_actual_inventory_entry_preserves_lock_after_unknown_exception(self):
        from tests.test_inventory_stage_trace import Harness,ROOT
        for stage in ('places','website','postprocess','linked'):
            with self.subTest(stage=stage):
                h=Harness(path=ROOT/'bd_orchestrator.py',crash=stage)
                with self.assertRaises(LookupError):h.run()
                self.assertEqual(h.released,0)

    def test_actual_inventory_entry_system_exit_preserves_lock(self):
        from tests.test_inventory_stage_trace import Harness,ROOT
        h=Harness(path=ROOT/'bd_orchestrator.py')
        def exit_now():raise SystemExit(31)
        h.ns['_resolve_active_discovery_state']=exit_now
        with self.assertRaises(SystemExit):h.run()
        self.assertEqual(h.released,0)

    def test_actual_inventory_known_return_releases_without_second_execution(self):
        from tests.test_inventory_stage_trace import Harness,ROOT
        for options in ({},{'state_error':'ACTIVE_STATE_NOT_SET'},{'provider_error':True}):
            with self.subTest(options=options):
                h=Harness(path=ROOT/'bd_orchestrator.py',**options)
                h.run()
                self.assertEqual(h.released,1)
                self.assertLessEqual(sum(name=='places' for name,_ in h.business),1)


if __name__=='__main__':unittest.main()
