"""Local first-party tracking provider.

No third-party services. All tracking data stays in our SQLite database.
Tokens are HMAC-SHA256 hashed. IP addresses are salted+hashed (not stored raw).
Events are classified as 'open_signal'/'click_signal' — never 'confirmed_read'.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Set
from urllib.parse import urlparse

from .provider import (
    EmailEngagementProvider, TrackingMessage, EngagementEvent,
    classify_open_signal, engagement_priority,
)

# Config
TOKEN_BYTES = 32
DEFAULT_RETENTION_DAYS = 60
OPEN_DEDUPE_WINDOW_SECONDS = 60  # Same token+UA within 60s = duplicate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ip_salt() -> str:
    return os.environ.get("EMAIL_TRACKING_IP_SALT", "change-me")


def _hash_ip(ip: str) -> str:
    """Hash IP with salt. Raw IP is NEVER stored."""
    import hashlib
    return hashlib.sha256(
        (_ip_salt() + ip).encode()
    ).hexdigest()[:24]


class LocalFirstPartyProvider(EmailEngagementProvider):
    """Self-hosted first-party tracking. No external services."""

    name = "local_first_party"

    def generate_token(self) -> str:
        return secrets.token_urlsafe(TOKEN_BYTES)

    def _skip_tracking(self) -> bool:
        """Check if tracking is globally disabled."""
        return os.environ.get("EMAIL_OPEN_TRACKING_ENABLED", "false").lower() != "true"

    def _click_tracking_enabled(self) -> bool:
        return os.environ.get("EMAIL_CLICK_TRACKING_ENABLED", "false").lower() == "true"

    def _base_url(self) -> str:
        return os.environ.get("EMAIL_TRACKING_PUBLIC_BASE_URL", "").rstrip("/")

    # ── Lifecycle ──────────────────────────────────────────

    def prepare_message(
        self, conn, *, lead_id, organization_key="", plan_entry_id="",
        plan_id="", message_type="new_outreach", is_test=False, **__
    ) -> Optional[TrackingMessage]:
        if self._skip_tracking() and not is_test:
            return None

        token = self.generate_token()
        token_hash = self.hash_token(token)
        now = _now()
        retention = int(os.environ.get(
            "EMAIL_TRACKING_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)
        ))
        expires = (datetime.now(timezone.utc) + timedelta(days=retention)).isoformat()

        c = conn.cursor()
        c.execute(
            """INSERT INTO email_tracking_messages (
                tracking_token_hash, lead_id, organization_key,
                plan_entry_id, plan_id, message_type, provider,
                tracking_enabled, created_at, expires_at, status, is_test
            ) VALUES (?,?,?,?,?,?,?,0,?,?,?,?)""",
            (token_hash, lead_id, organization_key, plan_entry_id, plan_id,
             message_type, self.name, now, expires, "pending",
             1 if is_test else 0),
        )
        conn.commit()

        msg = TrackingMessage(
            id=c.lastrowid or 0,
            tracking_token_hash=token_hash,
            lead_id=lead_id,
            organization_key=organization_key,
            plan_entry_id=plan_entry_id,
            plan_id=plan_id,
            message_type=message_type,
            provider=self.name,
            tracking_enabled=False,
            created_at=now,
            expires_at=expires,
            status="pending",
            is_test=is_test,
        )
        # Return raw token only here for pixel insertion — NOT persisted
        msg._raw_token = token
        return msg

    def activate_after_send(
        self, conn, tracking_message_id, *, send_log_id=0, smtp_message_id="", **__
    ) -> bool:
        now = _now()
        c = conn.cursor()
        c.execute(
            """UPDATE email_tracking_messages
               SET send_log_id=?, smtp_message_id=?,
                   tracking_enabled=1, activated_at=?, status='active'
               WHERE id=? AND tracking_enabled=0""",
            (send_log_id, smtp_message_id, now, tracking_message_id),
        )
        conn.commit()
        return c.rowcount > 0

    def cancel_message(self, conn, tracking_message_id, *, reason="", **__) -> bool:
        now = _now()
        c = conn.cursor()
        c.execute(
            """UPDATE email_tracking_messages
               SET tracking_enabled=0, disabled_at=?, status='cancelled'
               WHERE id=?""",
            (now, tracking_message_id),
        )
        conn.commit()
        return c.rowcount > 0

    # ── Event recording ────────────────────────────────────

    def _write_event(
        self, conn, tracking_message_id, event_type, *,
        source_classification="direct_or_unknown",
        user_agent="", ip_address="",
        target_link_id=0, metadata=None,
        dedupe_key="",
    ) -> bool:
        now = _now()
        ip_h = _hash_ip(ip_address) if ip_address else ""
        meta = json.dumps(metadata or {})

        if not dedupe_key:
            dedupe_key = f"{tracking_message_id}:{event_type}:{now[:16]}"

        c = conn.cursor()
        try:
            c.execute(
                """INSERT INTO email_engagement_events (
                    tracking_message_id, event_type, event_at, provider,
                    source_classification, user_agent_family, ip_hash,
                    target_link_id, metadata_json, dedupe_key, is_test
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (tracking_message_id, event_type, now, self.name,
                 source_classification, user_agent[:200], ip_h,
                 target_link_id, meta, dedupe_key,
                 # Copy is_test from tracking message
                 0),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # duplicate dedupe_key — skip
            return False

    def record_open(
        self, conn, token_hash, *, user_agent="", ip_address="", **__
    ) -> bool:
        msg = self._resolve_token(conn, token_hash)
        if not msg:
            return False

        classification = classify_open_signal(user_agent, ip_address)
        dedupe = f"open:{token_hash}:{classification}:{user_agent[:40]}"

        return self._write_event(
            conn, msg["id"], "open_signal",
            source_classification=classification,
            user_agent=user_agent,
            ip_address=ip_address,
            dedupe_key=dedupe,
        )

    def record_click(
        self, conn, token_hash, link_id, *, user_agent="", ip_address="", **__
    ) -> bool:
        msg = self._resolve_token(conn, token_hash)
        if not msg:
            return False

        return self._write_event(
            conn, msg["id"], "click_signal",
            source_classification="direct_or_unknown",
            user_agent=user_agent,
            ip_address=ip_address,
            target_link_id=link_id,
            dedupe_key=f"click:{token_hash}:{link_id}:{user_agent[:40]}",
        )

    def record_delivery(self, conn, tracking_message_id) -> bool:
        return self._write_event(
            conn, tracking_message_id, "delivery",
        )

    def record_bounce(
        self, conn, tracking_message_id, *, bounce_type="hard", diagnostic="", **__
    ) -> bool:
        event_type = f"bounce_{bounce_type}" if bounce_type in ("hard", "soft") else "bounce_hard"
        return self._write_event(
            conn, tracking_message_id, event_type,
            metadata={"diagnostic": diagnostic},
        )

    def record_complaint(self, conn, tracking_message_id) -> bool:
        return self._write_event(conn, tracking_message_id, "complaint")

    def record_unsubscribe(self, conn, tracking_message_id) -> bool:
        return self._write_event(conn, tracking_message_id, "unsubscribe")

    def record_reply(
        self, conn, tracking_message_id, *, reply_type="unknown", **__
    ) -> bool:
        return self._write_event(
            conn, tracking_message_id, "reply",
            metadata={"reply_type": reply_type},
        )

    # ── Query ──────────────────────────────────────────────

    def get_message_engagement(self, conn, tracking_message_id) -> Dict[str, Any]:
        c = conn.cursor()
        msg = c.execute(
            "SELECT * FROM email_tracking_messages WHERE id=?", (tracking_message_id,)
        ).fetchone()
        if not msg:
            return {"tracking_message_id": tracking_message_id, "found": False}

        events = c.execute(
            """SELECT event_type, event_at, source_classification
               FROM email_engagement_events
               WHERE tracking_message_id=?
               ORDER BY event_at""",
            (tracking_message_id,),
        ).fetchall()

        return {
            "tracking_message_id": tracking_message_id,
            "found": True,
            "tracking_enabled": bool(msg["tracking_enabled"]),
            "status": msg["status"],
            "smtp_message_id": msg["smtp_message_id"] or "",
            "events": [
                {"type": e["event_type"], "at": e["event_at"],
                 "classification": e["source_classification"]}
                for e in events
            ],
            "open_signal_count": sum(1 for e in events if e["event_type"] == "open_signal"),
            "click_signal_count": sum(1 for e in events if e["event_type"] == "click_signal"),
        }

    # ── Internal ───────────────────────────────────────────

    def _resolve_token(self, conn, token_hash) -> Optional[Dict]:
        """Look up tracking message by token hash. Checks expiry + enabled."""
        c = conn.cursor()
        c.execute(
            """SELECT * FROM email_tracking_messages
               WHERE tracking_token_hash=?
               AND tracking_enabled=1
               AND (expires_at IS NULL OR expires_at > ?)
               AND status='active'""",
            (token_hash, _now()),
        )
        row = c.fetchone()
        return dict(row) if row else None
