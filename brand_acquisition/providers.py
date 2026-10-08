"""Unauthenticated, bounded parsers for public discovery pages."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urljoin

from .models import BrandCandidate

USER_AGENT = "BrandAcquisitionResearch/1.0 (public pages; contact: research@example.invalid)"
MAX_BODY_BYTES = 2_000_000
SOURCES = ("tiktok_shop", "amazon", "wholesale")
MAX_SOURCE_CANDIDATES = 30


@dataclass
class PageResult:
    url: str
    status: str
    html: str = ""
    error: str = ""
    elapsed_seconds: float = 0.0


@dataclass
class ProviderRun:
    source: str
    candidates: list[BrandCandidate] = field(default_factory=list)
    pages_attempted: int = 0
    pages_fetched: int = 0
    failures: int = 0
    rate_limits: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class PublicPageFetcher:
    """Normal HTTP only. Access challenges and rate limits stop that source run."""

    def fetch(self, url: str, timeout: float = 15) -> PageResult:
        started = time.monotonic()
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        try:
            with urlopen(request, timeout=timeout) as response:
                status = int(response.status)
                body = response.read(MAX_BODY_BYTES + 1)
                if len(body) > MAX_BODY_BYTES:
                    return PageResult(url, "page_too_large", error="response_limit", elapsed_seconds=time.monotonic()-started)
                html = body.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
                lowered = html.lower()
                if _is_challenge(lowered):
                    return PageResult(url, "access_restricted", error="challenge_or_login", elapsed_seconds=time.monotonic()-started)
                if status == 429:
                    return PageResult(url, "rate_limited", error="http_429", elapsed_seconds=time.monotonic()-started)
                return PageResult(url, "ok" if 200 <= status < 300 else "http_error", html, f"http_{status}" if status >= 300 else "", time.monotonic()-started)
        except HTTPError as exc:
            status = "rate_limited" if exc.code == 429 else "access_restricted" if exc.code in (401, 403) else "http_error"
            return PageResult(url, status, error=f"http_{exc.code}", elapsed_seconds=time.monotonic()-started)
        except (URLError, TimeoutError, OSError) as exc:
            return PageResult(url, "network_error", error=type(exc).__name__, elapsed_seconds=time.monotonic()-started)


def _is_challenge(text: str) -> bool:
    return any(term in text for term in ("captcha", "verify you are human", "robot check", "sign in to continue", "login to continue", "access denied"))


class _PageFacts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.jsonld: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.meta: dict[str, str] = {}
        self._script = False
        self._script_type = ""
        self._script_buf: list[str] = []
        self._title = False
        self.title_parts: list[str] = []
        self._heading = False
        self.heading_parts: list[str] = []
        self.text_parts: list[str] = []
        self._anchor = ""
        self._anchor_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self._script = True
            self._script_type = attrs.get("type", "").lower()
            self._script_buf = []
        elif tag == "meta" and (key := (attrs.get("property") or attrs.get("name") or "").lower()):
            self.meta[key] = attrs.get("content", "")
        elif tag == "title":
            self._title = True
        elif tag in {"h1", "h2"}:
            self._heading = True
        elif tag == "a":
            self._anchor = attrs.get("href", "")
            self._anchor_buf = []

    def handle_endtag(self, tag):
        if tag == "script" and self._script:
            if "ld+json" in self._script_type:
                self.jsonld.append("".join(self._script_buf))
            self._script = False
        elif tag == "title":
            self._title = False
        elif tag in {"h1", "h2"}:
            self._heading = False
        elif tag == "a" and self._anchor:
            self.links.append((self._anchor, " ".join("".join(self._anchor_buf).split())))
            self._anchor = ""

    def handle_data(self, data):
        if self._script:
            self._script_buf.append(data)
        if self._title:
            self.title_parts.append(data)
        if self._heading:
            self.heading_parts.append(data)
        if not self._script:
            self.text_parts.append(data)
        if self._anchor:
            self._anchor_buf.append(data)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _facts(html: str) -> _PageFacts:
    parser = _PageFacts()
    parser.feed(html)
    return parser


def _json_objects(facts: _PageFacts):
    for raw in facts.jsonld:
        try:
            yield from _walk(json.loads(raw))
        except (ValueError, TypeError):
            continue


def _candidate(source: str, name: str, url: str, *, owner: str = "", category: str = "",
               signal: dict | None = None, official_website: str = "") -> BrandCandidate:
    return BrandCandidate(
        brand_name=name.strip(), brand_owner_name=owner.strip(), source_platforms=[source], source_urls=[url],
        product_categories=[category] if category else [], public_sales_signals=signal or {},
        sales_signal_observed_at=datetime.now(timezone.utc).isoformat(),
        official_website=official_website,
        identity_class="seller_or_listing" if source != "wholesale" else "directory_listing",
        product_evidence=[{"source_url": url, "brand_claim": name.strip()}],
    )


def parse_tiktok_shop(html: str, url: str) -> list[BrandCandidate]:
    """Extract Product/Store signals; all remain unconfirmed seller candidates."""
    facts = _facts(html)
    found: dict[str, BrandCandidate] = {}
    title = " ".join(facts.title_parts)
    for obj in _json_objects(facts):
        typ = obj.get("@type", [])
        if isinstance(typ, str): typ = [typ]
        if "Product" not in typ: continue
        brand = obj.get("brand", "")
        brand_url = brand.get("url", "") if isinstance(brand, dict) else ""
        if isinstance(brand, dict): brand = brand.get("name", "")
        name = str(brand or obj.get("name", "")).strip()
        if not name: continue
        offers = obj.get("offers", {})
        offer = offers[0] if isinstance(offers, list) and offers else offers
        seller = offer.get("seller", {}) if isinstance(offer, dict) else {}
        seller_name = seller.get("name", "") if isinstance(seller, dict) else str(seller or "")
        found.setdefault(name.casefold(), _candidate("tiktok_shop", name, url, owner=seller_name, official_website=brand_url,
            category="cards_paper_goods", signal={"seller_name": seller_name} if seller_name else {}))
    shop = re.search(r"(?:shopName|storeName|sellerName)\s*[=:]\s*[\"']([^\"']+)", html, re.I)
    if shop and not found:
        name = shop.group(1).strip()
        found[name.casefold()] = _candidate("tiktok_shop", name, url, category="cards_paper_goods",
                                            signal={"page_title": title} if title else {})
    if not found and facts.heading_parts:
        # Publicly rendered seller pages expose the shop heading and basic sales
        # counters even when no machine-readable Product schema is provided.
        name = " ".join(" ".join(facts.heading_parts).split()).strip()
        visible = " ".join(facts.text_parts)
        signals = {}
        for label, key in (("followers?", "followers"), ("sold", "sold"), ("videos?", "videos")):
            match = re.search(rf"([\d,.]+\s*[KkMm+]?)[\s\n]*{label}", visible, re.I)
            if match:
                signals[key] = match.group(1).strip()
        if name:
            found[name.casefold()] = _candidate("tiktok_shop", name, url, category="cards_paper_goods", signal=signals)
            found[name.casefold()].product_evidence = [
                {"source_url": urljoin(url, href), "product_title": label}
                for href, label in facts.links if label and re.search(r"card|playing|paper|notebook|journal|game", label, re.I)
            ] or found[name.casefold()].product_evidence
    return list(found.values())


def parse_amazon(html: str, url: str) -> list[BrandCandidate]:
    """Use public product structured data only; seller identity is not brand ownership."""
    facts = _facts(html)
    found: dict[str, BrandCandidate] = {}
    for obj in _json_objects(facts):
        types = obj.get("@type", [])
        if isinstance(types, str): types = [types]
        if "Product" not in types: continue
        brand = obj.get("brand", "")
        brand_url = brand.get("url", "") if isinstance(brand, dict) else ""
        if isinstance(brand, dict): brand = brand.get("name", "")
        name = str(brand or "").strip()
        if not name: continue
        offers = obj.get("offers", {})
        offer = offers[0] if isinstance(offers, list) and offers else offers
        price = offer.get("price") if isinstance(offer, dict) else None
        found.setdefault(name.casefold(), _candidate("amazon", name, url, official_website=brand_url,
            category="cards_paper_goods", signal={"price_observed": price} if price else {}))
    for key, val in facts.meta.items():
        if key in {"og:brand", "product:brand"} and val.strip():
            name = val.strip()
            found.setdefault(name.casefold(), _candidate("amazon", name, url, category="cards_paper_goods"))
    if not found:
        # Text rendered from real item pages commonly presents an explicit
        # "Brand:" field separate from the marketplace seller.
        match = re.search(r"\bBrand\s*:\s*([^\r\n<]+)", html, re.I)
        if match:
            name = " ".join(match.group(1).split()).strip()
            seller = re.search(r"\bSold by\s+([^\r\n<]+)", html, re.I)
            rating = re.search(r"([\d,]+)\s+ratings?", html, re.I)
            signal = {}
            if seller: signal["marketplace_seller"] = " ".join(seller.group(1).split())
            if rating: signal["ratings"] = rating.group(1).replace(",", "")
            found[name.casefold()] = _candidate("amazon", name, url, category="cards_paper_goods", signal=signal)
    return list(found.values())


def parse_wholesale(html: str, url: str) -> list[BrandCandidate]:
    """Parse Faire and exhibitor-like brand cards, but never assume supplier=owner."""
    facts = _facts(html)
    found: dict[str, BrandCandidate] = {}
    for obj in _json_objects(facts):
        types = obj.get("@type", [])
        if isinstance(types, str): types = [types]
        if not set(types) & {"Brand", "Organization", "Product"}: continue
        name = str(obj.get("name", "")).strip()
        if not name: continue
        if "Product" in types:
            brand = obj.get("brand", {})
            name = str(brand.get("name", "") if isinstance(brand, dict) else brand).strip() or name
        found.setdefault(name.casefold(), _candidate("wholesale", name, url, official_website=str(obj.get("url") or ""),
            owner=str(obj.get("parentOrganization", {}).get("name", "") if isinstance(obj.get("parentOrganization"), dict) else ""),
            category="cards_paper_goods"))
    for href, label in facts.links:
        clean = " ".join(label.split())
        if not clean or len(clean) > 80 or not re.search(r"brand|supplier|exhibitor|wholesale|shop", href, re.I): continue
        if clean.casefold() in {x.casefold() for x in ("home", "brands", "view all", "learn more", "next", "previous")}: continue
        found.setdefault(clean.casefold(), _candidate("wholesale", clean, urljoin(url, href),
                                                      category="cards_paper_goods"))
    return list(found.values())


PARSERS = {"tiktok_shop": parse_tiktok_shop, "amazon": parse_amazon, "wholesale": parse_wholesale}


def run_public_source(source: str, urls: list[str], fetcher=None, max_pages: int = 3,
                      max_candidates: int = MAX_SOURCE_CANDIDATES) -> ProviderRun:
    if source not in PARSERS:
        raise ValueError(f"unsupported source: {source}")
    run = ProviderRun(source)
    fetcher = fetcher or PublicPageFetcher()
    # A restriction stops only this provider, not other independent source runs.
    for url in urls[:max(0, min(3, int(max_pages)))]:
        run.pages_attempted += 1
        result = fetcher.fetch(url)
        if result.status == "ok":
            run.pages_fetched += 1
            remaining = max(0, MAX_SOURCE_CANDIDATES - len(run.candidates))
            run.candidates.extend(PARSERS[source](result.html, url)[:min(remaining, max_candidates)])
            if len(run.candidates) >= MAX_SOURCE_CANDIDATES:
                break
        else:
            run.failures += 1
            run.rate_limits += result.status == "rate_limited"
            run.errors.append({"url": url, "status": result.status, "error": result.error})
            if result.status in {"rate_limited", "access_restricted"}:
                break
    return run
