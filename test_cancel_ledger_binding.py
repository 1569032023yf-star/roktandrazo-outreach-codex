"""Offline adversarial tests for cancellation ledger and journal binding."""
import os
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from autonomy.lock_recovery import exclusive_lock
from autonomy.single_slot_adapter import AdapterError, CancellationJournal, SingleSlotAdapter
from test_cancellation_cost import CancellationCostTests
from test_growth_ledger import T, signed


@unittest.skipUnless(os.name == 'nt', 'Windows local-ledger pin required')
class CancellationLedgerBindingTests(CancellationCostTests):
    def copy_db(self, source, destination):
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)

    def test_unverified_adapter_subclass_cannot_reserve_cancellation(self):
        c=self.case
        class UnsupportedAdapter(SingleSlotAdapter): pass
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            adapter=UnsupportedAdapter(c.slots,c.budget,target=c.target,consumer=c.trust,
                wall_clock=lambda:T+10,cancellation_journal=journal)
            with self.assertRaisesRegex(AdapterError,'CANCEL_LEDGER_BINDING_UNAVAILABLE'):
                adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
            self.assertFalse(journal.path.exists())
            self.assertEqual(len(self.rows()),1)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_cost_verifier_cannot_reserve_in_decoy_or_write_journal(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            original=c.budget.path
            decoy=c.root/'budget-decoy.sqlite'
            self.copy_db(original,decoy)
            verify=c.trust.verify
            def redirect(envelope,*,kind,now):
                result=verify(envelope,kind=kind,now=now)
                if kind=='budget_request': c.budget.path=str(decoy)
                return result
            c.trust.verify=redirect
            try:
                result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
                self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
                self.assertFalse(result['allow_cancel_dispatch'])
                self.assertFalse(journal.path.exists())
                for path in (original,decoy):
                    with closing(sqlite3.connect(path)) as db:
                        self.assertIsNone(db.execute('SELECT state FROM reservations WHERE id=?',(cost_id,)).fetchone())
                        self.assertEqual(db.execute('SELECT count(*) FROM reservations').fetchone(),(1,))
                self.assertTrue((c.runtime/'supervisor.tree-unverified').exists())
            finally:
                c.trust.verify=verify;c.budget.path=original
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_cancel_verifier_cannot_redirect_slot_or_journal(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            original=c.slots.path
            decoy=c.root/'slot-decoy.sqlite'
            self.copy_db(original,decoy)
            original_journal=journal.path
            decoy_journal=c.root/'journal-decoy.sqlite'
            with closing(sqlite3.connect(decoy_journal)): pass
            verify=c.trust.verify
            for target in ('slots','journal'):
                def redirect(envelope,*,kind,now):
                    result=verify(envelope,kind=kind,now=now)
                    if kind=='offline_cancel_request':
                        if target=='slots': c.slots.path=str(decoy)
                        else: journal.path=decoy_journal
                    return result
                c.trust.verify=redirect
                try:
                    result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
                    self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
                    self.assertFalse(result['allow_cancel_dispatch'])
                    self.assertFalse(original_journal.exists())
                    with closing(sqlite3.connect(decoy_journal)) as db:
                        self.assertEqual(db.execute('SELECT count(*) FROM sqlite_master').fetchone(),(0,))
                    for path in (original,decoy):
                        with closing(sqlite3.connect(path)) as db:
                            self.assertEqual(db.execute("SELECT state FROM slots WHERE slot='one'").fetchone(),('unknown',))
                    self.assertEqual(len(self.rows()),1)
                finally:
                    c.trust.verify=verify;c.slots.path=original;journal.path=original_journal
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_journal_retarget_before_and_after_commit_is_unknown(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            original=journal.path
            decoy=c.root/'journal-decoy.sqlite'
            with closing(sqlite3.connect(decoy)): pass
            def retarget(stage):
                if stage=='before_commit': journal.path=decoy
            journal.fault=retarget
            request=signed('offline_cancel_request',T+10,**fields)
            result=c.adapter.reserve_cancellation(admission,request,cost_request=cost)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertFalse(result['allow_cancel_dispatch'])
            with closing(sqlite3.connect(original)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE name='cancellations'").fetchone(),(0,))
            with closing(sqlite3.connect(decoy)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM sqlite_master').fetchone(),(0,))
            self.assertEqual(next(r for r in self.rows() if r['id']==cost_id)['state'],'reserved')
            journal.path=original
            journal.fault=lambda stage:setattr(journal,'path',decoy) if stage=='after_commit' else None
            result=c.adapter.reserve_cancellation(admission,request,cost_request=cost)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            with closing(sqlite3.connect(original)) as db:
                self.assertEqual(db.execute('SELECT state FROM cancellations').fetchall(),[('RESERVED_RECONCILE_ONLY',)])
            with closing(sqlite3.connect(decoy)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM sqlite_master').fetchone(),(0,))
            c.adapter.cancellation_journal=CancellationJournal(original)
            self.assertEqual(c.adapter.reserve_cancellation(admission,request,cost_request=cost)['outcome'],'DUPLICATE_RESERVED')
            self.assertEqual(len(self.rows()),2)
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_existing_journal_cannot_be_replaced_during_verification(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            with closing(sqlite3.connect(journal.path)): pass
            source=c.root/'replacement.sqlite'
            with closing(sqlite3.connect(source)): pass
            verify=c.trust.verify
            blocked=[]
            def replace(envelope,*,kind,now):
                result=verify(envelope,kind=kind,now=now)
                if kind=='offline_cancel_request':
                    try:os.replace(source,journal.path)
                    except PermissionError:blocked.append(True)
                return result
            c.trust.verify=replace
            try:
                result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
                self.assertEqual(result['outcome'],'RESERVED_RECONCILE_ONLY')
                self.assertEqual(blocked,[True])
                with closing(sqlite3.connect(journal.path)) as db:
                    self.assertEqual(db.execute('SELECT state FROM cancellations').fetchall(),[('RESERVED_RECONCILE_ONLY',)])
            finally:c.trust.verify=verify
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_new_journal_created_by_verifier_is_not_adopted(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            verify=c.trust.verify
            def create(envelope,*,kind,now):
                result=verify(envelope,kind=kind,now=now)
                if kind=='offline_cancel_request':
                    with closing(sqlite3.connect(journal.path)) as db:
                        db.execute('CREATE TABLE unexpected (x INTEGER)')
                return result
            c.trust.verify=create
            try:
                result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
                self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
                self.assertFalse(result['allow_cancel_dispatch'])
                with closing(sqlite3.connect(journal.path)) as db:
                    self.assertEqual(db.execute('SELECT name FROM sqlite_master').fetchall(),[('unexpected',)])
                # The cost may already have committed; it remains charged.
                self.assertEqual(next(r for r in self.rows() if r['id']==cost_id)['state'],'reserved')
            finally:c.trust.verify=verify
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_cost_after_commit_path_change_keeps_true_reservation_and_no_intent(self):
        c=self.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.prepare()
            original=c.budget.path
            decoy=c.root/'budget-commit-decoy.sqlite'
            self.copy_db(original,decoy)
            reserve=c.budget.reserve_cancellation_cost
            def retarget(*args,**kwargs):
                c.budget.fault=lambda stage:setattr(c.budget,'path',str(decoy)) if stage=='after_commit' else None
                try:return reserve(*args,**kwargs)
                finally:c.budget.fault=lambda stage:None
            c.budget.reserve_cancellation_cost=retarget
            try:
                result=c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
                self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
                self.assertFalse(result['allow_cancel_dispatch'])
                self.assertFalse(journal.path.exists())
                with closing(sqlite3.connect(original)) as db:
                    self.assertEqual(db.execute('SELECT state FROM reservations WHERE id=?',(cost_id,)).fetchone(),('reserved',))
                with closing(sqlite3.connect(decoy)) as db:
                    self.assertIsNone(db.execute('SELECT state FROM reservations WHERE id=?',(cost_id,)).fetchone())
                self.assertTrue((c.runtime/'supervisor.tree-unverified').exists())
            finally:
                c.budget.path=original;c.budget.reserve_cancellation_cost=reserve
            c.adapter.reconcile(admission,**c.backend.receipts)

    def test_unverified_recovery_never_touches_either_database_or_fence(self):
        from autonomy.cancellation_recovery import recover_cancellation
        from test_cancellation_recovery import prepare, authorization
        c=self.case
        with self.assertRaisesRegex(RuntimeError,'ASSOCIATED_TREE_UNVERIFIED'), exclusive_lock(c.runtime):
            data=prepare(self)
            recovery=c.root/'recovery.sqlite'
            decoy_slots=c.root/'recovery-slots-decoy.sqlite'
            decoy_budget=c.root/'recovery-budget-decoy.sqlite'
            self.copy_db(c.slots.path,decoy_slots)
            self.copy_db(c.budget.path,decoy_budget)
            before_lock=(c.runtime/'supervisor.lock').read_bytes()
            before_fence=(c.runtime/'supervisor.tree-unverified').read_bytes()
            def rows(path,sql):
                with closing(sqlite3.connect(path)) as db:return db.execute(sql).fetchall()
            slots_sql='SELECT slot,state,token FROM slots ORDER BY slot'
            budget_sql='SELECT id,state,charged FROM reservations ORDER BY id'
            before_slots=rows(c.slots.path,slots_sql)
            before_budget=rows(c.budget.path,budget_sql)
            called=[]
            def redirect(stage):
                called.append(stage)
                c.slots.path=str(decoy_slots);c.budget.path=str(decoy_budget)
            result=recover_cancellation(c.adapter,authorization(c,data,recovery),*data[:4],
                recovery_path=recovery,fault=redirect)
            self.assertEqual(result['outcome'],'UNKNOWN_RECONCILE_ONLY')
            self.assertFalse(result['allow_dispatch']);self.assertFalse(result['allow_cancel_dispatch'])
            self.assertEqual(called,[])
            self.assertFalse(recovery.exists())
            self.assertEqual((c.runtime/'supervisor.lock').read_bytes(),before_lock)
            self.assertEqual((c.runtime/'supervisor.tree-unverified').read_bytes(),before_fence)
            for path in (c.slots.path,decoy_slots):self.assertEqual(rows(path,slots_sql),before_slots)
            for path in (c.budget.path,decoy_budget):self.assertEqual(rows(path,budget_sql),before_budget)
