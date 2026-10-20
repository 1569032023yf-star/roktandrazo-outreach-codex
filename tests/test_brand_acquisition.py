from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brand_acquisition.history import HistoryChecker
from brand_acquisition.models import BrandCandidate, SourceMetric
from brand_acquisition.pipeline import AcquisitionPipeline, PipelineConfig, deduplicate, funnel
from brand_acquisition.providers import (
    PageResult, parse_amazon, parse_tiktok_shop, parse_wholesale, run_public_source,
)


# Reduced fixtures based on public rendered structures observed in research:
# TikTok's indexed snapshot is stale, Faire's category snapshot was crawled today,
# and Amazon is an archived item-page exhibit (live Amazon access returned 503).
# These are not raw HTML captures. No email data is included.
TIKTOK_PAGE = '''<html><body><h1>Sleazy Greetings</h1><span>32.5K+ Follower</span>
<span>201.9K Sold</span><span>888 Videos</span>
<a href="/product/123">Funny Birthday Greeting Card</a><span>20.5K sold</span></body></html>'''
AMAZON_PAGE = '''Good Luck Note Cards - 12 Cards and Envelopes - Good Luck Greeting Cards
Brand: Little Notes by Comptime
17 ratings
Amazon's Choice in Greeting Cards
Ships from Amazon
Sold by Comptime Digital Prin...'''
FAIRE_PAGE = '''<html><body><a href="/brand/quilling-card">Quilling Card</a><span>5.0 (556) $150 min</span>
<a href="/brand/hester-cook">Hester &amp; Cook - Stationery</a><span>5.0 (90) $200 min</span>
<a href="/brand/other-paper-co">Other Paper Co</a></body></html>'''
LOCAL_TEMP = Path(__file__).resolve().parents[1] / "output" / "brand_acquisition_test_tmp"


def temp_dir():
    LOCAL_TEMP.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=LOCAL_TEMP)


class StaticFetcher:
    def __init__(self, result): self.result = result
    def fetch(self, url): return PageResult(url, **self.result)


class BrandAcquisitionTests(unittest.TestCase):
    def test_three_public_source_page_structures_yield_unconfirmed_candidates(self):
        tiktok = parse_tiktok_shop(TIKTOK_PAGE, "https://shop.tiktok.com/us/store/seller-outlet/123")
        amazon = parse_amazon(AMAZON_PAGE, "https://www.amazon.com/dp/example")
        wholesale = parse_wholesale(FAIRE_PAGE, "https://www.faire.com/suppliers/brands")
        self.assertEqual(tiktok[0].brand_name, "Sleazy Greetings")
        self.assertEqual(tiktok[0].public_sales_signals["sold"], "201.9K")
        self.assertEqual(amazon[0].brand_name, "Little Notes by Comptime")
        self.assertEqual(amazon[0].public_sales_signals["marketplace_seller"], "Comptime Digital Prin...")
        self.assertTrue(any(x.brand_name == "Quilling Card" for x in wholesale))
        self.assertTrue(any(x.brand_name == "Hester & Cook - Stationery" for x in wholesale))
        self.assertTrue(all(x.brand_identity_status == "unknown" for x in tiktok + amazon + wholesale))

    def test_brand_owner_and_reseller_are_not_conflated(self):
        item = parse_tiktok_shop(TIKTOK_PAGE, "https://shop.tiktok.com/us/store/seller-outlet/123")[0]
        self.assertEqual(item.identity_class, "MARKETPLACE_SELLER")
        self.assertEqual(item.brand_owner_name, "")
        self.assertEqual(item.brand_identity_status, "unknown")

    def test_cross_source_dedup_keeps_source_evidence(self):
        a = BrandCandidate("PaperWorks", official_website="https://paperworks.example", official_site_verified=True, source_platforms=["amazon"], source_urls=["https://a.example/p"])
        b = BrandCandidate("paper works", official_website="https://paperworks.example", official_site_verified=True, source_platforms=["wholesale"], source_urls=["https://f.example/b"])
        result = deduplicate([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0].source_platforms), {"amazon", "wholesale"})
        self.assertEqual(len(result[0].source_urls), 2)

    def test_owner_site_first_party_evidence_history_and_mx_fail_closed(self):
        item = BrandCandidate("PaperWorks", source_platforms=["wholesale"], official_website="https://paperworks.example",
                              brand_identity_status="brand_owner_confirmed")
        with temp_dir() as tmp:
            pipe = AcquisitionPipeline(tmp, history_check=lambda _x: "new_candidate",
                official_site_check=lambda _x: True,
                first_party_extract=lambda _x: {"email":"sales@paperworks.example", "role":"sales",
                    "url":"https://paperworks.example/wholesale", "excerpt":"Contact sales@paperworks.example", "checked_at":"2026-10-08T00:00:00Z",
                    "official_identity_verified":True, "http_status":200, "final_url":"https://paperworks.example/wholesale"},
                mx_check=lambda _x: "nxdomain")
            payload = pipe.enrich([item])
            got = payload["candidates"][0]
            self.assertEqual(got["brand_identity_status"], "brand_owner_confirmed")
            self.assertEqual(got["email_evidence_url"], "https://paperworks.example/wholesale")
            self.assertEqual(got["mx_status"], "nxdomain")
            self.assertEqual(payload["metrics"]["HISTORY_CLEAN_BRANDS_WITH_EMAIL"], 0)

    def test_history_unavailable_is_unknown_never_clean(self):
        item = BrandCandidate("CardCo", official_website="https://cardco.example", brand_identity_status="brand_owner_confirmed")
        with temp_dir() as tmp:
            payload = AcquisitionPipeline(tmp, official_site_check=lambda _: True,
                first_party_extract=lambda _: {"email":"sales@cardco.example", "url":"https://cardco.example/contact",
                    "excerpt":"sales@cardco.example", "role":"sales"}, mx_check=lambda _: "ok").enrich([item])
        self.assertEqual(payload["candidates"][0]["history_status"], "UNKNOWN")
        self.assertEqual(payload["metrics"]["HISTORY_CLEAN_BRANDS_WITH_EMAIL"], 0)

    def test_restricted_source_fails_without_retry_or_other_source_effect(self):
        fetcher = StaticFetcher({"status":"access_restricted", "error":"challenge_or_login"})
        run = run_public_source("amazon", ["https://www.amazon.com/s?k=cards", "https://www.amazon.com/s?k=paper"], fetcher)
        self.assertEqual(run.pages_attempted, 1)
        self.assertEqual(run.failures, 1)
        self.assertEqual(run.candidates, [])

    def test_resume_does_not_repeat_completed_organization(self):
        with temp_dir() as tmp:
            item = BrandCandidate("CardCo", source_platforms=["wholesale"], official_website="https://cardco.example",
                                  brand_identity_status="brand_owner_confirmed")
            calls = []
            site_check = lambda _: calls.append("site") or True
            history_check = lambda _: "new_candidate"
            first = AcquisitionPipeline(tmp, history_check=history_check, official_site_check=site_check).enrich([item])
            checkpoint_before = json.loads((Path(tmp) / "checkpoint.json").read_text())
            second = AcquisitionPipeline(tmp, history_check=history_check, official_site_check=site_check).enrich([item])
            checkpoint_after = json.loads((Path(tmp) / "checkpoint.json").read_text())
            self.assertEqual(first["candidates"][0]["brand_identity_status"], "brand_owner_confirmed")
            self.assertEqual(first["candidates"][0]["enrichment_status"], "complete")
            self.assertEqual(second["candidates"][0]["enrichment_status"], "complete")
            self.assertEqual(calls, ["site"])
            self.assertEqual(checkpoint_before["candidates"][0]["enrichment_status"], "complete")
            self.assertEqual(checkpoint_after["candidates"][0]["enrichment_status"], "complete")

    def test_funnel_metrics_are_unique_candidate_based_and_source_scoped(self):
        candidates = [BrandCandidate("CardCo", brand_identity_status="brand_owner_confirmed", business_email="sales@cardco.example",
            official_site_verified=True, email_official_identity_verified=True, email_evidence_url="https://cardco.example/contact",
            email_evidence_excerpt="Contact sales@cardco.example", email_hygiene_status="ok", mx_status="ok",
            history_status="new_candidate", source_platforms=["tiktok_shop", "wholesale"])]
        metrics = funnel(candidates, [SourceMetric("tiktok_shop", brands_discovered=2), SourceMetric("wholesale", brands_discovered=1)], 1.2)
        self.assertEqual(metrics["RAW_BRANDS_DISCOVERED"], 3)
        self.assertEqual(metrics["DEDUPED_UNIQUE_BRANDS"], 1)
        self.assertEqual(metrics["TIKTOK_VERIFIED_EMAIL_BRANDS"], 1)
        self.assertEqual(metrics["WHOLESALE_VERIFIED_EMAIL_BRANDS"], 1)

    def test_no_history_path_is_unknown_and_non_development_path_rejected(self):
        self.assertEqual(HistoryChecker()(None), "UNKNOWN")
        with self.assertRaises(ValueError):
            HistoryChecker("missing.db", development_copy=False)

    def test_existing_contact_history_blocks_new_pool_count(self):
        item = BrandCandidate("CardCo", source_platforms=["wholesale"], official_website="https://cardco.example",
            brand_identity_status="brand_owner_confirmed")
        with temp_dir() as tmp:
            calls = []
            payload = AcquisitionPipeline(tmp, history_check=lambda _: "previously_sent",
                official_site_check=lambda _: calls.append("official-site") or True,
                first_party_extract=lambda _: {"email":"sales@cardco.example", "url":"https://cardco.example/wholesale",
                    "excerpt":"sales@cardco.example", "role":"sales"}, mx_check=lambda _: "ok").enrich([item])
        self.assertEqual(payload["candidates"][0]["history_status"], "previously_sent")
        self.assertEqual(calls, [])
        self.assertEqual(payload["metrics"]["NEW_UNIQUE_BRAND_OWNERS"], 0)
        self.assertEqual(payload["metrics"]["HISTORY_CLEAN_BRANDS_WITH_EMAIL"], 0)

    def test_first_party_adapter_reuses_discovery_identity_and_email_extractor(self):
        from brand_acquisition.pipeline import make_first_party_enricher
        class OfficialPageFetcher:
            def fetch(self, url):
                return {"text":"PaperWorks official site wholesale sales@paperworks.example",
                    "html":"<html><body>PaperWorks official site wholesale sales@paperworks.example</body></html>",
                    "status":200, "final_url":url, "tls_verified":True}
        verify, extract = make_first_party_enricher(OfficialPageFetcher())
        item = BrandCandidate("PaperWorks", official_website="https://paperworks.example",
                              brand_identity_status="brand_owner_confirmed")
        self.assertTrue(verify(item))
        evidence = extract(item)
        self.assertEqual(evidence["email"], "sales@paperworks.example")
        self.assertIn("sales@paperworks.example", evidence["excerpt"])

    def test_source_checkpoint_resume_and_independent_sources(self):
        class CountingFetcher:
            def __init__(self, html): self.calls = 0; self.html = html
            def fetch(self, url):
                self.calls += 1
                return PageResult(url, "ok", self.html)
        with temp_dir() as tmp:
            fetchers = {}
            def factory(source):
                return fetchers.setdefault(source, CountingFetcher(TIKTOK_PAGE if source == "tiktok_shop" else FAIRE_PAGE))
            pipe = AcquisitionPipeline(tmp)
            first = pipe.run_sources({"tiktok_shop":["https://public.example/shop"], "wholesale":["https://public.example/brands"]}, factory)
            second = pipe.run_sources({"tiktok_shop":["https://public.example/shop"], "wholesale":["https://public.example/brands"]}, factory)
        self.assertEqual(fetchers["tiktok_shop"].calls, 1)
        self.assertEqual(fetchers["wholesale"].calls, 1)
        self.assertEqual(first["metrics"]["RAW_BRANDS_DISCOVERED"], 4)
        self.assertEqual(second["metrics"]["RAW_BRANDS_DISCOVERED"], 4)

    def test_network_failure_is_retryable_then_recovers_after_backoff(self):
        class RecoveringFetcher:
            def __init__(self): self.calls = 0
            def fetch(self, url):
                self.calls += 1
                if self.calls == 1: return PageResult(url, "transient_failure", error="DNS")
                return PageResult(url, "ok", TIKTOK_PAGE, final_url=url, fetched_at="2026-10-08T12:02:00Z")
        with temp_dir() as tmp:
            fetcher = RecoveringFetcher()
            pipe = AcquisitionPipeline(tmp)
            url = "https://shop.example/category"
            pipe.run_sources({"tiktok_shop":[url]}, lambda _:fetcher, now="2026-10-08T12:00:00+00:00")
            checkpoint = Path(tmp) / "source_checkpoints" / "source_tiktok_shop.json"
            first = json.loads(checkpoint.read_text())
            self.assertNotIn(url, first["completed_urls"])
            self.assertIn(url, first["retryable_urls"])
            recovered = pipe.run_sources({"tiktok_shop":[url]}, lambda _:fetcher, now="2026-10-08T12:02:00+00:00")
            second = json.loads(checkpoint.read_text())
            self.assertEqual(fetcher.calls, 2)
            self.assertIn(url, second["completed_urls"])
            self.assertEqual(second["url_states"][url]["status"], "SUCCESS")
            self.assertGreater(recovered["metrics"]["RAW_BRANDS_DISCOVERED"], 0)

    def test_same_name_different_verified_domains_are_preserved_as_conflict(self):
        a = BrandCandidate("Bright Paper", official_website="https://brightpaper-one.example", official_site_verified=True)
        b = BrandCandidate("Bright Paper", official_website="https://brightpaper-two.example", official_site_verified=True)
        result = deduplicate([a, b])
        self.assertEqual(len(result), 2)
        self.assertTrue(all(x.brand_identity_status == "identity_conflict" for x in result))

    def test_failed_identity_site_check_does_not_overwrite_owner_identity(self):
        item = BrandCandidate("Confirmed Brand", official_website="https://brand.example", brand_identity_status="brand_owner_confirmed")
        with temp_dir() as tmp:
            result = AcquisitionPipeline(tmp, history_check=lambda _:"new_candidate", official_site_check=lambda _:False).enrich([item])
        got = result["candidates"][0]
        self.assertEqual(got["brand_identity_status"], "brand_owner_confirmed")
        self.assertEqual(got["official_site_verification_status"], "failed_or_unavailable")

    def test_public_url_guard_rejects_private_and_non_https_official_targets(self):
        from brand_acquisition.providers import validate_public_url
        self.assertFalse(validate_public_url("http://127.0.0.1/", resolver=lambda *a, **k:[])[0])
        self.assertFalse(validate_public_url("http://public.example/", require_https=True, resolver=lambda *a, **k:[(None,None,None,None,("8.8.8.8",443))])[0])

    def test_runtime_callbacks_are_wired_and_first_party_only(self):
        from brand_acquisition.pipeline import make_runtime_callbacks
        callbacks = make_runtime_callbacks()
        self.assertEqual(set(callbacks), {"brand_owner_check", "official_site_check", "first_party_extract", "mx_check"})
        self.assertTrue(all(callable(x) for x in callbacks.values()))

    def test_owner_callback_requires_verified_first_party_site_and_listing(self):
        from brand_acquisition.pipeline import make_runtime_callbacks
        class Site:
            def fetch(self, url):
                return {"text":"PaperWorks official products", "html":"<html><body>PaperWorks official products wholesale sales@paperworks.example</body></html>",
                        "status":200,"final_url":url,"tls_verified":True}
        callbacks = make_runtime_callbacks(Site())
        candidate = BrandCandidate("PaperWorks", official_website="https://paperworks.example",
            discovery_source_url="https://faire.example/brand/paperworks", brand_claim="PaperWorks",
            product_or_listing_evidence=[{"product_title":"PaperWorks cards"}])
        self.assertTrue(callbacks["brand_owner_check"](candidate))
        self.assertEqual(candidate.identity_class, "BRAND_OWNER")
        unsubstantiated = BrandCandidate("PaperWorks", official_website="https://paperworks.example")
        self.assertFalse(callbacks["brand_owner_check"](unsubstantiated))

    def test_first_party_extractor_rejects_guessed_or_missing_evidence(self):
        item = BrandCandidate("PaperWorks", official_website="https://paperworks.example", brand_identity_status="brand_owner_confirmed")
        with temp_dir() as tmp:
            result = AcquisitionPipeline(tmp, history_check=lambda _:"new_candidate", official_site_check=lambda _:True,
                first_party_extract=lambda _: {"email":"sales@paperworks.example", "role":"sales"},
                mx_check=lambda _:"ok").enrich([item])
        candidate = result["candidates"][0]
        self.assertEqual(candidate["business_email"], "")
        self.assertEqual(candidate["email_hygiene_status"], "evidence_incomplete")
        self.assertEqual(candidate["mx_status"], "not_checked_evidence_incomplete")

    def test_directory_email_is_not_first_party_when_domain_differs(self):
        from brand_acquisition.pipeline import make_first_party_enricher
        class DirectoryLike:
            def fetch(self, url):
                return {"text":"Directory listing PaperWorks sales@directory.example", "html":"<html>PaperWorks sales@directory.example</html>",
                        "status":200,"final_url":"https://directory.example/listing","tls_verified":True}
        verify, extract = make_first_party_enricher(DirectoryLike())
        item = BrandCandidate("PaperWorks", official_website="https://paperworks.example", brand_identity_status="brand_owner_confirmed")
        self.assertFalse(verify(item))
        self.assertEqual(extract(item), {})

    def test_rate_limit_retries_later_but_pauses_source_this_run(self):
        class RateLimited:
            def __init__(self): self.calls=[]
            def fetch(self, url):
                self.calls.append(url)
                return PageResult(url, "rate_limited", error="http_429")
        with temp_dir() as tmp:
            fetcher = RateLimited()
            pipe = AcquisitionPipeline(tmp)
            urls = ["https://shop.example/one", "https://shop.example/two"]
            pipe.run_sources({"tiktok_shop":urls}, lambda _:fetcher, now="2026-10-08T12:00:00+00:00")
            cp = json.loads((Path(tmp)/"source_checkpoints"/"source_tiktok_shop.json").read_text())
        self.assertEqual(fetcher.calls, urls[:1])
        self.assertNotIn(urls[0], cp["completed_urls"])
        self.assertEqual(cp["url_states"][urls[0]]["status"], "TRANSIENT_FAILURE")
        self.assertTrue(cp["url_states"][urls[0]]["rate_limited"])

    def test_captcha_and_parse_empty_are_terminal_and_distinct(self):
        with temp_dir() as tmp:
            pipe = AcquisitionPipeline(tmp)
            restricted = StaticFetcher({"status":"access_restricted", "error":"challenge_or_login"})
            url = "https://amazon.example/category"
            pipe.run_sources({"amazon":[url]}, lambda _:restricted, now="2026-10-08T12:00:00+00:00")
            cp = json.loads((Path(tmp)/"source_checkpoints"/"source_amazon.json").read_text())
            self.assertIn(url, cp["access_restricted_urls"])
            self.assertNotIn(url, cp["completed_urls"])
        with temp_dir() as tmp:
            pipe = AcquisitionPipeline(tmp)
            empty = StaticFetcher({"status":"ok", "html":"<html><body>No product listings</body></html>"})
            pipe.run_sources({"amazon":[url]}, lambda _:empty, now="2026-10-08T12:00:00+00:00")
            cp = json.loads((Path(tmp)/"source_checkpoints"/"source_amazon.json").read_text())
            self.assertEqual(cp["url_states"][url]["status"], "PARSE_EMPTY")
            self.assertIn(url, cp["completed_urls"])

    def test_corrupt_source_checkpoint_is_not_silently_overwritten(self):
        with temp_dir() as tmp:
            path = Path(tmp)/"source_checkpoints"/"source_tiktok_shop.json"
            path.parent.mkdir(parents=True)
            path.write_text("{broken")
            pipe = AcquisitionPipeline(tmp)
            result = pipe.run_sources({"tiktok_shop":["https://shop.example/cat"]}, lambda _:self.fail("must not fetch"))
            self.assertEqual(result["source_errors"]["tiktok_shop"][0]["status"], "checkpoint_corrupt")
            self.assertEqual(path.read_text(), "{broken")

    def test_network_diagnostic_reports_dns_layer_without_fetch(self):
        from brand_acquisition.diagnostics import diagnose_network
        class NeverFetch:
            def fetch(self, _): raise AssertionError("DNS-blocked hosts must not be requested")
        def dns_failure(*_args, **_kwargs): raise OSError("blocked")
        result = diagnose_network(endpoints={"tiktok":"https://tt.example/", "amazon":"https://amz.example/", "faire":"https://faire.example/"},
            fetcher=NeverFetch(), resolver=dns_failure, proxy_probe=lambda *_:False)
        self.assertFalse(result["NETWORK_EGRESS_AVAILABLE"])
        self.assertFalse(result["DNS_RESOLUTION_AVAILABLE"])
        self.assertTrue(result["DEVELOPMENT_ENV_NETWORK_BLOCKED"])

    def test_network_diagnostic_reports_sanitized_proxy_source_and_port(self):
        import os
        from unittest.mock import patch
        from brand_acquisition.diagnostics import diagnose_network
        class NeverFetch:
            def fetch(self, _): raise AssertionError("DNS-blocked hosts must not be requested")
        with patch.dict(os.environ, {"HTTPS_PROXY":"http://user:secret@127.0.0.1:3213/private"}, clear=True):
            result = diagnose_network(endpoints={"tiktok":"https://tt.example/"}, fetcher=NeverFetch(),
                resolver=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("blocked")),
                proxy_probe=lambda host, port: host == "127.0.0.1" and port == 3213)
        self.assertEqual(result["PROXY_CONFIG_SOURCE"], "process_environment:HTTPS_PROXY")
        self.assertEqual(result["PROXY_PORT"], 3213)
        self.assertTrue(result["PROXY_REACHABLE"])
        self.assertFalse(result["NETWORK_POLICY_SOURCE_IDENTIFIED"])
        self.assertNotIn("secret", repr(result))
        self.assertNotIn("private", repr(result))

    def test_history_suppression_and_bounce_fail_closed(self):
        for state in ("suppressed", "unsubscribed", "hard_bounced", "duplicate_organization", "organization_previously_sent"):
            item = BrandCandidate("PaperWorks", brand_identity_status="brand_owner_confirmed", official_website="https://paperworks.example")
            with temp_dir() as tmp:
                result = AcquisitionPipeline(tmp, history_check=lambda _, value=state:value,
                    official_site_check=lambda _:self.fail("history must block before site fetch")).enrich([item])
            self.assertNotEqual(result["metrics"]["HISTORY_CLEAN_BRANDS_WITH_EMAIL"], 1)

    def test_timeout_is_retryable_not_completed(self):
        with temp_dir() as tmp:
            timeout = StaticFetcher({"status":"timeout", "error":"TimeoutError"})
            pipe = AcquisitionPipeline(tmp)
            url = "https://shop.example/slow"
            pipe.run_sources({"tiktok_shop":[url]}, lambda _:timeout, now="2026-10-08T12:00:00+00:00")
            cp = json.loads((Path(tmp)/"source_checkpoints"/"source_tiktok_shop.json").read_text())
        self.assertIn(url, cp["retryable_urls"])
        self.assertNotIn(url, cp["completed_urls"])

    def test_403_access_restriction_is_recorded_and_not_retried(self):
        with temp_dir() as tmp:
            restricted = StaticFetcher({"status":"access_restricted", "http_status":403, "error":"http_403"})
            pipe = AcquisitionPipeline(tmp)
            url = "https://amazon.example/blocked"
            pipe.run_sources({"amazon":[url]}, lambda _:restricted, now="2026-10-08T12:00:00+00:00")
            cp = json.loads((Path(tmp)/"source_checkpoints"/"source_amazon.json").read_text())
        self.assertIn(url, cp["access_restricted_urls"])
        self.assertNotIn(url, cp["retryable_urls"])

    def test_unsafe_cross_party_or_private_redirect_is_rejected(self):
        from urllib.error import URLError
        from urllib.request import Request
        from brand_acquisition.providers import _PublicRedirectHandler
        handler = _PublicRedirectHandler(require_https=True, allowed_domain="paperworks.example")
        req = Request("https://paperworks.example/")
        with self.assertRaises(URLError):
            handler.redirect_request(req, None, 302, "Found", {}, "https://127.0.0.1/admin")
        with self.assertRaises(URLError):
            handler.redirect_request(req, None, 302, "Found", {}, "https://malicious.example/")

    def test_fixture_and_imported_candidates_are_excluded_from_live_counts(self):
        class FixtureFetcher:
            def fetch(self, url):
                return PageResult(url, "ok", TIKTOK_PAGE, fetch_method="fixture")
        with temp_dir() as tmp:
            result = AcquisitionPipeline(tmp).run_sources({"tiktok_shop":["https://shop.example/test"]}, lambda _:FixtureFetcher(),
                now="2026-10-08T12:00:00+00:00")
        self.assertGreater(len(result["candidates"]), 0)
        self.assertEqual(result["metrics"]["RAW_BRANDS_DISCOVERED"], 0)
        self.assertEqual(result["metrics"]["PER_SOURCE"][0]["fixture_candidates"], len(result["candidates"]))
        self.assertTrue(all(c["fixture_status"] == "KNOWN_TEST_SEED" for c in result["candidates"]))

    def test_import_manifest_requires_timestamp_and_remains_discovery_only(self):
        from brand_acquisition.providers import ImportedPageFetcher
        with temp_dir() as tmp:
            root = Path(tmp)
            manifest = root / "pages.json"
            url = "https://shop.example/imported"
            manifest.write_text(json.dumps({"scope":"discovery_only", "pages":[{
                "source_url":url, "collected_at":"2026-10-08T12:00:00Z", "acquisition_method":"authorized_export",
                "evidence_scope":"discovery_only", "html":TIKTOK_PAGE}]}))
            fetcher = ImportedPageFetcher(manifest)
            result = AcquisitionPipeline(root / "run").run_sources({"tiktok_shop":[url]}, lambda _:fetcher,
                now="2026-10-08T12:05:00+00:00")
            self.assertGreater(len(result["candidates"]), 0)
            self.assertEqual(result["metrics"]["RAW_BRANDS_DISCOVERED"], 0)
            self.assertTrue(all(c["data_origin"] == "public_import" for c in result["candidates"]))
            manifest.write_text(json.dumps({"scope":"discovery_only", "pages":[{
                "source_url":url, "collected_at":"2026-10-08T12:00:00", "acquisition_method":"authorized_export",
                "evidence_scope":"discovery_only", "html":TIKTOK_PAGE}]}))
            with self.assertRaises(ValueError):
                ImportedPageFetcher(manifest).fetch(url)

    def test_caps_are_conservative(self):
        with self.assertRaises(ValueError): PipelineConfig(max_candidates=91)
        with self.assertRaises(ValueError): PipelineConfig(provider_max_pages=4)
        with self.assertRaises(ValueError): PipelineConfig(http_workers=5)
        with self.assertRaises(ValueError): PipelineConfig(browser_workers=2)


if __name__ == "__main__":
    unittest.main()
