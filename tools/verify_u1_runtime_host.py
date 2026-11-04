"""Verify extracted runtime candidate / 验证解压候选，禁止安装和外部请求。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from autonomy.release_store import ordinary,safe_path
from publisher_channel.install_inputs import InstallInputPins,pin_package,pin_python_runtime


def extract_checked(archive,expected,output):
    if not re.fullmatch('[0-9a-f]{64}',expected or ''):raise ValueError('ARCHIVE_APPROVAL_REQUIRED')
    archive=ordinary(archive);output=ordinary(output)
    if output.exists():raise ValueError('NEW_EXTRACTION_REQUIRED')
    digest=hashlib.sha256()
    with archive.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    if digest.hexdigest()!=expected:raise ValueError('ARCHIVE_HASH_MISMATCH')
    with zipfile.ZipFile(archive) as z:
        rows=z.infolist();seen=set();total=0
        if not 1<=len(rows)<=8300:raise ValueError('ARCHIVE_COUNT')
        for row in rows:
            name=safe_path(row.filename);lower=name.casefold()
            if (row.orig_filename!=row.filename or '\\' in row.orig_filename or row.is_dir() or
                (row.external_attr>>16)&0o170000==0o120000 or row.flag_bits&1 or
                not 0<=row.file_size<=256*1024*1024 or
                any(lower==x or lower.startswith(x+'/') or x.startswith(lower+'/') for x in seen)):
                raise ValueError('ARCHIVE_ENTRY')
            seen.add(lower);total+=row.file_size
        if total>1024*1024*1024:raise ValueError('ARCHIVE_TOTAL')
        output.mkdir()
        for row in rows:
            target=output/row.filename;target.parent.mkdir(parents=True,exist_ok=True)
            count=0
            with z.open(row) as source,target.open('xb') as dest:
                for chunk in iter(lambda:source.read(1024*1024),b''):
                    count+=len(chunk)
                    if count>row.file_size:raise ValueError('ARCHIVE_SIZE')
                    dest.write(chunk)
            if count!=row.file_size:raise ValueError('ARCHIVE_SIZE')
    return output


def verify(archive,archive_sha256,manifest_sha256,source_commit,output):
    root=extract_checked(archive,archive_sha256,output)
    results=[]
    with InstallInputPins() as pins:
        manifest=pin_package(pins,root,manifest_sha256,source_commit)
        if manifest['schema']!='rokt.disabled-host-package.v2':raise ValueError('HOST_V2_REQUIRED')
        rows={row['path']:row['sha256'] for row in manifest['files']}
        runtime=root/'runtime/python'
        content=pin_python_runtime(pins,str(runtime/'U1_RUNTIME_CONTENT.json'),
                                   rows['runtime/python/U1_RUNTIME_CONTENT.json'],str(runtime/'python.exe'))
        expected={'runtime/python/'+n:d for n,d in content['files'].items()}
        if any(rows.get(n)!=d for n,d in expected.items()):raise ValueError('HOST_RUNTIME_CONTENT_MISMATCH')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PIP_'))}
        script=('import sys,json,sqlite3,ssl,ctypes,multiprocessing,zoneinfo;'
                'import dns.resolver,httpx,playwright.sync_api,tzdata,greenlet;'
                'from pathlib import Path;'
                'root=Path(sys.executable).resolve().parent;'
                'assert all(Path(p).resolve().is_relative_to(root) for p in sys.path);'
                'print(json.dumps(dict(python=sys.version,executable=sys.executable,isolated=sys.flags.isolated)))')
        commands=[[str(runtime/'python.exe'),'-I','-B','-c',script],
                  [str(runtime/'python.exe'),'-I','-B','-m','pip','--isolated','--disable-pip-version-check','check'],
                  [str(root/'service/RoktU1Bridge.exe'),'--validate-runtime',str(runtime/'U1_RUNTIME_CONTENT.json'),
                   rows['runtime/python/U1_RUNTIME_CONTENT.json'],str(runtime/'python.exe')]]
        for command in commands:
            result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=120)
            results.append(dict(command=command[1:],returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
            if result.returncode:raise ValueError('EXTRACTED_RUNTIME_PROBE_FAILED:'+json.dumps(results))
        pins.revalidate()
    report=dict(source_commit=source_commit,manifest_sha256=manifest_sha256,archive_sha256=archive_sha256,
                description_zh='仅验证解压后的运行时；未验证完整业务依赖闭包、应用发布或真实安装。',
                description_en='Extracted runtime checks only; complete business dependency closure, application release and real installation are unverified.',
                checks=results,extracted_runtime_verified=True,full_business_import_closure=False,
                application_release_verified=False,installation_verified=False,production_ready=False,
                allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('archive','archive-sha256','manifest-sha256','source-commit','output','report'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    result=verify(args.archive,args.archive_sha256,args.manifest_sha256,args.source_commit,args.output)
    with Path(args.report).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(extracted_runtime_verified=True,production_ready=False)))
