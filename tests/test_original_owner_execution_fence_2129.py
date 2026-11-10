import unittest
from unittest.mock import Mock, patch
from autonomy.single_slot_adapter import SingleSlotAdapter, OriginalOwnerSlotAdapter, AdapterError
from autonomy.inventory_event_bridge import ExistingOwnerBridge


class OwnerExecutionFenceTests(unittest.TestCase):
    def test_execute_paths_do_not_touch_state(self):
        adapter = object.__new__(OriginalOwnerSlotAdapter)
        adapter.original_owner = Mock()
        adapter.slots = Mock()
        adapter.budget = Mock()
        adapter.backend = Mock()
        expected = {'outcome': 'UNKNOWN_RECONCILE_ONLY', 'production_execution': False}
        with patch.object(adapter, '_admission', side_effect=AssertionError('admission invoked')):
            for invoke in (adapter.execute, lambda *a: SingleSlotAdapter.execute(adapter, *a),
                           lambda *a: SingleSlotAdapter._execute_impl(adapter, *a)):
                self.assertEqual(invoke({}, {}, {}, {}), expected)
        for dependency in (adapter.original_owner, adapter.slots, adapter.budget, adapter.backend):
            self.assertEqual(dependency.mock_calls, [])

    def test_preparation_and_bridge_reject_before_effects(self):
        adapter = object.__new__(OriginalOwnerSlotAdapter)
        adapter.original_owner = Mock()
        with self.assertRaisesRegex(AdapterError, 'ORIGINAL_OWNER_EXECUTION_DISABLED'):
            adapter.prepare_event({})
        bridge = object.__new__(ExistingOwnerBridge)
        bridge.adapter = adapter
        with patch.object(adapter, '_lock', side_effect=AssertionError('lock invoked')):
            with self.assertRaisesRegex(AdapterError, 'ORIGINAL_OWNER_EXECUTION_DISABLED'):
                bridge.consume({})
        self.assertEqual(adapter.original_owner.mock_calls, [])

    def test_plain_single_slot_is_not_guarded(self):
        adapter = object.__new__(SingleSlotAdapter)
        adapter.target = None
        with patch.object(adapter, '_execute_impl', return_value={'sentinel': True}) as invoke:
            self.assertEqual(adapter.execute({}, {}, {}, {}), {'sentinel': True})
            invoke.assert_called_once()

if __name__ == '__main__': unittest.main()
