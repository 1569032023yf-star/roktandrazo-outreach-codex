import unittest
from autonomy.unattended_policy import (
    GATES, INVENTORY, readiness, slot_action, budget_reservation,
)


class UnattendedPolicyTests(unittest.TestCase):
    def test_every_missing_or_nonboolean_gate_fails_closed(self):
        valid = dict.fromkeys(GATES, True)
        valid['inventory_id'] = INVENTORY
        self.assertEqual(readiness(valid), ())
        for gate in GATES:
            for bad in (False, None, 1, 'true', [], {}):
                with self.subTest(gate=gate, value=bad):
                    self.assertIn('MISSING_' + gate.upper(), readiness({**valid, gate: bad}))
            missing = dict(valid)
            del missing[gate]
            self.assertIn('MISSING_' + gate.upper(), readiness(missing))

    def test_identity_and_output_redaction(self):
        self.assertEqual(readiness(None), ('INVALID_EVIDENCE',))
        result = readiness({'inventory_id': 'secret-token-url-cookie'})
        self.assertIn('INVENTORY_MISMATCH', result)
        self.assertNotIn('secret', repr(result))

    def test_restart_never_replays_uncertain_or_completed_slot(self):
        for due in (True, False, None):
            for state in ('running', 'unknown'):
                self.assertEqual(slot_action(state, due=due, readiness_errors=()), 'RECONCILE_ONLY')
            self.assertEqual(slot_action('completed', due=due, readiness_errors=()), 'NO_REPLAY')

    def test_pending_is_only_a_claim_proposal(self):
        self.assertEqual(slot_action('pending', due=True, readiness_errors=()), 'REQUIRES_ATOMIC_CLAIM')
        for due in (1, 'yes', None, False):
            self.assertEqual(slot_action('pending', due=due, readiness_errors=()), 'DEFER')
        for errors in (None, [], ('MISSING_AUDIT_READY',)):
            self.assertEqual(slot_action('pending', due=True, readiness_errors=errors), 'DEFER')
        self.assertEqual(slot_action('expired', due=True, readiness_errors=()), 'INVALID_STATE')

    def test_unknown_reservations_still_consume_cap(self):
        self.assertEqual(budget_reservation(10, 4, 5, 2), 'CAP_REACHED')
        self.assertEqual(budget_reservation(10, 4, 5, 1), 'WITHIN_CAP')
        for value in (-1, True, 1.5, '1', None):
            self.assertEqual(budget_reservation(10, 0, value, 1), 'INVALID_BUDGET')
        self.assertEqual(budget_reservation(10, 0, 0, 0), 'INVALID_BUDGET')


if __name__ == '__main__':
    unittest.main()
