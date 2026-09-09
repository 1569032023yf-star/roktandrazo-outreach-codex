"""Build review-only release artifacts / 构建仅供审查的发布制品。"""
import difflib
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PRODUCTION=Path(r'C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach')
FILES=['bd_db.py','bd_orchestrator.py','discovery/discovery_service.py',
       'discovery/providers/browser_maps.py','history_crosscheck.py','discovery/website_resolver.py']
FROZEN=['bd_sender.py','daily_session.py','preflight_gate.py','campaign_eligible_v2.py','final_send_plan.py']

def sha(data):
    return hashlib.sha256(data).hexdigest().upper()

def main():
    package=ROOT/'PHASE3_RELEASE_PACKAGE'
    package.mkdir(exist_ok=True)
    previous=(ROOT/'handoff/phases/PHASE3B_FINAL_PATCH_MANIFEST.md').read_text(encoding='utf-8')
    manifest=['# Phase 3 最终补丁清单 / Phase 3 Final Patch Manifest','',
              '仅限审查；未部署。 / Review only; not deployed.','',
              'DB_MIGRATION_REQUIRED = false','FROZEN_FILES_IN_PATCH = 0','',
              'bd_db.py 仅选择性补丁；禁止复制开发保护代码。 / bd_db.py is selective-patch only; development guards are excluded.','']
    hashes={}
    for name in FILES:
        source=PRODUCTION/name
        baseline=source.read_bytes() if source.exists() else None
        expected=re.search(r'PATH = '+re.escape(name)+r'\nACTION = .*?\nPRODUCTION_BASELINE_SHA256 = (\w+)',previous).group(1)
        assert (sha(baseline) if baseline is not None else 'MISSING')==expected, 'PRODUCTION_BASELINE_DRIFT:'+name
        if name=='bd_db.py':
            old=baseline.decode('utf-8').replace('\r\n','\n')
            dev=(ROOT/name).read_text(encoding='utf-8')
            target=(old.split('def init_db():')[0]+'def init_db():'+dev.split('def init_db():',1)[1]).encode('utf-8')
            patch=''.join(difflib.unified_diff(old.splitlines(True),target.decode().splitlines(True),fromfile='a/bd_db.py',tofile='b/bd_db.py'))
            (package/'bd_db.py.patch').write_bytes(patch.encode('utf-8'))
            action='SELECTIVE_PATCH_ONLY'
        else:
            target=(ROOT/name).read_bytes()
            dest=package/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(target)
            action='REPLACE' if baseline is not None else 'ADD'
        text=target.decode('utf-8')
        assert not any(value in text for value in ('import development_safety','from development_safety','dev_safe_fsp','import sitecustomize'))
        hashes[name]={'baseline':expected,'target':sha(target),'action':action}
        manifest.extend(['```text',f'PATH = {name}',f'ACTION = {action}',f'PRODUCTION_BASELINE_SHA256 = {expected}',
                         f'TARGET_SHA256 = {sha(target)}','PATCH_SCOPE = Phase 2/3 approved upstream replenishment; existing evidence linkage / 已批准上游补库与已有线索证据关联','```',''])
    frozen={name:sha((ROOT/name).read_bytes()) for name in FROZEN}
    expected=json.loads((ROOT/'handoff/phases/FROZEN_SHA256.json').read_text())
    assert all(frozen[n]==expected[n].upper() for n in FROZEN),'FROZEN_DRIFT'
    assert all((ROOT/n).read_bytes()==(PRODUCTION/n).read_bytes() for n in FROZEN),'PRODUCTION_FROZEN_DRIFT'
    manifest.extend(['## 部署与回滚 / Deployment and rollback','',
        '沿用 Phase 3C 手册的备份、维护暂停和回滚流程；制品路径改为 PHASE3_RELEASE_PACKAGE，基线与目标 SHA 使用本清单。 / Reuse the Phase 3C backup, maintenance hold, and rollback procedures with PHASE3_RELEASE_PACKAGE and this manifest’s baseline/target hashes.',
        '现有 schema 足够，无迁移；回滚仅恢复原始代码，不自动清除新证据或恢复发送状态。 / Existing schema is sufficient; no migration. Restore original code for rollback without deleting evidence or resetting delivery state.',''])
    report='\n'.join(manifest)
    (ROOT/'PHASE3_FINAL_PATCH_MANIFEST.md').write_text(report,encoding='utf-8')
    (ROOT/'handoff/phases/PHASE3_FINAL_PATCH_MANIFEST.md').write_text(report,encoding='utf-8')
    (ROOT/'_audit_quarantine/phase3d/release_hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    print(json.dumps({'frozen_files_changed':0,'files':hashes}))

if __name__=='__main__':
    main()
