"""Offline, Windows-only identity pin for an existing recovery SQLite file.

This is one building block, not a recovery authorization or a multi-store lock.
The caller must obtain the expected identity from an already trusted source.
It does not protect SQLite sidecars from external writes or bind the owner fence.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
import threading

from autonomy.single_slot_adapter import AdapterError, _pin_windows_ledger


def _identity(path):
    stat = path.stat()
    if not stat.st_ino or stat.st_nlink != 1:
        raise AdapterError('RECOVERY_LOG_IDENTITY_UNAVAILABLE')
    return stat.st_dev, stat.st_ino


def _family(path):
    return (path, *(Path(str(path) + suffix) for suffix in ('-journal', '-wal', '-shm')))


def _reject_aliases(path, protected):
    # SQLite sidecar names are reserved in both directions. Resolve before
    # comparing names, and compare file IDs as well when both files exist.
    for other in protected:
        for left in _family(path):
            for right in _family(other):
                if (os.path.normcase(str(left)) == os.path.normcase(str(right)) or
                        (left.exists() and right.exists() and os.path.samefile(left, right))):
                    raise AdapterError('RECOVERY_LOG_ALIAS_REJECTED')


@contextmanager
def pinned_recovery_log(path, *, expected_identity, protected):
    """Pin one existing log; yield a connection check for ``_record``.

    The expected identity must be obtained independently before untrusted
    callbacks. No file is created. The guard pins only the log, and must not be
    used as evidence that other databases or the operation are bound.
    """
    path = Path(path).resolve(strict=True)
    others = tuple(Path(item).resolve(strict=True) for item in protected)
    if (type(expected_identity) is not tuple or len(expected_identity) != 2
            or not all(type(value) is int and value > 0 for value in expected_identity)):
        raise AdapterError('RECOVERY_LOG_EXPECTED_IDENTITY_REQUIRED')
    _reject_aliases(path, others)
    with _pin_windows_ledger(path) as pinned:
        if pinned != expected_identity or _identity(path) != expected_identity:
            raise AdapterError('RECOVERY_LOG_IDENTITY_CHANGED')

        active = True
        gate = threading.Lock()

        def check(connection):
            with gate:
                try:
                    if not active:
                        raise AdapterError('RECOVERY_LOG_PIN_INACTIVE')
                    if type(connection) is not sqlite3.Connection:
                        raise AdapterError('RECOVERY_LOG_CONNECTION_REJECTED')
                    if _identity(path) != expected_identity:
                        raise AdapterError('RECOVERY_LOG_IDENTITY_CHANGED')
                    _reject_aliases(path, others)
                    databases = connection.execute('PRAGMA database_list').fetchall()
                    main = [row for row in databases if row[1] == 'main']
                    if len(main) != 1 or not main[0][2]:
                        raise AdapterError('RECOVERY_LOG_CONNECTION_REJECTED')
                    opened = Path(main[0][2]).resolve(strict=True)
                    if opened != path or _identity(opened) != expected_identity:
                        raise AdapterError('RECOVERY_LOG_CONNECTION_REJECTED')
                except (OSError, ValueError) as exc:
                    raise AdapterError('RECOVERY_LOG_UNVERIFIED') from exc

        try:
            yield check
        finally:
            # Drain in-flight checks before the enclosing context releases the
            # pin; future checks fail even during the small window before close.
            with gate:
                active = False
