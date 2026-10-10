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
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brand_acquisition.capture_import import import_manifest
from brand_acquisition.capture_manifest import write_capture, write_manifest, validate_manifest
from brand_acquisition.pipeline import AcquisitionPipeline, PipelineConfig, make_runtime_callbacks
from brand_acquisition.providers import PageResult, PublicPageFetcher, SafeOfficialPageFetcher, run_public_source
from brand_acquisition.source_catalog import load_catalog

DEFAULT_OUT = ROOT / "output" / "brand_acquisition" / "phase4b1d"


def _blocked_by_network_policy() -> bool:
    return os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED", "").strip().casefold() in {"1", "true", "yes", "on"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("capture-public", "import-pages", "replay", "validate-manifest"), required=True)
    parser.add_argument("--catalog")
    parser.add_argument("--manifest")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    out = Path(args.output_dir)
    if args.mode == "validate-manifest":
        if not args.manifest: parser.error("--manifest is required")
        print(json.dumps(validate_manifest(args.manifest), ensure_ascii=False, indent=2))
        return 0
    if args.mode in {"import-pages", "replay"}:
        if not args.manifest: parser.error("--manifest is required")
        manifest, runs = import_manifest(args.manifest)
        out.mkdir(parents=True, exist_ok=True)
        payload = {"scope": "discovery_only", "source_authenticity_verified": False,
            "manifest": os.path.abspath(args.manifest),
            "candidates": [candidate.to_dict() for run in runs for candidate in run.candidates],
            "source_runs": [{"source": run.source, "pages_attempted": run.pages_attempted,
                "pages_fetched": run.pages_fetched, "candidates": len(run.candidates), "errors": run.errors}
                for run in runs]}
        (out / "imported_discovery_candidates.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"pages_validated": manifest["pages_validated"], "candidates": len(payload["candidates"]),
                          "output": str(out / "imported_discovery_candidates.json")}, ensure_ascii=False))
        return 0
    # Gate before reading a catalog, constructing a fetcher, resolving DNS, or sending requests.
    if _blocked_by_network_policy():
        print(json.dumps({"status": "NETWORK_POLICY_BLOCKED", "requests_made": 0,
                          "reason": "CODEX_SANDBOX_NETWORK_DISABLED"}), file=sys.stderr)
        return 2
    catalog = load_catalog(args.catalog)
    out.mkdir(parents=True, exist_ok=True)
    capture_root = out / "captures"
    fetcher = PublicPageFetcher()
    records, candidates, summaries = [], [], []
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
        if not source or not result.get("html"):
            return
        record = write_capture(capture_root, source_platform=source, requested_url=url,
            final_url=result.get("final_url") or url, captured_at=result.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
            capture_method="official_site_https", http_status=int(result.get("status") or 200),
            content_type="text/html", html=result["html"], page_category="official_site",
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


if __name__ == "__main__":
    raise SystemExit(main())
