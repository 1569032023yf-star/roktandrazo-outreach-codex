"""Deterministic provider for offline tests."""
from __future__ import annotations

from discovery.models import PlaceSearchResult, ProviderPage
from discovery.providers.base import SearchProvider


def _nashville_results(query: str, cursor: str) -> ProviderPage:
    if "timeout" in query:
        return ProviderPage(provider="mock", query=query, city="Nashville", state="TN", page_cursor=cursor, status="provider_timeout", error="mock timeout")
    if cursor == "page2":
        return ProviderPage(
            provider="mock",
            query=query,
            city="Nashville",
            state="TN",
            page_cursor=cursor,
            results=[
                PlaceSearchResult(
                    provider="mock",
                    provider_result_id="mock-nashville-002",
                    place_id="mock-place-002",
                    business_name="Nashville Toy Shelf",
                    formatted_address="200 Game Ave, Nashville, TN 37203",
                    city="Nashville",
                    state="TN",
                    phone="615-555-0200",
                    website="https://nashvilletoyshelf.example",
                    business_status="OPERATIONAL",
                    primary_type="store",
                    types=["store", "point_of_interest"],
                    source_query=query,
                    raw_payload={"email": "hello@nashvilletoyshelf.example", "evidence_snippet": "hello@nashvilletoyshelf.example"},
                )
            ],
            next_page_cursor="",
            request_count=1,
            cost_units=0,
        )
    return ProviderPage(
        provider="mock",
        query=query,
        city="Nashville",
        state="TN",
        page_cursor=cursor,
        results=[
            PlaceSearchResult(
                provider="mock",
                provider_result_id="mock-nashville-001",
                place_id="mock-place-001",
                business_name="Nashville Board Game Depot",
                formatted_address="100 Game St, Nashville, TN 37201",
                city="Nashville",
                state="TN",
                phone="615-555-0100",
                website="https://nashvilleboardgames.example",
                business_status="OPERATIONAL",
                primary_type="store",
                types=["store", "point_of_interest"],
                source_query=query,
                raw_payload={"email": "orders@nashvilleboardgames.example", "evidence_snippet": "orders@nashvilleboardgames.example"},
            ),
            PlaceSearchResult(
                provider="mock",
                provider_result_id="mock-nashville-closed",
                place_id="mock-place-closed",
                business_name="Closed Nashville Games",
                formatted_address="101 Old St, Nashville, TN 37201",
                city="Nashville",
                state="TN",
                website="https://closednashvillegames.example",
                business_status="CLOSED_PERMANENTLY",
                primary_type="store",
                types=["store"],
                source_query=query,
                raw_payload={},
            ),
        ],
        next_page_cursor="page2",
        request_count=1,
        cost_units=0,
    )


class MockPlacesProvider(SearchProvider):
    provider_name = "mock"

    def __init__(self, pages: dict[tuple[str, str], ProviderPage] | None = None, configured: bool = True) -> None:
        self.pages = pages or {}
        self._configured = configured

    @property
    def configured(self) -> bool:
        return self._configured

    def search_places(self, query: str, city: str, state: str, page_cursor: str = "", page_size: int = 20) -> ProviderPage:
        if not self.configured:
            return ProviderPage(provider=self.provider_name, query=query, city=city, state=state, page_cursor=page_cursor, status="provider_not_configured", error="mock provider disabled")
        if (query, page_cursor or "") in self.pages:
            return self.pages[(query, page_cursor or "")]
        if city == "Nashville" and state in {"TN", "Tennessee"}:
            return _nashville_results(query, page_cursor or "")
        return ProviderPage(provider=self.provider_name, query=query, city=city, state=state, page_cursor=page_cursor, results=[], request_count=1, cost_units=0)

