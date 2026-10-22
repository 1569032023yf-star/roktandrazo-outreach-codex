"""Fixed authorized bridge client / 固定正式通道客户端，凭据仅驻内存。

No executor CLI, registry writes, production paths or arbitrary commands.
不直接调用执行器、不写注册表、不接受生产路径或任意命令。
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

CHANNEL = Path('C:/Users/15690/WorkBuddy/deploy-channel')
READ_ONLY_OBSERVATIONS = {'runtime', 'city', 'provider-audit', 'scheduler', 'safe'}


def observation_body(operation, run_id=None, city=None, hours=None, limit=None):
    """Closed read-only contract; never accepts SQL, paths or SAFE refresh."""
    import re
    body = {}
    for key, value, allowed in (
        ('run_id', run_id, {'runtime'}), ('city', city, {'city', 'provider-audit'}),
        ('hours', hours, {'provider-audit', 'scheduler'}), ('limit', limit, {'runtime'}),
    ):
        if value is None:
            continue
        if operation not in allowed:
            raise ValueError('parameter not supported for operation: ' + key)
        if key == 'run_id' and (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9:_\-]{1,80}', value)):
            raise ValueError('invalid run_id')
        if key == 'city' and (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z .'\-]{1,64}", value)):
            raise ValueError('invalid city name')
        if key in {'hours', 'limit'} and (type(value) is not int or not 1 <= value <= (168 if key == 'hours' else 50)):
            raise ValueError('invalid range: ' + key)
        body[key] = value
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['health', 'releases', 'register', 'preflight', 'apply', 'status', 'telemetry', 'negative-checks', *sorted(READ_ONLY_OBSERVATIONS)])
    parser.add_argument('--release-id')
    parser.add_argument('--operation-id')
    parser.add_argument('--run-id')
    parser.add_argument('--city')
    parser.add_argument('--hours', type=int)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        obs_body = observation_body(args.operation, args.run_id, args.city, args.hours, args.limit)
        if args.operation in READ_ONLY_OBSERVATIONS and (args.release_id or args.operation_id):
            raise ValueError('release/operation identifiers are not observation parameters')
    except ValueError as error:
        parser.error(str(error))
    sys.path.insert(0, str(CHANNEL / 'bin'))
    spec = importlib.util.spec_from_file_location('city_bridge_credentials', CHANNEL / 'bin/bridge.py')
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    token = bridge.cred_read('rokt-deploy-channel:bridge-token')

    def request(path, body):
        req = urllib.request.Request('http://127.0.0.1:8791' + path,
            data=json.dumps(body).encode(), method='POST',
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return {'http_status': response.status, 'response': json.load(response)}
        except urllib.error.HTTPError as error:
            return {'http_status': error.code, 'response': json.load(error)}
        except (urllib.error.URLError, TimeoutError):
            return {'http_status': None, 'outcome': 'UNKNOWN_TRANSPORT_FAILURE',
                    'reconcile_before_retry': args.operation in {'register', 'apply'}}

    if args.operation == 'negative-checks':
        result = {'unregistered_release': request('/v1/preflight', {'release_id': 'city-closure-unregistered-probe'}),
                  'arbitrary_command': request('/v1/execute', {'command': 'REJECT_ONLY_NO_EXECUTION'}),
                  'path_traversal': request('/v1/preflight', {'release_id': '../invalid'})}
    else:
        body = dict(obs_body)
        if args.release_id:
            body['release_id'] = args.release_id
        if args.operation_id:
            body['operation_id'] = args.operation_id
        if args.operation == 'apply':
            body['confirm'] = True
        result = request('/v1/' + args.operation, body)
    result['observed_at'] = datetime.now(timezone.utc).isoformat()
    result['summary_zh'] = '正式受限通道真实响应；传输失败不推断生产状态。'
    result['summary_en'] = 'Live restricted-channel response; transport failures do not establish production state.'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    # Responses may include business metadata; print only operation/status.
    print(json.dumps({'operation': args.operation, 'http_status': result.get('http_status'),
                      'outcome': result.get('outcome'), 'artifact': str(args.output)}))


if __name__ == '__main__':
    main()
