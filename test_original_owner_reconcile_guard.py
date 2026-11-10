"""Offline proof that unbound original-owner reconciliation touches no stores."""
from contextlib import closing
import sqlite3
import unittest
from unittest.mock import patch

from autonomy.single_slot_adapter import SingleSlotAdapter
from test_original_inventory_owner import OriginalOwnerTests


class OriginalOwnerReconcileGuardTests(unittest.TestCase):
    def test_normal_and_direct_base_calls_preserve_three_real_databases(self):
        fixture = OriginalOwnerTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        adapter = fixture.f.adapter
        paths = (fixture.f.slots.path, fixture.f.budget.path, fixture.path)

        def dumps():
            with closing(sqlite3.connect(paths[0])) as slots, \
                 closing(sqlite3.connect(paths[1])) as budget, \
                 closing(sqlite3.connect(paths[2])) as owner:
                return tuple(tuple(db.iterdump()) for db in (slots, budget, owner))

        before = dumps()
        with patch.object(adapter, '_admission', side_effect=AssertionError('admission read')), \
             patch.object(adapter, '_verify', side_effect=AssertionError('receipt read')), \
             patch.object(fixture.authority, 'receipt_binding', side_effect=AssertionError('owner read')), \
             patch.object(fixture.authority, 'mark_tree', side_effect=AssertionError('fence write')), \
             patch.object(fixture.f.slots, 'reconcile', side_effect=AssertionError('slot write')), \
             patch.object(fixture.f.budget, 'settle', side_effect=AssertionError('budget write')), \
             patch('autonomy.single_slot_adapter.sqlite3.connect', side_effect=AssertionError('database opened')):
            for call in (adapter.reconcile,
                         lambda *args: SingleSlotAdapter.reconcile(adapter, *args)):
                self.assertEqual(call({}, {}, {}),
                                 {'outcome': 'UNKNOWN_RECONCILE_ONLY', 'production_execution': False})
        self.assertEqual(before, dumps())
        self.assertEqual(fixture.f.backend.calls, 0)


if __name__ == '__main__':
    unittest.main()
