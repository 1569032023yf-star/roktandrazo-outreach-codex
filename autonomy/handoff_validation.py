"""Pure pinned-handoff verification / 固定交接证据验证，无网络或写入。"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta

METADATA = frozenset(('schema_version', 'evidence_kind', 'generated_at',
    'business_timezone', 'producer', 'channel', 'run_id', 'data_sources',
    'production_code_sha256', 'unavailable', 'payload_sha256', 'ruleset_sha256'))


def reconcile_inventory_firings(scheduler, runtime):
    """Read-only attribution; temporal proximity alone grants no authority.

    仅对账：不能把同窗口post-send当Inventory，不授予派发权限。
    """
    authority='automation-1784775229336'
    def stamp(value):
        parsed=datetime.fromisoformat(value)
        if parsed.tzinfo is None:raise ValueError('AWARE_TIMESTAMP_REQUIRED')
        return parsed
    rows={}
    for row in runtime['runs']:
        rows.setdefault(row['run_id'],[]).append(row)
    run_claims=Counter(f.get('run_id') for f in scheduler['firings'])
    firing_claims=Counter(f.get('firing_id') for f in scheduler['firings'])
    results=[]
    for firing in scheduler['firings']:
        candidates=rows.get(firing.get('run_id'),[])
        reason='UNIQUE_RUNTIME_ROW_REQUIRED'
        verified=False
        try:
            triggered=stamp(firing['triggered_at'])
            completed=stamp(firing['completed_at'])
            unique=(type(firing.get('firing_id')) is str and bool(firing['firing_id']) and
                    firing_claims[firing['firing_id']]==1 and run_claims[firing.get('run_id')]==1)
            if not unique:
                reason='ONE_TO_ONE_FIRING_RUN_REQUIRED'
            if unique and len(candidates)==1:
                row=candidates[0]
                reason='INVENTORY_STAGE_AND_AUTHORITY_REQUIRED'
                if (scheduler['canonical_automation']['id']==authority and
                    row['stage']=='inventory' and row['trigger_id']==authority and
                    row['run_id'].startswith('inventory:') and
                    type(firing.get('executed')) is bool and firing['executed']):
                    start=stamp(row['process_started_at']);end=stamp(row['process_finished_at'])
                    verified=triggered<=start<=end<=completed and row['status']=='completed'
                    reason='VERIFIED_INVENTORY_ROW' if verified else 'RUN_WINDOW_OR_TERMINAL_MISMATCH'
            drift=(triggered-stamp(firing['planned_at'])).total_seconds()
            tolerance=scheduler['reconciliation_model']['tolerance_seconds']
            within=(type(tolerance) in (int,float) and tolerance>=0 and abs(drift)<=tolerance)
        except (KeyError,ValueError,TypeError,AttributeError):
            verified=False;reason='INCOMPLETE_OR_INVALID_EVIDENCE';drift=None;within=False
        results.append(dict(firing_id=firing.get('firing_id'),run_id=firing.get('run_id'),
            inventory_execution_verified=verified,reason=reason,
            calculated_drift_seconds=drift,within_declared_tolerance=within))
    return dict(pairs=results,verified_inventory_executions=sum(x['inventory_execution_verified'] for x in results),
        zero_missed_runs='UNKNOWN',production_accepted=False,allow_dispatch=False)


def verify_document(raw, expected_blob, *, now, original_generated_at=None):
    """Verify bytes first; explicitly supplied original time is never guessed.

    先验 Git 字节；原生成时间必须显式提供，恢复后仍披露覆盖差异。
    This validates integrity, not business truth or production acceptance.
    完整性验证不代表业务真实性或生产验收。
    """
    actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if actual != expected_blob:
        raise ValueError('GIT_BLOB_MISMATCH')
    result = {'git_blob_sha': actual, 'git_blob_verified': True,
              'payload_verified': None, 'production_accepted': False}
    value = json.loads(raw)
    if value.get('schema_version') != '1.0':
        raise ValueError('UNSUPPORTED_SCHEMA')
    stamp = datetime.fromisoformat(value['generated_at'])
    if now.tzinfo is None or stamp.tzinfo is None or not timedelta(0) <= now - stamp <= timedelta(hours=1):
        raise ValueError('STALE_OR_INVALID_TIMESTAMP')
    result['generated_at'] = value['generated_at']
    if 'payload_sha256' not in value:
        return result
    core = {k: v for k, v in value.items() if k not in METADATA}
    if value.get('evidence_kind') in ('runtime', 'safe', 'scheduler'):
        core['business_timezone'] = value['business_timezone']
        core['generated_at'] = original_generated_at or value['generated_at']
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if digest != value['payload_sha256']:
        raise ValueError('PAYLOAD_MISMATCH')
    result.update(payload_verified=True, payload_sha256=digest)
    if original_generated_at is not None:
        result['recovered_original_generated_at'] = original_generated_at
        result['envelope_overwrote_original_timestamp'] = original_generated_at != value['generated_at']
    return result
