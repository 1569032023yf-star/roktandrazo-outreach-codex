"""Disabled provider — no tracking, no modifications to email pipeline."""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from .provider import EmailEngagementProvider, TrackingMessage


class DisabledProvider(EmailEngagementProvider):
    """No-op provider. All methods return safe defaults. Zero performance impact."""

    name = "disabled"

    def prepare_message(self, conn, **kwargs) -> Optional[TrackingMessage]:
        return None

    def activate_after_send(self, conn, tracking_message_id, **kwargs) -> bool:
        return False

    def cancel_message(self, conn, tracking_message_id, **kwargs) -> bool:
        return False

    def record_open(self, conn, token_hash, **kwargs) -> bool:
        return False

    def record_click(self, conn, token_hash, link_id, **kwargs) -> bool:
        return False

    def record_delivery(self, conn, tracking_message_id) -> bool:
        return False

    def record_bounce(self, conn, tracking_message_id, **kwargs) -> bool:
        return False

    def record_complaint(self, conn, tracking_message_id) -> bool:
        return False

    def record_unsubscribe(self, conn, tracking_message_id) -> bool:
        return False

    def record_reply(self, conn, tracking_message_id, **kwargs) -> bool:
        return False

    def get_message_engagement(self, conn, tracking_message_id) -> Dict[str, Any]:
        return {"provider": "disabled", "tracking_enabled": False, "events": []}

    def generate_token(self) -> str:
        return ""
