"""test_business_rules_unified.py — P7 统一业务规则测试。

覆盖：
  1. email_hygiene.hygiene_check — 必败/必过清单
  2. mx_status.mx_status_from_dns — 全状态映射（timeout 绝不能转 nxdomain）
  3. broad_ready.is_broad_outreach_ready — blocker/non-blocker（mock 库）
  4. config.py 无硬编码明文密码

Run: C:\\Users\\15690\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe tests/test_business_rules_unified.py -v
"""
import os
import sqlite3
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
# 保证从项目根导入模块
import sys
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# 确保测试环境无生产 secret
for k in ("BD_SMTP_PASSWORD", "BD_TRACKING_PEPPER", "EMAIL_TRACKING_PEPPER",
          "DASHBOARD_API_KEY", "TRACKING_DASHBOARD_API_KEY"):
    os.environ.pop(k, None)

from email_hygiene import hygiene_check
from mx_status import (
    mx_status_from_dns, MX_PASS, IMPLICIT_MAIL_ROUTE, NULL_MX, NXDOMAIN,
    NO_MAIL_ROUTE, TIMEOUT, SERVFAIL, RETRY_PENDING, ALL_STATUSES,
)
from broad_ready import (
    is_broad_outreach_ready, BROAD_BLOCKERS, NON_BLOCKERS,
)


# ═══════════════════════════════════════════════════════════
# 1. Email Hygiene
# ═══════════════════════════════════════════════════════════
class TestHygieneCheck(unittest.TestCase):
    """hygiene_check 必败/必过清单。"""

    def test_must_fail_list(self):
        """必须 FAIL 的地址。"""
        fail_cases = {
            # 图片/资源伪邮箱
            "tbs_rev_hz_type_110x@2x.png",
            "certificate1_235x235@2x.jpg",
            # www. 前缀 local-part
            "www.kll@toystoreandgifts.com",
            # sentry / hash 系统地址
            "errors@sentry.io",
            "a3f9b2c1d4e5f6a7b8c9d0e1f2a3b4c5@x.com",
            # example/test/占位地址
            "abc@example.com",
            "info@test.com",
            "user@localhost",
            "buyer@yourdomain.com",
            # 无 @ 或格式非法
            "no-at-sign",
            "bad@@double.com",
            "missing@tld",
            # 系统邮箱前缀
            "noreply@business.com",
            "donotreply@business.com",
        }
        for email in fail_cases:
            with self.subTest(email=email):
                result = hygiene_check(email)
                self.assertFalse(result["valid"], msg=f"{email!r} 应 FAIL: {result}")
                self.assertTrue(result["reason"])

    def test_must_pass_list(self):
        """必须 PASS 的地址（泛邮箱不是 blocker）。"""
        pass_cases = {
            "901gamesmemphis@gmail.com",
            "info@business-domain.com",
            "hello@business-domain.com",
            "contact@business-domain.com",
            "sales@business-domain.com",
            "orders@business-domain.com",
        }
        for email in pass_cases:
            with self.subTest(email=email):
                result = hygiene_check(email)
                self.assertTrue(result["valid"], msg=f"{email!r} 应 PASS: {result}")
                self.assertEqual(result["reason"], "ok")

    def test_empty_and_none(self):
        """空值必须 FAIL。"""
        self.assertFalse(hygiene_check("")["valid"])
        self.assertFalse(hygiene_check(None)["valid"])


# ═══════════════════════════════════════════════════════════
# 2. MX 状态
# ═══════════════════════════════════════════════════════════
class TestMxStatusFromDns(unittest.TestCase):
    """mx_status_from_dns 全状态映射。"""

    def test_mx_pass(self):
        self.assertEqual(mx_status_from_dns(True, True, False, False, None), MX_PASS)
        self.assertEqual(mx_status_from_dns(True, False, False, False, None), MX_PASS)

    def test_implicit_mail_route(self):
        """无 MX 但有 A/AAAA → 隐式路由，不算 fail。"""
        self.assertEqual(mx_status_from_dns(False, True, False, False, None), IMPLICIT_MAIL_ROUTE)
        self.assertEqual(mx_status_from_dns(False, False, True, False, None), IMPLICIT_MAIL_ROUTE)

    def test_null_mx(self):
        self.assertEqual(mx_status_from_dns(True, True, False, True, None), NULL_MX)
        self.assertEqual(mx_status_from_dns(False, False, False, True, None), NULL_MX)

    def test_nxdomain(self):
        self.assertEqual(mx_status_from_dns(False, False, False, False, "NXDOMAIN"), NXDOMAIN)
        self.assertEqual(mx_status_from_dns(False, False, False, False, "nxdomain"), NXDOMAIN)

    def test_timeout_never_nxdomain(self):
        """timeout 绝不能转成 nxdomain，必须是重试语义。"""
        for err in ("timeout", "Timeout", "dns_timeout", "network_error", "ECONNRESET"):
            with self.subTest(err=err):
                self.assertEqual(mx_status_from_dns(False, False, False, False, err), RETRY_PENDING)
        # 未知错误名 → 同样按重试处理，而不是永久失败
        self.assertEqual(mx_status_from_dns(False, False, False, False, "weird_dns_thing"), RETRY_PENDING)

    def test_servfail(self):
        self.assertEqual(mx_status_from_dns(False, False, False, False, "SERVFAIL"), SERVFAIL)

    def test_no_mail_route(self):
        """无 MX 无 A 无 AAAA 且无错误 → no_mail_route。"""
        self.assertEqual(mx_status_from_dns(False, False, False, False, None), NO_MAIL_ROUTE)

    def test_status_enum_exhaustive(self):
        """枚举齐全性。"""
        self.assertEqual(len(ALL_STATUSES), 8)
        for s in (MX_PASS, IMPLICIT_MAIL_ROUTE, NULL_MX, NXDOMAIN,
                  NO_MAIL_ROUTE, TIMEOUT, SERVFAIL, RETRY_PENDING):
            self.assertIn(s, ALL_STATUSES)


# ═══════════════════════════════════════════════════════════
# 3. Broad Outreach Ready
# ═══════════════════════════════════════════════════════════
class TestBroadReady(unittest.TestCase):
    """is_broad_outreach_ready 的 blocker / non-blocker 判定（mock 库）。"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        c = self.conn.cursor()
        c.execute("CREATE TABLE suppression_list (id INTEGER PRIMARY KEY, email TEXT, reason TEXT, added_at TEXT)")
        c.execute("CREATE TABLE bounce_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, domain TEXT, bounce_type TEXT)")
        c.execute("CREATE TABLE reply_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, summary TEXT, suggested_action TEXT)")
        c.execute("CREATE TABLE send_log (id INTEGER PRIMARY KEY, lead_id INTEGER, email TEXT, status TEXT)")
        c.execute("CREATE TABLE leads (id INTEGER PRIMARY KEY, email TEXT, organization_key TEXT, domain_hash TEXT)")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _lead(self, email="sales@toystore.com", **overrides):
        lead = {
            "id": 1,
            "email": email,
            "store_name": "Toy Store",
            "city": "Memphis",
            "state": "TN",
            "official_website": "https://toystore.com",
            "organization_key": "org:domain:toystore.com",
            "domain_hash": "hash-a",
        }
        lead.update(overrides)
        return lead

    def test_clean_lead_is_ready(self):
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertTrue(result["ready"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["ready_reason"], "broad_outreach_ready")

    def test_invalid_email_blocker(self):
        result = is_broad_outreach_ready(
            self._lead(email="tbs_rev_hz_type_110x@2x.png"), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("image_fake_email", result["blockers"])

    def test_example_test_address_blocker(self):
        result = is_broad_outreach_ready(
            self._lead(email="abc@example.com"), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("example_test_address", result["blockers"])

    def test_suppression_blocker(self):
        self.conn.execute(
            "INSERT INTO suppression_list (email, reason) VALUES ('sales@toystore.com', 'manual')")
        self.conn.commit()
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("suppression", result["blockers"])

    def test_hard_bounce_blocker(self):
        self.conn.execute(
            "INSERT INTO bounce_log (lead_id, email, bounce_type) VALUES (1, 'sales@toystore.com', 'hard')")
        self.conn.commit()
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("hard_policy_permanent_bounce", result["blockers"])

    def test_policy_bounce_blocker(self):
        self.conn.execute(
            "INSERT INTO bounce_log (lead_id, email, bounce_type) VALUES (1, 'sales@toystore.com', 'policy')")
        self.conn.commit()
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertIn("hard_policy_permanent_bounce", result["blockers"])

    def test_negative_reply_blocker(self):
        self.conn.execute(
            "INSERT INTO reply_log (lead_id, email, summary) VALUES (1, 'sales@toystore.com', 'Please stop contacting us')")
        self.conn.commit()
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("negative_reply", result["blockers"])

    def test_previously_sent_email_blocker(self):
        self.conn.execute(
            "INSERT INTO send_log (lead_id, email, status) VALUES (1, 'sales@toystore.com', 'sent')")
        self.conn.commit()
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("previously_sent_email", result["blockers"])

    def test_previously_sent_org_blocker(self):
        self.conn.execute(
            "INSERT INTO leads (id, email, organization_key, domain_hash) VALUES (9, 'other@toystore.com', 'org:domain:toystore.com', 'hash-b')")
        self.conn.execute(
            "INSERT INTO send_log (lead_id, email, status) VALUES (9, 'other@toystore.com', 'sent')")
        self.conn.commit()
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("previously_sent_org", result["blockers"])

    def test_shared_domain_history_blocker(self):
        """同 domain_hash 的组织已有发送历史 → shared_domain_org_history。"""
        self.conn.execute(
            "INSERT INTO leads (id, email, organization_key, domain_hash) VALUES (9, 'other@toystore.com', 'org:other', 'hash-a')")
        self.conn.execute(
            "INSERT INTO send_log (lead_id, email, status) VALUES (9, 'other@toystore.com', 'sent')")
        self.conn.commit()
        result = is_broad_outreach_ready(self._lead(), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("shared_domain_org_history", result["blockers"])

    def test_third_party_mismatch_blocker(self):
        """store 是 Quarterstaff Games 但邮箱是 diane@sevendaysvt.com → 由 business association 阻断。"""
        lead = self._lead(email="diane@sevendaysvt.com", store_name="Quarterstaff Games",
                          organization_key="org:quarterstaff", domain_hash="hash-c")
        result = is_broad_outreach_ready(lead, {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("third_party_mismatch", result["blockers"])

    def test_contact_form_only_blocker(self):
        result = is_broad_outreach_ready(
            self._lead(email="", status="contact_form_pool"), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("contact_form_only", result["blockers"])

    def test_unsubscribed_blocker(self):
        result = is_broad_outreach_ready(
            self._lead(unsubscribed_at="2026-08-01T00:00:00"), {"conn": self.conn})
        self.assertFalse(result["ready"])
        self.assertIn("unsubscribed", result["blockers"])

    def test_non_blockers_are_not_blockers(self):
        """NON_BLOCKERS 中的信号不能导致 ready=False。"""
        lead = self._lead()
        # 无 named buyer / CONTACT_ROLE_UNCERTAIN / Gmail / 泛邮箱 / 无 strict A0 证据 / retail-custom 混合
        variants = [
            {},
            {"email_source_type": "public_directory", "contact_role": "CONTACT_ROLE_UNCERTAIN"},
            {"email": "901gamesmemphis@gmail.com"},
            {"email": "info@business-domain.com"},
            {"email": "orders@business-domain.com"},
            {"evidence_snippet": ""},
            {"store_type": "retail/custom mixed"},
        ]
        for overrides in variants:
            with self.subTest(overrides=overrides):
                result = is_broad_outreach_ready(self._lead(**overrides), {"conn": self.conn})
                self.assertTrue(result["ready"], msg=f"{overrides} 不应被阻断: {result}")

    def test_ctx_injection_avoids_db(self):
        """注入集合（不传 conn）也应生效。"""
        lead = self._lead()
        result = is_broad_outreach_ready(lead, {
            "suppressed_emails": {"sales@toystore.com"},
        })
        self.assertFalse(result["ready"])
        self.assertIn("suppression", result["blockers"])

    def test_blocker_and_nonblocker_sets(self):
        """BROAD_BLOCKERS / NON_BLOCKERS 集合定义。"""
        self.assertIn("previously_sent_email", BROAD_BLOCKERS)
        self.assertIn("hard_policy_permanent_bounce", BROAD_BLOCKERS)
        self.assertIn("third_party_mismatch", BROAD_BLOCKERS)
        self.assertIn("contact_form_only", BROAD_BLOCKERS)
        self.assertIn("gmail", NON_BLOCKERS)
        self.assertIn("generic_contact_mailbox", NON_BLOCKERS)
        self.assertIn("contact_role_uncertain", NON_BLOCKERS)
        # 集合互斥
        self.assertTrue(BROAD_BLOCKERS.isdisjoint(NON_BLOCKERS))


# ═══════════════════════════════════════════════════════════
# 4. config.py 无硬编码明文密码
# ═══════════════════════════════════════════════════════════
class TestConfigNoHardcodedSecret(unittest.TestCase):
    def test_no_plaintext_smtp_password_in_source(self):
        src = (PROJECT_DIR / "config.py").read_text(encoding="utf-8")
        self.assertNotIn("zqlgeodqmifdchhj", src)

    def test_config_imports_without_env(self):
        """未设置 BD_SMTP_PASSWORD 时 import config 不抛错。"""
        import config
        self.assertEqual(config.SMTP_PASSWORD, "")
        # fail-closed：get_smtp_password 在密码缺失时必须抛错
        with self.assertRaises(RuntimeError):
            config.get_smtp_password()


if __name__ == "__main__":
    unittest.main(verbosity=2)
