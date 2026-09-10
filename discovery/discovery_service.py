"""Single-city discovery orchestration for inventory Lane A."""
from __future__ import annotations

import json
import hashlib
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import bd_db
from discovery.models import PlaceSearchResult, ProviderPage, utc_now
from discovery.normalizer import (
    is_closed_status,
    is_suitable_retail,
    normalize_address,
    normalize_business_name,
    normalize_phone,
    normalized_domain,
)
from discovery.providers.base import SearchProvider, load_provider
from history_crosscheck import cross_check, normalize_email, host
from lead_hygiene_gate import evaluate_a0
from outreach_control import RETAIL_QUERY_FAMILIES
from retail_city_queue import search_queries
from broad_outreach_gate import _gen_organization_key
from timezone_resolver import resolve_timezone


BLOCKING_HISTORY_RESULTS = {
    "suppressed_or_unsubscribed",
    "bounced",
    "previously_sent",
    "exact_duplicate",
    "rejected",
}

STAGING_POSTPROCESS_STATUSES = (
    "website_lookup_pending",
    "email_extraction_pending",
    "validation_pending",
    "history_check_pending",
)
EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
WEBSITE_SCAN_PATHS = (
    ("", "official_homepage"),
    ("contact", "official_contact_page"),
    ("about", "official_about_page"),
    ("wholesale", "official_wholesale_page"),
    ("vendor", "official_vendor_page"),
    ("partnership", "official_partnership_page"),
    ("privacy", "official_privacy_page"),
    ("terms", "official_terms_page"),
)
CONTACT_FORM_RE = re.compile(r"<form\b[^>]*>.*?</form>", re.IGNORECASE | re.DOTALL)
NOISE_EMAIL_PREFIXES = ("noreply@", "no-reply@", "example@", "privacy@", "copyright@")


class _VisibleTextParser(HTMLParser):
    """Extract visible text and mailto targets, excluding hidden/script content."""

    _NON_VISIBLE = {"script", "style", "template", "noscript", "svg"}
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visibility_stack: list[bool] = [True]
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = {str(k).lower(): str(v or "").lower() for k, v in attrs}
        style = attrs_map.get("style", "").replace(" ", "")
        visible = self.visibility_stack[-1] and not (
            tag.lower() in self._NON_VISIBLE
            or "hidden" in attrs_map
            or attrs_map.get("aria-hidden") == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        )
        if tag.lower() not in self._VOID:
            self.visibility_stack.append(visible)
        if visible:
            href = attrs_map.get("href", "")
            if href.startswith("mailto:"):
                self.parts.append(href[7:].split("?", 1)[0])

    def handle_endtag(self, _tag: str) -> None:
        if len(self.visibility_stack) > 1:
            self.visibility_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.visibility_stack[-1] and data.strip():
            self.parts.append(data.strip())


def _visible_text_from_html(html: str) -> str:
    parser = _VisibleTextParser()
    try:
        parser.feed(str(html or ""))
    except Exception:
        return ""
    return " ".join(parser.parts)


class UrlLibWebsiteFetcher:
    """Small default fetcher; tests inject a fake object with the same fetch(url) method."""

    def __init__(self, timeout_seconds: float = 12.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str) -> dict:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "WorkBuddyDiscovery/1.0 (+official-site-validation)"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            content_type = response.headers.get("content-type", "")
            if "text" not in content_type and "html" not in content_type and "xml" not in content_type:
                return ""
            html = response.read().decode("utf-8", errors="replace")
            return {
                "text": _visible_text_from_html(html),
                "html": html,
                "status": getattr(response, "status", 200),
                "final_url": response.geturl(),
                "tls_verified": True,
                "fetched_at": utc_now(),
            }


@dataclass
class DiscoveryRunSummary:
    status: str
    city: str = ""
    state: str = ""
    provider: str = ""
    query_family: str = ""
    page_cursor: str = ""
    next_page_cursor: str = ""
    results_seen: int = 0
    new_unique_places: int = 0
    duplicate_places: int = 0
    leads_created: int = 0
    existing_leads_linked: int = 0
    provider_errors: int = 0
    validation_statuses: dict[str, int] = field(default_factory=dict)
    error: str = ""


class DiscoveryService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        provider: SearchProvider | None = None,
        provider_name: str | None = None,
        page_size: int = 20,
    ) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.provider = provider or load_provider(provider_name)
        self.page_size = page_size

    def run_places_batch(self, city_row: dict, max_pages: int = 1) -> DiscoveryRunSummary:
        city_id = int(city_row["id"])
        city = city_row["city"]
        state = city_row["state"]
        query_pairs = list(zip(RETAIL_QUERY_FAMILIES, search_queries(city_row)))
        active = self._active_query(city_id, self.provider.provider_name, query_pairs, city_row)
        if not active:
            self._mark_places_matrix_completed(city_id)
            return DiscoveryRunSummary(status="places_matrix_completed_web_pending", city=city, state=state, provider=self.provider.provider_name)

        query_family, query, page_cursor = active
        if not self.provider.configured:
            self._record_provider_failure(city_id, query_family, page_cursor, "configuration_blocked", "provider_not_configured")
            return DiscoveryRunSummary(
                status="configuration_blocked",
                city=city,
                state=state,
                provider=self.provider.provider_name,
                query_family=query_family,
                page_cursor=page_cursor,
                error="provider_not_configured",
            )

        summary = DiscoveryRunSummary(
            status="running",
            city=city,
            state=state,
            provider=self.provider.provider_name,
            query_family=query_family,
            page_cursor=page_cursor,
        )
        pages_processed = 0
        current_cursor = page_cursor
        while pages_processed < max_pages:
            page = self.provider.search_places(query, city, state, current_cursor, self.page_size)
            self._audit_request(city_id, query_family, page)
            if not page.ok:
                self._record_provider_failure(city_id, query_family, current_cursor, page.status, page.error)
                summary.status = page.status
                summary.error = page.error
                summary.provider_errors += 1
                return summary

            page_new = 0
            page_dup = 0
            for result in page.results:
                discovery_id, is_new = self._upsert_result(city_id, query_family, result)
                self._record_hit(discovery_id, query_family, result.source_query, result.provider, result.provider_result_id)
                if is_new:
                    page_new += 1
                    location_status = self._active_city_validation(discovery_id, result, city_row)
                    if location_status:
                        status, lead_id = location_status, None
                    else:
                        status, lead_id = self._classify_and_maybe_create_lead(discovery_id, result)
                    summary.validation_statuses[status] = summary.validation_statuses.get(status, 0) + 1
                    if lead_id:
                        summary.leads_created += 1
                else:
                    page_dup += 1
                    summary.validation_statuses["duplicate_place"] = summary.validation_statuses.get("duplicate_place", 0) + 1

            pages_processed += 1
            summary.results_seen += len(page.results)
            summary.new_unique_places += page_new
            summary.duplicate_places += page_dup
            summary.next_page_cursor = page.next_page_cursor
            self._checkpoint_after_page(city_id, query_family, current_cursor, page, page_new, page_dup)
            if not page.next_page_cursor:
                self._complete_query(city_id, query_family)
                summary.status = "query_completed"
                break
            current_cursor = page.next_page_cursor
            summary.page_cursor = current_cursor

        if summary.status == "running":
            summary.status = "paused_by_runtime_limit" if pages_processed >= max_pages and summary.next_page_cursor else "running"
        if self._all_places_queries_completed(city_id):
            self._mark_places_matrix_completed(city_id)
            summary.status = "places_matrix_completed_web_pending"
        # Commit staged discovery rows so results persist even if the caller
        # (orchestrator / manual run) does not wrap this in a transaction.
        try:
            self.conn.commit()
        except sqlite3.Error:
            pass
        return summary

    def run_staging_postprocess(
        self,
        city_row: dict,
        max_results: int = 20,
        fetcher: Any | None = None,
        staging_ids: list[int] | None = None,
    ) -> DiscoveryRunSummary:
        """Process staged Places rows into A0, manual review, or contact-form pools."""
        city_id = int(city_row["id"])
        fetcher = fetcher or UrlLibWebsiteFetcher()
        placeholders = ",".join("?" for _ in STAGING_POSTPROCESS_STATUSES)
        rows = self.conn.execute(
            f"""SELECT * FROM lead_discovery_results
                WHERE active_city_id=? AND validation_status IN ({placeholders})
                ORDER BY discovered_at ASC, id ASC
                LIMIT ?""",
            (city_id, *STAGING_POSTPROCESS_STATUSES, max(1, int(max_results or 20))),
        ).fetchall()
        if staging_ids is not None:
            rows = self._linked_retry_rows(city_row, staging_ids, require_website=True)
        summary = DiscoveryRunSummary(
            status="staging_postprocess",
            city=city_row["city"],
            state=city_row["state"],
            provider=self.provider.provider_name,
            results_seen=len(rows),
        )
        for row in rows:
            status, lead_id = self._postprocess_staged_result(dict(row), city_row, fetcher)
            summary.validation_statuses[status] = summary.validation_statuses.get(status, 0) + 1
            persisted = self.conn.execute("SELECT validation_status FROM lead_discovery_results WHERE id=?", (row["id"],)).fetchone()
            if lead_id and persisted and persisted[0] == "existing_lead_linked":
                summary.existing_leads_linked += 1
            elif lead_id:
                summary.leads_created += 1
        if not rows:
            summary.status = "staging_postprocess_empty"
        return summary

    def run_website_resolution(self, city_row: dict, resolver: Any, max_results: int = 20,
                               staging_ids: list[int] | None = None) -> DiscoveryRunSummary:
        """Resolve missing official websites; directory/social URLs remain hints only."""
        rows = self.conn.execute(
            """SELECT * FROM lead_discovery_results
               WHERE active_city_id=? AND COALESCE(website,'')=''
                 AND validation_status IN ('website_lookup_pending','manual_review_needed')
               ORDER BY discovered_at,id LIMIT ?""",
            (int(city_row["id"]), max(1, int(max_results))),
        ).fetchall()
        if staging_ids is not None:
            rows = self._linked_retry_rows(city_row, staging_ids, require_website=False)
        summary = DiscoveryRunSummary(
            status="website_resolution", city=city_row["city"], state=city_row["state"],
            provider=self.provider.provider_name, results_seen=len(rows),
        )
        for raw_row in rows:
            row = dict(raw_row)
            result = resolver.resolve(row)
            status = result.status
            if status == "resolved":
                self.conn.execute(
                    """UPDATE lead_discovery_results
                       SET website=?,normalized_domain=?,validation_status='email_extraction_pending',
                           rejection_reason='',last_seen_at=? WHERE id=?""",
                    (result.website, normalized_domain(result.website), utc_now(), row["id"]),
                )
                if row.get("linked_lead_id"):
                    self.conn.execute(
                        "UPDATE leads SET official_website=?,last_checked_at=? WHERE id=? AND COALESCE(official_website,'')=''",
                        (result.website, utc_now(), row["linked_lead_id"]),
                    )
                status = "website_resolved"
            else:
                self.conn.execute(
                    "UPDATE lead_discovery_results SET rejection_reason=?,last_seen_at=? WHERE id=?",
                    (f"website_resolution:{status}:{result.error}"[:500], utc_now(), row["id"]),
                )
            summary.validation_statuses[status] = summary.validation_statuses.get(status, 0) + 1
        if not rows:
            summary.status = "website_resolution_empty"
        return summary

    def _linked_retry_allowed(self, row: dict, city_row: dict) -> bool:
        """Fail closed on history/identity; a linkage alone is not official evidence."""
        lead_row = self.conn.execute('SELECT * FROM leads WHERE id=?', (row.get('linked_lead_id'),)).fetchone()
        if not lead_row or self._row_outside_active_city(row, city_row):
            return False
        if (not str(row.get('city') or '').strip()
                or str(row.get('city')).strip().lower() != str(city_row.get('city') or '').strip().lower()
                or _normalize_state(row.get('state')) != _normalize_state(city_row.get('state'))):
            return False
        lead = dict(lead_row)
        from discovery.website_resolver import _official_url
        if row.get('website') and not _official_url(row['website']):
            return False
        if lead.get('email_source_type') in {'guessed', 'third_party', 'directory', 'social_media'}:
            return False
        if str(lead.get('email') or '').strip() or lead.get('status') not in {'new', 'manual_review_needed'}:
            return False
        if lead.get('review_status') in {'rejected', 'identity_review'}:
            return False
        if lead.get('review_reason_code') not in {'website_lookup_required', 'review_recovery', 'no_public_email_or_form'}:
            return False
        if row.get('validation_status') not in {*STAGING_POSTPROCESS_STATUSES, 'manual_review_needed', 'review_recovery'}:
            return False
        reason = str(row.get('rejection_reason') or '')
        if reason and not reason.startswith(('website_resolution:not_found:', 'website_resolution:network_error:', 'website_resolution:network_retry:')):
            return False
        if row.get('history_crosscheck_result') in BLOCKING_HISTORY_RESULTS - {'exact_duplicate'}:
            return False
        if normalize_business_name(lead.get('store_name', '')) != normalize_business_name(row.get('business_name', '')):
            return False
        if (str(lead.get('city') or '').strip().lower() != str(row.get('city') or '').strip().lower()
                or _normalize_state(lead.get('state')) != _normalize_state(row.get('state'))):
            return False
        if lead.get('formatted_address') and row.get('formatted_address') and normalize_address(lead['formatted_address']) != normalize_address(row['formatted_address']):
            return False
        if lead.get('organization_key') and lead['organization_key'] != _gen_organization_key({**lead, 'organization_key': ''}):
            return False
        if lead.get('review_reason_code') == 'no_public_email_or_form' and not row.get('official_match'):
            return False
        if lead.get('review_reason_code') == 'review_recovery' and lead.get('review_reason_detail') != 'review_recovery=official_site_unavailable':
            return False
        checks = cross_check(self.conn, lead)
        members = {lead['id'], *(r['id'] for r in checks.get('related_leads', []))}
        if lead.get('organization_key'):
            members.update(r[0] for r in self.conn.execute('SELECT id FROM leads WHERE organization_key=?', (lead['organization_key'],)))
        for lid in members:
            member = dict(self.conn.execute('SELECT * FROM leads WHERE id=?', (lid,)).fetchone())
            history = cross_check(self.conn, member)
            if any(history.get(k) for k in ('previously_sent', 'hard_bounced', 'suppressed', 'unsubscribed', 'rejected', 'replied')):
                return False
            if member.get('status') not in {'new', 'manual_review_needed', 'approved_manual_send'}:
                return False
        return True

    def _linked_retry_rows(self, city_row, ids, require_website):
        rows = []
        for sid in ids:
            row = self.conn.execute('SELECT * FROM lead_discovery_results WHERE id=? AND active_city_id=?', (sid, city_row['id'])).fetchone()
            if row and bool(str(row['website'] or '').strip()) == require_website and self._linked_retry_allowed(dict(row), city_row):
                rows.append(row)
        return rows

    def run_linked_backlog(self, city_row, resolver, max_results=20, fetcher=None):
        """Bounded active-city re-entry; retry metadata is separate from provider facts."""
        limit = min(20, max(0, int(max_results)))
        rows = self.conn.execute("""SELECT s.* FROM lead_discovery_results s JOIN leads l ON l.id=s.linked_lead_id
            WHERE s.active_city_id=? AND trim(coalesce(l.email,''))=''
            ORDER BY coalesce(json_extract(CASE WHEN json_valid(s.raw_payload_json) THEN s.raw_payload_json ELSE '{}' END,
                '$.linked_backlog_retry.last_attempt_at'), ''), s.id""", (city_row['id'],)).fetchall()
        eligible = [dict(r) for r in rows if self._linked_retry_allowed(dict(r), city_row)]
        selected = eligible[:limit]
        summary = {'eligible': len(eligible), 'processed': len(selected), 'website_processed': 0,
                   'postprocess_processed': 0, 'existing_leads_linked': 0}
        for row in selected:
            payload = json.loads(row.get('raw_payload_json') or '{}')
            previous = payload.get('linked_backlog_retry', {})
            payload['linked_backlog_retry'] = {**previous, 'last_attempt_at': utc_now(),
                'attempts': int(previous.get('attempts', 0)) + 1,
                'original_validation_status': previous.get('original_validation_status', row['validation_status']),
                'original_rejection_reason': previous.get('original_rejection_reason', row['rejection_reason'])}
            self.conn.execute('UPDATE lead_discovery_results SET raw_payload_json=? WHERE id=?', (json.dumps(payload), row['id']))
            self._linked_backlog_active = row['linked_lead_id']
            self.conn.execute('SAVEPOINT linked_retry_attempt')
            try:
                web = self.run_website_resolution(city_row, resolver, max_results=1, staging_ids=[row['id']])
                post = self.run_staging_postprocess(city_row, max_results=1, fetcher=fetcher, staging_ids=[row['id']])
                summary['website_processed'] += web.results_seen
                summary['postprocess_processed'] += post.results_seen
                summary['existing_leads_linked'] += post.existing_leads_linked
            except Exception as exc:
                self.conn.execute('ROLLBACK TO linked_retry_attempt')
                summary['errors'] = summary.get('errors', 0) + 1
                payload['linked_backlog_retry']['last_error_type'] = type(exc).__name__
                self.conn.execute('UPDATE lead_discovery_results SET raw_payload_json=? WHERE id=?', (json.dumps(payload), row['id']))
            finally:
                self.conn.execute('RELEASE linked_retry_attempt')
                self._linked_backlog_active = None
                # Preserve provenance even when the existing evidence gate rejects a retry.
                self.conn.execute('UPDATE lead_discovery_results SET linked_lead_id=? WHERE id=? AND linked_lead_id IS NULL',
                                  (row['linked_lead_id'], row['id']))
        return summary

    def run_web_directory_probe(self, city_row: dict) -> str:
        page = self.provider.search_web_directories(city_row["city"], city_row["state"], city_row.get("active_query_family") or "", "")
        self.conn.execute(
            "UPDATE retail_city_queue SET web_directory_status=?, last_error=? WHERE id=?",
            (page.status, page.error, city_row["id"]),
        )
        return page.status

    def city_completion_status(self, city_id: int) -> str:
        city = self.conn.execute("SELECT * FROM retail_city_queue WHERE id=?", (city_id,)).fetchone()
        if not city:
            return "city_not_found"
        validation_pending = self.conn.execute(
            """SELECT 1 FROM lead_discovery_results WHERE active_city_id=?
               AND validation_status IN ('validation_pending','history_check_pending','website_lookup_pending','email_extraction_pending')
               LIMIT 1""",
            (city_id,),
        ).fetchone()
        if validation_pending:
            return "validation_pending"
        if not self._all_places_queries_completed(city_id):
            return "places_pending"
        web_status = dict(city).get("web_directory_status")
        if web_status == "web_directory_provider_not_configured":
            return "places_matrix_completed_web_pending"
        return "search_matrix_exhausted_ready"

    def _active_query(self, city_id: int, provider: str, query_pairs: list[tuple[str, str]], city_row: dict) -> tuple[str, str, str] | None:
        self._ensure_query_rows(city_id, provider, query_pairs)
        active_family = city_row.get("active_query_family")
        if active_family:
            row = self._query_row(city_id, provider, active_family)
            if row and row["status"] != "completed":
                query = dict(query_pairs).get(active_family) or f"{active_family} {city_row['city']} {city_row['state']}"
                return active_family, query, row["page_cursor"] or city_row.get("page_cursor") or ""
        for family, query in query_pairs:
            row = self._query_row(city_id, provider, family)
            if row["status"] != "completed":
                page_cursor = row["page_cursor"] or ""
                self.conn.execute(
                    """UPDATE retail_city_queue SET active_provider=?, active_source=?, active_query_family=?,
                       page_cursor=?, resume_state=? WHERE id=?""",
                    (provider, provider, family, page_cursor, "places_query_active", city_id),
                )
                return family, query, page_cursor
        return None

    def _ensure_query_rows(self, city_id: int, provider: str, query_pairs: list[tuple[str, str]]) -> None:
        now = utc_now()
        for family, query in query_pairs:
            self.conn.execute(
                """INSERT OR IGNORE INTO lead_discovery_query_state
                   (active_city_id, provider, query_family, query_text, status, started_at)
                   VALUES (?, ?, ?, ?, 'pending', ?)""",
                (city_id, provider, family, query, now),
            )

    def _query_row(self, city_id: int, provider: str, query_family: str) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT * FROM lead_discovery_query_state WHERE active_city_id=? AND provider=? AND query_family=?",
            (city_id, provider, query_family),
        ).fetchone()

    def _upsert_result(self, city_id: int, query_family: str, result: PlaceSearchResult) -> tuple[int, bool]:
        now = utc_now()
        norm_name = normalize_business_name(result.business_name)
        norm_addr = normalize_address(result.formatted_address)
        norm_phone = normalize_phone(result.phone)
        norm_domain = normalized_domain(result.website)
        existing = None
        if result.provider_result_id:
            existing = self.conn.execute(
                "SELECT id FROM lead_discovery_results WHERE provider=? AND provider_result_id=?",
                (result.provider, result.provider_result_id),
            ).fetchone()
        if not existing and result.place_id:
            existing = self.conn.execute("SELECT id FROM lead_discovery_results WHERE place_id=?", (result.place_id,)).fetchone()
        if not existing and norm_name and norm_addr:
            existing = self.conn.execute(
                """SELECT id FROM lead_discovery_results
                   WHERE normalized_business_name=? AND normalized_address=? AND city=? AND state=?""",
                (norm_name, norm_addr, result.city, result.state),
            ).fetchone()
        if not existing and norm_name and norm_phone and not norm_addr:
            existing = self.conn.execute(
                """SELECT id FROM lead_discovery_results
                   WHERE normalized_business_name=? AND normalized_phone=? AND city=? AND state=?""",
                (norm_name, norm_phone, result.city, result.state),
            ).fetchone()
        if existing:
            current = self.conn.execute(
                "SELECT raw_payload_json FROM lead_discovery_results WHERE id=?",
                (existing["id"],),
            ).fetchone()
            stored_payload = _raw_payload({"raw_payload_json": current[0] if current else ""})
            merged_payload = dict(result.raw_payload or {})
            if stored_payload.get("official_email_evidence"):
                merged_payload["official_email_evidence"] = stored_payload["official_email_evidence"]
            self.conn.execute(
                """UPDATE lead_discovery_results SET last_seen_at=?, source_query=COALESCE(source_query, ?),
                   raw_payload_json=?, raw_types_json=?, normalized_domain=COALESCE(NULLIF(normalized_domain,''), ?),
                   country=COALESCE(NULLIF(country,''), ?)
                   WHERE id=?""",
                (
                    now,
                    result.source_query,
                    json.dumps(merged_payload, sort_keys=True, default=str),
                    json.dumps(result.types),
                    norm_domain,
                    result.country,
                    existing["id"],
                ),
            )
            return int(existing["id"]), False

        cur = self.conn.execute(
            """INSERT INTO lead_discovery_results
               (provider, provider_result_id, place_id, business_name, normalized_business_name,
                formatted_address, normalized_address, city, state, country, postal_code, phone, normalized_phone,
                website, normalized_domain, business_status, primary_type, raw_types_json, source_query,
                query_family, source_url, raw_payload_json, active_city_id, discovered_at, last_seen_at,
                validation_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'validation_pending')""",
            (
                result.provider,
                result.provider_result_id,
                result.place_id,
                result.business_name,
                norm_name,
                result.formatted_address,
                norm_addr,
                result.city,
                result.state,
                result.country,
                result.postal_code,
                result.phone,
                norm_phone,
                result.website,
                norm_domain,
                result.business_status,
                result.primary_type,
                json.dumps(result.types),
                result.source_query,
                query_family,
                result.source_url,
                json.dumps(result.raw_payload, sort_keys=True, default=str),
                city_id,
                now,
                now,
            ),
        )
        return int(cur.lastrowid), True

    def _record_hit(self, discovery_id: int, query_family: str, source_query: str, provider: str, provider_result_id: str) -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO lead_discovery_hits
               (discovery_result_id, query_family, source_query, provider, provider_result_id, seen_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (discovery_id, query_family, source_query, provider, provider_result_id, utc_now()),
        )

    def _active_city_validation(self, discovery_id: int, result: PlaceSearchResult, city_row: dict) -> str:
        actual_city = str(result.city or "").strip()
        actual_state = _normalize_state(result.state)
        expected_city = str(city_row.get("city") or "").strip()
        expected_state = _normalize_state(city_row.get("state"))
        country = str(result.country or "").upper()
        if country and country not in {"US", "USA", "UNITED STATES"}:
            self._update_result(discovery_id, "outside_active_city", "", None, "country_mismatch")
            return "outside_active_city"
        if not actual_city or not actual_state:
            self._update_result(discovery_id, "location_review", "", None, "address_components_missing")
            return "location_review"
        # State-level providers (web_directory) discover stores across the whole state,
        # so only require state match — not the exact active city.
        provider_name = (self.provider.provider_name or "").lower()
        if provider_name in ("web_directory", "webdir"):
            if actual_state != expected_state:
                self._update_result(discovery_id, "outside_active_city", "", None, "active_state_mismatch")
                return "outside_active_city"
            return ""
        if actual_city.lower() != expected_city.lower() or actual_state != expected_state:
            self._update_result(discovery_id, "outside_active_city", "", None, "active_city_mismatch")
            return "outside_active_city"
        return ""

    def _postprocess_staged_result(self, row: dict, city_row: dict, fetcher: Any) -> tuple[str, int | None]:
        discovery_id = int(row["id"])
        if self._row_outside_active_city(row, city_row):
            self._update_result(discovery_id, "outside_active_city", "", None, "active_city_mismatch")
            return "outside_active_city", None
        website = str(row.get("website") or "").strip()
        if not website:
            return "website_lookup_pending", None
        pages = _fetch_official_pages(website, fetcher)
        if not pages:
            candidate = self._candidate_from_row(
                row,
                email="",
                contact_form_url="",
                evidence_url=website,
                evidence_snippet="Official site temporarily unavailable; recheck required.",
                evidence_method="official_site_unavailable",
                confidence_score="B",
                status="manual_review_needed",
                official_match=False,
                review_reason_code="review_recovery",
                notes_suffix="review_recovery=official_site_unavailable",
            )
            lead_id = self._insert_review_candidate(discovery_id, candidate, "review_recovery", "official_site_unavailable")
            return "review_recovery", lead_id

        official_match = _official_identity_match(row, pages)
        email_evidence = _extract_email_evidence(pages)
        contact_form = _extract_contact_form_evidence(pages)
        if not official_match:
            evidence_url = pages[0]["url"]
            evidence_snippet = _snippet_from_text(pages[0]["text"], row.get("business_name") or row.get("normalized_domain") or "")
            candidate = self._candidate_from_row(
                row,
                email=email_evidence.get("email", ""),
                contact_form_url=contact_form.get("url", ""),
                evidence_url=evidence_url,
                evidence_snippet=evidence_snippet or "Official site identity could not be confirmed.",
                evidence_method="identity_review",
                confidence_score="B",
                status="manual_review_needed",
                official_match=False,
                review_reason_code="identity_review",
                notes_suffix="identity_review=official_site_not_confirmed",
            )
            lead_id = self._insert_review_candidate(discovery_id, candidate, "identity_review", "official_site_not_confirmed")
            return "identity_review", lead_id

        if email_evidence.get("email"):
            candidate = self._candidate_from_row(
                row,
                email=email_evidence["email"],
                contact_form_url=contact_form.get("url", ""),
                evidence_url=email_evidence["url"],
                evidence_snippet=email_evidence["snippet"],
                evidence_method=email_evidence["method"],
                confidence_score="A",
                status="new",
                official_match=True,
                notes_suffix="website_postprocess=email_found",
            )
            candidate["email_source_type"] = _email_source_type(email_evidence["method"], email_evidence["snippet"])
            candidate["email_verified_on_official_site"] = True
            candidate["official_email_evidence"] = {
                **email_evidence["evidence"],
                "email_source_type": candidate["email_source_type"],
            }
            hygiene = evaluate_a0({**candidate, "official_match": True})
            if hygiene.a0_eligible:
                candidate["auto_sendable"] = 1
                candidate["manual_sendable"] = 0
                candidate["review_status"] = "hygiene_passed"
                return self._insert_a0_candidate(discovery_id, candidate)
            candidate.update({
                "confidence_score": "B",
                "status": "manual_review_needed",
                "auto_sendable": 0,
                "manual_sendable": 0,
                "review_status": "pending",
                "review_reason_code": "hygiene_failed",
                "review_reason_detail": ",".join(hygiene.reasons),
            })
            lead_id = self._insert_review_candidate(discovery_id, candidate, "manual_review_needed", "hygiene_failed")
            return "manual_review_needed", lead_id

        if contact_form.get("url"):
            candidate = self._candidate_from_row(
                row,
                email="",
                contact_form_url=contact_form["url"],
                evidence_url=contact_form["url"],
                evidence_snippet=contact_form["snippet"],
                evidence_method="official_contact_form",
                confidence_score="C",
                status="contact_form_pool",
                official_match=True,
                review_reason_code="contact_form_only",
                notes_suffix="website_postprocess=contact_form_only",
            )
            candidate["contact_form_only"] = True
            lead_id = self._insert_review_candidate(discovery_id, candidate, "contact_form_pool", "contact_form_only")
            return "contact_form_pool", lead_id

        best_page = _best_identity_page(pages)
        candidate = self._candidate_from_row(
            row,
            email="",
            contact_form_url="",
            evidence_url=best_page["url"],
            evidence_snippet=_snippet_from_text(best_page["text"], row.get("business_name") or "") or "Official site matched; no public email or contact form found.",
            evidence_method=best_page["method"],
            confidence_score="B",
            status="manual_review_needed",
            official_match=True,
            review_reason_code="no_public_email_or_form",
            notes_suffix="website_postprocess=no_email_or_form",
        )
        lead_id = self._insert_review_candidate(discovery_id, candidate, "manual_review_needed", "no_public_email_or_form")
        return "manual_review_needed", lead_id

    def _insert_a0_candidate(self, discovery_id: int, candidate: dict) -> tuple[str, int | None]:
        if getattr(self, '_linked_backlog_active', None):
            return self._link_existing_evidence(discovery_id, candidate) or ('identity_review', None)
        merged = self._link_existing_evidence(discovery_id, candidate)
        if merged is not None:
            return merged
        history = cross_check(self.conn, candidate)
        if history["result"] in BLOCKING_HISTORY_RESULTS:
            self._update_result(
                discovery_id,
                "history_blocked",
                history["result"],
                None,
                history["result"],
                candidate.get("evidence_url", ""),
                candidate.get("evidence_snippet", ""),
                candidate.get("evidence_method", ""),
                candidate.get("contact_form_url", ""),
                1,
                candidate.get("official_email_evidence"),
            )
            return "history_blocked", None
        if history["result"] == "identity_duplicate_new_email":
            bd_db.insert_lead(candidate, conn=self.conn)
            self._update_result(
                discovery_id,
                "identity_review",
                history["result"],
                None,
                "identity_duplicate_new_email",
                candidate.get("evidence_url", ""),
                candidate.get("evidence_snippet", ""),
                candidate.get("evidence_method", ""),
                candidate.get("contact_form_url", ""),
                1,
                candidate.get("official_email_evidence"),
            )
            return "identity_review", None
        lead_id = bd_db.insert_lead(candidate, conn=self.conn)
        if lead_id:
            self._update_result(
                discovery_id,
                "lead_created",
                history["result"],
                lead_id,
                "",
                candidate.get("evidence_url", ""),
                candidate.get("evidence_snippet", ""),
                candidate.get("evidence_method", ""),
                candidate.get("contact_form_url", ""),
                1,
                candidate.get("official_email_evidence"),
            )
            return "lead_created", lead_id
        self._update_result(discovery_id, "history_blocked", history["result"], None, "insert_failed_or_duplicate")
        return "history_blocked", None

    def _link_existing_evidence(self, discovery_id: int, candidate: dict) -> tuple[str, int | None] | None:
        """Link verified evidence atomically; never replace another location or email.

        The savepoint joins the caller transaction. Acquiring the write lock before
        reading prevents concurrent workers from both observing an empty email.
        """
        self.conn.execute("SAVEPOINT existing_evidence")
        try:
            self.conn.execute("UPDATE lead_discovery_results SET id=id WHERE id=?", (discovery_id,))
            staged = self.conn.execute("SELECT * FROM lead_discovery_results WHERE id=?", (discovery_id,)).fetchone()
            history = cross_check(self.conn, candidate)
            related = history.get("related_leads", [])
            matches = [r for r in related if r.get("same_business_identity") and r.get("same_domain")
                       and (r.get("same_location") or (not r.get("location_comparable")
                            and staged and staged["linked_lead_id"] == r["id"]))]
            if not matches:
                return None

            def finish(status, reason, lead_id=None):
                self._update_result(discovery_id, status, reason, lead_id, reason,
                    candidate.get("evidence_url", ""), candidate.get("evidence_snippet", ""),
                    candidate.get("evidence_method", ""), candidate.get("contact_form_url", ""),
                    int(bool(candidate.get("official_match"))), candidate.get("official_email_evidence"))
                return status, lead_id

            if len(matches) != 1:
                return finish("identity_review", "ambiguous_existing_identity")
            if getattr(self, '_linked_backlog_active', None) and matches[0]['id'] != self._linked_backlog_active:
                return finish('identity_review', 'linked_identity_mismatch')
            lead = dict(self.conn.execute("SELECT * FROM leads WHERE id=?", (matches[0]["id"],)).fetchone())
            org = str(lead.get("organization_key") or "")
            if org and candidate.get("organization_key") and org != candidate["organization_key"]:
                return finish("identity_review", "organization_conflict")
            # Check all related identities AND every member of an explicit organization.
            members = {r["id"] for r in related}
            if org:
                members.update(r[0] for r in self.conn.execute("SELECT id FROM leads WHERE organization_key=?", (org,)))
            for member_id in members:
                member = dict(self.conn.execute("SELECT * FROM leads WHERE id=?", (member_id,)).fetchone())
                for subject in (member, {**member, "email": candidate.get("email", "")}):
                    checks = cross_check(self.conn, subject)
                    if any(checks.get(k) for k in ("previously_sent", "hard_bounced", "suppressed", "unsubscribed", "rejected", "replied")):
                        return finish("history_blocked", "existing_identity_history_blocked")
                if str(member.get("status") or "").lower() in {
                    "sent", "previously_sent", "suppressed", "unsubscribed", "bounced", "hard_bounced",
                    "policy_bounced", "rejected", "review_rejected", "replied", "do_not_contact",
                    "failed", "delivery_issue", "bounce_review"}:
                    return finish("history_blocked", "existing_identity_status_blocked")

            ev = candidate.get("official_email_evidence") or {}
            email = normalize_email(candidate.get("email", ""))
            website_host = host(candidate.get("official_website", ""))
            try:
                checked = datetime.fromisoformat(str(ev.get("fetched_at", "")).replace("Z", "+00:00"))
                valid_time = checked.tzinfo is not None and 0 <= (datetime.now(timezone.utc) - checked).total_seconds() <= 30 * 86400
                valid_http = 200 <= int(ev.get("http_status", 0)) < 300
            except (ValueError, TypeError):
                valid_time = valid_http = False
            valid = (email and candidate.get("official_match") and candidate.get("email_verified_on_official_site")
                and ev.get("email") == email and email in str(ev.get("visible_text_excerpt", ""))
                and ev.get("email_source_type") == "official_page_visible"
                and ev.get("http_success") is True and ev.get("tls_success") is True
                and valid_http and valid_time and re.fullmatch(r"[a-fA-F0-9]{64}", str(ev.get("content_hash", "")))
                and urllib.parse.urlsplit(str(ev.get("final_url", ""))).scheme == "https"
                and all(urllib.parse.urlsplit(str(ev.get(k, ""))).scheme in {"http", "https"}
                        and host(str(ev.get(k, ""))) == website_host for k in ("requested_url", "final_url")))
            if not valid:
                return finish("identity_review", "invalid_official_evidence")
            existing_email = str(lead.get("email") or "").strip()
            if existing_email and normalize_email(existing_email) != email:
                self.conn.execute("UPDATE leads SET status='manual_review_needed',review_status='identity_review',"
                    "review_reason_code='identity_duplicate_new_email',auto_sendable=0 WHERE id=?", (lead["id"],))
                return finish("identity_review", "identity_duplicate_new_email")
            if existing_email:
                if not lead.get("email_verified_on_official_site"):
                    return finish("identity_review", "existing_unverified_email")
                return finish("existing_lead_linked", "same_verified_email", lead["id"])
            if lead.get("review_reason_code") not in (None, "", "identity_review", "identity_duplicate_new_email",
                    "website_lookup_required", "no_public_email_or_form", "review_recovery"):
                return finish("identity_review", "existing_review_requires_operator")
            updates = {k: candidate.get(k) for k in ("email", "email_source_type", "evidence_url",
                "evidence_snippet", "evidence_method", "email_verified_on_official_site", "confidence_score",
                "auto_sendable", "manual_sendable", "review_status", "status")}
            updates.update(evidence_checked_at=ev["fetched_at"], last_checked_at=ev["fetched_at"],
                           review_reason_code=candidate.get("review_reason_code", ""),
                           review_reason_detail=candidate.get("review_reason_detail", ""))
            for key in ("organization_key", "recipient_timezone", "timezone_status"):
                if not lead.get(key) or (key == "timezone_status" and lead.get(key) in {"TIMEZONE_UNRESOLVED", "UNSET"}
                        and candidate.get("timezone_status") == "RESOLVED"
                        and lead.get("recipient_timezone") in (None, "", candidate.get("recipient_timezone"))):
                    updates[key] = candidate.get(key, "")
            columns = {r[1] for r in self.conn.execute("PRAGMA table_info(leads)")}
            updates = {k: v for k, v in updates.items() if k in columns}
            self.conn.execute("UPDATE leads SET " + ",".join(k + "=?" for k in updates) + " WHERE id=?",
                              (*updates.values(), lead["id"]))
            return finish("existing_lead_linked", "same_identity_empty_email", lead["id"])
        except Exception:
            self.conn.execute("ROLLBACK TO existing_evidence")
            raise
        finally:
            self.conn.execute("RELEASE existing_evidence")

    def _insert_review_candidate(self, discovery_id: int, candidate: dict, status: str, reason: str) -> int | None:
        if getattr(self, '_linked_backlog_active', None):
            if candidate.get('official_email_evidence'):
                result = self._link_existing_evidence(discovery_id, candidate)
                return result[1] if result else None
            previous = self.conn.execute('SELECT official_match FROM lead_discovery_results WHERE id=?', (discovery_id,)).fetchone()
            self._update_result(discovery_id, status, '', self._linked_backlog_active,
                '' if reason in {'official_site_unavailable', 'no_public_email_or_form'} else reason,
                candidate.get('evidence_url', ''), candidate.get('evidence_snippet', ''),
                candidate.get('evidence_method', ''), candidate.get('contact_form_url', ''),
                int(bool(candidate.get('official_match') or (reason == 'official_site_unavailable' and previous and previous[0]))))
            return None
        candidate["auto_sendable"] = 0
        candidate["manual_sendable"] = 0
        candidate.setdefault("review_status", "pending")
        candidate.setdefault("review_reason_code", reason)
        if candidate.get("official_email_evidence"):
            merged = self._link_existing_evidence(discovery_id, candidate)
            if merged is not None:
                return merged[1]
        history = cross_check(self.conn, candidate)
        if history["result"] in BLOCKING_HISTORY_RESULTS:
            self._update_result(
                discovery_id,
                "history_blocked",
                history["result"],
                None,
                history["result"],
                candidate.get("evidence_url", ""),
                candidate.get("evidence_snippet", ""),
                candidate.get("evidence_method", ""),
                candidate.get("contact_form_url", ""),
                int(bool(candidate.get("official_match"))),
                candidate.get("official_email_evidence"),
            )
            return None
        lead_id = bd_db.insert_lead(candidate, conn=self.conn)
        self._update_result(
            discovery_id,
            status if lead_id else "history_blocked",
            history["result"],
            lead_id,
            "" if lead_id else "insert_failed_or_duplicate",
            candidate.get("evidence_url", ""),
            candidate.get("evidence_snippet", ""),
            candidate.get("evidence_method", ""),
            candidate.get("contact_form_url", ""),
            int(bool(candidate.get("official_match"))),
            candidate.get("official_email_evidence"),
        )
        return lead_id

    def _candidate_from_row(
        self,
        row: dict,
        *,
        email: str,
        contact_form_url: str,
        evidence_url: str,
        evidence_snippet: str,
        evidence_method: str,
        confidence_score: str,
        status: str,
        official_match: bool,
        review_reason_code: str = "",
        notes_suffix: str = "",
    ) -> dict:
        raw = _raw_payload(row)
        normalized_email = normalize_email(email)
        timezone_name, timezone_status = resolve_timezone(row.get("city"), row.get("state"), row.get("postal_code"))
        candidate = {
            "store_name": row.get("business_name") or "",
            "store_type": raw.get("store_type") or row.get("primary_type") or "retail_store",
            "city": row.get("city") or "",
            "state": row.get("state") or "",
            "official_website": row.get("website") or "",
            "formatted_address": row.get("formatted_address") or "",
            "normalized_address": row.get("normalized_address") or normalize_address(row.get("formatted_address") or ""),
            "phone": row.get("phone") or "",
            "normalized_phone": row.get("normalized_phone") or normalize_phone(row.get("phone") or ""),
            "email": normalized_email,
            "email_type": "business_email" if normalized_email else "",
            "contact_form_url": contact_form_url,
            "evidence_url": evidence_url,
            "evidence_snippet": evidence_snippet,
            "evidence_method": evidence_method,
            "email_source_type": _email_source_type(evidence_method, evidence_snippet) if normalized_email else "contact_form" if contact_form_url else "unknown",
            "email_verified_on_official_site": bool(normalized_email and official_match),
            "confidence_score": confidence_score,
            "status": status,
            "source_keyword": row.get("source_query") or "",
            "source_platform": row.get("provider") or "",
            "product_fit": raw.get("product_fit") or "retail_games_gifts",
            "fit_reason": raw.get("fit_reason") or f"Discovered via {row.get('provider') or 'places'} for {row.get('source_query') or ''}",
            "notes": f"discovery_result_id={row.get('id')}; provider={row.get('provider')}; {notes_suffix}".strip(),
            "review_reason_code": review_reason_code,
            "review_reason_detail": notes_suffix,
            "review_status": "pending",
            "auto_sendable": 0,
            "manual_sendable": 0,
            "official_match": official_match,
            "allow_same_domain_locations": True,
            "domain_hash": "|".join(
                [
                    row.get("normalized_domain") or normalized_domain(row.get("website") or ""),
                    normalize_business_name(row.get("business_name") or ""),
                    row.get("normalized_address") or normalize_address(row.get("formatted_address") or ""),
                    str(row.get("city") or "").lower(),
                    str(row.get("state") or "").lower(),
                ]
            ),
            "recipient_timezone": timezone_name or "",
            "timezone_status": timezone_status,
        }
        candidate["organization_key"] = _gen_organization_key(candidate)
        return candidate

    def _row_outside_active_city(self, row: dict, city_row: dict) -> bool:
        actual_city = str(row.get("city") or "").strip()
        actual_state = _normalize_state(row.get("state"))
        if not actual_city or not actual_state:
            return False
        provider_name = (self.provider.provider_name or "").lower()
        if provider_name in ("web_directory", "webdir"):
            # State-level provider: only state must match the active city's state.
            return actual_state != _normalize_state(city_row.get("state"))
        return actual_city.lower() != str(city_row.get("city") or "").strip().lower() or actual_state != _normalize_state(city_row.get("state"))

    def _classify_and_maybe_create_lead(self, discovery_id: int, result: PlaceSearchResult) -> tuple[str, int | None]:
        if is_closed_status(result.business_status):
            self._update_result(discovery_id, "rejected", "", None, "business_closed")
            return "rejected", None
        suitable, reason = is_suitable_retail(result.business_name, result.primary_type, result.types)
        if not suitable:
            self._update_result(discovery_id, "rejected", "", None, reason)
            return "rejected", None
        if not result.website:
            self._update_result(discovery_id, "website_lookup_pending", "", None, "website_lookup_required")
            return "website_lookup_pending", None

        raw = result.raw_payload or {}
        email = normalize_email(raw.get("email", ""))
        contact_form_url = str(raw.get("contact_form_url") or "")
        candidate = self._candidate_from_row(
            {
                "id": discovery_id,
                "business_name": result.business_name,
                "primary_type": result.primary_type,
                "city": result.city,
                "state": result.state,
                "website": result.website,
                "formatted_address": result.formatted_address,
                "normalized_address": normalize_address(result.formatted_address),
                "phone": result.phone,
                "normalized_phone": normalize_phone(result.phone),
                "source_query": result.source_query,
                "provider": result.provider,
                "normalized_domain": normalized_domain(result.website),
                "raw_payload_json": json.dumps(raw, sort_keys=True, default=str),
            },
            email=email,
            contact_form_url=contact_form_url,
            evidence_url=raw.get("evidence_url") or result.website,
            evidence_snippet=raw.get("evidence_snippet") or (email if email else ""),
            evidence_method=raw.get("evidence_method") or ("official_page_visible" if email else "official_contact_form" if contact_form_url else ""),
            confidence_score="A" if email else "C" if contact_form_url else "B",
            status="new" if email else "contact_form_pool" if contact_form_url else "manual_review_needed",
            official_match=bool(email or contact_form_url),
            review_reason_code="contact_form_only" if contact_form_url and not email else "",
            notes_suffix="places_raw_payload_email" if email else "",
        )
        history = cross_check(self.conn, candidate)
        if not email and not contact_form_url:
            self._update_result(discovery_id, "email_extraction_pending", history["result"], None, "")
            return "email_extraction_pending", None
        if history["result"] in BLOCKING_HISTORY_RESULTS:
            self._update_result(discovery_id, "history_blocked", history["result"], None, history["result"])
            return "history_blocked", None
        if history["result"] == "identity_duplicate_new_email":
            bd_db.insert_lead(candidate, conn=self.conn)
            self._update_result(discovery_id, "identity_review", history["result"], None, "identity_duplicate_new_email")
            return "identity_review", None
        if email:
            hygiene = evaluate_a0({**candidate, "official_match": True})
            if hygiene.a0_eligible:
                candidate["auto_sendable"] = 1
                candidate["manual_sendable"] = 0
                candidate["review_status"] = "hygiene_passed"
            else:
                candidate.update({
                    "confidence_score": "B",
                    "status": "manual_review_needed",
                    "review_reason_code": "hygiene_failed",
                    "review_reason_detail": ",".join(hygiene.reasons),
                    "auto_sendable": 0,
                })
        lead_id = bd_db.insert_lead(candidate, conn=self.conn)
        if lead_id:
            status = "lead_created" if email and candidate.get("auto_sendable") else "manual_review_needed" if email else "contact_form_pool"
            self._update_result(discovery_id, status, history["result"], lead_id, "")
            return status, lead_id
        self._update_result(discovery_id, "history_blocked", history["result"], None, history["result"])
        return "history_blocked", None

    def _update_result(
        self,
        discovery_id: int,
        status: str,
        history_result: str,
        linked_lead_id: int | None,
        rejection_reason: str,
        evidence_url: str = "",
        evidence_snippet: str = "",
        evidence_method: str = "",
        contact_form_url: str = "",
        official_match: int | None = None,
        evidence_metadata: dict | None = None,
    ) -> None:
        raw_payload_json = None
        if evidence_metadata:
            row = self.conn.execute(
                "SELECT raw_payload_json FROM lead_discovery_results WHERE id=?",
                (discovery_id,),
            ).fetchone()
            raw_payload = _raw_payload({"raw_payload_json": row[0] if row else ""})
            raw_payload["official_email_evidence"] = evidence_metadata
            raw_payload_json = json.dumps(raw_payload, sort_keys=True, default=str)
        self.conn.execute(
            """UPDATE lead_discovery_results
               SET validation_status=?, history_crosscheck_result=?, linked_lead_id=?, rejection_reason=?,
                   evidence_url=COALESCE(NULLIF(?, ''), evidence_url),
                   evidence_snippet=COALESCE(NULLIF(?, ''), evidence_snippet),
                   evidence_method=COALESCE(NULLIF(?, ''), evidence_method),
                    contact_form_url=COALESCE(NULLIF(?, ''), contact_form_url),
                    official_match=COALESCE(?, official_match),
                    raw_payload_json=COALESCE(?, raw_payload_json),
                    location_status=CASE WHEN ? IN ('outside_active_city','location_review') THEN ? ELSE location_status END
               WHERE id=?""",
            (
                status,
                history_result,
                linked_lead_id,
                rejection_reason,
                evidence_url,
                evidence_snippet,
                evidence_method,
                contact_form_url,
                official_match,
                raw_payload_json,
                status,
                status,
                discovery_id,
            ),
        )

    def _audit_request(self, city_id: int, query_family: str, page: ProviderPage) -> None:
        self.conn.execute(
            """INSERT INTO provider_request_audit
               (active_city_id, provider, query_family, source_query, page_cursor, next_page_cursor,
                status, error, result_count, request_count, cost_units, requested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                city_id,
                page.provider,
                query_family,
                page.query,
                page.page_cursor,
                page.next_page_cursor,
                page.status,
                page.error,
                len(page.results),
                page.request_count,
                page.cost_units,
                page.fetched_at,
            ),
        )

    def _checkpoint_after_page(
        self,
        city_id: int,
        query_family: str,
        current_cursor: str,
        page: ProviderPage,
        new_places: int,
        duplicate_places: int,
    ) -> None:
        now = utc_now()
        next_cursor = page.next_page_cursor or ""
        no_new_expr = "consecutive_pages_without_new_place + 1" if new_places == 0 else "0"
        self.conn.execute(
            f"""UPDATE lead_discovery_query_state
                SET status='running', page_cursor=?, pages_processed=pages_processed+1,
                    results_seen=results_seen+?, new_unique_places=new_unique_places+?,
                    duplicate_places=duplicate_places+?, consecutive_pages_without_new_place={no_new_expr},
                    last_success_at=?, resume_state=?
                WHERE active_city_id=? AND provider=? AND query_family=?""",
            (
                next_cursor,
                len(page.results),
                new_places,
                duplicate_places,
                now,
                json.dumps({"page_cursor": next_cursor, "previous_cursor": current_cursor}),
                city_id,
                page.provider,
                query_family,
            ),
        )
        self.conn.execute(
            f"""UPDATE retail_city_queue
                SET active_provider=?, active_source=?, active_query_family=?, page_cursor=?,
                    pages_processed=pages_processed+1, results_seen=results_seen+?,
                    new_unique_places=new_unique_places+?, duplicate_places=duplicate_places+?,
                    consecutive_pages_without_new_place={no_new_expr}, last_success_at=?,
                    resume_state=?
                WHERE id=?""",
            (
                page.provider,
                page.provider,
                query_family,
                next_cursor,
                len(page.results),
                new_places,
                duplicate_places,
                now,
                json.dumps({"query_family": query_family, "page_cursor": next_cursor}),
                city_id,
            ),
        )

    def _complete_query(self, city_id: int, query_family: str) -> None:
        now = utc_now()
        self.conn.execute(
            """UPDATE lead_discovery_query_state SET status='completed', page_cursor='', completed_at=?
               WHERE active_city_id=? AND provider=? AND query_family=?""",
            (now, city_id, self.provider.provider_name, query_family),
        )
        self.conn.execute(
            """UPDATE retail_city_queue SET active_query_family=NULL, page_cursor='', resume_state='query_completed'
               WHERE id=?""",
            (city_id,),
        )

    def _record_provider_failure(self, city_id: int, query_family: str, page_cursor: str, status: str, error: str) -> None:
        now = utc_now()
        self.conn.execute(
            """UPDATE lead_discovery_query_state
               SET status=?, provider_errors=provider_errors+1, last_error=?, resume_state=?
               WHERE active_city_id=? AND provider=? AND query_family=?""",
            (status, error, json.dumps({"page_cursor": page_cursor, "status": status}), city_id, self.provider.provider_name, query_family),
        )
        self.conn.execute(
            """UPDATE retail_city_queue
               SET active_provider=?, active_source=?, active_query_family=?, page_cursor=?,
                   provider_errors=provider_errors+1, last_error=?, resume_state=?, last_success_at=COALESCE(last_success_at, ?)
               WHERE id=?""",
            (self.provider.provider_name, self.provider.provider_name, query_family, page_cursor, error, status, now, city_id),
        )
        self.conn.execute(
            """INSERT INTO provider_request_audit
               (active_city_id, provider, query_family, source_query, page_cursor, next_page_cursor,
                status, error, result_count, request_count, cost_units, requested_at)
               VALUES (?, ?, ?, ?, ?, '', ?, ?, 0, 0, 0, ?)""",
            (city_id, self.provider.provider_name, query_family, query_family, page_cursor, status, error, now),
        )

    def _all_places_queries_completed(self, city_id: int) -> bool:
        total = self.conn.execute(
            "SELECT COUNT(*) FROM lead_discovery_query_state WHERE active_city_id=? AND provider=?",
            (city_id, self.provider.provider_name),
        ).fetchone()[0]
        completed = self.conn.execute(
            """SELECT COUNT(*) FROM lead_discovery_query_state
               WHERE active_city_id=? AND provider=? AND status='completed'""",
            (city_id, self.provider.provider_name),
        ).fetchone()[0]
        return total == len(RETAIL_QUERY_FAMILIES) and completed == total

    def _mark_places_matrix_completed(self, city_id: int) -> None:
        city = self.conn.execute("SELECT web_directory_status FROM retail_city_queue WHERE id=?", (city_id,)).fetchone()
        if city and not dict(city).get("web_directory_status"):
            self.conn.execute(
                "UPDATE retail_city_queue SET web_directory_status='web_directory_provider_not_configured' WHERE id=?",
                (city_id,),
            )
        status = self.city_completion_status(city_id)
        if status == "places_matrix_completed_web_pending":
            self.conn.execute(
                """UPDATE retail_city_queue SET status='places_matrix_completed_web_pending',
                   completion_reason='web_directory_provider_not_configured', web_directory_status=COALESCE(web_directory_status, 'web_directory_provider_not_configured')
                   WHERE id=?""",
                (city_id,),
            )
            self._write_city_report(city_id, "places_matrix_completed_web_pending")

    def _write_city_report(self, city_id: int, status: str) -> None:
        totals = dict(
            self.conn.execute(
                """SELECT
                   COUNT(*) AS total_results,
                   SUM(CASE WHEN validation_status='lead_created' THEN 1 ELSE 0 END) AS leads_created,
                   SUM(CASE WHEN validation_status='website_lookup_pending' THEN 1 ELSE 0 END) AS website_lookup_pending,
                   SUM(CASE WHEN validation_status='history_blocked' THEN 1 ELSE 0 END) AS history_blocked
                   FROM lead_discovery_results WHERE active_city_id=?""",
                (city_id,),
            ).fetchone()
        )
        self.conn.execute(
            """INSERT INTO city_discovery_reports (active_city_id, status, totals_json, generated_at)
               VALUES (?, ?, ?, ?)""",
            (city_id, status, json.dumps(totals, sort_keys=True), datetime.now(timezone.utc).isoformat()),
        )


def _normalize_state(value: Any) -> str:
    text = str(value or "").strip().upper()
    aliases = {"TENNESSEE": "TN", "ARKANSAS": "AR", "KENTUCKY": "KY"}
    return aliases.get(text, text)


def _raw_payload(row: dict) -> dict:
    raw = row.get("raw_payload_json") or {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _with_scheme(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    return "https://" + text


def _scan_urls(website: str) -> list[tuple[str, str]]:
    base = _with_scheme(website)
    if not base:
        return []
    parsed = urllib.parse.urlsplit(base)
    root = urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc, "", "", ""))
    urls: list[tuple[str, str]] = []
    seen: set[str] = set()
    for path, method in WEBSITE_SCAN_PATHS:
        url = root if not path else urllib.parse.urljoin(root + "/", path)
        if url not in seen:
            seen.add(url)
            urls.append((url, method))
    return urls


def _fetch_official_pages(website: str, fetcher: Any) -> list[dict]:
    pages: list[dict] = []
    for url, method in _scan_urls(website):
        try:
            fetched = fetcher.fetch(url)
        except Exception:
            fetched = ""
        if isinstance(fetched, dict):
            text = str(fetched.get("text") or "")
            html = str(fetched.get("html") or "")
            final_url = str(fetched.get("final_url") or url)
            status = int(fetched.get("status") or 0)
            requested_domain = normalized_domain(url)
            final_domain = normalized_domain(final_url)
            same_party = bool(requested_domain and final_domain and (
                requested_domain == final_domain or requested_domain.endswith("." + final_domain) or final_domain.endswith("." + requested_domain)
            ))
            tls_success = bool(fetched.get("tls_verified", False))
            http_success = 200 <= status < 400
            if not http_success or not tls_success or not same_party:
                text = ""
        else:
            # A plain string cannot prove HTTP or TLS success and therefore
            # cannot be promoted as first-party evidence.
            text = ""
            html = ""
            final_url = url
        if text:
            pages.append({
                "url": final_url,
                "requested_url": url,
                "final_url": final_url,
                "method": method,
                "text": text,
                "html": html,
                "http_status": status,
                "http_success": http_success,
                "tls_success": tls_success,
                "fetched_at": str(fetched.get("fetched_at") or utc_now()),
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })
    return pages


def _business_tokens(name: str) -> list[str]:
    stop = {"the", "and", "store", "shop", "llc", "inc", "co", "company", "toy", "toys", "game", "games", "gift", "gifts"}
    return [token for token in re.findall(r"[a-z0-9]+", str(name or "").lower()) if len(token) >= 3 and token not in stop]


def _official_identity_match(row: dict, pages: list[dict]) -> bool:
    name = str(row.get("business_name") or "")
    tokens = _business_tokens(name)
    domain = str(row.get("normalized_domain") or normalized_domain(row.get("website") or "")).lower()
    if tokens and any(token in domain for token in tokens):
        return True
    haystack = " ".join(page["text"][:5000].lower() for page in pages)
    if name and name.lower() in haystack:
        return True
    return bool(tokens and sum(1 for token in tokens if token in haystack) >= min(2, len(tokens)))


def _clean_email(email: str) -> str:
    text = normalize_email(email)
    if not text or any(text.startswith(prefix) for prefix in NOISE_EMAIL_PREFIXES):
        return ""
    if text.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return ""
    return text


def _snippet_from_text(text: str, needle: str, max_len: int = 220) -> str:
    haystack = re.sub(r"\s+", " ", str(text or "")).strip()
    if not haystack:
        return ""
    target = str(needle or "").strip()
    if target:
        idx = haystack.lower().find(target.lower())
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(haystack), idx + len(target) + 120)
            return haystack[start:end][:max_len]
    return haystack[:max_len]


def _extract_email_evidence(pages: list[dict]) -> dict:
    candidates = []
    for page in pages:
        for match in EMAIL_RE.finditer(page["text"]):
            email = _clean_email(match.group(1))
            if not email:
                continue
            snippet = _snippet_from_text(page["text"], email)
            local = email.split("@", 1)[0].lower()
            method = page["method"]
            score = 0
            if any(word in method for word in ("wholesale", "vendor", "partnership")):
                score += 400
            if any(word in local for word in ("wholesale", "vendor", "partner", "partnership")):
                score += 300
            elif any(word in local for word in ("sales", "business", "contact")):
                score += 200
            elif local in {"info", "general"}:
                score += 100
            candidates.append((score, {
                "email": email,
                "url": page["url"],
                "snippet": snippet or email,
                "method": method,
                "evidence": {
                    "requested_url": page["requested_url"],
                    "final_url": page["final_url"],
                    "http_status": page["http_status"],
                    "http_success": page["http_success"],
                    "tls_success": page["tls_success"],
                    "fetched_at": page["fetched_at"],
                    "visible_text_excerpt": snippet or email,
                    "content_hash": page["content_hash"],
                    "email": email,
                    "email_source_type": _email_source_type(method, snippet),
                },
            }))
    return max(candidates, key=lambda item: item[0])[1] if candidates else {}


def _extract_contact_form_evidence(pages: list[dict]) -> dict:
    for page in pages:
        form = CONTACT_FORM_RE.search(page.get("html") or page["text"])
        url_is_contact = any(token in page["url"].lower() for token in ("contact", "support", "wholesale", "vendor", "partnership"))
        form_is_business_contact = bool(form and re.search(r"name=[\"']?(?:message|email|inquiry|contact)|(?:message|inquiry|contact).{0,40}(?:submit|send)", form.group(0), re.IGNORECASE | re.DOTALL))
        if url_is_contact and form_is_business_contact:
            return {
                "url": page["url"],
                "snippet": _snippet_from_text(page["text"], "contact") or "Official site contains a contact form.",
            }
    return {}


def _best_identity_page(pages: list[dict]) -> dict:
    for method in ("official_contact_page", "official_about_page", "official_wholesale_page", "official_vendor_page", "official_homepage"):
        for page in pages:
            if page["method"] == method:
                return page
    return pages[0]


def _email_source_type(evidence_method: str, snippet: str) -> str:
    method = str(evidence_method or "")
    if "wholesale" in method or "vendor" in method or "partnership" in method:
        return "wholesale_vendor_page"
    if "mailto:" in str(snippet or "").lower():
        return "official_mailto"
    return "official_page_visible"
