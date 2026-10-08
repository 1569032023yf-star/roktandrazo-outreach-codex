"""Unauthenticated, bounded parsers for public discovery pages."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from datetime import datetime, timezone
import ipaddress
import json
import re
import socket
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

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
    final_url: str = ""
    http_status: int | None = None
    content_type: str = ""
    fetched_at: str = ""
    fetch_method: str = "https"
    error_type: str = ""

    @property
    def requested_url(self) -> str:
        return self.url

    def to_dict(self, *, include_html: bool = False) -> dict[str, Any]:
        result = {
            "requested_url": self.url,
            "final_url": self.final_url or self.url,
            "http_status": self.http_status,
            "fetch_status": self.status,
            "content_type": self.content_type,
            "fetched_at": self.fetched_at,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "error_type": self.error_type or self.error,
            "fetch_method": self.fetch_method,
        }
        if include_html:
            result["html"] = self.html
        return result


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
    url_outcomes: list[dict[str, Any]] = field(default_factory=list)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_public_url(url: str, *, require_https: bool = False,
                        resolver=socket.getaddrinfo) -> tuple[bool, str]:
    """Reject local/private targets and non-web schemes before any request."""
    try:
        parsed = urlsplit(str(url or ""))
        if parsed.scheme not in ({"https"} if require_https else {"http", "https"}):
            return False, "unsupported_scheme"
        if not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return False, "invalid_authority"
        host = parsed.hostname.rstrip(".").lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
            return False, "private_hostname"
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            records = resolver(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = [ipaddress.ip_address(record[4][0].split("%", 1)[0]) for record in records]
        if not addresses or any(not address.is_global for address in addresses):
            return False, "non_public_address"
        return True, ""
    except (OSError, ValueError, TypeError, UnicodeError):
        return False, "dns_or_url_error"


class _PublicRedirectHandler(HTTPRedirectHandler):
    def __init__(self, *, require_https: bool = False, allowed_domain: str = ""):
        super().__init__()
        self.require_https = require_https
        self.allowed_domain = allowed_domain.lower().removeprefix("www.")

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        ok, reason = validate_public_url(newurl, require_https=self.require_https)
        host = (urlsplit(newurl).hostname or "").lower().removeprefix("www.")
        same_party = not self.allowed_domain or host == self.allowed_domain or host.endswith("." + self.allowed_domain)
        if not ok or not same_party:
            raise URLError("unsafe_redirect:" + (reason or "cross_party"))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicPageFetcher:
    """Normal HTTP only. Access challenges and rate limits stop that source run."""

    def fetch(self, url: str, timeout: float = 15, *, require_https: bool = False,
              allowed_domain: str = "") -> PageResult:
        started = time.monotonic()
        ok, reason = validate_public_url(url, require_https=require_https)
        if not ok:
            return PageResult(url, "network_error", error=reason, elapsed_seconds=time.monotonic()-started,
                              fetched_at=_timestamp(), fetch_method="https", error_type=reason)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        try:
            with build_opener(_PublicRedirectHandler(require_https=require_https, allowed_domain=allowed_domain)).open(request, timeout=timeout) as response:
                status = int(response.status)
                body = response.read(MAX_BODY_BYTES + 1)
                if len(body) > MAX_BODY_BYTES:
                    return PageResult(url, "permanent_unavailable", error="response_limit", final_url=response.geturl(),
                                      http_status=status, fetched_at=_timestamp(), elapsed_seconds=time.monotonic()-started,
                                      error_type="response_limit")
                content_type = response.headers.get("Content-Type", "")
                if content_type and "html" not in content_type.lower() and "text/plain" not in content_type.lower():
                    return PageResult(url, "permanent_unavailable", error="non_html_content", final_url=response.geturl(),
                                      http_status=status, content_type=content_type, fetched_at=_timestamp(),
                                      elapsed_seconds=time.monotonic()-started, error_type="non_html_content")
                html = body.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
                lowered = html.lower()
                if _is_challenge(lowered):
                    return PageResult(url, "access_restricted", error="challenge_or_login", final_url=response.geturl(),
                                      http_status=status, content_type=content_type, fetched_at=_timestamp(),
                                      elapsed_seconds=time.monotonic()-started, error_type="challenge_or_login")
                if status == 429:
                    return PageResult(url, "rate_limited", error="http_429", final_url=response.geturl(), http_status=status,
                                      content_type=content_type, fetched_at=_timestamp(), elapsed_seconds=time.monotonic()-started,
                                      error_type="http_429")
                fetch_status = "ok" if 200 <= status < 300 else "permanent_unavailable" if status in {404, 410} else "transient_failure"
                return PageResult(url, fetch_status, html, f"http_{status}" if status >= 300 else "",
                                  time.monotonic()-started, response.geturl(), status, content_type, _timestamp(), "https",
                                  f"http_{status}" if status >= 300 else "")
        except HTTPError as exc:
            status = "rate_limited" if exc.code == 429 else "access_restricted" if exc.code in (401, 403) else "permanent_unavailable" if exc.code in {404, 410} else "transient_failure"
            return PageResult(url, status, error=f"http_{exc.code}", final_url=exc.geturl(), http_status=exc.code,
                              content_type=exc.headers.get("Content-Type", "") if exc.headers else "",
                              fetched_at=_timestamp(), elapsed_seconds=time.monotonic()-started, error_type=f"http_{exc.code}")
        except (URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", None)
            error_type = type(reason).__name__ if reason is not None else type(exc).__name__
            status = "permanent_unavailable" if str(reason or "").startswith("unsafe_redirect:") else "transient_failure"
            return PageResult(url, status, error=type(exc).__name__, final_url=url, fetched_at=_timestamp(),
                              elapsed_seconds=time.monotonic()-started, error_type=error_type)


class SafeOfficialPageFetcher:
    """HTTPS-only, same-domain adapter for the existing official-page checker."""
    def __init__(self):
        self.fetcher = PublicPageFetcher()

    def fetch_https_upgrade(self, url: str) -> dict:
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        result = self.fetcher.fetch(url, require_https=True, allowed_domain=host)
        return {"text": re.sub(r"<[^>]+>", " ", result.html), "html":result.html,
                "final_url":result.final_url or url, "status":result.http_status or 0,
                "tls_verified":urlsplit(result.final_url or url).scheme == "https" and result.status == "ok",
                "fetched_at":result.fetched_at, "fetch_transport":"https"}

    def fetch(self, url: str) -> dict:
        return self.fetch_https_upgrade(url)


class BrowserRenderedFetcher:
    """Adapter for an explicitly supplied, authorized public browser renderer."""

    def __init__(self, renderer=None):
        self.renderer = renderer

    @property
    def available(self) -> bool:
        return callable(self.renderer)

    def fetch(self, url: str) -> PageResult:
        started = time.monotonic()
        if not self.available:
            return PageResult(url, "transient_failure", error="browser_renderer_unavailable",
                              fetched_at=_timestamp(), fetch_method="browser_rendered", error_type="capability_missing")
        ok, reason = validate_public_url(url)
        if not ok:
            return PageResult(url, "permanent_unavailable", error=reason, fetched_at=_timestamp(),
                              fetch_method="browser_rendered", error_type=reason)
        try:
            response = self.renderer(url)
            final_url = str(response.get("final_url") or url)
            final_ok, final_reason = validate_public_url(final_url)
            if not final_ok:
                return PageResult(url, "permanent_unavailable", error="unsafe_final_url:" + final_reason,
                                  final_url=final_url, http_status=response.get("http_status"),
                                  fetched_at=_timestamp(), elapsed_seconds=time.monotonic()-started,
                                  fetch_method="browser_rendered", error_type=final_reason)
            status = int(response.get("http_status") or 0)
            html = str(response.get("html") or "")
            content_type = str(response.get("content_type") or "text/html")
            fetch_status = "ok" if 200 <= status < 300 and html else "transient_failure"
            return PageResult(url, fetch_status, html, str(response.get("error") or ""),
                              time.monotonic()-started, final_url, status, content_type,
                              str(response.get("fetched_at") or _timestamp()), "browser_rendered",
                              str(response.get("error_type") or ""))
        except Exception as exc:
            return PageResult(url, "transient_failure", error=type(exc).__name__, final_url=url,
                              fetched_at=_timestamp(), elapsed_seconds=time.monotonic()-started,
                              fetch_method="browser_rendered", error_type=type(exc).__name__)


class ImportedPageFetcher:
    """Load timestamped public page captures for discovery-only deterministic replay."""

    def __init__(self, manifest: str | Path):
        self.path = Path(manifest)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("scope") != "discovery_only" or not isinstance(payload.get("pages"), list):
            raise ValueError("import manifest must declare scope=discovery_only and pages[]")
        self.pages = {str(row.get("source_url")): row for row in payload["pages"] if row.get("source_url")}

    def fetch(self, url: str) -> PageResult:
        row = self.pages.get(url)
        if not row:
            return PageResult(url, "permanent_unavailable", error="not_in_import_manifest",
                              fetched_at=_timestamp(), fetch_method="public_page_import", error_type="missing_import")
        fetched_at = str(row.get("collected_at") or "")
        method = str(row.get("acquisition_method") or "")
        try:
            collected = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            if collected.tzinfo is None or collected.utcoffset() is None:
                raise ValueError("timestamp must include a timezone")
        except ValueError as exc:
            raise ValueError("imported page requires an ISO 8601 collected_at timestamp") from exc
        if not method or not str(row.get("html") or ""):
            raise ValueError("imported page requires acquisition_method and html")
        if row.get("evidence_scope", "discovery_only") != "discovery_only":
            raise ValueError("external imports cannot be used as official-site or email evidence")
        return PageResult(url, "ok", str(row["html"]), final_url=str(row.get("final_url") or url),
                          http_status=int(row.get("http_status") or 200),
                          content_type=str(row.get("content_type") or "text/html"), fetched_at=fetched_at,
                          fetch_method="public_page_import:" + method)


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
        outcome = result.to_dict()
        if result.status in {"ok", "success"}:
            run.pages_fetched += 1
            outcome["status"] = "PENDING_PARSE"
            remaining = max(0, MAX_SOURCE_CANDIDATES - len(run.candidates))
            try:
                parsed = PARSERS[source](result.html, result.final_url or url)
            except Exception as exc:
                outcome.update({"status": "TRANSIENT_FAILURE", "error_type": type(exc).__name__})
                run.failures += 1
                run.errors.append({"url": url, "status": "parse_error", "error": type(exc).__name__})
                run.url_outcomes.append(outcome)
                continue
            fetched_at = result.fetched_at or _timestamp()
            origin = "test_fixture" if result.fetch_method == "fixture" else "public_import" if result.fetch_method.startswith("public_page_import:") else "live_public"
            for candidate in parsed:
                candidate.discovery_source_url = url
                candidate.source_page_fetched_at = fetched_at
                candidate.brand_claim = candidate.brand_name
                candidate.source_acquisition_method = result.fetch_method
                candidate.data_origin = origin
                candidate.fixture_status = "KNOWN_TEST_SEED" if origin == "test_fixture" else ""
                candidate.product_or_listing_evidence = list(candidate.product_evidence)
                candidate.public_sales_signals.setdefault("rating", "NOT_AVAILABLE")
                candidate.public_sales_signals.setdefault("sold", "NOT_AVAILABLE")
            run.candidates.extend(parsed[:min(remaining, max_candidates)])
            outcome["status"] = "SUCCESS" if parsed else "PARSE_EMPTY"
            outcome["candidate_count"] = len(parsed)
            outcome["data_origin"] = origin
            if len(run.candidates) >= MAX_SOURCE_CANDIDATES:
                run.url_outcomes.append(outcome)
                break
        else:
            run.failures += 1
            outcome["status"] = {
                "network_error": "TRANSIENT_FAILURE", "timeout": "TRANSIENT_FAILURE",
                "transient_failure": "TRANSIENT_FAILURE", "rate_limited": "ACCESS_RESTRICTED",
                "access_restricted": "ACCESS_RESTRICTED", "permanent_unavailable": "PERMANENT_UNAVAILABLE",
                "http_error": "TRANSIENT_FAILURE", "page_too_large": "PERMANENT_UNAVAILABLE",
            }.get(result.status, "TRANSIENT_FAILURE")
            run.rate_limits += result.status == "rate_limited"
            run.errors.append({"url": url, "status": result.status, "error": result.error or result.error_type})
            if result.status == "rate_limited":
                outcome["status"] = "TRANSIENT_FAILURE"
                outcome["rate_limited"] = True
            if outcome["status"] == "ACCESS_RESTRICTED":
                run.url_outcomes.append(outcome)
                break
        run.url_outcomes.append(outcome)
    return run
