"""Copy-only seven-candidate re-audit and conservative inventory drift replay."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import broad_ready
import campaign_eligible
import campaign_eligible_v2
from scripts.phase4a8m_canary import make_copy
from scripts.phase4a8n_gate_audit import audit_one

REPORT = ROOT / "handoff" / "phases" / "PHASE4A8O_SEVEN_CANDIDATE_REAUDIT.json"


def seven(copy: Path, reconstructed: Path, prior: Path) -> dict:
    records = [r for r in json.loads(reconstructed.read_text(encoding="utf-8"))["records"]
               if r.get("new_relative_to_leads_email") and
               str(r.get("social_email_class") or "").startswith("CLASS_A")]
    old = json.loads(prior.read_text(encoding="utf-8"))["candidates"]
    if len(records) != 7 or len(old) != 7:
        raise RuntimeError("expected_same_seven_candidates")
    mx_by_id = {int(row["lead_id"]): (str(row["MX_STATUS"]).lower(), row.get("MX_CHECKED_AT")) for row in old}
    conn = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("seven_copy_integrity_failed")
        updated = [audit_one(conn, row, lambda _domain, ident=row["lead_id"]: mx_by_id[int(ident)])
                   for row in records]
    finally:
        conn.close()
    safe = []
    for index, (before, after) in enumerate(zip(old, updated), 1):
        if int(before["lead_id"]) != int(after["lead_id"]):
            raise RuntimeError("candidate_identity_order_changed")
        previous_form = any("contact_form_only" in b for b in before["CURRENT_V1_BLOCKERS"])
        current_form = any("contact_form_only" in b for b in after["CURRENT_V1_BLOCKERS"])
        third_party = any("third_party_email" in b for b in after["CURRENT_V1_BLOCKERS"])
        policy = "evidence_source_not_approved" in after["CURRENT_V1_BLOCKERS"]
        remaining = set(after["CURRENT_V1_BLOCKERS"] + after["CURRENT_V2_BLOCKERS"])
        policy_only = bool(policy and remaining == {"evidence_source_not_approved"} and
                           all(after[key] for key in ("HISTORY_CLEAN", "SUPPRESSION_CLEAN", "BOUNCE_CLEAN",
                               "EMAIL_HYGIENE_PASS", "MX_PASS", "UNIQUE_ORG", "IDENTITY_STRONG",
                               "FRESH_PUBLIC_EVIDENCE", "LITERAL_VISIBLE_EMAIL")))
        bucket = ("C_THIRD_PARTY_DOMAIN_BLOCKED" if third_party else
                  "A_POLICY_ONLY_BLOCKED" if policy_only else "H_OTHER_BLOCKED")
        safe.append({"candidate_ref": f"CLASS_A_{index:02d}",
                     "CONTACT_FORM_ONLY_BEFORE": previous_form,
                     "CONTACT_FORM_ONLY_AFTER": current_form,
                     "CONTACT_FORM_STALE_FIXED": previous_form and not current_form,
                     "THIRD_PARTY_DOMAIN_BLOCKED": third_party,
                     "SOURCE_POLICY_BLOCKED": policy,
                     "HISTORY_CLEAN": after["HISTORY_CLEAN"], "MX_PASS": after["MX_PASS"],
                     "UNIQUE_ORG": after["UNIQUE_ORG"],
                     "CURRENT_V1_RESULT": after["CURRENT_V1_RESULT"],
                     "CURRENT_V2_RESULT": after["CURRENT_V2_RESULT"],
                     "CURRENT_V1_BLOCKERS": after["CURRENT_V1_BLOCKERS"],
                     "CURRENT_V2_BLOCKERS": after["CURRENT_V2_BLOCKERS"],
                     "CLASS_A_READY_EXCEPT_POLICY": policy_only,
                     "FINAL_BUCKET": bucket,
                     "SAFE_ELIGIBLE_FROM_SOCIAL": False})
    return {"CLASS_A_CANDIDATES_REAUDITED": len(safe),
            "HISTORY_CLEAN": sum(r["HISTORY_CLEAN"] for r in safe),
            "MX_PASS": sum(r["MX_PASS"] for r in safe),
            "UNIQUE_ORG": sum(r["UNIQUE_ORG"] for r in safe),
            "CONTACT_FORM_ONLY_BEFORE": sum(r["CONTACT_FORM_ONLY_BEFORE"] for r in safe),
            "CONTACT_FORM_ONLY_AFTER": sum(r["CONTACT_FORM_ONLY_AFTER"] for r in safe),
            "CONTACT_FORM_STALE_BLOCKS_REMOVED": sum(r["CONTACT_FORM_STALE_FIXED"] for r in safe),
            "THIRD_PARTY_DOMAIN_BLOCKED": sum(r["THIRD_PARTY_DOMAIN_BLOCKED"] for r in safe),
            "SOURCE_POLICY_BLOCKED": sum(r["SOURCE_POLICY_BLOCKED"] for r in safe),
            "OTHER_BLOCKED": sum(r["FINAL_BUCKET"] == "H_OTHER_BLOCKED" for r in safe),
            "CLASS_A_READY_EXCEPT_POLICY": sum(r["CLASS_A_READY_EXCEPT_POLICY"] for r in safe),
            "CURRENT_V1_PASS": sum(r["CURRENT_V1_RESULT"] for r in safe),
            "CURRENT_V2_PASS": sum(r["CURRENT_V2_RESULT"] for r in safe),
            "CANDIDATES": safe}


def drift(copy: Path) -> dict:
    conn = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("fresh_copy_integrity_failed")
        rows = [dict(r) for r in conn.execute("SELECT * FROM leads WHERE email IS NOT NULL AND TRIM(email)!=''")]
        cache = {}
        for row in conn.execute("SELECT key,value FROM system_config WHERE key LIKE 'mx_cache_%'"):
            try:
                from campaign_eligible_v2 import _parse_ts, ASIA_SH
                from datetime import datetime
                value = json.loads(row["value"])
                checked = _parse_ts(value.get("checked_at") or value.get("cached_at"))
                if checked and (datetime.now(ASIA_SH) - checked).total_seconds() <= 24 * 3600:
                    cache[row["key"][len("mx_cache_"):]] = value["status"]
            except (KeyError, ValueError, TypeError):
                pass
        domains = {r["email"].rsplit("@", 1)[-1].lower() for r in rows if "@" in r["email"]}
        mx_lookup = {domain: cache.get(domain, "dns_error") for domain in domains}
        original_form = broad_ready._is_contact_form_only
        original_source = campaign_eligible._source_policy_blocked
        blocked_statuses = {"sent", "bounced", "do_not_contact", "rejected", "failed",
                            "delivery_issue", "bounce_review"}
        def evaluate(old: bool, mx_values: dict[str, str]):
            if old:
                broad_ready._is_contact_form_only = lambda lead: bool(
                    lead.get("status") == "contact_form_pool" or lead.get("contact_form_only") or
                    (lead.get("contact_form_url") and not str(lead.get("email") or "").strip()))
                campaign_eligible._source_policy_blocked = lambda lead: False
            try:
                results = {}
                for lead in rows:
                    if lead.get("status") in blocked_statuses or (old and lead.get("status") == "contact_form_pool"):
                        continue
                    ident = lead["id"]
                    br = broad_ready.is_broad_outreach_ready(lead, {"conn": conn})["ready"]
                    v1 = campaign_eligible.review_campaign_eligible(lead, {"conn": conn})["eligible"]
                    v2 = campaign_eligible_v2.review_campaign_eligible_v2(
                        lead, {"conn": conn, "mx_lookup": mx_values})["eligible"]
                    results[ident] = (br, v1, v2, lead.get("organization_key") or f"lead:{ident}")
                return results
            finally:
                broad_ready._is_contact_form_only = original_form
                campaign_eligible._source_policy_blocked = original_source
        before, after = evaluate(True, mx_lookup), evaluate(False, mx_lookup)
        simulated_mx = {domain: "ok" for domain in domains}
        sim_before, sim_after = evaluate(True, simulated_mx), evaluate(False, simulated_mx)
        changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
        expected = {r["id"] for r in rows if
                    (r.get("status") == "contact_form_pool" and r.get("email")) or
                    campaign_eligible._source_policy_blocked(r)}
        def totals(results):
            return (sum(v[0] for v in results.values()), sum(v[1] for v in results.values()),
                    len({v[3] for v in results.values() if v[2]}))
        b, a = totals(before), totals(after)
        sb, sa = totals(sim_before), totals(sim_after)
        sim_changed = {k for k in sim_before.keys() | sim_after.keys()
                       if sim_before.get(k, (False, False, False))[2] !=
                       sim_after.get(k, (False, False, False))[2]}
        unexpected = changed - expected
        source_by_id = {r["id"]: str(r.get("email_source_type") or "<empty>") for r in rows}
        v1_drops = Counter(source_by_id[k] for k in before.keys() | after.keys()
                           if before.get(k, (False, False, False))[1] and
                           not after.get(k, (False, False, False))[1])
        v1_gains = Counter(source_by_id[k] for k in before.keys() | after.keys()
                           if not before.get(k, (False, False, False))[1] and
                           after.get(k, (False, False, False))[1])
        return {"REPLAY_SCOPE": "All leads with an email, excluding terminal statuses; MX from fresh (<24h) cache only, missing cache=dns_error. / 全部有邮箱且非终态线索；MX 仅用 24 小时内缓存，缺失按 dns_error 关闭。",
                "LEADS_WITH_EMAIL": len(rows), "FRESH_MX_CACHE_DOMAINS": len(cache),
                "BROAD_READY_TOTAL_BEFORE": b[0], "BROAD_READY_TOTAL_AFTER": a[0],
                "V1_ELIGIBLE_TOTAL_BEFORE": b[1], "V1_ELIGIBLE_TOTAL_AFTER": a[1],
                "V2_SAFE_UNIQUE_ORGS_BEFORE": b[2], "V2_SAFE_UNIQUE_ORGS_AFTER": a[2],
                "V2_MX_OK_STRESS_TEST_BEFORE": sb[2], "V2_MX_OK_STRESS_TEST_AFTER": sa[2],
                "V2_MX_OK_STRESS_UNEXPECTED_DRIFT": len(sim_changed - expected),
                "V2_MX_OK_STRESS_LABEL": "Synthetic MX=ok for policy drift detection only; not SAFE inventory. / 仅以合成 MX=ok 检测政策漂移，不代表 SAFE 库存。",
                "V1_DROPS_BY_SOURCE": dict(sorted(v1_drops.items())),
                "V1_GAINS_BY_SOURCE": dict(sorted(v1_gains.items())),
                "UNEXPECTED_BROAD_READY_DRIFT": sum(before.get(k, (False, False, False))[0] != after.get(k, (False, False, False))[0] for k in unexpected),
                "UNEXPECTED_V1_DRIFT": sum(before.get(k, (False, False, False))[1] != after.get(k, (False, False, False))[1] for k in unexpected),
                "UNEXPECTED_V2_DRIFT": sum(before.get(k, (False, False, False))[2] != after.get(k, (False, False, False))[2] for k in unexpected),
                "EXPECTED_AFFECTED_ROWS": len(changed - unexpected), "UNEXPECTED_AFFECTED_ROWS": len(unexpected)}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reuse-copy", action="store_true", help="reuse the already-verified phase copy after a code-only iteration")
    args = parser.parse_args()
    fresh = ROOT / "data" / "phase4a8o_copy.db"
    if args.reuse_copy:
        if not fresh.is_file():
            raise RuntimeError("verified_phase_copy_missing")
    else:
        make_copy(args.source, fresh)
    result = {"PHASE": "4A.8O / 七候选重新审计 / Seven-candidate re-audit",
              "SEVEN": seven(ROOT / "data" / "phase4a8n_copy.db",
                             ROOT / "output" / "phase4a8n_reconstructed_candidates.json",
                             ROOT / "output" / "phase4a8n_private_gate_audit.json"),
              "DRIFT": drift(fresh), "PRODUCTION_DB_WRITES": 0, "SMTP_CONNECTIONS": 0}
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"SEVEN": {k: v for k, v in result["SEVEN"].items() if k != "CANDIDATES"},
                      "DRIFT": result["DRIFT"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
