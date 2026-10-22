"""Pure pinned-handoff verification / 固定交接证据验证，无网络或写入。"""
import hashlib
import json
from datetime import datetime, timedelta

METADATA = frozenset(('schema_version', 'evidence_kind', 'generated_at',
    'business_timezone', 'producer', 'channel', 'run_id', 'data_sources',
    'production_code_sha256', 'unavailable', 'payload_sha256', 'ruleset_sha256'))


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
