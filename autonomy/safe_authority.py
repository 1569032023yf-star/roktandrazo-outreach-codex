"""Strict, pure SAFE authority projection / 严格且无副作用的 SAFE 权威投影。

The trusted transport caller supplies approved_channel separately. This module
has no network, credential, database, scheduler, file-write or refresh operation.
调用方在认证传输后单独传入通道授权；此模块没有网络、凭据、数据库或写入行为。
"""
from datetime import datetime, timedelta, timezone
import re

CHANNEL = 'rokt-deploy-channel'
RULE_HASHES = {
    'campaign_eligible_v2.py': '1143bedf563c0f76b883359362ffb2c2ea11c375fd923dc59768c5529cf3ad34',
    'preflight_gate.py': '2cd286f201430fb9a48c68ead512671f398732e50e768c2fd69031f127f52622',
}
# Six hours is this consumer's maximum measurement age, independently of the
# producer's fresh flag. Transport/generated receipts must be <= one hour old.
# 独立策略：测量起点最长六小时，传输回执和生成时间最长一小时。
MAX_MEASUREMENT_AGE = timedelta(hours=6)
MAX_RECEIPT_AGE = timedelta(hours=1)


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _timestamp(value):
    _require(type(value) is str, 'INVALID_TIMESTAMP')
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError('INVALID_TIMESTAMP') from None
    _require(stamp.tzinfo is not None and stamp.utcoffset() is not None, 'INVALID_TIMESTAMP')
    return stamp


def _is_count(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def diagnose_safe_readings(receipt, *, approved_channel=None):
    """Aggregate diagnostic only; never acceptance / 仅聚合诊断，不确认 SAFE。

    A count delta cannot distinguish database mutation, MX volatility or rule
    evaluation changes. Never echo raw failure text or customer identifiers.
    数量差异不能区分数据库变更、MX 波动或规则变化；根因保留 UNKNOWN。
    """
    _require(approved_channel == CHANNEL, 'UNAPPROVED_SOURCE')
    _require(type(receipt) is dict and type(receipt.get('http_status')) is int
             and receipt['http_status'] == 200, 'TRANSPORT_NOT_VERIFIED')
    raw = receipt.get('response')
    _require(type(raw) is dict and raw.get('schema') == 'rokt.safe_authority.v1'
             and raw.get('operation') == 'safe'
             and raw.get('authoritative_route') == '/v1/safe', 'INVALID_SAFE_ENVELOPE')
    readings = raw.get('readings')
    _require(type(readings) is list and len(readings) == 2, 'INVALID_SAFE_READINGS')
    counts = []
    for index, reading in enumerate(readings, 1):
        _require(type(reading) is dict and type(reading.get('reading')) is int
                 and reading['reading'] == index, 'INVALID_SAFE_READINGS')
        rows, orgs = reading.get('candidate_rows'), reading.get('unique_organizations')
        _require(_is_count(rows) and _is_count(orgs) and rows >= orgs, 'INVALID_SAFE_READINGS')
        counts.append((rows, orgs, _timestamp(reading.get('sampling_time'))))
    _require(counts[0][2] < counts[1][2], 'INVALID_READINGS_ORDER')
    row_delta = counts[1][0] - counts[0][0]
    org_delta = counts[1][1] - counts[0][1]
    duplicates_delta = row_delta - org_delta
    signals = []
    if row_delta:
        signals.append('CANDIDATE_ROW_COUNT_CHANGED')
    if org_delta:
        signals.append('UNIQUE_ORGANIZATION_COUNT_CHANGED')
    if duplicates_delta:
        signals.append('DUPLICATE_ROW_EXCESS_CHANGED')
    if type(raw.get('reading_agreement')) is bool and raw['reading_agreement'] != (org_delta == 0):
        signals.append('DECLARED_AGREEMENT_CONFLICT')
    return {'schema': 'rokt.safe-reading-diagnostics.v1',
            'acceptance_scope': 'DIAGNOSTIC_ONLY', 'current_safe': 'UNKNOWN',
            'safe_net_growth': 'UNKNOWN', 'root_cause': 'UNKNOWN',
            'signals': signals, 'candidate_rows_delta': row_delta,
            'unique_organizations_delta': org_delta,
            'duplicate_row_excess_delta': duplicates_delta,
            'sampling_gap_seconds': (counts[1][2] - counts[0][2]).total_seconds(),
            'summary_zh': '仅比较双读聚合差异；缺少同快照资格原因证据，不能归因或确认净增。',
            'summary_en': 'Aggregate reading differences only; without same-snapshot eligibility reasons, causation and net growth remain unknown.'}


def consume_safe_authority(receipt, *, approved_channel=None, now=None):
    """Validate authenticated evidence and return only allowlisted aggregates.

    验证认证回执，仅返回固定聚合；发现量不冒充确认组织，缺历史净增仍 UNKNOWN。
    This accepts no comparable historical ledger, so net growth always remains
    UNKNOWN even if a producer adds an unsupported numeric growth claim.
    """
    now = now if now is not None else datetime.now(timezone.utc)
    _require(isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None,
             'INVALID_NOW')
    _require(approved_channel == CHANNEL, 'UNAPPROVED_SOURCE')
    _require(type(receipt) is dict and type(receipt.get('http_status')) is int
             and receipt['http_status'] == 200, 'TRANSPORT_NOT_VERIFIED')
    raw = receipt.get('response')
    _require(type(raw) is dict, 'INVALID_SAFE_ENVELOPE')
    _require(raw.get('schema') == 'rokt.safe_authority.v1'
             and raw.get('operation') == 'safe' and raw.get('verdict') == 'ok'
             and raw.get('authoritative_route') == '/v1/safe', 'INVALID_SAFE_ENVELOPE')
    _require(all(raw.get(key) is True for key in (
        'available', 'fresh', 'measurement_complete', 'mx_probe_ok', 'reading_agreement')),
        'SAFE_NOT_AVAILABLE')
    _require('failure_reason' in raw and raw['failure_reason'] is None, 'SAFE_MEASUREMENT_FAILURE')

    observed = _timestamp(receipt.get('observed_at'))
    generated = _timestamp(raw.get('generated_at'))
    measured = _timestamp(raw.get('measured_at'))
    finished = _timestamp(raw.get('finished_at'))
    _require(measured <= finished <= generated <= observed <= now, 'INVALID_MEASUREMENT_ORDER')
    _require(now - measured <= MAX_MEASUREMENT_AGE
             and now - generated <= MAX_RECEIPT_AGE
             and now - observed <= MAX_RECEIPT_AGE, 'STALE_SAFE_MEASUREMENT')

    rules = raw.get('rule_version')
    _require(type(rules) is dict and rules.get('name') == 'V1_V2_MX_HISTORY_SUPPRESSION_BUSINESS_FIT'
             and rules.get('entrypoint') == 'campaign_eligible_v2.select_candidates_for_plan_v2'
             and rules.get('mx_probe') == 'preflight_gate.query_mx', 'INVALID_SAFE_RULES')
    code = rules.get('code')
    _require(type(code) is dict and all(type(code.get(name)) is dict
             and code[name].get('sha256') == sha for name, sha in RULE_HASHES.items()),
             'UNREVIEWED_SAFE_RULES')
    _require(raw.get('source') == 'bd_leads.db (read-only)'
             and type(raw.get('method')) is str
             and 'mode=ro connection' in raw['method']
             and 'SAFE = distinct organization_key over the returned candidate rows' in raw['method'],
             'INVALID_SAFE_METHOD')
    db = raw.get('db_identity')
    _require(type(db) is dict and db.get('quick_check') == 'ok'
             and type(db.get('sha256')) is str
             and re.fullmatch(r'[0-9a-f]{64}', db['sha256']) is not None,
             'INVALID_DATABASE_IDENTITY')

    controls = []
    for key, expected in (('mx_positive_control', 'ok'), ('mx_negative_control', 'nxdomain')):
        control = raw.get(key)
        _require(type(control) is dict and control.get('mx_status') == expected, 'INVALID_MX_CONTROL')
        controls.append(_timestamp(control.get('checked_at')))
    readings = raw.get('readings')
    total = raw.get('safe_unique_orgs')
    _require(_is_count(total) and type(readings) is list and len(readings) == 2,
             'INVALID_SAFE_READINGS')
    samples = []
    for index, reading in enumerate(readings, 1):
        _require(type(reading) is dict and type(reading.get('reading')) is int
                 and reading['reading'] == index, 'INVALID_SAFE_READINGS')
        count, candidates = reading.get('unique_organizations'), reading.get('candidate_rows')
        _require(_is_count(count) and _is_count(candidates) and count == total
                 and candidates >= count, 'SAFE_READINGS_DISAGREE')
        samples.append(_timestamp(reading.get('sampling_time')))
    _require(measured <= min(controls) and max(controls) <= samples[0]
             and samples[0] < samples[1] <= finished, 'INVALID_READINGS_ORDER')

    def funnel(period, hours):
        section = raw.get('new_customer_funnel')
        section = section.get(period) if type(section) is dict else None
        if type(section) is not dict or type(section.get('window_hours')) is not int or section['window_hours'] != hours:
            section = {}
        return {name: section[name] if _is_count(section.get(name)) else 'UNKNOWN' for name in (
            'merchant_records_discovered', 'unique_organizations_discovered', 'verified_official_sites',
            'new_leads', 'new_leads_with_email', 'new_first_party_official_emails',
            'new_distinct_organization_keys')}

    return {
        'schema': 'rokt.safe-authority-observation.v1',
        'source': CHANNEL, 'observed_at': observed.isoformat(),
        'measured_at': measured.isoformat(), 'finished_at': finished.isoformat(),
        'safe_authority_connected': True, 'current_safe': total,
        'rule_sha256': dict(RULE_HASHES), 'db_sha256': db['sha256'],
        'measurement_age_hours': (now - measured).total_seconds() / 3600,
        'rolling_24h': funnel('h24', 24), 'rolling_7d': funnel('d7', 168),
        'new_verified_organizations_24h': 'UNKNOWN',
        'safe_net_growth_24h': 'UNKNOWN', 'safe_net_growth_7d': 'UNKNOWN',
        'summary_zh': '双读与权威规则验证通过；发现不等于身份确认，无可比历史不计算净增。',
        'summary_en': 'Two readings and authority rules validated; discovery is not confirmed identity; no net growth without comparable history.',
        'acceptance_scope': 'SAFE_AUTHORITY_SNAPSHOT_ONLY_NOT_FULL_B_ACCEPTANCE',
    }
