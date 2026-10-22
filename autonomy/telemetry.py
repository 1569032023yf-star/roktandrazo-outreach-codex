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


def consume_bridge_receipt(receipt, *, approved_channel=None, now=None):
    """Allowlisted v2 aggregate consumer; no network/DB access.

    只消费调用方认证过的正式回执；缺失指标和不充分证明保持UNKNOWN。
    Channel identity inside JSON is not authorization: the trusted caller must
    separately supply approved_channel after authenticated transport.
    """
    now = _now(now)
    if approved_channel != 'rokt-deploy-channel':
        _reject('UNAPPROVED_SOURCE')
    if type(receipt) is not dict or receipt.get('http_status') != 200:
        _reject('TRANSPORT_NOT_VERIFIED')
    raw = receipt.get('response')
    if (type(raw) is not dict or raw.get('schema') != 'rokt.telemetry.v1'
            or raw.get('channel_id') != approved_channel
            or raw.get('test_mode') is not False or raw.get('verdict') != 'OK'):
        _reject('INVALID_BRIDGE_ENVELOPE')
    try:
        collected = datetime.fromisoformat(raw['generated_at'])
        if collected.tzinfo is None or collected.utcoffset() is None:
            _reject('INVALID_TIMESTAMP')
    except (KeyError, TypeError, ValueError):
        _reject('INVALID_TIMESTAMP')
    if collected > now or now - collected > MAX_AGE:
        _reject('STALE_OR_FUTURE_BRIDGE_RECEIPT')

    def section(key):
        value = raw.get(key)
        return value if type(value) is dict else {}

    def count(obj, key):
        value = obj.get(key)
        return value if type(value) is int and 0 <= value <= 2**63 - 1 else 'UNKNOWN'

    discovery, sends = section('discovery'), section('sends')
    guard, inventory = section('guardrails'), section('inventory')
    city, safe = section('city'), section('safe')
    result = {
        'source': approved_channel, 'observed_at': collected.isoformat(),
        'schema': 'rokt.bd-business-observation.v1',
        'summary_zh': '正式认证回执的固定聚合投影；存量、观察窗口和未知资格分开。',
        'summary_en': 'Fixed aggregate projection of an authenticated receipt; totals, observation windows and unknown eligibility remain separate.',
        'historical_totals': {key: count(discovery, key) for key in ('leads_total', 'leads_with_email')},
        'rolling_24h': {'provider_requests': count(discovery, 'provider_requests_24h'),
                        'new_raw_merchants': 'UNKNOWN', 'new_verified_organizations': 'UNKNOWN',
                        'new_verified_official_sites': 'UNKNOWN', 'new_first_party_emails': 'UNKNOWN',
                        'new_history_clean_organizations': 'UNKNOWN', 'safe_net_growth': 'UNKNOWN'},
        'rolling_7d': {'new_verified_organizations': 'UNKNOWN', 'safe_net_growth': 'UNKNOWN'},
        'current_safe': 'UNKNOWN',
        'safe_authority_connected': False,
        'safety': {'smtp_disabled': guard.get('smtp_enabled') == '0',
                   'smtp_observed': guard.get('smtp_enabled') if guard.get('smtp_enabled') in ('0', '1') else 'UNKNOWN',
                   'sent_today': count(sends, 'sent_today'), 'total_sent': count(sends, 'total_sent'),
                   'duplicate_inventory': 'UNKNOWN',
                   'designated_inventory_active_count': count(section('automations'), 'active_inventory_count'),
                   'running_inventory_last_2h': count(inventory, 'running_inventory_24h_window'),
                   'lock_released': inventory.get('lock_value') == 'released'},
        'bounce_total': count(sends, 'bounce_log'),
        'suppression_total': count(sends, 'suppression_list'),
        'stage_telemetry': 'NOT_EXPOSED',
        'city_completion_conditions': 'NOT_EXPOSED',
        'lake_placid_provider_requests': 'UNKNOWN',
        'last_inventory_run': 'UNKNOWN',
        'active_cities': [],
        'limitations_zh': ['指定ID计数不能证明全局Inventory唯一性。', '旧running_inventory_24h_window实际上只统计2小时。', 'SAFE快照未包含完整资格来源和有效性契约，不能据此确认权威连接。'],
        'limitations_en': ['A designated-ID count does not establish global Inventory uniqueness.', 'Legacy running_inventory_24h_window actually covers two hours.', 'SAFE snapshots lack a complete authority/validity contract and cannot establish authority connectivity.'],
    }
    # Never copy arbitrary strings or customer details into the public projection.
    statuses = {'active', 'ACTIVE', 'pending', 'PENDING', 'QUEUED', 'completed', 'COMPLETED'}
    cities = city.get('active')
    if isinstance(cities, list):
        for row in cities[:100]:
            if (type(row) is dict and type(row.get('city')) is str
                    and re.fullmatch(r'[A-Za-z .\x27-]{1,80}', row['city'])
                    and type(row.get('status')) is str and row['status'] in statuses):
                result['active_cities'].append({'city': row['city'], 'status': row['status']})
    runs = inventory.get('recent_runs')
    if isinstance(runs, list):
        for row in runs[:100]:
            if (type(row) is dict and row.get('stage') == 'inventory'
                    and type(row.get('run_id')) is str
                    and re.fullmatch(r'inventory:\d{4}-\d{2}-\d{2}:[a-zA-Z0-9_-]{1,64}', row['run_id'])
                    and type(row.get('status')) is str
                    and row['status'] in {'completed', 'partial', 'stopped', 'running'}):
                result['last_inventory_run'] = {key: row[key] for key in ('run_id', 'status')}
                result['last_inventory_run']['actual_historical_run_count'] = count(row, 'actual')
                # stop_reason/error are untrusted free text; do not echo them.
                result['last_inventory_run']['target_met'] = row.get('stop_reason') == 'target_met'
                break
    return result


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
