"""SQLite-backed single-city retail discovery state; no network or project imports."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlsplit

from outreach_control import DEFAULT_RETAIL_CITIES, RETAIL_QUERY_FAMILIES, RETAIL_SOURCES, all_city_completion_conditions_met


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def seed_default_queue(conn: sqlite3.Connection) -> None:
    conn.executemany("""INSERT OR IGNORE INTO retail_city_queue (city, state, priority, timezone, status)
        VALUES (?, ?, ?, ?, 'pending')""", DEFAULT_RETAIL_CITIES)


# NY 实验州第一轮城市清单（Upstate-first：small / regional / college / tourist，非 NYC 主导）。
# 按优先级升序；NYC / Long Island 不进入本轮（Major Metro 不自动获得高优先级）。
NY_FIRST_ROUND_CITIES: list[tuple[str, str, int, str]] = [
    ("Ithaca",            "NY", 1,  "America/New_York"),   # college town
    ("Saratoga Springs",  "NY", 2,  "America/New_York"),   # tourist town
    ("Cooperstown",       "NY", 3,  "America/New_York"),   # tourist town
    ("Lake Placid",       "NY", 4,  "America/New_York"),   # tourist town
    ("Oneonta",           "NY", 5,  "America/New_York"),   # college town
    ("New Paltz",         "NY", 6,  "America/New_York"),   # college town
    ("Corning",           "NY", 7,  "America/New_York"),   # small / regional
    ("Glens Falls",       "NY", 8,  "America/New_York"),   # small city
    ("Plattsburgh",       "NY", 9,  "America/New_York"),   # small / college
    ("Watertown",         "NY", 10, "America/New_York"),   # small city
    ("Utica",             "NY", 11, "America/New_York"),   # regional center
    ("Binghamton",        "NY", 12, "America/New_York"),   # regional / college
    ("Poughkeepsie",      "NY", 13, "America/New_York"),   # Hudson Valley regional
    ("Syracuse",          "NY", 14, "America/New_York"),   # regional center / college
    ("Albany",            "NY", 15, "America/New_York"),   # state capital / regional
    ("Rochester",         "NY", 16, "America/New_York"),   # regional center
    ("Buffalo",           "NY", 17, "America/New_York"),   # regional center
]


def seed_state_cities(conn: sqlite3.Connection, state: str, cities: list[tuple[str, str, int, str]]) -> int:
    """State-scoped seed: INSERT OR IGNORE per state; returns number of new rows."""
    before = conn.total_changes
    conn.executemany("""INSERT OR IGNORE INTO retail_city_queue (city, state, priority, timezone, status)
        VALUES (?, ?, ?, ?, 'pending')""", cities)
    conn.commit()
    return conn.total_changes - before


def _state_filter(state: str | None) -> tuple[str, list[object]]:
    return (" AND state=?" if state else "", [state] if state else [])


def active_city(conn: sqlite3.Connection, state: str | None = None) -> dict | None:
    st_clause, st_args = _state_filter(state)
    row = conn.execute(f"""SELECT * FROM retail_city_queue
        WHERE status IN ('active','validating','paused_by_runtime_limit','places_matrix_completed_web_pending',
                         'CONTACT_ENRICHMENT_IN_PROGRESS','DISCOVERY_IN_PROGRESS','QUEUED'){st_clause}
        ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'CONTACT_ENRICHMENT_IN_PROGRESS' THEN 1 WHEN 'DISCOVERY_IN_PROGRESS' THEN 2 ELSE 3 END, priority, id
        LIMIT 1""", st_args).fetchone()
    return dict(row) if row else None


def activate_next_city(conn: sqlite3.Connection, state: str | None = None) -> dict:
    st_clause, st_args = _state_filter(state)
    current = active_city(conn, state=state)
    if current:
        if current['status'] in ('paused_by_runtime_limit', 'places_matrix_completed_web_pending'):
            conn.execute("UPDATE retail_city_queue SET status='active' WHERE id=?", (current['id'],))
            return dict(conn.execute("SELECT * FROM retail_city_queue WHERE id=?", (current['id'],)).fetchone())
        return current
    paused = conn.execute(f"SELECT * FROM retail_city_queue WHERE status='paused_by_runtime_limit'{st_clause} ORDER BY priority, id LIMIT 1", st_args).fetchone()
    if paused:
        conn.execute("UPDATE retail_city_queue SET status='active' WHERE id=?", (paused['id'],))
        return dict(conn.execute("SELECT * FROM retail_city_queue WHERE id=?", (paused['id'],)).fetchone())
    row = conn.execute(f"""SELECT * FROM retail_city_queue
        WHERE status IN ('pending','QUEUED','CONTACT_ENRICHMENT_IN_PROGRESS','DISCOVERY_IN_PROGRESS'){st_clause}
        ORDER BY priority, id LIMIT 1""", st_args).fetchone()
    if not row:
        # Check if current city is active with enrichment status (state-scoped)
        current_check = conn.execute(f"SELECT * FROM retail_city_queue WHERE status='CONTACT_ENRICHMENT_IN_PROGRESS'{st_clause} ORDER BY priority LIMIT 1", st_args).fetchone()
        if current_check:
            row = current_check
        else:
            raise RuntimeError('no pending retail city')
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE retail_city_queue SET status='active', started_at=COALESCE(started_at, ?) WHERE id=?", (now, row['id']))
    return dict(conn.execute("SELECT * FROM retail_city_queue WHERE id=?", (row['id'],)).fetchone())


def search_queries(city_row: dict) -> list[str]:
    return [f"{family} {city_row['city']} {city_row['state']}" for family in RETAIL_QUERY_FAMILIES]


def checkpoint(conn: sqlite3.Connection, city_id: int, query_family: str, source: str, page_cursor: str,
               counters: dict[str, int] | None = None, paused: bool = False) -> None:
    if query_family not in RETAIL_QUERY_FAMILIES or source not in RETAIL_SOURCES:
        raise ValueError('unknown query family or source')
    counters = counters or {}
    allowed = {'discovered_count', 'unique_domain_count', 'official_site_count', 'public_email_count',
               'strict_a0_count', 'manual_review_count', 'contact_form_count', 'duplicate_count', 'rejected_count',
               'pages_processed', 'results_seen', 'new_unique_places', 'duplicate_places', 'provider_errors',
               'consecutive_pages_without_new_place'}
    table_cols = _columns(conn, 'retail_city_queue')
    updates = ['active_query_family=?', 'active_source=?', 'page_cursor=?', 'status=?']
    values: list[object] = [query_family, source, page_cursor, 'paused_by_runtime_limit' if paused else 'active']
    if 'active_provider' in table_cols:
        updates.insert(2, 'active_provider=?')
        values.insert(2, source)
    for name, value in counters.items():
        if name not in allowed:
            raise ValueError(f'unsupported counter: {name}')
        if name not in table_cols:
            continue
        updates.append(f'{name}=?')
        values.append(value)
    values.append(city_id)
    conn.execute(f"UPDATE retail_city_queue SET {', '.join(updates)} WHERE id=?", values)


def complete_if_exhausted(conn: sqlite3.Connection, city_id: int, checks: dict[str, bool]) -> bool:
    if not all_city_completion_conditions_met(checks):
        return False
    # ``places_matrix_completed_web_pending`` is a holding state, not proof
    # that more Places work exists.  It may become terminal only after every
    # fail-closed completion check below has passed.
    cursor = conn.execute("""UPDATE retail_city_queue SET status='search_matrix_exhausted', completed_at=?,
        completion_reason='search_matrix_exhausted' WHERE id=? AND status IN
        ('active','validating','paused_by_runtime_limit','places_matrix_completed_web_pending')""",
        (datetime.now(timezone.utc).isoformat(), city_id))
    return cursor.rowcount == 1


def city_completion_checks(conn: sqlite3.Connection, city_id: int, provider: str) -> dict[str, bool]:
    """Derive the existing completion contract from durable queue/staging state.

    This is deliberately conservative: absent rows, unknown directory state,
    retryable network outcomes, and every outstanding staging/recovery item
    keep the city active.  It performs no lead or evidence mutation.
    """
    queue = conn.execute("SELECT * FROM retail_city_queue WHERE id=?", (city_id,)).fetchone()
    if not queue:
        return {key: False for key in _COMPLETION_KEYS}
    city = dict(queue)
    query_rows = conn.execute(
        """SELECT status, page_cursor, pages_processed, consecutive_pages_without_new_place, completed_at
           FROM lead_discovery_query_state WHERE active_city_id=? AND provider=?""",
        (city_id, provider),
    ).fetchall()
    query_total = len(query_rows)
    query_completed = sum(1 for row in query_rows if row["status"] == "completed")
    queries_complete = (
        int(query_total or 0) == len(RETAIL_QUERY_FAMILIES)
        and int(query_completed or 0) == int(query_total or 0)
    )
    # Canonical Discovery is the source of truth: it writes ``completed`` only
    # after no next cursor or after two consecutive pages with no new unique
    # place.  Require the accompanying durable checkpoint, but never confuse
    # raw provider result_count with new unique places (duplicate pages are a
    # legitimate exhaustion path).
    query_exhaustion = queries_complete and all(
        str(row["page_cursor"] or "") == ""
        and bool(row["completed_at"])
        and int(row["pages_processed"] or 0) > 0
        for row in query_rows
    )
    two_empty_pages = query_exhaustion
    # Repository history defines no independently persisted city-level
    # three-batch measure.  provider_request_audit.result_count is raw provider
    # output, not new_unique_places, and must not create a contradictory gate.
    # Keep the legacy required key compatible with the only durable, canonical
    # exhaustion contract rather than fabricate historical batch progress.
    last_three_batches_empty = query_exhaustion
    web_reason_complete = city.get("web_directory_status") in {
        "completed", "not_required", "not_applicable", "web_directory_provider_not_configured",
    }
    staged_pending = conn.execute(
        """SELECT 1 FROM lead_discovery_results WHERE active_city_id=?
           AND validation_status IN
           ('validation_pending','history_check_pending','website_lookup_pending',
            'email_extraction_pending') LIMIT 1""",
        (city_id,),
    ).fetchone() is not None
    retryable_network = conn.execute(
        """SELECT 1 FROM lead_discovery_results WHERE active_city_id=?
           AND (COALESCE(rejection_reason, '') LIKE 'website_resolution:network_retry:%'
                OR COALESCE(rejection_reason, '') LIKE 'website_resolution:network_error:%')
           LIMIT 1""",
        (city_id,),
    ).fetchone() is not None
    candidate_rows = conn.execute(
        """SELECT d.*, l.email AS linked_email, l.status AS linked_status,
                  l.review_status AS linked_review_status,
                  l.review_reason_code AS linked_review_reason_code,
                  l.review_reason_detail AS linked_review_reason_detail
           FROM lead_discovery_results d LEFT JOIN leads l ON l.id=d.linked_lead_id
           WHERE d.active_city_id=?""",
        (city_id,),
    ).fetchall()
    retryable_manual = any(_manual_review_retryable(dict(row)) for row in candidate_rows)
    linked_retry = any(_linked_backlog_retryable(dict(row)) for row in candidate_rows)
    no_open_work = not (staged_pending or retryable_network or retryable_manual or linked_retry)
    return {
        "all_query_families": query_exhaustion,
        "all_sources_or_reasons": web_reason_complete,
        "pagination_complete": query_exhaustion,
        "two_empty_pages": two_empty_pages,
        "all_candidates_classified": no_open_work,
        "no_unprocessed_candidates": no_open_work,
        "official_site_recheck": no_open_work,
        "review_recovery": no_open_work,
        "last_three_batches_empty": last_three_batches_empty,
    }


def _manual_review_retryable(row: dict) -> bool:
    """Keep only records reachable by an existing automatic retry lane open."""
    if row.get("validation_status") != "manual_review_needed":
        return False
    # The normal resolver owns unlinked, website-less manual-review rows.
    if row.get("linked_lead_id") is None:
        return not str(row.get("website") or "").strip()
    return _linked_backlog_retryable(row)


def _linked_backlog_retryable(row: dict) -> bool:
    """Conservative durable mirror of the existing linked-backlog entry gate.

    Terminal manual-review outcomes (for example hygiene failures and identity
    reviews) are intentionally excluded.  This function performs no network,
    no lead mutation, and no evidence mutation.
    """
    try:
        retry = json.loads(str(row.get("raw_payload_json") or "{}"))
    except (TypeError, ValueError):
        retry = {}
    if (retry.get("linked_backlog_retry") or {}).get("automation_terminal_outcome") == "access_unreachable":
        return False
    if row.get("linked_lead_id") is None or str(row.get("linked_email") or "").strip():
        return False
    if row.get("linked_status") not in {"new", "manual_review_needed"}:
        return False
    if row.get("linked_review_status") in {"rejected", "identity_review"}:
        return False
    if row.get("linked_review_reason_code") not in {
        "website_lookup_required", "review_recovery", "no_public_email_or_form",
    }:
        return False
    if row.get("validation_status") not in {
        "validation_pending", "history_check_pending", "website_lookup_pending",
        "email_extraction_pending", "manual_review_needed", "review_recovery",
    }:
        return False
    reason = str(row.get("rejection_reason") or "")
    if reason and not reason.startswith((
        "website_resolution:not_found:", "website_resolution:network_error:", "website_resolution:network_retry:",
    )):
        return False
    if row.get("history_crosscheck_result") in {
        "suppressed_or_unsubscribed", "bounced", "previously_sent", "exact_duplicate", "rejected",
    }:
        return False
    website = str(row.get("website") or "").strip()
    if website and urlsplit(website).scheme not in {"http", "https"}:
        return False
    if (row.get("linked_review_reason_code") == "review_recovery"
            and row.get("linked_review_reason_detail") != "review_recovery=official_site_unavailable"):
        return False
    if row.get("linked_review_reason_code") == "no_public_email_or_form" and not row.get("official_match"):
        return False
    return True


_COMPLETION_KEYS = frozenset({
    "all_query_families", "all_sources_or_reasons", "pagination_complete", "two_empty_pages",
    "all_candidates_classified", "no_unprocessed_candidates", "official_site_recheck",
    "review_recovery", "last_three_batches_empty",
})


def complete_active_city_if_exhausted(conn: sqlite3.Connection, provider: str, state: str | None = None) -> bool:
    """Terminalize the active city only when its durable, fail-closed checks pass."""
    current = active_city(conn, state=state)
    if not current:
        return False
    return complete_if_exhausted(conn, int(current["id"]), city_completion_checks(conn, int(current["id"]), provider))
