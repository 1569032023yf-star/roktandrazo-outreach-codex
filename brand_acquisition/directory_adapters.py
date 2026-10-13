"""Public directory discovery. Layouts are offline contracts, not live-certified DOMs.

Directory membership and explicit website links never establish ownership,
purchase intent, contact consent, or eligibility to send.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

from .models import BrandCandidate
from .official_site_resolver import resolve_official_site_candidates

DIRECTORY_SOURCES = {
    "toyfair": {"url": "https://www.toyassociation.org/tf/attend/participating-retailers/toyfair/attend/participating-retailers.aspx?hkey=f3bcc45f-a1d2-4a7f-aa7b-e06f4e8f2f96", "year": 2026, "class": "trade_show_participant"},
    "gca": {"url": "https://www.greetingcard.org/become-a-member/member-directories/", "year": None, "class": "association_member_directory"},
    "nynow": {"url": "https://nynow.a2zinc.net/Summer2026/Public/exhibitors.aspx", "year": 2026, "class": "trade_show_exhibitor"},
    "astra": {"url": "https://astratoy.org/Web/Astra/Sites/Main/Marketing/About/Astra_Storelocator.aspx", "year": None, "class": "association_store_locator"},
}
DIRECTORY_CATALOG = {"schema_version": "1.0", "sources": {
    source: [{"category": "industry_directory", "url": spec["url"]}]
    for source, spec in DIRECTORY_SOURCES.items()}}


@dataclass
class _Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: "_Node | None" = None

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, _Node):
                yield from child.walk()

    def text(self):
        return " ".join(" ".join(c.text() if isinstance(c, _Node) else c
                                 for c in self.children).split())


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), parent=self.current)
        self.current.children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def _label(node):
    raw = node.attrs.get("class", "") + " " + node.attrs.get("id", "")
    return re.sub(r"([a-z])([A-Z])", r"\1-\2", raw).casefold()


def _field(node, aliases):
    for part in node.walk():
        key = str(part.attrs.get("data-field") or part.attrs.get("itemprop") or "").casefold()
        if key in aliases or any(re.search(r"(?:^|[\s_-])" + re.escape(a) + r"(?:$|[\s_-])", _label(part)) for a in aliases):
            return part.text()
    return ""


def _records(html):
    tree = _Tree()
    tree.feed(html)
    nodes = list(tree.root.walk())
    # Header-based tables survive changed CSS classes without treating nav as orgs.
    for table in (n for n in nodes if n.tag == "table"):
        rows = [n for n in table.walk() if n.tag == "tr"]
        headers = []
        for row in rows:
            cells = [n for n in row.children if isinstance(n, _Node) and n.tag in {"td", "th"}]
            if any(c.tag == "th" for c in cells):
                headers = [c.text().casefold() for c in cells]
                continue
            name_index = next((i for i, h in enumerate(headers) if h in {
                "company", "company name", "organization", "organization name", "retailer", "retailer name",
                "exhibitor", "exhibitor name", "member", "member name", "name"}), None)
            if name_index is None or name_index >= len(cells):
                continue
            values = dict(zip(headers, (c.text() for c in cells)))
            yield {"name": cells[name_index].text(), "country": values.get("country", ""),
                   "category": values.get("category", values.get("categories", values.get("products", ""))),
                   "kind": values.get("type", values.get("member type", "")), "node": row}
    # Record-scoped cards and public lists; never attach a page-global site link.
    for node in nodes:
        if any(p.tag == "table" for p in _ancestors(node)):
            continue
        label = _label(node)
        is_card = bool(re.search(r"(?:company|organization|exhibitor|retailer|member|store)[_-](?:card|entry|item|listing|record|row)\b", label))
        is_list = node.tag == "li" and any(re.search(r"directory|participating-retailers|retailer-list|member-list|store-list", _label(p)) for p in _ancestors(node))
        if not (is_card or is_list or node.attrs.get("data-company-name")):
            continue
        if any(re.search(r"(?:company|organization|exhibitor|retailer|member|store)[_-](?:card|entry|item|listing|record|row)\b", _label(p)) for p in _ancestors(node)):
            continue
        name = node.attrs.get("data-company-name") or _field(node, ("name", "company-name", "organization-name", "exhibitor-name"))
        if not name:
            name = next((p.text() for p in node.walk() if p.tag in {"h2", "h3", "h4"}), "")
        if not name and is_list:
            name = next((p.text() for p in node.children if isinstance(p, _Node) and p.tag in {"a", "strong", "b"}), "")
            if not name and all(isinstance(c, str) for c in node.children):
                name = node.text()
        yield {"name": name, "country": node.attrs.get("data-country") or _field(node, ("country", "addresscountry")),
               "category": node.attrs.get("data-category") or _field(node, ("category", "categories", "products")),
               "kind": node.attrs.get("data-type") or _field(node, ("type", "member-type")), "node": node}
    # Explicit Organization JSON-LD scoped properties, not arbitrary JSON names.
    for node in nodes:
        if node.tag != "script" or node.attrs.get("type") != "application/ld+json":
            continue
        try:
            value = json.loads(node.text())
        except ValueError:
            continue
        stack = value if isinstance(value, list) else [value]
        while stack:
            obj = stack.pop()
            if not isinstance(obj, dict):
                continue
            stack.extend(obj.get("@graph", []))
            stack.extend(x.get("item", x) if isinstance(x, dict) else x for x in obj.get("itemListElement", []))
            kinds = obj.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if not any(k in {"Organization", "Store", "LocalBusiness", "Corporation"} for k in kinds):
                continue
            address = obj.get("address", {})
            country = address.get("addressCountry", "") if isinstance(address, dict) else ""
            if isinstance(country, dict):
                country = country.get("name", "")
            yield {"name": obj.get("name", ""), "country": country,
                   "category": obj.get("category", ""), "kind": obj.get("additionalType", ""),
                   "website": obj.get("url", ""), "node": node}


def _ancestors(node):
    parent = node.parent
    while parent:
        yield parent
        parent = parent.parent


def _toyfair_country_rows(html):
    """Captured 2026 text rows: scoped bold name followed by explicit country.

    A row's evidence must not include links or countries from sibling retailers.
    """
    tree = _Tree()
    tree.feed(html)
    if not any(n.tag in {"h1", "h2", "h3"} and "participating retailers" in n.text().casefold()
               for n in tree.root.walk()):
        return
    for paragraph in tree.root.walk():
        if paragraph.tag != "p" or not any("inner-tab-data" in _label(p) for p in _ancestors(paragraph)):
            continue
        for index, child in enumerate(paragraph.children):
            if not isinstance(child, _Node) or child.tag != "strong":
                continue
            following = paragraph.children[index + 1:index + 2]
            country = re.fullmatch(r"\s*\(([^()<>]{2,80})\)\s*", following[0]) if following and isinstance(following[0], str) else None
            if not country:
                continue
            name = child.text()
            evidence_node = _Node("p", children=[name, " (" + country.group(1) + ")"])
            yield {"name": name, "country": country.group(1).strip(), "category": "", "kind": "",
                   "node": evidence_node}


def classify(source, category, kind):
    evidence = " ".join((category, kind)).casefold().replace("_", " ").replace("-", " ")
    if re.search(r"supplier|printer|printing service|manufacturer|print production", evidence):
        return "SUPPLIER_CANDIDATE", "SUPPLIER", "excluded", "supplier_or_competing_production_business"
    if re.search(r"distributor|wholesaler|importer|distribution", evidence):
        return "DISTRIBUTOR_CANDIDATE", "DISTRIBUTOR", "candidate", "explicit_distribution_category"
    relevant = bool(re.search(r"toy|game|puzzle|gift|bookstore|book store|educational|greeting card|stationery|paper|card brand|card publisher", evidence))
    if category and not relevant:
        return "IDENTITY_UNVERIFIED", "UNKNOWN", "excluded", "explicit_category_outside_target_scope"
    if source in {"toyfair", "astra"}:
        return "RETAIL_BUYER_CANDIDATE", "UNKNOWN", "candidate" if relevant else "needs_review", "retail_directory_registration_buyer_type_unverified"
    if "publisher" in evidence and relevant:
        return "PUBLISHER_CANDIDATE", "CARD_PUBLISHER", "candidate", "explicit_relevant_publisher_category"
    if "greeting card" in evidence or "card brand" in evidence:
        return "BRAND_OWNER_CANDIDATE", "CARD_BRAND", "candidate", "explicit_card_product_category_owner_unverified"
    if "paper" in evidence or "stationery" in evidence:
        return "BRAND_OWNER_CANDIDATE", "PAPER_GOODS_BRAND", "candidate", "explicit_paper_product_category_owner_unverified"
    if relevant:
        return "BRAND_OWNER_CANDIDATE", "UNKNOWN", "candidate", "relevant_product_category_owner_unverified"
    return "IDENTITY_UNVERIFIED", "UNKNOWN", "needs_review", "missing_product_or_business_category"


def parse_directory(source, html, url):
    if source not in DIRECTORY_SOURCES or not url or urlsplit(url).scheme != "https":
        raise ValueError("directory source and HTTPS evidence URL are required")
    spec = DIRECTORY_SOURCES[source]
    # Preserve an explicitly dated archive instead of assigning the default year.
    year_match = re.search(r"(?:Summer|Winter|Spring|Fall)(20\d{2})", url, re.I)
    source_year = int(year_match.group(1)) if year_match else spec["year"]
    found = []
    seen = set()
    records = list(_records(html))
    if source == "toyfair":
        records.extend(_toyfair_country_rows(html))
    for record in records:
        name = " ".join(str(record["name"] or "").split())
        if not name or len(name) > 200 or name.casefold() in {"company", "company name", "home", "contact", "login", "sign in", "website"}:
            continue
        country = str(record["country"] or "").strip()
        category = str(record["category"] or "").strip()
        kind = str(record["kind"] or "").strip()
        links = []
        for node in record["node"].walk():
            if node.tag == "a" and node.attrs.get("href"):
                target = urljoin(url, node.attrs["href"])
                if urlsplit(target).hostname != urlsplit(url).hostname:
                    links.append({"url": target, "label": node.text(), "rel": node.attrs.get("rel", "")})
        website = str(record.get("website") or "")
        if website and urlsplit(website).hostname == urlsplit(url).hostname:
            website = ""  # directory profile URL is not an official business site
        evidence = {"source_url": url, "organization_name": name, "country": country,
                    "category": category, "member_type": kind, "source_year": source_year,
                    "source_class": spec["class"], "links": links, "website_url": website,
                    "excerpt": record["node"].text()[:1200]}
        orgtype, membertype, filter_status, reason = classify(source, category, kind)
        candidate = BrandCandidate(name, organization_name=name, organization_type=orgtype,
            directory_member_type=membertype, organization_country=country,
            directory_source_year=source_year, directory_source_class=spec["class"],
            category_filter_status=filter_status, category_filter_reason=reason,
            source_platforms=[source], source_urls=[url], discovery_source_url=url,
            product_categories=[category] if category else [], product_evidence=[evidence],
            product_or_listing_evidence=[evidence], directory_evidence=[evidence], brand_claim=name)
        resolved = resolve_official_site_candidates(candidate, [evidence])
        candidate.official_site_candidates = resolved["candidate_websites"]
        candidate.official_site_resolution_status = resolved["resolution_status"]
        fingerprint = json.dumps([name, country, category, kind, candidate.official_site_candidates], sort_keys=True)
        candidate.directory_record_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
        if candidate.directory_record_id in seen:
            continue
        seen.add(candidate.directory_record_id)
        if filter_status == "excluded":
            candidate.exclusions.append("directory_category:" + reason)
        found.append(candidate)
    # Same-name explicit different sites are potential conflicts, never a merge.
    names = {}
    for candidate in found:
        domains = {urlsplit(x["website"]).hostname for x in candidate.official_site_candidates}
        names.setdefault(candidate.brand_name.casefold(), set()).update(domains)
    for candidate in found:
        if len(names[candidate.brand_name.casefold()]) > 1:
            candidate.identity_class = "IDENTITY_CONFLICT"
            candidate.exclusions.append("directory_same_name_distinct_explicit_domains")
    # Prefer explicitly labelled US entries; never infer geography from a name.
    found.sort(key=lambda c: c.organization_country.casefold().strip() not in {
        "us", "usa", "u.s.", "u.s.a.", "united states", "united states of america"})
    return found


def toyfair_retailer_directory_adapter(html, url):
    return parse_directory("toyfair", html, url)


def gca_brand_directory_adapter(html, url):
    return parse_directory("gca", html, url)


def nynow_exhibitor_directory_adapter(html, url):
    return parse_directory("nynow", html, url)


def astra_public_store_directory_adapter(html, url):
    """Only parse supplied public lists; public availability remains unvalidated."""
    return parse_directory("astra", html, url)


DIRECTORY_PARSERS = {"toyfair": toyfair_retailer_directory_adapter,
    "gca": gca_brand_directory_adapter, "nynow": nynow_exhibitor_directory_adapter,
    "astra": astra_public_store_directory_adapter}
