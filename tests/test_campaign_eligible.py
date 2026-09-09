"""Campaign Eligible 复核模块测试。"""
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from campaign_eligible import review_campaign_eligible, _is_third_party_email


def _mem_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE leads (
        id INTEGER PRIMARY KEY, store_name TEXT, city TEXT, state TEXT,
        email TEXT, official_website TEXT, organization_key TEXT,
        recipient_timezone TEXT, timezone_status TEXT, icp_route TEXT,
        icp_priority TEXT, icp_reason TEXT, status TEXT, confidence_score TEXT,
        auto_sendable INTEGER, email_source_type TEXT, evidence_url TEXT,
        evidence_snippet TEXT, sendable_for_automatic_schedule INTEGER)""")
    conn.execute("""CREATE TABLE send_log (
        id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, status TEXT,
        message_type TEXT, sent_at TEXT, plan_entry_id INTEGER)""")
    conn.execute("""CREATE TABLE suppression_list (email TEXT)""")
    conn.execute("""CREATE TABLE bounce_log (
        id INTEGER PRIMARY KEY, email TEXT, bounce_type TEXT, lead_id INTEGER)""")
    conn.execute("""CREATE TABLE reply_log (
        id INTEGER PRIMARY KEY, email TEXT, summary TEXT, suggested_action TEXT, lead_id INTEGER)""")
    conn.execute("""CREATE TABLE contact_form_url (id INTEGER PRIMARY KEY, lead_id INTEGER, url TEXT)""")
    return conn


def _lead(**kw):
    base = {
        "store_name": "Test Store", "city": "Nashville", "state": "TN",
        "email": "info@teststore.com", "official_website": "https://teststore.com",
        "organization_key": "org:domain:teststore.com",
        "recipient_timezone": "America/Chicago", "timezone_status": "RESOLVED",
        "icp_route": "A", "icp_priority": "P2", "icp_reason": "ok",
        "status": "new", "confidence_score": "B", "auto_sendable": 0,
        "email_source_type": "official_page_visible",
        "evidence_url": "https://teststore.com/contact", "evidence_snippet": "info@teststore.com",
        "sendable_for_automatic_schedule": 1,
    }
    base.update(kw)
    return base


class ThirdPartyEmailTests(unittest.TestCase):
    def test_store_domain_email_not_third_party(self):
        self.assertFalse(_is_third_party_email("info@teststore.com", "https://teststore.com"))

    def test_free_mailbox_not_third_party(self):
        # gmail/yahoo/aol 免费域不算第三方（官网确认过即可）
        self.assertFalse(_is_third_party_email("owner@gmail.com", "https://teststore.com"))

    def test_third_party_domain_blocked(self):
        # gamecentre.net vs moonlitecomics.com → 第三方
        self.assertTrue(_is_third_party_email("support@thegamecentre.net", "http://moonlitecomics.com"))

    def test_no_website_with_own_domain_third_party(self):
        # 无官网 + 非免费域 → 无法确认归属
        self.assertTrue(_is_third_party_email("info@unknown.com", ""))


class CampaignEligibleTests(unittest.TestCase):
    def test_clean_lead_eligible(self):
        conn = _mem_db()
        ld = _lead()
        r = review_campaign_eligible(ld, {"conn": conn})
        self.assertTrue(r["eligible"], r["blockers"])
        self.assertEqual(r["pool"], "CAMPAIGN_ELIGIBLE")
        conn.close()

    def test_missing_org_key_review(self):
        conn = _mem_db()
        ld = _lead(organization_key="")
        r = review_campaign_eligible(ld, {"conn": conn})
        self.assertFalse(r["eligible"])
        self.assertIn("organization_key_empty", r["blockers"])
        self.assertEqual(r["pool"], "NEEDS_MANUAL_REVIEW")
        conn.close()

    def test_timezone_unresolved_review(self):
        conn = _mem_db()
        ld = _lead(timezone_status="TIMEZONE_UNRESOLVED", recipient_timezone=None)
        r = review_campaign_eligible(ld, {"conn": conn})
        self.assertFalse(r["eligible"])
        self.assertTrue(any("timezone" in b for b in r["blockers"]))
        self.assertEqual(r["pool"], "NEEDS_MANUAL_REVIEW")
        conn.close()

    def test_timezone_override_allowed(self):
        conn = _mem_db()
        ld = _lead(timezone_status="TIMEZONE_UNRESOLVED", recipient_timezone=None)
        r = review_campaign_eligible(ld, {"conn": conn, "allow_timezone_unresolved": True})
        self.assertTrue(r["eligible"])
        conn.close()

    def test_third_party_blocked(self):
        conn = _mem_db()
        ld = _lead(email="support@thegamecentre.net", official_website="http://moonlitecomics.com")
        r = review_campaign_eligible(ld, {"conn": conn})
        self.assertFalse(r["eligible"])
        self.assertTrue(any("third_party" in b for b in r["blockers"]))
        self.assertEqual(r["pool"], "BLOCKED")
        conn.close()

    def test_public_mailbox_with_official_evidence_eligible(self):
        conn = _mem_db()
        # aol 免费邮箱，但 evidence_url 是官网 contact 页 → 官方证据
        ld = _lead(
            email="owner@aol.com",
            official_website="http://www.stoneystoys.com",
            evidence_url="http://www.stoneystoys.com/contact-us/",
            evidence_snippet="owner@aol.com (official contact page)",
            email_source_type="web_search_official",
        )
        r = review_campaign_eligible(ld, {"conn": conn})
        self.assertTrue(r["eligible"], r["blockers"])
        self.assertEqual(r["pool"], "CAMPAIGN_ELIGIBLE")
        conn.close()

    def test_public_mailbox_directory_only_manual_review(self):
        conn = _mem_db()
        # yahoo 免费邮箱 + 无官网 + 仅目录 evidence → NEEDS_MANUAL_REVIEW
        ld = _lead(
            email="kaijudogirl@yahoo.com",
            official_website="",
            evidence_url="https://www.allbiz.com/business/collectors-connection",
            evidence_snippet="kaijudogirl@yahoo.com (directory listing)",
            email_source_type="web_search_directory",
            organization_key="org:name:collectors-connection:dyersburg:TN",
        )
        r = review_campaign_eligible(ld, {"conn": conn})
        self.assertFalse(r["eligible"])
        self.assertTrue(any("public_mailbox_no_official_evidence" in b for b in r["blockers"]))
        self.assertEqual(r["pool"], "NEEDS_MANUAL_REVIEW")
        conn.close()

    def test_public_mailbox_directory_only_hotmail_manual_review(self):
        conn = _mem_db()
        # hotmail + 无官网 + 目录 evidence → NEEDS_MANUAL_REVIEW
        ld = _lead(
            email="ttdcardsfrankfort@hotmail.com",
            official_website="",
            evidence_url="https://www.bizarchive.com/business/ttd-cards-frankfort",
            evidence_snippet="ttdcardsfrankfort@hotmail.com (directory listing)",
            email_source_type="web_search_directory",
            organization_key="org:name:ttd-cards-frankfort:frankfort:KY",
        )
        r = review_campaign_eligible(ld, {"conn": conn})
        self.assertFalse(r["eligible"])
        self.assertTrue(any("public_mailbox_no_official_evidence" in b for b in r["blockers"]))
        self.assertEqual(r["pool"], "NEEDS_MANUAL_REVIEW")
        conn.close()


if __name__ == "__main__":
    unittest.main()
