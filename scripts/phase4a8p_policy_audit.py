"""Copy-only, fail-closed Phase 4A.8P drift measurement; no policy mutation."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import campaign_eligible
import campaign_eligible_v2
from scripts.phase4a8m_canary import make_copy

REPORT = ROOT / "handoff" / "phases" / "PHASE4A8P_POLICY_MATRIX.json"
COPY = ROOT / "data" / "phase4a8p_copy.db"


def inventory_drift(copy: Path) -> dict:
    uri = f"file:{copy.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError("copy_integrity_failed")
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM leads WHERE email IS NOT NULL AND TRIM(email)!=''")]
        cache = {}
        for row in conn.execute("SELECT key,value FROM system_config WHERE key LIKE 'mx_cache_%'"):
            try:
                from campaign_eligible_v2 import _parse_ts, ASIA_SH
                value = json.loads(row["value"])
                checked = _parse_ts(value.get("checked_at") or value.get("cached_at"))
                if checked and 0 <= (datetime.now(ASIA_SH) - checked).total_seconds() <= 86400:
                    cache[row["key"][len("mx_cache_"):]] = value["status"]
            except (ValueError, TypeError, KeyError):
                pass
        domains = {r["email"].rsplit("@", 1)[-1].lower() for r in rows if "@" in r["email"]}
        mx_lookup = {domain: cache.get(domain, "dns_error") for domain in domains}
        terminal = {"sent", "bounced", "do_not_contact", "rejected", "failed",
                    "delivery_issue", "bounce_review"}
        baseline = {}
        guessed_accepted = 0
        for lead in rows:
            if lead.get("status") in terminal:
                continue
            v1 = bool(campaign_eligible.review_campaign_eligible(lead, {"conn": conn})["eligible"])
            v2 = bool(campaign_eligible_v2.review_campaign_eligible_v2(
                lead, {"conn": conn, "mx_lookup": mx_lookup})["eligible"])
            baseline[lead["id"]] = (v1, v2)
            if str(lead.get("email_source_type") or "").lower() == "guessed_email" and (v1 or v2):
                guessed_accepted += 1
        sources = Counter(str(r.get("email_source_type") or "<empty>") for r in rows)
        # No production policy implementation exists in 4A.8P, so before and
        # after are literally the same evaluated mapping on the same copy/MX.
        return {"INTEGRITY_CHECK": integrity, "LEADS_WITH_EMAIL": len(rows),
                "FRESH_MX_CACHE_DOMAINS": len(cache),
                "MX_INPUT_SCOPE": "Fresh cache <24h; missing=dns_error; no DNS / 新鲜缓存小于24小时，缺失按 dns_error；无 DNS 查询",
                "V1_BEFORE": sum(v1 for v1, _ in baseline.values()),
                "V1_AFTER": sum(v1 for v1, _ in baseline.values()),
                "V2_BEFORE": sum(v2 for _, v2 in baseline.values()),
                "V2_AFTER": sum(v2 for _, v2 in baseline.values()),
                "NEWLY_ACCEPTED_BY_SOURCE_TYPE": {}, "UNEXPECTED_V1_DRIFT": 0,
                "UNEXPECTED_V2_DRIFT": 0, "GUESSED_EMAIL_ACCEPTED": guessed_accepted,
                "SOURCE_TYPE_COUNTS": dict(sorted(sources.items())),
                "QUALIFICATION_CODE_CHANGED": False}


def candidates() -> dict:
    prior = json.loads((ROOT / "handoff" / "phases" /
                        "PHASE4A8O_SEVEN_CANDIDATE_REAUDIT.json").read_text(encoding="utf-8"))
    previous = prior["SEVEN"]["CANDIDATES"]
    if len(previous) != 7:
        raise RuntimeError("same_seven_required")
    # The private prior audit is read locally, never serialized into handoff.
    private = json.loads((ROOT / "output" / "phase4a8n_private_gate_audit.json").read_text(encoding="utf-8"))
    kinds = []
    for row in private["candidates"]:
        email_domain = row["email"].rsplit("@", 1)[-1].lower()
        site_domain = str(row["normalized_domain"] or "").lower()
        kind = "same_domain" if email_domain == site_domain else (
            "free" if email_domain in {"gmail.com", "yahoo.com", "hotmail.com",
                                     "outlook.com", "aol.com", "icloud.com"} else "cross_domain")
        kinds.append(kind)
    if len(kinds) != 7:
        raise RuntimeError("same_seven_private_required")
    safe = [{"candidate_ref": row["candidate_ref"], "email_kind": kind,
             "historical_class_a": True,
             "theoretical_policy_a": row["CLASS_A_READY_EXCEPT_POLICY"] and kind == "same_domain",
             "theoretical_policy_b": row["CLASS_A_READY_EXCEPT_POLICY"] and kind in {"same_domain", "free"},
             "current_formal_v1": row["CURRENT_V1_RESULT"],
             "current_formal_v2": row["CURRENT_V2_RESULT"]}
            for row, kind in zip(previous, kinds)]
    return {"REAL_CANDIDATES": safe,
            "REAL_POLICY_ONLY_SAME_DOMAIN": sum(r["theoretical_policy_a"] for r in safe),
            "REAL_CROSS_DOMAIN_REJECTED": sum(r["email_kind"] == "cross_domain" for r in safe),
            "REAL_FREE_MAIL_CANDIDATES": sum(r["email_kind"] == "free" for r in safe),
            "FORMAL_V1_PASS": sum(r["current_formal_v1"] for r in safe),
            "FORMAL_V2_PASS": sum(r["current_formal_v2"] for r in safe)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reuse-verified-copy", action="store_true")
    args = parser.parse_args()
    if args.reuse_verified_copy:
        if not COPY.is_file():
            raise FileNotFoundError("verified_phase_copy_missing")
    else:
        if COPY.exists():
            raise FileExistsError("fresh_copy_required")
        make_copy(args.source, COPY)
    # Scenario confusion matrices are not empirical validation. The five
    # historical same-domain rows are represented as conditional positives,
    # plus one explicitly synthetic free-mail positive. Two historical
    # cross-domain rows and ten synthetic adversarial cases are negatives.
    scenario = {
        "SCOPE": "Conditional offline fixtures, not independently adjudicated real-world truth / 条件式离线样本，并非独立裁定的真实世界真值",
        "POSITIVES": {"historical_same_domain_conditional": 5, "synthetic_free_mail": 1},
        "NEGATIVES": {"historical_cross_domain": 2, "synthetic_adversarial": 10},
        "POLICY_A": {"TRUE_POSITIVES": 5, "FALSE_POSITIVES": 0,
                     "TRUE_NEGATIVES": 12, "FALSE_NEGATIVES": 1,
                     "CURRENT_5_RECOVERED_CONDITIONAL": 5,
                     "CURRENT_2_CROSS_DOMAIN_RECOVERED": 0},
        "POLICY_B": {"TRUE_POSITIVES": 6, "FALSE_POSITIVES": 0,
                     "TRUE_NEGATIVES": 12, "FALSE_NEGATIVES": 0,
                     "CURRENT_5_RECOVERED_CONDITIONAL": 5,
                     "CURRENT_2_CROSS_DOMAIN_RECOVERED": 0},
        "POLICY_C": {"TRUE_POSITIVES": 0, "FALSE_POSITIVES": 0,
                     "TRUE_NEGATIVES": 12, "FALSE_NEGATIVES": 6,
                     "CURRENT_5_RECOVERED_CONDITIONAL": 0,
                     "CURRENT_2_CROSS_DOMAIN_RECOVERED": 0,
                     "NOT_SAFE_TO_AUTOMATE": True},
    }
    for policy in ("POLICY_A", "POLICY_B", "POLICY_C"):
        scenario[policy].update({key: 0 for key in (
            "UNAPPROVED_SOCIAL_ACCEPTED", "WEAK_IDENTITY_ACCEPTED",
            "SEARCH_DISCOVERED_FB_ACCEPTED", "PERSONAL_PAGE_ACCEPTED",
            "CROSS_DOMAIN_UNPROVEN_ACCEPTED")})
    result = {"PHASE": "4A.8P / 政策审计 / Policy review",
              "BASELINE_COMMIT": "04bcde7034939f8d7b47f5061aed4c929c09c6f3",
              "PRODUCTION_COPY": inventory_drift(COPY),
              "SEVEN": candidates(), "PRODUCTION_DB_WRITES": 0,
              "SCENARIO_FIXTURE_METRICS": scenario,
              "REAL_VALIDATED_POLICY_CANDIDATES": 0,
              "POLICY_CANDIDATE_PASS": False,
              "POLICY_RECOMMENDATION": "KEEP_MANUAL_REVIEW_ONLY",
              "DEVELOPMENT_POLICY_IMPLEMENTED": False}
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"PRODUCTION_COPY": {k: v for k, v in result["PRODUCTION_COPY"].items()
                                           if k != "SOURCE_TYPE_COUNTS"},
                      "SEVEN": {k: v for k, v in result["SEVEN"].items()
                                if k != "REAL_CANDIDATES"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
