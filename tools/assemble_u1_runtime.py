"""Assemble a workspace-only runtime from pinned ZIP/wheels, with no network.

仅在全新工作区目录装配固定ZIP与wheel；不安装Windows服务或激活业务。
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from tools.prepare_u1_python_runtime import prepare, sha


def write_runtime_content_manifest(output, python):
    output=Path(output)
    path=output/'U1_RUNTIME_CONTENT.json'
    if path.exists():raise ValueError('NEW_CONTENT_MANIFEST_REQUIRED')
    content=dict(schema='rokt.u1-runtime-content.v1',python=python,
                 files={p.relative_to(output).as_posix():sha(p.read_bytes())
                        for p in sorted(output.rglob('*')) if p.is_file()})
    path.write_text(json.dumps(content,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    return path


def wheel_requirements(lock, wheelhouse):
    if lock.get('schema') != 'rokt.u1-business-wheel-input.v1':
        raise ValueError('WHEEL_LOCK_SCHEMA')
    lines = []
    seen = set()
    for row in lock['wheels']:
        name, version, filename, digest = (row[k] for k in ('name','version','wheel','sha256'))
        if (not re.fullmatch('[A-Za-z0-9_.-]+', name) or
                not re.fullmatch('[A-Za-z0-9_.+!-]+', version) or
                not re.fullmatch('[A-Za-z0-9_.+-]+[.]whl', filename) or
                not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('WHEEL_LOCK_VALUE')
        key = re.sub('[-_.]+', '-', name).lower()
        if key in seen:
            raise ValueError('DUPLICATE_WHEEL_PROJECT')
        seen.add(key)
        wheel = Path(wheelhouse)/filename
        if wheel.is_symlink() or not wheel.is_file() or sha(wheel.read_bytes()) != digest:
            raise ValueError('WHEEL_HASH')
        lines.append(f'{name}=={version} --hash=sha256:{digest}')
    if not lines:
        raise ValueError('EMPTY_WHEEL_LOCK')
    return '\n'.join(lines)+'\n'


def assemble(archive, cpython_lock, wheel_lock, wheelhouse, output):
    # Validate all downloaded inputs before creating any output.
    requirements = wheel_requirements(wheel_lock, wheelhouse)
    output = Path(output).absolute()
    original = prepare(archive, cpython_lock['sha256'], output)
    exe = output/original['python']
    requirement_file = output/'BUSINESS_REQUIREMENTS.txt'
    requirement_file.write_text(requirements, encoding='utf-8')
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PIP_'))}
    env['PIP_NO_INDEX'] = '1'
    commands = [
        [str(exe),'-I','-B','-m','pip','--isolated','--disable-pip-version-check',
         'install','--no-index','--no-deps','--require-hashes','--no-compile',
         '--find-links',str(Path(wheelhouse).resolve()),'-r',str(requirement_file)],
        [str(exe),'-I','-B','-m','pip','--isolated','--disable-pip-version-check','check'],
        [str(exe),'-I','-B','-c',
         'import dns.resolver,httpx,playwright.sync_api,tzdata,greenlet;print("PINNED_DEPENDENCIES_IMPORT_OK")'],
    ]
    outputs = []
    with tempfile.TemporaryDirectory(prefix='u1-wheel-build-',dir=output.parent) as temp:
        env['TEMP'] = env['TMP'] = temp
        for command in commands:
            result = subprocess.run(command, cwd=output, env=env, capture_output=True,
                                    text=True, timeout=120)
            outputs.append(dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
            if result.returncode:
                (output/'ASSEMBLY_FAILURE.json').write_text(json.dumps(outputs,indent=2),encoding='utf-8')
                raise ValueError('OFFLINE_DEPENDENCY_ASSEMBLY_FAILED')
    manifest = dict(schema='rokt.u1-assembled-runtime.v1',
                    cpython_archive_sha256=cpython_lock['sha256'],
                    wheel_lock=wheel_lock, python=original['python'],
                    files={p.relative_to(output).as_posix():sha(p.read_bytes())
                           for p in sorted(output.rglob('*')) if p.is_file()},
                    validation=outputs, browsers_bundled=False,
                    business_import_closure_verified=False, bootstrap_integrated=False,
                    production_ready=False, allow_install=False, allow_dispatch=False,
                    allow_cancel_dispatch=False, smtp_enabled=False)
    (output/'ASSEMBLED_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    write_runtime_content_manifest(output,original['python'])
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('archive','cpython-lock','wheel-lock','wheelhouse','output'):
        p.add_argument('--'+field,required=True)
    a = p.parse_args()
    m = assemble(a.archive,json.loads(Path(a.cpython_lock).read_text(encoding='utf-8')),
                 json.loads(Path(a.wheel_lock).read_text(encoding='utf-8')),a.wheelhouse,a.output)
    print(json.dumps(dict(files=len(m['files']),validation=m['validation'],production_ready=False)))
