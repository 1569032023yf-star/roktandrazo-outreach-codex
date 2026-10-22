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
from autonomy.supervisor import atomic_json, dashboard, read

EXPECTED = {
    'bd_orchestrator.py': 'e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903',
    'discovery/discovery_service.py': '415fbe0cc3323bf45b389f84719c2ee6b52b9ca3d481da6d2f7f70b1c396bd8c',
    'retail_city_queue.py': '02d04313de82464f0f6933df9e7a72f8675ccb6e7ca63b14859751db3e80a6b2',
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
    atomic_json(ROOT / 'autonomy/runtime/telemetry/latest_business_observation.json', clean)
    dashboard(ROOT, bridge_receipt=receipt)
    # Do not replace workstream progress/acceptance with raw aggregate totals.
    state = read(ROOT / 'autonomy/WORKSTREAM_STATUS.json', {})
    state['production_observation'] = clean
    atomic_json(ROOT / 'autonomy/WORKSTREAM_STATUS.json', state)
    print(json.dumps({'observed_at': clean['observed_at'], 'receipt_path': clean['receipt_path'],
                      'business_acceptance': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
