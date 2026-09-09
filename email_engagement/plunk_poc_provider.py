"""Plunk PoC provider — isolated evaluation only, NOT production.

All events route to a SEPARATE plunk_poc_events table.
Never touches production SMTP, send_log, or final_send_plan.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .provider import EmailEngagementProvider, TrackingMessage


PLUNK_API_URL = os.environ.get("PLUNK_API_URL", "http://localhost:3000")


class PlunkPocProvider(EmailEngagementProvider):
    """Isolated Plunk proof-of-concept. Zero production impact."""

    name = "plunk_poc"

    def generate_token(self) -> str:
        return secrets.token_urlsafe(24)

    # ── Lifecycle ──────────────────────────────────────────

    def prepare_message(self, conn, **kwargs) -> Optional[TrackingMessage]:
        """Create PoC tracking record in plunk_poc_events table."""
        token = self.generate_token()
        token_hash = self.hash_token(token)
        now = datetime.now(timezone.utc).isoformat()

        c = conn.cursor()
        c.execute(
            """INSERT INTO plunk_poc_events (
                tracking_token_hash, lead_id, organization_key,
                plan_entry_id, plan_id, message_type, provider,
                tracking_enabled, created_at, status, is_test
            ) VALUES (?,?,?,?,?,?,?,0,?,?,?)""",
            (token_hash,
             kwargs.get("lead_id", 0),
             kwargs.get("organization_key", ""),
             kwargs.get("plan_entry_id", ""),
             kwargs.get("plan_id", ""),
             kwargs.get("message_type", "new_outreach"),
             self.name,
             now,
             "pending",
             1 if kwargs.get("is_test", False) else 0),
        )
        conn.commit()

        msg = TrackingMessage(
            id=c.lastrowid or 0,
            tracking_token_hash=token_hash,
            provider=self.name,
            tracking_enabled=False,
            status="pending",
            is_test=True,
        )
        msg._raw_token = token
        return msg

    def activate_after_send(
        self, conn, tracking_message_id, *, send_log_id=0, smtp_message_id="", **__
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        c = conn.cursor()
        c.execute(
            """UPDATE plunk_poc_events
               SET send_log_id=?, smtp_message_id=?,
                   tracking_enabled=1, activated_at=?, status='active'
               WHERE id=?""",
            (send_log_id, smtp_message_id, now, tracking_message_id),
        )
        conn.commit()
        return c.rowcount > 0

    def cancel_message(self, conn, tracking_message_id, **kwargs) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        c = conn.cursor()
        c.execute(
            "UPDATE plunk_poc_events SET tracking_enabled=0, status='cancelled' WHERE id=?",
            (tracking_message_id,),
        )
        conn.commit()
        return c.rowcount > 0

    # ── Event recording — PoC table only ───────────────────

    def _poc_event(self, conn, tracking_message_id, event_type):
        now = datetime.now(timezone.utc).isoformat()
        c = conn.cursor()
        c.execute(
            """UPDATE plunk_poc_events
               SET last_event_type=?, last_event_at=?, event_count=event_count+1
               WHERE id=?""",
            (event_type, now, tracking_message_id),
        )
        conn.commit()

    def record_open(self, conn, token_hash, **kwargs) -> bool:
        c = conn.cursor()
        c.execute(
            "SELECT id FROM plunk_poc_events WHERE tracking_token_hash=? AND tracking_enabled=1",
            (token_hash,),
        )
        row = c.fetchone()
        if row:
            self._poc_event(conn, row[0], "open_signal")
            return True
        return False

    def record_click(self, conn, token_hash, link_id, **kwargs) -> bool:
        c = conn.cursor()
        c.execute(
            "SELECT id FROM plunk_poc_events WHERE tracking_token_hash=? AND tracking_enabled=1",
            (token_hash,),
        )
        row = c.fetchone()
        if row:
            self._poc_event(conn, row[0], "click_signal")
            return True
        return False

    def record_delivery(self, conn, tracking_message_id) -> bool:
        self._poc_event(conn, tracking_message_id, "delivery")
        return True

    def record_bounce(self, conn, tracking_message_id, **kwargs) -> bool:
        self._poc_event(conn, tracking_message_id, "bounce")
        return True

    def record_complaint(self, conn, tracking_message_id) -> bool:
        self._poc_event(conn, tracking_message_id, "complaint")
        return True

    def record_unsubscribe(self, conn, tracking_message_id) -> bool:
        self._poc_event(conn, tracking_message_id, "unsubscribe")
        return True

    def record_reply(self, conn, tracking_message_id, **kwargs) -> bool:
        self._poc_event(conn, tracking_message_id, "reply")
        return True

    def get_message_engagement(self, conn, tracking_message_id) -> Dict[str, Any]:
        c = conn.cursor()
        row = c.execute(
            "SELECT * FROM plunk_poc_events WHERE id=?",
            (tracking_message_id,),
        ).fetchone()
        if not row:
            return {"found": False}
        return {
            "found": True,
            "status": row["status"],
            "event_count": row["event_count"],
            "last_event_type": row["last_event_type"],
            "last_event_at": row["last_event_at"],
        }
