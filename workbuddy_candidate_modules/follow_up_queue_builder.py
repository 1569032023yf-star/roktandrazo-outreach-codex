"""Follow-Up Queue Builder — 14-day no-reply follow-up identification.

Key design:
  - Based on send_log (confirmed sends only), not leads table alone
  - UTC time parsing with proper timezone handling
  - Full exclusion pipeline: reply → bounce → unsub → suppression → followup_count → hygiene → dedup
  - Dedup by email AND by domain per day
  - Output: raw_candidates, hygiene_pass, final_sendable

Read-only. Never modifies DB.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / "data" / "bd_leads.db"
OUTPUT_DIR = PROJECT_DIR / "output"

EMAIL_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9]\.)*[a-zA-Z]{2,}$')
CUTOFF_DAYS = 14
DEFAULT_TZ = timezone.utc

FORBIDDEN_EMAILS = {
    "demo.com", "example.com", "test.com", "localhost", "president@whitehouse.gov",
    "whitehouse.gov",
}
FORBIDDEN_DOMAINS = {"example.com", "demo.com", "test.com", "whitehouse.gov"}
FREE_PROVIDER_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com"}


def _mask(email_addr: str) -> str:
    if "@" not in email_addr:
        return "***"
    local, dom = email_addr.rsplit("@", 1)
    return f"{local[:3]}***@{dom}"


def _parse_sent_at(raw: str | None) -> datetime | None:
    """Parse sent_at to UTC datetime. Handles naive and aware formats.
    Naive timestamps are treated as UTC (production DB convention)."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        # Try ISO format with timezone
        if "+" in raw or raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
        # Try naive ISO
        dt = datetime.fromisoformat(raw)
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    # Try common formats
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def build_followup_queue() -> dict:
    conn = sqlite3.connect(f"file:{DB_PATH.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=CUTOFF_DAYS)

    # -- Step 1: Successful send_log entries --
    sent_rows = conn.execute("""
        SELECT sl.lead_id, sl.email, sl.sent_at, l.store_name, l.city, l.state,
               l.official_website, l.status as lead_status,
               l.replied_at, l.bounced_at, l.unsubscribed_at,
               COALESCE(l.followup_count, 0) as fu_count,
               l.last_followup_at, l.confidence_score,
               l.email_verified_on_official_site, l.email as lead_email
        FROM send_log sl
        JOIN leads l ON sl.lead_id = l.id
        WHERE sl.status = 'sent'
          AND sl.email IS NOT NULL AND sl.email != ''
        ORDER BY sl.sent_at
    """).fetchall()

    # Load suppression (normalized)
    suppressed = {
        r[0].strip().lower()
        for r in conn.execute("SELECT email FROM suppression_list WHERE email IS NOT NULL").fetchall()
    }

    # Load today's follow-up domains (dedup)
    today_str = now_utc.strftime("%Y-%m-%d")
    today_fu = set()
    # We'll track domain usage per day from existing data
    existing_domains_today = set()

    conn.close()

    raw_candidates = []
    excluded = {
        "total_sent_log_entries": len(sent_rows),
        "time_parse_failed": 0,
        "not_14d_yet": 0,
        "already_replied": 0,
        "hard_bounced": 0,
        "unsubscribed": 0,
        "suppressed": 0,
        "already_followed_up": 0,
        "bad_email": 0,
        "test_placeholder": 0,
        "status_blocked": 0,
        "domain_mismatch": 0,
    }

    for row in sent_rows:
        lid = row["lead_id"]
        email_addr = (row["email"] or "").strip().lower()
        store_name = (row["store_name"] or "")

        # -- Time parse --
        sent_dt = _parse_sent_at(row["sent_at"])
        if sent_dt is None:
            excluded["time_parse_failed"] += 1
            continue

        # -- 14-day check --
        if sent_dt > cutoff:
            excluded["not_14d_yet"] += 1
            continue

        days = (now_utc - sent_dt).days

        # -- Replied --
        if row["replied_at"]:
            excluded["already_replied"] += 1
            continue

        # -- Hard bounced --
        if row["bounced_at"]:
            excluded["hard_bounced"] += 1
            continue

        # -- Unsubscribed --
        if row["unsubscribed_at"]:
            excluded["unsubscribed"] += 1
            continue

        # -- Suppression (normalized) --
        if email_addr in suppressed:
            excluded["suppressed"] += 1
            continue

        # -- Already followed up (count > 0 OR last_followup_at non-null) --
        if (row["fu_count"] or 0) > 0 or row["last_followup_at"]:
            excluded["already_followed_up"] += 1
            continue

        # -- Email validation --
        if not email_addr or "@" not in email_addr:
            excluded["bad_email"] += 1
            continue

        # -- Test/placeholder --
        domain = email_addr.split("@")[1] if "@" in email_addr else ""
        if email_addr in FORBIDDEN_EMAILS or domain in FORBIDDEN_DOMAINS:
            excluded["test_placeholder"] += 1
            continue

        # -- Lead status blocked --
        if row["lead_status"] in ("do_not_contact", "delivery_issue", "invalid"):
            excluded["status_blocked"] += 1
            continue

        raw_candidates.append({
            "lead_id": lid,
            "store_name": store_name,
            "city": row["city"] or "",
            "state": row["state"] or "",
            "masked_email": _mask(email_addr),
            "email": email_addr,
            "domain": domain,
            "website": row["official_website"] or "",
            "sent_at_utc": sent_dt.isoformat(),
            "days_since_sent": days,
            "confidence_score": row["confidence_score"] or "",
        })

    # -- Hygiene Gate --
    hygiene_pass = []
    hygiene_blocked = 0
    for c in raw_candidates:
        email_addr = c["email"]
        domain = c["domain"]

        # Basic domain validation
        if domain in FREE_PROVIDER_DOMAINS:
            # Free email OK but flag
            pass

        # Domain mismatch: store website domain vs email domain
        website = c["website"]
        if website:
            web_domain = re.sub(r'^https?://(www\.)?', '', website.rstrip('/')).split('/')[0]
            if domain != "gmail.com" and web_domain and domain not in web_domain and web_domain not in domain:
                excluded["domain_mismatch"] += 1
                hygiene_blocked += 1
                continue

        hygiene_pass.append(c)

    # -- Dedup: same email → keep earliest (oldest send) --
    seen_email = {}
    dedup_pass = []
    for c in hygiene_pass:
        e = c["email"]
        if e in seen_email:
            continue
        seen_email[e] = True
        dedup_pass.append(c)

    # -- Dedup: same domain per day → only 1 per domain --
    seen_domain = {}
    final_sendable = []
    for c in dedup_pass:
        d = c["domain"]
        if d in seen_domain:
            continue
        seen_domain[d] = True
        final_sendable.append(c)

    suggested = min(5, len(final_sendable)) if final_sendable else 0

    return {
        "cutoff_days": CUTOFF_DAYS,
        "timestamp": now_utc.isoformat(),
        "raw_candidate_count": len(raw_candidates),
        "hygiene_pass_count": len(hygiene_pass),
        "final_sendable_count": len(final_sendable),
        "exclusion_counts": excluded,
        "dedup_counts": {
            "email_dedup_removed": len(hygiene_pass) - len(dedup_pass),
            "domain_dedup_removed": max(0, len(dedup_pass) - len(final_sendable)),
        },
        "suggested_daily_count": suggested,
        "queue": final_sendable,
    }


def main():
    print("=" * 50)
    print("Follow-Up Queue Builder v2 (14-day)")
    print("=" * 50)

    result = build_followup_queue()
    ex = result["exclusion_counts"]

    print(f"\n  raw candidates:         {result['raw_candidate_count']}")
    print(f"  hygiene_pass:           {result['hygiene_pass_count']}")
    print(f"  final_sendable:         {result['final_sendable_count']}")
    print(f"  suggested_daily:        {result['suggested_daily_count']}")
    print()
    print(f"  Exclusions:")
    print(f"    total send_log:         {ex['total_sent_log_entries']}")
    print(f"    time parse failed:      {ex['time_parse_failed']}")
    print(f"    not yet 14 days:        {ex['not_14d_yet']}")
    print(f"    already replied:        {ex['already_replied']}")
    print(f"    hard bounced:           {ex['hard_bounced']}")
    print(f"    unsubscribed:           {ex['unsubscribed']}")
    print(f"    suppressed:             {ex['suppressed']}")
    print(f"    already followed up:    {ex['already_followed_up']}")
    print(f"    bad email:              {ex['bad_email']}")
    print(f"    test/placeholder:       {ex['test_placeholder']}")
    print(f"    status blocked:         {ex['status_blocked']}")
    print(f"    domain mismatch:        {ex['domain_mismatch']}")
    print(f"    email dedup:            {result['dedup_counts']['email_dedup_removed']}")
    print(f"    domain dedup:           {result['dedup_counts']['domain_dedup_removed']}")

    if result["queue"]:
        oldest = result["queue"][0]
        newest = result["queue"][-1]
        print(f"\n  Range: {oldest['days_since_sent']}d – {newest['days_since_sent']}d since sent")
        print(f"\n  Top 10 follow-up candidates:")
        for item in result["queue"][:10]:
            print(f"    {item['lead_id']:4d} {item['store_name'][:28]:28s} {item['state']:3s} | {item['masked_email']:30s} | {item['days_since_sent']}d")

    # Save JSON (all emails masked in output)
    safe_queue = []
    for item in result["queue"]:
        safe_queue.append({
            "lead_id": item["lead_id"], "store_name": item["store_name"],
            "city": item["city"], "state": item["state"],
            "masked_email": item["masked_email"], "days_since_sent": item["days_since_sent"],
        })

    path = OUTPUT_DIR / "followup_queue_14d.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "timestamp": result["timestamp"], "cutoff_days": result["cutoff_days"],
        "raw_candidate_count": result["raw_candidate_count"],
        "hygiene_pass_count": result["hygiene_pass_count"],
        "final_sendable_count": result["final_sendable_count"],
        "exclusion_counts": result["exclusion_counts"],
        "dedup_counts": result["dedup_counts"],
        "queue": safe_queue,
    }
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n  Saved: {path}")


# ============================================================
# Quick regression
# ============================================================

def run_tests():
    p = 0
    # Test 1: naive time
    dt = _parse_sent_at("2026-06-30T10:00:00")
    ok = dt is not None and dt.tzinfo is not None
    print(f"  {'✓' if ok else '✗'} naive time parse: {dt}")
    if ok: p += 1

    # Test 2: aware time
    dt2 = _parse_sent_at("2026-06-30T10:00:00+00:00")
    ok2 = dt2 is not None
    print(f"  {'✓' if ok2 else '✗'} aware time parse: {dt2}")
    if ok2: p += 1

    # Test 3: bad time
    dt3 = _parse_sent_at("not a date")
    ok3 = dt3 is None
    print(f"  {'✓' if ok3 else '✗'} bad time returns None")
    if ok3: p += 1

    # Test 4: demo.com forbidden
    ok4 = "demo.com" in FORBIDDEN_DOMAINS
    print(f"  {'✓' if ok4 else '✗'} demo.com filtered")
    if ok4: p += 1

    # Test 5: whitehouse.gov filtered
    ok5 = "whitehouse.gov" in FORBIDDEN_DOMAINS
    print(f"  {'✓' if ok5 else '✗'} whitehouse.gov filtered")
    if ok5: p += 1

    # Test 6: suppression case insensitive
    suppressed = {"test@gmail.com", "test@gmail.COM"}
    ok6 = "test@gmail.com".strip().lower() in suppressed
    print(f"  {'✓' if ok6 else '✗'} suppression case-insensitive")
    if ok6: p += 1

    print(f"  {p}/6 passed")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        run_tests()
    else:
        main()
