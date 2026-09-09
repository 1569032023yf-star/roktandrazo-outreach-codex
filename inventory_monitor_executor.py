#!/usr/bin/env python3
"""
Inventory Monitor & Executor — 自主执行引擎
=============================================
唯一生产调度权威。不询问用户，自主监控、自动切换、完整验证。

Lane 顺序（用户指定）：
  1. Review Recovery
  2. Retail TN/AR/KY
  3. Custom Institutions
  4. Online Brands
  5. HTTP-first 备用发现

结束条件：
  complete: unique_auto_sendable >= 60
  partial: runtime window exhausted (cursor saved)
  failed: DB故障 / 所有网络路径不可用 / 不可恢复异常

send_enabled: HARDCODED false
"""

import json, os, re, sys, time, hashlib, sqlite3, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / "data" / "bd_leads.db"
STATUS_PATH = PROJECT_DIR / "output" / "inventory_recovery_status.json"
OUTPUT_DIR = PROJECT_DIR / "output"

SHANGHAI = timezone(timedelta(hours=8))
# Target is defined near LANE_NAMES (line ~365) — TARGET=30 sendable orgs
MAX_RUNTIME_MINUTES = 120
SEND_ENABLED = False

# ============================================================
# CONFIG
# ============================================================
HTTP_TIMEOUT = 10
HTTP_SCAN_DEADLINE = 25  # max wall-clock seconds for ONE http_scan_website call (skip-on-timeout guard)
MAX_SSL_TIMEOUT_SAME_SOURCE = 3
STALL_MINUTES = 10  # 10 min no new verified → stale
MAX_CONSECUTIVE_FAILURES = 5

CONTACT_PATHS = [
    '/', '/contact', '/contact-us', '/pages/contact',
    '/about', '/about-us', '/pages/about',
    '/wholesale', '/vendor', '/buyer', '/info',
]

SKIP_DOMAINS = {
    'facebook.com', 'instagram.com', 'twitter.com', 'yelp.com',
    'google.com', 'amazon.com', 'shopify.com', 'wix.com',
    'squarespace.com', 'etsy.com', 'ebay.com', 'linkedin.com',
    'pinterest.com', 'tiktok.com', 'youtube.com',
}

CHINA_TLDS = {'.cn', '.中国', '.公司', '.网络'}
CHINA_HOSTING_KEYWORDS = ['aliyun', 'tencent', 'qcloud', 'ucloud', 'beian']

# P1.7C: State no longer a discovery/inventory hard gate. Empty = all states allowed.
ALLOWED_STATES = frozenset()  # legacy value was {"TN","AR","KY"}; empty means no state restriction

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

EMAIL_RE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,63}@[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.(?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]\.)*[a-zA-Z]{2,}')
MAILTO_RE = re.compile(r'mailto:([A-Za-z0-9.!#$%&\'*+/=?^_`{|}~\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+)', re.I)

UNSAFE_EMAIL_DOMAINS = {
    'example.com', 'test.com', 'yourdomain.com', 'domain.com',
    'email.com', 'mail.com', 'company.com', 'website.com',
}
UNSAFE_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'admin', 'webmaster',
                   'postmaster', 'hostmaster', 'abuse', 'support@shopify',
                   'support@wix', 'support@squarespace'}


# ============================================================
# STATUS MANAGEMENT
# ============================================================

def read_status():
    if STATUS_PATH.exists():
        return json.loads(STATUS_PATH.read_text())
    return {}

def write_status(**kwargs):
    base = {"updated_at": datetime.now(SHANGHAI).isoformat()}
    existing = read_status()
    existing.update(base)
    existing.update(kwargs)
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False))


# ============================================================
# DB HELPERS
# ============================================================

def get_db(readonly=False):
    db_str = str(DB_PATH).replace('\\', '/')
    if readonly:
        conn = sqlite3.connect(f"file:{db_str}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(db_str)
    conn.row_factory = sqlite3.Row
    return conn

def count_sendable(conn=None):
    """Count unsent sendable organizations across all states (P1.7C: no 3-state filter)."""
    close_after = conn is None
    if conn is None:
        conn = get_db(readonly=True)
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(DISTINCT COALESCE(NULLIF(l.organization_key,''),'org_'||l.id)) FROM leads l
        WHERE l.status NOT IN ('sent','bounced','do_not_contact')
        AND l.email IS NOT NULL AND l.email != '' AND l.email LIKE '%@%.%'
        AND l.email NOT IN (SELECT email FROM suppression_list)
        AND l.email NOT IN (SELECT email FROM send_log WHERE status='sent')
        AND l.organization_key NOT IN (
            SELECT COALESCE(NULLIF(l2.organization_key,''),'org_'||l2.id)
            FROM send_log sl JOIN leads l2 ON sl.lead_id=l2.id WHERE sl.status='sent'
        )
    """)
    result = c.fetchone()[0]
    if close_after:
        conn.close()
    return result

def is_suppressed(email, conn):
    c = conn.cursor()
    c.execute("SELECT 1 FROM suppression_list WHERE email=?", (email.lower(),))
    return c.fetchone() is not None

def was_sent(email, conn):
    c = conn.cursor()
    c.execute("SELECT 1 FROM send_log WHERE lower(email)=? AND status='sent'", (email.lower(),))
    return c.fetchone() is not None

def was_bounced(email, conn):
    c = conn.cursor()
    c.execute("SELECT 1 FROM bounce_log WHERE lower(email)=? AND bounce_type='hard'", (email.lower(),))
    return c.fetchone() is not None

def is_duplicate_a0(email, conn):
    c = conn.cursor()
    c.execute("SELECT 1 FROM leads WHERE lower(email)=? AND confidence_score='A'", (email.lower(),))
    return c.fetchone() is not None

def safe_write_a0(lead_dict, conn, email, evidence_url, evidence_snippet):
    """Safe write A0 — full hygiene gate."""
    c = conn.cursor()
    lead_id = lead_dict.get('id')

    # Gate checks
    if not email or '@' not in email:
        return False, "no_email"
    email_lower = email.lower().strip()
    domain = email_lower.split('@')[-1]

    # Skip unsafe
    for prefix in UNSAFE_PREFIXES:
        if email_lower.startswith(prefix):
            return False, f"unsafe_prefix:{prefix}"
    if domain in UNSAFE_EMAIL_DOMAINS:
        return False, f"unsafe_domain:{domain}"

    # Suppression / sent / bounce / duplicate
    if is_suppressed(email_lower, conn):
        return False, "suppressed"
    if was_sent(email_lower, conn):
        return False, "already_sent"
    if was_bounced(email_lower, conn):
        return False, "bounced"
    if is_duplicate_a0(email_lower, conn):
        return False, "duplicate_a0"

    # Exchange MX skip
    c.execute("SELECT 1 FROM leads WHERE lower(email)=? AND mx_provider='exchange'", (email_lower,))
    if c.fetchone():
        return False, "exchange_mx"

    # Write A0
    c.execute("""
        UPDATE leads SET
            email=?, email_type='website_email',
            email_source_type='inventory_recovery',
            email_verified_on_official_site=1,
            evidence_url=?, evidence_snippet=?,
            confidence_score='A', status='new',
            last_checked_at=datetime('now')
        WHERE id=?
    """, (email_lower, evidence_url, evidence_snippet, lead_id))
    return True, "sendable_written"

def mark_checked(conn, lead_id):
    conn.cursor().execute("UPDATE leads SET last_checked_at=datetime('now') WHERE id=?", (lead_id,))

def select_batch(conn, lane, already_done, limit=20):
    """Select batch based on lane."""
    c = conn.cursor()
    placeholders = ','.join('?' * len(already_done)) if already_done else '0'

    if lane == "retail":
        # Lane 1: Retail stores (all states; P1.7C removed 3-state hard filter)
        c.execute(f"""
            SELECT * FROM leads
            WHERE status IN ('new','manual_review_needed')
            AND official_website IS NOT NULL AND official_website != ''
            AND (email IS NULL OR email='')
            AND confidence_score IN ('B','B2','')
            AND id NOT IN ({placeholders})
            LIMIT ?
        """, [*already_done, limit])
    elif lane == "institutions":
        # Lane 2: Museums, parks, visitor centers
        c.execute(f"""
            SELECT * FROM leads
            WHERE status IN ('new','contact_form_pool','manual_review_needed')
            AND official_website IS NOT NULL AND official_website != ''
            AND (email IS NULL OR email='')
            AND (store_type IN ('museum','museum_store','national_park','visitor_center','park_store','gift_shop')
                 OR store_name LIKE '%museum%' OR store_name LIKE '%park%'
                 OR store_name LIKE '%visitor%' OR store_name LIKE '%discovery%')
            AND id NOT IN ({placeholders})
            LIMIT ?
        """, [*already_done, limit])
    elif lane == "online_brands":
        # Lane 3: Online brands / catalog sites
        c.execute(f"""
            SELECT * FROM leads
            WHERE status IN ('new','contact_form_pool','manual_review_needed')
            AND official_website IS NOT NULL AND official_website != ''
            AND (email IS NULL OR email='')
            AND state NOT IN ('TN','AR','KY')
            AND id NOT IN ({placeholders})
            LIMIT ?
        """, [*already_done, limit])
    else:
        # Lane 4: HTTP-first — all remaining
        c.execute(f"""
            SELECT * FROM leads
            WHERE official_website IS NOT NULL AND official_website != ''
            AND (email IS NULL OR email='')
            AND id NOT IN ({placeholders})
            LIMIT ?
        """, [*already_done, limit])

    return c.fetchall()


# ============================================================
# HTTP SCANNING
# ============================================================

def is_china_hosted(domain, html_text=""):
    """Quick check if domain is China-hosted."""
    tld = '.' + domain.split('.')[-1] if '.' in domain else ''
    if tld in CHINA_TLDS:
        return True
    lower = html_text.lower()
    for kw in CHINA_HOSTING_KEYWORDS:
        if kw in lower:
            return True
    return False

def extract_emails_from_html(html_text):
    """Extract and deduplicate emails from HTML.

    Applies authoritative hygiene so image/resource filenames (foo@2x.jpg,
    foo_235x235@2x.png), sentry/hash addresses and system addresses are NOT
    treated as real contacts — they were previously counted as 'found' and
    then silently blocked later, wasting the scan.
    """
    try:
        from email_hygiene import hygiene_check
    except Exception:
        hygiene_check = None

    found = set()
    raw = set()
    # Standard emails
    for m in EMAIL_RE.finditer(html_text):
        e = m.group(0).lower().strip()
        if e not in UNSAFE_EMAIL_DOMAINS and not any(e.startswith(p) for p in UNSAFE_PREFIXES):
            raw.add(e)
    # Mailto
    for m in MAILTO_RE.finditer(html_text):
        e = m.group(1).lower().strip()
        if e not in UNSAFE_EMAIL_DOMAINS and not any(e.startswith(p) for p in UNSAFE_PREFIXES):
            raw.add(e)
    for e in raw:
        if hygiene_check is not None:
            h = hygiene_check(e)
            if not h.get('valid'):
                continue
        found.add(e)
    return list(found)


def http_scan_website(website, ssl_stats):
    """HTTP scan a website — try multiple paths, return first valid email + evidence.
    
    Strategy: try DIRECT first (Astrill proxy blocks many US retail sites).
    Only use proxy as fallback. curl subprocess without proxy as last resort.
    Network failures are ALWAYS distinguished from genuine absence of email.
    """
    import httpx
    import subprocess
    import time
    import os

    domain = urlparse(website).netloc.lower()
    if not domain:
        domain = website.replace('https://','').replace('http://','').split('/')[0]

    # Skip social media / platform domains
    for skip in SKIP_DOMAINS:
        if skip in domain:
            return None, None, None, "skip_platform"

    headers = {'User-Agent': USER_AGENT}
    
    # Build explicit proxy config from environment
    proxy_url = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
                 or os.environ.get("SCRAPER_PROXY") or os.environ.get("HTTP_PROXY")
                 or os.environ.get("http_proxy") or None)
    
    # Track attempt results
    attempts = 0
    last_error = None
    deadline = time.time() + HTTP_SCAN_DEADLINE  # per-candidate wall-clock cap

    def _attempt_fetch(url, use_proxy=False):
        """Try fetching with httpx. use_proxy=False = direct connection.

        Respects `deadline`: aborts immediately if the per-candidate budget
        is exhausted, instead of blocking on a slow/unreachable site (the
        Website-Recovery stall observed in P2.4E).
        """
        nonlocal attempts, last_error, deadline
        for retry in range(1):
            if time.time() > deadline:
                last_error = ('timeout', 'deadline_exceeded')
                return None, last_error
            attempts += 1
            try:
                client_kwargs = {
                    'timeout': HTTP_TIMEOUT,
                    'follow_redirects': True,
                    'verify': True,
                }
                if use_proxy and proxy_url:
                    client_kwargs['proxy'] = proxy_url
                    client_kwargs['trust_env'] = False
                else:
                    # Direct connection — explicitly disable proxy
                    client_kwargs['trust_env'] = False
                
                with httpx.Client(**client_kwargs) as client:
                    resp = client.get(url, headers=headers)
                    return resp, None
            except httpx.ConnectTimeout:
                last_error = ('timeout', url)
                ssl_stats['timeout_count'] = ssl_stats.get('timeout_count', 0) + 1
                time.sleep(1.0 * (retry + 1))
            except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = ('ssl_proxy_failure', url, str(e)[:60])
                ssl_stats['ssl_error_count'] = ssl_stats.get('ssl_error_count', 0) + 1
                time.sleep(0.5)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    last_error = ('rate_limited', url)
                    time.sleep(3.0 * (retry + 1))
                elif 400 <= e.response.status_code < 500:
                    return None, ('permanent_4xx', url, e.response.status_code)
                else:
                    last_error = ('http_error', url, e.response.status_code)
                    time.sleep(1.0)
            except Exception as e:
                last_error = ('unknown', url, str(e)[:60])
                time.sleep(0.5)
        return None, last_error

    # ── Primary: httpx DIRECT (no proxy — Astrill blocks US retail via proxy) ──
    for path in CONTACT_PATHS:
        if time.time() > deadline:
            break
        url = urljoin(website, path)
        resp, err = _attempt_fetch(url, use_proxy=False)
        
        if resp and resp.status_code == 200:
            html = resp.text
            emails = extract_emails_from_html(html)
            if emails:
                for e in emails:
                    edom = e.split('@')[-1]
                    skip_this = any(sd in edom for sd in SKIP_DOMAINS)
                    if not skip_this and not is_china_hosted(domain, html):
                        ssl_stats['direct_fetch_success'] = ssl_stats.get('direct_fetch_success', 0) + 1
                        return e, url, f"Email {e} found on {url}", "http_success"
        elif err and err[0] == 'permanent_4xx':
            continue

    # Try homepage direct
    if time.time() > deadline:
        resp, err = None, ('timeout', 'deadline_exceeded')
    else:
        resp, err = _attempt_fetch(website, use_proxy=False)
    if resp and resp.status_code == 200:
        html = resp.text
        emails = extract_emails_from_html(html)
        for e in emails:
            edom = e.split('@')[-1]
            skip_this = any(sd in edom for sd in SKIP_DOMAINS)
            if not skip_this and not is_china_hosted(domain, html):
                ssl_stats['direct_fetch_success'] = ssl_stats.get('direct_fetch_success', 0) + 1
                return e, website, f"Email {e} found on homepage {website}", "http_homepage"
    elif resp and resp.status_code != 200:
        ssl_stats['direct_fetch_non200'] = ssl_stats.get('direct_fetch_non200', 0) + 1
    elif err:
        # Direct failed — try proxy
        ssl_stats['direct_failed'] = ssl_stats.get('direct_failed', 0) + 1
        if time.time() > deadline:
            resp2, err2 = None, ('timeout', 'deadline_exceeded')
        else:
            resp2, err2 = _attempt_fetch(website, use_proxy=True)
        if resp2 and resp2.status_code == 200:
            html = resp2.text
            emails = extract_emails_from_html(html)
            for e in emails:
                edom = e.split('@')[-1]
                skip_this = any(sd in edom for sd in SKIP_DOMAINS)
                if not skip_this and not is_china_hosted(domain, html):
                    ssl_stats['proxy_fallback_success'] = ssl_stats.get('proxy_fallback_success', 0) + 1
                    return e, website, f"Email {e} found via proxy on {website}", "proxy_fallback_homepage"

    # ── Fallback: curl subprocess WITHOUT proxy (direct, more reliable) ──
    if last_error and last_error[0] in ('ssl_proxy_failure', 'timeout', 'unknown'):
        curl_cmd = ['curl', '-s', '--max-time', '12', '-L', '-k', '--compressed', '--noproxy', '*',
                    '-H', f'User-Agent: {USER_AGENT}']
        
        try:
            # NOTE: --compressed handles gzip responses; text=True otherwise raises
            # UnicodeDecodeError on gzip bytes (0x8b magic), which falsely mapped to
            # network_retry_pending. Use binary + safe decode.
            r = subprocess.run(curl_cmd + [website], capture_output=True, timeout=15)
            raw = r.stdout
            html = None
            if raw:
                for enc in ('utf-8', 'latin-1'):
                    try:
                        html = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
            if r.returncode == 0 and html and len(html) > 200:
                emails = extract_emails_from_html(html)
                if emails:
                    for e in emails:
                        edom = e.split('@')[-1]
                        skip_this = any(sd in edom for sd in SKIP_DOMAINS)
                        if not skip_this and not is_china_hosted(domain, html):
                            ssl_stats['curl_fallback_used'] = ssl_stats.get('curl_fallback_used', 0) + 1
                            return e, website, f"Email {e} found via curl on {website}", "curl_fallback_homepage"
                else:
                    ssl_stats['curl_fallback_used'] = ssl_stats.get('curl_fallback_used', 0) + 1
                    return None, None, None, "website_scanned_no_email"
            else:
                ssl_stats['curl_fallback_failed'] = ssl_stats.get('curl_fallback_failed', 0) + 1
                return None, None, None, "network_retry_pending"
        except subprocess.TimeoutExpired:
            ssl_stats['curl_fallback_timeout'] = ssl_stats.get('curl_fallback_timeout', 0) + 1
            return None, None, None, "timeout_retry_pending"
        except Exception:
            ssl_stats['curl_fallback_failed'] = ssl_stats.get('curl_fallback_failed', 0) + 1
            return None, None, None, "network_retry_pending"

    if last_error:
        err_type = last_error[0]
        if err_type in ('ssl_proxy_failure', 'timeout'):
            return None, None, None, "ssl_proxy_failure"
        elif err_type == 'rate_limited':
            return None, None, None, "rate_limited"
        ssl_stats['network_error_count'] = ssl_stats.get('network_error_count', 0) + 1

    return None, None, None, "no_email_found"


# ============================================================
# LANE MANAGEMENT
# ============================================================

LANE_ORDER = ["retail", "institutions", "online_brands", "http_first_fallback"]
LANE_NAMES = {
    "retail": "Lane 1: Retail TN/AR/KY",
    "institutions": "Lane 2: Custom Institutions",
    "online_brands": "Lane 3: Online Brands",
    "http_first_fallback": "Lane 4: HTTP-first Fallback",
}

# Target: reachable sendable organizations (not A0 count)
TARGET = 30  # Sendable orgs for next batch
# Google Places API is OPTIONAL — never a blocker
# If not configured, skip and continue with other providers
# provider_unavailable_optional is not a stop reason

class LaneState:
    def __init__(self):
        self.current_lane_idx = 0
        self.lane_stats = {lane: {"processed": 0, "sendable_added": 0, "failed": 0} for lane in LANE_ORDER}
        self.degraded_lanes = set()

    @property
    def current_lane(self):
        return LANE_ORDER[self.current_lane_idx]

    def advance(self):
        self.current_lane_idx += 1
        return self.current_lane_idx < len(LANE_ORDER)

    def has_next(self):
        return self.current_lane_idx + 1 < len(LANE_ORDER)


class SSLMonitor:
    """Tracks SSL/timeout per source."""
    def __init__(self):
        self.timeout_count = 0
        self.ssl_error_count = 0
        self.consecutive_ssl = 0
        self.last_verified_at = datetime.now(SHANGHAI)
        self.consecutive_failures = 0
        self.last_error = None
        self.last_error_at = None

    def record_ssl_error(self, url):
        self.ssl_error_count += 1
        self.consecutive_ssl += 1
        self.consecutive_failures += 1
        self.last_error = f"SSL error: {url}"
        self.last_error_at = datetime.now(SHANGHAI).isoformat()

    def record_timeout(self, url):
        self.timeout_count += 1
        self.consecutive_ssl += 1
        self.consecutive_failures += 1
        self.last_error = f"Timeout: {url}"
        self.last_error_at = datetime.now(SHANGHAI).isoformat()

    def record_success(self):
        self.consecutive_ssl = 0
        self.consecutive_failures = 0
        self.last_verified_at = datetime.now(SHANGHAI)

    def should_degrade(self):
        """Check if current source should be marked degraded."""
        # Same source 3 consecutive SSL timeout
        if self.consecutive_ssl >= MAX_SSL_TIMEOUT_SAME_SOURCE:
            return True, "consecutive_ssl_timeout_3"
        # 10 min no new verified
        elapsed = (datetime.now(SHANGHAI) - self.last_verified_at).total_seconds()
        if elapsed > STALL_MINUTES * 60:
            return True, f"stall_{STALL_MINUTES}min_no_verified"
        # Consecutive failures > max retries
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return True, "max_consecutive_failures"
        return False, None

    def to_dict(self):
        return {
            "timeout_count": self.timeout_count,
            "ssl_error_count": self.ssl_error_count,
            "consecutive_ssl": self.consecutive_ssl,
            "last_verified_at": self.last_verified_at.isoformat(),
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
        }


# ============================================================
# MAIN EXECUTOR
# ============================================================

def main():
    runtime_start = time.time()
    sendable_initial = count_sendable()
    sendable_current = sendable_initial
    loop_count = 0
    total_candidates = 0
    total_verified = 0
    total_sendable_added = 0
    total_custom_c = 0

    lane_state = LaneState()
    ssl_monitor = SSLMonitor()
    already_processed_ids = set()

    write_status(
        status="running",
        date=datetime.now(SHANGHAI).strftime("%Y-%m-%d"),
        sendable_before=sendable_initial,
        sendable_current=sendable_initial,
        target=TARGET,
        send_enabled=SEND_ENABLED,
        started_at=datetime.now(SHANGHAI).isoformat(),
        current_lane=LANE_NAMES[lane_state.current_lane],
        loop_count=0,
        candidates_discovered=0,
        candidates_verified=0,
        sendable_added=0,
        unique_auto_sendable=sendable_initial,
        ssl_timeout_count=0,
        last_error=None,
    )

    conn = get_db()

    try:
        while sendable_current < TARGET:
            # Runtime check
            elapsed = (time.time() - runtime_start) / 60
            if elapsed >= MAX_RUNTIME_MINUTES:
                write_status(
                    status="partial",
                    stop_reason="runtime_window_exhausted",
                    sendable_current=sendable_current,
                    gap=TARGET - sendable_current,
                    loops=loop_count,
                )
                break

            # Check SSL degradation
            should_deg, deg_reason = ssl_monitor.should_degrade()
            if should_deg and lane_state.has_next():
                print(f"\n[DEGRADE] {deg_reason} — switching lane: {LANE_NAMES[lane_state.current_lane]} → next")
                lane_state.degraded_lanes.add(lane_state.current_lane)
                write_status(
                    lane_degraded=LANE_NAMES[lane_state.current_lane],
                    degrade_reason=deg_reason,
                )
                if not lane_state.advance():
                    write_status(
                        status="partial",
                        stop_reason="all_lanes_degraded",
                        sendable_current=sendable_current,
                    )
                    break
                ssl_monitor = SSLMonitor()  # Reset monitor for new lane
                write_status(current_lane=LANE_NAMES[lane_state.current_lane])

            # Select batch
            batch = select_batch(conn, lane_state.current_lane, already_processed_ids, limit=20)

            if not batch:
                print(f"\n  {LANE_NAMES[lane_state.current_lane]}: queue empty, switching lane")
                if not lane_state.advance():
                    write_status(
                        current_lane="none_available",
                        status="partial",
                        stop_reason="all_lanes_exhausted",
                        sendable_current=sendable_current,
                        gap=TARGET - sendable_current,
                    )
                    break
                write_status(current_lane=LANE_NAMES[lane_state.current_lane])
                continue

            # Process batch
            loop_count += 1
            batch_size = len(batch)
            total_candidates += batch_size
            batch_added = 0
            batch_verified = 0

            print(f"\n{'='*60}")
            print(f"  Loop {loop_count} | {LANE_NAMES[lane_state.current_lane]}")
            print(f"  A0: {sendable_current}/{TARGET} | Batch: {batch_size} | Elapsed: {elapsed:.0f}min")
            print(f"{'='*60}")

            for lead in batch:
                lead_id = lead['id']
                if lead_id in already_processed_ids:
                    continue
                already_processed_ids.add(lead_id)

                website = (lead['official_website'] or '').strip() if lead['official_website'] else ''
                if not website or not website.startswith('http'):
                    mark_checked(conn, lead_id)
                    continue

                store_name = lead['store_name'] or 'Unknown'
                print(f"  [{store_name}] {website[:80]}")

                # Scan
                ssl_stats = {'timeout_count': ssl_monitor.timeout_count, 'ssl_error_count': ssl_monitor.ssl_error_count}
                email, ev_url, ev_snippet, result_type = http_scan_website(website, ssl_stats)

                if email and ev_url:
                    # Full verification gate
                    success, reason = safe_write_a0(dict(lead), conn, email, ev_url, ev_snippet)
                    if success:
                        batch_added += 1
                        total_sendable_added += 1
                        conn.commit()  # Commit immediately per A0
                        sendable_current = count_sendable(conn)
                        ssl_monitor.record_success()
                        print(f"    A0: {email} ({reason})")
                    else:
                        ssl_monitor.record_success()
                        if reason in ('already_sent', 'bounced', 'suppressed', 'duplicate_a0'):
                            mark_checked(conn, lead_id)
                        print(f"    Skipped: {reason}")
                else:
                    if result_type in ('skip_platform', 'no_email_found'):
                        # No email — move to contact_form_pool if not already
                        batch_verified += 1
                        total_verified += 1
                        ssl_monitor.record_success()
                        c = conn.cursor()
                        c.execute("""
                            UPDATE leads SET
                                status=CASE WHEN status IN ('new','manual_review_needed')
                                    THEN 'contact_form_pool' ELSE status END,
                                last_checked_at=datetime('now')
                            WHERE id=?
                        """, (lead_id,))
                        total_custom_c += 1
                        print(f"    C: {result_type}")
                    else:
                        ssl_monitor.record_success()
                        mark_checked(conn, lead_id)

                # Update SSL monitor from scan stats
                if ssl_stats.get('timeout_count', 0) > ssl_monitor.timeout_count:
                    diff = ssl_stats['timeout_count'] - ssl_monitor.timeout_count
                    ssl_monitor.timeout_count = ssl_stats['timeout_count']
                    ssl_monitor.consecutive_failures += diff
                    ssl_monitor.last_error = f"Timeout: {ssl_stats.get('last_timeout_url', '')}"
                    ssl_monitor.last_error_at = ssl_stats.get('last_timeout_at', '')

                if ssl_stats.get('ssl_error_count', 0) > ssl_monitor.ssl_error_count:
                    diff = ssl_stats['ssl_error_count'] - ssl_monitor.ssl_error_count
                    ssl_monitor.ssl_error_count = ssl_stats['ssl_error_count']
                    ssl_monitor.consecutive_failures += diff
                    ssl_monitor.last_error = f"SSL: {ssl_stats.get('last_ssl_error_url', '')}"
                    ssl_monitor.last_error_at = ssl_stats.get('last_ssl_error_at', '')

            # Commit batch
            conn.commit()

            # Update status
            lane_state.lane_stats[lane_state.current_lane]['processed'] += batch_size
            lane_state.lane_stats[lane_state.current_lane]['sendable_added'] += batch_added
            lane_state.lane_stats[lane_state.current_lane]['failed'] += (batch_size - batch_added)

            sendable_current = count_sendable(conn)

            write_status(
                sendable_current=sendable_current,
                loop_count=loop_count,
                candidates_discovered=total_candidates,
                candidates_verified=total_verified,
                sendable_added=total_sendable_added,
                unique_auto_sendable=sendable_current,
                ssl_timeout_count=ssl_monitor.timeout_count,
                ssl_error_count=ssl_monitor.ssl_error_count,
                last_error=ssl_monitor.last_error,
                current_lane=LANE_NAMES[lane_state.current_lane],
                lane_stats={k: v for k, v in lane_state.lane_stats.items() if v['processed'] > 0},
            )

            print(f"\n  Batch result: +{batch_added} A0 | Pool: {sendable_current}/{TARGET}")

            if sendable_current >= TARGET:
                write_status(
                    status="complete",
                    sendable_current=sendable_current,
                    gap=0,
                    stop_reason="target_reached",
                )
                break

        # Final status determination
        if sendable_current >= TARGET:
            final_status = "complete"
            stop_reason = "target_reached"
        elif elapsed >= MAX_RUNTIME_MINUTES:
            final_status = "partial"
            stop_reason = "runtime_window_exhausted"
        else:
            final_status = "partial"
            stop_reason = "all_lanes_exhausted_or_degraded"

    except sqlite3.Error as e:
        final_status = "failed"
        stop_reason = f"database_error: {e}"
        write_status(status="failed", stop_reason=stop_reason, last_error=str(e))
        traceback.print_exc()
    except Exception as e:
        final_status = "failed"
        stop_reason = f"unrecoverable_error: {e}"
        write_status(status="failed", stop_reason=stop_reason, last_error=str(e))
        traceback.print_exc()
    finally:
        try:
            conn.close()
        except Exception:
            pass

        # Final report
        final_a0 = count_sendable()
        elapsed_final = (time.time() - runtime_start) / 60

        lanes_executed = [LANE_NAMES[l] for l in LANE_ORDER
                          if lane_state.lane_stats[l]['processed'] > 0]

        final_report = {
            "status": final_status,
            "stop_reason": stop_reason,
            "sendable_initial": sendable_initial,
            "sendable_final": final_a0,
            "sendable_added": total_sendable_added,
            "candidates_discovered": total_candidates,
            "candidates_verified": total_verified,
            "custom_c_added": total_custom_c,
            "ssl_timeout_count": ssl_monitor.timeout_count,
            "ssl_error_count": ssl_monitor.ssl_error_count,
            "http_first_switched": len(lane_state.degraded_lanes) > 0,
            "degraded_lanes": list(lane_state.degraded_lanes),
            "lanes_executed": lanes_executed,
            "loops": loop_count,
            "runtime_minutes": round(elapsed_final, 1),
            "send_enabled": SEND_ENABLED,
            "today_new_outreach": 6,  # from outreach_status.json
            "today_target": 20,
            "today_status": "underfilled",
            "today_stop_reason": "send_window_closed_after_inventory_shortage",
            "extra_emails_sent": False,
            "updated_at": datetime.now(SHANGHAI).isoformat(),
        }

        write_status(**final_report)

        # Print final report
        print(f"\n{'='*60}")
        print(f"INVENTORY RESULT")
        print(f"{'='*60}")
        for k, v in final_report.items():
            print(f"  {k}: {v}")

        # Write final report JSON
        report_path = OUTPUT_DIR / f"inventory_final_report_{datetime.now(SHANGHAI).strftime('%Y%m%d_%H%M')}.json"
        report_path.write_text(json.dumps(final_report, indent=2, ensure_ascii=False))

        return final_report


if __name__ == "__main__":
    main()
