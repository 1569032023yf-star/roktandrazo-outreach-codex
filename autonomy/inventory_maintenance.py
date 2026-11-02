"""Original Inventory DB exclusion primitives; no scheduler or installation entry.

Callers must already possess authorized DB access. Deployment of all original
lock consumers and installer integration is still required; no expiry/replay.
"""
import json
import re

KEY = 'u1:inventory:maintenance:v1'
PREFIX = 'run_lock:daily_outreach:'


def binding_bytes(binding):
    fields={'operation_id':64,'source_commit':40,'manifest_sha256':64,'lease_nonce':64}
    if type(binding) is not dict or set(binding)!=set(fields)|{'inventory_id'}:
        raise ValueError('EXACT_MAINTENANCE_BINDING_REQUIRED')
    if binding['inventory_id']!='1784775229336' or any(
            type(binding[k]) is not str or not re.fullmatch('[0-9a-f]{'+str(n)+'}',binding[k])
            for k,n in fields.items()):
        raise ValueError('EXACT_MAINTENANCE_BINDING_REQUIRED')
    return json.dumps(binding,sort_keys=True,separators=(',',':'))


def blocked(conn):
    """Use inside the original run-lock BEGIN IMMEDIATE transaction."""
    row=conn.execute('SELECT value FROM system_config WHERE key=?',(KEY,)).fetchone()
    return row is not None and row[0]!='released'


def acquire(conn,binding):
    raw=binding_bytes(binding);op=KEY+':'+binding['operation_id']
    try:
        conn.execute('BEGIN IMMEDIATE')
        if blocked(conn) or conn.execute('SELECT 1 FROM system_config WHERE key=?',(op,)).fetchone():
            raise ValueError('STOP_AND_PRESERVE_MAINTENANCE_PENDING_OR_REPLAY')
        # No stale override: even an old holder may have an unknown side effect.
        rows=conn.execute('SELECT key,value FROM system_config WHERE substr(key,1,?)=?',
                          (len(PREFIX),PREFIX)).fetchall()
        if any(not k.endswith('_acquired_at') and v not in ('','released') for k,v in rows):
            raise ValueError('ORIGINAL_INVENTORY_NOT_QUIESCENT')
        sql="INSERT INTO system_config(key,value,updated_at) VALUES(?,?,datetime('now')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at"
        conn.execute(sql,(op,raw));conn.execute(sql,(KEY,raw));conn.commit()
    except BaseException:
        conn.rollback();raise


def assert_held(conn,binding):
    raw=binding_bytes(binding)
    row=conn.execute('SELECT value FROM system_config WHERE key=?',(KEY,)).fetchone()
    if row is None or row[0]!=raw:raise ValueError('STOP_AND_PRESERVE_MAINTENANCE_LOST')


def release_verified(conn,binding,*,final_verified=False):
    if final_verified is not True:raise ValueError('STOP_AND_PRESERVE_FINAL_VERIFICATION_REQUIRED')
    try:
        conn.execute('BEGIN IMMEDIATE');assert_held(conn,binding)
        conn.execute("UPDATE system_config SET value='released',updated_at=datetime('now') WHERE key=?",(KEY,))
        conn.commit()  # Keep the operation tombstone: a lost receipt never replays.
    except BaseException:
        conn.rollback();raise
