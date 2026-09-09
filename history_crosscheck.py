"""Historical identity and delivery checks shared by discovery and manual email review.

Return values:
  new_candidate               — no match found, safe to insert
  exact_duplicate             — same business + same address/place → true duplicate
  same_organization_new_location — same org, DIFFERENT address → create new location
  related_location            — related but not same org (e.g. shared domain only)
  identity_duplicate_new_email — same business identity, different email
  previously_sent             — email has been sent before
  suppressed_or_unsubscribed  — email in suppression list
  bounced                     — email has hard/policy bounce
  rejected                    — previously rejected in review
"""
from __future__ import annotations

import re
import sqlite3
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def normalize_email(value: str) -> str:
    value = str(value or '').strip().lower()
    if any(ch.isspace() for ch in value) or ',' in value or ';' in value or not EMAIL_RE.fullmatch(value):
        return ''
    return value


def host(value: str) -> str:
    raw = str(value or '').strip().lower()
    if raw and '://' not in raw:
        raw = 'https://' + raw
    return (urlparse(raw).hostname or '').removeprefix('www.')


def normalized_identity(candidate: dict) -> str:
    return '|'.join(re.sub(r'\W+', '', str(candidate.get(key, '')).lower()) for key in ('store_name', 'city', 'state')) + '|' + host(candidate.get('official_website', ''))


def _norm_address(value: str) -> str:
    text = str(value or '').lower().strip()
    text = text.replace(' street', ' st').replace(' avenue', ' ave').replace(' road', ' rd')
    text = text.replace(' pike', ' pk').replace(' drive', ' dr').replace(' lane', ' ln')
    text = text.replace(' boulevard', ' blvd').replace(' highway', ' hwy')
    return re.sub(r'\W+', '', text)


def _norm_phone(value: str) -> str:
    digits = re.sub(r'\D+', '', str(value or ''))
    return digits[1:] if len(digits) == 11 and digits.startswith('1') else digits


def _exists(conn, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def _columns(conn, table: str) -> set[str]:
    if not _exists(conn, table):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def cross_check(conn: sqlite3.Connection, candidate: dict, exclude_lead_id: int | None = None) -> dict:
    """Read all historical records.

    Key distinction:
    - exact_duplicate: same business name + same city/state + SAME address → true duplicate
    - same_organization_new_location: related business identity match but DIFFERENT address → new location, same org
    - related_location: shared domain or email, different business → separate org, just related
    """
    email = normalize_email(candidate.get('email', ''))
    website_host = host(candidate.get('official_website', ''))
    name = re.sub(r'\W+', '', str(candidate.get('store_name', '')).lower())
    city, state = str(candidate.get('city', '')).lower(), str(candidate.get('state', '')).upper()
    cand_addr = candidate.get('normalized_address') or _norm_address(candidate.get('formatted_address', ''))
    cand_phone = candidate.get('normalized_phone') or _norm_phone(candidate.get('phone', ''))

    where_excl = ' AND id != ?' if exclude_lead_id else ''
    params = (exclude_lead_id,) if exclude_lead_id else ()
    related = []
    lead_cols = _columns(conn, 'leads')
    select_cols = [c for c in ('id', 'email', 'store_name', 'city', 'state', 'official_website', 'formatted_address',
                               'normalized_address', 'phone', 'normalized_phone', 'status', 'review_status', 'unsubscribed_at',
                               'lead_identity_hash', 'domain_hash') if c in lead_cols]
    if not select_cols:
        return new_candidate_result(email, website_host)

    for row in conn.execute(f"SELECT {', '.join(select_cols)} FROM leads WHERE 1=1{where_excl}", params):
        item = dict(row)
        item_email = normalize_email(item.get('email', ''))
        same_email = bool(email and item_email == email)
        item_addr = item.get('normalized_address') or _norm_address(item.get('formatted_address', ''))
        item_phone = item.get('normalized_phone') or _norm_phone(item.get('phone', ''))

        # Business identity: same normalized name + city + state
        item_name = re.sub(r'\W+', '', str(item.get('store_name', '')).lower())
        same_business_identity = bool(name and item_name == name and
                                       city == str(item.get('city', '')).lower() and
                                       state == str(item.get('state', '')).upper())

        # Location match: same address or same phone
        same_location_addr = bool(cand_addr and item_addr and cand_addr == item_addr)
        same_location_phone = bool(cand_phone and item_phone and cand_phone == item_phone)
        same_location = same_location_addr or same_location_phone

        # Same organization: shared domain or shared business identity
        same_domain = bool(website_host and website_host == host(item.get('official_website', '')))
        same_org = same_business_identity or (same_domain and (same_email or (name and item_name)))
        same_site = same_domain and same_business_identity

        if same_email or same_business_identity or same_domain:
            if same_location_addr:
                item['match_type'] = 'exact_location_match'
            elif same_business_identity:
                item['match_type'] = 'business_identity_different_location'
            elif same_email:
                item['match_type'] = 'exact_email'
            elif same_domain:
                item['match_type'] = 'shared_domain'
            else:
                item['match_type'] = 'related'
            item['same_organization'] = same_org
            # Address is the location identity. A chain may publish one shared
            # phone number for multiple physical stores, so phone alone must
            # not collapse distinct addresses.
            item['same_location'] = same_location_addr
            item['location_comparable'] = bool(cand_addr and item_addr)
            item['same_business_identity'] = same_business_identity
            item['same_domain'] = same_domain
            related.append(item)

    # Determine if this is a shared-org different-location case
    has_org_match_different_location = any(
        r.get('same_organization') and r.get('location_comparable') and not r.get('same_location')
        for r in related
    )
    has_exact_location_match = any(r.get('same_location') for r in related)

    # Check send/bounce/suppression
    email_sent = bool(email and _exists(conn, 'send_log') and
                      conn.execute("SELECT 1 FROM send_log WHERE lower(email)=? AND status='sent'", (email,)).fetchone())
    bounce_cols = _columns(conn, 'bounce_log')
    bounce_matches, bounce_params = [], []
    if email and 'email' in bounce_cols:
        bounce_matches.append('lower(email)=?'); bounce_params.append(email)
    if candidate.get('id') and 'lead_id' in bounce_cols:
        bounce_matches.append('lead_id=?'); bounce_params.append(candidate['id'])
    email_bounced = bool(bounce_matches and conn.execute(
        "SELECT 1 FROM bounce_log WHERE (" + " OR ".join(bounce_matches) + ") "
        "AND lower(COALESCE(bounce_type,'')) IN ('hard','policy','permanent')", tuple(bounce_params)
    ).fetchone())
    suppressed = bool(email and _exists(conn, 'suppression_list') and
                      conn.execute("SELECT 1 FROM suppression_list WHERE lower(email)=?", (email,)).fetchone())
    replied = bool(email and _exists(conn, 'reply_log') and
                   conn.execute("SELECT 1 FROM reply_log WHERE lower(email)=?", (email,)).fetchone())
    sent_related = bool(related and _exists(conn, 'send_log') and
                        conn.execute("SELECT 1 FROM send_log WHERE status='sent' AND lead_id IN (%s)" %
                                     ','.join('?' * len(related)), tuple(r['id'] for r in related)).fetchone())
    rejected = any(r.get('review_status') == 'rejected' or r.get('status') == 'review_rejected' for r in related)
    unsubscribed = suppressed or any(r.get('status') == 'unsubscribed' or r.get('unsubscribed_at') for r in related)

    # Result priority (highest first)
    if suppressed:
        result = 'suppressed_or_unsubscribed'
    elif email_bounced:
        result = 'bounced'
    elif email_sent or sent_related:
        result = 'previously_sent'
    elif rejected:
        result = 'rejected'
    elif has_exact_location_match:
        # Same business + same address → true duplicate
        result = 'exact_duplicate'
    elif has_org_match_different_location:
        # Same organization, different location → create new location
        result = 'same_organization_new_location'
    elif related and any(
        r['match_type'] == 'exact_email'
        or (r.get('same_business_identity') and not r.get('location_comparable'))
        for r in related
    ):
        result = 'identity_duplicate_new_email'
    elif related:
        result = 'related_location'
    else:
        result = 'new_candidate'

    return {'result': result, 'email': email, 'related_leads': related,
            'previously_sent': email_sent or sent_related,
            'hard_bounced': email_bounced, 'suppressed': suppressed,
            'unsubscribed': unsubscribed, 'replied': replied, 'rejected': rejected,
            'domain_match': bool(website_host and email.endswith('@' + website_host)),
            'has_org_match': has_org_match_different_location,
            'has_location_match': has_exact_location_match}


def new_candidate_result(email: str, website_host: str) -> dict:
    return {'result': 'new_candidate', 'email': email, 'related_leads': [],
            'previously_sent': False, 'hard_bounced': False, 'suppressed': False,
            'unsubscribed': False, 'replied': False, 'rejected': False,
            'domain_match': bool(website_host and email.endswith('@' + website_host)),
            'has_org_match': False, 'has_location_match': False}
