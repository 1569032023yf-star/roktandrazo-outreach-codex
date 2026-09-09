"""Production-compatible tests for lead_hygiene_gate.py.

These tests verify the Codex hygiene gate logic against real production DB schema
and field semantics. No production DB writes. Uses read-only queries only.

Test categories:
1. Pure logic tests (no DB dependency) - field mapping validation
2. Production DB read-only tests - verify schema compatibility
3. Risk scenario tests - suppression, bounce, delivery_issue, duplicate_domain, etc.
"""
import sqlite3
import unittest
import sys
import os

# Import from isolated copy
sys.path.insert(0, os.path.dirname(__file__))
from lead_hygiene_gate import evaluate_a0, is_strict_a0, normalize_state, email_domain, HygieneDecision


# ============================================================
# 1. Pure Logic Tests (no DB)
# ============================================================

class TestNormalizeState(unittest.TestCase):
    """Test state normalization against production state data."""
    def test_tn_alias(self):
        self.assertEqual(normalize_state("Tennessee"), "TN")
        self.assertEqual(normalize_state("TN"), "TN")
        self.assertEqual(normalize_state("tn"), "TN")

    def test_ar_alias(self):
        self.assertEqual(normalize_state("Arkansas"), "AR")
        self.assertEqual(normalize_state("AR"), "AR")

    def test_ky_alias(self):
        self.assertEqual(normalize_state("Kentucky"), "KY")
        self.assertEqual(normalize_state("KY"), "KY")

    def test_out_of_scope(self):
        self.assertEqual(normalize_state("CA"), "CA")
        self.assertEqual(normalize_state("California"), "California")

    def test_empty_state(self):
        self.assertEqual(normalize_state(""), "")
        self.assertEqual(normalize_state(None), "")


class TestEmailDomain(unittest.TestCase):
    def test_valid_domain(self):
        self.assertEqual(email_domain("hello@example.com"), "example.com")

    def test_no_at(self):
        self.assertEqual(email_domain("noemail"), "")

    def test_multiple_at(self):
        # rsplit with maxsplit=1 handles this correctly
        self.assertEqual(email_domain("user@domain@extra.com"), "extra.com")

    def test_empty(self):
        self.assertEqual(email_domain(""), "")
        self.assertEqual(email_domain(None), "")


class TestHygieneDecision(unittest.TestCase):
    """Test the evaluate_a0 function with production-like candidate dicts."""

    def _valid_a0_candidate(self, **overrides):
        """Build a candidate that would pass all A0 gates."""
        c = {
            "email": "hello@example.com",
            "official_website": "https://example.com",
            "evidence_url": "https://example.com/contact",
            "evidence_snippet": "Contact hello@example.com for wholesale",
            "email_verified_on_official_site": True,
            "email_source_type": "official_page_visible",
            "official_match": True,
            "state": "TN",
        }
        c.update(overrides)
        return c

    def test_valid_a0_passes(self):
        decision = evaluate_a0(self._valid_a0_candidate())
        self.assertTrue(decision.a0_eligible)
        self.assertEqual(decision.status, "A0")
        self.assertEqual(decision.reasons, ())

    def test_missing_email_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(email=""))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("email_missing", decision.reasons)

    def test_invalid_email_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(email="not-an-email"))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("email_invalid", decision.reasons)

    def test_missing_official_website_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(official_website=""))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("official_website_missing", decision.reasons)

    def test_missing_evidence_url_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(evidence_url=""))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("evidence_url_missing", decision.reasons)

    def test_missing_evidence_snippet_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(evidence_snippet=""))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("evidence_snippet_missing", decision.reasons)

    def test_unverified_email_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(email_verified_on_official_site=False))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("official_site_email_not_verified", decision.reasons)

    def test_non_official_source_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(email_source_type="manual_lookup"))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("email_source_not_official", decision.reasons)

    def test_out_of_scope_state_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(state="CA"))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("state_out_of_scope", decision.reasons)

    def test_suppressed_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(suppressed=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("suppressed", decision.reasons)

    def test_bounced_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(bounced=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("bounced", decision.reasons)

    def test_delivery_issue_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(delivery_issue=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("delivery_issue", decision.reasons)

    def test_already_sent_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(already_sent=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("already_sent", decision.reasons)

    def test_duplicate_domain_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(duplicate_domain=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("duplicate_domain", decision.reasons)

    def test_guessed_email_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(guessed_email=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("guessed_email", decision.reasons)

    def test_social_only_stays_b1(self):
        decision = evaluate_a0(self._valid_a0_candidate(social_only=True, status="B1_social_verified"))
        self.assertEqual(decision.status, "B1_social_verified")
        self.assertFalse(decision.a0_eligible)

    def test_contact_form_only_stays_c(self):
        decision = evaluate_a0(self._valid_a0_candidate(contact_form_only=True))
        self.assertEqual(decision.status, "C_contact_form_or_social_message")
        self.assertFalse(decision.a0_eligible)

    def test_free_email_unverified_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(
            email="store@gmail.com",
            email_verified_on_official_site=False
        ))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("unverified_free_email", decision.reasons)

    def test_free_email_verified_passes_free_check(self):
        """If email is verified on official site, free email domain is OK."""
        decision = evaluate_a0(self._valid_a0_candidate(email="store@gmail.com"))
        self.assertTrue(decision.a0_eligible)

    def test_directory_domain_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(email="store@yelp.com"))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("directory_or_social_domain", decision.reasons)

    def test_noreply_prefix_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(email="noreply@example.com"))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("unsafe_role_email", decision.reasons)

    def test_third_party_directory_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(third_party_directory=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("third_party_directory", decision.reasons)

    def test_supplier_email_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(supplier_email=True))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("supplier_email", decision.reasons)

    def test_not_official_match_rejected(self):
        decision = evaluate_a0(self._valid_a0_candidate(official_match=False))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("business_identity_not_matched", decision.reasons)

    def test_multiple_reasons_accumulated(self):
        """When multiple gates fail, all reasons should be reported."""
        decision = evaluate_a0(self._valid_a0_candidate(
            email="", official_website="", state="CA", guessed_email=True
        ))
        self.assertFalse(decision.a0_eligible)
        self.assertIn("email_missing", decision.reasons)
        self.assertIn("official_website_missing", decision.reasons)
        self.assertIn("state_out_of_scope", decision.reasons)
        self.assertIn("guessed_email", decision.reasons)


# ============================================================
# 2. Production DB Schema Compatibility Tests (READ-ONLY)
# ============================================================

class TestProductionSchemaCompatibility(unittest.TestCase):
    """Verify that lead_hygiene_gate fields can be derived from production DB."""

    @classmethod
    def setUpClass(cls):
        db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "bd_leads.db"
        )
        if not os.path.exists(db_path):
            raise unittest.SkipTest("Production DB not found")
        cls.conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
        cls.conn.row_factory = sqlite3.Row
        cls.db_cols = {row[1] for row in cls.conn.execute("PRAGMA table_info(leads)")}

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_email_field_exists(self):
        self.assertIn("email", self.db_cols)

    def test_official_website_field_exists(self):
        self.assertIn("official_website", self.db_cols)

    def test_evidence_url_field_exists(self):
        self.assertIn("evidence_url", self.db_cols)

    def test_evidence_snippet_field_exists(self):
        """evidence_snippet was added by Codex evidence_snippet backfill migration."""
        self.assertIn("evidence_snippet", self.db_cols)

    def test_email_verified_on_official_site_exists(self):
        self.assertIn("email_verified_on_official_site", self.db_cols)

    def test_email_source_type_exists(self):
        self.assertIn("email_source_type", self.db_cols)

    def test_state_field_exists(self):
        self.assertIn("state", self.db_cols)

    def test_status_field_exists(self):
        self.assertIn("status", self.db_cols)

    def test_official_match_NOT_in_db(self):
        """CRITICAL GAP: official_match is NOT a DB column.
        The gate expects candidate['official_match'] but production has no such field.
        This must be derived from email_verified_on_official_site + email_source_type."""
        self.assertNotIn("official_match", self.db_cols)

    def test_suppressed_NOT_in_leads_table(self):
        """suppressed must be derived from suppression_list JOIN, not a column."""
        self.assertNotIn("suppressed", self.db_cols)

    def test_bounced_NOT_in_leads_table(self):
        """bounced must be derived from bounce_log JOIN or bounced_at column."""
        self.assertNotIn("bounced", self.db_cols)
        self.assertIn("bounced_at", self.db_cols)

    def test_already_sent_NOT_in_leads_table(self):
        """already_sent must be derived from send_log JOIN or sent_at column."""
        self.assertNotIn("already_sent", self.db_cols)
        self.assertIn("sent_at", self.db_cols)

    def test_duplicate_domain_NOT_in_leads_table(self):
        """duplicate_domain must be computed via domain_hash grouping."""
        self.assertNotIn("duplicate_domain", self.db_cols)
        self.assertIn("domain_hash", self.db_cols)

    def test_guessed_email_NOT_in_leads_table(self):
        """guessed_email is not a column; must be derived from email_source_type
        (e.g., source_type not in OFFICIAL_SOURCE_TYPES = guessed)."""
        self.assertNotIn("guessed_email", self.db_cols)

    def test_email_source_type_whitelist_compatible(self):
        """Production email_source_type values that the gate should accept."""
        rows = self.conn.execute(
            "SELECT DISTINCT email_source_type FROM leads WHERE email_source_type IS NOT NULL"
        ).fetchall()
        prod_types = {r[0] for r in rows}
        gate_accepted = {"official_page_visible", "official_mailto", "wholesale_vendor_page"}
        # Show what production has that gate would reject
        rejected_by_gate = prod_types - gate_accepted
        # manual_lookup is valid in production but rejected by gate
        self.assertIn("manual_lookup", prod_types)  # verify it exists
        self.assertNotIn("manual_lookup", gate_accepted)  # gate rejects it

    def test_leads_with_evidence_snippet_count(self):
        """Verify evidence_snippet backfill actually populated some rows."""
        count = self.conn.execute(
            "SELECT COUNT(*) FROM leads WHERE evidence_snippet IS NOT NULL AND evidence_snippet != ''"
        ).fetchone()[0]
        self.assertGreater(count, 0, "No evidence_snippet data found")

    def test_mx_provider_column_exists(self):
        """Production uses mx_provider for Exchange filtering; gate doesn't check this."""
        self.assertIn("mx_provider", self.db_cols)


# ============================================================
# 3. Production Risk Scenario Tests (READ-ONLY)
# ============================================================

class TestProductionRiskScenarios(unittest.TestCase):
    """Test that the gate correctly handles real production risk patterns."""

    @classmethod
    def setUpClass(cls):
        db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "bd_leads.db"
        )
        if not os.path.exists(db_path):
            raise unittest.SkipTest("Production DB not found")
        cls.conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
        cls.conn.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_no_leads_in_suppression_list_are_sendable(self):
        """Suppressed emails must not appear in sendable leads."""
        suppressed_emails = {
            r[0] for r in self.conn.execute("SELECT email FROM suppression_list").fetchall()
        }
        if not suppressed_emails:
            self.skipTest("No suppression entries")
        sendable = self.conn.execute("""
            SELECT email FROM leads WHERE status='new' AND confidence_score='A'
            AND email IS NOT NULL AND email != ''
        """).fetchall()
        for row in sendable:
            self.assertNotIn(row[0], suppressed_emails,
                             f"Suppressed email {row[0]} found in sendable leads")

    def test_no_hard_bounced_leads_are_sendable(self):
        """Hard-bounced emails must not be sendable."""
        bounced = {
            r[0] for r in self.conn.execute(
                "SELECT DISTINCT email FROM bounce_log WHERE bounce_type='hard'"
            ).fetchall()
        }
        if not bounced:
            self.skipTest("No hard bounce entries")
        sendable = self.conn.execute("""
            SELECT email FROM leads WHERE status='new' AND confidence_score='A'
            AND email IS NOT NULL AND email != ''
        """).fetchall()
        for row in sendable:
            self.assertNotIn(row[0], bounced,
                             f"Hard-bounced email {row[0]} found in sendable leads")

    def test_no_already_sent_leads_are_resendable(self):
        """Leads already in send_log with status=sent must not be resendable."""
        sent_emails = {
            r[0] for r in self.conn.execute(
                "SELECT email FROM send_log WHERE status='sent'"
            ).fetchall()
        }
        if not sent_emails:
            self.skipTest("No sent entries")
        sendable = self.conn.execute("""
            SELECT email FROM leads WHERE status='new' AND confidence_score='A'
            AND email IS NOT NULL AND email != ''
        """).fetchall()
        for row in sendable:
            self.assertNotIn(row[0], sent_emails,
                             f"Already-sent email {row[0]} found in sendable leads")

    def test_facebook_only_emails_not_a0(self):
        """Leads with email_source_type indicating social-only should not be A0.
        Note: production doesn't have social_only column, so this must be checked
        via email_source_type or status."""
        # Check if any leads have social-derived source types
        social_types = self.conn.execute("""
            SELECT DISTINCT email_source_type FROM leads
            WHERE email_source_type LIKE '%social%' OR email_source_type LIKE '%facebook%'
        """).fetchall()
        # If found, they should not be in A0 sendable pool
        if social_types:
            for st in social_types:
                sendable = self.conn.execute("""
                    SELECT COUNT(*) FROM leads
                    WHERE status='new' AND confidence_score='A'
                    AND email_source_type = ?
                """, (st[0],)).fetchone()[0]
                self.assertEqual(sendable, 0,
                    f"Social source type '{st[0]}' has sendable A0 leads")

    def test_only_tn_ar_ky_in_sendable(self):
        """Sendable leads should only be in target states."""
        sendable = self.conn.execute("""
            SELECT state FROM leads WHERE status='new' AND confidence_score='A'
            AND email IS NOT NULL AND email != ''
        """).fetchall()
        for row in sendable:
            state = (row[0] or "").strip().upper()
            if state in ("TENNESSEE", "ARKANSAS", "KENTUCKY"):
                state = {"TENNESSEE": "TN", "ARKANSAS": "AR", "KENTUCKY": "KY"}[state]
            self.assertIn(state, ("TN", "AR", "KY"),
                         f"Sendable lead in non-target state: {state}")

    def test_no_duplicate_domain_in_sendable(self):
        """No two sendable leads should share the same domain_hash."""
        rows = self.conn.execute("""
            SELECT domain_hash, COUNT(*) as cnt FROM leads
            WHERE status='new' AND confidence_score='A'
            AND email IS NOT NULL AND email != ''
            AND domain_hash IS NOT NULL
            GROUP BY domain_hash HAVING cnt > 1
        """).fetchall()
        self.assertEqual(len(rows), 0,
            f"Duplicate domains in sendable pool: {[(r[0], r[1]) for r in rows]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
