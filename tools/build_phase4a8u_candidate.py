"""Build and rehearse a development-only candidate / 构建并演练开发候选包。

No production paths, databases, network, or deployment calls are used.
不访问生产路径、数据库、网络或部署入口。
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '72bdd70a13dd959264a3137fc546334249b48be1'
TARGETS = ('discovery/discovery_service.py', 'retail_city_queue.py')


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if not (ROOT / '.development-copy').is_file():
        raise RuntimeError('DEVELOPMENT_COPY_REQUIRED')
    dest = ROOT / 'patches/production/phase4a8u'
    dest.mkdir(parents=True, exist_ok=True)
    patch = git('diff', '--no-ext-diff', '--binary', BASE, '--', *TARGETS)
    if not patch:
        raise RuntimeError('EMPTY_PATCH')
    patch_path = dest / 'city_timeout_recovery.patch'
    patch_path.write_bytes(patch)
    records = []
    # A temporary isolated repository is only an offline patch rehearsal.
    with tempfile.TemporaryDirectory(prefix='phase4a8u-rehearsal-') as temp:
        work = Path(temp)
        git('init', '-q', cwd=work)
        git('config', 'core.autocrlf', 'false', cwd=work)
        originals = {}
        for target in TARGETS:
            before = git('show', f'{BASE}:{target}')
            originals[target] = before
            path = work / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(before)
        git('apply', '--check', str(patch_path), cwd=work)
        git('apply', str(patch_path), cwd=work)
        for target in TARGETS:
            before = originals[target]
            after = (work / target).read_bytes()
            expected = (ROOT / target).read_bytes().replace(b'\r\n', b'\n')
            if after != expected:
                raise RuntimeError(f'CANDIDATE_BYTES_MISMATCH:{target}')
            compile(after, target, 'exec')
            records.append({'path': target, 'candidate_base_sha256': sha(before),
                            'candidate_after_sha256': sha(after),
                            'before_bytes': len(before), 'after_bytes': len(after),
                            'production_source_sha256': 'UNKNOWN'})
        git('apply', '--reverse', '--check', str(patch_path), cwd=work)
        git('apply', '--reverse', str(patch_path), cwd=work)
        for target in TARGETS:
            if (work / target).read_bytes() != originals[target]:
                raise RuntimeError(f'ROLLBACK_BYTES_MISMATCH:{target}')
    manifest = {
        'description_zh': '开发基线候选包；未经生产源码指纹核实，不可作为已批准发布清单',
        'description_en': 'Development-baseline candidate; not an approved release until production source fingerprints are attested',
        'release_id': 'phase4a8u-city-timeout-terminal-recovery',
        'status': 'CANDIDATE_REQUIRES_PRODUCTION_ATTESTATION_AND_REGISTRATION',
        'base_commit': BASE, 'files': records, 'patch_sha256': sha(patch),
        'patch_bytes': len(patch), 'candidate_line_endings': 'LF',
        'offline_forward_and_reverse_byte_verification': True,
        'production_compatibility_verified': False, 'production_deployed': False,
        'inventory_id': '1784775229336', 'manual_inventory_trigger_allowed': False,
        'smtp_enabled': 0, 'emails_sent_by_this_task': 0,
        'required_gates': ['approved_production_source_snapshot_and_sha256', 'new_release_registration',
            'all_file_before_hashes_match', 'version_compatibility', 'tests_and_review',
            'inventory_idle_and_official_lock', 'safe_schedule_window', 'byte_backup_verified',
            'atomic_replacement_with_all_file_failure_rollback', 'after_hashes_verified',
            'smtp_disabled_and_sending_tasks_paused', 'normal_scheduled_runtime_acceptance'],
    }
    (dest / 'release_request.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
