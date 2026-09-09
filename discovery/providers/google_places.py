"""Google Places Text Search provider.

No API key is ever logged or stored. Missing configuration fails closed.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from discovery.models import PlaceSearchResult, ProviderPage
from discovery.providers.base import SearchProvider


GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.addressComponents",
        "places.googleMapsUri",
        "places.postalAddress",
        "places.businessStatus",
        "places.types",
        "places.primaryType",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.location",
        "nextPageToken",
    ]
)


class GooglePlacesProvider(SearchProvider):
    provider_name = "google_places"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 12.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.2,
        location_bias: dict[str, Any] | None = None,
        location_restriction: dict[str, Any] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.min_interval_seconds = min_interval_seconds
        self.location_bias = location_bias or self._location_bias_from_env()
        self.location_restriction = location_restriction or self._location_restriction_from_env()
        self._last_request_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _location_bias_from_env(self) -> dict[str, Any] | None:
        raw = os.getenv("GOOGLE_PLACES_LOCATION_BIAS_JSON", "").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _location_restriction_from_env(self) -> dict[str, Any] | None:
        raw = os.getenv("GOOGLE_PLACES_LOCATION_RESTRICTION_JSON", "").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def search_places(
        self,
        query: str,
        city: str,
        state: str,
        page_cursor: str = "",
        page_size: int = 20,
    ) -> ProviderPage:
        if not self.configured:
            return ProviderPage(
                provider=self.provider_name,
                query=query,
                city=city,
                state=state,
                page_cursor=page_cursor,
                status="provider_not_configured",
                error="GOOGLE_MAPS_API_KEY is not configured",
            )

        body: dict[str, Any] = {
            "textQuery": query,
            "pageSize": max(1, min(int(page_size or 20), 20)),
        }
        if page_cursor:
            body["pageToken"] = page_cursor
        if self.location_restriction:
            body["locationRestriction"] = self.location_restriction
        elif self.location_bias:
            body["locationBias"] = self.location_bias

        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        for attempt in range(self.max_retries + 1):
            wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()
            req = urllib.request.Request(GOOGLE_PLACES_URL, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                results = [self._normalize_place(p, query, city, state, data.get("nextPageToken", "")) for p in data.get("places", [])]
                return ProviderPage(
                    provider=self.provider_name,
                    query=query,
                    city=city,
                    state=state,
                    page_cursor=page_cursor,
                    results=results,
                    next_page_cursor=data.get("nextPageToken", "") or "",
                    status="ok",
                    request_count=1,
                    cost_units=1,
                )
            except urllib.error.URLError as exc:
                if attempt >= self.max_retries:
                    return ProviderPage(
                        provider=self.provider_name,
                        query=query,
                        city=city,
                        state=state,
                        page_cursor=page_cursor,
                        status="provider_timeout" if "timed out" in str(exc).lower() else "provider_error",
                        error=str(exc.reason if hasattr(exc, "reason") else exc),
                        request_count=attempt + 1,
                        cost_units=attempt + 1,
                    )
            except Exception as exc:
                return ProviderPage(
                    provider=self.provider_name,
                    query=query,
                    city=city,
                    state=state,
                    page_cursor=page_cursor,
                    status="provider_error",
                    error=str(exc),
                    request_count=attempt + 1,
                    cost_units=attempt + 1,
                )
        return ProviderPage(provider=self.provider_name, query=query, city=city, state=state, page_cursor=page_cursor, status="provider_error")

    def _normalize_place(self, place: dict[str, Any], query: str, city: str, state: str, next_page_cursor: str) -> PlaceSearchResult:
        display = place.get("displayName") or {}
        location = place.get("location") or {}
        types = list(place.get("types") or [])
        place_id = str(place.get("id") or "")
        parsed_city, parsed_state, parsed_postal, parsed_country = _parse_address_fields(place)
        return PlaceSearchResult(
            provider=self.provider_name,
            provider_result_id=place_id,
            place_id=place_id,
            business_name=str(display.get("text") or ""),
            formatted_address=str(place.get("formattedAddress") or ""),
            city=parsed_city,
            state=parsed_state,
            country=parsed_country,
            postal_code=parsed_postal,
            phone=str(place.get("nationalPhoneNumber") or ""),
            website=str(place.get("websiteUri") or ""),
            business_status=str(place.get("businessStatus") or ""),
            primary_type=str(place.get("primaryType") or ""),
            types=types,
            source_query=query,
            source_url=str(place.get("googleMapsUri") or GOOGLE_PLACES_URL),
            raw_payload=place,
            next_page_cursor=next_page_cursor,
            location_lat=location.get("latitude"),
            location_lng=location.get("longitude"),
        )


def _component_text(component: dict[str, Any], short: bool = False) -> str:
    key = "shortText" if short else "longText"
    return str(component.get(key) or component.get("longText") or component.get("shortText") or "")


def _parse_address_fields(place: dict[str, Any]) -> tuple[str, str, str, str]:
    city = ""
    state = ""
    postal_code = ""
    country = ""

    for component in place.get("addressComponents") or []:
        types = set(component.get("types") or [])
        if not city and ({"locality", "postal_town", "sublocality", "administrative_area_level_3"} & types):
            city = _component_text(component)
        if not state and "administrative_area_level_1" in types:
            state = _component_text(component, short=True)
        if not postal_code and "postal_code" in types:
            postal_code = _component_text(component)
        if not country and "country" in types:
            country = _component_text(component, short=True)

    postal = place.get("postalAddress") or {}
    city = city or str(postal.get("locality") or "")
    state = state or str(postal.get("administrativeArea") or "")
    postal_code = postal_code or str(postal.get("postalCode") or "")
    country = country or str(postal.get("regionCode") or "")
    return city.strip(), state.strip(), postal_code.strip(), country.strip()
