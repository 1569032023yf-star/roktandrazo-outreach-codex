#!/usr/bin/env python3
"""Offline-first, auditable brand acquisition capture/import CLI."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from threading import Lock
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brand_acquisition.capture_import import import_manifest
from brand_acquisition.capture_manifest import CaptureRecord, write_capture, write_manifest, validate_manifest
from brand_acquisition.directory_adapters import DIRECTORY_CATALOG, DIRECTORY_PARSERS, DIRECTORY_SOURCES
from brand_acquisition.directory_pipeline import DirectoryAcquisitionPipeline, make_directory_callbacks
from brand_acquisition.pipeline import AcquisitionPipeline, PipelineConfig, make_runtime_callbacks
from brand_acquisition.providers import PageResult, PublicPageFetcher, SafeOfficialPageFetcher, run_public_source
from brand_acquisition.source_catalog import load_catalog

DEFAULT_OUT = ROOT / "output" / "brand_acquisition" / "phase4b1d"


def _blocked_by_network_policy() -> bool:
    return os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED", "").strip().casefold() in {"1", "true", "yes", "on"}


def main(argv=None, *, directory=False) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("capture-public", "import-pages", "replay", "validate-manifest"), required=True)
    parser.add_argument("--catalog")
    parser.add_argument("--manifest")
    if directory:
        parser.add_argument("--development-history-copy")
        parser.add_argument("--confirm-development-history-copy", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT.parent / "phase4b1e" if directory else DEFAULT_OUT))
    args = parser.parse_args(argv)
    if directory and args.development_history_copy and (args.mode != "capture-public" or not args.confirm_development_history_copy):
        parser.error("history copy is live-development-only and requires explicit development-copy confirmation")
    out = Path(args.output_dir)
    if args.mode == "validate-manifest":
        if not args.manifest: parser.error("--manifest is required")
        print(json.dumps(validate_manifest(args.manifest), ensure_ascii=False, indent=2))
        return 0
    if args.mode in {"import-pages", "replay"}:
        if not args.manifest: parser.error("--manifest is required")
        manifest, runs = import_manifest(args.manifest)
        if directory:
            runs = [run for run in runs if run.source in DIRECTORY_SOURCES]
        out.mkdir(parents=True, exist_ok=True)
        payload = {"scope": "discovery_only", "source_authenticity_verified": False,
            "manifest": os.path.abspath(args.manifest),
            "candidates": [candidate.to_dict() for run in runs for candidate in run.candidates],
            "source_runs": [{"source": run.source, "pages_attempted": run.pages_attempted,
                "pages_fetched": run.pages_fetched, "candidates": len(run.candidates), "errors": run.errors}
                for run in runs]}
        if directory:
            raw = [c for run in runs for c in run.candidates]
            pipeline = DirectoryAcquisitionPipeline(out, PipelineConfig(provider_max_pages=2))
            enriched = pipeline.enrich(raw)
            payload["candidates"] = enriched["candidates"]
            payload["directory_metrics"] = enriched["directory_metrics"]
        (out / "imported_discovery_candidates.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"pages_validated": manifest["pages_validated"], "candidates": len(payload["candidates"]),
                          "output": str(out / "imported_discovery_candidates.json")}, ensure_ascii=False))
        return 0
    # Gate before reading a catalog, constructing a fetcher, resolving DNS, or sending requests.
    if _blocked_by_network_policy():
        print(json.dumps({"status": "NETWORK_POLICY_BLOCKED", "requests_made": 0,
                          "reason": "CODEX_SANDBOX_NETWORK_DISABLED"}), file=sys.stderr)
        return 2
    catalog = load_catalog(args.catalog) if args.catalog or not directory else DIRECTORY_CATALOG["sources"]
    if directory and (not catalog or any(source not in DIRECTORY_SOURCES for source in catalog)):
        raise ValueError("directory canary catalog must contain directory sources only")
    out.mkdir(parents=True, exist_ok=True)
    capture_root = out / "captures"
    fetcher = PublicPageFetcher()
    records, candidates, summaries = [], [], []
    if directory:
        from brand_acquisition.history import HistoryChecker
        history = HistoryChecker(args.development_history_copy,
            development_copy=bool(args.confirm_development_history_copy)) if args.development_history_copy else None
        return _capture_directories(catalog, out, capture_root, fetcher, history_check=history)
    for source, entries in catalog.items():
        class RecordingFetcher:
            def fetch(self, url):
                result = fetcher.fetch(url, require_https=True)
                # One bounded backoff retry for transient transport/5xx errors.
                if result.status in {"transient_failure", "network_error", "timeout"}:
                    time.sleep(1.0)
                    result = fetcher.fetch(url, require_https=True)
                if result.status in {"ok", "success"} and result.html:
                    record = write_capture(capture_root, source_platform=source, requested_url=url,
                        final_url=result.final_url or url, captured_at=result.fetched_at or datetime.now(timezone.utc).isoformat(),
                        capture_method="public_https", http_status=result.http_status or 200,
                        content_type=result.content_type or "text/html", html=result.html,
                        page_category=next((e["category"] for e in entries if e["url"] == url), "uncategorized"))
                    records.append(record)
                    result.capture_id = record.capture_id
                    result.data_origin = "LIVE_PUBLIC_CAPTURE"
                return result
        run = run_public_source(source, [entry["url"] for entry in entries], RecordingFetcher(), max_pages=3)
        categories = {entry["url"]: entry["category"] for entry in entries}
        for candidate in run.candidates:
            category = categories.get(candidate.discovery_source_url)
            if category:
                candidate.product_categories = [category]
        candidates.extend(run.candidates)
        summaries.append({"source": source, "pages_attempted": run.pages_attempted,
            "pages_fetched": run.pages_fetched, "candidates": len(run.candidates), "errors": run.errors})
    write_manifest(capture_root, records)
    # Live enrich uses existing bounded HTTPS checks and fail-closed history defaults.
    source_by_host = {}
    for candidate in candidates:
        for site in ([candidate.official_website] if candidate.official_website else []):
            host = (urlsplit(site).hostname or "").lower().removeprefix("www.")
            if host:
                source_by_host.setdefault(host, candidate.source_platforms[0] if candidate.source_platforms else "wholesale")
        for item in candidate.official_site_candidates:
            host = (urlsplit(item.get("website", "")).hostname or "").lower().removeprefix("www.")
            if host:
                source_by_host.setdefault(host, candidate.source_platforms[0] if candidate.source_platforms else "wholesale")

    def record_official_page(url, result):
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        source = source_by_host.get(host)
        if not source or not result.html:
            return
        record = write_capture(capture_root, source_platform=source, requested_url=url,
            final_url=result.final_url or url, captured_at=result.fetched_at or datetime.now(timezone.utc).isoformat(),
            capture_method="official_site_https", http_status=result.http_status or 200,
            content_type=result.content_type or "text/html", html=result.html, page_category="official_site",
            data_origin="LIVE_PUBLIC_CAPTURE")
        records.append(record)

    callbacks = make_runtime_callbacks(SafeOfficialPageFetcher(observer=record_official_page))
    payload = AcquisitionPipeline(out, PipelineConfig(), **callbacks).enrich(candidates)
    write_manifest(capture_root, records)
    payload["source_runs"] = summaries
    payload["capture_manifest"] = str(capture_root / "capture_manifest.json")
    (out / "live_discovery_result.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"pages_fetched": len(records), "candidates": len(candidates),
        "output": str(out / "live_discovery_result.json")}, ensure_ascii=False))
    return 0


def _capture_directories(catalog, out, capture_root, fetcher, history_check=None):
    """Reuse durable source retries and enrichment checkpoints for directory canaries."""
    records = []
    manifest_path = capture_root / "capture_manifest.json"
    if manifest_path.exists():
        validated = validate_manifest(manifest_path)
        keys = CaptureRecord.__dataclass_fields__
        records = [CaptureRecord(**{k: row[k] for k in keys}) for row in validated["pages"]]
    previous_capture_count = len(records)
    lock = Lock()
    source_by_host = {}

    def record(source, url, result, category):
        if result.status != "ok" or not result.html:
            return
        item = write_capture(capture_root, source_platform=source, requested_url=url,
            final_url=result.final_url or url,
            captured_at=result.fetched_at or datetime.now(timezone.utc).isoformat(),
            capture_method="official_site_https" if category == "official_site" else "public_https",
            http_status=result.http_status or 200, content_type=result.content_type or "text/html",
            html=result.html, page_category=category)
        with lock:
            records.append(item)
            write_manifest(capture_root, records)
        result.capture_id = item.capture_id
        result.data_origin = "LIVE_PUBLIC_CAPTURE"

    class RecordingFetcher:
        def __init__(self, source):
            self.source = source

        def fetch(self, url):
            result = fetcher.fetch(url, require_https=True)
            record(self.source, url, result, "industry_directory")
            if result.status == "ok":
                for c in DIRECTORY_PARSERS[self.source](result.html, result.final_url or url):
                    for site in c.official_site_candidates:
                        with lock:
                            source_by_host.setdefault(urlsplit(site["website"]).hostname, self.source)
            return result

    # Restore official candidate attribution for enrichment retries when source
    # checkpoints correctly skip already-fetched directory pages.
    checkpoint_root = out / "source_checkpoints"
    for source in catalog:
        path = checkpoint_root / f"source_{source}.json"
        if path.exists():
            try:
                for c in json.loads(path.read_text(encoding="utf-8")).get("candidates", []):
                    for site in c.get("official_site_candidates", []):
                        source_by_host.setdefault(urlsplit(site["website"]).hostname, source)
            except (OSError, ValueError, TypeError):
                pass  # shared source checkpoint loader reports and preserves corruption

    def official_observer(url, result):
        source = source_by_host.get(urlsplit(url).hostname)
        if source:
            record(source, url, result, "official_site")

    callbacks = make_directory_callbacks(SafeOfficialPageFetcher(observer=official_observer))
    if history_check is not None:
        callbacks["history_check"] = history_check
    config = PipelineConfig(provider_max_pages=2, source_max_candidates=min(30, 90 // len(catalog)))
    pipeline = DirectoryAcquisitionPipeline(out, config, **callbacks)
    payload = pipeline.run_sources({s: [r["url"] for r in entries[:2]] for s, entries in catalog.items()},
        fetcher_factory=RecordingFetcher)
    astra_status = "NOT_SELECTED"
    if "astra" in catalog:
        cp_path = checkpoint_root / "source_astra.json"
        cp = json.loads(cp_path.read_text(encoding="utf-8")) if cp_path.exists() else {}
        states = {v.get("status") for v in cp.get("url_states", {}).values()}
        astra_status = ("RESTRICTED_STOPPED" if "ACCESS_RESTRICTED" in states else
            "PUBLIC_LIST_PARSED_IDENTITY_UNVERIFIED" if cp.get("candidates") else
            "NO_PUBLIC_RECORDS_OR_UNSUPPORTED_LAYOUT" if "PARSE_EMPTY" in states else
            "PENDING_RETRY_OR_ENVIRONMENT_REVIEW")
    new_records = records[previous_capture_count:]
    payload.update({"scope": "isolated_development_directory_canary",
        "astra_status": astra_status,
        "capture_manifest": str(write_manifest(capture_root, records)),
        "LIVE_PAGES_FETCHED": sum(r.page_category == "industry_directory" for r in new_records),
        "FIRST_PARTY_PAGES_CAPTURED": sum(r.page_category == "official_site" for r in new_records),
        "capture_count_including_previous_runs": len(records),
        "max_pages_per_source": 2, "max_raw_candidates": 90,
        "http_workers_max": 4, "browser_workers_max": 1})
    (out / "live_directory_result.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(out / "live_directory_result.json"),
                      "directory_metrics": payload["directory_metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
