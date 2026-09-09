"""
EmailEngagementProvider — pluggable email tracking interface.

Default: disabled (no tracking).
Select via: EMAIL_ENGAGEMENT_PROVIDER=disabled|local_first_party|plunk_poc
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Protocol
from urllib.parse import urlparse


# ── Data classes ──────────────────────────────────────────────

@dataclass
class TrackingMessage:
    """A tracking record bound to one email send."""
    id: int = 0
    tracking_token_hash: str = ""
    lead_id: int = 0
    organization_key: str = ""
    plan_entry_id: str = ""
    plan_id: str = ""
    send_log_id: int = 0
    smtp_message_id: str = ""
    message_type: str = "new_outreach"
    provider: str = "disabled"
    tracking_enabled: bool = False
    created_at: str = ""
    activated_at: str = ""
    expires_at: str = ""
    disabled_at: str = ""
    status: str = "pending"
    is_test: bool = False


@dataclass
class EngagementEvent:
    """A single engagement event (open, click, bounce, etc.)."""
    tracking_message_id: int = 0
    event_type: str = ""
    event_at: str = ""
    provider: str = ""
    source_classification: str = "direct_or_unknown"
    user_agent_family: str = ""
    ip_hash: str = ""
    target_link_id: int = 0
    metadata_json: str = "{}"
    dedupe_key: str = ""
    is_test: bool = False


# ── Abstract Provider ─────────────────────────────────────────

class EmailEngagementProvider(ABC):
    """Pluggable email engagement tracking.

    All tracking is opt-in. Provider must be explicitly selected
    via EMAIL_ENGAGEMENT_PROVIDER environment variable.
    Default is 'disabled'.
    """

    name: str = "base"

    # ── Lifecycle ──────────────────────────────────────────

    @abstractmethod
    def prepare_message(
        self,
        conn: sqlite3.Connection,
        *,
        lead_id: int,
        organization_key: str = "",
        plan_entry_id: str = "",
        plan_id: str = "",
        message_type: str = "new_outreach",
        is_test: bool = False,
    ) -> Optional[TrackingMessage]:
        """Create a pending tracking record BEFORE SMTP send.

        tracking_enabled=False until activate_after_send() is called.
        Returns None if tracking is disabled for this message.
        """
        ...

    @abstractmethod
    def activate_after_send(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
        *,
        send_log_id: int,
        smtp_message_id: str = "",
    ) -> bool:
        """Activate tracking AFTER successful SMTP send.

        Binds send_log_id + smtp_message_id.
        Sets tracking_enabled=True + activated_at=now.
        """
        ...

    @abstractmethod
    def cancel_message(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
        *,
        reason: str = "",
    ) -> bool:
        """Cancel tracking for a message that was NOT sent.

        Sets tracking_enabled=False + disabled_at=now.
        """
        ...

    # ── Event recording ────────────────────────────────────

    @abstractmethod
    def record_open(
        self,
        conn: sqlite3.Connection,
        token_hash: str,
        *,
        user_agent: str = "",
        ip_address: str = "",
        source_classification: str = "direct_or_unknown",
    ) -> bool:
        """Record an open_signal event. Returns True if event was new."""
        ...

    @abstractmethod
    def record_click(
        self,
        conn: sqlite3.Connection,
        token_hash: str,
        link_id: int,
        *,
        user_agent: str = "",
        ip_address: str = "",
    ) -> bool:
        """Record a click_signal event."""
        ...

    @abstractmethod
    def record_delivery(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
    ) -> bool:
        """Record a delivery event."""
        ...

    @abstractmethod
    def record_bounce(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
        *,
        bounce_type: str = "hard",
        diagnostic: str = "",
    ) -> bool:
        """Record a bounce event. bounce_type: hard/soft/policy/permanent."""
        ...

    @abstractmethod
    def record_complaint(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
    ) -> bool:
        """Record an abuse complaint event."""
        ...

    @abstractmethod
    def record_unsubscribe(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
    ) -> bool:
        """Record an unsubscribe event."""
        ...

    @abstractmethod
    def record_reply(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
        *,
        reply_type: str = "unknown",
    ) -> bool:
        """Record a reply event."""
        ...

    # ── Query ──────────────────────────────────────────────

    @abstractmethod
    def get_message_engagement(
        self,
        conn: sqlite3.Connection,
        tracking_message_id: int,
    ) -> Dict[str, Any]:
        """Return engagement summary for a message."""
        ...

    # ── Token ──────────────────────────────────────────────

    @abstractmethod
    def generate_token(self) -> str:
        """Generate a cryptographically secure random token."""
        ...

    def hash_token(self, token: str) -> str:
        """Hash a token for storage. Uses HMAC-SHA256 with pepper.

        P7：pepper 不再有硬编码默认值；未配置 → fail-closed（抛错），
        绝不回退到 change-me-in-production 之类的固定值。
        """
        pepper = os.environ.get("BD_TRACKING_PEPPER") or os.environ.get("EMAIL_TRACKING_PEPPER") or ""
        if not pepper:
            raise RuntimeError(
                "EMAIL_TRACKING_PEPPER/BD_TRACKING_PEPPER 未配置：token 哈希不可用（fail-closed）。"
            )
        return hmac.new(
            pepper.encode(), token.encode(), hashlib.sha256
        ).hexdigest()

    # ── HTML helpers ───────────────────────────────────────

    def build_pixel_html(self, token: str, base_url: str) -> str:
        """Build tracking pixel <img> tag. Only for HTML emails."""
        if not base_url:
            return ""
        return (
            f'<img src="{base_url.rstrip("/")}/o/{token}.gif" '
            f'width="1" height="1" alt="" '
            f'style="display:none;visibility:hidden" />'
        )

    def build_tracked_link(self, token: str, link_id: int, base_url: str) -> str:
        """Build tracked click URL."""
        if not base_url:
            return ""
        return f'{base_url.rstrip("/")}/c/{token}/{link_id}'


# ── Provider factory ──────────────────────────────────────────

def load_provider(name: str | None = None) -> EmailEngagementProvider:
    """Load provider by name. Default from env, fallback to disabled."""
    if name is None:
        name = os.environ.get("EMAIL_ENGAGEMENT_PROVIDER", "disabled")

    if name == "disabled" or name == "":
        from email_engagement.disabled_provider import DisabledProvider
        return DisabledProvider()
    elif name == "local_first_party":
        from email_engagement.local_first_party_provider import LocalFirstPartyProvider
        return LocalFirstPartyProvider()
    elif name == "plunk_poc":
        from email_engagement.plunk_poc_provider import PlunkPocProvider
        return PlunkPocProvider()
    else:
        raise ValueError(f"Unknown EMAIL_ENGAGEMENT_PROVIDER: {name}")


# ── Utility ───────────────────────────────────────────────────

def classify_open_signal(
    user_agent: str,
    ip_address: str = "",
    *,
    known_proxy_asns: set[str] | None = None,
) -> str:
    """Heuristic classification of open_signal source.

    NEVER call this 'confirmed_read' or 'human_open'.
    Classification is statistical, not deterministic.
    """
    ua = user_agent.lower()

    # Apple Mail Privacy Protection
    if "darwin" in ua or "apple" in ua or "mozilla/5.0" in ua:
        # Apple MPP pre-fetches images via proxy
        if any(kw in ua for kw in ("mac os x", "iphone", "ipad", "cfnetwork")):
            return "likely_apple_mpp"

    # Google image proxy
    if "googleimageproxy" in ua or "google-proxy" in ua:
        return "likely_google_proxy"

    # Known security scanners
    scanner_kws = (
        "security", "scanner", "curl", "wget", "python-requests",
        "go-http-client", "axios", "node-fetch", "java",
        "bot", "spider", "crawler",
    )
    if any(kw in ua for kw in scanner_kws):
        return "likely_security_scanner"

    return "direct_or_unknown"


def engagement_priority(event_type: str) -> int:
    """Return numeric priority: higher = more engagement."""
    return {
        "reply": 100,
        "business_link_click": 80,
        "click_signal": 70,
        "multiple_non_proxy_open": 50,
        "single_open_signal": 30,
        "delivery_only": 10,
        "bounce_soft": -50,
        "bounce_hard": -100,
        "complaint": -200,
        "unsubscribe": -300,
    }.get(event_type, 0)
