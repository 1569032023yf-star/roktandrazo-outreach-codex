"""Build a real local development PE/package. Never production approval or install."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from autonomy.disabled_host_package import RUNTIME_PATHS, build_package, canonical


def build_development(destination, source_commit):
    if os.name!='nt':raise RuntimeError('WINDOWS_BUILD_REQUIRED')
    windows=Path(os.environ['WINDIR'])
    compiler=windows/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    source=Path(__file__).with_name('windows')/'RoktU1Bridge.cs'
    script="$ErrorActionPreference='Stop';$observations=@{};"
    for name,path in RUNTIME_PATHS.items():
        script+="$target=Join-Path $env:WINDIR '"+path+"';$observations['"+name+"']=@{path='"+path+"';version=[Diagnostics.FileVersionInfo]::GetVersionInfo($target).FileVersion};"
    script+="@{schema='rokt.disabled-host-runtime.v1';framework='.NET Framework 4 x64';files=$observations}|ConvertTo-Json -Depth 5 -Compress"
    shell=windows/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(shell),'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],capture_output=True,timeout=20,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    dependencies=json.loads(result.stdout.decode('utf-8-sig'))
    for name,path in RUNTIME_PATHS.items():
        dependencies['files'][name]['sha256']=hashlib.sha256((windows/path).read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='u1-compile-') as temp:
        wrapper=Path(temp)/'RoktU1Bridge.exe'
        subprocess.run([str(compiler),'/nologo','/noconfig','/nostdlib+','/target:exe','/platform:x64']+
                       ['/reference:'+str(windows/RUNTIME_PATHS[k]) for k in ('mscorlib','System','System.Core','System.ServiceProcess','System.Web.Extensions')]+
                       ['/out:'+str(wrapper),str(source)],capture_output=True,timeout=30,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        artifacts={
            'service/RoktU1Bridge.exe':wrapper.read_bytes(),
            'service/RoktU1Bridge.cs':source.read_bytes(),
            'runtime/dependencies.json':canonical(dependencies),
            'runtime/build.json':canonical(dict(schema='rokt.local-development-build.v1',
                compiler_sha256=hashlib.sha256(compiler.read_bytes()).hexdigest(),
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                approval='NOT_APPROVED_LOCAL_DEVELOPMENT_ONLY')),
            'config/host.json':canonical(dict(schema='rokt.disabled-host-config.v1',inventory_id='1784775229336',service_name='RoktU1Bridge',allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,scheduler_created=False))}
    # These computed local hashes are explicitly observations, not production approval.
    result=build_package(destination,artifacts,{k:hashlib.sha256(v).hexdigest() for k,v in artifacts.items()},source_commit=source_commit)
    result.update(approval='NOT_APPROVED_LOCAL_DEVELOPMENT_ONLY',
        source_commit_semantics='CALLER_PIN_MUST_CONTAIN_MATCHING_SOURCE_BYTES',
        wrapper_sha256=hashlib.sha256(artifacts['service/RoktU1Bridge.exe']).hexdigest())
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--source-commit',required=True)
    args=parser.parse_args()
    print(json.dumps(build_development(args.output,args.source_commit),sort_keys=True))
