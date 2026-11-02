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
        self._file = self.path.open('x+b', buffering=0)
        self._expected = b''
        self._count = 0
        self._pending = None
        self._failed = False
        try:
            identity = os.fstat(self._file.fileno())
            self._identity = (identity.st_dev, identity.st_ino)
            self._write(dict(schema='rokt.install-journal.v1', operation_id=operation_id,
                             manifest_sha256=manifest_sha256, lease_binding=lease_binding,
                             before='ABSENT', kind='PREPARED'))
        except BaseException:
            self._file.close()
            raise

    def _write(self, record):
        try:
            self.revalidate()
            data = _line(record)
            if self._file.write(data) != len(data):
                raise OSError('SHORT_JOURNAL_WRITE')
            os.fsync(self._file.fileno())
            self._expected += data
            self.revalidate()
        except BaseException:
            self._failed = True
            raise

    def revalidate(self):
        """Detect observed mutation, not an ACL or concurrent-writer exclusion.

        检测已观察到的替换/内容修改；失败后不可恢复写入，不授权重放。
        Checks cannot eliminate mutation races between checks and effects.
        """
        if self._failed:
            raise ValueError('STOP_AND_PRESERVE')
        try:
            for identity in (os.fstat(self._file.fileno()), self.path.stat()):
                if ((identity.st_dev, identity.st_ino) != self._identity or
                        identity.st_nlink != 1):
                    raise ValueError('JOURNAL_IDENTITY_CHANGED')
            self._file.seek(0)
            observed = self._file.read(len(self._expected) + 1)
            self._file.seek(0, os.SEEK_END)
            if observed != self._expected:
                raise ValueError('JOURNAL_CONTENT_CHANGED')
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


MAX_JOURNAL_BYTES = 16384


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_FIELD')
        result[key] = value
    return result


def inspect_install(path, *, expected_binding=None):
    """Never reconstruct a writer or authorize any installation/replay."""
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_JOURNAL_BYTES + 1)
    oversized = len(raw) > MAX_JOURNAL_BYTES
    complete = False
    count = 0
    pending = None
    binding_verified = False
    try:
        if oversized or not raw.endswith(b'\n'):
            raise ValueError('TORN_LOG')
        rows = [json.loads(line, object_pairs_hook=_unique_object) for line in raw.splitlines()]
        if not all(type(row) is dict for row in rows):
            raise ValueError('OBJECT_ROWS_REQUIRED')
        header = rows[0]
        if header['schema'] != 'rokt.install-journal.v1' or header['kind'] != 'PREPARED' or header['before'] != 'ABSENT':
            raise ValueError('BAD_HEADER')
        if (not isinstance(header.get('operation_id'), str) or
                not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', header['operation_id']) or
                any(not isinstance(header.get(key), str) or
                    not re.fullmatch('[0-9a-f]{64}', header[key])
                    for key in ('manifest_sha256', 'lease_binding'))):
            raise ValueError('BAD_BINDING')
        if expected_binding is not None:
            keys = {'operation_id', 'manifest_sha256', 'lease_binding'}
            if (type(expected_binding) is not dict or set(expected_binding) != keys or
                    any(header[key] != expected_binding[key] for key in keys)):
                raise ValueError('BINDING_MISMATCH')
            binding_verified = True
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
    except (ValueError, KeyError, IndexError, TypeError, RecursionError):
        pass
    return dict(observed='ALL_RECEIPTS_RECORDED' if complete else 'UNKNOWN',
                completed_steps=count, pending_step=pending,
                journal_sha256=None if oversized else hashlib.sha256(raw).hexdigest(),
                oversized=oversized, binding_verified=binding_verified,
                action='STOP_AND_PRESERVE', allow_replay=False, allow_install=False,
                allow_dispatch=False, production_execution=False)
