"""Offline regressions for Phase 4A.8O contact-form and source semantics."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from broad_ready import _is_contact_form_only, is_broad_outreach_ready
from campaign_eligible import _is_official_evidence, review_campaign_eligible, select_candidates_for_plan
from campaign_eligible_v2 import review_campaign_eligible_v2, select_candidates_for_plan_v2
from production_adapter import build_candidate_from_db_row
from review_workflow import _is_contact_form
from tests.test_campaign_eligible import _lead, _mem_db


class ContactFormStateTests(unittest.TestCase):
    def test_no_email_contact_form_url(self):
        self.assertTrue(_is_contact_form_only({"email": "", "contact_form_url": "https://shop.test/contact"}))

    def test_no_email_contact_form_pool(self):
        self.assertTrue(_is_contact_form_only({"email": "", "status": "contact_form_pool"}))

    def test_email_and_contact_form_url(self):
        self.assertFalse(_is_contact_form_only({"email": "buyer@shop.test", "contact_form_url": "https://shop.test/contact"}))

    def test_email_overrides_stale_flags_and_status(self):
        lead = _lead(email="buyer@teststore.com", status="contact_form_pool",
                     contact_form_only=True, contact_form_url="https://teststore.com/contact")
        self.assertFalse(_is_contact_form_only(lead))
        self.assertFalse(_is_contact_form(lead))
        self.assertNotIn("contact_form_only", is_broad_outreach_ready(lead)["blockers"])

    def test_adapter_ignores_historical_contact_form_status_with_email(self):
        candidate = build_candidate_from_db_row({"id": 1, "email": "buyer@shop.test",
            "status": "contact_form_pool", "email_source_type": "official_mailto",
            "contact_form_url": "https://shop.test/contact"}, {})
        self.assertFalse(candidate["contact_form_only"])

    def test_email_bearing_form_pool_enters_v1_and_v2_candidate_selection(self):
        conn = _mem_db()
        try:
            conn.execute("ALTER TABLE leads ADD COLUMN evidence_checked_at TEXT")
            lead = _lead(status="contact_form_pool")
            lead.update(id=1, evidence_checked_at=datetime.now(timezone.utc).isoformat())
            names = list(lead)
            conn.execute(f"INSERT INTO leads ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                         tuple(lead.values()))
            self.assertEqual(len(select_candidates_for_plan(conn, 10)), 1)
            with patch("preflight_gate.query_mx", return_value=("ok", "now")):
                self.assertEqual(len(select_candidates_for_plan_v2(conn, 10)), 1)
        finally:
            conn.close()


class EvidenceSourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.conn = _mem_db()

    def tearDown(self):
        self.conn.close()

    def test_approved_sources_remain_allowed(self):
        for source in ("official_page_visible", "official_mailto", "first_party_structured_data",
                       "wholesale_vendor_page", "web_search_official"):
            with self.subTest(source=source):
                lead = _lead(email_source_type=source)
                self.assertTrue(_is_official_evidence(lead, lead["email"], lead["official_website"]))
                self.assertTrue(review_campaign_eligible(lead, {"conn": self.conn})["eligible"])

    def test_explicit_unapproved_sources_fail_closed_even_same_domain(self):
        for source in ("official_site_linked_facebook", "facebook_social", "social_only",
                       "third_party_directory", "search_snippet", "guessed_email",
                       "web_search_directory", "manual_lookup", "contact_form_only"):
            with self.subTest(source=source):
                lead = _lead(email_source_type=source, evidence_url="https://teststore.com/contact")
                self.assertFalse(_is_official_evidence(lead, lead["email"], lead["official_website"]))
                self.assertIn("evidence_source_not_approved",
                              review_campaign_eligible(lead, {"conn": self.conn})["blockers"])

    def test_legacy_empty_source_keeps_first_party_fallback(self):
        for source in ("", "legacy", "unknown", "manual_verified", "inventory_recovery", "website_extracted"):
            with self.subTest(source=source):
                lead = _lead(email_source_type=source, email="owner@gmail.com",
                             evidence_url="https://teststore.com/contact")
                self.assertTrue(_is_official_evidence(lead, lead["email"], lead["official_website"]))
                self.assertTrue(review_campaign_eligible(lead, {"conn": self.conn})["eligible"])

    def test_v2_does_not_promote_explicit_social_source(self):
        lead = _lead(email_source_type="official_site_linked_facebook",
                     evidence_checked_at=datetime.now(timezone.utc).isoformat())
        result = review_campaign_eligible_v2(lead, {"conn": self.conn, "mx_lookup": {"teststore.com": "ok"}})
        self.assertFalse(result["eligible"])
        self.assertIn("evidence_source_not_approved", result["blockers"])


if __name__ == "__main__":
    unittest.main()
