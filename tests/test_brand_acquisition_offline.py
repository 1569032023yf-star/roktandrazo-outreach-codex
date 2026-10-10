from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from brand_acquisition.capture_import import import_manifest
from brand_acquisition.capture_manifest import validate_manifest, write_capture, write_manifest
from brand_acquisition.email_quality import audit_brand_email
from brand_acquisition.models import BrandCandidate
from brand_acquisition.official_site_resolver import resolve_official_site_candidates
from brand_acquisition.pipeline import AcquisitionPipeline, funnel
from brand_acquisition.providers import PageResult, run_public_source
from scripts.run_brand_capture import main

LOCAL_TEMP = Path(__file__).resolve().parents[1] / "output" / "brand_acquisition_test_tmp"
LOCAL_TEMP.mkdir(parents=True, exist_ok=True)


class BrandAcquisitionOfflineTests(unittest.TestCase):
    def test_explicit_website_is_candidate_but_marketplace_and_guesses_are_not(self):
        c = BrandCandidate("Bright Cards", official_website="https://brightcards.example")
        r = resolve_official_site_candidates(c, [])
        self.assertEqual(r["candidate_websites"][0]["website"], "https://brightcards.example/")
        c.official_website = ""
        r = resolve_official_site_candidates(c, [{"brand_name": "Bright Cards"}])
        self.assertEqual(r["candidate_websites"], [])
        c.official_website = "https://amazon.com/brightcards"
        self.assertEqual(resolve_official_site_candidates(c, [])["candidate_websites"], [])

    def test_unverified_merchant_never_becomes_safe_identity(self):
        c = BrandCandidate("Unknown Shop", official_website="https://unknown.example",
            source_urls=["https://market.example/listing"], brand_claim="Unknown Shop",
            product_evidence=[{"source_url": "https://market.example/listing"}])
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            payload = AcquisitionPipeline(tmp, history_check=lambda _: "UNKNOWN",
                brand_owner_check=lambda _: False).enrich([c])
        got = payload["candidates"][0]
        self.assertEqual(got["identity_class"], "IDENTITY_UNVERIFIED")
        self.assertFalse(got["official_site_verified"])
        self.assertEqual(payload["metrics"]["BRAND_OWNERS_CONFIRMED"], 0)

    def test_imported_candidate_cannot_gain_contact_qualification_without_live_revalidation(self):
        candidate = BrandCandidate("Imported Brand", official_website="https://brand.example",
            official_site_verified=True, brand_identity_status="brand_owner_confirmed",
            business_email="sales@brand.example", email_official_identity_verified=True,
            data_origin="public_import", data_origin_label="AUTHORIZED_PUBLIC_IMPORT")
        callback_called = []
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            payload = AcquisitionPipeline(tmp, history_check=lambda _: callback_called.append("history") or "new_candidate",
                official_site_check=lambda _: callback_called.append("site") or True,
                first_party_extract=lambda _: callback_called.append("email") or {}).enrich([candidate])
        result = payload["candidates"][0]
        self.assertEqual(result["enrichment_status"], "live_revalidation_required")
        self.assertEqual(result["business_email"], "")
        self.assertFalse(result["official_site_verified"])
        self.assertEqual(callback_called, [])
        self.assertEqual(payload["metrics"]["FIRST_PARTY_EMAILS_FOUND"], 0)

    def test_candidate_owner_and_existing_confirmed_resume_paths(self):
        candidate = BrandCandidate("Owner", official_website="https://owner.example",
            brand_claim="Owner", product_evidence=[{"source_url":"https://market.example/item"}],
            source_urls=["https://market.example/item"])
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            payload = AcquisitionPipeline(tmp, history_check=lambda _: "new_candidate",
                brand_owner_check=lambda _: True, official_site_check=lambda _: True).enrich([candidate])
        self.assertEqual(payload["candidates"][0]["identity_class"], "BRAND_OWNER")
        self.assertTrue(payload["candidates"][0]["official_site_verified"])
        existing = BrandCandidate("Known", official_website="https://known.example",
                                  brand_identity_status="brand_owner_confirmed")
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            payload = AcquisitionPipeline(tmp, history_check=lambda _: "UNKNOWN",
                official_site_check=lambda _: True).enrich([existing])
        self.assertTrue(payload["candidates"][0]["official_site_verified"])

    def test_parser_explicit_official_link_flows_through_site_verification(self):
        page = '<html><body><h1>Bright Brand</h1><a href="https://brightbrand.example/">Official Website</a></body></html>'
        class Fetcher:
            def fetch(self, url): return PageResult(url, "ok", page, final_url=url, fetch_method="fixture")
        run = run_public_source("tiktok_shop", ["https://shop.tiktok.com/store/bright"], Fetcher())
        candidate = run.candidates[0]
        # Use a deterministic mock verifier below to exercise the pipeline path;
        # keep fixture provenance untrusted and do not count it as live output.
        candidate.data_origin = "unclassified"
        candidate.data_origin_label = "UNCLASSIFIED"
        seen = []
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            payload = AcquisitionPipeline(tmp, history_check=lambda _: "new_candidate",
                brand_owner_check=lambda c: seen.append(c.official_website) or c.official_website == "https://brightbrand.example/",
                official_site_check=lambda _: True).enrich([candidate])
        self.assertEqual(seen, ["https://brightbrand.example/"])
        self.assertTrue(payload["candidates"][0]["official_site_verified"])

    def test_email_placeholder_and_cross_domain_gate(self):
        self.assertFalse(audit_brand_email("info@mysite.com", "https://brand.example")["valid"])
        self.assertFalse(audit_brand_email("sales@other.example", "https://brand.example")["valid"])
        evidence = {"email_domain_affiliation": {"domain":"other.example", "excerpt":"sales@other.example",
            "evidence_url":"https://brand.example/about", "independently_verified":True}}
        self.assertTrue(audit_brand_email("sales@other.example", "https://brand.example", evidence)["valid"])
        self.assertTrue(audit_brand_email("sales@brand.example", "https://brand.example")["valid"])

    def test_pipeline_quarantines_placeholder_and_does_not_count_it_as_found(self):
        candidate = BrandCandidate("Template Site", official_website="https://brand.example",
            brand_identity_status="brand_owner_confirmed", brand_claim="Template Site",
            data_origin_label="LIVE_PUBLIC_CAPTURE")
        email = {"email":"info@mysite.com", "role":"GENERAL", "url":"https://brand.example/contact",
            "excerpt":"Contact info@mysite.com", "official_identity_verified":True,
            "http_status":200, "final_url":"https://brand.example/contact"}
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            payload = AcquisitionPipeline(tmp, history_check=lambda _: "new_candidate",
                official_site_check=lambda _: True, first_party_extract=lambda _: email,
                mx_check=lambda _: self.fail("placeholder email must not reach MX")).enrich([candidate])
        result = payload["candidates"][0]
        self.assertEqual(result["business_email"], "")
        self.assertEqual(result["rejected_business_email"], "info@mysite.com")
        self.assertEqual(result["email_quality_status"], "rejected")
        self.assertEqual(payload["metrics"]["FIRST_PARTY_EMAILS_FOUND"], 0)
        self.assertEqual(payload["metrics"]["LIVE_VERIFIED_OFFICIAL_EMAILS"], 0)

    def test_import_manifest_integrity_and_live_claim_is_downgraded(self):
        html = '<html><body><h1>Paper Brand</h1></body></html>'
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            row = write_capture(tmp, source_platform="tiktok_shop", requested_url="https://shop.tiktok.com/search?q=cards",
                final_url="https://shop.tiktok.com/search?q=cards", captured_at="2026-10-10T00:00:00+00:00",
                capture_method="public_https", http_status=200, content_type="text/html", html=html,
                page_category="greeting_cards", data_origin="LIVE_PUBLIC_CAPTURE")
            manifest_path = write_manifest(tmp, [row])
            manifest, runs = import_manifest(manifest_path)
            self.assertEqual(manifest["pages_validated"], 1)
            self.assertFalse(manifest["source_authenticity_verified"])
            self.assertEqual(runs[0].candidates[0].data_origin, "public_import")
            self.assertEqual(runs[0].candidates[0].data_origin_label, "AUTHORIZED_PUBLIC_IMPORT")
            self.assertEqual(hashlib.sha256((Path(tmp) / row.content_file).read_bytes()).hexdigest(), row.content_sha256)
            (Path(tmp) / row.content_file).write_text("altered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                validate_manifest(manifest_path)

    def test_manifest_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory(dir=LOCAL_TEMP) as tmp:
            root = Path(tmp)
            outside = root / "outside.html"
            outside.write_text("<html></html>", encoding="utf-8")
            payload = {"schema_version":"1.0", "scope":"discovery_only", "pages":[{
                "capture_id":"a"*32, "source_platform":"amazon", "requested_url":"https://amazon.com/x",
                "final_url":"https://amazon.com/x", "captured_at":"2026-10-10T00:00:00Z",
                "capture_method":"import", "http_status":200, "content_type":"text/html",
                "content_sha256":hashlib.sha256(b"<html></html>").hexdigest(), "content_file":"../outside.html",
                "page_category":"paper", "data_origin":"AUTHORIZED_PUBLIC_IMPORT"}]}
            path = root / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError): validate_manifest(path)

    def test_network_disabled_capture_command_fails_before_requests(self):
        with patch.dict(os.environ, {"CODEX_SANDBOX_NETWORK_DISABLED":"1"}):
            self.assertEqual(main(["--mode", "capture-public"]), 2)

    def test_offline_page_result_source_provenance_is_not_live(self):
        class Fixture:
            def fetch(self, url):
                return PageResult(url, "ok", '<html><body><h1>Fixture Cards</h1></body></html>',
                                  fetch_method="fixture")
        run = run_public_source("tiktok_shop", ["https://shop.tiktok.com/search?q=cards"], Fixture())
        self.assertTrue(all(x.data_origin_label == "TEST_FIXTURE" for x in run.candidates))
        self.assertTrue(all(x.identity_class == "MARKETPLACE_SELLER" for x in run.candidates))


if __name__ == "__main__":
    unittest.main()
