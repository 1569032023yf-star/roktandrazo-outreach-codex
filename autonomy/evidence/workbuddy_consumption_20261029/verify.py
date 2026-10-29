"""固定证据离线核验 / Offline verification of pinned evidence; no production access."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2]))
from autonomy.handoff_validation import METADATA

rows = []
for meta in json.loads((ROOT / 'connector_metadata.json').read_text(encoding='utf-8')):
    raw = (ROOT / 'source' / meta['name']).read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    assert actual == meta['sha'], (meta['name'], actual, meta['sha'])
    doc = json.loads(raw)
    assert doc['producer'] == 'workbuddy-production-operator'
    stamp = datetime.fromisoformat(doc['generated_at'])
    assert stamp.utcoffset() is not None
    assert doc.get('source') or doc.get('sources') or doc.get('evidence_kind') == 'phase0_delta'
    assert doc.get('schema_version') == '1.0' or doc.get('schema') == 'rokt.phase0_refresh.v1'
    required = {
        'PHASE0_STATE_REFRESH_20261029.json': ('canonical_inventory','scheduler_vs_receipts','safe','cities','safety'),
        'SAFE_AUTHORITY_SNAPSHOT.json': ('readings','safe_unique_orgs','rule_version','db_identity'),
        'INVENTORY_SCHEDULER_RECONCILIATION.json': ('firings','runs_matched','canonical_automation','reconciliation_model'),
        'PRODUCTION_RUNTIME_LATEST.json': ('latest_run','recent_runs','latest_run_stage_trace','send_freeze'),
        'CITY_STAGE_TRACE.json': ('formal_completion','discrepancies','ruleset'),
        'PROVIDER_REQUEST_AUDIT_24H.json': ('h24','per_run_attribution','all_cities_7d'),
        'WORKBUDDY_LONG_TERM_OPERATIONS.json': ('fields','sources'),
    }
    assert all(k in doc for k in required[meta['name']])
    core = {k:v for k,v in doc.items() if k not in METADATA}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    rows.append(dict(meta, bytes=len(raw), git_blob_verified=True, json_parsed=True,
        schema=doc.get('schema'), schema_version=doc.get('schema_version'),
        schema_check='ENVELOPE_AND_DECLARED_VERSION_ONLY_NO_EXTERNAL_JSON_SCHEMA',
        producer=doc['producer'], source=doc.get('source',doc.get('sources', 'phase0_delta summaries')),
        generated_at=doc['generated_at'], measured_at=doc.get('measured_at'),
        payload_sha256=doc.get('payload_sha256'), computed_payload_sha256=digest,
        payload_verified=digest == doc['payload_sha256'] if 'payload_sha256' in doc else None,
        freshness='PINNED_HISTORICAL_SNAPSHOT_NOT_LIVE_ACCEPTANCE'))
out = dict(schema='codex.workbuddy-consumption-verification.v1',
    description_zh='逐字节Git及JSON核验；只验证声明schema及结构，不伪称独立生产重采样。',
    description_en='Byte-level Git and JSON verification; checks declared schema/envelope, not independent production resampling.',
    verified_at=datetime.now(timezone.utc).isoformat(), files=rows)
(ROOT / 'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
