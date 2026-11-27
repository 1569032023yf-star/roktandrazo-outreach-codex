"""Local template drafts and immutable versions. No production or send authority."""
import base64
import binascii
from contextlib import closing
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone

TEMPLATE_ID = 'rokt-local-main'
MAX_IMAGE = 2_000_000
CID_PATTERN = re.compile(r'cid:([0-9a-f]{64})@rokt-local', re.I)


class VersionConflict(Exception):
    pass


def _connect(store):
    store.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(store / 'template_workspace.sqlite3'), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
      CREATE TABLE IF NOT EXISTS template_versions (
        template_id TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL,
        subject TEXT NOT NULL, html TEXT NOT NULL, text_body TEXT NOT NULL,
        asset_ids TEXT NOT NULL, PRIMARY KEY(template_id, version));
      CREATE TABLE IF NOT EXISTS template_assets (
        asset_id TEXT PRIMARY KEY, mime TEXT NOT NULL, bytes BLOB NOT NULL, created_at TEXT NOT NULL);
    ''')
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def _version(row):
    return {'template_id': row['template_id'], 'version': row['version'],
            'created_at': row['created_at'], 'subject': row['subject'], 'html': row['html'],
            'text': row['text_body'], 'asset_ids': json.loads(row['asset_ids'])}


def read(store):
    with closing(_connect(store)) as conn:
        rows = conn.execute('SELECT * FROM template_versions WHERE template_id=? ORDER BY version DESC',
                            (TEMPLATE_ID,)).fetchall()
    return {'template_id': TEMPLATE_ID, 'versions': [_version(r) for r in rows],
            'production_published': False}


def save(store, value):
    if set(value) != {'revision', 'subject', 'html', 'text'} or type(value['revision']) is not int:
        raise ValueError('invalid template')
    if any(not isinstance(value[k], str) for k in ('subject', 'html', 'text')):
        raise ValueError('invalid fields')
    if len(value['subject']) > 998 or any(c in value['subject'] for c in '\r\n'):
        raise ValueError('invalid subject')
    if len(value['html'].encode('utf-8')) > 150000 or len(value['text'].encode('utf-8')) > 150000:
        raise ValueError('template too large')
    assets = sorted(set(x.lower() for x in CID_PATTERN.findall(value['html'])))
    conn = _connect(store)
    try:
        conn.execute('BEGIN IMMEDIATE')
        current = conn.execute('SELECT COALESCE(MAX(version),0) FROM template_versions WHERE template_id=?',
                               (TEMPLATE_ID,)).fetchone()[0]
        if current != value['revision']:
            raise VersionConflict('模板已在其他页面修改，请刷新并比较后再保存。')
        for asset in assets:
            if not conn.execute('SELECT 1 FROM template_assets WHERE asset_id=?', (asset,)).fetchone():
                raise ValueError('missing image')
        new_version = current + 1
        conn.execute('INSERT INTO template_versions VALUES(?,?,?,?,?,?,?)',
                     (TEMPLATE_ID, new_version, _now(), value['subject'], value['html'],
                      value['text'], json.dumps(assets)))
        conn.commit()
        row = conn.execute('SELECT * FROM template_versions WHERE template_id=? AND version=?',
                           (TEMPLATE_ID, new_version)).fetchone()
        return {'version': _version(row), 'production_published': False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_asset(store, value):
    if set(value) != {'data'} or not isinstance(value['data'], str):
        raise ValueError('invalid image')
    try:
        raw = base64.b64decode(value['data'], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('invalid image') from None
    if not raw or len(raw) > MAX_IMAGE:
        raise ValueError('image size')
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif raw.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif raw.startswith((b'GIF87a', b'GIF89a')):
        mime = 'image/gif'
    elif raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        mime = 'image/webp'
    else:
        raise ValueError('unsupported image')
    asset_id = hashlib.sha256(raw).hexdigest()
    with closing(_connect(store)) as conn, conn:
        conn.execute('INSERT OR IGNORE INTO template_assets VALUES(?,?,?,?)', (asset_id, mime, raw, _now()))
    return {'asset_id': asset_id, 'cid': f'cid:{asset_id}@rokt-local', 'mime': mime,
            'size': len(raw), 'production_published': False}


def asset(store, asset_id):
    if not re.fullmatch(r'[0-9a-f]{64}', asset_id):
        raise ValueError('invalid asset id')
    with closing(_connect(store)) as conn:
        row = conn.execute('SELECT mime, bytes FROM template_assets WHERE asset_id=?', (asset_id,)).fetchone()
    if not row:
        raise ValueError('asset not found')
    return {'asset_id': asset_id, 'mime': row['mime'], 'data': base64.b64encode(row['bytes']).decode('ascii')}
