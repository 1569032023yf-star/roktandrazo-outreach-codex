from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from time import monotonic
from typing import Callable, Iterable
from urllib.parse import urlsplit

from .models import BrandCandidate, SourceMetric


@dataclass(frozen=True)
class PipelineConfig:
    http_workers: int = 4
    browser_workers: int = 1
    max_candidates: int = 90
    provider_max_pages: int = 3

    def __post_init__(self):
        if not 1 <= self.http_workers <= 4 or self.browser_workers != 1:
            raise ValueError("concurrency is bounded at HTTP_WORKERS<=4 and BROWSER_WORKERS=1")
        if not 1 <= self.max_candidates <= 90 or not 1 <= self.provider_max_pages <= 3:
            raise ValueError("candidate/page caps exceed conservative canary bounds")


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _domain(url: str) -> str:
    return (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower().removeprefix("www.")


def _marketplace_url(url: str) -> bool:
    host = _domain(url)
    marketplaces = ("amazon.com", "tiktok.com", "faire.com", "etsy.com", "ebay.com", "walmart.com", "aliexpress.com")
    return any(host == domain or host.endswith("." + domain) for domain in marketplaces)


def organization_key(candidate: BrandCandidate) -> str:
    domain = _domain(candidate.official_website) if candidate.official_site_verified else ""
    owner = _norm(candidate.brand_owner_name) if any(e.get("type") == "verified_parent_company" for e in candidate.owner_verification_evidence) else ""
    brand = _norm(candidate.brand_name)
    source = candidate.discovery_source_url or (candidate.source_urls[0] if candidate.source_urls else "")
    channel = ",".join(sorted(candidate.source_platforms))
    return "domain:" + domain if domain else "owner:" + owner if owner else f"observation:{channel}:{source}:{brand}"


def deduplicate(candidates: Iterable[BrandCandidate]) -> list[BrandCandidate]:
    """Merge only on an identical verified domain or exact source observation."""
    merged: dict[str, BrandCandidate] = {}
    seen_domains: dict[str, str] = {}
    verified_name_domains: dict[str, set[str]] = {}
    for candidate in candidates:
        key = organization_key(candidate)
        domain = _domain(candidate.official_website) if candidate.official_site_verified else ""
        existing_key = seen_domains.get(domain) if domain else None
        existing_key = existing_key or key
        if existing_key not in merged:
            merged[existing_key] = candidate
        else:
            prior = merged[existing_key]
            prior.source_platforms = list(dict.fromkeys(prior.source_platforms + candidate.source_platforms))
            prior.source_urls = list(dict.fromkeys(prior.source_urls + candidate.source_urls))
            prior.product_categories = list(dict.fromkeys(prior.product_categories + candidate.product_categories))
            prior.product_evidence.extend(x for x in candidate.product_evidence if x not in prior.product_evidence)
            prior.public_sales_signals.update(candidate.public_sales_signals)
            if not prior.official_website and candidate.official_website:
                prior.official_website = candidate.official_website
            if not prior.brand_owner_name:
                prior.brand_owner_name = candidate.brand_owner_name
            existing_domain = _domain(prior.official_website) if prior.official_site_verified else ""
            if domain and existing_domain and domain != existing_domain:
                prior.brand_identity_status = candidate.brand_identity_status = "identity_conflict"
                prior.exclusions.append("identity_conflict:verified_domain_mismatch")
                candidate.exclusions.append("identity_conflict:verified_domain_mismatch")
        if domain:
            seen_domains[domain] = existing_key
            verified_name_domains.setdefault(_norm(candidate.brand_name), set()).add(domain)
    for key, candidate in merged.items():
        candidate.organization_key = key
        domains = verified_name_domains.get(_norm(candidate.brand_name), set())
        if len(domains) > 1:
            candidate.brand_identity_status = "identity_conflict"
            if "identity_conflict:similar_name_distinct_verified_domains" not in candidate.exclusions:
                candidate.exclusions.append("identity_conflict:similar_name_distinct_verified_domains")
    return list(merged.values())


class AcquisitionPipeline:
    """Discovery/enrichment orchestrator. Persistence is JSON only, never a lead DB."""

    def __init__(self, output_dir: str | Path, config: PipelineConfig | None = None,
                 history_check: Callable[[dict], str] | None = None,
                 brand_owner_check: Callable[[BrandCandidate], bool] | None = None,
                 official_site_check: Callable[[BrandCandidate], bool] | None = None,
                 first_party_extract: Callable[[BrandCandidate], dict] | None = None,
                 mx_check: Callable[[str], str] | None = None):
        self.output_dir = Path(output_dir)
        self.config = config or PipelineConfig()
        self.history_check = history_check or (lambda _candidate: "UNKNOWN")
        self.brand_owner_check = brand_owner_check or (lambda _candidate: False)
        self.official_site_check = official_site_check or (lambda _candidate: False)
        self.first_party_extract = first_party_extract or (lambda _candidate: {})
        self.mx_check = mx_check or (lambda _email: "unknown")

    def enrich(self, candidates: Iterable[BrandCandidate], source_metrics: list[SourceMetric] | None = None) -> dict:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        started = monotonic()
        unique = deduplicate(candidates)
        unique = unique[:self.config.max_candidates]
        # Merge completed enrichment from a prior run; only completed or history-blocked
        # records skip repeat website fetches. Unknown/pending records can resume later.
        checkpoint = self.output_dir / "checkpoint.json"
        prior_candidates: dict[str, BrandCandidate] = {}
        if checkpoint.exists():
            try:
                prior = json.loads(checkpoint.read_text(encoding="utf-8"))
                prior_candidates = {organization_key(BrandCandidate(**item)): BrandCandidate(**item)
                    for item in prior.get("candidates", [])}
            except (OSError, ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"candidate checkpoint is corrupt and was preserved: {type(exc).__name__}") from exc
        for index, item in enumerate(unique):
            previous = prior_candidates.get(organization_key(item))
            if previous:
                previous.source_platforms = list(dict.fromkeys(previous.source_platforms + item.source_platforms))
                previous.source_urls = list(dict.fromkeys(previous.source_urls + item.source_urls))
                previous.product_categories = list(dict.fromkeys(previous.product_categories + item.product_categories))
                previous.product_evidence.extend(x for x in item.product_evidence if x not in previous.product_evidence)
                previous.public_sales_signals.update(item.public_sales_signals)
                if not previous.official_website:
                    previous.official_website = item.official_website
                unique[index] = previous
        pending = [item for item in unique if item.enrichment_status not in {"complete", "history_blocked"}]
        # Site calls can use the existing bounded browser fallback; keep this lane at 1.
        with ThreadPoolExecutor(max_workers=self.config.browser_workers) as pool:
            list(pool.map(self._enrich_one, pending))
        checkpoint.write_text(json.dumps({"candidates": [item.to_dict() for item in unique]}, indent=2), encoding="utf-8")
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "history_source_available": bool(getattr(self.history_check, "database", None)
                and getattr(self.history_check, "development_copy", False)
                and Path(self.history_check.database).is_file()),
            "history_note": "UNKNOWN unless an explicit development read-only history checker is supplied",
            "candidates": [item.to_dict() for item in unique],
            "metrics": funnel(unique, source_metrics or [], monotonic() - started),
        }
        (self.output_dir / "brand_candidates.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _enrich_one(self, candidate: BrandCandidate) -> None:
        candidate.organization_key = organization_key(candidate)
        if candidate.brand_identity_status == "identity_conflict":
            candidate.enrichment_status = "identity_conflict"
            candidate.exclusions.append("identity_conflict_fail_closed")
            return
        candidate.history_status = str(self.history_check(candidate.to_dict()) or "UNKNOWN")
        if candidate.history_status not in {"UNKNOWN", "new_candidate"}:
            candidate.exclusions.append("history:" + candidate.history_status)
            candidate.enrichment_status = "history_blocked"
            return
        if candidate.history_status == "UNKNOWN":
            candidate.exclusions.append("history_unknown_fail_closed")
        # Owner confirmation must be performed by an explicit, evidence-backed callback.
        if candidate.brand_identity_status not in {"brand_owner_confirmed", "official_brand_store"}:
            if self.brand_owner_check(candidate):
                candidate.brand_identity_status = "brand_owner_confirmed"
            else:
                candidate.brand_identity_status = "unknown"
                candidate.enrichment_status = "identity_pending"
                candidate.exclusions.append("brand_owner_not_confirmed")
                return
        if candidate.brand_identity_status not in {"brand_owner_confirmed", "official_brand_store"}:
            candidate.exclusions.append("brand_owner_not_confirmed")
            return
        if not candidate.official_website or not self.official_site_check(candidate):
            candidate.official_site_verification_status = "failed_or_unavailable"
            candidate.enrichment_status = "site_unverified"
            candidate.exclusions.append("official_site_unverified")
            return
        candidate.official_site_verified = True
        candidate.official_site_verification_status = "verified"
        extracted = self.first_party_extract(candidate) or {}
        candidate.business_email = str(extracted.get("email") or "")
        candidate.email_role = str(extracted.get("role") or "")
        candidate.email_evidence_url = str(extracted.get("url") or "")
        candidate.email_evidence_excerpt = str(extracted.get("excerpt") or "")
        candidate.email_checked_at = str(extracted.get("checked_at") or "")
        candidate.email_evidence_source_type = str(extracted.get("source_type") or "")
        candidate.email_http_status = extracted.get("http_status")
        candidate.email_final_url = str(extracted.get("final_url") or "")
        candidate.email_official_identity_verified = bool(extracted.get("official_identity_verified", False))
        if candidate.business_email:
            from email_hygiene import hygiene_check
            hygiene = hygiene_check(candidate.business_email)
            if not hygiene.get("valid"):
                candidate.email_hygiene_status = str(hygiene.get("reason", "failed"))
                candidate.exclusions.append("email_hygiene:" + str(hygiene.get("reason", "failed")))
                candidate.mx_status = "not_checked_invalid"
            elif (not candidate.email_evidence_url or not candidate.email_evidence_excerpt
                  or candidate.business_email.lower() not in candidate.email_evidence_excerpt.lower()
                  or not candidate.email_official_identity_verified
                  or not candidate.email_final_url or not candidate.email_http_status):
                candidate.exclusions.append("first_party_evidence_incomplete")
                candidate.email_hygiene_status = "evidence_incomplete"
                candidate.mx_status = "not_checked_evidence_incomplete"
                candidate.business_email = ""
            else:
                candidate.email_hygiene_status = "ok"
        # Check the actual mailbox after first-party extraction too. The early
        # organization check above avoids costly site work for already-contacted parties.
        if candidate.business_email:
            post_email_history = str(self.history_check(candidate.to_dict()) or "UNKNOWN")
            candidate.history_status = post_email_history
            if post_email_history not in {"UNKNOWN", "new_candidate"}:
                candidate.enrichment_status = "history_blocked"
                candidate.exclusions.append("history:" + post_email_history)
                return
            if post_email_history == "UNKNOWN" and "history_unknown_fail_closed" not in candidate.exclusions:
                candidate.exclusions.append("history_unknown_fail_closed")
        if candidate.business_email and candidate.email_hygiene_status == "ok":
            candidate.mx_status = self.mx_check(candidate.business_email)
        candidate.enrichment_status = "complete" if candidate.history_status != "UNKNOWN" else "history_unknown_pending"

    def run_sources(self, source_pages: dict[str, list[str]], fetcher_factory=None, *, now=None) -> dict:
        """Run providers independently with one durable checkpoint per source."""
        pipeline_started = monotonic()
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from .providers import ProviderRun, run_public_source
        self.output_dir.mkdir(parents=True, exist_ok=True)

        def run_one(source: str, urls: list[str]):
            source_started = monotonic()
            cp_path = self.output_dir / "source_checkpoints" / f"source_{source}.json"
            cp = {"url_states": {}, "attempt_counts": {}, "attempt_history": [], "candidates": []}
            checkpoint_error = ""
            if cp_path.exists():
                try:
                    cp = json.loads(cp_path.read_text(encoding="utf-8"))
                    if not isinstance(cp, dict):
                        raise ValueError("checkpoint root must be object")
                except (OSError, ValueError, TypeError) as exc:
                    checkpoint_error = type(exc).__name__
                    cp = {"url_states": {}, "attempt_counts": {}, "attempt_history": [], "candidates": []}
            if checkpoint_error:
                # Preserve corrupt bytes for inspection; never silently reset to success.
                return ProviderRun(source, errors=[{"status":"checkpoint_corrupt", "error":checkpoint_error}])
            url_states = dict(cp.get("url_states", {}))
            done = set(cp.get("completed_urls", []))
            candidates = [BrandCandidate(**item) for item in cp.get("candidates", [])]
            errors = list(cp.get("errors", []))
            attempted = int(cp.get("pages_attempted", 0))
            fetched = int(cp.get("pages_fetched", 0))
            failures = int(cp.get("failures", 0))
            rate_limits = int(cp.get("rate_limits", 0))
            restricted = set(cp.get("access_restricted_urls", []))
            retryable = set(cp.get("retryable_urls", []))
            attempts = dict(cp.get("attempt_counts", {}))
            history = list(cp.get("attempt_history", []))
            outcomes = []
            paused_for_rate_limit = False
            timestamp = now or datetime.now(timezone.utc)
            if isinstance(timestamp, datetime) and timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            current_time = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
            for url in urls[:self.config.provider_max_pages]:
                if url in done or url in restricted or len(candidates) >= 30:
                    continue
                state = url_states.get(url, {})
                if state.get("status") == "PARSE_EMPTY":
                    continue
                count = int(attempts.get(url, 0))
                if count >= 3:
                    continue
                last = state.get("last_attempt_at", "")
                if last and url in retryable:
                    try:
                        previous_time = datetime.fromisoformat(last.replace("Z", "+00:00"))
                        now_time = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
                        delay = min(3600, 60 * (2 ** max(0, count - 1)))
                        if (now_time - previous_time).total_seconds() < delay:
                            continue
                    except (ValueError, TypeError):
                        continue
                fetcher = fetcher_factory(source) if fetcher_factory else None
                part = run_public_source(source, [url], fetcher=fetcher, max_pages=1)
                attempted += part.pages_attempted
                fetched += part.pages_fetched
                failures += part.failures
                rate_limits += part.rate_limits
                candidates.extend(part.candidates[:max(0, 30 - len(candidates))])
                errors.extend(part.errors)
                attempts[url] = count + 1
                outcome = part.url_outcomes[0] if part.url_outcomes else {"status":"TRANSIENT_FAILURE"}
                outcomes.append(outcome)
                status = outcome.get("status", "TRANSIENT_FAILURE")
                url_states[url] = {**outcome, "last_attempt_at": current_time}
                history.append({"url":url, "attempt":attempts[url], "at":current_time, "status":status,
                                "error_type":outcome.get("error_type", "")})
                if status == "SUCCESS":
                    done.add(url); retryable.discard(url); restricted.discard(url)
                    url_states[url]["last_success_at"] = current_time
                elif status == "PARSE_EMPTY":
                    done.add(url); retryable.discard(url)
                elif status == "ACCESS_RESTRICTED":
                    restricted.add(url); retryable.discard(url)
                elif status in {"PERMANENT_UNAVAILABLE"}:
                    done.add(url); retryable.discard(url)
                else:
                    retryable.add(url)
                    if outcome.get("rate_limited"):
                        paused_for_rate_limit = True
                cp_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {"source_state":status, "last_attempt_at":current_time,
                    "last_success_at":max((v.get("last_success_at", "") for v in url_states.values()), default=""),
                    "completed_urls": sorted(done), "retryable_urls": sorted(retryable),
                    "access_restricted_urls":sorted(restricted), "attempt_counts":attempts,
                    "url_states":url_states, "attempt_history":history,
                    "candidates": [c.to_dict() for c in candidates], "errors": errors,
                    "pages_attempted": attempted, "pages_fetched": fetched,
                    "failures": failures, "rate_limits": rate_limits}
                temp_path = cp_path.with_suffix(".json.tmp")
                temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                temp_path.replace(cp_path)
                if paused_for_rate_limit:
                    break
            run = ProviderRun(source, candidates, attempted, fetched, failures, rate_limits, errors,
                              url_outcomes=outcomes)
            run.elapsed_seconds = monotonic() - source_started
            return run

        sources = list(source_pages.items())
        runs = []
        with ThreadPoolExecutor(max_workers=min(self.config.http_workers, max(1, len(sources)))) as executor:
            futures = {executor.submit(run_one, source, urls): source for source, urls in sources}
            for future in as_completed(futures):
                runs.append(future.result())
        from .models import SourceMetric
        metrics = [SourceMetric(source=run.source, pages_attempted=run.pages_attempted,
            pages_fetched=run.pages_fetched,
            brands_discovered=sum(c.data_origin == "live_public" for c in run.candidates),
            fixture_candidates=sum(c.data_origin != "live_public" for c in run.candidates), failures=run.failures,
            rate_limits=run.rate_limits,
            network_failures=sum(e.get("status") in {"network_error", "transient_failure", "timeout"} for e in run.errors),
            access_restricted=sum(e.get("status") == "access_restricted" for e in run.errors),
            parse_empty=sum(o.get("status") == "PARSE_EMPTY" for o in run.url_outcomes),
            runtime_seconds=round(run.elapsed_seconds, 3)) for run in runs]
        candidates = [candidate for run in runs for candidate in run.candidates]
        enriched = self.enrich(candidates, metrics)
        enriched["metrics"]["TOTAL_RUNTIME_SECONDS"] = round(monotonic() - pipeline_started, 3)
        enriched["source_errors"] = {run.source: run.errors for run in runs}
        (self.output_dir / "brand_candidates.json").write_text(json.dumps(enriched, indent=2), encoding="utf-8")
        return enriched


def funnel(candidates: list[BrandCandidate], source_metrics: list[SourceMetric], runtime_seconds: float) -> dict:
    source_new: dict[str, int] = {}
    source_verified: dict[str, int] = {}
    for c in candidates:
        if c.history_status == "new_candidate" and c.brand_identity_status in {"brand_owner_confirmed", "official_brand_store"}:
            for source in c.source_platforms:
                source_new[source] = source_new.get(source, 0) + 1
                if (c.business_email and c.email_evidence_url and c.email_evidence_excerpt
                    and c.official_site_verified and c.email_official_identity_verified
                    and c.email_hygiene_status == "ok" and c.mx_status == "ok"):
                    source_verified[source] = source_verified.get(source, 0) + 1
    known = [c for c in candidates if c.history_status != "UNKNOWN"]
    for metric in source_metrics:
        source_items = [c for c in candidates if metric.source in c.source_platforms]
        metric.official_sites_verified = sum(c.official_site_verified for c in source_items)
        metric.emails_found = sum(bool(c.business_email and c.email_evidence_url and c.email_evidence_excerpt
            and c.official_site_verified and c.email_official_identity_verified) for c in source_items)
        metric.new_owners_with_email = sum(bool(c.business_email and c.email_hygiene_status == "ok" and c.mx_status == "ok" and c.history_status == "new_candidate"
            and c.brand_identity_status in {"brand_owner_confirmed", "official_brand_store"}) for c in source_items)
    best_source = "undetermined"
    viable = [m for m in source_metrics if m.pages_fetched]
    if viable:
        if any(m.new_owners_with_email for m in viable):
            best_source = max(viable, key=lambda m: (m.new_owners_with_email, -m.runtime_seconds)).source
        elif any(m.emails_found for m in viable):
            best_source = max(viable, key=lambda m: (m.emails_found, -m.runtime_seconds)).source
        elif any(m.brands_discovered for m in viable):
            best_source = max(viable, key=lambda m: (m.brands_discovered, -m.runtime_seconds)).source
    return {
        "RAW_BRANDS_DISCOVERED": sum(m.brands_discovered for m in source_metrics),
        "DEDUPED_UNIQUE_BRANDS": len(candidates),
        "BRAND_OWNERS_CONFIRMED": sum(c.brand_identity_status in {"brand_owner_confirmed", "official_brand_store"} for c in candidates),
        "EXISTING_ORGS_EXCLUDED": sum(c.history_status not in {"UNKNOWN", "new_candidate"} for c in candidates),
        "HISTORY_BLOCKED_ORGS": sum(c.history_status in {"suppressed_or_unsubscribed", "bounced", "rejected", "previously_sent"} for c in candidates),
        "NEW_UNIQUE_BRAND_OWNERS": sum(c.history_status == "new_candidate" and c.brand_identity_status in {"brand_owner_confirmed", "official_brand_store"} for c in candidates),
        "OFFICIAL_SITES_FOUND": sum(bool(c.official_website) for c in candidates),
        "OFFICIAL_SITES_VERIFIED": sum(c.official_site_verified for c in candidates),
        "FIRST_PARTY_EMAILS_FOUND": sum(bool(c.business_email and c.email_evidence_url and c.email_evidence_excerpt
            and c.official_site_verified and c.email_official_identity_verified) for c in candidates),
        "B2B_EMAILS_FOUND": sum(bool(c.business_email and c.email_evidence_url and c.email_evidence_excerpt
            and c.official_site_verified and c.email_official_identity_verified
            and c.email_role in {"wholesale", "sales", "partnerships", "business", "trade", "orders", "info", "hello"}) for c in candidates),
        "MX_OK": sum(c.mx_status == "ok" for c in candidates),
        "HISTORY_CLEAN_BRANDS_WITH_EMAIL": sum(bool(c.business_email and c.email_evidence_url and c.email_evidence_excerpt
            and c.official_site_verified and c.email_official_identity_verified
            and c.email_hygiene_status == "ok" and c.mx_status == "ok" and c.history_status == "new_candidate"
            and c.brand_identity_status in {"brand_owner_confirmed", "official_brand_store"}) for c in candidates),
        "HISTORY_KNOWN_CANDIDATES": len(known),
        "TIKTOK_NEW_BRANDS": source_new.get("tiktok_shop", 0),
        "TIKTOK_VERIFIED_EMAIL_BRANDS": source_verified.get("tiktok_shop", 0),
        "AMAZON_NEW_BRANDS": source_new.get("amazon", 0),
        "AMAZON_VERIFIED_EMAIL_BRANDS": source_verified.get("amazon", 0),
        "WHOLESALE_NEW_BRANDS": source_new.get("wholesale", 0),
        "WHOLESALE_VERIFIED_EMAIL_BRANDS": source_verified.get("wholesale", 0),
        "TOTAL_RUNTIME_SECONDS": round(runtime_seconds, 3),
        "PROVIDER_PAGES_ATTEMPTED": sum(m.pages_attempted for m in source_metrics),
        "PROVIDER_PAGES_FETCHED": sum(m.pages_fetched for m in source_metrics),
        "NETWORK_FAILURES": sum(m.network_failures for m in source_metrics),
        "HTTP_429": sum(m.rate_limits for m in source_metrics),
        "ACCESS_RESTRICTED": sum(m.access_restricted for m in source_metrics),
        "PARSE_EMPTY": sum(m.parse_empty for m in source_metrics),
        "PER_SOURCE": [m.to_dict() for m in source_metrics],
        "BEST_PERFORMING_SOURCE": best_source,
    }


def make_first_party_enricher(fetcher=None):
    """Reuse discovery's established first-party identity and email evidence code."""
    from discovery.discovery_service import (
        BrowserFallbackWebsiteFetcher, _extract_email_evidence, _fetch_official_pages,
        _official_identity_match,
    )
    from discovery.normalizer import normalized_domain
    web_fetcher = fetcher or BrowserFallbackWebsiteFetcher()
    verified_pages: dict[str, list[dict]] = {}

    def verify(candidate: BrandCandidate) -> bool:
        if not candidate.official_website or _marketplace_url(candidate.official_website):
            return False
        cache_key = candidate.organization_key or organization_key(candidate)
        if verified_pages.get(cache_key):
            return True
        row = {"business_name": candidate.brand_name, "website": candidate.official_website,
               "normalized_domain": normalized_domain(candidate.official_website)}
        pages = _fetch_official_pages(candidate.official_website, web_fetcher)
        if not pages or not _official_identity_match(row, pages):
            return False
        verified_pages[cache_key] = pages
        candidate.official_site_verification_status = "verified"
        candidate.official_site_final_url = str(pages[0].get("final_url") or pages[0].get("url") or "")
        candidate.official_site_checked_at = str(pages[0].get("fetched_at") or "")
        return True

    def extract(candidate: BrandCandidate) -> dict:
        pages = verified_pages.get(candidate.organization_key or organization_key(candidate), [])
        evidence = _extract_email_evidence(pages, candidate.brand_name)
        chosen = evidence
        if not chosen:
            return {}
        email = chosen.get("email", "")
        local = email.split("@", 1)[0].lower()
        role = next((name for name in ("wholesale", "sales", "partnerships", "business", "trade", "orders", "info", "hello") if name in local), "other")
        evidence = chosen.get("evidence", {})
        return {"email": email, "role": role, "url": chosen.get("url", ""),
                "excerpt": chosen.get("snippet", ""), "checked_at": evidence.get("fetched_at", ""),
                "source_type":"first_party_official_page", "http_status":evidence.get("http_status"),
                "final_url":evidence.get("final_url", chosen.get("url", "")),
                "official_identity_verified":True}
    return verify, extract


def make_runtime_callbacks(fetcher=None):
    """Assemble existing first-party identity/email checks with safe public fetch."""
    from .providers import SafeOfficialPageFetcher
    verify_site, extract_email = make_first_party_enricher(fetcher or SafeOfficialPageFetcher())

    def owner(candidate: BrandCandidate) -> bool:
        # Marketplace/directory claims only become owner evidence when they are
        # corroborated by the brand's own verified HTTPS site.
        has_listing = bool(candidate.brand_claim and (candidate.product_or_listing_evidence or candidate.product_evidence))
        if not candidate.official_website or not has_listing or not verify_site(candidate):
            return False
        candidate.owner_verification_evidence.append({
            "type":"first_party_site_plus_independent_listing",
            "source_url":candidate.discovery_source_url,
            "official_site":candidate.official_website,
            "verified":True,
        })
        candidate.identity_class = "brand_owner"
        return True

    def mx(email: str) -> str:
        from email_hygiene import check_mx_cached
        domain = email.rsplit("@", 1)[-1].lower()
        result = check_mx_cached(domain)
        provider = result.get("provider")
        return {"google":"ok", "exchange":"ok", "other":"ok", "no_mx":"no_route",
                "nxdomain":"nxdomain", "dns_timeout":"dns_error", "dns_error":"dns_error"}.get(provider, "unknown")

    return {"brand_owner_check":owner, "official_site_check":verify_site,
            "first_party_extract":extract_email, "mx_check":mx}
