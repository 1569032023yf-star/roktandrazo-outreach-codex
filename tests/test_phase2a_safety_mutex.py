from __future__ import annotations

import smtplib
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import bd_db
import bd_orchestrator
from development_safety import DevelopmentSafetyError, assert_safe_database_path


class DevelopmentSafetyTests(unittest.TestCase):
    def test_production_database_path_is_rejected(self):
        with self.assertRaises(DevelopmentSafetyError):
            assert_safe_database_path(
                r"C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach\data\bd_leads.db"
            )

    def test_smtp_is_fail_closed(self):
        with self.assertRaises(DevelopmentSafetyError):
            smtplib.SMTP_SSL("smtp.example.test", 465)

    def test_duplicate_job_registration_stops_orchestrator(self):
        with mock.patch("sys.argv", ["bd_orchestrator.py", "--stage", "inventory", "--live"]), \
             mock.patch.object(bd_orchestrator, "start_job_run", return_value=False), \
             mock.patch.object(bd_orchestrator, "stage_inventory") as stage:
            self.assertFalse(bd_orchestrator.main())
            stage.assert_not_called()


class AtomicMutexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "mutex.sqlite"
        self.old_path = bd_db.DB_PATH
        bd_db.DB_PATH = str(self.path)
        bd_db.init_db()

    def tearDown(self):
        bd_db.DB_PATH = self.old_path
        self.temp.cleanup()

    def _race(self, action):
        barrier = threading.Barrier(2)
        results = []

        def contender(name):
            barrier.wait()
            results.append(action(name))

        threads = [threading.Thread(target=contender, args=(f"holder-{i}",)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results

    def test_atomic_lock_has_one_winner_and_owner_release(self):
        results = self._race(lambda holder: bd_db.acquire_run_lock("inventory:2099-01-01", holder))
        self.assertEqual(sorted(results), [False, True])
        locked, owner = bd_db.check_run_lock("inventory:2099-01-01")
        self.assertTrue(locked)
        self.assertFalse(bd_db.release_run_lock("inventory:2099-01-01", "wrong-owner"))
        self.assertTrue(bd_db.release_run_lock("inventory:2099-01-01", owner))

    def test_atomic_job_registration_has_one_winner(self):
        # Fresh concurrent registration.
        results = self._race(
            lambda holder: bd_db.start_job_run(holder, "inventory", "2099-01-01", target=30, dry_run=False)
        )
        self.assertEqual(sorted(results), [False, True])
        self._clear_runs()

        # Two stale-takeover contenders: one winner, one write-free loser.
        now = datetime(2099, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        self._insert_job("stale", (now - timedelta(seconds=7201)).strftime("%Y-%m-%d %H:%M:%S"))
        results = self._race(
            lambda holder: bd_db.start_job_run(
                holder, "inventory", "2099-01-01", dry_run=False, now_utc=now
            )
        )
        self.assertEqual(sorted(results), [False, True])
        conn = sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_runs WHERE status='running'").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT status FROM job_runs WHERE run_id='stale'").fetchone()[0], "failed")
        conn.close()
        self._clear_runs()

        # A fresh duplicate is rejected with no job or state mutation.
        now = datetime(2099, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        self._insert_job("fresh", (now - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S"))
        self.assertFalse(bd_db.start_job_run("loser", "inventory", "2099-01-01", now_utc=now))
        conn = sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT status FROM job_runs WHERE run_id='fresh'").fetchone()[0], "running")
        conn.close()
        self._clear_runs()

        # Exactly 7200 seconds remains fresh; 7201 seconds is stale, in UTC.
        now = datetime(2099, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        self._insert_job("boundary", (now - timedelta(seconds=7200)).strftime("%Y-%m-%d %H:%M:%S"))
        self.assertFalse(bd_db.start_job_run("at-boundary", "inventory", "2099-01-01", now_utc=now))
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE job_runs SET started_at=? WHERE run_id='boundary'",
                     ((now - timedelta(seconds=7201)).strftime("%Y-%m-%d %H:%M:%S"),))
        conn.commit()
        conn.close()
        self.assertTrue(bd_db.start_job_run("past-boundary", "inventory", "2099-01-01", now_utc=now))
        self._clear_runs()

        # A replacement INSERT failure rolls stale cleanup back in the same transaction.
        now = datetime(2099, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        self._insert_job("stale", (now - timedelta(seconds=7201)).strftime("%Y-%m-%d %H:%M:%S"))
        self._insert_job("collision", (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                         status="completed", stage="post-send", business_date="2098-12-31")
        with self.assertRaises(sqlite3.IntegrityError):
            bd_db.start_job_run("collision", "inventory", "2099-01-01", now_utc=now)
        conn = sqlite3.connect(self.path)
        stale = conn.execute("SELECT status,stop_reason,finished_at FROM job_runs WHERE run_id='stale'").fetchone()
        self.assertEqual(stale, ("running", None, None))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_runs WHERE stage='inventory' AND business_date='2099-01-01'").fetchone()[0], 1)
        conn.close()

    def _clear_runs(self):
        conn = sqlite3.connect(self.path)
        conn.execute("DELETE FROM job_runs")
        conn.execute("DELETE FROM system_state")
        conn.commit()
        conn.close()

    def _insert_job(self, run_id, started_at, status="running", stage="inventory", business_date="2099-01-01"):
        conn = sqlite3.connect(self.path)
        conn.execute(
            """INSERT INTO job_runs
               (run_id,stage,business_date,started_at,status,target,current_step,process_id,dry_run)
               VALUES (?,?,?,?,?,0,'test',0,0)""",
            (run_id, stage, business_date, started_at, status),
        )
        conn.commit()
        conn.close()


if __name__ == "__main__":
    unittest.main()
