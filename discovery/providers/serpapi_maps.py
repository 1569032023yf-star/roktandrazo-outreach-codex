"""Disabled SerpAPI Google Maps provider.

The previous implementation used an unverified pagination token path. Until a
complete SerpAPI pagination contract is tested, selecting this provider must
fail closed instead of producing partial production discovery.
"""
from __future__ import annotations

import os

from discovery.models import ProviderPage
from discovery.providers.base import SearchProvider


class SerpApiMapsProvider(SearchProvider):
    provider_name = "serpapi_maps"

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 12.0) -> None:
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search_places(self, query: str, city: str, state: str, page_cursor: str = "", page_size: int = 20) -> ProviderPage:
        return ProviderPage(
            provider=self.provider_name,
            query=query,
            city=city,
            state=state,
            page_cursor=page_cursor,
            status="experimental_disabled",
            error="serpapi_maps is experimental_disabled until pagination is verified",
            request_count=0,
            cost_units=0,
        )
