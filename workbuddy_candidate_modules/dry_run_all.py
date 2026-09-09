"""Full production dry-run: adapter + gate on ALL leads. Read-only, no side effects."""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from lead_hygiene_gate import evaluate_a0
from production_adapter import build_candidate_from_db_row, build_context

DB = os.path.join(os.path.dirname(__file__), "..", "data", "bd_leads.db")
conn = sqlite3.connect(f"file:{os.path.abspath(DB)}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
ctx = build_context(conn)

rows = conn.execute("SELECT * FROM leads").fetchall()

total = 0
a0_eligible = 0
b2_rejected = 0
b1_social = 0
c_form = 0
reasons_tally = {}
examples_per_reason = {}

counters = {
    "suppression_blocked": 0,
    "state_blocked": 0,
    "empty_email_blocked": 0,
    "empty_domain_blocked": 0,
    "invalid_email_blocked": 0,
    "evidence_missing_blocked": 0,
    "already_sent_blocked": 0,
    "bounce_blocked": 0,
    "delivery_issue_blocked": 0,
    "guessed_blocked": 0,
    "non_official_source_blocked": 0,
    "not_verified_blocked": 0,
    "not_official_match_blocked": 0,
    "social_blocked": 0,
    "form_blocked": 0,
    "free_email_blocked": 0,
    "directory_blocked": 0,
    "noreply_blocked": 0,
    "supplier_blocked": 0,
    "third_party_blocked": 0,
    "exchange_mx_count": 0,
}

REASON_MAP = {
    "suppression": "suppression_blocked",
    "state_out_of_scope": "state_blocked",
    "email_missing": "empty_email_blocked",
    "email_domain_missing": "empty_domain_blocked",
    "email_invalid": "invalid_email_blocked",
    "evidence_url_missing": "evidence_missing_blocked",
    "evidence_snippet_missing": "evidence_missing_blocked",
    "already_sent": "already_sent_blocked",
    "bounced": "bounce_blocked",
    "delivery_issue": "delivery_issue_blocked",
    "guessed_email": "guessed_blocked",
    "email_source_not_official": "non_official_source_blocked",
    "official_site_email_not_verified": "not_verified_blocked",
    "business_identity_not_matched": "not_official_match_blocked",
    "social_only_evidence": "social_blocked",
    "contact_form_only": "form_blocked",
    "unverified_free_email": "free_email_blocked",
    "directory_or_social_domain": "directory_blocked",
    "unsafe_role_email": "noreply_blocked",
    "supplier_email": "supplier_blocked",
    "third_party_directory": "third_party_blocked",
}

for row in rows:
    rd = dict(row)
    total += 1
    candidate = build_candidate_from_db_row(rd, ctx)
    decision = evaluate_a0(candidate)

    if candidate.get("is_exchange_mx"):
        counters["exchange_mx_count"] += 1

    if decision.a0_eligible:
        a0_eligible += 1
    elif decision.status == "B1_social_verified":
        b1_social += 1
    elif decision.status == "C_contact_form_or_social_message":
        c_form += 1
    else:
        b2_rejected += 1

    for reason in decision.reasons:
        reasons_tally[reason] = reasons_tally.get(reason, 0) + 1
        if reason not in examples_per_reason:
            email = candidate.get("email", "")
            masked = email[:3] + "***" if len(email) > 3 else "***"
            examples_per_reason[reason] = {
                "masked_email": masked,
                "state": candidate.get("state", ""),
                "store": (candidate.get("store_name", "") or "")[:25],
            }
        key = REASON_MAP.get(reason)
        if key:
            counters[key] += 1

conn.close()

print("=" * 65)
print("LEAD HYGIENE GATE - FULL PRODUCTION DRY-RUN")
print("=" * 65)
print()
print(f"Total records:                {total}")
print(f"A0 eligible (PASS):           {a0_eligible}")
print(f"B2 rejected:                  {b2_rejected}")
print(f"B1 social:                    {b1_social}")
print(f"C contact form:               {c_form}")
print(f"Exchange MX flagged:          {counters['exchange_mx_count']}")
print(f"SUM check:                    {a0_eligible + b2_rejected + b1_social + c_form}")
print()
print("--- REJECTION BREAKDOWN ---")
print()
for label, key in [
    ("Suppression blocked", "suppression_blocked"),
    ("Non-TN/AR/KY state", "state_blocked"),
    ("Empty email", "empty_email_blocked"),
    ("Empty domain", "empty_domain_blocked"),
    ("Invalid email format", "invalid_email_blocked"),
    ("Evidence missing (URL+snippet)", "evidence_missing_blocked"),
    ("Already sent/bounced", "already_sent_blocked"),
    ("Hard bounced", "bounce_blocked"),
    ("Delivery issue", "delivery_issue_blocked"),
    ("Guessed email", "guessed_blocked"),
    ("Non-official source type", "non_official_source_blocked"),
    ("Not verified on official site", "not_verified_blocked"),
    ("Not official match", "not_official_match_blocked"),
    ("Social only", "social_blocked"),
    ("Contact form only", "form_blocked"),
    ("Unverified free email", "free_email_blocked"),
    ("Directory domain", "directory_blocked"),
    ("Noreply prefix", "noreply_blocked"),
    ("Supplier email", "supplier_blocked"),
    ("Third-party directory", "third_party_blocked"),
]:
    print(f"  {label:35s} {counters[key]:4d}")
print()
print("--- REASONS TALLY (deduplicated per-lead) ---")
for reason, count in sorted(reasons_tally.items(), key=lambda x: -x[1]):
    ex = examples_per_reason.get(reason, {})
    print(f"  {reason:40s} {count:4d}  ex: {ex.get('masked_email','')} | {ex.get('state','')} | {ex.get('store','')}")
print()
print("--- A0 ELIGIBLE LEADS (if any) ---")
if a0_eligible == 0:
    print("  None - all leads rejected by gate")
else:
    conn2 = sqlite3.connect(f"file:{os.path.abspath(DB)}?mode=ro", uri=True)
    conn2.row_factory = sqlite3.Row
    ctx2 = build_context(conn2)
    for row in conn2.execute("SELECT * FROM leads").fetchall():
        rd = dict(row)
        cand = build_candidate_from_db_row(rd, ctx2)
        if evaluate_a0(cand).a0_eligible:
            email = cand.get("email", "")
            masked = email[:3] + "***" if len(email) > 3 else "***"
            print(f"  id={rd['id']} {masked} | {cand.get('state','')} | {cand.get('store_name','')[:30]}")
    conn2.close()
