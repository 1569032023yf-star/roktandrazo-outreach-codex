"""Offline safety tests. Fixture claims/addresses never represent production evidence."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
import re
import sqlite3
from contextlib import closing
import tempfile
import unittest
from unittest.mock import patch

import send_resumption as s
import v6_outreach as v
import controlled_v6_test as internal


def policy():
    now = datetime.now(s.SH)
    return {"authorization_scope": "phase5a-v6-controlled-resumption", "postal_address_verified": True,
        "postal_address_evidence": "FIXTURE ONLY", "verified_postal_address": "123 Fixture Lane, Test City, ZZ 00000",
        "verified_claims": {x: True for x in s.CLAIMS}, "enabled": True, "follow_up_enabled": False,
        "emergency_stop": False, "risk_signals": [], "stage": 1, "daily_cap": 5,
        "evidence": {k: {"passed": True, "reference": "FIXTURE ONLY", "checked_at": now.isoformat()} for k in s.LIVE_EVIDENCE},
        "verified_from_email": "sender@example.invalid", "reviewed_leads": {}}


def lead(p, i=1, kind="toy_store", email=None):
    d = {"id": i, "store_name": "Toy & Book Shop", "store_type": kind, "email": email or f"info{i}@example.invalid",
         "organization_key": f"org:{i}", "evidence_url": "https://example.invalid/about"}
    p["reviewed_leads"][str(i)] = {"identity_verified": True, "organization_key": d["organization_key"],
        "email": d["email"], "evidence_url": d["evidence_url"], "business_type_verified": True,
        "business_type": kind, "recipient_role": "unknown", "product_fit_verified": True,
        "business_contact_basis_verified": True}
    return d


def rendered_lead(p, i=1, **kwargs):
    d = lead(p, i, **kwargs)
    content = v.render(d, p)
    d.update(template_id=content["template_key"], template_key=content["template_key"],
        email_subject=content["subject"], email_body=content["body_text"], email_body_html=content["body_html"],
        content_sha256=content["content_sha256"], evidence_url="https://example.invalid/contact")
    return d


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.p = policy()
        self.lead = lead(self.p)

    def test_full_pinned_hashes(self):
        for key in v.TEMPLATES:
            self.assertEqual(len(v.LOCKED_SHA256[key]), 64)
            self.assertEqual(v.canonical_hash(key), v.LOCKED_SHA256[key])

    def test_exact_user_subjects_and_no_links_tracking(self):
        for kind, key, subject in [("toy_store", v.RETAIL, "Puzzles & card games for Toy & Book Shop?"),
            ("greeting_card_brand", v.CUSTOM, "Custom product production for Toy & Book Shop"),
            ("unknown", v.REFERRAL, "Right contact at Toy & Book Shop?")]:
            d = lead(self.p, kind=kind)
            result = v.render(d, self.p)
            self.assertEqual(result["template_key"], key)
            self.assertEqual(result["subject"], subject)
            self.assertNotRegex(result["body_html"], r"https?://|<img|href=|src=")
            self.assertFalse(result["has_pixel"])
            self.assertIn("Business mailing address: 123 Fixture Lane", result["body_text"])

    def test_text_html_semantic_parity(self):
        result = v.render(self.lead, self.p)
        text = unescape(re.sub("<[^>]+>", " ", result["body_html"]))
        self.assertEqual(" ".join(text.split()), " ".join(result["body_text"].split()))

    def test_info_toy_gets_retail(self):
        self.assertEqual(v.route(lead(self.p, kind="toy_store", email="info@example.invalid"), self.p), v.RETAIL)

    def test_hello_brand_gets_custom(self):
        self.assertEqual(v.route(lead(self.p, kind="greeting_card_brand", email="hello@example.invalid"), self.p), v.CUSTOM)

    def test_gift_and_museum_are_retail(self):
        for kind in ("gift_shop", "museum_store"):
            self.assertEqual(v.route(lead(self.p, kind=kind), self.p), v.RETAIL)

    def test_unverified_manual_override_blocked(self):
        self.lead["template_override"] = v.CUSTOM
        with self.assertRaisesRegex(ValueError, "MANUAL_TEMPLATE"):
            v.route(self.lead, self.p)

    def test_verified_manual_override_first(self):
        self.lead["template_override"] = v.CUSTOM
        self.p["reviewed_leads"]["1"]["approved_template_override"] = v.CUSTOM
        self.assertEqual(v.route(self.lead, self.p), v.CUSTOM)

    def test_name_heuristic_cannot_create_identity(self):
        self.lead["store_name"] = "Museum Gift Factory"
        self.p["reviewed_leads"] = {}
        with self.assertRaisesRegex(ValueError, "IDENTITY_REVIEW"):
            v.route(self.lead, self.p)

    def test_unverified_business_support_refers(self):
        review = self.p["reviewed_leads"]["1"]
        review.update(business_type_verified=False, recipient_role="support")
        self.assertEqual(v.route(self.lead, self.p), v.REFERRAL)

    def test_recipient_change_rejected(self):
        self.lead["email"] = "other@example.invalid"
        with self.assertRaisesRegex(ValueError, "RECIPIENT_REVIEW_MISMATCH"):
            v.render(self.lead, self.p)

    def test_missing_postal_blocks_customers(self):
        self.p["verified_postal_address"] = ""
        with self.assertRaisesRegex(ValueError, "POSTAL_ADDRESS"):
            v.render(self.lead, self.p)

    def test_claims_must_be_confirmed(self):
        self.p["verified_claims"][s.CLAIMS[0]] = False
        with self.assertRaisesRegex(ValueError, "CLAIMS_UNVERIFIED"):
            v.render(self.lead, self.p)

    def test_header_html_and_placeholder_injection_rejected(self):
        for name in ("x\r\nBcc: evil", "<img src=x>", "{signature}", "www.example.invalid"):
            self.lead["store_name"] = name
            with self.assertRaises(ValueError):
                v.render(self.lead, self.p)

    def test_frozen_body_tampering_rejected(self):
        item = v.render(self.lead, self.p)
        item["body_html"] += "<img src=x>"
        with self.assertRaisesRegex(ValueError, "CONTENT_MISMATCH"):
            v.validate_message(item, self.lead, self.p)

    def test_v5_plan_rejected(self):
        item = v.render(self.lead, self.p)
        item["template_id"] = "retail_distributor_v5_locked"
        with self.assertRaisesRegex(ValueError, "V6_ONLY"):
            v.validate_message(item, self.lead, self.p)

    def test_template_mutation_rejected(self):
        changed = dict(v.TEMPLATES)
        changed[v.RETAIL] = ("Changed", changed[v.RETAIL][1])
        with patch.object(v, "TEMPLATES", changed), self.assertRaisesRegex(ValueError, "INTEGRITY"):
            v.render(self.lead, self.p)


class EvidenceTests(unittest.TestCase):
    def test_missing_expired_failed_evidence_and_emergency_stop(self):
        for key in s.LIVE_EVIDENCE:
            for change in ({"passed": False}, {"checked_at": (datetime.now(s.SH)-timedelta(hours=25)).isoformat()}):
                p = policy()
                p["evidence"][key].update(change)
                with self.assertRaises(ValueError):
                    s.require_ready(p)
        for field, val in (("emergency_stop", True), ("follow_up_enabled", True), ("risk_signals", ["hard_bounce"]), ("enabled", False)):
            p = policy()
            p[field] = val
            with self.assertRaises(ValueError):
                s.require_ready(p)

    def test_first_cap_and_escalation_24h(self):
        p = policy()
        self.assertEqual(s.require_ready(p), 5)
        p.update(stage=2, daily_cap=10)
        with self.assertRaises(ValueError):
            s.require_ready(p)
        now = datetime.now(s.SH)
        p["stage_feedback"] = {"1": {"passed": True, "reference": "FIXTURE", "started_at": (now-timedelta(hours=23)).isoformat(), "reviewed_at": now.isoformat()}}
        with self.assertRaises(ValueError):
            s.require_ready(p)
        p["stage_feedback"]["1"]["started_at"] = (now-timedelta(hours=25)).isoformat()
        self.assertEqual(s.require_ready(p), 10)

    def test_cap_configuration_cannot_raise_stage_one(self):
        p = policy()
        p["daily_cap"] = 40
        with self.assertRaisesRegex(ValueError, "CAP_MISMATCH"):
            s.require_ready(p)


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name)/"test.db")
        self.now = datetime(2026, 10, 19, 23, 0, tzinfo=s.SH)
        self.p = policy()
        for ev in self.p["evidence"].values():
            ev["checked_at"] = self.now.isoformat()
        with closing(sqlite3.connect(self.db)) as c, c:
            c.executescript("CREATE TABLE leads(id INTEGER PRIMARY KEY, organization_key TEXT); CREATE TABLE final_send_plan(id INTEGER PRIMARY KEY, lead_id INTEGER, message_type TEXT, outreach_batch_date TEXT, status TEXT);")
            for i in range(1, 21):
                c.execute("INSERT INTO leads VALUES (?,?)", (i, f"org:{i}"))
                c.execute("INSERT INTO final_send_plan VALUES (?,?,'new_outreach','2026-10-19','planned')", (i, i))

    def reserve(self, i):
        s.reserve_smtp(self.db, i, f"org:{i}", "2026-10-19", self.p, now=self.now)

    def test_sixth_blocked_across_batches(self):
        for i in range(1, 6):
            self.reserve(i)
        with self.assertRaisesRegex(ValueError, "DAILY_CAP|PILOT_FEEDBACK"):
            self.reserve(6)

    def test_concurrent_workers_cannot_exceed_five(self):
        def worker(i):
            try:
                self.reserve(i)
                return 1
            except ValueError:
                return 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(worker, range(1, 21))), 5)

    def test_duplicate_plan_and_organization_blocked(self):
        self.reserve(1)
        with self.assertRaises(ValueError):
            self.reserve(1)
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("UPDATE leads SET organization_key='org:1' WHERE id=2")
        with self.assertRaisesRegex(ValueError, "ALREADY_RESERVED"):
            s.reserve_smtp(self.db, 2, "org:1", "2026-10-19", self.p, now=self.now)

    def test_spoofed_plan_org_or_date_blocked(self):
        with self.assertRaisesRegex(ValueError, "PLAN_CHANGED"):
            s.reserve_smtp(self.db, 1, "fake", "2026-10-19", self.p, now=self.now)
        with self.assertRaisesRegex(ValueError, "BUSINESS_DATE"):
            s.reserve_smtp(self.db, 1, "org:1", "2026-10-18", self.p, now=self.now)

    def test_quota_not_freed_by_ambiguous_or_failed_result(self):
        self.reserve(1)
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("UPDATE final_send_plan SET status='failed' WHERE id=1")
            self.assertEqual(s.used_slots(c, "2026-10-19"), 1)


    def test_durable_halt_blocks_fsp_and_later_smtp(self):
        s.halt_new_outreach(self.db, "FIXTURE_SMTP_ERROR")
        with self.assertRaisesRegex(ValueError, "DURABLE_EMERGENCY_HALT"):
            self.reserve(1)
        with closing(sqlite3.connect(self.db)) as conn, self.assertRaisesRegex(ValueError, "DURABLE_EMERGENCY_HALT"):
            s.remaining_plan_capacity(conn, "2026-10-19", policy())


class InternalTests(unittest.TestCase):
    def test_three_internal_versions_no_address_no_link(self):
        p = {"internal_test_only": True, "controlled_test_recipients": ["qa@example.invalid"], "test_ownership_reference": "FIXTURE"}
        for key in v.TEMPLATES:
            m = v.render_internal_test(key, "qa@example.invalid", p)
            self.assertIn("[INTERNAL V6 TEST]", m["subject"])
            self.assertNotIn("Business mailing address:", m["body_text"])
            self.assertNotIn("{address}", m["body_text"])
            self.assertTrue(m["test_only"])
            self.assertEqual(m["attachments"], [])

    def test_other_or_obsolete_recipient_blocked(self):
        p = {"internal_test_only": True, "controlled_test_recipients": ["new@example.invalid"], "test_ownership_reference": "FIXTURE"}
        with self.assertRaises(ValueError):
            v.render_internal_test(v.RETAIL, "old@example.invalid", p)

    def test_development_cannot_send_internal_mail(self):
        p = {"internal_test_only": True, "controlled_test_recipients": ["qa@example.invalid"], "test_ownership_reference": "FIXTURE"}
        with patch.object(internal, "load_test_policy", return_value=p), self.assertRaisesRegex(ValueError, "DEVELOPMENT_INTERNAL_SMTP_BLOCKED"):
            internal.send_internal_tests(send=True)


    def test_mocked_internal_transport_three_only_and_durable_no_retry(self):
        from contextlib import ExitStack
        from unittest.mock import Mock
        import bd_sender
        with tempfile.TemporaryDirectory() as root:
            policy = {"internal_test_only": True, "allow_internal_without_postal_address": True,
                "controlled_test_recipients": ["qa@example.invalid"], "test_ownership_reference": "FIXTURE",
                "authorized_at": datetime.now(s.SH).isoformat(), "test_run_id": "FIXTURE-RUN",
                "verified_from_email": "sender@example.invalid"}
            server = Mock()
            server.sendmail.return_value = {}
            with ExitStack() as stack:
                stack.enter_context(patch.object(internal, 'ROOT', Path(root)))
                stack.enter_context(patch.object(internal, 'AUDIT_PATH', Path(root)/'audit.sqlite3'))
                stack.enter_context(patch.object(internal, 'load_test_policy', return_value=policy))
                stack.enter_context(patch('env_loader.get_sender_info',return_value={'email':'sender@example.invalid'}))
                stack.enter_context(patch.object(bd_sender,'_create_connection',return_value=server))
                result = internal.send_internal_tests(send=True)
                self.assertEqual(len(result['results']),3)
                self.assertEqual(server.sendmail.call_count,3)
                for call in server.sendmail.call_args_list:
                    self.assertEqual(call.args[1], ['qa@example.invalid'])
                    self.assertIn('Message-ID:', call.args[2])
                    self.assertIn('Reply-To:', call.args[2])
                with self.assertRaises(sqlite3.IntegrityError):
                    internal.send_internal_tests(send=True)
                self.assertEqual(server.sendmail.call_count,3)
                self.assertFalse((Path(root)/'bd_leads.db').exists())

    def test_internal_ready_rejects_expired_or_sender_mismatch(self):
        p = {"internal_test_only":True,"allow_internal_without_postal_address":True,
            "controlled_test_recipients":["qa@example.invalid"],"test_ownership_reference":"FIXTURE",
            "verified_from_email":"sender@example.invalid","authorized_at":(datetime.now(s.SH)-timedelta(hours=25)).isoformat(),
            "test_run_id":"FIXTURE"}
        with self.assertRaisesRegex(ValueError,'EXPIRED'):
            internal.require_test_ready(p,'qa@example.invalid','sender@example.invalid')
        with self.assertRaisesRegex(ValueError,'SENDER_IDENTITY'):
            internal.require_test_ready(p,'qa@example.invalid','different@example.invalid')


class IntegrationTests(unittest.TestCase):
    """Real FSP/preflight/SMTP-budget gates against an isolated fixture DB."""
    def setUp(self):
        import final_send_plan as f
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "integration.sqlite3"
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.execute("CREATE TABLE leads(id INTEGER PRIMARY KEY,store_name TEXT,email TEXT,organization_key TEXT,store_type TEXT,timezone_status TEXT,recipient_timezone TEXT)")
        fields = ','.join(x + (' INTEGER' if x == 'lead_id' else ' TEXT') for x in f._BASE_ENTRY_FIELDS)
        self.conn.execute("CREATE TABLE final_send_plan(id INTEGER PRIMARY KEY,plan_id TEXT," + fields + ",status TEXT DEFAULT 'planned',skip_reason TEXT)")
        self.p = policy()
        self.date = datetime.now(s.SH).date().isoformat()
        self.items = []
        for i in range(1, 8):
            d = rendered_lead(self.p, i)
            d.update(status="new",confidence_score="A",auto_sendable=1,email_verified_on_official_site=1,
                email_source_type="official_page_visible",evidence_snippet="FIXTURE",timezone_status="RESOLVED",recipient_timezone="America/Chicago")
            self.conn.execute("INSERT INTO leads VALUES(?,?,?,?,?,?,?)", (i,d['store_name'],d['email'],d['organization_key'],d['store_type'],d['timezone_status'],d['recipient_timezone']))
            self.items.append(d)
        self.conn.commit()
        self.patch = patch.object(s, 'load_policy', return_value=self.p)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def freeze(self):
        import final_send_plan as f
        result = f.create_plan(self.conn, self.items, self.date, 'new_outreach')
        self.conn.commit()
        return result

    def test_real_fsp_caps_five_and_preflight_checks_frozen_content(self):
        import preflight_gate as gate
        self.assertTrue(self.freeze())
        rows = self.conn.execute("SELECT * FROM final_send_plan WHERE status='planned'").fetchall()
        self.assertEqual(len(rows), 5)
        self.assertEqual(gate.check_template(self.conn, rows)['status'], 'pass')
        self.conn.execute("UPDATE final_send_plan SET body_text='tampered' WHERE id=1")
        rows = self.conn.execute("SELECT * FROM final_send_plan").fetchall()
        self.assertEqual(gate.check_template(self.conn, rows)['status'], 'fail')

    def test_fsp_refuses_old_v5_and_followup(self):
        import final_send_plan as f
        self.items[0]['template_id']='retail_distributor_v5_locked'
        with self.assertRaisesRegex(ValueError, 'V6_ONLY'):
            self.freeze()
        with self.assertRaisesRegex(ValueError, 'FOLLOW_UP_DISABLED'):
            f.create_plan(self.conn, self.items, self.date, 'follow_up')

    def test_sender_real_content_reservation_and_no_retry_after_acceptance(self):
        import bd_sender as sender
        from unittest.mock import Mock
        from contextlib import ExitStack

        self.freeze()
        frozen = dict(self.conn.execute("SELECT * FROM final_send_plan WHERE id=1").fetchone())
        item = dict(self.items[0], final_plan_entry_id=1, authorization_id='FIXTURE-AUTH', message_type='new_outreach', outreach_batch_date=self.date)
        server = Mock()
        server.sendmail.return_value = {}
        server.quit.side_effect = RuntimeError('QUIT disconnected after acceptance')
        with ExitStack() as stack:
            for name, value in [('is_configured',True),('is_suppressed',False),('_send_log_has_sent',False),
                    ('get_test_config',{'test_mode':False,'test_email':''}),('get_sender_info',{'name':'QA','email':'sender@example.invalid'}),
                    ('validate_send_authorization',{}),('_commit_send_success',(True,'')),('_save_to_sent',(True,'')),('_create_connection',server)]:
                stack.enter_context(patch.object(sender,name,return_value=value))
            stack.enter_context(patch.object(sender,'DB_PATH',str(self.db)))
            stack.enter_context(patch('recipient_scheduler.in_send_window',return_value=True))
            item['email_body'] += 'tampered'
            self.assertFalse(sender.send_one(item)['success'])
            server.sendmail.assert_not_called()
            item['email_body'] = self.items[0]['email_body']
            first = sender.send_one(item)
            self.assertTrue(first['success'], first)
            self.assertEqual(server.sendmail.call_count,1)
            second = sender.send_one(item)
            self.assertFalse(second['success'])
            self.assertEqual(server.sendmail.call_count,1)
            with closing(sqlite3.connect(self.db)) as conn:
                self.assertEqual(s.used_slots(conn,self.date),1)

    def test_registry_hash_refresh_preserves_v6_locks(self):
        import bd_template
        bd_template._compute_template_hashes()
        for key in v.TEMPLATES:
            self.assertEqual(bd_template.get_template_sha256(key), v.LOCKED_SHA256[key])


if __name__ == "__main__":
    unittest.main()
