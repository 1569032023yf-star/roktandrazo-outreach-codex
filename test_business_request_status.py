"""Offline request creation/execution/status/settlement integration checks.
测试临时账本和签名夹具；没有真实 Provider 或生产费用。
"""
from contextlib import closing
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch

from autonomy.growth_ledger import digest
from autonomy.lock_recovery import exclusive_lock, mark_tree
from autonomy.single_slot_adapter import AdapterError
import test_single_slot_adapter as fixtures
from test_growth_ledger import T, amounts, signed


class BusinessRequestStatusTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SingleSlotTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def read(self, admission):
        return self.f.adapter.request_status(admission)

    def test_not_recorded_is_not_zero_cost_and_query_has_no_backend_dependency(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            self.f.adapter.backend = None
            status = self.read(admission)
            self.assertEqual(status['business_state'], 'NOT_RECORDED')
            self.assertIsNone(status['resource_budget'])
            self.assertIsNone(status['provider_billing']['billed_amount'])
            self.assertIsNone(status['provider_billing']['currency'])
            self.assertEqual(status['provider_billing']['status'], 'CONTRACT_MISSING')
        self.assertEqual(self.f.slots.snapshot(), [])

    def test_pending_request_does_not_authorize_execution(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            self.f.slots.admit_due('one', T+10, self.f.plan, now=T+10, epoch=1, owner='owner')
            status = self.read(admission)
            self.assertEqual(status['slot_state'], 'PENDING')
            self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            for key in ('replay_authorized', 'allow_dispatch', 'allow_cancel_dispatch', 'production_execution'):
                self.assertIs(status[key], False)
            self.assertEqual(self.f.backend.calls, 0)

    def test_reservation_without_claim_remains_unknown_and_fully_charged(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            self.f.budget.reserve(self.f.request, now=T+10)
            status = self.read(admission)
            self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            budget = status['resource_budget']
            self.assertEqual(budget['state'], 'RESERVED')
            self.assertEqual(budget['charged'], amounts())
            self.assertIsNone(budget['actual'])
            self.assertIsNone(budget['receipt_digest'])

    def test_success_and_failure_require_both_durable_receipts(self):
        for mode, expected in (('success', 'COMPLETED'), ('failed', 'FAILED')):
            with self.subTest(mode=mode):
                f = fixtures.SingleSlotTests('runTest'); f.setUp()
                try:
                    f.backend.mode = mode
                    with exclusive_lock(f.runtime):
                        admission = f.admission()
                        self.assertEqual(f.run_one(admission)['outcome'], expected)
                        first = f.adapter.request_status(admission)
                        self.assertEqual(first['business_state'], 'UNKNOWN_RECONCILE_ONLY')
                        self.assertEqual(first['resource_budget']['state'], 'SETTLED')
                        self.assertEqual(first['resource_budget']['actual'], amounts())
                        self.assertIsNone(first['provider_billing']['billed_amount'])
                        f.adapter.reconcile(admission, **f.backend.receipts)
                        self.assertEqual(f.adapter.request_status(admission), first)
                        self.assertEqual(f.backend.calls, 1)
                finally:
                    f.doCleanups()

    def test_unknown_readback_and_later_reconciliation_never_repeat_backend(self):
        self.f.backend.mode = 'lost'
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            self.assertEqual(self.f.run_one(admission)['outcome'], 'UNKNOWN_RECONCILE_ONLY')
            for _ in range(2):
                status = self.read(admission)
                self.assertEqual(status['slot_state'], 'UNKNOWN')
                self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
                self.assertIsNone(status['resource_budget']['actual'])
            self.f.adapter.reconcile(admission, **self.f.backend.receipts)
            self.assertEqual(self.read(admission)['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.f.backend.calls, 1)

    def test_terminal_slot_with_failed_settlement_is_unknown_until_repaired(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            with patch.object(self.f.budget, 'settle', side_effect=OSError('offline injected failure')):
                self.assertEqual(self.f.run_one(admission)['outcome'], 'UNKNOWN_RECONCILE_ONLY')
            status = self.read(admission)
            self.assertEqual(status['slot_state'], 'COMPLETED')
            self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertIsNone(status['resource_budget']['actual'])
            self.f.adapter.reconcile(admission, **self.f.backend.receipts)
            self.assertEqual(self.read(admission)['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.f.backend.calls, 1)

    def test_known_zero_resource_usage_is_distinct_from_unknown_monetary_cost(self):
        self.f.backend.mode = 'lost'
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission(); self.f.run_one(admission)
            payload = self.f.backend.receipts['budget_receipt']['payload']
            receipt = signed('budget_receipt', T+10, **self.f.common,
                claim_token_hash=payload['claim_token_hash'], outcome='known',
                actual=amounts(0), externally_reconciled=True)
            self.f.adapter.reconcile(admission, self.f.backend.receipts['slot_receipt'], receipt)
            status = self.read(admission)
            self.assertEqual(status['resource_budget']['actual'], amounts(0))
            self.assertIsNone(status['provider_billing']['billed_amount'])

    def test_overrun_is_queryable_but_cannot_be_reported_as_completed(self):
        self.f.backend.mode = 'lost'
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission(); self.f.run_one(admission)
            payload = self.f.backend.receipts['budget_receipt']['payload']
            receipt = signed('budget_receipt', T+10, **self.f.common,
                claim_token_hash=payload['claim_token_hash'], outcome='known',
                actual=amounts(2), externally_reconciled=True)
            self.f.adapter.reconcile(admission, self.f.backend.receipts['slot_receipt'], receipt)
            status = self.read(admission)
            self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(status['resource_budget']['state'], 'OVERRUN')
            self.assertEqual(status['resource_budget']['actual'], amounts(2))
            mark_tree('verified_closed', binding=self.f.adapter._tree_binding(self.f.common),
                      claim_hash=digest(self.f.backend.operation['token']))  # Fixture cleanup only.

    def test_reads_are_byte_preserving_and_do_not_return_claim_secrets(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission(); self.f.run_one(admission)
            files = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in self.f.root.rglob('*') if p.is_file()}
            before = files()
            token = self.f.backend.operation['token']
            with patch.object(self.f.budget, 'tx', side_effect=AssertionError('write transaction')), \
                 patch.object(self.f.backend, 'execute_once', side_effect=AssertionError('dispatch')):
                status = self.read(admission)
            self.assertEqual(files(), before)
            self.assertNotIn(token, json.dumps(status))

    def test_missing_budget_is_not_created_and_bad_schema_is_rejected(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            path = self.f.root/'budget.sqlite'
            saved = self.f.root/'saved.sqlite'; path.rename(saved)
            with self.assertRaises((AdapterError, FileNotFoundError)):
                self.read(admission)
            self.assertFalse(path.exists())
            saved.rename(path)
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('PRAGMA user_version=99'); conn.commit()
            with self.assertRaisesRegex(AdapterError, 'SCHEMA_REJECTED'):
                self.read(admission)

    def test_foreign_request_binding_and_claim_hash_are_rejected(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission(); self.f.run_one(admission)
            with self.f.budget.tx() as conn:
                conn.execute('UPDATE reservations SET claim_hash=?', (digest('foreign'),))
            with self.assertRaisesRegex(AdapterError, 'CLAIM_CONFLICT'):
                self.read(admission)
            with self.f.budget.tx() as conn:
                conn.execute('UPDATE reservations SET binding=?', ('{}',))
            with self.assertRaisesRegex(AdapterError, 'BUDGET_CONFLICT'):
                self.read(admission)

    def test_unexpected_slot_or_budget_schema_objects_are_rejected(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            for path in (self.f.slots.path, self.f.budget.path):
                with self.subTest(path=path):
                    with closing(sqlite3.connect(path)) as conn:
                        conn.execute('CREATE VIEW unexpected AS SELECT 1'); conn.commit()
                    with self.assertRaisesRegex(AdapterError, 'SCHEMA_REJECTED'):
                        self.read(admission)
                    with closing(sqlite3.connect(path)) as conn:
                        conn.execute('DROP VIEW unexpected'); conn.commit()
    def test_invalid_signature_and_owner_loss_reject_status(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            tampered = dict(admission, signature='invalid')
            with self.assertRaises(AdapterError):
                self.read(tampered)
        with self.assertRaises(AdapterError):
            self.read(admission)

    def test_corrupt_accounting_cannot_invent_settlement_or_release_reservations(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            self.f.budget.reserve(self.f.request, now=T+10)
            with self.f.budget.tx() as conn:
                conn.execute('UPDATE reservations SET charged=?', (json.dumps(amounts(0)),))
            with self.assertRaisesRegex(AdapterError, 'ACCOUNTING_CONFLICT'):
                self.read(admission)
            with self.f.budget.tx() as conn:
                conn.execute("UPDATE reservations SET state='settled'")
            with self.assertRaisesRegex(AdapterError, 'SETTLEMENT_CONFLICT'):
                self.read(admission)

    def test_real_provider_worker_refusal_preserves_budget_and_query_cannot_replay(self):
        import io
        import sys
        import time
        from pathlib import Path
        from autonomy.process_backend import ProcessBackend
        from autonomy.provider_worker import main
        from test_provider_worker import ProviderWorkerTests, BoundSearchRequestTests, WorkerOperationTests
        config, config_hash = ProviderWorkerTests().config(self.f.root)
        request = BoundSearchRequestTests().request(provider='browser_maps')
        raw = WorkerOperationTests().encode(dict(provider_request=request))
        # Invoke the real pinned Worker and adapter in-process: development
        # guards may intentionally block the isolated subprocess launcher.
        with patch('autonomy.provider_worker.sys.stdin', io.TextIOWrapper(io.BytesIO(raw))), \
             patch('autonomy.provider_worker.sys.stderr', io.StringIO()) as errors:
            self.assertEqual(main(['--provider-config', str(config),
                                   '--provider-config-sha256', config_hash]), 78)
            refusal = json.loads(errors.getvalue())
            self.assertEqual(refusal['error'], 'CONTRACT_MISSING')
            self.assertIs(refusal['external_request_started'], False)
        worker = Path('autonomy/provider_worker.py').absolute()
        self.f.adapter.backend = ProcessBackend.for_provider_worker(
            self.f.root/'provider-backend.sqlite', python=sys.executable,
            python_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
            backend_id=self.f.target.backend_id, provider_config=str(config),
            provider_config_sha256=config_hash)
        self.f.adapter.monotonic = time.monotonic
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission(provider_request=request)
            self.assertEqual(self.f.run_one(admission)['outcome'], 'UNKNOWN_RECONCILE_ONLY')
            first = self.read(admission)
            self.assertEqual(first['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(first['resource_budget']['charged'], amounts())
            self.assertIsNone(first['resource_budget']['actual'])
            self.assertIsNone(first['provider_billing']['billed_amount'])
            with patch.object(self.f.adapter.backend, 'execute_once', side_effect=AssertionError('replay')):
                self.assertEqual(self.read(admission), first)
            self.assertFalse((self.f.root/'unused-cache').exists())
            from autonomy.lock_recovery import _ACTIVE_LEASE
            owned = _ACTIVE_LEASE.get()[1]
            mark_tree('verified_closed', binding=owned['tree_binding'], claim_hash=owned['tree_claim_hash'])  # Fixture cleanup only.

    def test_original_owner_execution_and_status_join_without_legacy_lease(self):
        import test_original_inventory_owner as original
        case = original.OriginalOwnerTests('runTest'); case.setUp()
        try:
            event = case.event()
            case.f.adapter.prepare_event(event)
            self.assertEqual(case.f.run_one(event['admission'])['outcome'], 'COMPLETED')
            status = case.f.adapter.request_status(event['admission'])
            self.assertEqual(status['business_state'], 'COMPLETED')
            self.assertFalse((case.f.runtime/'supervisor.lock').exists())
            self.assertEqual(case.f.backend.calls, 1)
            self.assertTrue(case.release())
            with self.assertRaises(AdapterError):
                case.f.adapter.request_status(event['admission'])
        finally:
            case.doCleanups()

    def test_closure_write_failure_keeps_lease_status_unknown_until_reconcile(self):
        with exclusive_lock(self.f.runtime):
            admission = self.f.admission()
            original = self.f.adapter._mark_tree
            def fail_closed(state, *args):
                if state == 'verified_closed':
                    raise OSError('injected closure failure')
                return original(state, *args)
            with patch.object(self.f.adapter, '_mark_tree', side_effect=fail_closed):
                self.assertEqual(self.f.run_one(admission)['outcome'], 'UNKNOWN_RECONCILE_ONLY')
            status = self.read(admission)
            self.assertEqual(status['slot_state'], 'COMPLETED')
            self.assertEqual(status['resource_budget']['state'], 'SETTLED')
            self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertFalse(status['replay_authorized'])
            with self.assertRaisesRegex(RuntimeError, 'TREE_CLAIM_BINDING_MISMATCH'):
                mark_tree('verified_closed')  # An unbound close cannot clear this request.
            self.assertEqual(self.read(admission)['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.f.adapter.reconcile(admission, **self.f.backend.receipts)
            self.assertEqual(self.read(admission)['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(self.f.backend.calls, 1)

    def test_original_owner_closure_failure_keeps_status_unknown_until_reconcile(self):
        import test_original_inventory_owner as original
        case = original.OriginalOwnerTests('runTest'); case.setUp()
        try:
            event = case.event()
            case.f.adapter.prepare_event(event)
            real_mark = case.f.adapter._mark_tree
            def fail_closed(state, *args):
                if state == 'verified_closed':
                    raise OSError('injected closure failure')
                return real_mark(state, *args)
            with patch.object(case.f.adapter, '_mark_tree', side_effect=fail_closed):
                self.assertEqual(case.f.run_one(event['admission'])['outcome'], 'UNKNOWN_RECONCILE_ONLY')
            status = case.f.adapter.request_status(event['admission'])
            self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(status['slot_state'], 'COMPLETED')
            self.assertEqual(status['resource_budget']['state'], 'SETTLED')
            self.assertFalse(case.release())
            case.f.adapter.reconcile(event['admission'], **case.f.backend.receipts)
            self.assertEqual(case.f.adapter.request_status(event['admission'])['business_state'], 'COMPLETED')
            self.assertEqual(case.f.backend.calls, 1)
            self.assertTrue(case.release())
        finally:
            case.doCleanups()

    def test_original_owner_event_intent_without_slot_or_budget_is_unknown(self):
        import test_original_inventory_owner as original
        case = original.OriginalOwnerTests('runTest'); case.setUp()
        try:
            event = case.event()
            case.f.adapter.prepare_event(event)
            before = case.session()
            status = case.f.adapter.request_status(event['admission'])
            self.assertEqual(status['business_state'], 'UNKNOWN_RECONCILE_ONLY')
            self.assertEqual(status['slot_state'], 'NOT_RECORDED')
            self.assertIsNone(status['resource_budget'])
            for key in ('replay_authorized', 'allow_dispatch',
                        'allow_cancel_dispatch', 'production_execution'):
                self.assertIs(status[key], False)
            self.assertEqual(case.f.backend.calls, 0)
            self.assertEqual(case.f.slots.snapshot(), [])
            self.assertEqual(case.session(), before)
            self.assertFalse(case.release())
        finally:
            case.doCleanups()

    def test_unrecognized_adapter_subclass_cannot_claim_not_recorded(self):
        from autonomy.single_slot_adapter import SingleSlotAdapter
        from autonomy.business_request_status import _project

        class OtherAuthorityAdapter(SingleSlotAdapter):
            pass

        adapter = object.__new__(OtherAuthorityAdapter)
        result = _project(adapter, {'request_id': 'fixture', 'run_id': 'fixture'},
                          {}, None, None)
        self.assertEqual(result['business_state'], 'UNKNOWN_RECONCILE_ONLY')
        self.assertFalse(result['replay_authorized'])


if __name__ == '__main__':
    unittest.main()
