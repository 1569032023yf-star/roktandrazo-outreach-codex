"""Final Auto-Sendable A0 Audit — precise classification, mature brand gate."""
import json, sqlite3

conn = sqlite3.connect("data/bd_leads.db")
conn.row_factory = sqlite3.Row

EXACT_TOTAL = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

# ── All rows that PASS the strict A0 query (raw candidates) ──
raw = conn.execute("""
    SELECT DISTINCT l.id, l.store_name, l.city, l.state, l.email, l.store_type,
           l.source_platform, l.evidence_url, l.evidence_snippet, l.evidence_method,
           l.lead_identity_hash, l.product_fit, l.official_website, l.email_source_type
    FROM leads l WHERE l.status='new' AND l.confidence_score='A'
    AND l.email_verified_on_official_site=1 AND l.email IS NOT NULL AND l.email!=''
    AND l.email LIKE '%@%'
    AND l.email NOT IN(SELECT email FROM suppression_list WHERE email IS NOT NULL)
    AND l.id NOT IN(SELECT lead_id FROM send_log WHERE status IN('sent','bounced'))
    AND (l.mx_provider IS NULL OR l.mx_provider='' OR (l.mx_provider NOT LIKE '%exchange%' AND l.mx_provider NOT LIKE '%outlook%' AND l.mx_provider NOT LIKE '%microsoft%'))
""").fetchall()

# ── Legacy/display-only: leads that look like A0 but were collected outside current target zone ──
# These were early-phase leads from other states, never sent, with legacy evidence
LEGACY_IDS = {27, 29, 31, 339, 356}  # Thinker Toys Carmel, Acadia Shops, Packrat's, Hopscotch, Old Fox Books

# ── Dedup by identity hash + email ──
def mask(e):
    if "@" not in (e or ""): return "***"
    l, d = e.split("@", 1)
    return f"{l[:3]}***@{d}"

seen_lih = {}
seen_email = {}
deduped = []
dups = []
for r in raw:
    lih = r["lead_identity_hash"] or ""
    email = (r["email"] or "").strip().lower()
    if lih and lih in seen_lih:
        dups.append({"id": r["id"], "reason": "dup_identity", "dup_of": seen_lih[lih]})
        continue
    if email and email in seen_email:
        dups.append({"id": r["id"], "reason": "dup_email", "dup_of": seen_email[email]})
        continue
    seen_lih[lih] = r["id"]
    seen_email[email] = r["id"]
    deduped.append(dict(r))

# ── Classify each lead ──
display_only = []
auto = []
for r in deduped:
    if r["id"] in LEGACY_IDS:
        display_only.append(dict(r))
        continue
    auto.append(dict(r))

# ── Eliminate unclassified: route every lead ──
def route(r):
    """Returns (segment, template, reason)."""
    st = r["state"] or ""
    sty = r["store_type"] or ""
    pf = (r["product_fit"] or "").lower()
    website = (r["official_website"] or "").lower()

    in_retail = st in ("TN", "AR", "KY")
    in_custom = sty in (
        "museum_store", "national_park_store", "visitor_center",
        "school_store", "university_store", "aquarium_store",
        "historic_site", "foundation_store", "online_brand",
        "crowdfunding", "independent_creator",
    )

    # Institution → custom
    if in_custom and in_retail:
        return ("overlap", "custom_production_v1", "Institution in target state — custom production")
    if in_custom:
        return ("custom", "custom_production_v1", "Institution or online brand — custom production")
    if in_retail:
        return ("retail", "hybrid_wholesale_custom_v1", "Retail store in TN/AR/KY — hybrid wholesale+custom")

    # Out-of-state: check product_fit for clues
    is_brand = any(kw in pf for kw in ["own brand", "original", "custom puzzle", "manufacturer", "brand"])
    if is_brand:
        return ("custom", "custom_production_v1", "Out-of-state brand with own product line")

    sty_lower = sty.lower()
    is_gift = any(kw in sty_lower for kw in ["gift", "puzzle", "toy", "game", "hobby"])
    if is_gift:
        return ("retail", "hybrid_wholesale_custom_v1", "Out-of-state gift/toy/game store")

    return ("retail", "hybrid_wholesale_custom_v1", "Default retail")

retail_set, custom_set, overlap_set = [], [], []

for r in auto:
    seg, tmpl, reason = route(r)
    r["segment"] = seg
    r["template_id"] = tmpl
    r["routing_reason"] = reason
    if seg == "retail":
        retail_set.append(r)
    elif seg == "custom":
        custom_set.append(r)
    elif seg == "overlap":
        overlap_set.append(r)
        retail_set.append(r)
        custom_set.append(r)

# ── Mature brand gate ──
MATURE_CHECK = {
    "Cards Against Humanity": "enterprise_manual_review",
    "What Do You Meme": "enterprise_manual_review",
    "Ultra PRO": "contact_role_uncertain",
    "Renegade Game Studios": "fit_confirmed",
    "Dire Wolf Digital": "fit_confirmed",
    "CGE Czech Games": "fit_confirmed",
    "Bezier Games": "fit_confirmed",
    "Ridleys Games": "contact_role_uncertain",
    "Level 99 Games": "fit_confirmed",
    "Stone Blade Entertainment": "fit_confirmed",
}

mature_manual = []
mature_uncertain = []
final_auto = []

for r in auto:
    name = r["store_name"]
    if name in MATURE_CHECK:
        result = MATURE_CHECK[name]
        if result == "enterprise_manual_review":
            r["mature_result"] = "enterprise_manual_review"
            r["status"] = "manual_review"
            mature_manual.append(r)
            continue
        elif result == "contact_role_uncertain":
            r["mature_result"] = "contact_role_uncertain"
            r["status"] = "manual_review"
            mature_uncertain.append(r)
            continue
        else:
            r["mature_result"] = "fit_confirmed"
    else:
        r["mature_result"] = "not_reviewed"
    final_auto.append(r)

# ── Counts ──
retail_auto = [r for r in final_auto if r["segment"] == "retail" or r["segment"] == "overlap"]
custom_auto = [r for r in final_auto if r["segment"] == "custom" or r["segment"] == "overlap"]
overlap_auto = [r for r in final_auto if r["segment"] == "overlap"]

print(f"=== FINAL AUTO-SENDABLE A0 AUDIT ===")
print(f"Leads exact total:      {EXACT_TOTAL}")
print(f"Raw A0 rows:            {len(raw)}")
print(f"Display-only (legacy):  {len(display_only)}")
print(f"  {[r['id'] for r in display_only]}")
print(f"Dedup removed:          {len(dups)}")
print(f"After display-only:     {len(auto)}")
print(f"Mature brand manual:    {len(mature_manual)} ({[r['store_name'] for r in mature_manual]})")
print(f"Contact role uncertain: {len(mature_uncertain)} ({[r['store_name'] for r in mature_uncertain]})")
print(f"")
print(f"CLASSIFICATION:")
print(f"  Retail-qualified:     {len(retail_auto)}")
print(f"  Custom-qualified:     {len(custom_auto)}")
print(f"  Overlap:              {len(overlap_auto)}")
print(f"  Manual review:        {len(mature_manual) + len(mature_uncertain)}")
print(f"  Final auto-sendable:  {len(final_auto)}")
print(f"  Safety target:        30")
print(f"  Real gap:             {max(0, 30 - len(final_auto))}")

# ── Detail ──
print(f"\n{'='*60}")
print(f"AUTO-SENDABLE ({len(final_auto)}):")
for r in final_auto:
    print(f"  {r['id']:4d} {r['store_name'][:28]:28s} {r['segment']:7s} | {mask(r['email']):30s} | {r['source_platform'] or 'N/A':12s} | mature={r['mature_result']}")

if mature_manual:
    print(f"\nENTERPRISE MANUAL REVIEW ({len(mature_manual)}):")
    for r in mature_manual:
        print(f"  {r['id']:4d} {r['store_name'][:28]:28s} → {r['mature_result']}")

if mature_uncertain:
    print(f"\nCONTACT ROLE UNCERTAIN ({len(mature_uncertain)}):")
    for r in mature_uncertain:
        print(f"  {r['id']:4d} {r['store_name'][:28]:28s} → {r['mature_result']}")

# ── Output JSON ──
output = {
    "exact_leads_total": EXACT_TOTAL,
    "raw_a0_rows": len(raw),
    "display_only_legacy": len(display_only),
    "dedup_removed": len(dups),
    "mature_enterprise_manual": len(mature_manual),
    "mature_contact_uncertain": len(mature_uncertain),
    "retail_qualified": len(retail_auto),
    "custom_qualified": len(custom_auto),
    "overlap": len(overlap_auto),
    "manual_review_total": len(mature_manual) + len(mature_uncertain),
    "final_auto_sendable": len(final_auto),
    "safety_target": 30,
    "real_gap": max(0, 30 - len(final_auto)),
    "auto_sendable": [
        {
            "lead_id": r["id"],
            "store_name": r["store_name"],
            "masked_email": mask(r["email"]),
            "state": r["state"] or "",
            "segment": r["segment"],
            "template_id": r["template_id"],
            "routing_reason": r["routing_reason"],
            "source_platform": r["source_platform"] or "",
            "mature_review": r["mature_result"],
        }
        for r in final_auto
    ],
    "manual_review": [
        {
            "lead_id": r["id"],
            "store_name": r["store_name"],
            "reason": r.get("mature_result", "unclassified"),
        }
        for r in mature_manual + mature_uncertain
    ],
    "display_only": [{"lead_id": r["id"], "store_name": r["store_name"]} for r in display_only],
}

with open("output/a0_inventory_reconciliation.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\nSaved: output/a0_inventory_reconciliation.json")
conn.close()
