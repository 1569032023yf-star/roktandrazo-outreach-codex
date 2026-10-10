"""Portable page-capture manifest with path, size, and integrity validation.

Hashes detect accidental changes. They do not authenticate the claimed source,
HTTP status, TLS, or capture method. Imported pages always remain discovery-only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PureWindowsPath
import re
from urllib.parse import urlsplit
import uuid

from .pipeline_types import DATA_ORIGINS

SCHEMA_VERSION = "1.0"
MAX_CAPTURE_BYTES = 2_000_000
SOURCE_PLATFORMS = frozenset({"tiktok_shop", "amazon", "wholesale"})


@dataclass(frozen=True)
class CaptureRecord:
    capture_id: str
    source_platform: str
    requested_url: str
    final_url: str
    captured_at: str
    capture_method: str
    http_status: int
    content_type: str
    content_sha256: str
    content_file: str
    page_category: str
    data_origin: str

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_url(value: str) -> str:
    parsed = urlsplit(str(value or ""))
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("capture URLs must be credential-free public HTTPS URLs")
    if parsed.port not in (None, 443):
        raise ValueError("capture URL port is not allowed")
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("local host URLs are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("non-public IP URLs are not allowed")
    return value


def _safe_content_path(root: Path, relative: str) -> Path:
    raw = str(relative or "")
    rel = Path(raw)
    win_rel = PureWindowsPath(raw)
    if ("\\" in raw or rel.is_absolute() or win_rel.is_absolute() or win_rel.drive
            or not rel.parts or any(part in {"..", ""} for part in rel.parts)
            or any(part == ".." for part in win_rel.parts)):
        raise ValueError("content_file must be a safe relative path")
    # Avoid pathlib.resolve on sandboxed Windows hosts (which can be denied even
    # for repository-local temporary files). Lexical containment plus a symlink
    # check on every component provides the required traversal protection.
    base = Path(os.path.abspath(root))
    target = base / rel
    if not target.is_relative_to(base):
        raise ValueError("content_file escapes the capture root")
    current = base
    for part in rel.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("symlink content paths are not allowed")
    if not target.is_file():
        raise ValueError("content_file must be a regular file")
    return target


def write_capture(root: str | Path, *, source_platform: str, requested_url: str,
                  final_url: str, captured_at: str, capture_method: str, http_status: int,
                  content_type: str, html: str | bytes, page_category: str,
                  data_origin: str = "LIVE_PUBLIC_CAPTURE") -> CaptureRecord:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if source_platform not in SOURCE_PLATFORMS:
        raise ValueError("unsupported source_platform")
    _validate_url(requested_url)
    _validate_url(final_url)
    if data_origin not in DATA_ORIGINS:
        raise ValueError("unsupported data_origin")
    if not capture_method or not page_category:
        raise ValueError("capture_method and page_category are required")
    try:
        parsed_time = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
            raise ValueError
    except (AttributeError, ValueError):
        raise ValueError("captured_at must be timezone-aware ISO-8601") from None
    body = html.encode("utf-8") if isinstance(html, str) else bytes(html)
    if not body or len(body) > MAX_CAPTURE_BYTES:
        raise ValueError("capture body must be non-empty and within the size limit")
    digest = hashlib.sha256(body).hexdigest()
    capture_id = uuid.uuid4().hex
    rel = Path("pages") / f"{capture_id}.html"
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return CaptureRecord(capture_id, source_platform, requested_url, final_url, captured_at,
        capture_method, int(http_status), str(content_type or ""), digest,
        rel.as_posix(), str(page_category), data_origin)


def write_manifest(root: str | Path, records: list[CaptureRecord]) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "capture_manifest.json"
    payload = {"schema_version": SCHEMA_VERSION, "scope": "discovery_only",
        "pages": [record.to_dict() for record in records]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_manifest(manifest_path: str | Path) -> dict:
    path = Path(os.path.abspath(manifest_path))
    if path.is_symlink():
        raise ValueError("manifest symlinks are not allowed")
    root = path.parent
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"manifest is unreadable: {type(exc).__name__}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION or payload.get("scope") != "discovery_only":
        raise ValueError("unsupported manifest schema or scope")
    pages = payload.get("pages")
    if not isinstance(pages, list):
        raise ValueError("manifest pages must be a list")
    validated = []
    seen_ids = set()
    for row in pages:
        if not isinstance(row, dict):
            raise ValueError("each capture record must be an object")
        required = ("capture_id", "source_platform", "requested_url", "final_url", "captured_at",
            "capture_method", "http_status", "content_type", "content_sha256", "content_file", "page_category", "data_origin")
        if any(not row.get(key) for key in required):
            raise ValueError("capture record has missing required metadata")
        if row["capture_id"] in seen_ids or not re.fullmatch(r"[a-f0-9]{32}", str(row["capture_id"])):
            raise ValueError("capture_id must be unique lowercase hex")
        seen_ids.add(row["capture_id"])
        if row["source_platform"] not in SOURCE_PLATFORMS or row["data_origin"] not in DATA_ORIGINS:
            raise ValueError("unsupported source_platform or data_origin")
        _validate_url(row["requested_url"])
        _validate_url(row["final_url"])
        try:
            dt = datetime.fromisoformat(str(row["captured_at"]).replace("Z", "+00:00"))
            if dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError
            status = int(row["http_status"])
        except (ValueError, TypeError):
            raise ValueError("invalid timestamp or HTTP status") from None
        if not 100 <= status <= 599:
            raise ValueError("HTTP status is outside valid range")
        body_path = _safe_content_path(root, row["content_file"])
        body = body_path.read_bytes()
        if not body or len(body) > MAX_CAPTURE_BYTES:
            raise ValueError("captured content is empty or exceeds the size limit")
        if not re.fullmatch(r"[a-f0-9]{64}", str(row["content_sha256"])):
            raise ValueError("content_sha256 format is invalid")
        digest = hashlib.sha256(body).hexdigest()
        if digest != row["content_sha256"]:
            raise ValueError("content_sha256 mismatch")
        validated.append({**row, "_resolved_content_path": str(body_path),
                          "_import_trust": "discovery_only_unverified_source",
                          "_live_capture_claim": row["data_origin"] == "LIVE_PUBLIC_CAPTURE"})
    return {"schema_version": SCHEMA_VERSION, "scope": "discovery_only", "pages": validated,
            "pages_validated": len(validated),
            "source_authenticity_verified": False,
            "note": "SHA-256 verifies file integrity only; manifest claims do not establish source authenticity or TLS."}
