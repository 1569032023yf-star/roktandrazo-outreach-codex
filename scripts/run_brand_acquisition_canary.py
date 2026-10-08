"""Bounded public brand-acquisition diagnostic/canary; development JSON only."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brand_acquisition import AcquisitionPipeline, PipelineConfig
from brand_acquisition.diagnostics import diagnose_network
from brand_acquisition.pipeline import make_runtime_callbacks
from brand_acquisition.providers import ImportedPageFetcher, PublicPageFetcher
from brand_acquisition.history import HistoryChecker

OUTPUT = ROOT / "output" / "brand_acquisition" / "phase4b1b"
SOURCE_PAGES = {
    "tiktok_shop": ["https://shop.tiktok.com/us/k/greetings-cards", "https://shop.tiktok.com/us/k/personal-greeting-cards"],
    "amazon": ["https://www.amazon.com/s?k=greeting+cards"],
    "wholesale": ["https://www.faire.com/category/Holiday%20Cards"],
}
CSV_FIELDS = ["brand_name", "brand_owner_name", "source_platforms", "discovery_source_url", "brand_claim",
              "official_website", "official_site_verification_status", "business_email", "email_evidence_url",
              "email_evidence_source_type", "history_status", "mx_status", "data_origin"]


def write_outputs(result: dict) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "source_checkpoints").mkdir(parents=True, exist_ok=True)
    candidates = result.get("candidates", [])
    (OUTPUT / "brand_candidates.json").write_text(json.dumps(candidates, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUTPUT / "brand_candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in candidates:
            row = {key:item.get(key, "") for key in CSV_FIELDS}
            row["source_platforms"] = ";".join(item.get("source_platforms", []))
            writer.writerow(row)


def main(argv=None) -> int:
    global OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("diagnostic", "live-public", "replay"), default="diagnostic")
    parser.add_argument("--import-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    OUTPUT = args.output_dir
    OUTPUT.mkdir(parents=True, exist_ok=True)
    diagnosis = diagnose_network()
    (OUTPUT / "network_diagnostic.json").write_text(json.dumps(diagnosis, indent=2), encoding="utf-8")
    if args.mode == "diagnostic":
        print(json.dumps(diagnosis, indent=2))
        return 0
    if args.mode == "live-public" and diagnosis["DEVELOPMENT_ENV_NETWORK_BLOCKED"]:
        result = {"candidates":[], "LIVE_CANARY_BLOCKED_BY_ENVIRONMENT":True,
                  "PROVIDER_PAGES_ATTEMPTED":0, "PROVIDER_PAGES_FETCHED":0,
                  "NETWORK_DIAGNOSTIC":diagnosis,
                  "metrics":{"RAW_BRANDS_DISCOVERED":0, "DEDUPED_UNIQUE_BRANDS":0,
                    "BRAND_OWNERS_CONFIRMED":0, "OFFICIAL_SITES_VERIFIED":0,
                    "FIRST_PARTY_EMAILS_FOUND":0, "B2B_EMAILS_FOUND":0,
                    "HISTORY_CLEAN_BRANDS_WITH_EMAIL":0, "NETWORK_FAILURES":0,
                    "ACCESS_RESTRICTED":0, "HTTP_429":0, "PARSE_EMPTY":0}}
        for source in SOURCE_PAGES:
            cp_path = OUTPUT / "source_checkpoints" / f"source_{source}.json"
            if not cp_path.exists():
                cp_path.write_text(json.dumps({"source_state":"PENDING", "last_attempt_at":"",
                    "last_success_at":"", "completed_urls":[], "retryable_urls":[],
                    "access_restricted_urls":[], "attempt_counts":{}, "url_states":{},
                    "attempt_history":[], "candidates":[]}, indent=2), encoding="utf-8")
        write_outputs(result)
        (OUTPUT / "canary_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    if args.mode == "replay":
        if not args.import_manifest:
            parser.error("--mode replay requires --import-manifest")
        fetcher = ImportedPageFetcher(args.import_manifest)
    else:
        fetcher = PublicPageFetcher()
    callbacks = make_runtime_callbacks()
    history_path = os.environ.get("BRAND_ACQUISITION_DEV_HISTORY_DB", "")
    history_approved = os.environ.get("BRAND_ACQUISITION_HISTORY_IS_DEVELOPMENT_COPY", "").lower() == "true"
    history_checker = HistoryChecker()
    if history_path and history_approved:
        resolved_history = Path(history_path).resolve()
        allowed_roots = [(ROOT / "output" / "brand_acquisition" / "dev_history").resolve(),
                         (ROOT / "data" / "development_history").resolve()]
        if not any(resolved_history == root or root in resolved_history.parents for root in allowed_roots):
            raise ValueError("history input must be an explicitly approved development copy under the documented development-only directories")
        history_checker = HistoryChecker(resolved_history, development_copy=True)
    pipeline = AcquisitionPipeline(OUTPUT, PipelineConfig(), history_check=history_checker, **callbacks)
    result = pipeline.run_sources(SOURCE_PAGES, fetcher_factory=lambda _source:fetcher)
    result["LIVE_CANARY_BLOCKED_BY_ENVIRONMENT"] = False if args.mode == "replay" else False
    result["DATA_MODE"] = "public_page_replay_discovery_only" if args.mode == "replay" else "live_public"
    result["HISTORY_SOURCE_AVAILABLE"] = bool(result.get("history_source_available"))
    result["NETWORK_DIAGNOSTIC"] = diagnosis
    write_outputs(result)
    (OUTPUT / "canary_manifest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result.get("metrics", {}), indent=2))
    print("Output:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
