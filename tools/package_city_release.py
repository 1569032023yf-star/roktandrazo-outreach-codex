"""Byte-exact offline package and rollback rehearsal / 精确字节离线打包及回滚演练。"""
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'autonomy/runtime/channel_takeover_20261021/production_snapshot'
CANDIDATE = ROOT / 'autonomy/runtime/city_semantic_rebase_20261021/candidate'
DEST = ROOT / 'patches/production/phase4a8u'
PINNED = {
    'discovery/discovery_service.py': '96dcc751dff7ff9174b556120bdf440211328ccf52b32559509164cb0169ae14',
    'retail_city_queue.py': '03b4c6302dba271b5b0bed34567db5048086d4b1d0e9b2aee9a878023f349432',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    # Import only the existing executor's pure patch parser. Never call its runtime APIs.
    path = Path('C:/Users/15690/WorkBuddy/deploy-channel/bin/executor.py')
    spec = importlib.util.spec_from_file_location('city_offline_parser', path)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    chunks, targets = [], []
    for rel, before_sha in PINNED.items():
        before, after = (BASE / rel).read_bytes(), (CANDIDATE / rel).read_bytes()
        assert sha(before) == before_sha, 'Baseline bytes drifted'
        section = b''.join(difflib.diff_bytes(difflib.unified_diff,
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=('a/' + rel).encode(), tofile=('b/' + rel).encode()))
        count = sum(line.startswith(b'@@ ') for line in section.splitlines())
        assert parser.apply_unified(before, section, rel, expected_hunks=count) == after
        assert parser.apply_unified(after, section, rel, reverse=True, expected_hunks=count) == before
        # Both-file backups must be independently recoverable exact bytes.
        backup = bytes(before)
        assert sha(backup) == before_sha
        targets.append({'path': rel, 'before_sha256': before_sha, 'after_sha256': sha(after),
                        'before_bytes': len(before), 'after_bytes': len(after), 'hunks': count,
                        'exact_forward_reverse': True, 'offline_backup_restore_verified': True})
        chunks.append(section)
    patch = b''.join(chunks)
    (DEST / 'city_recovery.patch').write_bytes(patch)
    manifest = {'schema_version': 2,
        'release_id': 'phase4a8u-city-recovery-production-rebase-20261022',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'author_identity': 'codex-city-developer',
        'summary_zh': '仅城市有界超时恢复；保留身份、历史、邮箱资格与发送冻结门禁。',
        'summary_en': 'Bounded city timeout recovery only; preserve identity, history, email eligibility and sending freeze.',
        'status': 'AWAITING_FINAL_REVIEW', 'target_files': targets,
        'patch_sha256': sha(patch), 'production_backup_verified': 'NOT_EXECUTED',
        'rollback_scope': 'OFFLINE_EXACT_BYTE_REHEARSAL_ONLY'}
    (DEST / 'candidate_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
