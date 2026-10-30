"""真实退出所有者快照与终态关联 / Dead-owner snapshots and terminal joins."""
import copy
import hashlib
import unittest
import test_drain_bundle_preflight as fixtures
from autonomy.cancellation_terminal_bundle import inspect_cancellation_terminal_bundle
from autonomy.cancellation_terminal import PROTOCOL
from test_growth_ledger import consumer, signed, amounts, T


class CancellationTerminalBundleTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DrainBundlePreflightTests(); self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.binding = dict(self.f.base.data['cost']['payload']['claim_binding'])
        fields = dict(self.binding); fields.pop('inventory_id')
        self.terminal = signed('offline_cancel_terminal', T+10, **dict(fields,
            cancel_terminal_protocol=PROTOCOL, cancel_outcome='already_completed',
            terminal_confirmed=True, external_drained=True))
        self.fee = signed('budget_receipt', T+10, **dict(fields, outcome='known',
            externally_reconciled=True, actual=amounts(0)))

    def check(self, **changes):
        f = self.f
        args = dict(now=T+10, expected=f.expected, lock_bytes=f.base.lock,
            budget_snapshot=f.base.snapshot, slots_snapshot=f.slots,
            journal_snapshot=f.journal)
        args.update(changes)
        terminal=args.pop('terminal',self.terminal)
        fee=args.pop('fee',self.fee)
        result=inspect_cancellation_terminal_bundle(consumer(),
            signed('offline_owner_drain',T+10,**args.pop('fields',f.fields)),
            terminal,f.base.data['receipts']['slot_receipt'],fee,**args)
        for key in ('allow_reconcile','allow_lock_recovery','allow_dispatch',
                    'allow_cancel_dispatch','production_accepted'):
            self.assertIs(result[key],False)
        self.assertEqual(result['owner_liveness'],'UNKNOWN')
        return result

    def test_real_dead_owner_snapshot_terminal_join_has_no_mutation_or_authority(self):
        f=self.f;before=f.base.helper.inspect(f.base.root,f.base.data)
        files={p:p.read_bytes() for p in f.base.root.rglob('*') if p.is_file()}
        self.assertTrue(self.check()['evidence_matches'])
        self.assertEqual(f.base.helper.inspect(f.base.root,f.base.data),before)
        self.assertEqual({p:p.read_bytes() for p in files},files)

    def test_valid_old_proof_cannot_override_changed_signed_persisted_state(self):
        f=self.f;cost_id=f.expected['cancel_cost_request_id']
        cases=[('budget',f.base.snapshot,"UPDATE reservations SET state='settled' WHERE id=?",(cost_id,)),
               ('budget',f.base.snapshot,'DELETE FROM reservations WHERE id=?',(cost_id,)),
               ('slots',f.slots,"UPDATE slots SET state='completed'",()),
               ('slots',f.slots,"UPDATE authority SET owner='new-owner'",()),
               ('journal',f.journal,'DELETE FROM cancellations',())]
        for kind,raw,sql,params in cases:
            with self.subTest(kind=kind,sql=sql):
                image=f.mutate(raw,sql,params);key=kind+'_snapshot_sha256'
                expected=dict(f.expected,**{key:hashlib.sha256(image).hexdigest()})
                fields=dict(f.fields,**{key:expected[key]})
                self.assertFalse(self.check(expected=expected,fields=fields,
                    **{kind+'_snapshot':image})['evidence_matches'])

    def test_ack_late_wrong_binding_and_missing_image_fail_closed(self):
        self.assertFalse(self.check(now=T+111)['evidence_matches'])
        self.assertFalse(self.check(journal_snapshot=None)['evidence_matches'])
        fields=dict(self.binding, cancel_terminal_protocol=PROTOCOL, cancel_outcome='already_completed', terminal_confirmed=True, external_drained=True);fields.pop('inventory_id')
        # The drain/snapshot evidence remains fresh while only this terminal
        # has expired, so a fresh bundle cannot revive a late terminal.
        self.assertFalse(self.check(terminal=signed('offline_cancel_terminal',T-100,
            **fields))['evidence_matches'])
        for change in ({'cancel_outcome':'ACK'},{'journal_id':'a'*64},
                       {'cancel_cost_request_id':'b'*64},{'terminal_confirmed':False}):
            self.assertFalse(self.check(terminal=signed('offline_cancel_terminal',T+10,
                **dict(fields,**change)))['evidence_matches'])
        bad=copy.deepcopy(self.fee);bad['mac']='0'*64
        self.assertFalse(self.check(fee=bad)['evidence_matches'])


if __name__=='__main__':unittest.main()
