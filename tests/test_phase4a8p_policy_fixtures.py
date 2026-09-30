"""Offline policy-review fixtures; these do not authorize a Facebook source."""
import unittest


def evaluate_policy(item, policy, max_age_days=30):
    """A/B comparison model, deliberately separate from production V1/V2."""
    if policy not in {"A", "B"}:
        return False  # No independently verified enterprise-domain mechanism for C.
    required = ("official_website", "official_link_source_url", "facebook_page_url",
                "facebook_page_fetched_at", "visible_email", "visible_email_excerpt")
    if any(not item.get(key) for key in required):
        return False
    if not all(item.get(key) for key in ("verified_official_page", "official_site_direct_link",
                                              "business_page", "browser_public", "email_literal_visible",
                                              "same_merchant", "official_link_still_present")):
        return False
    if item.get("discovery_method") != "official_site_direct_link":
        return False
    if item.get("independent_identity_signal_count", 0) < 1:
        return False
    if item.get("age_days", 999) > max_age_days:
        return False
    if item.get("email_kind") == "same_domain":
        return True
    return policy == "B" and item.get("email_kind") == "free"


class Phase4A8PPolicyFixtures(unittest.TestCase):
    def setUp(self):
        self.good = dict(official_website="https://merchant.example",
                         official_link_source_url="https://merchant.example/contact",
                         facebook_page_url="https://facebook.com/merchant",
                         facebook_page_fetched_at="2026-09-30T00:00:00Z",
                         visible_email="sales@merchant.example",
                         visible_email_excerpt="Email sales@merchant.example",
                         verified_official_page=True, official_site_direct_link=True,
                         business_page=True, browser_public=True, email_literal_visible=True,
                         same_merchant=True, official_link_still_present=True,
                         discovery_method="official_site_direct_link",
                         independent_identity_signal_count=1, age_days=1,
                         email_kind="same_domain")

    def test_same_domain_qualifies_only_in_review_model(self):
        self.assertTrue(evaluate_policy(self.good, "A"))
        self.assertTrue(evaluate_policy(self.good, "B"))

    def test_free_mail_differs_by_policy(self):
        item = dict(self.good, email_kind="free")
        self.assertFalse(evaluate_policy(item, "A"))
        self.assertTrue(evaluate_policy(item, "B"))

    def test_cross_domain_never_qualifies_without_independent_domain_mechanism(self):
        item = dict(self.good, email_kind="cross_domain")
        for policy in ("A", "B", "C"):
            self.assertFalse(evaluate_policy(item, policy))

    def test_explicit_unapproved_sources_fail(self):
        for method in ("facebook_social", "social_only", "search_snippet",
                       "third_party_directory", "facebook_search"):
            with self.subTest(method=method):
                self.assertFalse(evaluate_policy(dict(self.good, discovery_method=method), "B"))

    def test_missing_contract_field_fails(self):
        for key in ("official_website", "official_link_source_url", "facebook_page_url",
                    "facebook_page_fetched_at", "visible_email", "visible_email_excerpt"):
            with self.subTest(field=key):
                self.assertFalse(evaluate_policy(dict(self.good, **{key: ""}), "B"))

    def test_weak_identity_personal_page_or_hidden_email_fails(self):
        for key, value in (("independent_identity_signal_count", 0), ("business_page", False),
                           ("email_literal_visible", False), ("same_merchant", False),
                           ("browser_public", False), ("verified_official_page", False)):
            with self.subTest(key=key):
                self.assertFalse(evaluate_policy(dict(self.good, **{key: value}), "B"))

    def test_changed_or_expired_evidence_fails(self):
        for key, value in (("official_link_still_present", False), ("age_days", 31),
                           ("official_site_direct_link", False)):
            with self.subTest(key=key):
                self.assertFalse(evaluate_policy(dict(self.good, **{key: value}), "B"))
        self.assertTrue(evaluate_policy(dict(self.good, age_days=30), "B"))

    def test_thirty_sixty_ninety_day_comparison(self):
        self.assertFalse(evaluate_policy(dict(self.good, age_days=31), "B", 30))
        self.assertTrue(evaluate_policy(dict(self.good, age_days=31), "B", 60))
        self.assertFalse(evaluate_policy(dict(self.good, age_days=61), "B", 60))
        self.assertTrue(evaluate_policy(dict(self.good, age_days=61), "B", 90))


if __name__ == "__main__":
    unittest.main()
