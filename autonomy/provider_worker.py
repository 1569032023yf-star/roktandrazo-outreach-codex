"""Pinned real-adapter Worker entrypoint / 固定真实适配器Worker入口。

No scheduler, receipt signer, installation or dispatch authorization.
不创建调度器、不签回执、不授予安装或派发权限。
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

# -I intentionally excludes cwd/PYTHONPATH. The fixed worker belongs to the
# manifest-bound python/autonomy tree, never a caller-supplied import directory.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autonomy.provider_environment import pinned_provider_adapter


def read_operation(stream):
    """Decode bounded backend input; integrity checks do not grant authority.
    有界读取现有后端操作；摘要一致不代表Owner授权。
    """
    from autonomy.growth_ledger import digest
    from autonomy.single_slot_adapter import BACKEND_PROTOCOL, OPERATION_SCHEMA
    from autonomy.unattended_policy import INVENTORY
    import re
    raw = stream.read(65537)
    if type(raw) is not bytes or not raw or len(raw) > 65536:
        raise ValueError('WORKER_OPERATION_SIZE')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:raise ValueError('WORKER_OPERATION_DUPLICATE_KEY')
            result[key] = value
        return result
    def nonfinite(value):raise ValueError('WORKER_OPERATION_NONFINITE')
    value = json.loads(raw,object_pairs_hook=unique,parse_constant=nonfinite)
    if (type(value) is not dict or value.get('schema') != OPERATION_SCHEMA or
        value.get('backend_protocol') != BACKEND_PROTOCOL or
        value.get('scope') != 'isolated_offline' or
        value.get('production_execution') is not False or
        value.get('inventory_id') != INVENTORY or
        type(value.get('backend_id')) is not str or not value['backend_id'] or
        type(value.get('max_wall_seconds')) is not int or
        not 0 < value['max_wall_seconds'] <= 3600):
        raise ValueError('WORKER_OPERATION_REJECTED')
    body = dict(value);key = body.pop('idempotency_key',None)
    if type(key) is not str or not re.fullmatch('[0-9a-f]{64}',key) or key != digest(body):
        raise ValueError('WORKER_OPERATION_BINDING')
    original = ('original_event_digest','original_claim_digest')
    if any(k in value for k in original):
        hashes = original + ('lock_token_hash','process_identity_hash','runtime_id','slots_id','budget_id')
        if any(type(value.get(k)) is not str or not re.fullmatch('[0-9a-f]{64}',value[k]) for k in hashes):
            raise ValueError('WORKER_ORIGINAL_JOIN_REQUIRED')
        if (type(value.get('epoch')) is not int or value['epoch'] < 1 or
            any(type(value.get(k)) is not str or not value[k] for k in
                ('slot','owner','run_id','request_id','token'))):
            raise ValueError('WORKER_ORIGINAL_CLAIM_REQUIRED')
        claim = {k:value[k] for k in ('slot','epoch','owner','run_id','request_id')}
        claim['claim_token_hash'] = digest(value['token'])
        if digest(claim) != value['original_claim_digest']:
            raise ValueError('WORKER_ORIGINAL_CLAIM_BINDING')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider-config', required=True)
    parser.add_argument('--provider-config-sha256', required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(argv)
    try:
        operation = None if args.preflight else read_operation(sys.stdin.buffer)
        with pinned_provider_adapter(args.provider_config, args.provider_config_sha256) as adapter:
            contract = asdict(adapter.contract)
            # Construct the actual configured adapter, without performing a query.
            # The capability view is not a backend receipt or business result.
            if args.preflight:
                print(json.dumps(dict(schema='rokt.provider-worker-preflight.v1',
                    provider=adapter.provider_name, configured=adapter.configured,
                    contract=contract, dispatch_authorized=False,
                    production_execution=False), sort_keys=True))
                return 0
            # No adapter currently supplies authoritative run-bound terminal,
            # cancellation and billing receipts. Never synthesize zero costs,
            # execute a billable query or return the backend receipt envelope.
            print(json.dumps(dict(error='CONTRACT_MISSING',provider=adapter.provider_name,
                missing_fields=contract['missing_fields'],external_request_started=False,
                operation_digest_checked=operation is not None),
                sort_keys=True), file=sys.stderr)
            return 78
    except Exception:
        # Do not echo exceptions/configuration: they may contain credential data.
        print('PROVIDER_WORKER_INPUT_REJECTED', file=sys.stderr)
        return 65


if __name__ == '__main__':
    raise SystemExit(main())
