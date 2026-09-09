"""Normalization and suitability checks for discovery results."""
from __future__ import annotations

import re
from urllib.parse import urlparse


TARGET_TYPE_HINTS = {
    "book_store",
    "electronics_store",
    "gift_shop",
    "home_goods_store",
    "museum",
    "point_of_interest",
    "store",
    "tourist_attraction",
}

EXCLUDED_TYPE_HINTS = {
    "accounting",
    "bar",
    "cafe",
    "car_dealer",
    "car_repair",
    "dentist",
    "doctor",
    "electrician",
    "finance",
    "food",
    "general_contractor",
    "hair_care",
    "insurance_agency",
    "lawyer",
    "lodging",
    "moving_company",
    "painter",
    "plumber",
    "real_estate_agency",
    "restaurant",
    "roofing_contractor",
    "spa",
    "travel_agency",
}

EXCLUDED_NAME_HINTS = (
    "restaurant",
    "bar & grill",
    "grill",
    "cafe",
    "coffee",
    "salon",
    "plumbing",
    "roofing",
    "law office",
    "attorney",
    "insurance",
    "real estate",
)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_business_name(value: str) -> str:
    text = normalize_text(value).lower()
    text = text.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", text)


def normalize_address(value: str) -> str:
    text = normalize_text(value).lower()
    text = text.replace(" street", " st").replace(" avenue", " ave").replace(" road", " rd")
    return re.sub(r"[^a-z0-9]+", "", text)


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def normalized_domain(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    host = urlparse(raw).hostname or ""
    return host.removeprefix("www.")


def is_closed_status(value: str) -> bool:
    return str(value or "").strip().upper() in {
        "CLOSED_PERMANENTLY",
        "PERMANENTLY_CLOSED",
        "CLOSED",
    }


def is_suitable_retail(name: str, primary_type: str, types: list[str]) -> tuple[bool, str]:
    lowered_name = normalize_text(name).lower()
    all_types = {str(t or "").lower() for t in types}
    if primary_type:
        all_types.add(str(primary_type).lower())
    if any(hint in lowered_name for hint in EXCLUDED_NAME_HINTS):
        return False, "excluded_name_hint"
    if all_types & EXCLUDED_TYPE_HINTS:
        return False, "excluded_place_type"
    if all_types & TARGET_TYPE_HINTS:
        return True, ""
    if any(term in lowered_name for term in ("toy", "game", "book", "gift", "puzzle", "comic", "hobby")):
        return True, ""
    return False, "not_target_retail"

