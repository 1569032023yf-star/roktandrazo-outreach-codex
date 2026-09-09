"""Provider-neutral discovery models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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
