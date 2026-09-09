"""Positive sample validation: 3-5 historically clean leads.

Tests gate can CORRECTLY PASS real production-quality leads.
Also tests gate CORRECTLY BLOCKS dirty variants.

Only reads from production DB. No writes, no side effects.
"""
import sqlite3
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from lead_hygiene_gate import evaluate_a0, is_strict_a0
from production_adapter import build_candidate_from_db_row, build_context


def _get_ro_conn():
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "bd_leads.db")
    if not os.path.exists(db_path):
        raise unittest.SkipTest("Production DB not found")
    conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


class TestPositiveSamples(unittest.TestCase):
    """Verify gate correctly PASSES 5 clean real leads and REJECTS dirty variants."""

    @classmethod
    def setUpClass(cls):
        cls.conn = _get_ro_conn()
        cls.ctx = build_context(cls.conn)

        # 5 historically clean leads: TN/AR/KY, complete evidence, official source
        cls.clean_ids = [454, 451, 452, 450, 453]
        cls.clean_labels = [
            "Outer Limits Boro (TN)",
            "CREATE Studio (KY)",
            "Steadfast Hobbies (AR)",
            "Card N All Gaming (KY)",
            "Jonathan's Gatlinburg (TN)",
        ]

        # Build clean test candidates: copy real DB rows, reset to 'new' status
        cls.clean_candidates = []
        for lead_id in cls.clean_ids:
            row = dict(cls.conn.execute(
                "SELECT * FROM leads WHERE id = ?", (lead_id,)
            ).fetchone())
            # Reset to "new" state for positive validation:
            # - clear sent_at so already_sent check doesn't fire
            # - reset status to 'new'
            row["sent_at"] = None
            row["status"] = "new"
            # Build candidate with CLEAN context (remove from sent/suppressed sets)
            clean_ctx = {
                "suppressed_emails": cls.ctx["suppressed_emails"] - {row["email"].strip().lower()},
                "hard_bounced_emails": cls.ctx["hard_bounced_emails"] - {row["email"].strip().lower()},
                "policy_bounced_emails": cls.ctx["policy_bounced_emails"],
                "sent_emails": cls.ctx["sent_emails"] - {row["email"].strip().lower()},
                "duplicate_domain_hashes": cls.ctx["duplicate_domain_hashes"],
            }
            candidate = build_candidate_from_db_row(row, clean_ctx)
            cls.clean_candidates.append((lead_id, row, candidate))

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    # ============================================================
    # POSITIVE: Gate MUST PASS these 5 clean leads
    # ============================================================

    def test_clean_sample_01_outer_limits_boro_passes(self):
        lid, row, cand = self.clean_candidates[0]
        decision = evaluate_a0(cand)
        self.assertTrue(
            decision.a0_eligible,
            f"Outer Limits Boro (id={lid}) SHOULD pass but rejected: {decision.reasons}\n"
            f"email={cand.get('email')} verified={cand.get('email_verified_on_official_site')} "
            f"source={cand.get('email_source_type')} official_match={cand.get('official_match')} "
            f"ev_url={'Y' if cand.get('evidence_url') else 'N'} ev_snip={'Y' if cand.get('evidence_snippet') else 'N'}"
        )

    def test_clean_sample_02_create_studio_passes(self):
        lid, row, cand = self.clean_candidates[1]
        decision = evaluate_a0(cand)
        self.assertTrue(
            decision.a0_eligible,
            f"CREATE Studio (id={lid}) SHOULD pass but rejected: {decision.reasons}"
        )

    def test_clean_sample_03_steadfast_hobbies_passes(self):
        lid, row, cand = self.clean_candidates[2]
        decision = evaluate_a0(cand)
        self.assertTrue(
            decision.a0_eligible,
            f"Steadfast Hobbies (id={lid}) SHOULD pass but rejected: {decision.reasons}"
        )

    def test_clean_sample_04_card_n_all_passes(self):
        lid, row, cand = self.clean_candidates[3]
        decision = evaluate_a0(cand)
        self.assertTrue(
            decision.a0_eligible,
            f"Card N All Gaming (id={lid}) SHOULD pass but rejected: {decision.reasons}"
        )

    def test_clean_sample_05_jonathans_gatlinburg_passes(self):
        lid, row, cand = self.clean_candidates[4]
        decision = evaluate_a0(cand)
        self.assertTrue(
            decision.a0_eligible,
            f"Jonathan's Gatlinburg (id={lid}) SHOULD pass but rejected: {decision.reasons}"
        )

    # ============================================================
    # NEGATIVE: Gate MUST REJECT dirty variants of same leads
    # ============================================================

    def test_already_sent_variant_rejected(self):
        """If same lead is still in sent_emails context, gate must reject."""
        lid, row, _ = self.clean_candidates[0]
        cand = build_candidate_from_db_row(row, self.ctx)  # Use REAL context with sent_emails
        decision = evaluate_a0(cand)
        self.assertFalse(decision.a0_eligible,
            f"Outer Limits Boro SHOULD be rejected when already_sent is True")
        self.assertIn("already_sent", decision.reasons)

    def test_wrong_state_variant_rejected(self):
        """If we change state to CA, gate must reject."""
        lid, row, _ = self.clean_candidates[0]
        row_fake = dict(row)
        row_fake["state"] = "CA"
        clean_ctx = {
            "suppressed_emails": set(),
            "hard_bounced_emails": set(),
            "policy_bounced_emails": set(),
            "sent_emails": set(),
            "duplicate_domain_hashes": set(),
        }
        cand = build_candidate_from_db_row(row_fake, clean_ctx)
        decision = evaluate_a0(cand)
        self.assertFalse(decision.a0_eligible)
        self.assertIn("state_out_of_scope", decision.reasons)

    def test_empty_evidence_variant_rejected(self):
        """If evidence_snippet is empty, gate must reject."""
        lid, row, _ = self.clean_candidates[0]
        row_fake = dict(row)
        row_fake["evidence_snippet"] = ""
        clean_ctx = {
            "suppressed_emails": set(),
            "hard_bounced_emails": set(),
            "policy_bounced_emails": set(),
            "sent_emails": set(),
            "duplicate_domain_hashes": set(),
        }
        cand = build_candidate_from_db_row(row_fake, clean_ctx)
        decision = evaluate_a0(cand)
        self.assertFalse(decision.a0_eligible)
        self.assertIn("evidence_snippet_missing", decision.reasons)

    def test_suppressed_variant_rejected(self):
        """If email is in suppression set, gate must reject."""
        lid, row, _ = self.clean_candidates[0]
        email_lower = (row["email"] or "").strip().lower()
        ctx_with_suppression = {
            "suppressed_emails": {email_lower},
            "hard_bounced_emails": set(),
            "policy_bounced_emails": set(),
            "sent_emails": set(),
            "duplicate_domain_hashes": set(),
        }
        cand = build_candidate_from_db_row(row, ctx_with_suppression)
        decision = evaluate_a0(cand)
        self.assertFalse(decision.a0_eligible)
        self.assertIn("suppressed", decision.reasons)

    def test_guessed_email_variant_rejected(self):
        """If email_source_type is guessed_email, gate must reject."""
        lid, row, _ = self.clean_candidates[0]
        row_fake = dict(row)
        row_fake["email_source_type"] = "guessed_email"
        row_fake["email_verified_on_official_site"] = 0
        clean_ctx = {
            "suppressed_emails": set(),
            "hard_bounced_emails": set(),
            "policy_bounced_emails": set(),
            "sent_emails": set(),
            "duplicate_domain_hashes": set(),
        }
        cand = build_candidate_from_db_row(row_fake, clean_ctx)
        decision = evaluate_a0(cand)
        self.assertFalse(decision.a0_eligible)
        self.assertIn("guessed_email", decision.reasons)

    def test_empty_official_website_variant_rejected(self):
        """If official_website is empty, gate must reject."""
        lid, row, _ = self.clean_candidates[0]
        row_fake = dict(row)
        row_fake["official_website"] = ""
        clean_ctx = {
            "suppressed_emails": set(),
            "hard_bounced_emails": set(),
            "policy_bounced_emails": set(),
            "sent_emails": set(),
            "duplicate_domain_hashes": set(),
        }
        cand = build_candidate_from_db_row(row_fake, clean_ctx)
        decision = evaluate_a0(cand)
        self.assertFalse(decision.a0_eligible)
        self.assertIn("official_website_missing", decision.reasons)

    def test_bounced_variant_rejected(self):
        """If email is in hard_bounced set, gate must reject."""
        lid, row, _ = self.clean_candidates[0]
        email_lower = (row["email"] or "").strip().lower()
        ctx_with_bounce = {
            "suppressed_emails": set(),
            "hard_bounced_emails": {email_lower},
            "policy_bounced_emails": set(),
            "sent_emails": set(),
            "duplicate_domain_hashes": set(),
        }
        cand = build_candidate_from_db_row(row, ctx_with_bounce)
        decision = evaluate_a0(cand)
        self.assertFalse(decision.a0_eligible)
        self.assertIn("bounced", decision.reasons)

    # ============================================================
    # EDGE CASE: manual_lookup approved should pass
    # ============================================================

    def test_manual_lookup_approved_with_evidence_passes(self):
        """manual_lookup + approved + complete evidence → gate must pass."""
        # Use a real manual_lookup lead if exists, else construct
        rows = self.conn.execute(
            "SELECT * FROM leads WHERE email_source_type = 'manual_lookup' AND email IS NOT NULL"
        ).fetchall()
        if rows:
            row = dict(rows[0])
            row["sent_at"] = None
            row["status"] = "new"
            row["manual_decision"] = "approved"
            row["manual_found_email"] = row["email"]
            if not row.get("evidence_url"):
                row["evidence_url"] = "https://example.com/contact"
            if not row.get("official_website"):
                row["official_website"] = "https://example.com"
            if not row.get("evidence_snippet"):
                row["evidence_snippet"] = f"Manual verified: {row['email']} on official site"
            row["email_verified_on_official_site"] = 1
            clean_ctx = {
                "suppressed_emails": set(),
                "hard_bounced_emails": set(),
                "policy_bounced_emails": set(),
                "sent_emails": set(),
                "duplicate_domain_hashes": set(),
            }
            cand = build_candidate_from_db_row(row, clean_ctx)
            decision = evaluate_a0(cand)
            self.assertTrue(decision.a0_eligible,
                f"Approved manual_lookup SHOULD pass: {decision.reasons} | "
                f"email_source_type={cand.get('email_source_type')} "
                f"official_match={cand.get('official_match')}")
        else:
            self.skipTest("No manual_lookup leads in DB")

    def test_manual_lookup_unapproved_rejected(self):
        """manual_lookup WITHOUT approval → gate must reject."""
        rows = self.conn.execute(
            "SELECT * FROM leads WHERE email_source_type = 'manual_lookup' AND email IS NOT NULL"
        ).fetchall()
        if rows:
            row = dict(rows[0])
            row["sent_at"] = None
            row["status"] = "new"
            # Don't set manual_decision=approved
            clean_ctx = {
                "suppressed_emails": set(),
                "hard_bounced_emails": set(),
                "policy_bounced_emails": set(),
                "sent_emails": set(),
                "duplicate_domain_hashes": set(),
            }
            cand = build_candidate_from_db_row(row, clean_ctx)
            decision = evaluate_a0(cand)
            self.assertFalse(decision.a0_eligible,
                f"Unapproved manual_lookup MUST be rejected: {decision.reasons}")
            self.assertIn("guessed_email", decision.reasons)
        else:
            self.skipTest("No manual_lookup leads in DB")


if __name__ == "__main__":
    unittest.main(verbosity=2)
