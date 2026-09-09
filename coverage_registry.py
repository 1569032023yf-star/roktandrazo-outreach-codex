"""Coverage Registry — city and platform search coverage tracking.

Persists to output/search_coverage_registry.json for continuity.
Caller is responsible for loading/saving.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = PROJECT_DIR / "output" / "search_coverage_registry.json"


# ============================================================
# City entries
# ============================================================

def init_city_entry(batch_id: str, state: str, city: str, city_type: str = "",
                    keywords: str = "", business_line: str = "retail") -> dict:
    return {
        "search_batch_id": batch_id,
        "search_date": datetime.now().strftime("%Y-%m-%d"),
        "business_line": business_line,
        "state": state,
        "city": city,
        "city_type": city_type,
        "search_keywords": keywords,
        "planned_or_unplanned": "planned",
        "previously_searched": False,
        "candidates_found": 0,
        "official_sites_found": 0,
        "emails_found": 0,
        "hygiene_passed": 0,
        "leads_added": 0,
        "emails_sent": 0,
        "search_status": "pending",
        "incomplete_reason": "",
    }


def finalize_city_entry(entry: dict, candidates: int, sites: int, emails: int,
                        hygiene: int, added: int, sent: int = 0, status: str = "complete"):
    entry["candidates_found"] = candidates
    entry["official_sites_found"] = sites
    entry["emails_found"] = emails
    entry["hygiene_passed"] = hygiene
    entry["leads_added"] = added
    entry["emails_sent"] = sent
    entry["search_status"] = status


# ============================================================
# Platform entries
# ============================================================

def init_platform_entry(platform: str, category: str, keyword: str = "",
                        business_line: str = "retail") -> dict:
    return {
        "platform": platform,
        "category": category,
        "search_keyword": keyword,
        "business_line": business_line,
        "search_date": datetime.now().strftime("%Y-%m-%d"),
        "result_pages_or_batches": 0,
        "candidates_found": 0,
        "own_brand_verified": 0,
        "non_cn_verified": 0,
        "country_uncertain": 0,
        "official_sites_found": 0,
        "public_emails_found": 0,
        "custom_production_qualified": 0,
        "sent_count": 0,
        "reject_count": 0,
        "reject_reasons": [],
    }


def finalize_platform_entry(entry: dict, candidates: int = 0, own_brand: int = 0,
                            non_cn: int = 0, uncertain: int = 0, sites: int = 0,
                            emails: int = 0, custom: int = 0, sent: int = 0,
                            reject: int = 0, reason: str = ""):
    entry["candidates_found"] = candidates
    entry["own_brand_verified"] = own_brand
    entry["non_cn_verified"] = non_cn
    entry["country_uncertain"] = uncertain
    entry["official_sites_found"] = sites
    entry["public_emails_found"] = emails
    entry["custom_production_qualified"] = custom
    entry["sent_count"] = sent
    entry["reject_count"] = reject
    if reason:
        entry["reject_reasons"].append(reason)


# ============================================================
# Registry operations
# ============================================================

def load_registry() -> dict:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text())
        except Exception:
            pass
    return {
        "created_at": datetime.now().isoformat(),
        "updated_at": "",
        "cities": [],
        "platforms": [],
        "stats": {},
    }


def save_registry(reg: dict):
    reg["updated_at"] = datetime.now().isoformat()
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2, ensure_ascii=False))


def recompute_stats(reg: dict):
    cities = reg.get("cities", [])
    completed = [c for c in cities if c.get("search_status") == "complete"]
    pending = [c for c in cities if c.get("search_status") == "pending"]

    states_covered = set(c.get("state", "") for c in completed)
    all_cities = [c.get("city", "") for c in completed]
    unique_cities = sorted(set(all_cities))

    platforms = reg.get("platforms", [])
    platform_names = sorted(set(p.get("platform", "") for p in platforms))

    total_candidates = sum(c.get("candidates_found", 0) for c in completed) + sum(p.get("candidates_found", 0) for p in platforms)
    total_sites = sum(c.get("official_sites_found", 0) for c in completed) + sum(p.get("official_sites_found", 0) for p in platforms)
    total_emails = sum(c.get("emails_found", 0) for c in completed) + sum(p.get("public_emails_found", 0) for p in platforms)
    total_hygiene = sum(c.get("hygiene_passed", 0) for c in completed)
    total_leads = sum(c.get("leads_added", 0) for c in completed)
    total_sent = sum(c.get("emails_sent", 0) for c in completed) + sum(p.get("sent_count", 0) for p in platforms)

    reg["stats"] = {
        "cities_searched": len(completed),
        "cities_pending": len(pending),
        "unique_cities": len(unique_cities),
        "states_covered": len(states_covered),
        "platform_categories": len(platform_names),
        "total_candidates": total_candidates,
        "total_official_sites": total_sites,
        "total_emails_found": total_emails,
        "total_hygiene_passed": total_hygiene,
        "total_leads_added": total_leads,
        "total_emails_sent": total_sent,
    }


def print_coverage_report(reg: dict):
    stats = reg.get("stats", {})
    print("=" * 55)
    print("Search Coverage Report")
    print("=" * 55)
    print(f"  Cities searched:     {stats.get('cities_searched', 0)}")
    print(f"  Cities pending:      {stats.get('cities_pending', 0)}")
    print(f"  Unique cities:       {stats.get('unique_cities', 0)}")
    print(f"  States covered:      {stats.get('states_covered', 0)}")
    print(f"  Total candidates:    {stats.get('total_candidates', 0)}")
    print(f"  Official sites:      {stats.get('total_official_sites', 0)}")
    print(f"  Emails found:        {stats.get('total_emails_found', 0)}")
    print(f"  Hygiene passed:      {stats.get('total_hygiene_passed', 0)}")
    print(f"  Leads added:         {stats.get('total_leads_added', 0)}")
    print(f"  Emails sent:         {stats.get('total_emails_sent', 0)}")

    cities = reg.get("cities", [])
    if cities:
        print(f"\n  City Detail:")
        for c in cities[:10]:
            st = c.get("search_status", "?")
            print(f"    {c.get('state',''):3s} | {c.get('city',''):20s} | {c.get('city_type',''):12s} | {st:8s} | cand={c.get('candidates_found',0)} sites={c.get('official_sites_found',0)} email={c.get('emails_found',0)}")
        if len(cities) > 10:
            print(f"    ... +{len(cities)-10} more")

    platforms = reg.get("platforms", [])
    if platforms:
        print(f"\n  Platform Detail:")
        for p in platforms[:5]:
            print(f"    {p.get('platform',''):12s} | {p.get('category',''):15s} | cand={p.get('candidates_found',0)} own={p.get('own_brand_verified',0)} non_cn={p.get('non_cn_verified',0)}")
        if len(platforms) > 5:
            print(f"    ... +{len(platforms)-5} more")

    print("=" * 55)


# ============================================================
# Send report
# ============================================================

def build_send_report(daily_target: int, today_sent: int, batch_sent: int,
                      hybrid_count: int, custom_count: int,
                      bounced: int, unsub: int, replied: int,
                      send_details: list = None,
                      unsent_details: list = None) -> dict:
    """Build a structured send report."""

    # Region summary
    region_summary = {"states": {}, "cities": {}, "online_brands": 0, "institutions": 0, "unknown": 0}
    if send_details:
        for d in send_details:
            state = d.get("state", "Unknown")
            city = d.get("city", "Unknown") or "Online"
            ctype = d.get("customer_type", "")
            region_summary["states"][state] = region_summary["states"].get(state, 0) + 1
            region_summary["cities"][city] = region_summary["cities"].get(city, 0) + 1
            if ctype == "online_brand":
                region_summary["online_brands"] += 1
            elif any(k in (ctype or "") for k in ["institution", "museum", "park", "school", "visitor"]):
                region_summary["institutions"] += 1
            else:
                region_summary["unknown"] += 1

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "daily_target": daily_target,
        "today_sent": today_sent + batch_sent,
        "this_batch": batch_sent,
        "remaining": max(0, daily_target - (today_sent + batch_sent)),
        "hybrid_template": hybrid_count,
        "custom_template": custom_count,
        "followup": 0,
        "bounce": bounced,
        "unsubscribe": unsub,
        "reply": replied,
        "region_summary": region_summary,
        "send_details": send_details or [],
        "unsent_details": unsent_details or [],
    }


def print_send_report(report: dict):
    print("=" * 55)
    print("Send Report")
    print("=" * 55)
    print(f"  Daily target:      {report['daily_target']}")
    print(f"  Today sent:        {report['today_sent']}")
    print(f"  This batch:        {report['this_batch']}")
    print(f"  Remaining:         {report['remaining']}")
    print(f"  Hybrid template:   {report['hybrid_template']}")
    print(f"  Custom template:   {report['custom_template']}")
    print(f"  Bounce:            {report['bounce']}")
    print(f"  Unsubscribe:       {report['unsubscribe']}")
    print(f"  Reply:             {report['reply']}")

    rs = report.get("region_summary", {})
    print(f"\n  State distribution:")
    for st, cnt in sorted(rs.get("states", {}).items()):
        print(f"    {st}: {cnt}")
    print(f"  Online brands:     {rs.get('online_brands', 0)}")
    print(f"  Institutions:      {rs.get('institutions', 0)}")

    details = report.get("send_details", [])
    if details:
        print(f"\n  Send details ({len(details)}):")
        for d in details[:10]:
            print(f"    {d.get('store','')[:25]:25s} | {d.get('city','')[:12]:12s} | {d.get('state',''):3s} | {d.get('template','')[:15]:15s} | {d.get('status','')}")
        if len(details) > 10:
            print(f"    ... +{len(details)-10} more")

    unsent = report.get("unsent_details", [])
    if unsent:
        print(f"\n  Unsent ({len(unsent)}):")
        for u in unsent[:5]:
            print(f"    {u.get('store','')[:25]:25s} | reason: {u.get('reason','')}")
    print("=" * 55)
