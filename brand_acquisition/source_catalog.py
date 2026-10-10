"""Small configurable, independently capped source URL catalog."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from .providers import PARSERS

DEFAULT_CATALOG = {
    "schema_version": "1.0",
    "sources": {
        "tiktok_shop": [
            {"category": "greeting_cards", "url": "https://shop.tiktok.com/search?q=greeting%20cards"},
            {"category": "playing_cards", "url": "https://shop.tiktok.com/search?q=playing%20cards"},
            {"category": "card_games", "url": "https://shop.tiktok.com/search?q=card%20games"},
            {"category": "flash_cards", "url": "https://shop.tiktok.com/search?q=flash%20cards"},
            {"category": "paper_gifts", "url": "https://shop.tiktok.com/search?q=paper%20gifts"},
            {"category": "stationery", "url": "https://shop.tiktok.com/search?q=stationery"},
            {"category": "paper_crafts", "url": "https://shop.tiktok.com/search?q=paper%20crafts"},
        ],
        "amazon": [
            {"category": "greeting_cards", "url": "https://www.amazon.com/s?k=greeting+cards"},
            {"category": "playing_cards", "url": "https://www.amazon.com/s?k=playing+cards"},
            {"category": "card_games", "url": "https://www.amazon.com/s?k=card+games"},
            {"category": "paper_goods", "url": "https://www.amazon.com/s?k=paper+goods+stationery"},
            {"category": "notebooks", "url": "https://www.amazon.com/s?k=notebooks+journals"},
            {"category": "paper_crafts", "url": "https://www.amazon.com/s?k=paper+crafts"},
        ],
        "wholesale": [
            {"category": "greeting_cards", "url": "https://www.faire.com/discover/greeting-cards"},
            {"category": "playing_cards", "url": "https://www.faire.com/discover/playing-cards"},
            {"category": "paper_goods", "url": "https://www.faire.com/discover/stationery"},
            {"category": "industry_exhibitors", "url": "https://www.nationalstationeryshow.com/exhibitors"},
            {"category": "manufacturer_directory", "url": "https://www.greetingcard.org/members"},
        ],
    },
}


def load_catalog(path: str | Path | None = None) -> dict[str, list[dict[str, str]]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8")) if path else DEFAULT_CATALOG
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0" or not isinstance(payload.get("sources"), dict):
        raise ValueError("unsupported source catalog")
    normalized = {}
    for source, rows in payload["sources"].items():
        if source not in PARSERS or not isinstance(rows, list):
            raise ValueError("unsupported source or invalid URL list")
        clean = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("catalog entry must be an object")
            url = str(row.get("url") or "")
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
                raise ValueError("catalog URLs must be credential-free HTTPS")
            clean.append({"category": str(row.get("category") or "uncategorized"), "url": url})
        normalized[source] = clean
    return normalized
