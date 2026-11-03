"""Bind event consumption to the existing Inventory DB lock, never a scheduler.

Only the original lock acquisition transaction creates an incarnation. Observers
cannot acquire, renew or take over an owner. Unknown work keeps the original
lock held. This supplies identity, not permission to dispatch production work.
"""
from contextlib import closing
import json
import os
import secrets
from pathlib import Path

from autonomy import inventory_maintenance as maintenance, lock_recovery
from autonomy.growth_ledger import digest
from autonomy.release_store import ordinary

SESSION_PREFIX = 'u1:inventory:owner-session:v1:'
FIELDS = {'lock_key', 'holder', 'pid', 'process_identity', 'nonce', 'tree_state', 'database_identity', 'event_digest', 'claim'}
CLAIM_FIELDS = {'slot', 'epoch', 'owner', 'run_id', 'request_id', 'claim_token_hash'}


def database_identity(conn):
    rows = conn.execute('PRAGMA database_list').fetchall()
    names = [row[2] for row in rows if row[1] == 'main']
    if len(names) != 1 or not names[0]:
        raise ValueError('EXISTING_ORIGINAL_DATABASE_REQUIRED')
    path = ordinary(Path(names[0]))
    stat = path.stat()
    if not path.is_file() or stat.st_nlink != 1:
        raise ValueError('ORIGINAL_DATABASE_IDENTITY_REJECTED')
    return dict(path=os.path.normcase(str(path.resolve(strict=True))), device=stat.st_dev, inode=stat.st_ino)


def session_key(lock_key):
    return SESSION_PREFIX + digest(lock_key)


def register_locked(conn, lock_key, holder):
    """Called only inside bd_db's original BEGIN IMMEDIATE acquisition."""
    if (not conn.in_transaction or not lock_key.startswith(maintenance.INVENTORY_PREFIX)
            or type(holder) is not str or not holder or holder == 'released'):
        raise ValueError('ORIGINAL_OWNER_TRANSACTION_REQUIRED')
    identity = lock_recovery.process_identity(os.getpid())
    if not identity:
        raise ValueError('ORIGINAL_OWNER_PROCESS_UNAVAILABLE')
    session = dict(lock_key=lock_key, holder=holder, pid=os.getpid(),
                   process_identity=identity, nonce=secrets.token_hex(32), tree_state='idle',
                   database_identity=database_identity(conn), event_digest=None, claim=None)
    conn.execute("INSERT INTO system_config(key,value,updated_at) VALUES(?,?,datetime('now')) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                 (session_key(lock_key), json.dumps(session, sort_keys=True, separators=(',', ':'))))
    return _binding(session)


def _session(conn, *, own_process=False):
    if maintenance.blocked(conn):
        raise ValueError('ORIGINAL_OWNER_MAINTENANCE_PENDING')
    rows = conn.execute("SELECT key,value FROM system_config WHERE substr(key,1,?)=? "
                        "AND substr(key,-12)<>'_acquired_at' AND (value IS NULL OR value<>'released')",
                        (len(maintenance.INVENTORY_PREFIX), maintenance.INVENTORY_PREFIX)).fetchall()
    if len(rows) != 1:
        raise ValueError('EXACT_ORIGINAL_OWNER_REQUIRED')
    lock_key, holder = rows[0]
    row = conn.execute('SELECT value FROM system_config WHERE key=?', (session_key(lock_key),)).fetchone()
    try:
        def unique(pairs):
            result = {}
            for k, v in pairs:
                if k in result:
                    raise ValueError('DUPLICATE_OWNER_FIELD')
                result[k] = v
            return result
        session = json.loads(row[0], object_pairs_hook=unique) if row else None
        if (type(session) is not dict or set(session) != FIELDS or
                session['lock_key'] != lock_key or session['holder'] != holder or
                type(holder) is not str or not holder or
                type(session['pid']) is not int or session['pid'] <= 0 or
                type(session['process_identity']) is not str or not session['process_identity'] or
                type(session['nonce']) is not str or len(session['nonce']) != 64 or
                any(x not in '0123456789abcdef' for x in session['nonce']) or
                session['tree_state'] not in ('idle', 'unverified', 'verified_closed') or
                session['database_identity'] != database_identity(conn) or
                (session['event_digest'] is not None and
                 (type(session['event_digest']) is not str or len(session['event_digest']) != 64 or
                  any(x not in '0123456789abcdef' for x in session['event_digest']))) or
                (session['claim'] is not None and
                 (type(session['claim']) is not dict or set(session['claim']) != CLAIM_FIELDS)) or
                (own_process and session['pid'] != os.getpid()) or
                lock_recovery.process_identity(session['pid']) != session['process_identity']):
            raise ValueError('ORIGINAL_OWNER_IDENTITY_REJECTED')
        return session
    except (TypeError, KeyError, json.JSONDecodeError):
        raise ValueError('ORIGINAL_OWNER_IDENTITY_REJECTED') from None


def _binding(session):
    return dict(lock_token_hash=digest({k: session[k] for k in
                     ('lock_key', 'holder', 'pid', 'process_identity', 'nonce', 'database_identity')}),
                process_identity_hash=digest(session['process_identity']))


def observer(connect):
    """Read existing authority through a provisioned connection; no DB creation.

    The host must supply its trusted read-only original-DB connection factory.
    No path, holder or PID is accepted from an HTTP event.
    """
    with closing(connect()) as conn:
        expected_database = database_identity(conn)
    def observe():
        with closing(connect()) as conn:
            conn.execute('BEGIN')
            try:
                if database_identity(conn) != expected_database:
                    raise ValueError('ORIGINAL_DATABASE_CHANGED')
                return _binding(_session(conn))
            finally:
                conn.rollback()
    return observe


class OriginalOwnerAuthority:
    """Same-process consumer of a captured original lock incarnation."""
    def __init__(self, connect):
        self.connect = connect
        with closing(connect()) as conn:
            conn.execute('BEGIN')
            try:
                self.binding = _binding(_session(conn, own_process=True))
                self.database_path = database_identity(conn)['path']
            finally:
                conn.rollback()

    def _check(self, conn):
        session = _session(conn, own_process=True)
        if _binding(session) != self.binding:
            raise ValueError('ORIGINAL_OWNER_INCARNATION_CHANGED')
        return session

    def check(self):
        with closing(self.connect()) as conn:
            conn.execute('BEGIN')
            try:
                self._check(conn)
                return dict(self.binding)
            finally:
                conn.rollback()

    def mark_tree(self, state):
        if state not in ('unverified', 'verified_closed'):
            raise ValueError('ORIGINAL_OWNER_TREE_STATE_REJECTED')
        with closing(self.connect()) as conn:
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('BEGIN IMMEDIATE')
            try:
                session = self._check(conn)
                session['tree_state'] = state
                conn.execute("UPDATE system_config SET value=?,updated_at=datetime('now') WHERE key=?",
                             (json.dumps(session, sort_keys=True, separators=(',', ':')),
                              session_key(session['lock_key'])))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def prepare_event(self, event_digest):
        """Intent precedes HTTP and all claims; a lost response never replays."""
        if (type(event_digest) is not str or len(event_digest) != 64 or
                any(x not in '0123456789abcdef' for x in event_digest)):
            raise ValueError('EXACT_EVENT_DIGEST_REQUIRED')
        with closing(self.connect()) as conn:
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('BEGIN IMMEDIATE')
            try:
                session = self._check(conn)
                if session['event_digest'] is not None or session['tree_state'] != 'idle':
                    raise ValueError('STOP_AND_PRESERVE_OWNER_EVENT_REPLAY')
                session.update(event_digest=event_digest, tree_state='unverified')
                conn.execute("UPDATE system_config SET value=?,updated_at=datetime('now') WHERE key=?",
                    (json.dumps(session, sort_keys=True, separators=(',', ':')),
                     session_key(session['lock_key'])))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def event_binding(self):
        with closing(self.connect()) as conn:
            conn.execute('BEGIN')
            try:
                session = self._check(conn)
                if session['event_digest'] is None:
                    raise ValueError('ORIGINAL_OWNER_EVENT_INTENT_REQUIRED')
                return dict(original_event_digest=session['event_digest'])
            finally:
                conn.rollback()

    def bind_claim(self, claim):
        if (type(claim) is not dict or set(claim) != CLAIM_FIELDS or
                type(claim['epoch']) is not int or claim['epoch'] < 1 or
                any(type(claim[k]) is not str or not claim[k] for k in CLAIM_FIELDS-{'epoch'})):
            raise ValueError('EXACT_ORIGINAL_CLAIM_REQUIRED')
        with closing(self.connect()) as conn:
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('BEGIN IMMEDIATE')
            try:
                session = self._check(conn)
                if (session['event_digest'] is None or session['tree_state'] != 'unverified' or
                        session['claim'] is not None):
                    raise ValueError('STOP_AND_PRESERVE_ORIGINAL_CLAIM_REPLAY')
                session['claim'] = claim
                conn.execute("UPDATE system_config SET value=?,updated_at=datetime('now') WHERE key=?",
                    (json.dumps(session, sort_keys=True, separators=(',', ':')),
                     session_key(session['lock_key'])))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def receipt_binding(self, claim=None):
        with closing(self.connect()) as conn:
            conn.execute('BEGIN')
            try:
                session = self._check(conn)
                if (session['event_digest'] is None or session['claim'] is None or
                        (claim is not None and session['claim'] != claim)):
                    raise ValueError('ORIGINAL_OWNER_CLAIM_JOIN_REQUIRED')
                return dict(self.binding, original_event_digest=session['event_digest'],
                            original_claim_digest=digest(session['claim']))
            finally:
                conn.rollback()


def release_allowed_locked(conn, lock_key, holder, expected_owner):
    """Bound owners must prove their incarnation and a settled execution tree.
    Do not turn a dead process or corrupted session into a release permission.
    """
    row = conn.execute('SELECT value FROM system_config WHERE key=?', (session_key(lock_key),)).fetchone()
    if row is None:
        return False
    try:
        session = _session(conn, own_process=True)
        return (session['lock_key'] == lock_key and session['holder'] == holder and
                type(expected_owner) is dict and expected_owner == _binding(session) and
                session['tree_state'] in ('idle', 'verified_closed'))
    except (ValueError, OSError):
        return False
