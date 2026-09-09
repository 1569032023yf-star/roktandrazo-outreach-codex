"""SQLite-backed single-city retail discovery state; no network or project imports."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

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
    conn.execute("""UPDATE retail_city_queue SET status='search_matrix_exhausted', completed_at=?,
        completion_reason='search_matrix_exhausted' WHERE id=? AND status IN ('active','validating','paused_by_runtime_limit')""",
        (datetime.now(timezone.utc).isoformat(), city_id))
    return conn.total_changes > 0
