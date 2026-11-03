"""Build actual U1 release/rollback tools from a fixed Git commit, no installation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
from autonomy.build_dev_disabled_host import build_development
from autonomy.release_store import build_bundle, canonical


def build(output, source_commit):
    repo=Path(__file__).resolve().parent.parent
    resolved=subprocess.check_output(['git','rev-parse',source_commit+'^{commit}'],cwd=repo,text=True).strip()
    # Compiler consumes working source: require equality with this pinned commit.
    build_inputs=('autonomy/windows/RoktU1Bridge.cs','autonomy/windows/u1_bootstrap.py',
                  'autonomy/windows/Install-DisabledHost.ps1','autonomy/windows/Rollback-DisabledHost.ps1',
                  'autonomy/build_dev_disabled_host.py','autonomy/disabled_host_package.py',
                  'autonomy/build_u1_delivery.py','autonomy/windows/Acl-Transaction.ps1',
                  'autonomy/windows/Host-InstallTransaction.ps1','autonomy/windows/Maintenance-Authority.ps1',
                  'autonomy/host_file_transaction.py')
    for name in build_inputs:
        pinned=subprocess.check_output(['git','show',resolved+':'+name],cwd=repo)
        if (repo/name).read_bytes().replace(b'\r\n',b'\n') != pinned.replace(b'\r\n',b'\n'):
            raise ValueError('BUILD_INPUT_NOT_PINNED')
    out=Path(output);out.mkdir()
    with tempfile.TemporaryDirectory(prefix='u1-delivery-') as temp:
        dev=Path(temp)/'bridge'
        build_development(dev,resolved)
        files={'host/'+p.relative_to(dev).as_posix():p.read_bytes() for p in dev.rglob('*') if p.is_file()}
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',resolved,'autonomy'],cwd=repo,text=True).splitlines()
    for name in names:
        if name.startswith('autonomy/') and name.endswith('.py') and '/evidence/' not in name:
            files['python/'+name]=subprocess.check_output(['git','show',resolved+':'+name],cwd=repo)
    files['DELIVERY.json']=canonical(dict(schema='rokt.u1-delivery.v1',source_commit=resolved,
        inventory_id='1784775229336',python_runtime='External CPython 3.11+ required; not bundled',
        service_start='Disabled',formal_backend_integrated=False,production_ready=False,
        formal_maintenance_integrated=False,allow_install=False,
        allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,scheduler_created=False))
    bundle=out/'install';digest=build_bundle(bundle,files,resolved)
    tools=out/'rollback-tools';tools.mkdir()
    for name in ('release_store.py',):
        (tools/name).write_bytes(subprocess.check_output(['git','show',resolved+':autonomy/'+name],cwd=repo))
    for name,raw in files.items():
        if name.startswith('host/'):
            target=tools/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    (tools/'README.md').write_text('回滚工具 / Rollback tools\n\n文件发布指针：release_store.py --root STORE rollback TRANSACTION --expected-current VERSION。\nFile publication pointer: use that command with retained versions/backups.\n\n禁用宿主完整文件/注册回滚：从host/调用 Install-DisabledHost.ps1 -Rollback -PackageRoot HOST -ApprovedManifestSha256 HASH -ApprovedSourceCommit SOURCE_SHA -RuntimePlan PLAN -ApprovedRuntimePlanSha256 PLAN_HASH -Execute。未决操作使用-RecoverInstall；两者仅补偿已知状态，禁止自动重放。\nDisabled-host file/registration compensation: use the above exact manifest and runtime plan. Use -RecoverInstall for interrupted operations; neither action replays forward effects.\n\n旧Rollback-DisabledHost.ps1只撤销注册，不是完整文件回滚。保留管理员审计目录全部日志；升级保留原有状态；首次安装回滚只清理身份匹配的事务新建空根。新部署还需要正式维护租约与身份门禁。此包不是数据库或现场状态备份。\nThe legacy Rollback-DisabledHost.ps1 is registration-only. Retain all administrator audit journals; upgrades preserve existing state, while fresh rollback removes only recorded empty roots with matching identities. Formal maintenance/identity gates remain required before installation. This archive is not a database/site-state backup.\n',encoding='utf-8')
    for folder in (bundle,tools):
        with zipfile.ZipFile(out/(folder.name+'.zip'),'x',compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(folder.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(folder).as_posix())
    result=dict(source_commit=resolved,manifest_sha256=digest,files=len(files),
        artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.zip')},
        independent_review='PENDING',production_ready=False)
    (out/'BUILD.json').write_bytes(canonical(result));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--source-commit',required=True)
    a=p.parse_args();print(json.dumps(build(a.output,a.source_commit),sort_keys=True))
