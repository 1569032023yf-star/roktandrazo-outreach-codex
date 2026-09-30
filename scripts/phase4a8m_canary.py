"""Phase 4A.8M bounded canary on a read-only-derived production SQLite copy.

Only aggregate counts are written to output; no merchant email or session data.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from review_evidence_workbench import (
    ROOT, recovery_classification, render_facebook_page, verify_recovered_website,
    discover_official_facebook_candidates,
)

MAX_REAL_MERCHANTS = 40
OUTPUT = ROOT / "output" / "phase4a8m_manual_review_facebook_canary.json"


def make_copy(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if not destination.is_relative_to(ROOT) or source == destination:
        raise ValueError("copy_must_be_inside_development_root")
    if destination.exists():
        raise FileExistsError("fresh_copy_required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    uri = "file:" + quote(str(source).replace("\\", "/"), safe="/:") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as readonly:
        readonly.execute("PRAGMA query_only=ON")
        with sqlite3.connect(destination) as target:
            readonly.backup(target)
            check = target.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise RuntimeError("copy_integrity_check_failed:" + str(check))


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def measure(copy: Path, network: bool, limit: int) -> dict:
    if not 1 <= limit <= MAX_REAL_MERCHANTS:
        raise ValueError("maximum_40")
    conn = sqlite3.connect(copy)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("copy_integrity_check_failed")
        rows = [dict(row) for row in conn.execute(
            "SELECT * FROM leads WHERE review_reason_code IS NOT NULL AND TRIM(review_reason_code)!='' "
            "AND COALESCE(review_status,'pending')='pending' ORDER BY id"
        )]
        counts = {
            "BASELINE_COMMIT": "41bcb4f4bab35c490e48c6c2460b7c6e8af450dd",
            "INTEGRITY_CHECK": "ok",
            "MANUAL_REVIEW_TOTAL": len(rows), "HISTORY_BLOCKED_EXCLUDED": 0,
            "RECOVERABLE_MANUAL_REVIEW": 0, "CANARY_SELECTED": 0,
            "FB_PAGES_ATTEMPTED": 0, "FB_PAGES_OPENED": 0,
            "FB_LOGIN_REQUIRED": 0, "FB_CAPTCHA": 0, "FB_PAGE_NOT_FOUND": 0,
            "FB_OTHER_ERRORS": 0, "OFFICIAL_SITE_LINKED_FB_PAGES": 0,
            "OFFICIAL_SITES_SCANNED_FOR_FB": 0,
            "STRONG_MATCH_FB_PAGES": 0, "FB_PUBLIC_EMAILS_FOUND": 0,
            "FB_NEW_EMAILS_NOT_IN_DB": 0, "CLASS_A_EMAILS_FOUND": 0,
            "CLASS_B_EMAILS_FOUND": 0, "CLASS_C_EMAILS_FOUND": 0,
            "FB_WEBSITE_RECOVERED": 0, "FB_WEBSITE_VERIFIED": 0,
            "FB_TO_OFFICIAL_SITE_EMAIL_FOUND": 0, "NEW_UNIQUE_ORGS_WITH_EMAIL": 0,
            "FB_NEW_EMAILS_NOT_IN_DB_SCOPE": "leads.email only; other history tables require reviewer gate",
            "NEW_UNIQUE_ORGS_WITH_EMAIL_SCOPE": "potential opportunity, not V1/V2/MX cleared",
            "NETWORK_RUN": network, "MAX_REAL_MERCHANTS": limit,
        }
        queue = {}
        if _table_exists(conn, "fb_enrichment_queue"):
            for item in conn.execute("SELECT lead_id,facebook_url,facebook_source FROM fb_enrichment_queue"):
                if item[1] and item[0] not in queue:
                    queue[item[0]] = (item[1], item[2] or "")
        candidates = []
        for lead in rows:
            recovery = recovery_classification(conn, lead)
            if recovery["value"] == "NONE":
                counts["HISTORY_BLOCKED_EXCLUDED"] += 1
                continue
            counts["RECOVERABLE_MANUAL_REVIEW"] += 1
            if recovery["value"] != "HIGH":
                continue
            url, source = queue.get(lead["id"], ("", ""))
            if not url:
                url = str(lead.get("facebook_url") or "")
                source = "existing_lead"
            if url or lead.get("official_website"):
                candidates.append((0 if url and source == "official_website_link" else
                                   1 if url else 2, lead, url))
        candidates.sort(key=lambda item: (item[0], item[1]["id"]))
        chosen = candidates[:limit]
        counts["CANARY_SELECTED"] = len(chosen)
        counts["HIGH_RECOVERABLE_WITH_EXISTING_FB_URL"] = sum(bool(url) for _, _, url in candidates)
        counts["HIGH_CANDIDATES_WITH_WEBSITE_OR_FB"] = len(candidates)
        if network:
            known_emails = {str(row[0]).lower() for row in conn.execute(
                "SELECT email FROM leads WHERE email IS NOT NULL AND TRIM(email)!=''"
            )}
            new_orgs = set()
            for _rank, lead, url in chosen:
                proved_link = None
                if not url and lead.get("official_website"):
                    counts["OFFICIAL_SITES_SCANNED_FOR_FB"] += 1
                    try:
                        url = discover_official_facebook_candidates(lead)["selected"]
                        proved_link = True if url else None
                    except Exception:
                        url = ""
                if not url:
                    continue
                counts["FB_PAGES_ATTEMPTED"] += 1
                result = render_facebook_page(lead, url, official_linked=proved_link)
                status = result.get("status")
                if status != "opened":
                    key = {
                        "facebook_login_required": "FB_LOGIN_REQUIRED",
                        "facebook_captcha": "FB_CAPTCHA",
                        "facebook_page_not_found": "FB_PAGE_NOT_FOUND",
                    }.get(status, "FB_OTHER_ERRORS")
                    counts[key] += 1
                    if status in {"facebook_login_required", "facebook_captcha"}:
                        break
                    continue
                counts["FB_PAGES_OPENED"] += 1
                tier = result.get("facebook_provenance_tier") or ""
                if tier.startswith("TIER_A"):
                    counts["OFFICIAL_SITE_LINKED_FB_PAGES"] += 1
                if tier.startswith("TIER_B"):
                    counts["STRONG_MATCH_FB_PAGES"] += 1
                email = (result.get("public_email") or "").lower()
                email_class = result.get("social_email_class") or ""
                if email:
                    counts["FB_PUBLIC_EMAILS_FOUND"] += 1
                    for label, key in (
                        ("CLASS_A", "CLASS_A_EMAILS_FOUND"),
                        ("CLASS_B", "CLASS_B_EMAILS_FOUND"),
                        ("CLASS_C", "CLASS_C_EMAILS_FOUND"),
                    ):
                        if email_class.startswith(label):
                            counts[key] += 1
                    if email not in known_emails and (email_class.startswith("CLASS_A") or email_class.startswith("CLASS_B")):
                        counts["FB_NEW_EMAILS_NOT_IN_DB"] += 1
                        new_orgs.add(str(lead.get("organization_key") or lead["id"]))
                website = result.get("public_website") or ""
                if website and not lead.get("official_website") and not tier.startswith("TIER_C"):
                    counts["FB_WEBSITE_RECOVERED"] += 1
                    verified = verify_recovered_website(lead, website)
                    if verified.get("verified"):
                        counts["FB_WEBSITE_VERIFIED"] += 1
                        if verified.get("facebook_to_official_site_email_found"):
                            counts["FB_TO_OFFICIAL_SITE_EMAIL_FOUND"] += 1
                            found = str((verified.get("first_party_email_evidence") or {}).get("email") or "").lower()
                            if found and found not in known_emails:
                                new_orgs.add(str(lead.get("organization_key") or lead["id"]))
            counts["NEW_UNIQUE_ORGS_WITH_EMAIL"] = len(new_orgs)
        novel = counts["FB_NEW_EMAILS_NOT_IN_DB"] + counts["FB_TO_OFFICIAL_SITE_EMAIL_FOUND"]
        orgs = counts["NEW_UNIQUE_ORGS_WITH_EMAIL"]
        yield_value = "HIGH_YIELD" if novel >= 4 or orgs >= 3 else (
            "MEDIUM_YIELD" if 1 <= novel <= 3 else "LOW_YIELD")
        counts["FACEBOOK_YIELD_RESULT"] = yield_value if network else "NOT_RUN"
        counts["FACEBOOK_PREFETCH_RECOMMENDED"] = network and yield_value in {"HIGH_YIELD", "MEDIUM_YIELD"}
        counts["MANUAL_ON_DEMAND_FACEBOOK_RECOMMENDED"] = network and yield_value == "LOW_YIELD"
        counts["GENERATED_AT"] = datetime.now(timezone.utc).isoformat()
        counts["PRODUCTION_DB_WRITES"] = 0
        counts["SMTP_CONNECTIONS"] = 0
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return counts
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--copy", type=Path, default=ROOT / "data" / "phase4a8m_canary_copy.db")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    make_copy(args.source, args.copy)
    result = measure(args.copy, args.network, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
