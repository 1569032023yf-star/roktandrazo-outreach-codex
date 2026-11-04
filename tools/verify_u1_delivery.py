"""Read-only extracted application probes / 只读解压应用验证，不安装、不派发。"""
import argparse
import json
import os
from pathlib import Path
import subprocess

from autonomy.release_store import ReleaseStore
from publisher_channel.install_inputs import InstallInputPins, pin_package, pin_python_runtime
from tools.verify_u1_runtime_host import extract_checked


IMPORT_PROBE = r'''
import sys,json,importlib,socket,subprocess
from pathlib import Path
app=Path(sys.argv[1]).resolve(); runtime=Path(sys.executable).resolve().parent
assert sys.flags.isolated and all(Path(p).resolve().is_relative_to(runtime) for p in sys.path)
sys.path.insert(0,str(app))
def deny(*args,**kwargs): raise RuntimeError('NETWORK_FORBIDDEN_OFFLINE_PROBE')
socket.socket.connect=deny; socket.create_connection=deny
names=['autonomy.u1_host_runtime','autonomy.inventory_event_bridge',
       'autonomy.original_inventory_owner','autonomy.process_backend',
       'publisher_channel.install_command','autonomy.windows.u1_bootstrap']
for name in names: importlib.import_module(name)
origins={}
for name,module in list(sys.modules.items()):
 if name.split('.')[0] in ('autonomy','publisher_channel'):
  origin=getattr(module,'__file__',None)
  if origin:
   assert Path(origin).resolve().is_relative_to(app),(name,origin)
   origins[name]=str(Path(origin).resolve().relative_to(app))
child=subprocess.run([sys.executable,'-I','-B','-c',
 'import sys; assert sys.flags.isolated; print("ISOLATED_CHILD_OK")'],
 capture_output=True,text=True,timeout=20,check=True)
print(json.dumps(dict(module_origins=origins,child_stdout=child.stdout)))
'''


def verify(args):
    root=extract_checked(args.archive,args.archive_sha256,args.output)
    manifest=ReleaseStore(root)._verify(root,args.manifest_sha256)
    if manifest['source_commit']!=args.source_commit: raise ValueError('SOURCE_MISMATCH')
    delivery=json.loads((root/'payload/DELIVERY.json').read_text(encoding='utf-8'))
    if (delivery.get('source_commit')!=args.source_commit or
        delivery.get('python_runtime_bundled') is not True or
        any(delivery.get(k) is not False for k in
            ('allow_install','allow_dispatch','allow_cancel_dispatch','smtp_enabled','production_ready'))):
        raise ValueError('DELIVERY_BINDING_OR_GATE')
    host=root/'payload/host'; runtime=host/'runtime/python'; results=[]
    host_digest=manifest['files']['host/manifest.json']
    with InstallInputPins() as pins:
        host_manifest=pin_package(pins,host,host_digest,args.source_commit)
        rows={row['path']:row['sha256'] for row in host_manifest['files']}
        content_digest=rows['runtime/python/U1_RUNTIME_CONTENT.json']
        if content_digest!=delivery['runtime_manifest_sha256']: raise ValueError('RUNTIME_BINDING')
        pin_python_runtime(pins,str(runtime/'U1_RUNTIME_CONTENT.json'),content_digest,str(runtime/'python.exe'))
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PIP_'))}
        commands=[
            [str(runtime/'python.exe'),'-I','-B','-c',IMPORT_PROBE,str(root/'payload/python')],
            [str(runtime/'python.exe'),'-I','-B','-m','pip','--isolated','--disable-pip-version-check','check'],
            [str(host/'service/RoktU1Bridge.exe'),'--validate-runtime',str(runtime/'U1_RUNTIME_CONTENT.json'),content_digest,str(runtime/'python.exe')]]
        for command in commands:
            result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=120)
            results.append(dict(arguments=command[1:],returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
            if result.returncode: raise ValueError('DELIVERY_PROBE_FAILED:'+json.dumps(results))
        pins.revalidate()
    # Recheck after subprocess probes to detect unexpected package writes.
    ReleaseStore(root)._verify(root,args.manifest_sha256)
    return dict(checks=results,manifest_files=len(manifest['files']),offline_entrypoint_imports_verified=True,
                full_business_import_closure=False,bootstrap_arguments_verified=False,
                installation_verified=False,rollback_verified=False,provider_accepted=False)


def verify_with_report(args):
    with Path(args.report).open('x',encoding='utf-8') as record:
        state=dict(source_commit=args.source_commit,archive_sha256=args.archive_sha256,
                   manifest_sha256=args.manifest_sha256,outcome='RUNNING',
                   description_zh='仅离线入口导入、包内子进程和完整性；不证明正式业务、安装或回滚。',
                   description_en='Offline entrypoint imports, packaged subprocess and integrity only; not formal business, installation or rollback acceptance.',
                   allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,
                   production_ready=False)
        def persist():
            record.seek(0);json.dump(state,record,indent=2,ensure_ascii=False)
            record.truncate();record.flush();os.fsync(record.fileno())
        persist()
        try: result=verify(args)
        except BaseException as exc:
            state.update(outcome='UNKNOWN' if isinstance(exc,(subprocess.TimeoutExpired,KeyboardInterrupt,SystemExit)) else 'FAILED',
                         error_type=type(exc).__name__,error=str(exc));persist();raise
        state.update(result,outcome='VERIFIED');persist()
        return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('archive','archive-sha256','manifest-sha256','source-commit','output','report'):
        parser.add_argument('--'+key,required=True)
    print(json.dumps(verify_with_report(parser.parse_args()),ensure_ascii=True))
