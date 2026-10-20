"""Authorized 4B1G conversion; all sensitive outputs remain below ignored output/."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brand_acquisition.site_conversion import (
    SearchEvidenceAdapter, SiteConversion, load_directory_input, save_json,
    blocked_by_network_policy,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--search-evidence', required=True)
    parser.add_argument('--authorized-live-web', action='store_true')
    args = parser.parse_args()
    if not args.authorized_live_web:
        parser.error('live first-party conversion requires --authorized-live-web')
    if blocked_by_network_policy(os.environ.get('CODEX_SANDBOX_NETWORK_DISABLED')):
        parser.error('NETWORK_POLICY_BLOCKED; use discovery-only search imports offline')
    if not (ROOT / '.development-copy').is_file():
        parser.error('development copy marker required')
    # Existing web-only development switch; SMTP/IMAP guards remain installed.
    os.environ['ROKT_DEV_CONTROLLED_WEB'] = '1'
    import development_safety
    development_safety.install()
    records, provenance = load_directory_input(args.input_dir)
    out = ROOT / 'output' / 'brand_acquisition' / 'phase4b1g'
    save_json(out / 'input_validation.json', provenance)
    observations = json.loads(Path(args.search_evidence).read_text(encoding='utf-8'))
    metrics = SiteConversion(records, SearchEvidenceAdapter(observations), out,
        provenance['input_sha256']).run()
    print(json.dumps(metrics))  # Counts only, never the real contact list.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
