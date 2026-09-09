"""Shadow Mode: compare production get_sendable_leads() SQL vs hygiene gate.

Read-only. No DB writes. No SMTP. No file modifications.

Output:
- SQL picked N leads; gate passed M
- Reasons gate rejected SQL-passed leads
- Leads gate would pass but SQL rejected (gaps in SQL)
"""
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

# ============================================================
# 1. Exact production SQL (from bd_db.py get_sendable_leads, line 325-338)
# ============================================================
c = conn.cursor()
sql_a0 = c.execute("""
    SELECT * FROM leads
    WHERE status = 'new' AND confidence_score = 'A'
    AND email_verified_on_official_site = 1
    AND email_source_type IN ('official_page_visible','official_mailto','wholesale_vendor_page','manual_lookup')
    AND email IS NOT NULL AND email != ''
    AND email NOT IN (SELECT email FROM suppression_list)
    AND id NOT IN (SELECT lead_id FROM send_log WHERE status IN ('sent','bounced'))
    AND (mx_provider IS NULL OR mx_provider = '' OR
         (mx_provider NOT LIKE '%exchange%' AND mx_provider NOT LIKE '%outlook%' AND mx_provider NOT LIKE '%microsoft%'))
    ORDER BY collected_at ASC
""").fetchall()

sql_picked = [dict(r) for r in sql_a0]
print(f"SQL A0 query picked: {len(sql_picked)} leads")

# ============================================================
# 2. Run gate on every SQL-picked lead
# ============================================================

gate_passed = []
gate_rejected = []
rejection_reasons: dict[str, int] = {}

for lead in sql_picked:
    candidate = build_candidate_from_db_row(lead, ctx)
    decision = evaluate_a0(candidate)
    if decision.a0_eligible:
        gate_passed.append(lead)
    else:
        gate_rejected.append((lead, candidate, decision.reasons))
        for reason in decision.reasons:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

print(f"Gate passed:            {len(gate_passed)}")
print(f"Gate rejected (extra):  {len(gate_rejected)}")

if rejection_reasons:
    print()
    print("--- Reasons gate rejected leads that SQL let through ---")
    for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason:40s} {count:3d}")

if gate_rejected:
    print()
    print("--- Rejected leads (masked) ---")
    for lead, cand, reasons in gate_rejected[:10]:
        email = cand.get("email", "")
        masked = email[:3] + "***" if len(email) > 3 else "***"
        print(f"  id={lead['id']:4d} {masked:30s} state={cand.get('state','')} reasons={reasons}")

# ============================================================
# 3. What would gate pass that SQL missed? ("gaps in SQL")
# ============================================================

# Run gate on ALL leads, find ones gate passes but SQL excludes
all_rows = conn.execute("SELECT * FROM leads").fetchall()
gate_would_pass = []
sql_missed = []

for row in all_rows:
    rd = dict(row)
    candidate = build_candidate_from_db_row(rd, ctx)
    decision = evaluate_a0(candidate)
    if decision.a0_eligible:
        gate_would_pass.append(rd)

# Which of gate_would_pass are NOT in sql_picked?
sql_ids = {r["id"] for r in sql_picked}
sql_missed = [r for r in gate_would_pass if r["id"] not in sql_ids]

print()
print(f"Leads gate would pass (full scan): {len(gate_would_pass)}")
print(f"Of those, SQL missed:               {len(sql_missed)}")

if sql_missed:
    print()
    print("--- Leads gate passes but SQL rejects ---")
    for lead in sql_missed:
        cand = build_candidate_from_db_row(lead, ctx)
        email = cand.get("email", "")
        masked = email[:3] + "***" if len(email) > 3 else "***"
        # Analyze WHY SQL rejected it
        rd = lead
        why = []
        if rd.get("status") != "new":
            why.append(f"status={rd['status']}")
        if rd.get("confidence_score") != "A":
            why.append(f"score={rd['confidence_score']}")
        if rd.get("email_verified_on_official_site") != 1:
            why.append("not_verified")
        if rd.get("email_source_type", "") not in ("official_page_visible","official_mailto","wholesale_vendor_page","manual_lookup"):
            why.append(f"source={rd.get('email_source_type','')}")
        if not rd.get("email"):
            why.append("no_email")
        mx = rd.get("mx_provider", "") or ""
        if any(k in mx.lower() for k in ("exchange","outlook","microsoft")):
            why.append(f"mx={mx}")
        # Check suppression
        email_lower = (rd.get("email","") or "").strip().lower()
        if email_lower in ctx["suppressed_emails"]:
            why.append("suppressed")
        if email_lower in ctx["sent_emails"]:
            why.append("in_send_log")
        print(f"  id={rd['id']:4d} {masked:30s} state={rd.get('state','')} sql_blocked_by={', '.join(why)}")

# ============================================================
# 4. Summary
# ============================================================

print()
print("=" * 60)
print("SHADOW MODE SUMMARY")
print("=" * 60)
print(f"SQL query picked:       {len(sql_picked)}")
print(f"Gate passed those:      {len(gate_passed)}")
print(f"Gate rejected extras:   {len(gate_rejected)}")
print(f"Gate would pass (full): {len(gate_would_pass)}")
print(f"SQL missed (gate ok):   {len(sql_missed)}")
print(f"False positives (SQL ok, gate rejects): {len(gate_rejected)}")
print(f"False negatives (SQL block, gate ok):   {len(sql_missed)}")

conn.close()
