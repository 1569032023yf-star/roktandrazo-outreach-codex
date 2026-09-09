"""Development-only SAFE_FSP materialization; no sender consumes this table."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from campaign_eligible_v2 import review_campaign_eligible_v2


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS dev_safe_fsp (
        id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL,
        lead_id INTEGER NOT NULL,
        organization_key TEXT NOT NULL,
        email TEXT NOT NULL,
        v2_result_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(run_id, organization_key),
        UNIQUE(run_id, email)
    )""")


def materialize_dev_fsp(conn: sqlite3.Connection, lead_ids: list[int], mx_lookup: dict[str, str], run_id: str) -> dict:
    """Apply frozen V2/MX and persist only eligible rows in a dev-only table."""
    ensure_schema(conn)
    counts = {"evaluated": 0, "eligible": 0, "inserted": 0, "blocked": 0}
    reasons: dict[str, int] = {}
    for lead_id in sorted(set(int(item) for item in lead_ids)):
        row = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            continue
        lead = dict(row)
        result = review_campaign_eligible_v2(lead, {"conn": conn, "mx_lookup": mx_lookup})
        counts["evaluated"] += 1
        if not result["eligible"]:
            counts["blocked"] += 1
            for reason in result.get("blockers") or ["unknown"]:
                reasons[reason] = reasons.get(reason, 0) + 1
            continue
        counts["eligible"] += 1
        before = conn.total_changes
        conn.execute(
            """INSERT OR IGNORE INTO dev_safe_fsp
               (run_id,lead_id,organization_key,email,v2_result_json,created_at)
               VALUES (?,?,?,?,?,?)""",
            (run_id, lead_id, lead.get("organization_key") or "", lead.get("email") or "",
             json.dumps(result, sort_keys=True, default=str), datetime.now(timezone.utc).isoformat()),
        )
        counts["inserted"] += int(conn.total_changes > before)
    return {**counts, "rejection_reasons": reasons, "run_id": run_id}
