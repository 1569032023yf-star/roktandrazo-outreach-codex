"""Integrity-checked, discovery-only replay of captured public pages."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .capture_manifest import validate_manifest
from .providers import PageResult, run_public_source


class CaptureImportFetcher:
    def __init__(self, records):
        self._records = {row["requested_url"]: row for row in records}

    def fetch(self, url: str) -> PageResult:
        row = self._records.get(url)
        if row is None:
            return PageResult(url, "permanent_unavailable", error="capture_not_in_manifest",
                              fetch_method="public_page_import:missing", data_origin="AUTHORIZED_PUBLIC_IMPORT")
        content = Path(row["_resolved_content_path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != row["content_sha256"]:
            return PageResult(url, "permanent_unavailable", error="capture_hash_mismatch",
                              fetch_method="public_page_import:integrity_error", data_origin="AUTHORIZED_PUBLIC_IMPORT")
        body = content.decode("utf-8", errors="replace")
        origin = row["data_origin"]
        # A manifest's LIVE_PUBLIC_CAPTURE assertion is not authenticated by its hash.
        # All imported material is conservatively downgraded to discovery-only import.
        if origin in {"LIVE_PUBLIC_CAPTURE", "AUTHORIZED_PUBLIC_IMPORT"}:
            origin = "AUTHORIZED_PUBLIC_IMPORT"
        return PageResult(url, "ok", body, final_url=row["final_url"], http_status=int(row["http_status"]),
            content_type=row["content_type"], fetched_at=row["captured_at"],
            fetch_method="public_page_import:" + row["capture_id"], capture_id=row["capture_id"],
            data_origin=origin)


def import_manifest(manifest_path: str | Path) -> tuple[dict, list]:
    manifest = validate_manifest(manifest_path)
    runs = []
    for platform in ("tiktok_shop", "amazon", "wholesale"):
        pages = [row for row in manifest["pages"] if row["source_platform"] == platform]
        if pages:
            fetcher = CaptureImportFetcher(pages)
            runs.append(run_public_source(platform, [row["requested_url"] for row in pages],
                                          fetcher=fetcher, max_pages=3))
    return manifest, runs
