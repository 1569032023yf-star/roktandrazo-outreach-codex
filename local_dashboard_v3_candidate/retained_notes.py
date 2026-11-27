"""Append-only local annotations; no production or sending permissions."""
from contextlib import closing
from datetime import datetime, timezone
import sqlite3
import json
from urllib.parse import urlsplit
from . import data


class VersionConflict(Exception):
    pass


def _connect(store):
    store.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(store / 'retained_notes.sqlite3'), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS annotations (
        city_id INTEGER NOT NULL, discovery_id INTEGER NOT NULL, revision INTEGER NOT NULL,
        created_at TEXT NOT NULL, website TEXT NOT NULL, email TEXT NOT NULL,
        contact TEXT NOT NULL, note TEXT NOT NULL, evidence TEXT NOT NULL, verified INTEGER NOT NULL,
        PRIMARY KEY(city_id, discovery_id, revision))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS source_snapshots (
        city_id INTEGER NOT NULL, discovery_id INTEGER NOT NULL,
        captured_at TEXT NOT NULL, source_json TEXT NOT NULL,
        PRIMARY KEY(city_id, discovery_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS source_observations (
        city_id INTEGER NOT NULL, discovery_id INTEGER NOT NULL, revision INTEGER NOT NULL,
        observed_at TEXT NOT NULL, source_json TEXT NOT NULL,
        PRIMARY KEY(city_id, discovery_id, revision))''')
    return conn


def _snapshot(conn, row):
    allowed = ('id', 'active_city_id', 'business_name', 'formatted_address', 'city', 'state',
               'phone', 'contact_form_url', 'website', 'source_url', 'provider', 'query_family',
               'discovered_at', 'last_seen_at', 'validation_status', 'rejection_reason',
               'evidence_url', 'evidence_snippet', 'official_match', 'linked_lead_id')
    snapshot = {key: row[key] for key in allowed if key in row.keys()}
    if snapshot.get('linked_lead_id'):
        lead = conn.execute('SELECT * FROM leads WHERE id=?', (snapshot['linked_lead_id'],)).fetchone()
        if lead:
            for key in ('email', 'email_source_type', 'review_reason_code', 'review_reason_detail'):
                if key in lead.keys():
                    snapshot[key] = lead[key]
    return snapshot


def _source(db, city_id, discovery_id):
    if type(city_id) is not int or type(discovery_id) is not int or city_id < 1 or discovery_id < 1:
        raise ValueError('invalid identity')
    with data.readonly(db) as conn:
        row = conn.execute('SELECT * FROM lead_discovery_results WHERE id=? AND active_city_id=?',
                           (discovery_id, city_id)).fetchone()
        return _snapshot(conn, row) if row is not None else None


def capture_city(store, db, city_id):
    """Save a provisional city handoff locally without touching source or send status.

    A consistent read transaction captures only known pending/review statuses;
    existing snapshots and all manual versions are preserved without updates.
    This is not a production completion receipt or authoritative classification.
    """
    if type(city_id) is not int or not 1 <= city_id <= 9999:
        raise ValueError('invalid city')
    statuses = ('validation_pending', 'history_check_pending', 'website_lookup_pending',
                'email_extraction_pending', 'review_recovery', 'manual_review_needed',
                'no_public_email', 'website_not_found', 'contact_form_pool', 'identity_review')
    with data.readonly(db) as source:
        city = source.execute('SELECT id,city,state FROM retail_city_queue WHERE id=?', (city_id,)).fetchone()
        if city is None:
            raise ValueError('unknown city')
        placeholders = ','.join('?' for _ in statuses)
        rows = source.execute(f'''SELECT * FROM lead_discovery_results WHERE active_city_id=?
            AND validation_status IN ({placeholders}) ORDER BY id LIMIT 20001''', (city_id, *statuses)).fetchall()
        if len(rows) > 20000:
            raise ValueError('city snapshot too large; no records saved')
        snapshots = []
        for row in rows:
            item = _snapshot(source, row)
            item['search_city'] = city['city']
            item['search_state'] = city['state']
            item['capture_classification'] = '待人工核查；非正式资格分类'
            snapshots.append(item)
    captured_at = datetime.now(timezone.utc).isoformat()
    with closing(_connect(store)) as target:
        try:
            target.execute('BEGIN IMMEDIATE')
            inserted = 0
            observations = 0
            for item in snapshots:
                prior = target.execute('SELECT captured_at,source_json FROM source_snapshots WHERE city_id=? AND discovery_id=?',
                                       (city_id, item['id'])).fetchone()
                result = target.execute('INSERT OR IGNORE INTO source_snapshots VALUES (?,?,?,?)',
                    (city_id, item['id'], captured_at, json.dumps(item, ensure_ascii=False)))
                inserted += result.rowcount
                # Preserve a pre-existing initial snapshot before recording any newer observation.
                if prior and not target.execute('SELECT 1 FROM source_observations WHERE city_id=? AND discovery_id=? LIMIT 1',
                                                (city_id, item['id'])).fetchone():
                    _observe(target, city_id, item['id'], prior['captured_at'], json.loads(prior['source_json']))
                observations += _observe(target, city_id, item['id'], captured_at, item)
            target.commit()
        except BaseException:
            target.rollback()
            raise
    return {'city_id': city_id, 'source_matched': len(snapshots), 'new_snapshots': inserted,
            'existing_preserved': len(snapshots) - inserted, 'new_observations': observations, 'captured_at': captured_at,
            'production_updated': False, 'send_authorized': False,
            'scope': '仅本机暂定待核查快照，不是城市完成回执或发送资格'}


def _observe(conn, city_id, discovery_id, observed_at, item):
    encoded = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    last = conn.execute('''SELECT revision,source_json FROM source_observations
        WHERE city_id=? AND discovery_id=? ORDER BY revision DESC LIMIT 1''', (city_id, discovery_id)).fetchone()
    if last and last['source_json'] == encoded:
        return 0
    conn.execute('INSERT INTO source_observations VALUES(?,?,?,?,?)',
                 (city_id, discovery_id, (last['revision'] if last else 0) + 1, observed_at, encoded))
    return 1


def _saved(conn, city_id, discovery_id):
    row = conn.execute('SELECT captured_at,source_json FROM source_snapshots WHERE city_id=? AND discovery_id=?',
                       (city_id, discovery_id)).fetchone()
    return {'captured_at': row['captured_at'], 'source': json.loads(row['source_json'])} if row else None


def read(store, db, city_id, discovery_id):
    with closing(_connect(store)) as conn:
        saved = _saved(conn, city_id, discovery_id)
        rows = [dict(row) for row in conn.execute('''SELECT revision,created_at,website,email,contact,note,evidence,verified
          FROM annotations WHERE city_id=? AND discovery_id=? ORDER BY revision DESC''', (city_id, discovery_id))]
        observations = [{'revision': row['revision'], 'observed_at': row['observed_at'],
                         'source': json.loads(row['source_json'])} for row in conn.execute('''
            SELECT revision,observed_at,source_json FROM source_observations
            WHERE city_id=? AND discovery_id=? ORDER BY revision DESC''', (city_id, discovery_id))]
        if not saved and not rows and _source(db, city_id, discovery_id) is None:
            raise ValueError('city and source record do not match')
    return {'city_id': city_id, 'discovery_id': discovery_id, 'versions': rows, 'snapshot': saved, 'observations': observations,
            'production_updated': False, 'send_authorized': False}


def saved_for_city(store, city_id):
    if type(city_id) is not int or not 1 <= city_id <= 9999:
        raise ValueError('invalid city')
    with closing(_connect(store)) as conn:
        rows = conn.execute('''SELECT s.discovery_id,
                COALESCE(o.observed_at,s.captured_at) AS captured_at,
                COALESCE(o.source_json,s.source_json) AS source_json
            FROM source_snapshots s LEFT JOIN source_observations o
                ON o.city_id=s.city_id AND o.discovery_id=s.discovery_id
                AND o.revision=(SELECT MAX(v.revision) FROM source_observations v
                                WHERE v.city_id=s.city_id AND v.discovery_id=s.discovery_id)
            WHERE s.city_id=? ORDER BY s.discovery_id''', (city_id,)).fetchall()
        items = []
        for row in rows:
            item = json.loads(row['source_json'])
            item['id'] = row['discovery_id']
            item['captured_at'] = row['captured_at']
            items.append(item)
        old = conn.execute('''SELECT DISTINCT a.discovery_id FROM annotations a
            LEFT JOIN source_snapshots s ON s.city_id=a.city_id AND s.discovery_id=a.discovery_id
            WHERE a.city_id=? AND s.discovery_id IS NULL ORDER BY a.discovery_id''', (city_id,)).fetchall()
        items.extend({'id': row['discovery_id'], 'business_name': '旧版补充：原商家名称未保存',
                      'validation_status': 'source_snapshot_unavailable'} for row in old)
        # Keep source values intact; annotations are separate user-supplied
        # evidence and must never be mistaken for official source fields.
        annotations = conn.execute('''SELECT a.discovery_id,a.revision,a.created_at,
                a.website,a.email,a.contact,a.note,a.evidence,a.verified
            FROM annotations a WHERE a.city_id=? AND a.revision=(
                SELECT MAX(v.revision) FROM annotations v
                WHERE v.city_id=a.city_id AND v.discovery_id=a.discovery_id)''', (city_id,)).fetchall()
        latest = {row['discovery_id']: dict(row) for row in annotations}
        for item in items:
            item['local_annotation'] = latest.get(item['id'])
    return {'items': items, 'total': len(items), 'source': '本机保存时的原始资料快照，不代表实时状态'}


def save(store, db, value):
    fields = {'city_id', 'discovery_id', 'revision', 'website', 'email', 'contact', 'note', 'evidence', 'verified'}
    if set(value) != fields or type(value['revision']) is not int or type(value['verified']) is not bool:
        raise ValueError('invalid annotation')
    limits = {'website': 2000, 'email': 254, 'contact': 1000, 'note': 4000, 'evidence': 2000}
    if any(not isinstance(value[k], str) or len(value[k]) > limit for k, limit in limits.items()):
        raise ValueError('invalid annotation field')
    if value['website'].strip():
        url = urlsplit(value['website'].strip())
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            raise ValueError('invalid website')
    if any(ch in value['email'] for ch in '\r\n'):
        raise ValueError('invalid email')
    with closing(_connect(store)) as conn:
        saved = _saved(conn, value['city_id'], value['discovery_id'])
        existing = conn.execute('SELECT 1 FROM annotations WHERE city_id=? AND discovery_id=? LIMIT 1',
                                (value['city_id'], value['discovery_id'])).fetchone() is not None
        try:
            source = None if saved else _source(db, value['city_id'], value['discovery_id'])
        except (sqlite3.Error, OSError):
            if not existing:
                raise
            source = None
        if not saved and not existing and source is None:
            raise ValueError('city and source record do not match')
        try:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT COALESCE(MAX(revision),0) FROM annotations WHERE city_id=? AND discovery_id=?',
                                   (value['city_id'], value['discovery_id'])).fetchone()[0]
            if current != value['revision']:
                raise VersionConflict('此线索在其他页面已有新版本，请重新读取后比较。')
            if source is not None:
                conn.execute('INSERT OR IGNORE INTO source_snapshots VALUES (?,?,?,?)',
                    (value['city_id'], value['discovery_id'], datetime.now(timezone.utc).isoformat(),
                     json.dumps(source, ensure_ascii=False)))
                _observe(conn, value['city_id'], value['discovery_id'], datetime.now(timezone.utc).isoformat(), source)
            revision = current + 1
            conn.execute('INSERT INTO annotations VALUES (?,?,?,?,?,?,?,?,?,?)',
                (value['city_id'], value['discovery_id'], revision, datetime.now(timezone.utc).isoformat(),
                 value['website'].strip(), value['email'].strip(), value['contact'].strip(), value['note'].strip(),
                 value['evidence'].strip(), int(value['verified'])))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'revision': revision, 'production_updated': False, 'send_authorized': False}
