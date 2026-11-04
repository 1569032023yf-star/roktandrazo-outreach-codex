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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider-config', required=True)
    parser.add_argument('--provider-config-sha256', required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(argv)
    try:
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
                missing_fields=contract['missing_fields'],external_request_started=False),
                sort_keys=True), file=sys.stderr)
            return 78
    except Exception:
        # Do not echo exceptions/configuration: they may contain credential data.
        print('PROVIDER_WORKER_INPUT_REJECTED', file=sys.stderr)
        return 65


if __name__ == '__main__':
    raise SystemExit(main())
