"""Fixed authenticated read-only observation / 固定认证只读观测入口。

Consumes the existing v2 client. No application import, database or production
mutation. Only local engineering reports/checkpoints are written.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from autonomy.telemetry import consume_bridge_receipt
from autonomy.supervisor import atomic_json, persist_business_observation, read

EXPECTED = {
    'bd_orchestrator.py': '0ddb12feea430a30166a2d1b8acbb1650205d608c52e2e2d808db183665454c8',
    'discovery/discovery_service.py': 'abc2f682cbff4a8b6781997bc2a08ac00f5e41289d67ce02b1c7afa519ad6770',
    'retail_city_queue.py': '27d60fa77644f15b786bfc61390d3671d4a3ee50cc8ae6e9e0fa42b19e820146',
}


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = ROOT / 'autonomy/runtime/bd_full_20261022/observations' / stamp
    folder.mkdir(parents=True)
    client = ROOT / 'tools/city_channel_client.py'
    for operation in ('health', 'telemetry'):
        subprocess.run([sys.executable, '-X', 'utf8', str(client), operation,
                        '--output', str(folder / (operation + '.json'))],
                       cwd=ROOT, check=True, timeout=55, capture_output=True)
    health = read(folder / 'health.json', {})
    if (health.get('http_status') != 200 or health.get('response', {}).get('test_mode') is not False
            or not health.get('response', {}).get('ok')):
        raise RuntimeError('AUTHENTICATED_HEALTH_UNAVAILABLE')
    receipt = read(folder / 'telemetry.json', {})
    clean = consume_bridge_receipt(receipt, approved_channel='rokt-deploy-channel')
    response = receipt['response']
    actual = health['response'].get('production_code_sha256', {})
    clean['production_sha_matches'] = {key: actual.get(key) == value
        and response.get('code', {}).get(key, {}).get('sha256') == value
        for key, value in EXPECTED.items()}
    if not all(clean['production_sha_matches'].values()):
        raise RuntimeError('PRODUCTION_SOURCE_CHANGED_RECONCILE_REQUIRED')
    clean['receipt_sha256'] = hashlib.sha256((folder / 'telemetry.json').read_bytes()).hexdigest()
    clean['receipt_path'] = str((folder / 'telemetry.json').relative_to(ROOT))
    atomic_json(folder / 'business_observation.json', clean)
    persist_business_observation(ROOT, bridge_receipt=receipt, observation=clean)
    print(json.dumps({'observed_at': clean['observed_at'], 'receipt_path': clean['receipt_path'],
                      'business_acceptance': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
