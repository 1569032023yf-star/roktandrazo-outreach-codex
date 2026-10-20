"""Read-only, opt-in history adapter. No configured copy means UNKNOWN."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class HistoryChecker:
    def __init__(self, database: str | Path | None = None, *, development_copy: bool = False):
        self.database = Path(database).resolve() if database else None
        self.development_copy = bool(development_copy)
        if self.database and not self.development_copy:
            raise ValueError("history database must be explicitly identified as a development read-only copy")

    def __call__(self, candidate: dict) -> str:
        if not self.database or not self.database.is_file() or not self.development_copy:
            return "UNKNOWN"
        conn = None
        try:
            uri = self.database.as_uri() + "?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=2)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            from history_crosscheck import cross_check
            probe = {
                "store_name": candidate.get("brand_owner_name") or candidate.get("brand_name"),
                "official_website": candidate.get("official_website"),
                "email": candidate.get("business_email"),
                "city": "", "state": "",
            }
            outcome = cross_check(conn, probe)
            result = str(outcome.get("result", "UNKNOWN"))
            return result if result else "UNKNOWN"
        except Exception:
            return "UNKNOWN"
        finally:
            if conn is not None:
                conn.close()
