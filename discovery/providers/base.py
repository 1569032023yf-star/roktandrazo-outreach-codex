"""Provider base classes and configuration lookup."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

from discovery.models import ProviderPage


class ProviderError(RuntimeError):
    pass


class SearchProvider(ABC):
    provider_name = "base"

    @property
    def configured(self) -> bool:
        return True

    @abstractmethod
    def search_places(
        self,
        query: str,
        city: str,
        state: str,
        page_cursor: str = "",
        page_size: int = 20,
    ) -> ProviderPage:
        raise NotImplementedError

    def search_web_directories(
        self,
        city: str,
        state: str,
        query_family: str,
        cursor: str = "",
    ) -> ProviderPage:
        return ProviderPage(
            provider=self.provider_name,
            query=query_family,
            city=city,
            state=state,
            page_cursor=cursor,
            status="web_directory_provider_not_configured",
            error="web_directory_provider_not_configured",
        )


def configured_provider_name(name: str | None = None) -> str:
    return (name or os.getenv("WORKBUDDY_DISCOVERY_PROVIDER") or os.getenv("DISCOVERY_PROVIDER") or "google_places").strip()


def load_provider(name: str | None = None) -> SearchProvider:
    provider_name = configured_provider_name(name)
    if provider_name == "google_places":
        from discovery.providers.google_places import GooglePlacesProvider

        return GooglePlacesProvider()
    if provider_name == "serpapi_maps":
        from discovery.providers.serpapi_maps import SerpApiMapsProvider

        return SerpApiMapsProvider()
    if provider_name == "mock":
        from discovery.providers.mock_provider import MockPlacesProvider

        return MockPlacesProvider()
    if provider_name == "browser_maps":
        from discovery.providers.browser_maps import BrowserMapsProvider

        return BrowserMapsProvider()
    if provider_name in ("web_directory", "webdir"):
        from discovery.providers.web_directory import WebDirectoryProvider

        return WebDirectoryProvider()
    raise ProviderError(f"unknown discovery provider: {provider_name}")

