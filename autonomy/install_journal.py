"""Offline durable installation intent primitive; never invokes an OS adapter.

The caller must supply an already protected audit directory. This component does
not establish Windows ACLs, a maintenance lease, or installation authority.
An exclusive operation file is never repaired, truncated, or reused on recovery.
"""
import hashlib
import json
import os
import re
from pathlib import Path

STEPS = ('STAGE', 'PUBLISH', 'REGISTER_DISABLED', 'CODE_ACL', 'STATE_ACL', 'VERIFY')


def _line(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


class InstallJournal:
    """Single writer, CREATE_NEW operation log. Reopening is status-only."""

    def __init__(self, audit_root, operation_id, manifest_sha256, lease_binding):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', operation_id):
            raise ValueError('INVALID_OPERATION_ID')
        for value in (manifest_sha256, lease_binding):
            if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
                raise ValueError('EXACT_DIGEST_REQUIRED')
        self.path = Path(audit_root) / (operation_id + '.jsonl')
        self._file = self.path.open('xb', buffering=0)
        self._count = 0
        self._pending = None
        self._failed = False
        try:
            self._write(dict(schema='rokt.install-journal.v1', operation_id=operation_id,
                             manifest_sha256=manifest_sha256, lease_binding=lease_binding,
                             before='ABSENT', kind='PREPARED'))
        except BaseException:
            self._file.close()
            raise

    def _write(self, record):
        try:
            data = _line(record)
            if self._file.write(data) != len(data):
                raise OSError('SHORT_JOURNAL_WRITE')
            os.fsync(self._file.fileno())
        except BaseException:
            self._failed = True
            raise

    def intent(self, step):
        if self._failed or self._pending or self._count >= len(STEPS) or step != STEPS[self._count]:
            raise ValueError('STOP_AND_PRESERVE')
        self._write(dict(kind='INTENT', step=step))
        self._pending = step

    def receipt(self, step, evidence_sha256):
        if self._failed or self._pending != step:
            raise ValueError('STOP_AND_PRESERVE')
        if not isinstance(evidence_sha256, str) or not re.fullmatch('[0-9a-f]{64}', evidence_sha256):
            raise ValueError('EXACT_EVIDENCE_DIGEST_REQUIRED')
        self._write(dict(kind='RECEIPT', step=step, evidence_sha256=evidence_sha256))
        self._pending = None
        self._count += 1

    def close(self):
        self._file.close()


def inspect_install(path):
    """Never reconstruct a writer or authorize any installation/replay."""
    raw = Path(path).read_bytes()
    complete = False
    count = 0
    pending = None
    try:
        if not raw.endswith(b'\n'):
            raise ValueError('TORN_LOG')
        rows = [json.loads(line) for line in raw.splitlines()]
        header = rows[0]
        if header['schema'] != 'rokt.install-journal.v1' or header['kind'] != 'PREPARED' or header['before'] != 'ABSENT':
            raise ValueError('BAD_HEADER')
        for row in rows[1:]:
            if count >= len(STEPS) or row['step'] != STEPS[count]:
                raise ValueError('BAD_ORDER')
            if row['kind'] == 'INTENT' and pending is None:
                pending = row['step']
            elif row['kind'] == 'RECEIPT' and pending == row['step'] and re.fullmatch('[0-9a-f]{64}', row['evidence_sha256']):
                pending = None
                count += 1
            else:
                raise ValueError('BAD_RECEIPT')
        complete = count == len(STEPS) and pending is None
    except (ValueError, KeyError, IndexError, TypeError):
        pass
    return dict(observed='ALL_RECEIPTS_RECORDED' if complete else 'UNKNOWN',
                completed_steps=count, pending_step=pending,
                journal_sha256=hashlib.sha256(raw).hexdigest(),
                action='STOP_AND_PRESERVE', allow_replay=False, allow_install=False,
                allow_dispatch=False, production_execution=False)
