import unittest

from app.lead_hygiene.lead_hygiene_gate import evaluate_a0, is_strict_a0


def valid_candidate(**changes):
    candidate = {
        "email": "hello@example.test", "official_website": "https://example.test",
        "evidence_url": "https://example.test/contact", "evidence_snippet": "Contact hello@example.test",
        "email_verified_on_official_site": True, "email_source_type": "official_page_visible",
        "official_match": True, "state": "TN",
    }
    candidate.update(changes)
    return candidate


class LeadHygieneGateTests(unittest.TestCase):
    def test_complete_official_evidence_is_a0(self):
        self.assertTrue(is_strict_a0(valid_candidate()))

    def test_social_only_email_stays_b1(self):
        decision = evaluate_a0(valid_candidate(social_only=True, status="B1_social_verified"))
        self.assertEqual("B1_social_verified", decision.status)
        self.assertFalse(decision.a0_eligible)

    def test_guessed_email_is_not_a0(self):
        decision = evaluate_a0(valid_candidate(guessed_email=True))
        self.assertIn("guessed_email", decision.reasons)

    def test_missing_evidence_is_not_a0(self):
        decision = evaluate_a0(valid_candidate(evidence_snippet=""))
        self.assertIn("evidence_snippet_missing", decision.reasons)

    def test_out_of_scope_state_is_not_a0(self):
        self.assertFalse(is_strict_a0(valid_candidate(state="CA")))

    def test_contact_form_is_c_pool(self):
        decision = evaluate_a0(valid_candidate(contact_form_only=True))
        self.assertEqual("C_contact_form_or_social_message", decision.status)


if __name__ == "__main__":
    unittest.main()