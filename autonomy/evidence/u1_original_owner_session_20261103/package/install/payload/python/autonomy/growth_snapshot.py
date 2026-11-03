"""Bounded inspection of approved standalone snapshot bytes, never a file path.

Matching a caller-supplied digest proves byte identity, not source authorization.
No migration, refund, replay, restore, production IO or approval is performed.
"""
from contextlib import closing
import hashlib
import re
import sqlite3
import time

from autonomy.growth_ledger import SCHEMA, SCHEMA_VERSION

MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_VM_STEPS = 2_000_000
MAX_SECONDS = 2.0
STATES = frozenset(('reserved', 'unknown', 'overrun', 'settled'))


def inspect_snapshot(snapshot, expected_sha256):
    """Inspect one standalone rollback-journal SQLite image in memory.

The approved export process must checkpoint and produce a consistent standalone
image. WAL-mode file bytes are refused, even if their digest is correct.
"""
    result = dict(schema_compatible=False, reason='SNAPSHOT_REJECTED',
                  unresolved_counts=None, reconciliation_required='UNKNOWN',
                  migration_authorized=False, production_ready=False)
    if type(snapshot) is not bytes or not 100 <= len(snapshot) <= MAX_SNAPSHOT_BYTES:
        return dict(result, reason='INVALID_SNAPSHOT_SIZE_OR_TYPE')
    if type(expected_sha256) is not str or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
        return dict(result, reason='INVALID_EXPECTED_HASH')
    if hashlib.sha256(snapshot).hexdigest() != expected_sha256:
        return dict(result, reason='HASH_MISMATCH')
    if snapshot[:16] != b'SQLite format 3\x00':
        return dict(result, reason='INVALID_SQLITE_IMAGE')
    if snapshot[18:20] != b'\x01\x01':
        return dict(result, reason='STANDALONE_IMAGE_REQUIRED')
    page_size = int.from_bytes(snapshot[16:18], 'big')
    page_size = 65536 if page_size == 1 else page_size
    page_count = int.from_bytes(snapshot[28:32], 'big')
    if (page_size < 512 or page_size > 65536 or page_size & (page_size - 1)
            or page_count * page_size != len(snapshot)
            or snapshot[24:28] != snapshot[92:96]):
        return dict(result, reason='INCOMPLETE_OR_NONCANONICAL_IMAGE')
    if not hasattr(sqlite3.Connection, 'deserialize'):
        return dict(result, reason='UNSUPPORTED_SQLITE_RUNTIME')
    started = time.monotonic()
    steps = 0
    exhausted = False

    def bounded():
        nonlocal steps, exhausted
        steps += 1000
        exhausted = steps > MAX_VM_STEPS or time.monotonic() - started > MAX_SECONDS
        return int(exhausted)

    try:
        with closing(sqlite3.connect(':memory:')) as conn:
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_SNAPSHOT_BYTES)
            conn.deserialize(snapshot)
            conn.execute('PRAGMA query_only=ON')
            conn.execute('PRAGMA trusted_schema=OFF')
            conn.set_progress_handler(bounded, 1000)
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            objects = conn.execute("SELECT type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchall()
            if version != SCHEMA_VERSION or len(objects) != len(SCHEMA) or any(t != 'table' or type(sql) is not str for t, sql in objects):
                return dict(result, reason='INCOMPATIBLE_SCHEMA')
            if {sql for _, sql in objects} != set(SCHEMA):
                return dict(result, reason='INCOMPATIBLE_SCHEMA')
            if conn.execute('PRAGMA integrity_check(1)').fetchall() != [('ok',)]:
                return dict(result, reason='INTEGRITY_CHECK_FAILED')
            counts = dict(conn.execute('SELECT state,count(*) FROM reservations GROUP BY state').fetchall())
            if any(type(state) is not str or state not in STATES for state in counts):
                return dict(result, reason='UNKNOWN_RESERVATION_STATE')
            unresolved = {state: counts.get(state, 0) for state in ('reserved', 'unknown', 'overrun')}
            if time.monotonic() - started > MAX_SECONDS:
                return dict(result, reason='INSPECTION_BUDGET_EXCEEDED')
            return dict(result, schema_compatible=True, reason='SCHEMA_COMPATIBLE_ONLY',
                        unresolved_counts=unresolved, reconciliation_required=any(unresolved.values()))
    except (sqlite3.Error, OverflowError, MemoryError):
        return dict(result, reason='INSPECTION_BUDGET_EXCEEDED' if exhausted else 'INVALID_OR_UNREADABLE_IMAGE')
