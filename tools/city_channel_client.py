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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['health', 'releases', 'register', 'preflight', 'apply', 'status', 'telemetry', 'negative-checks'])
    parser.add_argument('--release-id')
    parser.add_argument('--operation-id')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
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
        body = {}
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
