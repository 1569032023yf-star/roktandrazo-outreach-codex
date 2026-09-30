"""One bounded copy-only reconstruction of Phase 4A.8M review candidates.

The detailed result stays in ignored output. It is not a recipient list.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bd_review_server as server
from review_evidence_workbench import recovery_classification
from scripts.phase4a8m_canary import make_copy

OUTPUT = ROOT / "output" / "phase4a8n_reconstructed_candidates.json"


def reconstruct(source: Path, copy: Path) -> dict:
    make_copy(source, copy)
    conn = sqlite3.connect(copy)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("copy_integrity_failed")
    try:
        rows = [dict(row) for row in conn.execute(
            "SELECT * FROM leads WHERE review_reason_code IS NOT NULL AND TRIM(review_reason_code)!='' "
            "AND COALESCE(review_status,'pending')='pending' ORDER BY id")]
        queue = {}
        for item in conn.execute("SELECT lead_id,facebook_url,facebook_source FROM fb_enrichment_queue"):
            if item[1] and item[0] not in queue:
                queue[item[0]] = (item[1], item[2] or "")
        candidates = []
        for lead in rows:
            recovery = recovery_classification(conn, lead)
            if recovery["value"] != "HIGH":
                continue
            url, source_label = queue.get(lead["id"], ("", ""))
            if not url:
                url, source_label = str(lead.get("facebook_url") or ""), "existing_lead"
            if url or lead.get("official_website"):
                rank = 0 if url and source_label == "official_website_link" else 1 if url else 2
                candidates.append((rank, lead["id"], bool(url)))
        candidates.sort(key=lambda item: (item[0], item[1]))
        selected = candidates[:40]
        known = {str(row[0]).lower() for row in conn.execute(
            "SELECT email FROM leads WHERE email IS NOT NULL AND TRIM(email)!=''")}
    finally:
        conn.close()

    server.DB_PATH = copy
    records = []
    for rank, lead_id, had_url in selected:
        started = json.loads(server.api_fetch_facebook_evidence({"lead_id": lead_id}))
        if not started.get("ok"):
            records.append({"lead_id": lead_id, "status": started.get("error") or "start_failed"})
            continue
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            with server._EVIDENCE_LOCK:
                state = dict(server._EVIDENCE_RESULTS.get(lead_id) or {})
            if state.get("job_status") != "running":
                break
            time.sleep(0.3)
        else:
            raise RuntimeError("bounded_review_job_timeout")
        evidence = json.loads(server.api_review_evidence(lead_id))
        fb = evidence.get("facebook_evidence") or {}
        lead_identity = evidence.get("lead_identity") or {}
        email = str(fb.get("public_email") or "").lower()
        records.append({
            "lead_id": lead_id, "store_name": lead_identity.get("store_name"),
            "had_existing_url": had_url, "status": fb.get("status"),
            "facebook_url": fb.get("facebook_page_url"),
            "facebook_candidates_found": fb.get("facebook_candidates_found", 0),
            "facebook_candidate_selected": fb.get("facebook_candidate_selected"),
            "facebook_discovery_source_url": fb.get("facebook_discovery_source_url"),
            "facebook_provenance_tier": fb.get("facebook_provenance_tier"),
            "social_email_class": fb.get("social_email_class"),
            "public_email": email, "visible_email_excerpt": fb.get("visible_email_excerpt"),
            "fetched_at": fb.get("fetched_at"), "new_relative_to_leads_email": bool(email and email not in known),
            "identity_match_signals": fb.get("identity_match_signals") or {},
            "safe_eligible_from_social": fb.get("safe_eligible_from_social", False),
        })
        if fb.get("status") in {"facebook_login_required", "facebook_captcha"}:
            break
    result = {"integrity_check":"ok", "selected": len(selected), "records": records,
              "ui_discovery_reproduced": sum(bool(r.get("status") == "opened" and
                   not r.get("had_existing_url") and r.get("facebook_candidates_found")) for r in records),
              "class_a_new_relative_to_leads_email": sum(bool(r.get("new_relative_to_leads_email") and
                   str(r.get("social_email_class") or "").startswith("CLASS_A")) for r in records),
              "production_db_writes": 0, "smtp_connections": 0}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--copy", type=Path, default=ROOT / "data" / "phase4a8n_copy.db")
    args = parser.parse_args()
    value = reconstruct(args.source, args.copy)
    print(json.dumps({key: item for key, item in value.items() if key != "records"}, ensure_ascii=False))
