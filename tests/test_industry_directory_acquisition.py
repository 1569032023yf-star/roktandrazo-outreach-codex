"""Synthetic structures only: no live directory/customer claims or network calls."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from brand_acquisition.capture_manifest import write_capture, write_manifest, validate_manifest
from brand_acquisition.capture_import import import_manifest
from brand_acquisition.directory_adapters import DIRECTORY_PARSERS, DIRECTORY_SOURCES, classify
from brand_acquisition.directory_pipeline import DirectoryAcquisitionPipeline, directory_metrics, make_directory_callbacks
from brand_acquisition.models import BrandCandidate
from brand_acquisition.pipeline import PipelineConfig, deduplicate, organization_key
from brand_acquisition.providers import PageResult, run_public_source
from scripts.run_brand_capture import main, _capture_directories

TMP = Path(__file__).resolve().parents[1] / "output" / "brand_acquisition_test_tmp"
TMP.mkdir(parents=True, exist_ok=True)
STAMP = "2026-10-12T00:00:00+00:00"


def fixture(source, name="Synthetic Paper", country="United States", site="https://synthetic-paper.example/", category=None):
    category = category or ("Toy Stores" if source in {"toyfair", "astra"} else "Greeting Cards")
    return ('<section class="member-directory"><article class="company-card">'
            f'<h3>{name}</h3><span class="country">{country}</span>'
            f'<span class="category">{category}</span>'
            + (f'<a href="{site}">Official Website</a>' if site else '') + '</article></section>')


def candidate(source="toyfair", **kwargs):
    return DIRECTORY_PARSERS[source](fixture(source, **kwargs), DIRECTORY_SOURCES[source]["url"])[0]


class Fetcher:
    def __init__(self, source, status="ok", **kwargs):
        self.source, self.status, self.kwargs = source, status, kwargs
        self.calls = 0

    def fetch(self, url, **kwargs):
        self.calls += 1
        return PageResult(url, self.status, fixture(self.source, **self.kwargs), final_url=url,
                          http_status=200, fetched_at=STAMP, fetch_method="fixture")


class DirectoryParserTests(unittest.TestCase):
    def test_each_normal_page_and_unverified_contract(self):
        for source in DIRECTORY_PARSERS:
            with self.subTest(source=source):
                c = candidate(source)
                self.assertEqual(c.organization_name, "Synthetic Paper")
                self.assertEqual(c.organization_country, "United States")
                self.assertEqual(c.directory_source_year, DIRECTORY_SOURCES[source]["year"])
                self.assertEqual(c.directory_source_class, DIRECTORY_SOURCES[source]["class"])
                self.assertEqual(c.buyer_type, "unverified")
                self.assertFalse(c.official_site_verified)
                self.assertEqual(c.business_email, "")
                self.assertEqual(c.identity_class, "IDENTITY_UNVERIFIED")

    def test_each_empty_and_unrecognized_layout_fail_closed(self):
        for source, parser in DIRECTORY_PARSERS.items():
            for html in ("", "<nav><a>Home</a></nav>", "<main><h1>Directory</h1><p>No entries</p></main>"):
                with self.subTest(source=source, html=html):
                    self.assertEqual(parser(html, DIRECTORY_SOURCES[source]["url"]), [])

    def test_each_changed_css_table_and_jsonld(self):
        table = '<table><tr><th>Company Name</th><th>Country</th><th>Category</th></tr><tr><td>Synthetic Org</td><td>Canada</td><td>Stationery</td></tr></table>'
        ld = '<script type="application/ld+json">' + json.dumps({"@type": "Organization", "name": "Synthetic JSON", "category": "Paper Goods", "address": {"addressCountry": "Japan"}, "url": "https://synthetic-json.example/"}) + '</script>'
        for source, parser in DIRECTORY_PARSERS.items():
            with self.subTest(source=source):
                rows = parser(table, DIRECTORY_SOURCES[source]["url"])
                self.assertEqual(rows[0].organization_country, "Canada")
                self.assertEqual(parser(ld, DIRECTORY_SOURCES[source]["url"])[0].organization_country, "Japan")

    def test_each_no_site_non_us_and_no_domain_guess(self):
        for source in DIRECTORY_PARSERS:
            with self.subTest(source=source):
                c = candidate(source, country="France", site="")
                self.assertEqual(c.organization_country, "France")
                self.assertEqual(c.official_site_candidates, [])
                self.assertEqual(c.official_site_resolution_status, "OFFICIAL_SITE_UNRESOLVED")

    def test_each_company_link_scope(self):
        for source, parser in DIRECTORY_PARSERS.items():
            with self.subTest(source=source):
                html = '<a href="https://global.example">Official Website</a>' + fixture(source, name="Synthetic A", site="https://synthetic-a.example/") + fixture(source, name="Synthetic B", site="")
                a, b = parser(html, DIRECTORY_SOURCES[source]["url"])
                self.assertEqual(a.official_site_candidates[0]["website"], "https://synthetic-a.example/")
                self.assertEqual(b.official_site_candidates, [])

    def test_each_same_name_distinct_organizations_and_conflicts(self):
        for source, parser in DIRECTORY_PARSERS.items():
            with self.subTest(source=source):
                rows = parser(fixture(source, site="https://synthetic-a.example/") + fixture(source, country="Canada", site="https://synthetic-b.example/"), DIRECTORY_SOURCES[source]["url"])
                self.assertEqual(len(deduplicate(rows)), 2)
                self.assertTrue(all(c.identity_class == "IDENTITY_CONFLICT" for c in rows))
                a, b = candidate(source, site="", country="US"), candidate(source, site="", country="UK")
                self.assertNotEqual(organization_key(a), organization_key(b))
                self.assertEqual(len(deduplicate([a, b])), 2)

    def test_each_verified_duplicates_merge_all_evidence(self):
        for source in DIRECTORY_PARSERS:
            with self.subTest(source=source):
                a, b = candidate(source), candidate("gca" if source != "gca" else "nynow")
                for c in (a, b):
                    c.official_website = "https://synthetic-paper.example/"
                    c.official_site_verified = True
                    c.organization_identity_verified = True
                    c.data_origin_label = "LIVE_PUBLIC_CAPTURE"
                b.source_capture_ids = ["synthetic-id"]
                unique = deduplicate([a, b])
                self.assertEqual(len(unique), 1)
                self.assertEqual(len(unique[0].directory_evidence), 2)
                self.assertIn("synthetic-id", unique[0].source_capture_ids)
                self.assertEqual(directory_metrics([a, b], unique)["CROSS_SOURCE_DUPLICATES"], 1)

    def test_gca_member_types_and_supplier_filter(self):
        cases = [("Greeting Cards", "brand", "CARD_BRAND"), ("Greeting Cards", "publisher", "CARD_PUBLISHER"),
                 ("Stationery", "brand", "PAPER_GOODS_BRAND"), ("Paper", "printer", "SUPPLIER"),
                 ("Greeting Cards", "distributor", "DISTRIBUTOR"), ("", "", "UNKNOWN")]
        for cat, kind, expected in cases:
            self.assertEqual(classify("gca", cat, kind)[1], expected)
        c = candidate("gca", category="Printing Services")
        self.assertEqual(c.organization_type, "SUPPLIER_CANDIDATE")
        self.assertEqual(c.category_filter_status, "excluded")
        self.assertEqual(candidate("nynow", category="Industrial Steel").category_filter_status, "excluded")

    def test_toyfair_public_plain_list(self):
        html = '<ul class="participating-retailers"><li>Synthetic Name Only</li><li><strong>Synthetic Store</strong><span class="country">Mexico</span></li></ul>'
        rows = DIRECTORY_PARSERS["toyfair"](html, DIRECTORY_SOURCES["toyfair"]["url"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].category_filter_status, "needs_review")
        self.assertEqual(rows[1].organization_country, "Mexico")

    def test_archived_exhibitor_year_is_not_relabelled_current(self):
        c = DIRECTORY_PARSERS["nynow"](fixture("nynow"), "https://nynow.a2zinc.net/Summer2025/Public/exhibitors.aspx")[0]
        self.assertEqual(c.directory_source_year, 2025)

    def test_each_timestamp_and_provenance_propagation(self):
        for source in DIRECTORY_PARSERS:
            run = run_public_source(source, [DIRECTORY_SOURCES[source]["url"]], Fetcher(source), max_pages=2)
            self.assertEqual(run.candidates[0].directory_evidence[0]["captured_at"], STAMP)
            self.assertEqual(run.candidates[0].data_origin_label, "TEST_FIXTURE")


class DirectoryImportTests(unittest.TestCase):
    def write(self, tmp, source, origin="LIVE_PUBLIC_CAPTURE"):
        r = write_capture(tmp, source_platform=source, requested_url=DIRECTORY_SOURCES[source]["url"],
            final_url=DIRECTORY_SOURCES[source]["url"], captured_at=STAMP, capture_method="synthetic_test",
            http_status=200, content_type="text/html", html=fixture(source), page_category="industry_directory", data_origin=origin)
        return write_manifest(tmp, [r]), r

    def test_each_import_discovery_only_and_callbacks_not_called(self):
        for source in DIRECTORY_PARSERS:
            with self.subTest(source=source), tempfile.TemporaryDirectory(dir=TMP) as tmp:
                path, _ = self.write(tmp, source)
                _, runs = import_manifest(path)
                callbacks = Mock(side_effect=AssertionError("offline callback"))
                output = DirectoryAcquisitionPipeline(Path(tmp) / "out", organization_identity_check=callbacks,
                    official_site_check=callbacks, first_party_extract=callbacks, mx_check=callbacks).enrich(runs[0].candidates)
                c = output["candidates"][0]
                self.assertEqual(c["enrichment_status"], "live_revalidation_required")
                self.assertEqual(c["history_status"], "UNKNOWN")
                self.assertEqual(c["business_email"], "")
                self.assertEqual(output["directory_metrics"]["FIRST_PARTY_EMAILS_FOUND"], 0)
                self.assertEqual(output["directory_metrics"]["BY_DATA_ORIGIN"]["OFFLINE_IMPORT"]["DEDUPED_CANDIDATE_ORGS"], 1)
                callbacks.assert_not_called()

    def test_each_unsafe_path_missing_source_and_corrupt_content(self):
        for source in DIRECTORY_PARSERS:
            for damage in ("path", "source", "hash", "content"):
                with self.subTest(source=source, damage=damage), tempfile.TemporaryDirectory(dir=TMP) as tmp:
                    path, r = self.write(tmp, source)
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if damage == "path": value["pages"][0]["content_file"] = "../escape.html"
                    if damage == "source": del value["pages"][0]["requested_url"]
                    if damage == "hash": value["pages"][0]["content_sha256"] = "0" * 64
                    if damage == "content": (Path(tmp) / r.content_file).write_text("corrupt", encoding="utf-8")
                    path.write_text(json.dumps(value), encoding="utf-8")
                    with self.assertRaises(ValueError): validate_manifest(path)

    def test_official_captures_not_reparsed_as_directory(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            path, r = self.write(tmp, "gca")
            path = write_manifest(tmp, [replace(r, page_category="official_site")])
            self.assertEqual(import_manifest(path)[1], [])

    def test_cli_replay_outputs_ignored_discovery_candidates(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            path, _ = self.write(tmp, "toyfair")
            with patch("brand_acquisition.providers.PublicPageFetcher.fetch", side_effect=AssertionError("network")):
                self.assertEqual(main(["--mode", "replay", "--manifest", str(path), "--output-dir", str(Path(tmp) / "out")], directory=True), 0)
            payload = json.loads((Path(tmp) / "out" / "imported_discovery_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "discovery_only")
            self.assertEqual(len(payload["candidates"]), 1)


class DirectoryPipelineTests(unittest.TestCase):
    def callbacks(self, email="sales@synthetic-paper.example", history="new_candidate", mx="ok"):
        def identity(c):
            c.identity_class = "ORGANIZATION_CONFIRMED"
            c.official_site_checked_at = STAMP
            return True
        return dict(organization_identity_check=identity, official_site_check=lambda _: True,
            first_party_extract=lambda c: {"email": email, "role": "SALES", "url": c.official_website,
                "final_url": c.official_website, "excerpt": "Public business contact " + email,
                "checked_at": STAMP, "source_type": "first_party_official_page", "http_status": 200,
                "official_identity_verified": True}, history_check=lambda _: history, mx_check=lambda _: mx)

    def mock_observation(self, source):
        c = candidate(source)
        # Exercise runtime callbacks with mocked transport; never use these
        # synthetic LIVE labels in business reports or committed customer output.
        c.data_origin_label = "LIVE_PUBLIC_CAPTURE"
        return c

    def test_each_mock_end_to_end_and_never_claim_brand_owner(self):
        for source in DIRECTORY_PARSERS:
            with self.subTest(source=source), tempfile.TemporaryDirectory(dir=TMP) as tmp:
                payload = DirectoryAcquisitionPipeline(tmp, **self.callbacks()).enrich([self.mock_observation(source)])
                c = payload["candidates"][0]
                self.assertEqual(c["brand_identity_status"], "organization_confirmed")
                self.assertEqual(c["identity_class"], "ORGANIZATION_CONFIRMED")
                self.assertTrue(c["official_site_verified"])
                self.assertEqual(c["enrichment_status"], "complete")
                self.assertEqual(payload["metrics"]["BRAND_OWNERS_CONFIRMED"], 0)
                self.assertEqual(payload["directory_metrics"]["HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL"], 1)

    def test_each_wrong_email_placeholder_history_and_mx_fail_closed(self):
        for source in DIRECTORY_PARSERS:
            for options in ({"email": "sales@unrelated.example"}, {"email": "info@mysite.com"},
                            {"history": "UNKNOWN"}, {"mx": "dns_error"}):
                with self.subTest(source=source, options=options), tempfile.TemporaryDirectory(dir=TMP) as tmp:
                    payload = DirectoryAcquisitionPipeline(tmp, **self.callbacks(**options)).enrich([self.mock_observation(source)])
                    self.assertEqual(payload["directory_metrics"]["HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL"], 0)
                    self.assertNotEqual(payload["candidates"][0]["enrichment_status"], "complete")
                    if "email" in options:
                        self.assertEqual(payload["candidates"][0]["business_email"], "")

    def test_unconfirmed_site_and_excluded_supplier_never_extract_email(self):
        for c in (candidate("toyfair", site=""), candidate("gca", category="Printing Services")):
            with tempfile.TemporaryDirectory(dir=TMP) as tmp:
                extract = Mock(side_effect=AssertionError("no email"))
                payload = DirectoryAcquisitionPipeline(tmp, first_party_extract=extract).enrich([c])
                extract.assert_not_called()
                self.assertEqual(payload["directory_metrics"]["OFFICIAL_SITES_VERIFIED"], 0)

    def test_verified_after_enrichment_merges_cross_source(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            payload = DirectoryAcquisitionPipeline(tmp, **self.callbacks()).enrich([
                self.mock_observation("toyfair"), self.mock_observation("gca")])
            self.assertEqual(len(payload["candidates"]), 1)
            self.assertEqual(len(payload["candidates"][0]["directory_evidence"]), 2)

    def test_fixture_metrics_cannot_assert_verified_yield(self):
        c = candidate("gca")
        c.data_origin_label = "TEST_FIXTURE"
        c.official_site_verified = c.organization_identity_verified = True
        result = directory_metrics([c], [c])
        self.assertEqual(result["OFFICIAL_SITES_VERIFIED"], 0)
        self.assertEqual(result["BY_DATA_ORIGIN"]["TEST_FIXTURE"]["OFFICIAL_SITES_VERIFIED"], 0)

    def test_network_gate_before_any_fetcher(self):
        with patch.dict("os.environ", {"CODEX_SANDBOX_NETWORK_DISABLED": "1"}), patch("scripts.run_brand_capture.PublicPageFetcher", side_effect=AssertionError("network")):
            self.assertEqual(main(["--mode", "capture-public"], directory=True), 2)

    def test_each_source_retry_resume_without_refetch_completed(self):
        for source in DIRECTORY_PARSERS:
            with self.subTest(source=source), tempfile.TemporaryDirectory(dir=TMP) as tmp:
                url = DIRECTORY_SOURCES[source]["url"]
                fetch = Fetcher(source, "transient_failure")
                pipeline = DirectoryAcquisitionPipeline(tmp, PipelineConfig(provider_max_pages=2))
                now = datetime(2026, 10, 12, tzinfo=timezone.utc)
                pipeline.run_sources({source: [url]}, lambda _: fetch, now=now)
                fetch.status = "ok"
                pipeline.run_sources({source: [url]}, lambda _: fetch, now=now + timedelta(seconds=61))
                pipeline.run_sources({source: [url]}, lambda _: fetch, now=now + timedelta(seconds=122))
                self.assertEqual(fetch.calls, 2)
                cp = json.loads((Path(tmp) / "source_checkpoints" / f"source_{source}.json").read_text())
                self.assertEqual(cp["attempt_counts"][url], 2)

    def test_each_access_restriction_not_bypassed(self):
        for source in DIRECTORY_PARSERS:
            with self.subTest(source=source), tempfile.TemporaryDirectory(dir=TMP) as tmp:
                fetch = Fetcher(source, "access_restricted")
                pipeline = DirectoryAcquisitionPipeline(tmp, PipelineConfig(provider_max_pages=2))
                pages = {source: [DIRECTORY_SOURCES[source]["url"]]}
                pipeline.run_sources(pages, lambda _: fetch)
                pipeline.run_sources(pages, lambda _: fetch)
                self.assertEqual(fetch.calls, 1)

    def test_corrupt_checkpoint_preserved(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            p = Path(tmp) / "checkpoint.json"
            p.write_text("damaged", encoding="utf-8")
            with self.assertRaises(ValueError): DirectoryAcquisitionPipeline(tmp).enrich([candidate()])
            self.assertEqual(p.read_text(), "damaged")

    def test_raw_caps_and_two_page_limit(self):
        html = ''.join(fixture("toyfair", name=f"Synthetic {i}") for i in range(40))
        fetch = Mock()
        fetch.fetch.side_effect = lambda url: PageResult(url, "ok", html, fetch_method="fixture")
        run = run_public_source("toyfair", ["https://directory.example/1", "https://directory.example/2", "https://directory.example/3"], fetch, max_pages=2, max_candidates=22)
        self.assertEqual(len(run.candidates), 22)
        self.assertLessEqual(fetch.fetch.call_count, 2)

    def test_directory_live_runner_with_mock_fetch_and_official_recorder(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            fetch = Fetcher("toyfair")
            with patch("scripts.run_brand_capture.make_directory_callbacks", return_value={}):
                self.assertEqual(_capture_directories({"toyfair": [{"url": DIRECTORY_SOURCES["toyfair"]["url"]}]}, Path(tmp), Path(tmp) / "captures", fetch), 0)
            manifest = validate_manifest(Path(tmp) / "captures" / "capture_manifest.json")
            self.assertEqual(manifest["pages_validated"], 1)
            self.assertTrue((Path(tmp) / "source_checkpoints" / "source_toyfair.json").exists())

    def test_directory_callbacks_use_independent_first_party_match(self):
        verify = Mock(return_value=True)
        with patch("brand_acquisition.directory_pipeline.make_runtime_callbacks", return_value={"official_site_check": verify}):
            callbacks = make_directory_callbacks()
        c = candidate("toyfair")
        c.official_website = "https://synthetic-paper.example/"
        self.assertTrue(callbacks["organization_identity_check"](c))
        self.assertEqual(c.identity_class, "ORGANIZATION_CONFIRMED")
        self.assertFalse(c.owner_verification_evidence[-1]["brand_ownership_verified"])
        verify.assert_called_once_with(c)
        # A plausible domain without the business name on its pages is not
        # sufficient independent directory identity corroboration.
        from brand_acquisition.pipeline import make_first_party_enricher
        pages = [{"text": "Unrelated company contact", "url": "https://synthetic-paper.example/"}]
        with patch("discovery.discovery_service._fetch_official_pages", return_value=pages):
            strict_verify, _ = make_first_party_enricher(Mock(), strict_name_match=True)
            self.assertFalse(strict_verify(c))

    def test_completed_directory_enrichment_resumes_without_site_refetch(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            callbacks = self.callbacks()
            identity = Mock(side_effect=callbacks["organization_identity_check"])
            callbacks["organization_identity_check"] = identity
            pipeline = DirectoryAcquisitionPipeline(tmp, **callbacks)
            pipeline.enrich([self.mock_observation("toyfair")])
            result = pipeline.enrich([self.mock_observation("toyfair")])
            self.assertEqual(identity.call_count, 1)
            self.assertEqual(result["candidates"][0]["enrichment_status"], "complete")

    def test_import_cannot_resume_live_contact_qualification(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            pipeline = DirectoryAcquisitionPipeline(tmp, **self.callbacks())
            pipeline.enrich([self.mock_observation("toyfair")])
            imported = candidate("toyfair")
            imported.data_origin_label = "AUTHORIZED_PUBLIC_IMPORT"
            result = pipeline.enrich([imported])
            self.assertEqual(result["candidates"][0]["business_email"], "")
            self.assertFalse(result["candidates"][0]["official_site_verified"])

    def test_shared_first_party_extractor_and_capture_observer_with_mock_transport(self):
        # Real pipeline, identity check, extractor and recorder; network/MX are
        # mocked. These temporary synthetic observations are not live customers.
        def response(_self, url, **kwargs):
            directory = "toyassociation.org" in url
            html = fixture("toyfair") if directory else '<html><h1>Synthetic Paper</h1><p>Public sales contact: sales@synthetic-paper.example</p></html>'
            return PageResult(url, "ok", html, final_url=url, http_status=200,
                              fetched_at=STAMP, content_type="text/html")
        with tempfile.TemporaryDirectory(dir=TMP) as tmp, patch("brand_acquisition.providers.PublicPageFetcher.fetch", response), patch("email_hygiene.check_mx_cached", return_value={"provider": "google"}):
            from brand_acquisition.providers import PublicPageFetcher
            catalog = {"toyfair": [{"url": DIRECTORY_SOURCES["toyfair"]["url"]}]}
            self.assertEqual(_capture_directories(catalog, Path(tmp), Path(tmp) / "captures", PublicPageFetcher()), 0)
            result = json.loads((Path(tmp) / "live_directory_result.json").read_text(encoding="utf-8"))
            c = result["candidates"][0]
            self.assertEqual(c["business_email"], "sales@synthetic-paper.example")
            self.assertEqual(c["email_role"], "SALES")
            self.assertEqual(c["history_status"], "UNKNOWN")
            self.assertEqual(result["directory_metrics"]["HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL"], 0)
            pages = validate_manifest(Path(tmp) / "captures" / "capture_manifest.json")["pages"]
            self.assertTrue(any(p["page_category"] == "official_site" for p in pages))


if __name__ == "__main__":
    unittest.main()
