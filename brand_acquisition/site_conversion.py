"""Bounded, JSON-only directory conversion; search/imports are clues, never identity.

This stage deliberately does not call the domain-only acquisition deduplicator.
No database, sending plan, browser session, or production configuration is written.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from .capture_manifest import validate_manifest, write_capture
from .email_quality import audit_brand_email
from .history import HistoryChecker
from .providers import PublicPageFetcher

BLOCKED_HOSTS = {
    'facebook.com', 'instagram.com', 'linkedin.com', 'tiktok.com', 'youtube.com',
    'pinterest.com', 'x.com', 'twitter.com', 'yelp.com', 'crunchbase.com',
    'amazon.com', 'ebay.com', 'etsy.com', 'faire.com', 'walmart.com', 'shop.app',
    'toyassociation.org', 'nynow.com', 'a2zinc.net', 'google.com', 'bing.com',
    'thegeniusofplay.org', 'zoominfo.com', 'dnb.com', 'reddit.com',
}
LINK_HINTS = ('wholesale', 'retailer', 'partnership', 'sales', 'business', 'trade', 'contact', 'about')
RELEVANT = re.compile(r'\b(?:toys?|board games?|card games?|puzzles?|stationery|greeting cards?|gift wrap|bookstore|books?|comics?|paper goods|gift shop|collectibles?)\b', re.I)
RESTRICTED = {'access_restricted', 'rate_limited'}


def blocked_by_network_policy(value):
    return str(value or '').strip().casefold() in {'1', 'true', 'yes', 'on'}


def challenge_page(html):
    from .providers import _is_challenge
    return _is_challenge(html.casefold()) or bool(re.search(
        r'please wait while your request is being verified|<title>\s*one moment,? please', html, re.I))


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def name_key(value):
    words = re.findall(r'[a-z0-9]+', str(value).casefold())
    while words and words[-1] in {'llc', 'inc', 'incorporated', 'co', 'corp', 'corporation', 'ltd', 'limited'}:
        words.pop()
    return ' '.join(words)


def host(url):
    return (urlsplit(url).hostname or '').casefold().rstrip('.').removeprefix('www.')


def candidate_url(url):
    """Syntactic filtering only; fetcher additionally validates DNS and redirects."""
    try:
        p = urlsplit(str(url))
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return ''
        h = host(url)
        if h == 'localhost' or h.endswith(('.localhost', '.local', '.internal')):
            return ''
        if any(h == b or h.endswith('.' + b) for b in BLOCKED_HOSTS):
            return ''
        try:
            if not ipaddress.ip_address(h).is_global:
                return ''
        except ValueError:
            pass
        if p.path.casefold().endswith(('.pdf', '.jpg', '.png', '.zip')):
            return ''
        return urlunsplit((p.scheme, p.netloc, p.path or '/', p.query, ''))
    except (ValueError, TypeError):
        return ''


@dataclass(frozen=True)
class ConversionBudget:
    searches_per_candidate: int = 2
    hosts_per_candidate: int = 3
    pages_per_candidate: int = 12
    http_workers: int = 1
    browser_workers: int = 1

    def __post_init__(self):
        if not (1 <= self.searches_per_candidate <= 2 and 1 <= self.hosts_per_candidate <= 3
                and 1 <= self.pages_per_candidate <= 12 and 1 <= self.http_workers <= 4
                and self.browser_workers == 1):
            raise ValueError('conversion budget exceeds authorized bounds')


class SearchEvidenceAdapter:
    """Portable public-search observations. Arbitrary verified/email fields ignored.

    A connector/CLI exports observations keyed by immutable directory_record_id.
    Imports remain discovery_only; only the live first-party transport qualifies.
    """
    def __init__(self, observations, budget=None):
        self.observations = observations
        self.budget = budget or ConversionBudget()

    def discover(self, record):
        entries = self.observations.get(record['directory_record_id'], [])
        if len(entries) > self.budget.searches_per_candidate:
            raise ValueError('search budget exceeded')
        found, queries = [], []
        for entry in entries:
            dt = datetime.fromisoformat(str(entry.get('searched_at', '')).replace('Z', '+00:00'))
            if dt.tzinfo is None or not entry.get('query') or not entry.get('provider'):
                raise ValueError('search evidence needs provider/query/timezone')
            if entry.get('status') in RESTRICTED:
                break
            queries.append({k: entry.get(k) for k in ('query', 'provider', 'searched_at', 'status', 'evidence_file')})
            for result in entry.get('results', []):
                url = candidate_url(result.get('url', ''))
                if url and not any(x['url'] == url for x in found):
                    found.append({'url': url, 'title': str(result.get('title', '')),
                        'snippet': str(result.get('snippet', ''))[:500],
                        'query': entry['query'], 'searched_at': entry['searched_at'],
                        'provider': entry['provider'], 'evidence_scope': 'discovery_only'})
        hosts = list(dict.fromkeys(host(x['url']) for x in found))[:self.budget.hosts_per_candidate]
        return [x for x in found if host(x['url']) in hosts][:12], queries


class VisiblePage(HTMLParser):
    def __init__(self, html, base_url=''):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.tag_stack = []
        self.attr_stack, self.base_url = [], base_url
        self.text_parts, self.labels, self.links = [], [], []
        self.title_parts, self.logo_labels = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'script', 'style', 'noscript', 'template'}:
            self.hidden += 1
        self.tag_stack.append(tag)
        self.attr_stack.append(attrs)
        if not self.hidden and tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if not self.hidden and tag == 'img' and attrs.get('alt'):
            self.labels.append(attrs['alt'])
            ancestors = list(zip(self.tag_stack[:-1], self.attr_stack[:-1]))
            home_brand_link = any(t == 'a' and a.get('href') and
                host(urljoin(self.base_url,a['href'])) == host(self.base_url) and
                urlsplit(urljoin(self.base_url,a['href'])).path in {'','/','/index.html','/index.htm'} and
                not urlsplit(urljoin(self.base_url,a['href'])).query and
                re.search(r'logo|site.brand',str(a.get('id','')) + ' ' + str(a.get('class','')),re.I)
                for t,a in ancestors)
            if home_brand_link and 'logo' in ' '.join(str(attrs.get(k,'')) for k in ('alt','class','id','src')).casefold():
                self.logo_labels.append(re.sub(r'\blogo\b', '', attrs['alt'], flags=re.I).strip())

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'template'}:
            self.hidden = max(0, self.hidden - 1)
        if tag in self.tag_stack:
            index = len(self.tag_stack) - 1 - self.tag_stack[::-1].index(tag)
            del self.tag_stack[index:]
            del self.attr_stack[index:]

    def handle_data(self, value):
        if not self.hidden and value.strip():
            self.text_parts.append(value.strip())
            if 'title' in self.tag_stack:
                self.title_parts.append(value.strip())
            if any(t in {'title', 'h1', 'h2'} for t in self.tag_stack):
                self.labels.append(value.strip())

    @property
    def text(self):
        return ' '.join(self.text_parts)


def identity_evidence(record, pages):
    """Full name/explicit DBA in self labels, product context, and known country.

    No domain-token heuristic, generic script strings, or search snippets used.
    Country is not inferred from a .com or a directory listing.
    """
    original = record.get('organization_name') or record['brand_name']
    names = [original]
    if re.search(r'\bDBA\b', original, re.I):
        alias = re.split(r'\bDBA\b', original, flags=re.I)[-1]
        names.append(re.sub(r'\bDIST\.?$', 'Distributors', alias, flags=re.I))
    keys = [name_key(x) for x in names if len(name_key(x)) >= 4]
    text = ' '.join(p['text'] for p in pages)
    homepages = [p for p in pages if urlsplit(p['requested_url']).path in {'','/'}]
    labels = ' '.join(p.get('page_title','') + ' ' + ' '.join(p.get('logo_labels',[])) for p in homepages)
    # A product/category/review title can mention a third-party organization.
    # Require a complete standalone self-name segment or actual logo name.
    self_names = {name_key(re.split(r'\s*[|–—]\s*|\s+-\s+',p.get('page_title',''))[0]) for p in homepages}
    for p in homepages:
        primary = name_key(re.split(r'\s*[|–—]\s*|\s+-\s+',p.get('page_title',''))[0])
        self_names.update(name_key(label) for label in p.get('logo_labels',[]) if primary and
            (name_key(label) == primary or name_key(label).startswith(primary + ' ')))
    matched = next((k for k in keys if k in self_names), '')
    # A DBA may be declared in a first-party contact block instead of title.
    if not matched and len(keys) > 1 and re.search(r'\bDBA\b', text, re.I):
        matched = next((k for k in keys[1:] if ' ' + k + ' ' in ' ' + name_key(text) + ' '), '')
    country = str(record.get('organization_country', '')).casefold()
    country_ok = not country
    country_excerpt = ''
    if country in {'united states', 'us', 'usa'}:
        m = re.search(r'\b(?:United States|USA|U\.S\.A\.|(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\s+\d{5}(?:-\d{4})?)\b', text)
        country_ok = bool(m)
        country_excerpt = m.group(0) if m else ''
    elif country:
        country_ok = country in text.casefold()
        country_excerpt = country if country_ok else ''
    # A website may be a legitimate non-ICP organization; product/organization
    # context is required, not a fabricated relevance assertion.
    context = bool(RELEVANT.search(text) or re.search(r'\b(?:jewelry|candles?|fragrance|apparel|ceramics|handbags?|tea room|bakery|manufactur|distribut|about us)\w*\b', text, re.I))
    return {'verified': bool(matched and country_ok and context),
        'attributed_name': matched, 'country_match': country_ok,
        'country_evidence': country_excerpt, 'self_identity_excerpt': labels[:1200],
        'reason': 'first_party_name_country_context' if matched and country_ok and context else 'OFFICIAL_SITE_IDENTITY_PENDING',
        'page_urls': [p['final_url'] for p in pages]}


def classify(record, pages, identity):
    if not identity.get('verified'):
        return 'IDENTITY_UNVERIFIED', 'insufficient first-party identity'
    text = ' '.join(p['text'] for p in pages)
    match = RELEVANT.search(text)
    if not match:
        if re.search(r'\b(?:cake shoppe|tea room|bakery)\b', text, re.I):
            return 'IRRELEVANT', 'first-party bakery/tea-room business evidence'
        return 'IDENTITY_UNVERIFIED', 'ICP_RELEVANCE_PENDING: no sufficient target-product evidence'
    excerpt = text[max(0, match.start()-100):match.end()+150]
    if re.search(r'\b(?:toy manufacturer|printing manufacturer|contract manufacturer)\b', text, re.I):
        return 'SUPPLIER_OR_COMPETITOR', excerpt
    if re.search(r'\b(?:distributor|distribution)\b', text, re.I):
        return 'DISTRIBUTOR_CANDIDATE', excerpt
    if 'nynow' in record.get('source_platforms', []):
        return 'BRAND_OWNER_CANDIDATE', excerpt
    return 'RETAIL_BUYER_CANDIDATE', excerpt


def load_directory_input(input_dir):
    """Reuse original capture lineage, without trusting imported ownership claims."""
    root = Path(input_dir)
    manifest = validate_manifest(root / 'captures' / 'capture_manifest.json')
    payload = json.loads((root / 'live_directory_result.json').read_text(encoding='utf-8'))
    records = payload['candidates']
    if len(records) != 44:
        raise ValueError('4B1F input must contain the original 44 retained observations')
    captures = {p['capture_id']: p for p in manifest['pages']}
    seen = set()
    for record in records:
        rid = record.get('directory_record_id')
        if not rid or rid in seen or record.get('data_origin_label') != 'LIVE_PUBLIC_CAPTURE' or record.get('fixture_status'):
            raise ValueError('invalid, duplicate, or fixture directory observation')
        seen.add(rid)
        if not record.get('directory_evidence'):
            raise ValueError('missing source evidence')
        for ev in record['directory_evidence']:
            page = captures.get(ev.get('capture_id'))
            if not page or ev.get('source_url') != page['requested_url'] or ev.get('captured_at') != page['captured_at']:
                raise ValueError('capture lineage mismatch')
            visible = VisiblePage(Path(page['_resolved_content_path']).read_text(encoding='utf-8')).text
            if name_key(record['brand_name']) not in name_key(visible):
                raise ValueError('organization absent from captured directory')
    fingerprint = sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return records, {'input_sha256': fingerprint, 'pages_validated': manifest['pages_validated'],
        'capture_integrity_validated': True, 'capture_authenticity_reestablished': False,
        'input_scope': 'existing_4B1F_live_capture_lineage; independent official verification required'}


def attributed_groups(rows):
    groups = {}
    conflicts = set()
    by_name = {}
    for row in rows:
        if not row.get('official_site_verified'):
            continue
        identity = row['website_identity']
        # Same domain AND independently matched organization name AND country.
        key = (host(row['official_website']), identity['attributed_name'], row.get('organization_country', '').casefold())
        groups.setdefault(key, []).append(row)
        by_name.setdefault(identity['attributed_name'], set()).add(key[0])
    for name, domains in by_name.items():
        if len(domains) > 1:
            conflicts.update(row['directory_record_id'] for group in groups.values() for row in group
                             if row['website_identity']['attributed_name'] == name)
    return list(groups.values()), conflicts


def conversion_metrics(rows):
    fixture_rows = [r for r in rows if r.get('validation_scope') != 'live_first_party']
    rows = [r for r in rows if r.get('validation_scope') == 'live_first_party']
    groups, conflicts = attributed_groups(rows)
    verified = [g for g in groups if not any(r['directory_record_id'] in conflicts or r.get('identity_conflict') for r in g)]
    emails = [g for g in verified if any(r.get('business_email') and r.get('email_hygiene_status') == 'ok' for r in g)]
    mx = [g for g in emails if any(r.get('mx_status') == 'ok' and r.get('business_email') for r in g)]
    relevant = {'RETAIL_BUYER_CANDIDATE', 'BRAND_OWNER_CANDIDATE', 'DISTRIBUTOR_CANDIDATE'}
    out = {
        'INPUT_LIVE_DIRECTORY_CANDIDATES': len(rows),
        'ICP_RELEVANT_CANDIDATES': sum(r.get('organization_type') in relevant for r in rows),
        'PUBLIC_SEARCHES_PERFORMED': sum(len(r.get('search_queries', [])) for r in rows),
        'OFFICIAL_SITE_CANDIDATES_FOUND': sum(len(r.get('official_site_candidates', [])) for r in rows),
        'CANDIDATES_WITH_SITE_CLUES': sum(bool(r.get('official_site_candidates')) for r in rows),
        'OFFICIAL_SITES_VERIFIED': len(verified), 'UNIQUE_ORGANIZATIONS_VERIFIED': len(verified),
        'FIRST_PARTY_EMAILS_FOUND': len(emails),
        'B2B_ROLE_EMAILS_FOUND': sum(any(r.get('email_role') in {'wholesale','sales','partnerships','business','trade','orders','info','hello'} and r.get('business_email') for r in g) for g in emails),
        'MX_OK': len(mx), 'HISTORY_SOURCE_AVAILABLE': any(r.get('history_source_available') for r in rows),
        'HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL': sum(any(r.get('history_source_available') and r.get('history_status') == 'new_candidate' and r.get('mx_status') == 'ok' and r.get('business_email') for r in g) for g in mx),
        'DUPLICATES_CONFIRMED': sum(len(g)-1 for g in verified),
        'IDENTITY_CONFLICTS': len(conflicts | {r['directory_record_id'] for r in rows if r.get('identity_conflict')}),
        'ENGINEERING_FIXTURE_SITE_VALIDATIONS': sum(bool(r.get('official_site_verified')) for r in fixture_rows),
        'ENGINEERING_FIXTURE_EMAIL_VALIDATIONS': sum(bool(r.get('business_email')) for r in fixture_rows),
    }
    for source in ('toyfair', 'nynow'):
        out[source.upper() + '_VERIFIED_SITES'] = sum(any(source in r.get('source_platforms', []) for r in g) for g in verified)
        out[source.upper() + '_FIRST_PARTY_EMAILS'] = sum(any(source in r.get('source_platforms', []) and r.get('business_email') for r in g) for g in emails)
    return out


class SiteConversion:
    def __init__(self, records, search, output_dir, input_sha256, *, fetcher=None, extractor=None, mx_checker=None, history=None):
        self.records, self.search = records, search
        self.root, self.input_sha256 = Path(output_dir), input_sha256
        self.fetcher = fetcher or PublicPageFetcher()
        self.extractor = extractor
        self.mx_checker = mx_checker
        self.history = history or HistoryChecker()
        self.history_available = bool(isinstance(self.history, HistoryChecker)
            and self.history.development_copy and self.history.database and self.history.database.is_file())
        self.budget = search.budget
        self.state = {'input_sha256': input_sha256, 'rows': {}, 'stopped_hosts': {}, 'request_log': []}
        checkpoint = self.root / 'checkpoint.json'
        if checkpoint.is_file():
            self.state = json.loads(checkpoint.read_text(encoding='utf-8'))
            if self.state['input_sha256'] != input_sha256:
                raise ValueError('checkpoint input fingerprint mismatch')
        # Reconcile any old capture recognized as a challenge after parser fixes.
        for row in self.state['rows'].values():
            for page in row.get('pages',[]):
                if challenge_page(page.get('html','')):
                    self.state['stopped_hosts'][host(page['final_url'])] = 'access_restricted'
                    for entry in self.state['request_log']:
                        if entry['url'] == page['requested_url']:
                            entry['status'] = 'access_restricted'
                            entry['challenge_reclassified'] = True
                visible = VisiblePage(page.get('html',''), page['final_url'])
                page.update(page_title=' '.join(visible.title_parts), logo_labels=visible.logo_labels)
            row['pages'] = [p for p in row.get('pages',[]) if not challenge_page(p.get('html',''))]
            if row.get('official_site_verified'):
                pages = [p for p in row['pages'] if host(p['final_url']) == host(row['official_website'])]
                identity = identity_evidence(row, pages)
                if not identity['verified']:
                    row.update(official_site_verified=False, business_email='', official_website='',
                        history_status='UNKNOWN', mx_status='unknown', organization_type='IDENTITY_UNVERIFIED',
                        website_identity_status='OFFICIAL_SITE_IDENTITY_PENDING', conversion_status='pending')

    def _save(self):
        save_json(self.root / 'checkpoint.json', self.state)

    def _page(self, url, source, row):
        h = host(url)
        if h in self.state['stopped_hosts'] or row['http_attempts'] >= self.budget.pages_per_candidate:
            return None
        attempted_hosts = row.setdefault('attempted_hosts',list(dict.fromkeys(host(p['url']) for p in self.state['request_log']
            if any(host(c['url']) == host(p['url']) for c in row.get('official_site_candidates',[])))))
        if h not in attempted_hosts:
            if len(attempted_hosts) >= self.budget.hosts_per_candidate:
                return None
            attempted_hosts.append(h)
        row['http_attempts'] += 1
        self._save()  # Persist budget before network; a crash cannot reset it.
        try:
            result = self.fetcher.fetch(url, timeout=10, require_https=True, allowed_domain=h)
        except Exception as exc:
            self.state['request_log'].append({'url': url, 'status': 'network_error', 'error': type(exc).__name__, 'checked_at': now()})
            self._save()
            return None
        self.state['request_log'].append({'url': url, 'status': result.status, 'http_status': result.http_status,
            'final_url': result.final_url, 'checked_at': result.fetched_at, 'error_type': result.error_type})
        if result.status in RESTRICTED or result.http_status in {401,403,429} or challenge_page(result.html):
            self.state['stopped_hosts'][h] = result.status if result.status in RESTRICTED else 'access_restricted'
            self.state['request_log'][-1]['status'] = self.state['stopped_hosts'][h]
        self._save()
        if h in self.state['stopped_hosts'] or result.status != 'ok' or not result.html or not 200 <= int(result.http_status or 0) < 300:
            return None
        final = result.final_url or url
        live_transport = type(self.fetcher) is PublicPageFetcher and result.data_origin in {'', 'LIVE_PUBLIC_CAPTURE'}
        fixture_transport = row['validation_scope'] == 'test_fixture' and result.data_origin == 'LIVE_PUBLIC_CAPTURE'
        if not candidate_url(final) or host(final) != h or not (live_transport or fixture_transport):
            return None
        visible = VisiblePage(result.html, final)
        capture = write_capture(self.root / 'captures', source_platform=source, requested_url=url,
            final_url=final, captured_at=result.fetched_at, capture_method=result.fetch_method,
            http_status=result.http_status, content_type=result.content_type or 'text/html', html=result.html,
            page_category='official_site', data_origin='LIVE_PUBLIC_CAPTURE' if live_transport else 'TEST_FIXTURE')
        manifest_path = self.root / 'captures' / 'capture_manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.is_file() else {'schema_version':'1.0','scope':'discovery_only','pages':[]}
        manifest['pages'].append(capture.to_dict())
        save_json(manifest_path, manifest)
        page = {'url':final, 'requested_url':url, 'final_url':final, 'http_status':result.http_status,
            'http_success':True, 'tls_success':True, 'fetched_at':result.fetched_at,
            'text':visible.text, 'html':result.html, 'self_labels':' '.join(visible.labels), 'page_title':' '.join(visible.title_parts),
            'logo_labels':visible.logo_labels,
            'method':'official_' + next((x for x in LINK_HINTS if x in url.casefold()), 'homepage') + '_page',
            'content_hash':capture.content_sha256, 'capture_id':capture.capture_id,
            'links':[urljoin(final,x) for x in visible.links if any(k in x.casefold() for k in LINK_HINTS)]}
        row.setdefault('pages', []).append(page)
        self._save()
        return page

    def _convert(self, record):
        rid = record['directory_record_id']
        row = self.state['rows'].setdefault(rid, {**record, 'official_site_verified':False,
            'business_email':'', 'history_status':'UNKNOWN', 'mx_status':'unknown', 'http_attempts':0,
            'organization_type':'IDENTITY_UNVERIFIED', 'conversion_status':'pending', 'pages':[],
            'website_identity_status':'OFFICIAL_SITE_IDENTITY_PENDING'})
        row['history_source_available'] = self.history_available
        if not self.history_available:
            row['history_status'] = 'UNKNOWN'
        for key, default in {'website_identity_status':'OFFICIAL_SITE_IDENTITY_PENDING', 'official_website':'',
            'email_role':'', 'email_evidence_url':'', 'email_evidence_excerpt':'', 'email_checked_at':'',
            'email_http_status':None, 'email_final_url':''}.items():
            row.setdefault(key, default)
        row['validation_scope'] = ('test_fixture' if record.get('fixture_status') else
            'live_first_party' if type(self.fetcher) is PublicPageFetcher and record.get('data_origin_label') == 'LIVE_PUBLIC_CAPTURE'
            else 'discovery_only')
        clues, queries = self.search.discover(record)
        previous = row.get('search_queries',[])
        signatures = {(q['provider'],q['query'],q['searched_at']) for q in previous}
        added = [q for q in queries if (q['provider'],q['query'],q['searched_at']) not in signatures]
        if len(previous) + len(added) > self.budget.searches_per_candidate:
            raise ValueError('cumulative search budget exceeded')
        row['search_queries'] = previous + added
        old_clues = row.get('official_site_candidates',[])
        row['official_site_candidates'] = old_clues + [c for c in clues if c['url'] not in {x['url'] for x in old_clues}]
        clues = row['official_site_candidates']
        # Terminal rows are stable. New clues resume only missing-clue observations.
        if row.get('conversion_status') in {'reviewed', 'restricted', 'budget_exhausted'}:
            if row.get('business_email') and row.get('official_site_verified') and (
                row.get('mx_status') in {'dns_error','unknown'} or
                (row.get('history_status') == 'UNKNOWN' and self.history_available)):
                self._qualify(row)
                self._save()
            return
        if not clues:
            row['conversion_status'] = 'search_input_pending'
            self._save()
            return
        source = record['source_platforms'][0]
        accepted = []
        for h in list(dict.fromkeys(host(x['url']) for x in clues)):
            # Candidate/host cap also persists across changed search evidence.
            if h not in row.get('attempted_hosts',[]) and len(row.get('attempted_hosts',[])) >= self.budget.hosts_per_candidate:
                continue
            pages = [p for p in row['pages'] if host(p['final_url']) == h]
            queue = [candidate_url(x['url']) for x in clues if host(x['url']) == h]
            # Root is derived only from an observed URL, never a guessed domain.
            root = urlunsplit(('https', urlsplit(queue[0]).netloc, '/', '', ''))
            queue = list(dict.fromkeys([root] + queue))
            while queue and row['http_attempts'] < self.budget.pages_per_candidate:
                url = candidate_url(queue.pop(0))
                if any(p['requested_url'] == url for p in pages):
                    continue
                page = self._page(url, source, row)
                if h in self.state['stopped_hosts']:
                    break
                if page:
                    pages.append(page)
                    links = list(dict.fromkeys(candidate_url(x) for x in page['links'] if candidate_url(x) and host(x) == h))
                    links.sort(key=lambda x: next((i for i,k in enumerate(LINK_HINTS) if k in x.casefold()),99))
                    queue.extend(x for x in links if x not in queue and not any(p['requested_url']==x for p in pages))
                    identity = identity_evidence(record, pages)
                    # Enough identity and public email clues; spend no extra pages.
                    if identity['verified'] and re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', ' '.join(p['text'] for p in pages), re.I):
                        break
                elif not pages:
                    break  # No alias/path retries after an unsuccessful entry.
            identity = identity_evidence(record, pages)
            if identity['verified']:
                accepted.append((root, identity, pages))
        if len(accepted) > 1:
            row['identity_conflict'] = True
            row['conversion_status'] = 'reviewed'
            row['website_identity_status'] = 'IDENTITY_CONFLICT'
        elif accepted:
            website, identity, pages = accepted[0]
            row.update(official_website=website, official_site_verified=True, website_identity=identity,
                website_identity_status='ORGANIZATION_CONFIRMED', official_site_checked_at=pages[0]['fetched_at'])
            row['organization_type'], row['icp_evidence'] = classify(record, pages, identity)
            self._email(row, pages)
            row['conversion_status'] = 'reviewed'
        else:
            row['website_identity_status'] = 'OFFICIAL_SITE_IDENTITY_PENDING'
            row['conversion_status'] = ('restricted' if all(host(c['url']) in self.state['stopped_hosts'] for c in clues)
                else 'budget_exhausted' if row['http_attempts'] >= self.budget.pages_per_candidate else 'network_or_identity_pending')
        self._save()

    def _email(self, row, pages):
        if self.extractor is None:
            from discovery.discovery_service import _extract_email_evidence
            extractor = _extract_email_evidence
        else:
            extractor = self.extractor
        # Shared extractor sees accepted, same-party pages only. Iterate past
        # rejected third-party/template addresses without changing shared policy.
        valid_pages = [p for p in pages if host(p['final_url']) == host(row['official_website'])
                       and p['http_success'] and p['tls_success']]
        rejected = []
        for _ in range(20):
            result = extractor(valid_pages, row['brand_name'])
            if not result or not result.get('email'):
                break
            email = result['email'].casefold()
            proof = result.get('evidence', {})
            page = next((p for p in valid_pages if p['final_url'] == proof.get('final_url') and email in p['text'].casefold()), None)
            audit = audit_brand_email(email, row['official_website'], proof)
            if page and audit['valid'] and email in result.get('snippet','').casefold():
                role = next((k for k in ('wholesale','sales','partnerships','business','trade','orders','info','hello') if k in email.split('@')[0]), 'other')
                row.update(business_email=email, email_role=role, email_evidence_url=page['final_url'],
                    email_evidence_excerpt=result['snippet'], email_checked_at=page['fetched_at'],
                    email_http_status=page['http_status'], email_final_url=page['final_url'],
                    email_evidence_source_type='first_party_official_page', email_official_identity_verified=True,
                    email_hygiene_status='ok', email_capture_id=page['capture_id'])
                self._qualify(row)
                break
            rejected.append({'email':email, 'reason':audit['reason'] if not audit['valid'] else 'insufficient_visible_first_party_evidence'})
            valid_pages = [{**p, 'text':re.sub(re.escape(email),'',p['text'],flags=re.I),
                'html':re.sub(re.escape(email),'',p['html'],flags=re.I)} for p in valid_pages]
        row['rejected_email_observations'] = rejected

    def _qualify(self,row):
        if self.mx_checker is None:
            from email_hygiene import check_mx_cached
            mx = check_mx_cached(row['business_email'].rsplit('@',1)[1])
        else:
            mx = self.mx_checker(row['business_email'].rsplit('@',1)[1])
        row['mx_evidence'] = mx
        row['mx_status'] = ('ok' if mx.get('has_mx') and mx.get('provider') in {'google','exchange','other'}
            else 'dns_error' if mx.get('provider') in {'dns_error','dns_timeout'} else 'no_route')
        row['history_status'] = self.history(row) if self.history_available else 'UNKNOWN'

    def run(self):
        # Name cues affect ordering only; ICP metrics require live page evidence.
        ordered = sorted(self.records, key=lambda r: (not bool(RELEVANT.search(r['brand_name'])), r['brand_name'].casefold()))
        for record in ordered:
            self._convert(record)
        rows = [self.state['rows'][r['directory_record_id']] for r in self.records]
        groups, conflicts = attributed_groups(rows)
        for row in rows:
            if row['directory_record_id'] in conflicts:
                row['identity_conflict'] = True
                row['website_identity_status'] = 'IDENTITY_CONFLICT'
        self._save()
        metrics = conversion_metrics(rows)
        save_json(self.root / 'conversion_results.json', {'generated_at':now(), 'metrics':metrics, 'records':rows})
        save_json(self.root / 'manual_review.json', [r for r in rows if not r.get('official_site_verified') or r.get('identity_conflict')])
        save_json(self.root / 'organization_groups.json', [[r['directory_record_id'] for r in g] for g in groups])
        return metrics
