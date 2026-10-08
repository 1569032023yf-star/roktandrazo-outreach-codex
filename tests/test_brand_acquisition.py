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
        self.assertEqual(item.identity_class, "seller_or_listing")
        self.assertEqual(item.brand_owner_name, "")
        self.assertEqual(item.brand_identity_status, "unknown")

    def test_cross_source_dedup_keeps_source_evidence(self):
        a = BrandCandidate("PaperWorks", official_website="https://paperworks.example", source_platforms=["amazon"], source_urls=["https://a.example/p"])
        b = BrandCandidate("paper works", official_website="https://paperworks.example", source_platforms=["wholesale"], source_urls=["https://f.example/b"])
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
                    "url":"https://paperworks.example/wholesale", "excerpt":"Contact sales@paperworks.example", "checked_at":"2026-10-08T00:00:00Z"},
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
            email_hygiene_status="ok", mx_status="ok", history_status="new_candidate", source_platforms=["tiktok_shop", "wholesale"])]
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

    def test_caps_are_conservative(self):
        with self.assertRaises(ValueError): PipelineConfig(max_candidates=91)
        with self.assertRaises(ValueError): PipelineConfig(provider_max_pages=4)
        with self.assertRaises(ValueError): PipelineConfig(http_workers=5)
        with self.assertRaises(ValueError): PipelineConfig(browser_workers=2)


if __name__ == "__main__":
    unittest.main()
