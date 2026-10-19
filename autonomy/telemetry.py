"""Read-only sanitized aggregate validator / 只读脱敏聚合校验器。

No collectors, network, database, credentials, state writes or scheduler.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from uuid import UUID

INBOX = Path(__file__).resolve().parent / 'runtime' / 'telemetry' / 'inbox'
MAX_BYTES = 32768
MAX_AGE = timedelta(hours=1)
METRICS = frozenset({
    'new_verified_organizations', 'new_official_sites', 'new_first_party_emails',
    'new_history_mx_verified', 'new_safe_organizations', 'customer_emails_sent',
    'replies', 'bounces', 'unsubscribes',
})
FIELDS = frozenset({'schema_version', 'snapshot_id', 'source', 'collected_at',
                    'period', 'window_start', 'window_end', 'counts'})
SOURCE = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z', re.ASCII)


class InvalidSnapshot(ValueError):
    """Only fixed reason codes; never echo rejected payloads / 不回显输入。"""


def _reject(code):
    raise InvalidSnapshot(code)


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        _reject('INVALID_TIMESTAMP')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError:
        _reject('INVALID_TIMESTAMP')


def _now(value):
    value = value if value is not None else datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('AWARE_NOW_REQUIRED')
    return value.astimezone(timezone.utc)


def validate_snapshot(payload, *, approved_sources=(), now=None):
    """Validate one object; approval must come from trusted caller policy.

    单对象验证；来源授权必须由可信调用方提供，不接受输入内的授权标记。
    """
    now = _now(now)
    if type(payload) is not dict or set(payload) != FIELDS:
        _reject('INVALID_FIELDS')
    if type(payload['schema_version']) is not int or payload['schema_version'] != 1:
        _reject('INVALID_VERSION')
    sid = payload['snapshot_id']
    try:
        if type(sid) is not str or str(UUID(sid)) != sid:
            _reject('INVALID_ID')
    except (ValueError, AttributeError):
        _reject('INVALID_ID')
    source = payload['source']
    if (type(source) is not str or not SOURCE.fullmatch(source)
            or source not in approved_sources):
        _reject('UNAPPROVED_SOURCE')
    period = payload['period']
    if type(period) is not str or period not in ('24h', '7d'):
        _reject('INVALID_PERIOD')
    collected = _timestamp(payload['collected_at'])
    start = _timestamp(payload['window_start'])
    end = _timestamp(payload['window_end'])
    if collected > now or end > now or start > now:
        _reject('FUTURE_TIMESTAMP')
    if now - collected > MAX_AGE:
        _reject('STALE_SNAPSHOT')
    duration = timedelta(hours=24) if period == '24h' else timedelta(days=7)
    if end != collected or end - start != duration:
        _reject('INVALID_WINDOW')
    counts = payload['counts']
    if type(counts) is not dict or not counts or not set(counts) <= METRICS:
        _reject('INVALID_METRICS')
    if any(type(v) is not int or v < 0 or v > 2**63 - 1 for v in counts.values()):
        _reject('INVALID_COUNT')
    # Return a detached allowlisted object, never raw extra input.
    return {**payload, 'counts': dict(counts)}


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            _reject('DUPLICATE_JSON_KEY')
        obj[key] = value
    return obj


def read_inbox(*, approved_sources=(), now=None, seen_ids=(), inbox=INBOX):
    """Read approved local JSON snapshots without writing or consuming files.

    Results retain source/window boundaries: never sum rolling snapshots.
    测试可传临时 inbox；默认仅读取本地固定目录，不递归，不写状态。
    """
    now = _now(now)
    accepted, reasons = [], Counter()
    root = Path(inbox)
    result = {'status': 'UNKNOWN', 'snapshots': [], 'rejected': {}}
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)()
           for p in (root, *root.parents)):
        result['rejected'] = {'UNSAFE_INBOX': 1}
        return result
    try:
        paths = sorted(root.iterdir())
    except FileNotFoundError:
        return result
    except OSError:
        result['rejected'] = {'INBOX_UNREADABLE': 1}
        return result
    for path in paths:
        if path.suffix != '.json':
            continue
        try:
            if path.is_symlink() or getattr(path, 'is_junction', lambda: False)() or not path.is_file():
                _reject('UNSAFE_FILE')
            with path.open('rb') as handle:
                data = handle.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                _reject('OVERSIZED_SNAPSHOT')
            payload = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object)
            accepted.append(validate_snapshot(payload, approved_sources=approved_sources, now=now))
        except InvalidSnapshot as exc:
            reasons[str(exc)] += 1
        except (ValueError, UnicodeError, RecursionError):
            reasons['INVALID_JSON'] += 1
        except OSError:
            reasons['FILE_UNREADABLE'] += 1
    frequencies = Counter(s['snapshot_id'] for s in accepted)
    seen_ids = frozenset(seen_ids)
    unique = []
    for item in accepted:
        if frequencies[item['snapshot_id']] > 1 or item['snapshot_id'] in seen_ids:
            reasons['DUPLICATE_SNAPSHOT'] += 1
        else:
            unique.append(item)
    # Latest complete snapshot per source/period; no cross-source addition.
    groups = {}
    for item in unique:
        groups.setdefault((item['source'], item['period']), []).append(item)
    selected = []
    for items in groups.values():
        latest = max(s['collected_at'] for s in items)
        newest = [s for s in items if s['collected_at'] == latest]
        if len(newest) != 1:
            reasons['AMBIGUOUS_LATEST'] += len(newest)
        else:
            selected.append(newest[0])
    result['snapshots'] = sorted(selected, key=lambda s: (s['source'], s['period']))
    result['status'] = 'VALID' if selected else 'UNKNOWN'
    result['rejected'] = dict(sorted(reasons.items()))
    return result
