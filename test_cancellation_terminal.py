"""Versioned cancellation-terminal evidence joins with real offline bindings."""
import copy
import unittest
from pathlib import Path
import test_cancellation_cost as fixtures
from autonomy.cancellation_terminal import inspect_cancellation_terminal, PROTOCOL
from autonomy.lock_recovery import exclusive_lock
from test_growth_ledger import signed, amounts, T


class CancellationTerminalTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.CancellationCostTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_bound_proofs_match_without_authority_or_storage_mutation(self):
        self.check(False)

    def test_missing_wrong_version_ack_stale_signature_and_binding_reject(self):
        self.check(True)

    def check(self, negatives):
        c=self.fixture.case
        with exclusive_lock(c.runtime):
            admission,journal,fields,cost,cost_id=self.fixture.prepare()
            c.adapter.reserve_cancellation(admission,signed('offline_cancel_request',T+10,**fields),cost_request=cost)
            expected=dict(cost['payload']['claim_binding'])
            proof=dict(expected,cancel_terminal_protocol=PROTOCOL,cancel_outcome='already_completed',
                external_drained=True,terminal_confirmed=True)
            proof.pop('inventory_id')
            fee=dict(expected);fee.pop('inventory_id')
            fee.update(outcome='known',externally_reconciled=True,actual=amounts(0))
            terminal=signed('offline_cancel_terminal',T+10,**proof)
            original=c.backend.receipts['slot_receipt']
            receipt=signed('budget_receipt',T+10,**fee)
            paths=tuple(map(Path,(journal.path,c.runtime/'supervisor.lock',c.slots.path,c.budget.path)))
            before=[p.read_bytes() for p in paths];rows=self.fixture.rows()
            def inspect(t=terminal,o=original,r=receipt,e=expected,now=T+10):
                result=inspect_cancellation_terminal(c.budget.consumer,t,o,r,now=now,expected=e)
                for k in ('allow_reconcile','allow_lock_recovery','allow_dispatch','allow_cancel_dispatch','production_accepted'):
                    self.assertIs(result[k],False)
                return result['evidence_matches']
            self.assertTrue(inspect())
            if not negatives:
                for outcome in ('cancelled','already_failed'):
                    failed=signed('receipt',T+10,**dict(c.common,
                        token=original['payload']['token'],state='failed',external_drained=True))
                    self.assertTrue(inspect(t=signed('offline_cancel_terminal',T+10,
                        **dict(proof,cancel_outcome=outcome)),o=failed))
            if negatives:
                for k,v in dict(cancel_terminal_protocol='v2',external_drained=False,terminal_confirmed=False,
                    epoch=True,cancel_outcome='ACK',original_request_id='0'*64).items():
                    with self.subTest(field=k):
                        self.assertFalse(inspect(t=signed('offline_cancel_terminal',T+10,**dict(proof,**{k:v}))))
                self.assertFalse(inspect(t=None));self.assertFalse(inspect(r=None))
                self.assertFalse(inspect(now=T+111))
                bad=copy.deepcopy(terminal);bad['mac']='0'*64
                self.assertFalse(inspect(t=bad))
                self.assertFalse(inspect(e=dict(expected,epoch=True)))
                self.assertFalse(inspect(r=signed('budget_receipt',T+10,**dict(fee,outcome='unknown'))))
                self.assertFalse(inspect(r=c.backend.receipts['budget_receipt']))
                self.assertFalse(inspect(t=signed('offline_cancel_terminal',T+10,**dict(proof,cancel_outcome='cancelled'))))
                invalid=amounts(0);invalid['wall_seconds']=True
                self.assertFalse(inspect(r=signed('budget_receipt',T+10,**dict(fee,actual=invalid))))
                self.assertFalse(inspect(o=signed('receipt',T+10,**dict(c.common,token='wrong',state='completed',external_drained=True))))
            self.assertEqual([p.read_bytes() for p in paths],before)
            self.assertEqual(self.fixture.rows(),rows)
            self.assertEqual(c.backend.calls,1)
            c.adapter.reconcile(admission,**c.backend.receipts)


if __name__=='__main__':unittest.main()
