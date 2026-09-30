"""Read-only, per-candidate Phase 4A.8N gate audit on a development DB copy."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from broad_ready import _load_db_signals
from campaign_eligible import review_campaign_eligible
from campaign_eligible_v2 import review_campaign_eligible_v2
from email_hygiene import hygiene_check
from history_crosscheck import cross_check, host, normalize_email
from preflight_gate import query_mx

PRIVATE_OUTPUT = ROOT / "output" / "phase4a8n_private_gate_audit.json"
SANITIZED_OUTPUT = ROOT / "handoff" / "phases" / "PHASE4A8N_CLASS_A_GATE_AUDIT.json"


def _table(conn, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _count(conn, sql: str, args: tuple = ()) -> int:
    return int(conn.execute(sql, args).fetchone()[0])


def audit_one(conn, record: dict, mx_lookup) -> dict:
    lead_id = int(record["lead_id"])
    original = dict(conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())
    email = normalize_email(record.get("public_email") or "")
    domain = email.rsplit("@", 1)[-1] if email else ""
    fb_url = str(record.get("facebook_url") or "")
    excerpt = str(record.get("visible_email_excerpt") or "")
    tier = str(record.get("facebook_provenance_tier") or "")
    fetched = str(record.get("fetched_at") or "")
    identity = bool(tier.startswith("TIER_A") and (record.get("identity_match_signals") or {}).get("official_site_direct_link")
                    and any(bool(value) for key, value in (record.get("identity_match_signals") or {}).items()
                            if key != "official_site_direct_link"))
    visible = bool(email and email in excerpt.lower())
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(fetched.replace("Z", "+00:00"))
        fresh = 0 <= age.total_seconds() <= 90 * 86400
    except (ValueError, TypeError):
        fresh = False
    hygiene = hygiene_check(email)
    org = str(original.get("organization_key") or "")
    domain_hash = str(original.get("domain_hash") or "")
    signals = _load_db_signals(conn, email, org, domain_hash, lead_id)
    history = cross_check(conn, {**original, "email": email}, exclude_lead_id=lead_id)
    sent_log_any = _count(conn, "SELECT COUNT(*) FROM send_log WHERE lower(email)=?", (email,)) if _table(conn,"send_log") else None
    email_in_leads = _count(conn, "SELECT COUNT(*) FROM leads WHERE lower(email)=? AND id!=?", (email, lead_id))
    org_safe_elsewhere = _count(conn, "SELECT COUNT(*) FROM leads WHERE organization_key=? AND id!=? "
                                "AND (COALESCE(auto_sendable,0)=1 OR status='sent')", (org, lead_id)) if org else None
    suppressed = bool(signals["suppressed"] or original.get("unsubscribed_at") or original.get("do_not_contact"))
    bounce = bool(signals["hard_bounced"] or original.get("bounced_at") or original.get("delivery_issue"))
    history_clean = not any((signals["sent_email"], signals["sent_org"], signals["shared_domain_sent"],
                             signals["negative_reply"], history["previously_sent"], history["replied"],
                             original.get("sent_at"), original.get("organization_first_outreach_sent_at"),
                             original.get("history_status") in {"duplicate","exact_duplicate"}))
    unique_org = bool(org and not org_safe_elsewhere and history_clean)
    mx_status, mx_at = mx_lookup(domain) if domain else ("dns_error", None)
    if mx_status not in {"ok","nxdomain","null_mx","no_mail_route","dns_error"}:
        mx_status = "dns_error"
    view = dict(original)
    view.update({"email":email, "email_source_type":"official_site_linked_facebook",
                 "email_verified_on_official_site":0, "evidence_url":fb_url,
                 "evidence_snippet":excerpt, "evidence_checked_at":fetched})
    v1 = review_campaign_eligible(view, {"conn":conn})
    v2 = review_campaign_eligible_v2(view, {"conn":conn, "mx_lookup":{domain:mx_status}})
    independent = all((history_clean, not suppressed, not bounce, hygiene.get("valid"),
                       mx_status == "ok", unique_org, identity, visible, fresh))
    # Even if legacy V1 recognizes a same-domain email via a fallback, that
    # does not authorize a new social provenance type or make this SAFE.
    policy_only = bool(independent and not v1.get("eligible") and not v2.get("eligible") and
                       all("evidence" in b or "source" in b for b in
                           set(v1.get("blockers") or []) | set(v2.get("blockers") or [])))
    if suppressed or bounce:
        bucket = "D_SUPPRESSION_OR_BOUNCE_BLOCKED"
    elif not history_clean or not unique_org:
        bucket = "B_HISTORY_BLOCKED"
    elif mx_status in {"nxdomain","null_mx","no_mail_route"}:
        bucket = "C_MX_BLOCKED"
    elif not identity or not visible or not fresh:
        bucket = "E_IDENTITY_OR_EVIDENCE_BLOCKED"
    elif policy_only:
        bucket = "A_POLICY_ONLY_BLOCKED"
    else:
        bucket = "F_OTHER_BLOCKED"
    return {
        "lead_id":lead_id, "store_name":original.get("store_name"), "email":email,
        "organization_key":org,
        "normalized_domain":host(original.get("official_website") or ""),
        "NEW_EMAIL_STRING":not bool(email_in_leads),
        "NEW_ORGANIZATION":bool(org and not signals["sent_org"] and not signals["shared_domain_sent"]),
        "HISTORY_CLEAN_ORGANIZATION":history_clean,
        "EMAIL_PREVIOUSLY_SENT":bool(signals["sent_email"]),
        "ORGANIZATION_PREVIOUSLY_SENT":bool(signals["sent_org"]),
        "SHARED_DOMAIN_ORG_HISTORY":bool(signals["shared_domain_sent"]),
        "EMAIL_ALREADY_IN_LEADS":bool(email_in_leads),
        "EMAIL_ALREADY_IN_SEND_LOG":bool(sent_log_any) if sent_log_any is not None else "NOT_AVAILABLE",
        "SUPPRESSED":bool(signals["suppressed"]), "UNSUBSCRIBED":bool(original.get("unsubscribed_at")),
        "DO_NOT_CONTACT":bool(original.get("do_not_contact")),
        "HARD_BOUNCED":bool(signals["hard_bounced"]), "DELIVERY_ISSUE":bool(original.get("delivery_issue")),
        "DUPLICATE_ORGANIZATION":bool(org_safe_elsewhere) if org_safe_elsewhere is not None else "NOT_AVAILABLE",
        "NEGATIVE_REPLY_OR_STOP_SIGNAL":bool(signals["negative_reply"]),
        "HISTORY_CROSSCHECK_RESULT":history["result"], "HISTORY_CLEAN":history_clean,
        "SUPPRESSION_CLEAN":not suppressed, "BOUNCE_CLEAN":not bounce,
        "EMAIL_HYGIENE_PASS":bool(hygiene.get("valid")), "EMAIL_HYGIENE_REASON":hygiene.get("reason"),
        "MX_STATUS":mx_status.upper(), "MX_CHECKED_AT":mx_at, "MX_PASS":mx_status=="ok",
        "UNIQUE_ORG":unique_org, "IDENTITY_STRONG":identity, "FRESH_PUBLIC_EVIDENCE":fresh,
        "LITERAL_VISIBLE_EMAIL":visible,
        "CURRENT_V1_RESULT":bool(v1.get("eligible")), "CURRENT_V1_BLOCKERS":v1.get("blockers"),
        "CURRENT_V2_RESULT":bool(v2.get("eligible")), "CURRENT_V2_BLOCKERS":v2.get("blockers"),
        "CLASS_A_READY_EXCEPT_POLICY":policy_only, "BUCKET":bucket,
        "SAFE_ELIGIBLE_FROM_SOCIAL":False,
    }


def audit(copy: Path, reconstructed: Path) -> dict:
    payload = json.loads(reconstructed.read_text(encoding="utf-8"))
    records = [r for r in payload["records"] if r.get("new_relative_to_leads_email") and
               str(r.get("social_email_class") or "").startswith("CLASS_A")]
    conn = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("copy_integrity_failed")
    mx_cache = {}
    def lookup(domain):
        if domain not in mx_cache:
            mx_cache[domain] = query_mx(domain)
        return mx_cache[domain]
    try:
        audited = [audit_one(conn, r, lookup) for r in records]
    finally:
        conn.close()
    private = {"candidates":audited, "source_reconstructed":len(records),
               "ui_discovery_reproduced":payload.get("ui_discovery_reproduced",0)}
    PRIVATE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PRIVATE_OUTPUT.write_text(json.dumps(private, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")
    sanitized = []
    for ordinal, item in enumerate(audited, 1):
        sanitized.append({"candidate_ref": f"CLASS_A_{ordinal:02d}", **{
            key:value for key,value in item.items() if key not in
            {"lead_id","email","store_name","organization_key","normalized_domain"}}})
    bucket_counts = {name:sum(1 for row in audited if row["BUCKET"] == name) for name in (
        "A_POLICY_ONLY_BLOCKED","B_HISTORY_BLOCKED","C_MX_BLOCKED",
        "D_SUPPRESSION_OR_BOUNCE_BLOCKED","E_IDENTITY_OR_EVIDENCE_BLOCKED","F_OTHER_BLOCKED")}
    result = {"PHASE":"4A.8N / 七候选资格审计 / Seven-candidate gate audit",
              "SOURCE_SCOPE":"Read-only-derived production DB copy; no production writes. / 生产数据库只读来源副本；无生产写入。",
              "CLASS_A_CANDIDATES_RECONSTRUCTED":len(audited),
              "POLICY_ONLY_BLOCKED":bucket_counts["A_POLICY_ONLY_BLOCKED"],
              "HISTORY_BLOCKED":bucket_counts["B_HISTORY_BLOCKED"],
              "MX_BLOCKED":bucket_counts["C_MX_BLOCKED"],
              "SUPPRESSION_OR_BOUNCE_BLOCKED":bucket_counts["D_SUPPRESSION_OR_BOUNCE_BLOCKED"],
              "IDENTITY_OR_EVIDENCE_BLOCKED":bucket_counts["E_IDENTITY_OR_EVIDENCE_BLOCKED"],
              "OTHER_BLOCKED":bucket_counts["F_OTHER_BLOCKED"],
              "HISTORY_CLEAN":sum(bool(r["HISTORY_CLEAN"]) for r in audited),
              "MX_PASS":sum(bool(r["MX_PASS"]) for r in audited),
              "UNIQUE_ORG":sum(bool(r["UNIQUE_ORG"]) for r in audited),
              "CLASS_A_READY_EXCEPT_POLICY":sum(bool(r["CLASS_A_READY_EXCEPT_POLICY"]) for r in audited),
              "CURRENT_V1_PASS":sum(bool(r["CURRENT_V1_RESULT"]) for r in audited),
              "CURRENT_V2_PASS":sum(bool(r["CURRENT_V2_RESULT"]) for r in audited),
              "CANDIDATES":sanitized, "PRODUCTION_DB_WRITES":0, "SMTP_CONNECTIONS":0}
    SANITIZED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SANITIZED_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--copy", type=Path, required=True)
    parser.add_argument("--reconstructed", type=Path, default=ROOT / "output" / "phase4a8n_reconstructed_candidates.json")
    args=parser.parse_args()
    result=audit(args.copy,args.reconstructed)
    print(json.dumps({k:v for k,v in result.items() if k!="CANDIDATES"},ensure_ascii=False,default=str))
