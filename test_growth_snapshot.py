from contextlib import closing, contextmanager
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from autonomy.growth_ledger import GrowthLedger
from autonomy.growth_snapshot import inspect_snapshot, MAX_SNAPSHOT_BYTES


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.sqlite'
        GrowthLedger(self.path).initialize()

    @contextmanager
    def edit(self):
        with closing(sqlite3.connect(self.path)) as conn:
            with conn:
                yield conn

    def inspect(self, data=None):
        data = self.path.read_bytes() if data is None else data
        return inspect_snapshot(data, hashlib.sha256(data).hexdigest())

    def test_compatible_image_and_source_unchanged(self):
        data = self.path.read_bytes()
        result = self.inspect(data)
        self.assertTrue(result['schema_compatible'])
        self.assertFalse(result['reconciliation_required'])
        self.assertFalse(result['migration_authorized'])
        self.assertFalse(result['production_ready'])
        self.assertEqual(self.path.read_bytes(), data)

    def test_preserves_reserved_unknown_overrun(self):
        with self.edit() as conn:
            for index, state in enumerate(('reserved', 'unknown', 'overrun', 'settled')):
                conn.execute('INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (str(index), '2026-10-27', 'fixture-run', '{}', '{}', state, 'fixture-hash', None, None, None))
        data = self.path.read_bytes()
        result = self.inspect(data)
        self.assertEqual(result['unresolved_counts'], {'reserved': 1, 'unknown': 1, 'overrun': 1})
        self.assertTrue(result['reconciliation_required'])
        self.assertEqual(self.path.read_bytes(), data)

    def test_path_hash_and_size_denied(self):
        self.assertEqual(inspect_snapshot(str(self.path), '0'*64)['reason'], 'INVALID_SNAPSHOT_SIZE_OR_TYPE')
        self.assertEqual(inspect_snapshot(self.path.read_bytes(), '0'*64)['reason'], 'HASH_MISMATCH')
        self.assertEqual(self.inspect(b'x'*(MAX_SNAPSHOT_BYTES+1))['reason'], 'INVALID_SNAPSHOT_SIZE_OR_TYPE')

    def test_corrupt_and_wal_dependent_images_denied(self):
        self.assertFalse(self.inspect(b'x'*200)['schema_compatible'])
        data = bytearray(self.path.read_bytes()); data[18:20] = b'\x02\x02'
        self.assertEqual(self.inspect(bytes(data))['reason'], 'STANDALONE_IMAGE_REQUIRED')
        self.assertFalse(self.inspect(self.path.read_bytes()[:200])['schema_compatible'])

    def test_old_and_extra_schema_denied(self):
        with self.edit() as conn: conn.execute('PRAGMA user_version=1')
        self.assertEqual(self.inspect()['reason'], 'INCOMPATIBLE_SCHEMA')
        with self.edit() as conn:
            conn.execute('PRAGMA user_version=2'); conn.execute('CREATE VIEW extra AS SELECT 1')
        self.assertEqual(self.inspect()['reason'], 'INCOMPATIBLE_SCHEMA')

    def test_unknown_state_is_not_zero_unresolved(self):
        with self.edit() as conn:
            conn.execute('INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?,?,?)',
                ('x','day','run','{}','{}','unexpected','hash',None,None,None))
        result = self.inspect()
        self.assertEqual(result['reason'], 'UNKNOWN_RESERVATION_STATE')
        self.assertIsNone(result['unresolved_counts'])

    def test_internal_prefix_lookalike_and_extra_bytes_denied(self):
        with self.edit() as conn:
            conn.execute('CREATE TABLE sqliteXextra(value TEXT)')
        self.assertEqual(self.inspect()['reason'], 'INCOMPATIBLE_SCHEMA')
        self.assertEqual(self.inspect(self.path.read_bytes()+b'x')['reason'], 'INCOMPLETE_OR_NONCANONICAL_IMAGE')

    def test_vm_budget_fail_closed(self):
        with self.edit() as conn:
            conn.executemany('INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?,?,?)',
                [(str(i),'day','run','{}','{}','reserved','hash',None,None,None) for i in range(1000)])
        with patch('autonomy.growth_snapshot.MAX_VM_STEPS', 0):
            result = self.inspect()
        self.assertEqual(result['reason'], 'INSPECTION_BUDGET_EXCEEDED')


if __name__ == '__main__': unittest.main()
