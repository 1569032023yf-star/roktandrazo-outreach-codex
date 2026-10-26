"""Durable protocol for the existing Inventory; never dispatches or schedules.

Integrators must hold lock_recovery.exclusive_lock across admission and external
work, authenticate evidence via verify, and preserve this database on rollback.
SQLite exclusion is not a replacement for the production run lock. No lease
expiry authorizes replay. Default evidence verification denies everything.
"""
from contextlib import contextmanager, closing
import hashlib
import json
import sqlite3
import uuid

INVENTORY = '1784775229336'
STATES = frozenset(('pending', 'claimed', 'running', 'completed', 'failed', 'unknown', 'deferred'))


class LedgerError(RuntimeError):
    pass


def _integer(value):
    if type(value) is not int or value < 0:
        raise LedgerError('INVALID_INTEGER')
    return value


def _key(value):
    if type(value) is not str or not value or len(value) > 128 or not all(c.isalnum() or c in '-_:' for c in value):
        raise LedgerError('INVALID_IDENTIFIER')
    return value


class DurableSlots:
    def __init__(self, path, *, verify=None, connect=sqlite3.connect, fault=None):
        self.path = str(path)
        self.verify = verify or (lambda evidence: None)
        self.connect = connect
        self.fault = fault or (lambda stage: None)

    @contextmanager
    def _tx(self):
        c = None
        try:
            c = self.connect(self.path, timeout=5, isolation_level=None)
            c.row_factory = sqlite3.Row
            c.execute('PRAGMA synchronous=FULL')
            c.execute('BEGIN IMMEDIATE')
            yield c
            self.fault('before_commit')
            c.commit()
            self.fault('after_commit')
        except (sqlite3.Error, OSError):
            if c is not None:
                c.rollback()
            raise LedgerError('STORAGE_OUTCOME_UNVERIFIED') from None
        except BaseException:
            if c is not None:
                c.rollback()
            raise
        finally:
            if c is not None:
                c.close()

    def initialize(self):
        with self._tx() as c:
            c.execute('CREATE TABLE IF NOT EXISTS authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1), epoch INTEGER NOT NULL, owner TEXT NOT NULL)')
            c.execute("CREATE TABLE IF NOT EXISTS slots (slot TEXT PRIMARY KEY, inventory TEXT NOT NULL CHECK(inventory='1784775229336'), due INTEGER NOT NULL UNIQUE, state TEXT NOT NULL CHECK(state IN ('pending','claimed','running','completed','failed','unknown','deferred')), epoch INTEGER, owner TEXT, token TEXT, receipt TEXT)")
            c.execute('CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY, slot TEXT, event TEXT NOT NULL, epoch INTEGER)')
            c.execute('INSERT OR IGNORE INTO authority VALUES (1,0,?)', ('disabled',))

    def _evidence(self, evidence, *, kind, now, **bindings):
        _integer(now)
        try:
            evidence = self.verify(dict(evidence)) if isinstance(evidence, dict) else None
        except Exception:
            evidence = None
        if not isinstance(evidence, dict) or evidence.get('kind') != kind or evidence.get('inventory') != INVENTORY:
            raise LedgerError('EVIDENCE_REJECTED')
        observed = evidence.get('observed')
        expires = evidence.get('expires')
        if type(observed) is not int or type(expires) is not int or not 0 <= observed <= now <= expires:
            raise LedgerError('EVIDENCE_EXPIRED')
        if any(type(evidence.get(k)) is not type(v) or evidence.get(k) != v for k, v in bindings.items()):
            raise LedgerError('EVIDENCE_CONFLICT')
        return evidence

    def _authority(self, c, epoch, owner):
        _integer(epoch)
        _key(owner)
        row = c.execute('SELECT epoch,owner FROM authority').fetchone()
        if row is None or (row['epoch'], row['owner']) != (epoch, owner):
            raise LedgerError('AUTHORITY_FENCED')

    def switch_authority(self, expected_epoch, owner, evidence, *, now):
        _integer(expected_epoch)
        _key(owner)
        self._evidence(evidence, kind='authority', now=now, previous_epoch=expected_epoch, owner=owner, drained=True, old_disabled=True)
        with self._tx() as c:
            if c.execute('SELECT epoch FROM authority').fetchone()[0] != expected_epoch:
                raise LedgerError('AUTHORITY_FENCED')
            if c.execute("SELECT 1 FROM slots WHERE state IN ('claimed','running','unknown')").fetchone():
                raise LedgerError('RECONCILIATION_REQUIRED')
            c.execute('UPDATE authority SET epoch=?,owner=?', (expected_epoch+1, owner))
            c.execute("INSERT INTO audit(event,epoch) VALUES ('AUTHORITY_CHANGED',?)", (expected_epoch+1,))
        return expected_epoch+1

    def admit_due(self, slot, next_due, evidence, *, now, epoch, owner, missed=()):
        """Accept one trusted latest due, never compute cron or catch-up firings."""
        _key(slot)
        _integer(next_due)
        evidence = self._evidence(evidence, kind='schedule', now=now, slot=slot, next_due=next_due, epoch=epoch, owner=owner, latest_due=True)
        if type(missed) is not tuple or len(missed) > 100:
            raise LedgerError('INVALID_MISSED_SLOTS')
        for old_slot, old_due in missed:
            _key(old_slot)
            _integer(old_due)
            if old_due >= next_due or old_slot == slot:
                raise LedgerError('INVALID_MISSED_SLOTS')
        if missed and evidence.get('missed') != [list(x) for x in missed]:
            raise LedgerError('EVIDENCE_CONFLICT')
        if next_due > now:
            raise LedgerError('NOT_DUE')
        with self._tx() as c:
            self._authority(c, epoch, owner)
            row = c.execute('SELECT * FROM slots WHERE slot=?', (slot,)).fetchone()
            if row:
                if row['due'] != next_due:
                    raise LedgerError('SLOT_CONFLICT')
                return row['state']
            if c.execute('SELECT 1 FROM slots WHERE due>=?', (next_due,)).fetchone():
                raise LedgerError('STALE_SCHEDULE')
            for old_slot, old_due in missed:
                old = c.execute('SELECT due,state FROM slots WHERE slot=?',(old_slot,)).fetchone()
                if old and (old['due'] != old_due or old['state'] not in ('pending','deferred')):
                    raise LedgerError('SLOT_CONFLICT')
                if c.execute('SELECT 1 FROM slots WHERE due=? AND slot<>?',(old_due,old_slot)).fetchone():
                    raise LedgerError('SLOT_CONFLICT')
                c.execute('INSERT OR IGNORE INTO slots(slot,inventory,due,state) VALUES (?,?,?,?)',(old_slot,INVENTORY,old_due,'deferred'))
            c.execute("UPDATE slots SET state='deferred' WHERE state='pending'")
            c.execute('INSERT INTO slots(slot,inventory,due,state) VALUES (?,?,?,?)', (slot,INVENTORY,next_due,'pending'))
            c.execute("INSERT INTO audit(slot,event,epoch) VALUES (?,'ADMITTED',?)", (slot,epoch))
        return 'pending'

    def claim(self, slot, evidence, *, now, epoch, owner):
        _key(slot)
        self._evidence(evidence, kind='idle', now=now, slot=slot, epoch=epoch, owner=owner, external_state='idle', existing_lock_held=True)
        with self._tx() as c:
            self._authority(c, epoch, owner)
            row = c.execute('SELECT state FROM slots WHERE slot=?', (slot,)).fetchone()
            if row is None or row['state'] != 'pending':
                raise LedgerError('NO_REPLAY')
            if c.execute("SELECT 1 FROM slots WHERE state IN ('claimed','running','unknown')").fetchone():
                raise LedgerError('RECONCILIATION_REQUIRED')
            token = uuid.uuid4().hex
            c.execute("UPDATE slots SET state='claimed',epoch=?,owner=?,token=? WHERE slot=?", (epoch,owner,token,slot))
            c.execute("INSERT INTO audit(slot,event,epoch) VALUES (?,'CLAIMED',?)", (slot,epoch))
        return token

    def start(self, slot, token, *, epoch, owner):
        """One committed start only. Lost acknowledgement requires reconciliation."""
        with self._tx() as c:
            self._authority(c, epoch, owner)
            changed = c.execute("UPDATE slots SET state='running' WHERE slot=? AND token=? AND epoch=? AND owner=? AND state='claimed'", (slot,token,epoch,owner)).rowcount
            if changed != 1:
                raise LedgerError('NO_REPLAY')
            c.execute("INSERT INTO audit(slot,event,epoch) VALUES (?,'RUNNING',?)", (slot,epoch))
        return 'RUNNING_NOT_DISPATCHED'

    def mark_unknown(self, slot, token, *, epoch, owner):
        with self._tx() as c:
            self._authority(c, epoch, owner)
            changed = c.execute("UPDATE slots SET state='unknown' WHERE slot=? AND token=? AND epoch=? AND owner=? AND state IN ('claimed','running','unknown')", (slot,token,epoch,owner)).rowcount
            if changed != 1:
                raise LedgerError('INVALID_TRANSITION')
            c.execute("INSERT INTO audit(slot,event,epoch) VALUES (?,'UNKNOWN',?)", (slot,epoch))

    def reconcile(self, slot, state, evidence, *, now, epoch, owner):
        if state not in ('completed','failed'):
            raise LedgerError('INVALID_TRANSITION')
        evidence = self._evidence(evidence, kind='receipt', now=now, slot=slot, state=state, epoch=epoch, owner=owner, external_drained=True)
        receipt = evidence.get('receipt')
        _key(receipt)
        digest = hashlib.sha256(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self._tx() as c:
            self._authority(c,epoch,owner)
            row = c.execute('SELECT * FROM slots WHERE slot=?',(slot,)).fetchone()
            if row is None or evidence.get('token') != row['token'] or not row['token']:
                raise LedgerError('RECEIPT_CONFLICT')
            if row['state'] in ('completed','failed'):
                if row['state'] == state and row['receipt'] == digest:
                    return 'DUPLICATE_RECEIPT'
                raise LedgerError('RECEIPT_CONFLICT')
            if row['state'] not in ('claimed','running','unknown'):
                raise LedgerError('INVALID_TRANSITION')
            c.execute('UPDATE slots SET state=?,receipt=? WHERE slot=?',(state,digest,slot))
            c.execute('INSERT INTO audit(slot,event,epoch) VALUES (?,?,?)',(slot,state.upper(),epoch))
        return state

    def snapshot(self):
        # Read-only URI: a missing ledger must not silently be recreated.
        from pathlib import Path
        try:
            with closing(sqlite3.connect(Path(self.path).resolve().as_uri()+'?mode=ro',uri=True)) as c:
                return c.execute('SELECT slot,due,state,epoch FROM slots ORDER BY due').fetchall()
        except sqlite3.Error:
            raise LedgerError('STORAGE_OUTCOME_UNVERIFIED') from None
