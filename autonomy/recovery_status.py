"""Bounded, path-free recovery journal status; never execution authority."""
from contextlib import closing
import hashlib
import json
import re
import sqlite3
import time

from autonomy.cancellation_recovery import SCHEMA, HANDOFF_SCHEMA, PROTOCOL
from autonomy.growth_snapshot import MAX_SNAPSHOT_BYTES, MAX_VM_STEPS, MAX_SECONDS


def inspect_recovery_status(snapshot, expected_sha256, cancel_identity):
    """Inspect caller-approved standalone bytes, not a live database.

    Hash equality establishes byte identity only, never source authorization.
    COMPLETED describes this journal alone, not a closed lock or live operation.
    """
    result = dict(schema='rokt.offline-recovery-status.v1', accepted=False,
                  reason='SNAPSHOT_REJECTED', journal_phase='UNKNOWN',
                  execution_terminal='UNKNOWN', lock_closed='UNKNOWN',
                  source_authorized='UNKNOWN', allow_dispatch=False,
                  allow_cancel_dispatch=False, allow_reconcile=False,
                  replay_allowed=False, production_accepted=False)
    def hex64(value):
        return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None
    if not hex64(cancel_identity) or not hex64(expected_sha256):
        return dict(result, reason='INVALID_EXPECTED_CONTEXT')
    if type(snapshot) is not bytes or not 100 <= len(snapshot) <= MAX_SNAPSHOT_BYTES:
        return dict(result, reason='INVALID_SNAPSHOT_SIZE_OR_TYPE')
    if hashlib.sha256(snapshot).hexdigest() != expected_sha256:
        return dict(result, reason='HASH_MISMATCH')
    if snapshot[:16] != b'SQLite format 3\x00' or snapshot[18:20] != b'\x01\x01':
        return dict(result, reason='STANDALONE_IMAGE_REQUIRED')
    size = int.from_bytes(snapshot[16:18], 'big')
    size = 65536 if size == 1 else size
    if (size < 512 or size > 65536 or size & (size - 1) or
        int.from_bytes(snapshot[28:32], 'big') * size != len(snapshot) or
        snapshot[24:28] != snapshot[92:96]):
        return dict(result, reason='INCOMPLETE_IMAGE')
    if not hasattr(sqlite3.Connection, 'deserialize'):
        return dict(result, reason='UNSUPPORTED_SQLITE_RUNTIME')
    started = time.monotonic()
    steps = 0
    def bounded():
        nonlocal steps
        steps += 1000
        return int(steps > MAX_VM_STEPS or time.monotonic() - started > MAX_SECONDS)
    try:
        with closing(sqlite3.connect(':memory:')) as db:
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_SNAPSHOT_BYTES)
            db.deserialize(snapshot)
            db.execute('PRAGMA query_only=ON')
            db.execute('PRAGMA trusted_schema=OFF')
            db.set_progress_handler(bounded, 1000)
            objects = db.execute("SELECT type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' ORDER BY name").fetchall()
            if (db.execute('PRAGMA user_version').fetchone()[0] != 1 or
                objects != [('table', HANDOFF_SCHEMA), ('table', SCHEMA)]):
                return dict(result, reason='INCOMPATIBLE_SCHEMA')
            if db.execute('PRAGMA integrity_check(1)').fetchall() != [('ok',)]:
                return dict(result, reason='INTEGRITY_CHECK_FAILED')
            row = db.execute('SELECT binding,state FROM recoveries WHERE identity=?', (cancel_identity,)).fetchone()
            if time.monotonic() - started > MAX_SECONDS:
                return dict(result, reason='INSPECTION_BUDGET_EXCEEDED')
            if row is None:
                return dict(result, accepted=True, reason='NOT_RECORDED', journal_phase='NOT_RECORDED')
            if type(row[0]) is not str or len(row[0]) > 1024:
                return dict(result, reason='INVALID_PERSISTED_RECORD')
            binding = json.loads(row[0])
            if (type(binding) is not dict or set(binding) != {'binding_hash', 'receipts_hash', 'recovery_id', 'protocol'} or
                binding['protocol'] != PROTOCOL or
                not all(hex64(binding[k]) for k in ('binding_hash', 'receipts_hash', 'recovery_id')) or
                row[1] not in ('PREPARED', 'COMPLETED')):
                return dict(result, reason='INVALID_PERSISTED_RECORD')
            if time.monotonic() - started > MAX_SECONDS:
                return dict(result, reason='INSPECTION_BUDGET_EXCEEDED')
            return dict(result, accepted=True, reason='RECOVERY_JOURNAL_ONLY', journal_phase=row[1])
    except (sqlite3.Error, ValueError, TypeError, OverflowError, MemoryError, RecursionError):
        return dict(result, reason='INVALID_OR_UNREADABLE_IMAGE')
