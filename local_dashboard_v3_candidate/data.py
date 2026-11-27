"""Bounded read-only catalog. Never import a production business module."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

PRODUCTION_DB = Path.home() / 'WorkBuddy/2026-06-05-15-31-42/roktandrazo-outreach/data/bd_leads.db'
TABLES = {'retail_city_queue', 'lead_discovery_query_state', 'lead_discovery_results', 'leads', 'job_runs', 'provider_request_audit'}


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def readonly(path):
    # No immutable=1: observe the real SQLite WAL snapshot, not an obsolete main file.
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=3)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA query_only=ON')
        def authorize(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if table in TABLES else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION} else sqlite3.SQLITE_DENY
        conn.set_authorizer(authorize)
        conn.execute('BEGIN')
        yield conn
    finally:
        conn.close()


def catalog(path):
    with readonly(path) as conn:
        rows = [dict(r) for r in conn.execute('''
            SELECT c.id,c.city,c.state,c.timezone,c.priority,c.status,c.started_at,c.completed_at,
                   c.completion_reason,c.web_directory_status,c.last_success_at,
                   (SELECT count(*) FROM lead_discovery_results d WHERE d.active_city_id=c.id) candidates,
                   (SELECT count(*) FROM lead_discovery_query_state q WHERE q.active_city_id=c.id
                    AND q.provider=coalesce(nullif(c.active_provider,''),'browser_maps')) query_recorded,
                   (SELECT count(*) FROM lead_discovery_query_state q WHERE q.active_city_id=c.id
                    AND q.provider=coalesce(nullif(c.active_provider,''),'browser_maps') AND q.status='completed') query_completed
            FROM retail_city_queue c ORDER BY c.state,c.priority,c.id LIMIT 10000''')]
    return {'cities': rows, 'observed_at': now(), 'source': '正式库 · 限定字段只读视图',
            'scope': '仅现有城市队列；候选按搜索城市归属，不等于独立组织数或全州覆盖。'}


def merchants(path, city_id, page=1, search='', status='', email_only=False):
    if type(city_id) is not int or not 1 <= city_id <= 9999:
        raise ValueError('城市编号无效')
    if type(page) is not int or not 1 <= page <= 10000 or len(search) > 100 or len(status) > 80:
        raise ValueError('筛选范围无效')
    where = 'd.active_city_id=?'
    args = [city_id]
    if search:
        where += " AND (instr(lower(d.business_name),lower(?))>0 OR CAST(d.id AS TEXT)=?)"
        args += [search, search.removeprefix('ldr:')]
    if status:
        where += ' AND d.validation_status=?'
        args += [status]
    if email_only:
        where += " AND trim(coalesce(l.email,''))<>''"
    join = 'FROM lead_discovery_results d LEFT JOIN leads l ON l.id=d.linked_lead_id '
    with readonly(path) as conn:
        total = conn.execute('SELECT count(*) ' + join + 'WHERE ' + where, args).fetchone()[0]
        rows = [dict(r) for r in conn.execute('''SELECT d.id,d.business_name,d.formatted_address,
            d.city,d.state,d.phone,d.contact_form_url,d.website,d.source_url,d.provider,d.query_family,d.discovered_at,d.last_seen_at,
            d.validation_status,d.rejection_reason,d.history_crosscheck_result,d.linked_lead_id,
            d.evidence_url,d.evidence_snippet,d.official_match,l.email,l.email_source_type,
            l.email_verified_on_official_site,l.evidence_url email_evidence_url,
            l.evidence_snippet email_evidence_snippet,l.review_reason_code,l.review_reason_detail,
            l.status lead_status,l.organization_key,l.sent_at,l.replied_at,l.unsubscribed_at
            ''' + join + 'WHERE ' + where + ' ORDER BY d.id LIMIT 25 OFFSET ?', args + [(page - 1) * 25])]
        statuses = [dict(r) for r in conn.execute('''SELECT validation_status status,count(*) count
            FROM lead_discovery_results WHERE active_city_id=? GROUP BY validation_status ORDER BY count(*) DESC''', (city_id,))]
    return {'items': rows, 'total': total, 'page': page, 'page_size': 25, 'statuses': statuses,
            'observed_at': now(), 'source': '正式库 · lead_discovery_results / leads 限定字段',
            'scope': '历史候选记录；轮次归属未知。候选官网和邮箱不代表已通过资格或发送门禁。'}


def retained(path, city_id, page=1, search='', reason=''):
    """Read-only possible retained leads; not an authoritative classification."""
    if type(city_id) is not int or not 1 <= city_id <= 9999 or type(page) is not int or not 1 <= page <= 10000:
        raise ValueError('城市或页码无效')
    if len(search) > 100 or reason not in {'', 'email', 'website', 'identity'}:
        raise ValueError('筛选无效')
    statuses = ('validation_pending', 'history_check_pending', 'website_lookup_pending',
                'email_extraction_pending', 'review_recovery', 'manual_review_needed',
                'no_public_email', 'website_not_found', 'contact_form_pool', 'identity_review')
    where = "d.active_city_id=? AND d.validation_status IN (" + ','.join('?' for _ in statuses) + ")"
    args = [city_id, *statuses]
    if search:
        where += " AND (instr(lower(d.business_name),lower(?))>0 OR CAST(d.id AS TEXT)=?)"
        args += [search, search.removeprefix('ldr:')]
    if reason == 'email':
        where += " AND trim(coalesce(l.email,''))=''"
    elif reason == 'website':
        where += " AND trim(coalesce(d.website,''))=''"
    elif reason == 'identity':
        where += " AND (d.validation_status IN ('identity_review','review_recovery','manual_review_needed') OR coalesce(d.official_match,0)<>1)"
    join = ' FROM lead_discovery_results d LEFT JOIN leads l ON l.id=d.linked_lead_id '
    with readonly(path) as conn:
        total = conn.execute('SELECT count(*)' + join + 'WHERE ' + where, args).fetchone()[0]
        rows = [dict(row) for row in conn.execute('''SELECT d.id,d.business_name,d.formatted_address,
            d.city,d.state,d.phone,d.contact_form_url,d.website,d.source_url,d.provider,d.query_family,d.discovered_at,
            d.validation_status,d.rejection_reason,d.history_crosscheck_result,d.linked_lead_id,
            d.evidence_url,d.official_match,l.email,l.review_reason_code,l.review_reason_detail
            ''' + join + 'WHERE ' + where + ' ORDER BY d.id LIMIT 25 OFFSET ?', args + [(page-1)*25])]
    return {'items': rows, 'total': total, 'page': page, 'page_size': 25, 'observed_at': now(),
            'source': '正式库只读字段；现有状态的暂定展示，非正式保留线索分类'}


def linked_gate_diagnostics(path, city_id, references):
    """Report an observable gate mismatch without modifying or running either gate."""
    ids = []
    for ref in references[:50]:
        if isinstance(ref, str) and ref.startswith('ldr:') and ref[4:].isdigit():
            ids.append(int(ref[4:]))
    items = []
    with readonly(path) as conn:
        for row_id in ids:
            row = conn.execute('SELECT id,website FROM lead_discovery_results WHERE id=? AND active_city_id=?',
                               (row_id, city_id)).fetchone()
            if not row:
                continue
            url = str(row['website'] or '').strip()
            parsed = urlsplit(url)
            host = (parsed.hostname or '').lower().rstrip('.')
            if parsed.scheme in {'http', 'https'} and (host == 'facebook.com' or host.endswith('.facebook.com')):
                items.append({'ref': f'ldr:{row_id}', 'kind': 'facebook_official_gate_mismatch',
                    'detail': '该记录保存的是 Facebook 链接。城市关闭检查只验证链接协议；关联处理将 Facebook 排除为官网，因此两边条件不一致。',
                    'scope': '该条件足以使当前执行器拒绝此记录；未证明历史每轮的全部原因。'})
    return {'available': True, 'items': items, 'observed_at': now()}


def city_history_totals(path, city_id, provider):
    """City cumulative fields, never attributed to a particular run."""
    if type(city_id) is not int or not 1 <= city_id <= 9999 or not isinstance(provider, str) or len(provider) > 100:
        raise ValueError('参数无效')
    with readonly(path) as conn:
        query = dict(conn.execute('''SELECT sum(duplicate_places) duplicate_sightings,
            sum(provider_errors) provider_errors FROM lead_discovery_query_state
            WHERE active_city_id=? AND provider=?''', (city_id, provider)).fetchone())
        rows = dict(conn.execute('''SELECT count(*) candidate_rows,
            sum(CASE WHEN trim(coalesce(d.website,''))<>'' THEN 1 ELSE 0 END) candidate_websites,
            sum(CASE WHEN d.official_match=1 THEN 1 ELSE 0 END) official_match_rows,
            sum(CASE WHEN trim(coalesce(l.email,''))<>'' THEN 1 ELSE 0 END) linked_email_rows
            FROM lead_discovery_results d LEFT JOIN leads l ON l.id=d.linked_lead_id
            WHERE d.active_city_id=?''', (city_id,)).fetchone())
    return {'available': True, 'observed_at': now(), 'provider': provider, **query, **rows}
