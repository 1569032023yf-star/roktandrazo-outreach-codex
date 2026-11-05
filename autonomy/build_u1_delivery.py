"""Build actual U1 release/rollback tools from a fixed Git commit, no installation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile
from autonomy.build_dev_disabled_host import build_development
from autonomy.release_store import build_bundle, build_archive_from_paths, canonical
from autonomy.disabled_host_package import build_runtime_package


# Transitive repository-level dependencies of discovery.discovery_service.
# Keep this narrow: never ship unrelated root entrypoints, credentials or data.
DISCOVERY_ROOT_SOURCES = (
    'bd_db.py', 'env_loader.py', 'history_crosscheck.py', 'lead_hygiene_gate.py',
    'outreach_control.py', 'retail_city_queue.py', 'broad_outreach_gate.py',
    'email_hygiene.py', 'timezone_resolver.py', 'development_safety.py',
)


def build(output, source_commit, *, python_runtime=None, runtime_manifest_sha256=None):
    if (python_runtime is None)!=(runtime_manifest_sha256 is None):
        raise ValueError('EXACT_RUNTIME_INPUTS_REQUIRED')
    repo=Path(__file__).resolve().parent.parent
    resolved=subprocess.check_output(['git','rev-parse',source_commit+'^{commit}'],cwd=repo,text=True).strip()
    # Compiler consumes working source: require equality with this pinned commit.
    build_inputs=('autonomy/windows/RoktU1Bridge.cs','autonomy/windows/u1_bootstrap.py',
                  'autonomy/windows/Install-DisabledHost.ps1','autonomy/windows/Rollback-DisabledHost.ps1',
                  'autonomy/build_dev_disabled_host.py','autonomy/disabled_host_package.py',
                  'autonomy/build_u1_delivery.py','autonomy/windows/Acl-Transaction.ps1',
                  'autonomy/windows/Host-InstallTransaction.ps1','autonomy/windows/Maintenance-Authority.ps1','autonomy/windows/Observe-HostInstall.ps1','autonomy/windows/Host-PackagePreparation.ps1','autonomy/windows/Publisher-InstallHost.ps1',
                  'autonomy/host_file_transaction.py','autonomy/release_store.py',
                  'autonomy/directory_identity.py','publisher_channel/install_inputs.py',
                  'publisher_channel/install_verifier.py')
    for name in build_inputs:
        pinned=subprocess.check_output(['git','show',resolved+':'+name],cwd=repo)
        if (repo/name).read_bytes().replace(b'\r\n',b'\n') != pinned.replace(b'\r\n',b'\n'):
            raise ValueError('BUILD_INPUT_NOT_PINNED')
    out=Path(output);out.mkdir()
    host_sources={}
    with tempfile.TemporaryDirectory(prefix='u1-delivery-') as temp:
        dev=Path(temp)/'bridge'
        base=build_development(dev,resolved)
        if python_runtime is not None:
            host=out/'runtime-host'
            build_runtime_package(host,dev,base['manifest_sha256'],python_runtime,runtime_manifest_sha256)
            host_sources={'host/'+p.relative_to(host).as_posix():p for p in host.rglob('*') if p.is_file()}
            files={}
        else:
            files={'host/'+p.relative_to(dev).as_posix():p.read_bytes() for p in dev.rglob('*') if p.is_file()}
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',resolved,'autonomy','publisher_channel','discovery'],cwd=repo,text=True).splitlines()
    for name in names:
        if name.startswith(('autonomy/','publisher_channel/','discovery/')) and name.endswith('.py') and '/evidence/' not in name:
            files['python/'+name]=subprocess.check_output(['git','show',resolved+':'+name],cwd=repo)
    for name in DISCOVERY_ROOT_SOURCES:
        files['python/'+name]=subprocess.check_output(['git','show',resolved+':'+name],cwd=repo)
    documentation={
        'README.md':'autonomy/windows/U1-OFFLINE-DELIVERY.md',
        'dependencies/cpython-input.lock.json':'autonomy/windows/cpython-input.lock.json',
        'dependencies/business-wheels.lock.json':'autonomy/windows/business-wheels.lock.json'}
    for target,source in documentation.items():
        files[target]=subprocess.check_output(['git','show',resolved+':'+source],cwd=repo)
    files['DELIVERY.json']=canonical(dict(schema='rokt.u1-delivery.v1',source_commit=resolved,
        inventory_id='1784775229336',python_runtime='Bundled pinned AMD64 CPython' if python_runtime is not None else 'External CPython 3.11+ required; not bundled',
        service_start='Disabled',formal_backend_integrated=False,production_ready=False,
        publisher_source_included=True,python_runtime_integrated=False,
        python_runtime_bundled=python_runtime is not None,runtime_manifest_sha256=runtime_manifest_sha256,
        formal_maintenance_integrated=False,allow_install=False,
        allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,scheduler_created=False))
    bundle=out/'install'
    if host_sources:
        sources=out/'source-files';sources.mkdir()
        all_sources=dict(host_sources)
        for name,raw in files.items():
            path=sources/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            all_sources[name]=path
        digest=build_archive_from_paths(out/'install.zip',all_sources,resolved)
        file_count=len(all_sources)
    else:
        digest=build_bundle(bundle,files,resolved);file_count=len(files)
    tools=out/'rollback-tools';tools.mkdir()
    for name in ('release_store.py',):
        (tools/name).write_bytes(subprocess.check_output(['git','show',resolved+':autonomy/'+name],cwd=repo))
    for name,raw in files.items():
        if name.startswith('host/'):
            target=tools/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    if host_sources:
        # Rollback tools consume the exact archive bytes, not mutable sources.
        with zipfile.ZipFile(out/'install.zip') as install_archive:
            for name in host_sources:
                target=tools/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(install_archive.read('payload/'+name))
    (tools/'README.md').write_text('回滚工具 / Rollback tools\n\n文件发布指针：release_store.py --root STORE rollback TRANSACTION --expected-current VERSION。\nFile publication pointer: use that command with retained versions/backups.\n\n禁用宿主完整文件/注册回滚：从host/调用 Install-DisabledHost.ps1 -Rollback -PackageRoot HOST -ApprovedManifestSha256 HASH -ApprovedSourceCommit SOURCE_SHA -RuntimePlan PLAN -ApprovedRuntimePlanSha256 PLAN_HASH -Execute。未决操作使用-RecoverInstall；两者仅补偿已知状态，禁止自动重放。\nDisabled-host file/registration compensation: use the above exact manifest and runtime plan. Use -RecoverInstall for interrupted operations; neither action replays forward effects.\n\n旧Rollback-DisabledHost.ps1只撤销注册，不是完整文件回滚。保留管理员审计目录全部日志；升级保留原有状态；首次安装回滚只清理身份匹配的事务新建空根。新部署还需要正式维护租约与身份门禁。此包不是数据库或现场状态备份。\nThe legacy Rollback-DisabledHost.ps1 is registration-only. Retain all administrator audit journals; upgrades preserve existing state, while fresh rollback removes only recorded empty roots with matching identities. Formal maintenance/identity gates remain required before installation. This archive is not a database/site-state backup.\n',encoding='utf-8')
    for name in documentation:
        target=tools/('OFFLINE-DELIVERY.md' if name=='README.md' else name)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(files[name])
    for folder in ((tools,) if host_sources else (bundle,tools)):
        with zipfile.ZipFile(out/(folder.name+'.zip'),'x',compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(folder.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(folder).as_posix())
    result=dict(source_commit=resolved,manifest_sha256=digest,files=file_count,
        artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.zip')},
        python_runtime_bundled=bool(host_sources),package_complete=False,
        independent_review='PENDING',production_ready=False)
    (out/'BUILD.json').write_bytes(canonical(result));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--source-commit',required=True)
    p.add_argument('--python-runtime');p.add_argument('--runtime-manifest-sha256')
    a=p.parse_args();print(json.dumps(build(a.output,a.source_commit,python_runtime=a.python_runtime,runtime_manifest_sha256=a.runtime_manifest_sha256),sort_keys=True))
