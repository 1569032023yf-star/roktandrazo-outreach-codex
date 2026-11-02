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


if __name__=='__main__':unittest.main()
