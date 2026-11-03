"""Read-only space admission check; not a reservation / 只读空间准入，非预留。"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import tempfile

MIB = 1024 * 1024
MIN_FREE_BYTES = 256 * MIB
COMMIT_RESERVE_BYTES = 16 * MIB


def _positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f'{name} must be a positive integer')
    return value


def _existing_directory(path: Path) -> Path:
    candidate = path.resolve(strict=False)
    while True:
        try:
            mode = candidate.stat().st_mode
        except FileNotFoundError:
            parent = candidate.parent
            if parent == candidate:
                raise
            candidate = parent
            continue
        if not stat.S_ISDIR(mode):
            raise NotADirectoryError(str(candidate))
        return candidate


def check_storage(
    runtime: str | os.PathLike,
    root: str | os.PathLike,
    temp: str | os.PathLike | None = None,
    *,
    min_free_bytes: int = MIN_FREE_BYTES,
    commit_reserve_bytes: int = COMMIT_RESERVE_BYTES,
) -> dict:
    """Check every target, failing closed; never delete or launch anything.

    无效阈值抛 ValueError；路径或空间未知逐项返回 UNKNOWN 并拒绝启动。
    Invalid thresholds raise ValueError; unknown path/space rejects admission.
    """
    required = (_positive_integer(min_free_bytes, 'min_free_bytes')
                + _positive_integer(commit_reserve_bytes, 'commit_reserve_bytes'))
    checks = []
    for label, supplied in [('runtime', runtime), ('root', root), ('temp', temp)]:
        evidence = {'target': label, 'requested_path': None,
                    'resolved_path': None, 'checked_path': None,
                    'free_bytes': None, 'status': 'UNKNOWN', 'error_type': None}
        try:
            value = tempfile.gettempdir() if label == 'temp' and supplied is None else supplied
            raw = os.fspath(value)
            evidence['requested_path'] = raw
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError('target must be a nonempty directory path')
            path = Path(raw).resolve(strict=False)
            evidence['resolved_path'] = str(path)
            existing = _existing_directory(path)
            evidence['checked_path'] = str(existing)
            free = shutil.disk_usage(existing).free
            if isinstance(free, bool) or not isinstance(free, int) or free < 0:
                raise ValueError('disk usage returned invalid free bytes')
            evidence['free_bytes'] = free
            evidence['status'] = 'PASS' if free >= required else 'LOW_SPACE'
        except Exception as exc:
            # Error class only: never copy arbitrary exception payloads to reports.
            evidence['error_type'] = type(exc).__name__
        checks.append(evidence)
    allowed = all(item['status'] == 'PASS' for item in checks)
    return {'allow_start': allowed, 'reason': 'STORAGE_READY' if allowed else 'STORAGE_BLOCKED',
            'min_free_bytes': min_free_bytes, 'commit_reserve_bytes': commit_reserve_bytes,
            'required_free_bytes': required, 'checks': checks,
            'space_reserved': False}
