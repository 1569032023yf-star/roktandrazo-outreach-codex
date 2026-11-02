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
    bridge='autonomy/windows/RoktU1Bridge.cs'
    pinned=subprocess.check_output(['git','show',resolved+':'+bridge],cwd=repo)
    if (repo/bridge).read_bytes().replace(b'\r\n',b'\n') != pinned.replace(b'\r\n',b'\n'):
        raise ValueError('BRIDGE_SOURCE_NOT_PINNED')
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
        allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,scheduler_created=False))
    bundle=out/'install';digest=build_bundle(bundle,files,resolved)
    tools=out/'rollback-tools';tools.mkdir()
    for name in ('release_store.py',):
        (tools/name).write_bytes(subprocess.check_output(['git','show',resolved+':autonomy/'+name],cwd=repo))
    (tools/'README.md').write_text('回滚工具 / Rollback tools\n\nUse release_store.py --root STORE rollback TRANSACTION --expected-current VERSION.\n回滚必须同时保留STORE中的backups记录和versions旧版本；此包不是生产状态备份。\nRetain both backups and versions; this archive alone is not a state backup. No service or Inventory changes.\n',encoding='utf-8')
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
