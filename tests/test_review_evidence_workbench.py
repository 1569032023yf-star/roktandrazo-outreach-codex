"""Offline synthetic-DB coverage for the Phase 4A.8M evidence workbench."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bd_review_server as server
from migrations.migrate_city_outreach_40 import migrate
from review_evidence_workbench import (
    _fb_url, build_review_evidence, classify_facebook, official_linked_facebook,
    recovery_classification, render_facebook_page, verify_recovered_website,
    discover_official_facebook_candidates,
)
from scripts.phase4a8n_gate_audit import audit_one
from campaign_eligible import review_campaign_eligible, OFFICIAL_EVIDENCE_TYPES
from campaign_eligible_v2 import review_campaign_eligible_v2


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "review.db"
        conn = sqlite3.connect(self.path)
        conn.executescript("""
        CREATE TABLE leads (
          id INTEGER PRIMARY KEY, store_name TEXT, store_type TEXT, city TEXT, state TEXT,
          status TEXT, confidence_score TEXT, email TEXT, official_website TEXT,
          evidence_url TEXT, email_source_type TEXT, email_verified_on_official_site INTEGER,
          evidence_snippet TEXT, contact_form_url TEXT, domain_hash TEXT, mx_provider TEXT,
          sent_at TEXT, manual_decision TEXT, last_checked_at TEXT, review_reason_code TEXT,
          auto_sendable INTEGER DEFAULT 0, bounced_at TEXT, unsubscribed_at TEXT
        );
        CREATE TABLE send_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, status TEXT);
        CREATE TABLE suppression_list (email TEXT);
        CREATE TABLE bounce_log (email TEXT, bounce_type TEXT);
        CREATE TABLE reply_log (lead_id INTEGER, email TEXT, summary TEXT, suggested_action TEXT);
        CREATE TABLE system_config (key TEXT, value TEXT);
        CREATE TABLE fb_enrichment_queue (lead_id INTEGER, facebook_url TEXT, fb_check_status TEXT);
        """)
        conn.close()
        migrate(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""INSERT INTO leads
          (id,store_name,store_type,city,state,status,email,official_website,
           email_source_type,review_reason_code,review_status,organization_key,domain_hash)
          VALUES (1,'North Hobbies','retail_store','Ithaca','NY','manual_review_needed','',
                  'https://northhobbies.com','unknown','WEAK_EVIDENCE','pending','org_north','northhobbies.com')""")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def lead(self):
        return dict(self.conn.execute("SELECT * FROM leads WHERE id=1").fetchone())

    def test_recovery_high_and_evidence_model_unknown_mx(self):
        self.assertEqual(recovery_classification(self.conn, self.lead())["value"], "HIGH")
        evidence = build_review_evidence(self.conn, 1)
        self.assertTrue(evidence["ok"])
        self.assertEqual(evidence["mx_state"]["status"], "UNKNOWN")
        self.assertEqual(evidence["gate_matrix"]["mx_verification"]["state"], "UNKNOWN")
        self.assertFalse(evidence["v2_state"]["eligible"])
        self.assertIn("official_site_evidence", evidence)

    def test_history_and_suppression_excluded(self):
        self.conn.execute("INSERT INTO send_log (lead_id,email,status) VALUES (1,'buyer@northhobbies.com','sent')")
        self.conn.commit()
        self.assertEqual(recovery_classification(self.conn, self.lead())["value"], "NONE")
        self.conn.execute("DELETE FROM send_log")
        self.conn.execute("UPDATE leads SET email='buyer@northhobbies.com' WHERE id=1")
        self.conn.execute("INSERT INTO suppression_list (email) VALUES ('buyer@northhobbies.com')")
        self.conn.commit()
        self.assertEqual(recovery_classification(self.conn, self.lead())["value"], "NONE")

    def test_bounce_rejected_and_already_safe_excluded(self):
        for change in ("bounced_at='2026-01-01'", "review_status='rejected'", "auto_sendable=1"):
            self.conn.execute("UPDATE leads SET bounced_at=NULL,review_status='pending',auto_sendable=0 WHERE id=1")
            self.conn.execute("UPDATE leads SET " + change + " WHERE id=1")
            self.conn.commit()
            self.assertEqual(recovery_classification(self.conn, self.lead())["value"], "NONE")

    def test_facebook_provenance_a_b_c_and_email_classes(self):
        lead = self.lead()
        raw = {"name":"North Hobbies", "about":"North Hobbies in Ithaca NY: hello@northhobbies.com",
               "email":"hello@northhobbies.com", "website":"https://northhobbies.com"}
        a = classify_facebook(lead, raw, True)
        self.assertEqual(a["social_email_class"], "CLASS_A_OFFICIAL_LINKED_SOCIAL_EMAIL")
        self.assertFalse(a["safe_eligible_from_social"])
        b = classify_facebook(lead, raw, False)
        self.assertEqual(b["social_email_class"], "CLASS_B_STRONG_MATCH_SOCIAL_EMAIL")
        c = classify_facebook(lead, {"name":"Unrelated", "about":"hi@other.com", "email":"hi@other.com"}, False)
        self.assertEqual(c["social_email_class"], "CLASS_C_WEAK_SOCIAL_EMAIL")
        self.assertNotEqual(c["facebook_provenance_tier"], a["facebook_provenance_tier"])

    def test_no_hidden_email_and_no_personal_profile(self):
        lead = self.lead()
        result = classify_facebook(lead, {"name":"North Hobbies","about":"No visible email",
                                           "email":"hidden@northhobbies.com"}, True)
        self.assertEqual(result["public_email"], "")
        self.assertFalse(_fb_url("https://www.facebook.com/profile.php?id=123"))
        self.assertFalse(_fb_url("https://evil.example.com/northhobbies"))

    def test_official_link_must_be_on_accepted_page(self):
        lead = self.lead()
        page = {"text":"North Hobbies", "html":'<a href="https://www.facebook.com/northhobbies">FB</a>'}
        with patch("review_evidence_workbench._fetch_official_pages", return_value=[page]):
            self.assertTrue(official_linked_facebook(lead, "https://www.facebook.com/northhobbies"))
            self.assertFalse(official_linked_facebook(lead, "https://www.facebook.com/unrelated"))

    def test_discovery_is_verified_deduplicated_and_business_only(self):
        lead = self.lead()
        page = {"final_url":"https://northhobbies.com", "text":"North Hobbies", "html": (
            '<a href="https://www.facebook.com/northhobbies">A</a>'
            '<a href="https://www.facebook.com/northhobbies/?ref=site">A2</a>'
            '<a href="https://www.facebook.com/people/North/123">person</a>'
            '<a href="https://www.facebook.com/profile.php?id=1">profile</a>')}
        with patch("review_evidence_workbench._verified_official_page", return_value=page):
            found = discover_official_facebook_candidates(lead)
        self.assertEqual(found["status"], "found")
        self.assertEqual(len(found["candidates"]), 1)
        self.assertEqual(found["source_url"], "https://northhobbies.com")
        with patch("review_evidence_workbench._verified_official_page", return_value={}):
            self.assertEqual(discover_official_facebook_candidates(lead)["status"], "official_website_unverified")
        page["html"] = "<p>No social links</p>"
        with patch("review_evidence_workbench._verified_official_page", return_value=page):
            self.assertEqual(discover_official_facebook_candidates(lead)["status"],
                             "official_facebook_link_not_found")

    def test_review_api_uses_shared_discovery_when_no_saved_url(self):
        previous_db = server.DB_PATH
        server.DB_PATH = self.path
        try:
            discovered = {"status":"found", "selected":"https://www.facebook.com/northhobbies",
                          "candidates":["https://www.facebook.com/northhobbies"],
                          "source_url":"https://northhobbies.com"}
            rendered = {"status":"opened", "public_email":"hello@northhobbies.com",
                        "facebook_provenance_tier":"TIER_A_OFFICIAL_SITE_LINKED_FACEBOOK",
                        "safe_eligible_from_social":False}
            def run_now(lead_id, task):
                key, result = task()
                server._EVIDENCE_RESULTS[lead_id] = {key:result, "job_status":"complete"}
                return json.dumps({"ok":True})
            with patch.object(server, "_start_evidence_job", side_effect=run_now), \
                 patch.object(server, "discover_official_facebook_candidates", return_value=discovered) as find, \
                 patch.object(server, "render_facebook_page", return_value=rendered) as render:
                self.assertTrue(json.loads(server.api_fetch_facebook_evidence({"lead_id":1}))["ok"])
            find.assert_called_once()
            render.assert_called_once()
            evidence = json.loads(server.api_review_evidence(1))["facebook_evidence"]
            self.assertEqual(evidence["facebook_candidates_found"], 1)
            self.assertEqual(evidence["public_email"], "hello@northhobbies.com")
            self.assertFalse(evidence["safe_eligible_from_social"])
        finally:
            server.DB_PATH = previous_db
            server._EVIDENCE_RESULTS.pop(1, None)

    def test_review_api_existing_url_does_not_rediscover(self):
        previous_db = server.DB_PATH
        server.DB_PATH = self.path
        self.conn.execute("INSERT INTO fb_enrichment_queue (lead_id,facebook_url,fb_check_status) "
                          "VALUES (1,'https://www.facebook.com/northhobbies','pending')")
        self.conn.commit()
        try:
            with patch.object(server, "_start_evidence_job", side_effect=lambda _id, task: json.dumps(task()[1])) as launch, \
                 patch.object(server, "discover_official_facebook_candidates") as find, \
                 patch.object(server, "render_facebook_page", return_value={"status":"opened"}):
                result = json.loads(server.api_fetch_facebook_evidence({"lead_id":1}))
            self.assertEqual(result["status"], "opened")
            self.assertEqual(result["facebook_candidates_found"], 1)
            launch.assert_called_once()
            find.assert_not_called()
        finally:
            server.DB_PATH = previous_db

    def test_review_api_no_official_facebook_link_is_explicit(self):
        previous_db = server.DB_PATH
        server.DB_PATH = self.path
        try:
            with patch.object(server, "_start_evidence_job", side_effect=lambda _id, task: json.dumps(task()[1])), \
                 patch.object(server, "discover_official_facebook_candidates", return_value={
                     "status":"official_facebook_link_not_found", "selected":"", "candidates":[],
                     "source_url":"https://northhobbies.com"}), \
                 patch.object(server, "render_facebook_page") as render:
                result = json.loads(server.api_fetch_facebook_evidence({"lead_id":1}))
            self.assertEqual(result["status"], "official_facebook_link_not_found")
            render.assert_not_called()
        finally:
            server.DB_PATH = previous_db

    def test_canary_imports_the_same_discovery_function(self):
        source = (Path(__file__).resolve().parent.parent / "scripts" / "phase4a8m_canary.py").read_text(encoding="utf-8")
        self.assertIn("discover_official_facebook_candidates", source)
        self.assertNotIn("def discover_official_facebook_link(", source)

    def test_candidate_audit_org_history_precedes_email_novelty_and_mx_fails_closed(self):
        record = {"lead_id":1,"public_email":"hello@northhobbies.com",
                  "facebook_url":"https://www.facebook.com/northhobbies",
                  "visible_email_excerpt":"Call hello@northhobbies.com",
                  "facebook_provenance_tier":"TIER_A_OFFICIAL_SITE_LINKED_FACEBOOK",
                  "identity_match_signals":{"official_site_direct_link":True,"name":True},
                  "fetched_at":"2026-09-29T00:00:00+00:00"}
        unknown = audit_one(self.conn, record, lambda _: ("dns_error", "now"))
        self.assertTrue(unknown["NEW_EMAIL_STRING"])
        self.assertFalse(unknown["MX_PASS"])
        self.assertFalse(unknown["CLASS_A_READY_EXCEPT_POLICY"])
        self.conn.execute("INSERT INTO send_log (lead_id,email,status) VALUES (1,'old@northhobbies.com','sent')")
        self.conn.commit()
        history = audit_one(self.conn, record, lambda _: ("ok", "now"))
        self.assertTrue(history["NEW_EMAIL_STRING"])
        self.assertTrue(history["ORGANIZATION_PREVIOUSLY_SENT"])
        self.assertFalse(history["HISTORY_CLEAN"])
        self.assertEqual(history["BUCKET"], "B_HISTORY_BLOCKED")

    def test_current_policy_source_is_not_allowlisted_or_promoted_by_domain_fallback(self):
        self.assertNotIn("official_site_linked_facebook", OFFICIAL_EVIDENCE_TYPES)
        self.conn.execute("UPDATE leads SET status='new',email='hello@northhobbies.com',"
                          "email_source_type='official_site_linked_facebook',"
                          "evidence_url='https://www.facebook.com/northhobbies',"
                          "evidence_snippet='hello@northhobbies.com',"
                          "timezone_status='RESOLVED',recipient_timezone='America/New_York' WHERE id=1")
        self.conn.commit()
        lead = self.lead()
        lead["evidence_checked_at"] = "2026-09-29T00:00:00+00:00"
        # Phase 4A.8O closes the fallback documented by the former test.
        v1 = review_campaign_eligible(lead, {"conn":self.conn})
        v2 = review_campaign_eligible_v2(lead, {"conn":self.conn,
                                               "mx_lookup":{"northhobbies.com":"ok"}})
        self.assertFalse(v1["eligible"])
        self.assertFalse(v2["eligible"])
        self.assertIn("evidence_source_not_approved", v1["blockers"])
        self.assertIn("evidence_source_not_approved", v2["blockers"])

    def test_login_captcha_not_found_are_fail_soft(self):
        lead = self.lead()
        for status in ("facebook_login_required", "facebook_captcha", "facebook_page_not_found"):
            with patch.dict("os.environ", {"ROKT_DEV_CONTROLLED_WEB":"1"}):
                with patch("review_evidence_workbench.read_fb_page_with_limiter", return_value={"error":status}):
                    class FakePage:
                        def new_page(self): return object()
                        def close(self): pass
                    class FakeBrowser:
                        chromium = None
                        def __init__(self):
                            self.chromium = self
                        def launch_persistent_context(self,*a,**k): return FakePage()
                    class FakeContext:
                        def __enter__(self): return FakeBrowser()
                        def __exit__(self,*args): return None
                    with patch("playwright.sync_api.sync_playwright", return_value=FakeContext()):
                        result = render_facebook_page(lead,"https://www.facebook.com/northhobbies")
                        self.assertEqual(result["status"], status, result)
        self.assertEqual(render_facebook_page(lead,"https://www.facebook.com/northhobbies")["status"],
                         "controlled_web_not_enabled")

    def test_website_handoff_uses_canonical_verifier_and_extractor(self):
        lead = self.lead()
        page = {"text":"North Hobbies email hello@northhobbies.com", "html":"", "url":"https://northhobbies.com",
                "requested_url":"https://northhobbies.com","final_url":"https://northhobbies.com",
                "method":"official_homepage","http_status":200,"http_success":True,"tls_success":True,
                "fetched_at":"2026-09-29T00:00:00Z","content_hash":"abc"}
        with patch("review_evidence_workbench._fetch_official_pages", return_value=[page]):
            result = verify_recovered_website(lead,"https://northhobbies.com")
        self.assertTrue(result["verified"])
        self.assertTrue(result["facebook_to_official_site_email_found"])
        self.assertEqual(result["first_party_email_evidence"]["email"], "hello@northhobbies.com")
        self.assertFalse(result["persisted"])
        self.assertFalse(verify_recovered_website(lead,"http://127.0.0.1/")["verified"])

    def test_legacy_manual_a0_requires_manual_evidence(self):
        with patch.object(server, "api_manual_email", return_value=json.dumps({"ok":False,"error":"evidence_required"})) as gate:
            result = json.loads(server.api_manual_a0({"lead_id":1,"email":"guessed@northhobbies.com"}))
        self.assertFalse(result["ok"])
        gate.assert_called_once()

    def test_legacy_manual_a0_cannot_promote_without_evidence(self):
        previous_db = server.DB_PATH
        server.DB_PATH = self.path
        try:
            before = dict(self.conn.execute("SELECT * FROM leads WHERE id=1").fetchone())
            result = json.loads(server.api_manual_a0({"lead_id":1,"email":"guessed@northhobbies.com"}))
            after = dict(self.conn.execute("SELECT * FROM leads WHERE id=1").fetchone())
            self.assertFalse(result.get("promoted"))
            self.assertEqual(before, after)
        finally:
            server.DB_PATH = previous_db

    def test_evidence_decision_audit_never_mutates_lead(self):
        previous_db = server.DB_PATH
        server.DB_PATH = self.path
        server._EVIDENCE_RESULTS[1] = {"facebook":{
            "status":"opened","facebook_page_url":"https://www.facebook.com/northhobbies",
            "facebook_provenance_tier":"TIER_A_OFFICIAL_SITE_LINKED_FACEBOOK"}}
        try:
            before = dict(self.conn.execute("SELECT * FROM leads WHERE id=1").fetchone())
            accepted = json.loads(server.api_evidence_decision(
                {"lead_id":1,"action":"accept_facebook_identity","reason":"Official link and name match"}))
            self.assertTrue(accepted["ok"])
            after = dict(self.conn.execute("SELECT * FROM leads WHERE id=1").fetchone())
            self.assertEqual(before, after)
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM review_log WHERE lead_id=1").fetchone()[0],1)
            rejected_match = json.loads(server.api_evidence_decision(
                {"lead_id":1,"action":"reject_facebook_match","reason":"Page belongs to another store"}))
            self.assertTrue(rejected_match["ok"])
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM review_log WHERE lead_id=1").fetchone()[0],2)
            self.assertEqual(before, dict(self.conn.execute("SELECT * FROM leads WHERE id=1").fetchone()))
            server._EVIDENCE_RESULTS[1]["facebook"]["facebook_provenance_tier"] = "TIER_C_WEAK_OR_UNVERIFIED_FACEBOOK"
            rejected = json.loads(server.api_evidence_decision(
                {"lead_id":1,"action":"accept_facebook_identity","reason":"weak"}))
            self.assertFalse(rejected["ok"])
        finally:
            server.DB_PATH = previous_db
            server._EVIDENCE_RESULTS.pop(1,None)

    def test_browser_action_excludes_history_blocked_lead(self):
        previous_db = server.DB_PATH
        server.DB_PATH = self.path
        self.conn.execute("UPDATE leads SET review_status='rejected' WHERE id=1")
        self.conn.commit()
        try:
            with patch.object(server, "_start_evidence_job") as launch:
                result = json.loads(server.api_fetch_facebook_evidence({"lead_id":1}))
            self.assertEqual(result["error"], "history_blocked")
            launch.assert_not_called()
        finally:
            server.DB_PATH = previous_db

    def test_ui_sections_and_safe_external_links(self):
        script = (Path(__file__).resolve().parent.parent / "review_evidence_ui.js").read_text(encoding="utf-8")
        for heading in ("Merchant", "Why This Needs Review", "Current Email", "Official Site Evidence",
                        "Facebook Evidence", "Recovered Website", "Safety and Eligibility Gates",
                        "Review Actions", "Audit History"):
            self.assertIn(heading, script)
        self.assertIn('anchor.rel = "noopener noreferrer"', script)
        self.assertIn('el.textContent = String(value)', script)
        self.assertNotIn("iframe", script.lower())


if __name__ == "__main__":
    unittest.main()
