"""A0 Inventory Reconciliation — precise sets, no estimates."""
import json, sqlite3

conn = sqlite3.connect("data/bd_leads.db")
conn.row_factory = sqlite3.Row

# Step 1: all strict A0
all_a0 = conn.execute(
    """SELECT DISTINCT l.id, l.store_name, l.city, l.state, l.email, l.store_type,
       l.source_platform, l.evidence_url, l.evidence_snippet, l.evidence_method,
       l.lead_identity_hash, l.product_fit, l.official_website
    FROM leads l WHERE l.status='new' AND l.confidence_score='A'
    AND l.email_verified_on_official_site=1 AND l.email IS NOT NULL AND l.email!=''
    AND l.email LIKE '%@%'
    AND l.email NOT IN(SELECT email FROM suppression_list WHERE email IS NOT NULL)
    AND l.id NOT IN(SELECT lead_id FROM send_log WHERE status IN('sent','bounced'))
    AND (l.mx_provider IS NULL OR l.mx_provider='' OR (l.mx_provider NOT LIKE '%exchange%' AND l.mx_provider NOT LIKE '%outlook%' AND l.mx_provider NOT LIKE '%microsoft%'))
""").fetchall()

print(f"Raw A0 rows: {len(all_a0)}")

# Dedup by lead_identity_hash
seen_lih = {}
dedup = set()
dup_lih = []
for r in all_a0:
    lih = r["lead_identity_hash"] or ""
    if lih and lih in seen_lih:
        dup_lih.append({"id": r["id"], "dup_of": seen_lih[lih], "name": r["store_name"]})
        continue
    seen_lih[lih] = r["id"]
    dedup.add(r["id"])

# Dedup by normalized email
seen_email = {}
dup_email = set()
for r in all_a0:
    if r["id"] not in dedup:
        continue
    e = (r["email"] or "").strip().lower()
    if not e:
        dedup.discard(r["id"])
        continue
    if e in seen_email:
        dup_email.add(r["id"])
        continue
    seen_email[e] = r["id"]

final_ids = dedup - dup_email
final_rows = [r for r in all_a0 if r["id"] in final_ids]

# Classify
retail, custom = set(), set()
for r in final_rows:
    st = r["state"] or ""
    sty = r["store_type"] or ""
    if st in ("TN", "AR", "KY"):
        retail.add(r["id"])
    if sty in (
        "museum_store", "national_park_store", "visitor_center", "school_store",
        "university_store", "aquarium_store", "historic_site", "foundation_store",
        "online_brand", "crowdfunding", "independent_creator",
    ):
        custom.add(r["id"])

overlap = retail & custom
unclassified = set(r["id"] for r in final_rows) - retail - custom

calc = len(retail) + len(custom) - len(overlap) + len(unclassified)

print(f"\nRetail: {len(retail)} | Custom: {len(custom)} | Overlap: {len(overlap)} | Unclassified: {len(unclassified)}")
print(f"Formula: {len(retail)}+{len(custom)}-{len(overlap)}+{len(unclassified)} = {calc}")
print(f"Final IDs: {len(final_ids)} | Match: {calc == len(final_ids)}")

if unclassified:
    print(f"\nUNCLASSIFIED ({len(unclassified)}):")
    for r in final_rows:
        if r["id"] in unclassified:
            print(f"  {r['id']:4d} {r['store_name'][:28]:28s} st={r['state'] or '?':4s} type={r['store_type'] or '?':20s} | {r['email'][:35]}")

# Platform stats
amz = sum(1 for r in final_rows if r["source_platform"] == "Amazon")
ks = sum(1 for r in final_rows if r["source_platform"] in ("Kickstarter",))
gf = sum(1 for r in final_rows if r["source_platform"] == "Gamefound")
bk = sum(1 for r in final_rows if r["source_platform"] == "BackerKit")
inst = sum(1 for r in final_rows if r["store_type"] in ("museum_store","national_park_store","visitor_center","aquarium_store","historic_site","school_store","university_store"))
print(f"\nPlatforms: Amazon={amz} Kickstarter={ks} Gamefound={gf} BackerKit={bk} Institution={inst}")

# Hex check
h = conn.execute("SELECT id,store_name,email,confidence_score,status FROM leads WHERE store_name LIKE 'Palmetto%'").fetchall()
print(f"\nHex artifact: {[(r['id'],r['confidence_score'],r['status']) for r in h]}")

leads_total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
cc = conn.execute("SELECT COUNT(*) FROM leads WHERE confidence_score='C'").fetchone()[0]
conn.close()

# Output JSON
def mask(e):
    if "@" not in (e or ""):
        return "***"
    l, d = e.split("@", 1)
    return f"{l[:3]}***@{d}"

out = []
for r in final_rows:
    eid = r["id"]
    out.append({
        "lead_id": eid, "store_name": r["store_name"],
        "masked_email": mask(r["email"]),
        "state": r["state"] or "",
        "lead_segment": "retail" if eid in retail else ("custom" if eid in custom else "unclassified"),
        "retail_qualified": eid in retail,
        "custom_qualified": eid in custom,
        "overlap": eid in overlap,
        "source_platform": r["source_platform"] or "",
        "evidence_method": r["evidence_method"] or "",
        "final_sendable": True,
    })

report = {
    "leads_total": leads_total,
    "custom_c_count": cc,
    "raw_a0": len(all_a0),
    "dup_identity": len(dup_lih),
    "dup_email": len(dup_email),
    "final_unique_a0": len(final_ids),
    "retail": len(retail), "custom": len(custom),
    "overlap": len(overlap), "unclassified": len(unclassified),
    "formula_match": calc == len(final_ids),
    "leads": out,
}

with open("output/a0_inventory_reconciliation.json", "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print(f"\nSaved. Unique A0={len(final_ids)} Custom_C={cc}")
