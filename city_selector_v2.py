"""
Roktandrazo BD Outreach - City Selector V2
Expanded search queries: 10+ keyword types per city
Target: 30-50 candidates per city → 10-20 leads per city
"""

import json
import os
from datetime import datetime

# Expanded search query templates (10+ types per city)
SEARCH_QUERIES_V2 = [
    # Core retail
    "independent toy store {city} {state}",
    "board game store {city} {state}",
    "card game shop {city} {state}",
    "puzzle shop {city} {state}",
    "gift shop {city} {state} toys games",
    "museum gift shop {city} {state}",
    "bookstore gifts {city} {state}",
    "hobby shop {city} {state} games",
    "educational toy store {city} {state}",
    "family game store {city} {state}",
    # Directory/list searches (capture multiple stores per query)
    "best toy stores {city} {state}",
    "best game shops {city} {state}",
    "unique gift shops {city} {state}",
    "local toy shops {city} {state}",
    "where to buy puzzles {city} {state}",
]

# All previously searched cities (Phase 0 + Phase 1)
ALREADY_SEARCHED = {
    "portland_or", "austin_tx", "asheville_nc", "savannah_ga", "nashville_tn",
    "boulder_co", "sedona_az", "bar_harbor_me", "charleston_sc", "cape_cod_ma",
    "eureka_springs_ar", "lake_geneva_wi", "traverse_city_mi", "woodstock_vt",
    "stowe_vt", "park_city_ut", "carmel-by-the-sea_ca", "taos_nm", "bend_or",
    "grand_rapids_mi", "portsmouth_nh",
    "ithaca_ny", "chicago_il", "burlington_vt", "madison_wi", "santa_fe_nm",
}

# Recommended new cities for Phase 2
PHASE2_CITIES = [
    # Large metros (high retail density)
    {"city": "Denver", "state": "CO", "tier": "large", "pop": "715K", "reason": "Large metro, strong indie retail"},
    {"city": "San Diego", "state": "CA", "tier": "large", "pop": "1.38M", "reason": "Tourist + residential retail mix"},
    {"city": "Seattle", "state": "WA", "tier": "large", "pop": "737K", "reason": "Game culture hub, indie retail"},
    {"city": "Boston", "state": "MA", "tier": "large", "pop": "675K", "reason": "Historic city, museum stores"},
    {"city": "Philadelphia", "state": "PA", "tier": "large", "pop": "1.6M", "reason": "Historic city, diverse retail"},
    # Mid-size cities (indie retail sweet spot)
    {"city": "Ann Arbor", "state": "MI", "tier": "mid", "pop": "123K", "reason": "University town, indie retail"},
    {"city": "Fort Collins", "state": "CO", "tier": "mid", "pop": "170K", "reason": "University town, craft culture"},
    {"city": "Eugene", "state": "OR", "tier": "mid", "pop": "176K", "reason": "University town, eco-conscious"},
    {"city": "Savannah", "state": "GA", "tier": "tourist", "pop": "147K", "reason": "Historic tourist city"},
    {"city": "New Orleans", "state": "LA", "tier": "tourist", "pop": "383K", "reason": "Cultural capital, unique retail"},
]


def get_search_queries_v2(city_info: dict) -> list[str]:
    """Generate 15 search queries for a city."""
    queries = []
    for template in SEARCH_QUERIES_V2:
        queries.append(template.format(
            city=city_info["city"],
            state=city_info["state"]
        ))
    return queries


def get_phase2_cities(exclude_searched: bool = True) -> list[dict]:
    """Get Phase 2 city list, optionally excluding already-searched cities."""
    cities = []
    for city in PHASE2_CITIES:
        key = f"{city['city']}_{city['state']}".lower().replace(" ", "_")
        if exclude_searched and key in ALREADY_SEARCHED:
            continue
        cities.append(city)
    return cities


if __name__ == "__main__":
    cities = get_phase2_cities()
    print(f"Phase 2 cities: {len(cities)}")
    for c in cities:
        queries = get_search_queries_v2(c)
        print(f"\n{c['city']}, {c['state']} ({c['tier']}, pop {c['pop']}):")
        print(f"  {len(queries)} queries")
        for q in queries[:3]:
            print(f"    {q}")
        print(f"    ... and {len(queries)-3} more")
