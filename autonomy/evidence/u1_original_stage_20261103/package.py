"""重建固定工程制品 / Rebuild pinned engineering artifacts; no installation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SOURCE='3fbaa5ec42cb0655ecd1c811ccd8d02b1fc837bb'
BASELINE='3bbb77d7f2cce774b3addfdbf851342ad09393c5'
OWNER_FILES=('bd_db.py','bd_orchestrator.py','autonomy/original_inventory_owner.py',
             'autonomy/inventory_maintenance.py','autonomy/lock_recovery.py',
             'autonomy/growth_ledger.py','autonomy/unattended_policy.py','autonomy/release_store.py',
'autonomy/original_stage_event.py','autonomy/inventory_event_bridge.py','autonomy/process_backend.py',
'autonomy/single_slot_adapter.py','autonomy/process_job.py','autonomy/process_control.py',
'autonomy/durable_slots.py','autonomy/ledger_evidence.py','autonomy/host_preparation.py')


def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def blob(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)


def main():
    subprocess.run([sys.executable,'-B','-m','autonomy.build_u1_delivery',
        '--source-commit',SOURCE,'--output',str(HERE/'package')],cwd=ROOT,check=True)
    owner=HERE/'owner-companion';owner.mkdir()
    rows=[]
    for name in OWNER_FILES:
        raw=blob(SOURCE,name)
        before=subprocess.run(['git','show',BASELINE+':'+name],cwd=ROOT,capture_output=True)
        if before.returncode not in (0,128):raise ValueError('BASELINE_READ_FAILED')
        expected=dict(kind='FILE',git_blob_sha256=sha(before.stdout)) if before.returncode==0 else dict(kind='ABSENT')
        dest=owner/'payload'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        rows.append(dict(path=name,bytes=len(raw),sha256=sha(raw),expected_before=expected))
    manifest=dict(schema='rokt.original-owner-companion.v2',source_commit=SOURCE,baseline_commit=BASELINE,
        files=rows,site_before_bytes_verified=False,automatic_update_supported=False,
        production_applied=False,installable_release=False,allow_install=False,allow_dispatch=False,
        allow_cancel_dispatch=False,smtp_enabled=False)
    save(owner/'manifest.json',manifest)
    (owner/'README.md').write_text('''# 原所有者固定配套包 / Fixed original-owner companion

中文：仅含清单列出的十七个固定源码文件及精确摘要，补齐原取锁入口的新依赖。不是自动更新器，不扩大宿主安装器白名单，不允许任意路径。expected_before 是固定 Git 基线的字节条件，不是现场取证；现场只有精确匹配后才能由原正式通道受审替换，缺失或未知已有文件必须 STOP_AND_PRESERVE。未部署，门禁全 false。

English: Only the seventeen listed fixed source files and exact digests are included, completing new dependencies of the original lock entry. This is not an updater, does not expand the host installer's allowlist, and permits no arbitrary paths. expected_before is a fixed Git-baseline byte condition, not site evidence. A reviewed original-channel update must match it exactly before replacement; missing or unknown existing files require STOP_AND_PRESERVE. Not deployed; every gate remains false.

中文：此包只完成原锁身份、事件和结算接线的工程依赖。正式 Provider 执行协议及服务启动配置仍未完成，不能宣称完整可安装发布版。不要直接解压覆盖现场；生产配置、数据库、凭据和调度器均不在包内。

English: This archive completes engineering dependencies for original-lock identity, event and settlement wiring only. The formal Provider protocol and service activation configuration remain incomplete; this is not a complete installable release. Never extract it over the site. Production configuration, databases, credentials and schedulers are absent.
''',encoding='utf-8')
    archive=HERE/'owner-companion.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(owner.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(owner).as_posix())
    with tempfile.TemporaryDirectory(prefix='u1-owner-companion-import-') as temp:
        dest=Path(temp)
        with zipfile.ZipFile(archive) as z:z.extractall(dest)
        code="import sys;sys.path.insert(0,sys.argv[1]);from autonomy.original_inventory_owner import OriginalOwnerAuthority,observer;from autonomy import inventory_maintenance;from autonomy.original_stage_event import OriginalStageEvent;from autonomy.process_backend import ProcessBackend;print('OWNER_DEPENDENCIES_IMPORT_ONLY_OK')"
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(dest/'payload')],cwd=dest,
            capture_output=True,text=True,timeout=20)
        if result.returncode:raise ValueError('ISOLATED_OWNER_IMPORT_FAILED: '+result.stderr)
    save(HERE/'OWNER_PACKAGE.json',dict(source_commit=SOURCE,payload_files=len(rows),
        artifact_sha256=sha(archive.read_bytes()),manifest_sha256=sha((owner/'manifest.json').read_bytes()),
        isolated_import_passed=True,import_output=result.stdout.strip(),production_applied=False))
    artifacts=[]
    for folder in (HERE/'package',owner):
        for path in sorted(folder.rglob('*')):
            if path.is_file():artifacts.append(dict(path=path.relative_to(HERE).as_posix(),bytes=path.stat().st_size,sha256=sha(path.read_bytes())))
    artifacts.append(dict(path=archive.name,bytes=archive.stat().st_size,sha256=sha(archive.read_bytes())))
    save(HERE/'ARTIFACT_MANIFEST.json',dict(source_commit=SOURCE,files=artifacts))
    print(json.dumps(json.loads((HERE/'OWNER_PACKAGE.json').read_text())),flush=True)


if __name__=='__main__':main()
