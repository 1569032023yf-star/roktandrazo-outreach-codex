"""Offline pinned-byte package / 离线固定字节包，不调用生产执行入口。"""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = 'eceb019b70a3b24a1d90a4efeebd3692c446dd2c'
CANDIDATE = '8d63d2d45393509589261a1ddd0bbcf650a0d1b2'
FILES = ('discovery/providers/browser_maps.py',
         'discovery/providers/browser_maps_scraper.py',
         'discovery/models.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(ref, path):
    return subprocess.check_output(['git', 'show', f'{ref}:{path}'], cwd=ROOT)


def main():
    channel = Path('C:/Users/15690/WorkBuddy/deploy-channel/bin')
    sys.path.insert(0, str(channel))
    spec = importlib.util.spec_from_file_location('offline_provider_parser', channel/'executor.py')
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    import multifile
    dest = ROOT/'patches/production/provider_diagnostics_20261024'
    dest.mkdir(parents=True, exist_ok=True)
    sections, targets = [], []
    for path in FILES:
        before, after = blob(BASE, path), blob(CANDIDATE, path)
        section = b''.join(difflib.diff_bytes(difflib.unified_diff,
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=('a/'+path).encode(), tofile=('b/'+path).encode()))
        count = sum(line.startswith(b'@@ ') for line in section.splitlines())
        assert parser.apply_unified(before, section, path, expected_hunks=count) == after
        assert parser.apply_unified(after, section, path, reverse=True, expected_hunks=count) == before
        targets.append(dict(path=path, before_sha256=sha(before),
            after_sha256=sha(after), before_bytes=len(before), after_bytes=len(after),
            exact_forward_reverse=True,
            production_before_attestation='PENDING'))
        sections.append(section)
    patch = b''.join(sections)
    assert [s['path'] for s in multifile.parse_sections(patch)] == list(FILES)
    (dest/'change.patch').write_bytes(patch)
    manifest = dict(schema_version=2, release_id='provider-diagnostics-20261024',
        source_commit=CANDIDATE, development_base_commit=BASE,
        author_identity='codex-provider-engineering', target_files=targets,
        patch_sha256=sha(patch), release_ready=False, production_compatible='UNVERIFIED',
        summary_zh='开发基线精确正反补丁已验证；必须取得生产字节及scraper 路径许可后重验登记。',
        summary_en='Exact forward/reverse development patch verified; production bytes and scraper scope approval are required before registration.')
    (dest/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files':len(targets),'forward_reverse_verified':True,'release_ready':False}))


if __name__ == '__main__':
    main()
