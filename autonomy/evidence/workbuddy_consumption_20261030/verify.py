"""固定交接核验 / Pinned handoff verification; no production access."""
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2]))
from autonomy.handoff_validation import METADATA

rows = []
for meta in json.loads((ROOT / 'REMOTE_FILES.json').read_text(encoding='utf-8')):
    raw = (ROOT / 'source' / meta['name']).read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    assert actual == meta['sha']
    row = dict(meta, bytes=len(raw), git_blob_verified=True)
    if meta['name'].endswith('.json'):
        d = json.loads(raw)
        assert isinstance(d, dict)
        assert d.get('schema_version') == '1.0' or str(d.get('schema', '')).startswith('rokt.')
        assert datetime.fromisoformat(d['generated_at']).utcoffset() is not None
        core = {k:v for k,v in d.items() if k not in METADATA}
        digest = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        row.update(json_parsed=True, schema=d.get('schema'), schema_version=d.get('schema_version'),
                   schema_check='DECLARED_VERSION_AND_OBJECT_ENVELOPE_ONLY_NO_EXTERNAL_JSON_SCHEMA',
                   producer=d.get('producer'), source=d.get('source', d.get('sources', d.get('data_sources'))),
                   generated_at=d['generated_at'], measured_at=d.get('measured_at'),
                   payload_sha256=d.get('payload_sha256'), computed_payload_sha256=digest,
                   payload_verified=digest == d['payload_sha256'] if 'payload_sha256' in d else None)
    else:
        assert raw.decode('utf-8').strip()
        row.update(markdown_read=True, schema_check='DOCUMENT_NOT_JSON_SCHEMA')
    rows.append(row)
s = json.loads((ROOT/'source/INVENTORY_SCHEDULER_RECONCILIATION.json').read_text())
r = json.loads((ROOT/'source/PRODUCTION_RUNTIME_LATEST.json').read_text())
run_ids = {x['run_id'] for x in r['runs']}
pairs = []
for f in s['firings']:
    drift = (datetime.fromisoformat(f['triggered_at'])-datetime.fromisoformat(f['planned_at'])).total_seconds()
    pairs.append(dict(firing_id=f['firing_id'],run_id=f['run_id'], runtime_row_present=f['run_id'] in run_ids,
                      calculated_drift_seconds=drift, within_declared_tolerance=abs(drift)<=600,
                      evidence=f['execution_evidence']))
out = dict(schema='codex.workbuddy-consumption-verification.v1', verified_at=datetime.now(timezone.utc).isoformat(),
           workbuddy_commit='13572ee9f65a71d5006b4d5f53d699bb603c4702', commit_api_created_at='2026-10-29T14:54:12Z',
           files=rows, scheduler_pairs=pairs,
           limitations_zh='Git字节核验不代表生产声明真实或合同获批；无外部JSON Schema，未独立重采样。',
           limitations_en='Git byte verification does not establish production truth or contract approval; no external JSON Schema or independent resampling.')
(ROOT/'VERIFICATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'files':len(rows),'json':sum(x.get('json_parsed',False) for x in rows),'payload_mismatches':[x['name'] for x in rows if x.get('payload_verified') is False], 'pairs':pairs},indent=2))
