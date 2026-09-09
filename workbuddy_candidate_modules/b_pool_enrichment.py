"""HTTP-first B-pool enrichment engine for isolated, non-writing lab dry-runs.

The engine accepts an injected public-page fetcher. It has no database connection,
no SMTP dependency, no browser automation, and no live-send path.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.lead_hygiene.lead_hygiene_gate import ALLOWED_STATES, evaluate_a0, normalize_state
EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
WEBSITE_RE = re.compile(r"(?:WEBSITE|OFFICIAL_WEBSITE)\s*:\s*(https?://[^\s<]+)", re.I)


@dataclass
class EnrichmentResult:
    candidate_id: str
    status: str
    candidate: dict[str, Any]
    reasons: tuple[str, ...] = ()


@dataclass
class EnrichmentMetrics:
    checked_count: int = 0
    existing_website_verified: int = 0
    website_recovered_from_maps: int = 0
    facebook_pages_checked: int = 0
    websites_found_from_facebook: int = 0
    social_emails_found: int = 0
    B1_social_verified_count: int = 0
    official_site_A0_count: int = 0
    C_contact_form_count: int = 0
    rejected_count: int = 0
    browser_fallback_count: int = 0
    elapsed_seconds: float = 0.0
    strict_pool_before: int = 0
    strict_pool_after_estimate: int = 0

    def as_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["average_seconds_per_candidate"] = round(
            self.elapsed_seconds / self.checked_count, 6
        ) if self.checked_count else 0.0
        data["average_seconds_per_A0"] = round(
            self.elapsed_seconds / self.official_site_A0_count, 6
        ) if self.official_site_A0_count else None
        data["estimated_cost_per_A0"] = 0.0 if self.official_site_A0_count else None
        return data


Fetcher = Callable[[str], str | None]


def extract_public_emails(page: str) -> list[str]:
    return sorted(set(match.group(0).lower() for match in EMAIL_RE.finditer(page or "")))


def public_snippet(page: str, email: str, limit: int = 180) -> str:
    compact = " ".join((page or "").split())
    index = compact.lower().find(email.lower())
    if index < 0:
        return compact[:limit]
    start = max(0, index - 70)
    return compact[start : start + limit]


def page_matches_candidate(page: str, candidate: Mapping[str, Any]) -> bool:
    text = (page or "").lower()
    name = str(candidate.get("store_name") or "").lower().strip()
    city = str(candidate.get("city") or "").lower().strip()
    phone = re.sub(r"\D", "", str(candidate.get("phone") or ""))
    score = int(bool(name and name in text)) + int(bool(city and city in text))
    if phone and phone in re.sub(r"\D", "", text):
        score += 1
    return score >= 2


def discover_website(page: str) -> str | None:
    match = WEBSITE_RE.search(page or "")
    return match.group(1).rstrip(".,)") if match else None


def find_contact_form(page: str) -> bool:
    lowered = (page or "").lower()
    return "contact form" in lowered or "<form" in lowered or "messenger" in lowered


def verify_official_site(candidate: dict[str, Any], website: str, fetch: Fetcher) -> dict[str, Any] | None:
    pages = [website, website.rstrip("/") + "/contact", website.rstrip("/") + "/about"]
    for url in pages:
        page = fetch(url)
        if not page or not page_matches_candidate(page, candidate):
            continue
        emails = extract_public_emails(page)
        if emails:
            result = dict(candidate)
            result.update({
                "official_website": website,
                "email": emails[0],
                "evidence_url": url,
                "evidence_snippet": public_snippet(page, emails[0]),
                "email_source_type": "official_mailto" if "mailto:" in page.lower() else "official_page_visible",
                "email_verified_on_official_site": True,
                "official_match": True,
                "confidence_score": "A",
                "status": "new",
            })
            return result
    return None


def enrich_candidate(candidate: Mapping[str, Any], fetch: Fetcher, metrics: EnrichmentMetrics) -> EnrichmentResult:
    record = dict(candidate)
    candidate_id = str(record.get("candidate_id") or "unknown")
    if normalize_state(record.get("state")) not in ALLOWED_STATES:
        metrics.rejected_count += 1
        return EnrichmentResult(candidate_id, "B2_manual_review", record, ("state_out_of_scope",))

    website = str(record.get("website") or record.get("official_website") or "").strip()
    if website:
        metrics.existing_website_verified += 1
    elif record.get("maps_url"):
        maps_page = fetch(str(record["maps_url"])) or ""
        website = discover_website(maps_page) or ""
        if website:
            metrics.website_recovered_from_maps += 1

    if not website and record.get("facebook_url"):
        metrics.facebook_pages_checked += 1
        facebook_page = fetch(str(record["facebook_url"])) or ""
        if page_matches_candidate(facebook_page, record):
            website = discover_website(facebook_page) or ""
            if website:
                metrics.websites_found_from_facebook += 1
            else:
                social_emails = extract_public_emails(facebook_page)
                if social_emails:
                    metrics.social_emails_found += 1
                    metrics.B1_social_verified_count += 1
                    record.update({
                        "email": social_emails[0],
                        "social_only": True,
                        "status": "B1_social_verified",
                        "social_evidence_url": record["facebook_url"],
                        "social_evidence_snippet": public_snippet(facebook_page, social_emails[0]),
                    })
                    return EnrichmentResult(candidate_id, "B1_social_verified", record, ("social_only_evidence",))
                if find_contact_form(facebook_page):
                    metrics.C_contact_form_count += 1
                    record.update({"contact_form_only": True, "status": "C_contact_form_or_social_message"})
                    return EnrichmentResult(candidate_id, "C_contact_form_or_social_message", record, ("contact_form_only",))

    if website:
        verified = verify_official_site(record, website, fetch)
        if verified:
            decision = evaluate_a0(verified)
            if decision.a0_eligible:
                metrics.official_site_A0_count += 1
                return EnrichmentResult(candidate_id, "A0", verified)
            metrics.rejected_count += 1
            return EnrichmentResult(candidate_id, decision.status, verified, decision.reasons)

    if record.get("contact_form_url"):
        metrics.C_contact_form_count += 1
        record.update({"contact_form_only": True, "status": "C_contact_form_or_social_message"})
        return EnrichmentResult(candidate_id, "C_contact_form_or_social_message", record, ("contact_form_only",))

    metrics.rejected_count += 1
    return EnrichmentResult(candidate_id, "B2_manual_review", record, ("official_site_evidence_not_found",))


def run_enrichment(candidates: list[Mapping[str, Any]], pages: Mapping[str, str], strict_pool_before: int = 0) -> tuple[list[EnrichmentResult], EnrichmentMetrics]:
    """Run an entirely in-memory dry-run; no DB writes, SMTP, browser, or network."""
    metrics = EnrichmentMetrics(strict_pool_before=strict_pool_before)
    started = time.perf_counter()
    results: list[EnrichmentResult] = []
    fetch = lambda url: pages.get(url)
    for candidate in candidates:
        metrics.checked_count += 1
        results.append(enrich_candidate(candidate, fetch, metrics))
    metrics.elapsed_seconds = time.perf_counter() - started
    metrics.strict_pool_after_estimate = strict_pool_before + metrics.official_site_A0_count
    return results, metrics


def build_synthetic_fixture() -> dict[str, Any]:
    """Return 50 fabricated TN/AR/KY records and public-page fixtures for tests."""
    states = [("Nashville", "TN"), ("Little Rock", "AR"), ("Lexington", "KY")]
    candidates: list[dict[str, Any]] = []
    pages: dict[str, str] = {}

    def add(index: int, path: str, has_website: bool = False) -> None:
        city, state = states[(index - 1) % len(states)]
        name = f"Synthetic Store {index:02d}"
        phone = f"615-555-{index:04d}"
        candidate = {"candidate_id": f"lab-{index:02d}", "store_name": name, "city": city, "state": state, "phone": phone}
        website = f"https://synthetic-{index:02d}.example.test"
        if has_website:
            candidate["website"] = website
        elif path == "maps":
            candidate["maps_url"] = f"https://maps.example.test/{index:02d}"
            pages[candidate["maps_url"]] = f"{name} {city} {phone} WEBSITE: {website}"
        elif path.startswith("facebook"):
            candidate["facebook_url"] = f"https://facebook.example.test/{index:02d}"
            if path == "facebook_website":
                pages[candidate["facebook_url"]] = f"{name} {city} {phone} WEBSITE: {website}"
            elif path == "facebook_social":
                pages[candidate["facebook_url"]] = f"{name} {city} {phone} public contact social{index:02d}@social.example.test"
            else:
                pages[candidate["facebook_url"]] = f"{name} {city} {phone} Messenger contact form"
        elif path == "form":
            candidate["contact_form_url"] = f"https://forms.example.test/{index:02d}"
        candidates.append(candidate)
        if path in {"existing", "maps", "facebook_website"}:
            pages[website] = f"{name} | {city} | {phone} | Contact: hello{index:02d}@synthetic-{index:02d}.example.test"

    for i in range(1, 13): add(i, "existing", has_website=True)
    for i in range(13, 21): add(i, "maps")
    for i in range(21, 27): add(i, "facebook_website")
    for i in range(27, 35): add(i, "facebook_social")
    for i in range(35, 41): add(i, "form")
    for i in range(41, 51): add(i, "reject")
    return {"fixture_kind": "synthetic_no_customer_data", "strict_pool_before": 10, "candidates": candidates, "pages": pages}


def write_synthetic_lab_db(path: Path) -> None:
    """Create a synthetic-only SQLite fixture; never points at a production DB."""
    fixture = build_synthetic_fixture()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
            CREATE TABLE lab_candidates (candidate_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
            CREATE TABLE public_pages (url TEXT PRIMARY KEY, page_text TEXT NOT NULL);
            CREATE TABLE lab_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        conn.executemany(
            "INSERT INTO lab_candidates(candidate_id, payload_json) VALUES (?, ?)",
            [(row["candidate_id"], json.dumps(row, sort_keys=True)) for row in fixture["candidates"]],
        )
        conn.executemany(
            "INSERT INTO public_pages(url, page_text) VALUES (?, ?)", fixture["pages"].items()
        )
        conn.execute("INSERT INTO lab_meta(key, value) VALUES (?, ?)", ("strict_pool_before", str(fixture["strict_pool_before"])))
        conn.execute("INSERT INTO lab_meta(key, value) VALUES (?, ?)", ("fixture_kind", fixture["fixture_kind"]))
        conn.commit()
    finally:
        conn.close()


def read_lab_db(path: Path) -> dict[str, Any]:
    """Read an existing lab database in SQLite read-only mode."""
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        candidates = [json.loads(row[0]) for row in conn.execute("SELECT payload_json FROM lab_candidates ORDER BY candidate_id")]
        pages = dict(conn.execute("SELECT url, page_text FROM public_pages"))
        meta = dict(conn.execute("SELECT key, value FROM lab_meta"))
    finally:
        conn.close()
    if meta.get("fixture_kind") != "synthetic_no_customer_data":
        raise ValueError("Only synthetic_no_customer_data lab fixtures are accepted")
    return {"fixture_kind": meta["fixture_kind"], "strict_pool_before": int(meta["strict_pool_before"]), "candidates": candidates, "pages": pages}

def render_report(metrics: EnrichmentMetrics) -> str:
    values = metrics.as_dict()
    lines = [
        "# B Pool Enrichment Lab Dry-Run / B 池增强实验 Dry-Run",
        "",
        "## 中文摘要",
        "本报告使用 50 条合成、非客户数据的 TN/AR/KY 候选。引擎只在内存中读取 fixture；未连接网络、SMTP 或数据库，未发信，未写 WorkBuddy。",
        "结果仅说明合成夹具上的逻辑覆盖，不代表生产转化率，也没有真实基线可用于速度比较。",
        "",
        "## English Summary",
        "This report uses 50 synthetic, non-customer TN/AR/KY candidates. The engine reads the fixture in memory only; it does not connect to the network, SMTP, or a database, does not send email, and does not write WorkBuddy.",
        "Results demonstrate fixture logic coverage only. They are not production conversion evidence and no real baseline exists for a speed comparison.",
        "",
        "## Metrics / 指标",
    ]
    for key in ("checked_count", "existing_website_verified", "website_recovered_from_maps", "facebook_pages_checked", "websites_found_from_facebook", "social_emails_found", "B1_social_verified_count", "official_site_A0_count", "C_contact_form_count", "rejected_count", "browser_fallback_count", "average_seconds_per_candidate", "average_seconds_per_A0", "estimated_cost_per_A0", "strict_pool_before", "strict_pool_after_estimate"):
        lines.append(f"- `{key}`: {values[key]}")
    lines.extend(["", "## Safety / 安全", "- WorkBuddy written / 是否写 WorkBuddy: no / 否", "- DB written / 是否写数据库: no / 否", "- SMTP connected / 是否连接 SMTP: no / 否", "- Email sent / 是否发信: no / 否", "- Browser fallback used / 是否使用浏览器 fallback: no / 否", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="In-memory B-pool enrichment lab dry-run")
    parser.add_argument("--write-synthetic-fixture", type=Path)
    parser.add_argument("--write-synthetic-lab-db", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--lab-db", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    if args.write_synthetic_fixture:
        args.write_synthetic_fixture.parent.mkdir(parents=True, exist_ok=True)
        args.write_synthetic_fixture.write_text(json.dumps(build_synthetic_fixture(), indent=2), encoding="utf-8")
        print(args.write_synthetic_fixture)
        return 0
    if args.write_synthetic_lab_db:
        write_synthetic_lab_db(args.write_synthetic_lab_db)
        print(args.write_synthetic_lab_db)
        return 0
    if args.fixture and args.lab_db:
        parser.error("Use either --fixture or --lab-db, not both")
    fixture = read_lab_db(args.lab_db) if args.lab_db else (build_synthetic_fixture() if args.fixture is None else json.loads(args.fixture.read_text(encoding="utf-8")))
    _, metrics = run_enrichment(fixture["candidates"], fixture["pages"], int(fixture.get("strict_pool_before", 0)))
    report = render_report(metrics)
    if args.report_output:
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(report, encoding="utf-8")
        print(args.report_output)
    else:
        print(json.dumps(metrics.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())