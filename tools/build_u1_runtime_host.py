"""Offline host+CPython candidate / 离线宿主与CPython组包，不安装。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from autonomy.build_dev_disabled_host import build_development
from autonomy.disabled_host_package import build_runtime_package


def build(output,source_commit,runtime,runtime_sha256):
    repo=Path(__file__).resolve().parent.parent
    source=subprocess.check_output(['git','rev-parse',source_commit+'^{commit}'],cwd=repo,text=True).strip()
    inputs=['autonomy/disabled_host_package.py','autonomy/build_dev_disabled_host.py',
            'autonomy/windows','autonomy/host_file_transaction.py','autonomy/directory_identity.py',
            'publisher_channel/install_inputs.py','publisher_channel/install_verifier.py',
            'tools/build_u1_runtime_host.py']
    subprocess.run(['git','diff','--exit-code',source,'--',*inputs],cwd=repo,check=True,capture_output=True)
    out=Path(output).absolute();out.mkdir()
    with tempfile.TemporaryDirectory(prefix='u1-runtime-host-') as temp:
        host=Path(temp)/'host';base=build_development(host,source)
        combined=build_runtime_package(out/'host',host,base['manifest_sha256'],runtime,runtime_sha256)
    archive=out/'host-runtime.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted((out/'host').rglob('*')):
            if path.is_file():z.write(path,path.relative_to(out/'host').as_posix())
    digest=hashlib.sha256()
    with archive.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    result=dict(source_commit=source,manifest_sha256=combined['manifest_sha256'],
                archive_sha256=digest.hexdigest(),files=len(combined['manifest']['files']),
                runtime_manifest_sha256=runtime_sha256,allow_install=False,
                production_ready=False,package_complete=False,
                independent_review='PENDING',runtime_plan_install_path_binding='PENDING')
    (out/'BUILD.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('output','source-commit','runtime','runtime-sha256'):p.add_argument('--'+key,required=True)
    a=p.parse_args();print(json.dumps(build(a.output,a.source_commit,a.runtime,a.runtime_sha256)))
