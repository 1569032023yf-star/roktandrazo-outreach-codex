"""Isolated SQLite design experiment, not a production ledger implementation."""
import sqlite3
import tempfile
import unittest
from pathlib import Path


def reserve(connection, slot, units, cap):
    """Model atomic slot + reservation; all test callers use a temporary DB."""
    connection.execute('BEGIN IMMEDIATE')
    try:
        if connection.execute('SELECT 1 FROM slots WHERE slot=?', (slot,)).fetchone():
            connection.rollback()
            return 'NO_REPLAY'
        total = connection.execute('SELECT coalesce(sum(units),0) FROM slots').fetchone()[0]
        if total + units > cap:
            connection.rollback()
            return 'CAP_REACHED'
        connection.execute('INSERT INTO slots VALUES (?, ?, ?)', (slot, 'unknown', units))
        connection.commit()
        return 'RESERVED_NOT_DISPATCHED'
    except BaseException:
        connection.rollback()
        raise


class TemporaryLedgerModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rokt-offline-ledger-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'model.sqlite'
        self.a = self.connect()
        self.a.execute('CREATE TABLE slots(slot TEXT PRIMARY KEY, state TEXT NOT NULL, units INTEGER NOT NULL CHECK(units>0))')
        self.a.commit()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=0)
        self.addCleanup(c.close)
        return c

    def test_commit_then_restart_retains_unknown_and_budget(self):
        self.assertEqual(reserve(self.a, 'day1-slot1', 6, 10), 'RESERVED_NOT_DISPATCHED')
        self.a.close()
        b = self.connect()
        self.assertEqual(reserve(b, 'day1-slot1', 6, 10), 'NO_REPLAY')
        self.assertEqual(reserve(b, 'day1-slot2', 5, 10), 'CAP_REACHED')
        self.assertEqual(b.execute('SELECT state,units FROM slots').fetchone(), ('unknown', 6))

    def test_uncommitted_claim_rolls_back_on_connection_loss(self):
        self.a.execute('BEGIN IMMEDIATE')
        self.a.execute("INSERT INTO slots VALUES ('slot', 'unknown', 5)")
        self.a.close()
        b = self.connect()
        self.assertEqual(b.execute('SELECT count(*) FROM slots').fetchone()[0], 0)
        self.assertEqual(reserve(b, 'slot', 5, 10), 'RESERVED_NOT_DISPATCHED')

    def test_competing_writer_cannot_overreserve(self):
        b = self.connect()
        self.a.execute('BEGIN IMMEDIATE')
        self.a.execute("INSERT INTO slots VALUES ('first', 'unknown', 6)")
        with self.assertRaises(sqlite3.OperationalError):
            reserve(b, 'second', 6, 10)
        self.a.commit()
        self.assertEqual(reserve(b, 'second', 6, 10), 'CAP_REACHED')
        self.assertEqual(b.execute('SELECT sum(units) FROM slots').fetchone()[0], 6)

    def test_constraint_failure_has_no_partial_claim(self):
        with self.assertRaises(sqlite3.IntegrityError):
            reserve(self.a, 'invalid', -1, 10)
        self.assertEqual(self.a.execute('SELECT count(*) FROM slots').fetchone()[0], 0)
        self.assertEqual(reserve(self.a, 'valid', 1, 10), 'RESERVED_NOT_DISPATCHED')


if __name__ == '__main__':
    unittest.main()
