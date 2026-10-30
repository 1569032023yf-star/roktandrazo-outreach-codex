"""Independent cancellation-cost settlement failure contracts (offline only)."""
import json
import unittest
import test_cancellation_cost as fixtures
from autonomy.growth_ledger import GrowthError, GrowthLedger
from autonomy.single_slot_adapter import AdapterError
from autonomy.lock_recovery import exclusive_lock
from test_growth_ledger import signed, amounts, T


class CancellationSettlementTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CancellationCostTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.c = self.fixture.case

    def prepare(self):
        admission, journal, fields, cost, cost_id = self.fixture.prepare()
        result = self.c.adapter.reserve_cancellation(
            admission, signed('offline_cancel_request', T+10, **fields), cost_request=cost)
        self.assertEqual(result['outcome'], 'RESERVED_RECONCILE_ONLY')
        binding = dict(cost['payload']['claim_binding'])
        binding.pop('inventory_id')
        return admission, journal, cost_id, binding

    def receipt(self, binding, **changes):
        fields = dict(binding, outcome='known', externally_reconciled=True, actual=amounts(0))
        fields.update(changes)
        return signed('budget_receipt', T+10, **fields)

    def row(self, cost_id):
        return next(row for row in self.fixture.rows() if row['id'] == cost_id)

    def test_fee_settlement_commit_failure_and_ack_loss_reopen(self):
        for phase in ('before_commit', 'after_commit'):
            with self.subTest(phase=phase):
                fixture = CancellationSettlementTests(); fixture.setUp()
                try:
                    c = fixture.c
                    with exclusive_lock(c.runtime):
                        admission, journal, cost_id, binding = fixture.prepare()
                        journal_bytes = journal.path.read_bytes()
                        receipt = fixture.receipt(binding)
                        c.budget.fault = lambda stage: (_ for _ in ()).throw(OSError('fixture')) if stage == phase else None
                        with fixture.assertRaisesRegex(GrowthError, 'STORAGE_OUTCOME_UNVERIFIED'):
                            c.budget.settle(receipt, now=T+10)
                        c.budget.fault = lambda stage: None
                        c.budget = GrowthLedger(c.budget.path, consumer=c.budget.consumer)
                        c.adapter.budget = c.budget
                        row = fixture.row(cost_id)
                        fixture.assertEqual(row['state'], 'reserved' if phase == 'before_commit' else 'settled')
                        fixture.assertEqual(json.loads(row['charged']), amounts() if phase == 'before_commit' else amounts(0))
                        fixture.assertEqual(c.budget.settle(receipt, now=T+10), 'SETTLED' if phase == 'before_commit' else 'DUPLICATE')
                        fixture.assertEqual(c.budget.settle(receipt, now=T+10), 'DUPLICATE')
                        c.adapter.reconcile(admission, **c.backend.receipts)
                        fixture.assertEqual(journal.path.read_bytes(), journal_bytes)
                        fixture.assertEqual(c.backend.calls, 1)
                finally:
                    fixture.doCleanups()

    def test_unknown_fee_receipt_never_refunds_and_requires_separate_known_receipt(self):
        c = self.c
        with exclusive_lock(c.runtime):
            admission, journal, cost_id, binding = self.prepare()
            journal_bytes = journal.path.read_bytes()
            unknown = self.receipt(binding, outcome='unknown', actual=None, externally_reconciled=False)
            self.assertEqual(c.budget.settle(unknown, now=T+10), 'UNKNOWN_RESERVED')
            self.assertEqual(c.budget.settle(unknown, now=T+10), 'DUPLICATE')
            c.adapter.reconcile(admission, **c.backend.receipts)
            row = self.row(cost_id)
            self.assertEqual(row['state'], 'unknown')
            self.assertEqual(row['charged'], row['amount'])
            self.assertEqual(c.budget.settle(self.receipt(binding), now=T+10), 'SETTLED')
            self.assertEqual(journal.path.read_bytes(), journal_bytes)
            self.assertEqual(c.backend.calls, 1)

    def test_fee_receipt_conflicts_do_not_change_either_reservation_or_journal(self):
        c = self.c
        with exclusive_lock(c.runtime):
            admission, journal, cost_id, binding = self.prepare()
            before = self.fixture.rows(); journal_bytes = journal.path.read_bytes()
            mutations = dict(run_id='wrong', claim_token_hash='0'*64,
                original_request_id='0'*64, cancel_cost_protocol='rokt.offline-cancel-cost.v2',
                cancel_identity='0'*64, epoch=True, externally_reconciled=False)
            for key, value in mutations.items():
                with self.subTest(field=key), self.assertRaises(GrowthError):
                    c.budget.settle(self.receipt(binding, **{key:value}), now=T+10)
                self.assertEqual(self.fixture.rows(), before)
                self.assertEqual(journal.path.read_bytes(), journal_bytes)
            c.adapter.reconcile(admission, **c.backend.receipts)
            self.assertEqual(self.row(cost_id)['state'], 'reserved')
            self.assertEqual(c.backend.calls, 1)

    def test_original_settlement_failure_after_fee_settled_keeps_recovery_fence(self):
        for phase in ('before_commit', 'after_commit'):
            with self.subTest(phase=phase):
                fixture = CancellationSettlementTests(); fixture.setUp()
                try:
                    c = fixture.c
                    with exclusive_lock(c.runtime):
                        admission, journal, cost_id, binding = fixture.prepare()
                        journal_bytes = journal.path.read_bytes()
                        fee_receipt = fixture.receipt(binding)
                        fixture.assertEqual(c.budget.settle(fee_receipt, now=T+10), 'SETTLED')
                        original_settle = c.budget.settle
                        def faulted_settle(envelope, *, now):
                            c.budget.fault = lambda stage: (_ for _ in ()).throw(OSError('fixture')) if stage == phase else None
                            try:
                                return original_settle(envelope, now=now)
                            finally:
                                c.budget.fault = lambda stage: None
                        c.budget.settle = faulted_settle
                        with fixture.assertRaisesRegex(GrowthError, 'STORAGE_OUTCOME_UNVERIFIED'):
                            c.adapter.reconcile(admission, **c.backend.receipts)
                        c.budget.settle = original_settle
                        # Slot commit succeeded, but no joint acknowledgement:
                        # neither fee settlement nor terminal slot clears fence.
                        lock = json.loads((c.runtime/'supervisor.lock').read_text(encoding='utf-8'))
                        fixture.assertEqual(lock['tree_state'], 'unverified')
                        fixture.assertEqual(c.slots.snapshot()[0][2], 'completed')
                        fixture.assertEqual(fixture.row(cost_id)['state'], 'settled')
                        fixture.assertEqual(json.loads(fixture.row(cost_id)['charged']), amounts(0))
                        fixture.assertEqual(journal.path.read_bytes(), journal_bytes)
                        result = c.adapter.reconcile(admission, **c.backend.receipts)
                        fixture.assertEqual(result['budget_result'], 'SETTLED' if phase == 'before_commit' else 'DUPLICATE')
                        fixture.assertEqual(c.budget.settle(fee_receipt, now=T+10), 'DUPLICATE')
                        fixture.assertEqual(c.backend.calls, 1)
                finally:
                    fixture.doCleanups()

    def test_settled_fee_and_cancel_ack_cannot_replace_drained_terminal(self):
        c = self.c
        with exclusive_lock(c.runtime):
            admission, journal, cost_id, binding = self.prepare()
            journal_bytes = journal.path.read_bytes()
            self.assertEqual(c.budget.settle(self.receipt(binding), now=T+10), 'SETTLED')
            before = self.fixture.rows()
            ack = signed('receipt', T+10, **c.common,
                token=c.backend.receipts['slot_receipt']['payload']['token'],
                state='completed', cancel_ack=True, external_drained=False)
            with self.assertRaisesRegex(AdapterError, 'BINDING_MISMATCH'):
                c.adapter.reconcile(admission, ack, c.backend.receipts['budget_receipt'])
            self.assertEqual(self.fixture.rows(), before)
            self.assertEqual(c.slots.snapshot()[0][2], 'unknown')
            self.assertEqual(journal.path.read_bytes(), journal_bytes)
            c.adapter.reconcile(admission, **c.backend.receipts)
            self.assertEqual(self.row(cost_id)['state'], 'settled')
            self.assertEqual(c.backend.calls, 1)


if __name__ == '__main__':
    unittest.main()
