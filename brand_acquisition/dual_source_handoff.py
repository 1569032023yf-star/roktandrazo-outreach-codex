"""Offline discovery handoff; observations never confer qualification or ownership."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from datetime import datetime
from urllib.parse import urlsplit

from .history import HistoryChecker
from .models import BrandCandidate

SCHEMA = "dual-source-discovery/v1"


def _text(value, field, maximum=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"invalid {field}")
    return value.strip()


def _url(value):
    value = _text(value, "URL")
    parsed = urlsplit(value)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise ValueError("invalid public URL")
    if host.lower() == "localhost" or host.lower().endswith((".local", ".localhost")):
        raise ValueError("local URL")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise ValueError("non-public hostname")
    else:
        if not addr.is_global:
            raise ValueError("non-public IP")
    return value


def _stamp(value):
    value = _text(value, "captured_at", 64)
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("captured_at requires timezone")
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def normalize_observation(raw):
    """Allowlist fields; ignore imported SAFE/live/history/ownership assertions."""
    if not isinstance(raw, dict):
        raise ValueError("observation must be an object")
    source = raw.get("source")
    if source not in {"google", "osm"}:
        raise ValueError("source must be google or osm")
    location = raw.get("location")
    if not isinstance(location, dict) or not location:
        raise ValueError("location evidence required")
    allowed = {"address", "city", "state", "country", "latitude", "longitude"}
    if set(location) - allowed:
        raise ValueError("unknown location fields")
    clean_location = {}
    for key, value in location.items():
        if key in {"latitude", "longitude"}:
            limit = 90 if key == "latitude" else 180
            if type(value) not in {float, int} or not -limit <= value <= limit:
                raise ValueError("invalid coordinate")
            clean_location[key] = value
        else:
            clean_location[key] = _text(value, key)
    package_hash = _text(raw.get("package_sha256"), "package_sha256", 64).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", package_hash):
        raise ValueError("invalid package hash")
    evidence = raw.get("email_evidence", [])
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise ValueError("invalid email evidence")
    emails = []
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("invalid email evidence")
        email = _text(item.get("email"), "email", 320)
        excerpt = _text(item.get("excerpt"), "excerpt")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or email.casefold() not in excerpt.casefold():
            raise ValueError("email evidence mismatch")
        emails.append({"email": email, "source_url": _url(item.get("source_url")),
                       "excerpt": excerpt, "captured_at": _stamp(item.get("captured_at"))})
    return {"source": source, "provider_id": _text(raw.get("provider_id"), "provider_id", 512),
            "source_url": _url(raw.get("source_url")), "captured_at": _stamp(raw.get("captured_at")),
            "name": _text(raw.get("name"), "name", 512), "location": clean_location,
            "site_candidate": _url(raw["site_candidate"]) if raw.get("site_candidate") else "",
            "email_evidence": emails, "package_sha256": package_hash}


def export_observations(observations):
    """Return JSON-safe candidates without IO, DB paths, network or SAFE rules.

    Only identical source/provider identities group; all distinct observations
    survive. Website-domain matches merely annotate potential duplicates.
    """
    if not isinstance(observations, list) or len(observations) > 10000:
        raise ValueError("expected bounded observation list")
    grouped = {}
    for raw in observations:
        item = normalize_observation(raw)
        key = (item["source"], item["provider_id"])
        grouped.setdefault(key, {})[_canonical(item)] = item
    result = []
    for (source, provider_id), captures in sorted(grouped.items()):
        evidence = [captures[key] for key in sorted(captures)]
        first = evidence[0]
        identifier = hashlib.sha256(_canonical([source, provider_id]).encode()).hexdigest()
        candidate = BrandCandidate(brand_name=first["name"], source_platforms=[source],
                                   source_urls=sorted({x["source_url"] for x in evidence}),
                                   discovery_source_url=first["source_url"],
                                   source_acquisition_method="offline_import",
                                   data_origin="discovery_only", data_origin_label="DISCOVERY_ONLY",
                                   fixture_status="UNVERIFIED_IMPORT")
        candidate.source_capture_ids = [hashlib.sha256(_canonical(x).encode()).hexdigest() for x in evidence]
        candidate.official_site_candidates = [{"url": url, "status": "unverified"}
                                               for url in sorted({x["site_candidate"] for x in evidence if x["site_candidate"]})]
        candidate.history_status = HistoryChecker()(candidate.to_dict())
        candidate.stage_statuses = {"qualification": {"status": "pending", "reason": "existing_pipeline_required"}}
        result.append({"candidate_id": identifier, "candidate": candidate.to_dict(),
                       "qualification": "PENDING", "safe": False, "observations": evidence,
                       "dedupe_basis": {"source": source, "provider_id": provider_id},
                       "potential_duplicates": []})
    domains = {}
    for row in result:
        for observation in row["observations"]:
            if observation["site_candidate"]:
                host = urlsplit(observation["site_candidate"]).hostname.lower().removeprefix("www.")
                domains.setdefault(host, set()).add(row["candidate_id"])
    for row in result:
        peers = set()
        for ids in domains.values():
            if row["candidate_id"] in ids:
                peers.update(ids - {row["candidate_id"]})
        row["potential_duplicates"] = sorted(peers)
    return {"schema": SCHEMA, "provenance": "UNVERIFIED_IMPORT", "candidates": result}


def validate_handoff(payload):
    """Reject promoted/tampered derived fields by rebuilding from observations.

    This validates structure and conservative semantics, never source truth.
    """
    try:
        observations = [item for row in payload["candidates"] for item in row["observations"]]
        rebuilt = export_observations(observations)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("invalid handoff") from exc
    if payload != rebuilt:
        raise ValueError("handoff differs from conservative reconstruction")
    return True
