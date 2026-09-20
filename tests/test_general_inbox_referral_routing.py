"""Phase 4A.5: generic public inbox referral routing and frozen FSP metadata."""
from __future__ import annotations

import os
import sqlite3
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("BD_TRACKING_PEPPER", "test-pepper-for-unittest-only")

from bd_template import (
    _TEMPLATE_SHA256,
    apply_email_to_lead,
    get_email_for_lead,
    is_generic_public_inbox,
    route_template_for_lead,
)
from final_send_plan import create_plan


REFERRAL_KEY = "general_inbox_referral_v1_locked"
RETAIL_KEY = "retail_distributor_v5_locked"
CUSTOM_KEY = "custom_printing_production_v5_locked"
RETAIL_SHA = "ccb51505"
CUSTOM_SHA = "5893dbc9"


def _lead(email: str, store_type: str = "game_store") -> dict:
    return {
        "id": 41,
        "email": email,
        "store_name": "Example Games",
        "store_type": store_type,
        "status": "new",
        "confidence_score": "A",
        "auto_sendable": 1,
        "email_verified_on_official_site": 1,
        "email_source_type": "official_page_visible",
        "official_website": "https://example.test",
        "evidence_url": "https://example.test/contact",
        "evidence_snippet": email,
    }


def _fsp_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE final_send_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id TEXT, lead_id INTEGER, recipient_email TEXT, company_name TEXT,
            customer_type TEXT, lead_segment TEXT, template_id TEXT,
            source_city TEXT, source_state TEXT, evidence_url TEXT,
            hygiene_passed_at TEXT, message_type TEXT, outreach_batch_date TEXT,
            planned_sequence INTEGER, subject TEXT, body_text TEXT, body_html TEXT,
            status TEXT DEFAULT 'planned', skip_reason TEXT, sent_at TEXT,
            template_key TEXT, content_sha256 TEXT, renderer_version TEXT,
            renderer_sha256 TEXT, rendered_subject TEXT, rendered_text_body TEXT,
            rendered_html_body TEXT
        );
    """)
    return conn


class GeneralInboxReferralRoutingTests(unittest.TestCase):
    def test_exact_generic_local_parts_route_to_referral_template(self):
        for local_part in ("info", "service", "support", "hello", "contact", "office"):
            lead = _lead(f"{local_part}@example.test")
            self.assertTrue(is_generic_public_inbox(lead["email"]))
            self.assertEqual(route_template_for_lead(lead), REFERRAL_KEY)
            rendered = get_email_for_lead(lead)
            self.assertEqual(rendered["template_key"], REFERRAL_KEY)
            self.assertEqual(rendered["routing_reason"], "generic_public_inbox")
            self.assertIn("forward this note", rendered["body_text"])
            self.assertIn("Purchasing, Product, Sales, or Business Development", rendered["body_text"])

    def test_named_or_non_exact_local_parts_keep_existing_direct_routing(self):
        named = _lead("maria@example.test", "game_store")
        custom = _lead("buyer@example.test", "gift_shop")
        for non_generic in ("info+orders@example.test", "information@example.test", "contact.team@example.test"):
            self.assertFalse(is_generic_public_inbox(non_generic))
        self.assertEqual(route_template_for_lead(named), RETAIL_KEY)
        self.assertEqual(route_template_for_lead(custom), CUSTOM_KEY)
        self.assertEqual(get_email_for_lead(named)["routing_reason"], "store_type")
        self.assertEqual(get_email_for_lead(custom)["routing_reason"], "store_type")

    def test_existing_locked_template_hashes_are_unchanged(self):
        self.assertEqual(_TEMPLATE_SHA256[RETAIL_KEY], RETAIL_SHA)
        self.assertEqual(_TEMPLATE_SHA256[CUSTOM_KEY], CUSTOM_SHA)
        self.assertIn(REFERRAL_KEY, _TEMPLATE_SHA256)

    def test_existing_recipient_and_referral_metadata_freeze_into_fsp(self):
        lead = _lead("info@example.test")
        original_email = lead["email"]
        apply_email_to_lead(lead)
        lead["hygiene_passed_at"] = "2026-09-20T00:00:00+08:00"
        conn = _fsp_conn()
        try:
            plan_id = create_plan(conn, [lead], "2026-09-20", "new_outreach", eligible_check=lambda _lead: True)
            self.assertTrue(plan_id)
            row = dict(conn.execute("SELECT * FROM final_send_plan WHERE plan_id=?", (plan_id,)).fetchone())
            self.assertEqual(row["recipient_email"], original_email)
            self.assertEqual(row["template_id"], REFERRAL_KEY)
            self.assertEqual(row["template_key"], REFERRAL_KEY)
            self.assertEqual(row["content_sha256"], lead["content_sha256"])
            self.assertEqual(row["rendered_subject"], lead["email_subject"])
            self.assertEqual(row["rendered_text_body"], lead["email_body"])
            self.assertEqual(row["rendered_html_body"], lead["email_body_html"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM final_send_plan").fetchone()[0], 1)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
