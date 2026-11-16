"""Business fit from separately recorded first-party page evidence.

Search categories and contact evidence are discovery clues, not product evidence.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

_PRODUCT = re.compile(r"\b(?:jigsaw puzzles?|puzzles?|board games?|card games?|toys?|tabletop games?)\b", re.I)
_CUSTOM = re.compile(r"\b(?:custom|personalized|personalised|private[ -]label|bespoke)\b.{0,80}\b(?:puzzles?|toys?|games?|cards?|merchandise|packaging|print(?:ing)?)\b|\b(?:puzzles?|toys?|games?|cards?|merchandise|packaging)\b.{0,80}\b(?:custom|personalized|personalised|private[ -]label|bespoke)\b", re.I)
_INDUSTRIAL = re.compile(r"\b(?:industrial bearings?|ball bearings?|fasteners?|nuts and bolts)\b", re.I)
_COMMERCE = re.compile(r"\b(?:shop|sell|sells|selling|sold|stock|stocks|stocking|carry|carries|offer|offers|offering|store|products?|collections?|make|makes|made|manufacture|manufactures|design|designs|create|creates|print|prints|printing|retail|supply|supplies|speciali[sz]e[sd]?)\b", re.I)
_NEGATION = re.compile(r"\b(?:no|not|without|never|do not|does not|don't|doesn't)\b", re.I)


def _host(url):
    try:
        parsed = urlsplit(str(url or ""))
        if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
            return ""
        return parsed.hostname.lower().rstrip(".").removeprefix("www.")
    except ValueError:
        return ""


def _same_site(website, evidence_url):
    site, evidence = _host(website), _host(evidence_url)
    return bool(site and evidence and (site == evidence or evidence.endswith('.' + site)))


def _supports_product(snippet, match):
    # Require a trading verb before the product, with no intervening customer
    # context or different industrial goods. A product mention alone is weak.
    before = snippet[max(0, match.start()-100):match.start()]
    verbs = list(_COMMERCE.finditer(before))
    if not verbs:
        return False
    context = before[verbs[-1].end():]
    if re.search(r"[.!?;]|\b(?:for|to|against|without|not|no)\b", context, re.I) or _INDUSTRIAL.search(context):
        return False
    if _NEGATION.search(before[max(0, verbs[-1].start()-35):]):
        return False
    after = snippet[match.end():match.end()+55]
    if re.match(r"\s+(?:are|is|were|was)\s+not\b", after, re.I):
        return False
    return True


def classify_business_fit(lead):
    """Return matched, unsuitable, or unknown; never infer fit from a search query."""
    url = str(lead.get('business_evidence_url') or '')
    snippet = str(lead.get('business_evidence_snippet') or '').strip()
    if not snippet or not _same_site(lead.get('official_website'), url):
        return {'status': 'unknown', 'reason': 'business_evidence_missing_or_untrusted'}
    # Product mentions in articles or search terms alone do not establish trade.
    if not _COMMERCE.search(snippet):
        return {'status': 'unknown', 'reason': 'business_activity_not_established', 'url': url, 'snippet': snippet}
    for pattern, reason in ((_CUSTOM, 'custom_product_evidence'), (_PRODUCT, 'target_product_evidence')):
        for match in pattern.finditer(snippet):
            if _supports_product(snippet, match):
                return {'status': 'matched', 'reason': reason, 'url': url, 'snippet': snippet}
    if _INDUSTRIAL.search(snippet):
        return {'status': 'unsuitable', 'reason': 'industrial_product_evidence', 'url': url, 'snippet': snippet}
    return {'status': 'unknown', 'reason': 'business_evidence_not_decisive', 'url': url, 'snippet': snippet}


def evidence_from_official_pages(website, pages):
    """Extract a bounded product sentence only from already verified pages."""
    fallback = None
    for page in pages:
        if not page.get('tls_success') or not page.get('http_success') or not _same_site(website, page.get('url')):
            continue
        for sentence in re.split(r'(?<=[.!?])\s+|[\r\n]+', str(page.get('text') or '')):
            for match in _PRODUCT.finditer(sentence):
                start = max(0, match.start() - 120)
                candidate = {'official_website': website, 'business_evidence_url': page['url'],
                             'business_evidence_snippet': sentence[start:match.end()+120].strip()}
                if classify_business_fit(candidate)['status'] == 'matched':
                    return candidate
            if _INDUSTRIAL.search(sentence):
                match = _INDUSTRIAL.search(sentence)
                fallback = {'official_website': website, 'business_evidence_url': page['url'],
                            'business_evidence_snippet': sentence[max(0, match.start()-100):match.end()+100].strip()}
            if _CUSTOM.search(sentence):
                match = _CUSTOM.search(sentence)
                candidate = {'official_website': website, 'business_evidence_url': page['url'],
                             'business_evidence_snippet': sentence[max(0, match.start()-100):match.end()+100].strip()}
                if classify_business_fit(candidate)['status'] == 'matched':
                    return candidate
    return fallback or {}
