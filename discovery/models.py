"""Provider-neutral discovery models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import socket
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlaceSearchResult:
    provider: str
    provider_result_id: str
    place_id: str
    business_name: str
    formatted_address: str
    city: str
    state: str
    country: str = ""
    postal_code: str = ""
    phone: str = ""
    website: str = ""
    business_status: str = ""
    primary_type: str = ""
    types: list[str] = field(default_factory=list)
    source_query: str = ""
    source_url: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    next_page_cursor: str = ""
    fetched_at: str = field(default_factory=utc_now)
    location_lat: float | None = None
    location_lng: float | None = None

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderPage:
    provider: str
    query: str
    city: str
    state: str
    page_cursor: str
    results: list[PlaceSearchResult] = field(default_factory=list)
    next_page_cursor: str = ""
    status: str = "ok"
    error: str = ""
    request_count: int = 0
    cost_units: int = 0
    fetched_at: str = field(default_factory=utc_now)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


# Fixed, redacted Provider diagnostic wire contract.
class ErrorCode(str, Enum):
    BROWSER_LAUNCH_ERROR = "BROWSER_LAUNCH_ERROR"
    BROWSER_PROCESS_EXITED = "BROWSER_PROCESS_EXITED"
    PROXY_CONNECTION_ERROR = "PROXY_CONNECTION_ERROR"
    DNS_RESOLUTION_ERROR = "DNS_RESOLUTION_ERROR"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    SOURCE_RATE_LIMITED = "SOURCE_RATE_LIMITED"
    SOURCE_ACCESS_RESTRICTED = "SOURCE_ACCESS_RESTRICTED"
    SOURCE_VERIFICATION_REQUIRED = "SOURCE_VERIFICATION_REQUIRED"
    DOM_LAYOUT_CHANGED = "DOM_LAYOUT_CHANGED"
    RESULT_PARSE_ERROR = "RESULT_PARSE_ERROR"
    CACHE_READ_ERROR = "CACHE_READ_ERROR"
    CACHE_WRITE_ERROR = "CACHE_WRITE_ERROR"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


STAGES = frozenset({"IMPORT", "LAUNCH", "CONTEXT", "NAVIGATION", "SOURCE_CHECK", "DOM", "PARSE", "DETAIL", "SCROLL", "CACHE_READ", "CACHE_WRITE", "CLEANUP", "UNKNOWN"})


class ProviderFailure(Exception):
    def __init__(self, code, stage):
        self.code = ErrorCode(code)
        self.stage = stage if stage in STAGES else "UNKNOWN"
        super().__init__(f"{self.code.value}:{self.stage}")


def classify(exc, stage):
    if isinstance(exc, ProviderFailure):
        return exc
    # Stable Chromium net codes are explicit evidence. Do not guess from
    # arbitrary 'proxy', 'blocked' or 'timeout' words in customer-controlled data.
    text = str(exc)
    if "net::ERR_PROXY_CONNECTION_FAILED" in text or "net::ERR_TUNNEL_CONNECTION_FAILED" in text:
        code = ErrorCode.PROXY_CONNECTION_ERROR
    elif isinstance(exc, socket.gaierror) or "net::ERR_NAME_NOT_RESOLVED" in text:
        code = ErrorCode.DNS_RESOLUTION_ERROR
    elif isinstance(exc, TimeoutError) or "net::ERR_TIMED_OUT" in text or (type(exc).__name__ == "TimeoutError" and type(exc).__module__.startswith("playwright.")):
        code = ErrorCode.NETWORK_TIMEOUT
    elif type(exc).__name__ == "TargetClosedError" and type(exc).__module__.startswith("playwright."):
        code = ErrorCode.BROWSER_PROCESS_EXITED
    elif stage == "IMPORT" and isinstance(exc, ModuleNotFoundError) and (exc.name or "").startswith("playwright"):
        code = ErrorCode.BROWSER_LAUNCH_ERROR
    elif stage == "LAUNCH":
        code = ErrorCode.BROWSER_LAUNCH_ERROR
    elif stage == "CACHE_READ":
        code = ErrorCode.CACHE_READ_ERROR
    elif stage == "CACHE_WRITE":
        code = ErrorCode.CACHE_WRITE_ERROR
    else:
        code = ErrorCode.UNKNOWN_PROVIDER_ERROR
    return ProviderFailure(code, stage)


def safe_error(value, stage="UNKNOWN"):
    """Accept only the exact version-one code:stage wire format."""
    if isinstance(value, str):
        code, sep, observed_stage = value.partition(":")
        if sep and code in ErrorCode._value2member_map_ and observed_stage in STAGES:
            return value
    return str(ProviderFailure(ErrorCode.UNKNOWN_PROVIDER_ERROR, stage))
