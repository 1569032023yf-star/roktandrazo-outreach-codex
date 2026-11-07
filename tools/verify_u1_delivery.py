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
import sys,json,importlib,socket,subprocess,sqlite3,smtplib
from pathlib import Path
app=Path(sys.argv[1]).resolve(); runtime=Path(sys.executable).resolve().parent
assert sys.flags.isolated and all(Path(p).resolve().is_relative_to(runtime) for p in sys.path)
sys.path.insert(0,str(app))
def deny(*args,**kwargs): raise RuntimeError('NETWORK_FORBIDDEN_OFFLINE_PROBE')
socket.socket.connect=deny; socket.create_connection=deny
sqlite3.connect=deny; smtplib.SMTP=deny; smtplib.SMTP_SSL=deny
names=['autonomy.u1_host_runtime','autonomy.inventory_event_bridge',
       'autonomy.original_inventory_owner','autonomy.process_backend',
       'publisher_channel.install_command','autonomy.windows.u1_bootstrap',
       'discovery.providers.google_places','discovery.providers.browser_maps',
       'discovery.providers.serpapi_maps','discovery.providers.contracts',
       'discovery.discovery_service']
business_roots={'bd_db','history_crosscheck','lead_hygiene_gate','outreach_control',
                'retail_city_queue','broad_outreach_gate','email_hygiene','timezone_resolver'}
for name in names: importlib.import_module(name)
origins={}
for name,module in list(sys.modules.items()):
 if name.split('.')[0] in ('autonomy','publisher_channel','discovery') or name in business_roots:
  origin=getattr(module,'__file__',None)
  if origin:
   assert Path(origin).resolve().is_relative_to(app),(name,origin)
   origins[name]=str(Path(origin).resolve().relative_to(app))
assert business_roots <= set(origins), sorted(business_roots-set(origins))
child=subprocess.run([sys.executable,'-I','-B','-c',
 'import sys; assert sys.flags.isolated; print("ISOLATED_CHILD_OK")'],
 capture_output=True,text=True,timeout=20,check=True)
print(json.dumps(dict(module_origins=origins,child_stdout=child.stdout)))
'''


HTTP_PROBE = r'''
import sys,json,tempfile,secrets,time,threading,http.client,socket
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from autonomy.release_store import ReleaseStore,build_bundle,sha
from autonomy.u1_host_runtime import open_host
original_connect=socket.socket.connect
def local_only(self,address):
 if not isinstance(address,tuple) or address[0]!='127.0.0.1':
  raise RuntimeError('EXTERNAL_NETWORK_FORBIDDEN')
 return original_connect(self,address)
socket.socket.connect=local_only
with tempfile.TemporaryDirectory(prefix='u1-offline-http-',dir=sys.argv[2]) as tmp:
 root=Path(tmp);release=root/'release';state=root/'state';release.mkdir();state.mkdir()
 version=build_bundle(root/'fixture',{'fixture.txt':b'offline release fixture'},'a'*40)
 store=ReleaseStore(release);store.stage(root/'fixture',version);store.activate(version,expected_current=None)
 token=secrets.token_hex(32);snapshot=b'offline snapshot fixture'
 with open_host(release,state,token,int(time.time())+60,snapshot,sha(snapshot),port=0) as server:
  worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01});worker.start()
  statuses=[]
  try:
   for headers,expected in [({},401),({'Authorization':'Bearer '+token},200)]:
    client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:
     client.request('GET','/v1/health',headers=headers);reply=client.getresponse()
     assert reply.status==expected,(reply.status,expected)
     reply.read();statuses.append(reply.status)
    finally:client.close()
  finally:server.shutdown();worker.join(10)
  assert not worker.is_alive()
print(json.dumps(dict(local_http_statuses=statuses,fixture_release=True,
 fixture_snapshot=True,formal_provider=False,production_ports_tested=False)))
'''


BOOTSTRAP_PROBE = r'''
import sys,json,tempfile,runpy,socket,sqlite3,smtplib,time
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'payload/python'))
from autonomy.release_store import ReleaseStore

def deny(*args,**kwargs):raise RuntimeError('SIDE_EFFECT_FORBIDDEN_OFFLINE_BOOTSTRAP')
socket.socket.connect=deny;socket.create_connection=deny
real_connect=sqlite3.connect
# Only standalone caller-approved bytes are inspected in an in-memory database.
def memory_only(database,*args,**kwargs):
 if database!=':memory:':return deny()
 return real_connect(database,*args,**kwargs)
sqlite3.connect=memory_only;smtplib.SMTP=deny;smtplib.SMTP_SSL=deny
# Execute the actual packaged service bootstrap definitions, without starting it.
bootstrap=runpy.run_path(str(root/'payload/host/service/u1_bootstrap.py'))
with tempfile.TemporaryDirectory(prefix='b',dir=sys.argv[3]) as tmp:
 store=ReleaseStore(Path(tmp));store.stage(root,sys.argv[2])
 store.activate(sys.argv[2],expected_current=None)
 started=time.monotonic();folder=bootstrap['resolve_release'](Path(tmp))
 assert folder==Path(tmp)/'versions'/sys.argv[2]/'payload/python'
 import hashlib,io
 from contextlib import redirect_stdout
 # Exercise the actual packaged bootstrap -> host argument path; no authority read.
 state=Path(tmp)/'state';state.mkdir()
 token=Path(tmp)/'token';token.write_bytes(b'a'*64)
 from autonomy.cancellation_recovery import SCHEMA,HANDOFF_SCHEMA
 from contextlib import closing
 snapshot=Path(tmp)/'snapshot'
 with closing(sqlite3.connect(':memory:')) as db:
  db.execute(SCHEMA);db.execute(HANDOFF_SCHEMA);db.execute('PRAGMA user_version=1');db.commit()
  snapshot.write_bytes(db.serialize())
 config=Path(tmp)/'runtime.json'
 config.write_text(json.dumps(dict(schema='rokt.u1-python-runtime.v2',inventory_id='1784775229336',
  release_root=tmp,state_root=str(state),token_file=str(token),token_sha256=hashlib.sha256(token.read_bytes()).hexdigest(),
  credential_expires_at=int(time.time())+300,snapshot=str(snapshot),snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
  allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)),encoding='utf-8')
 before={str(p.relative_to(Path(tmp))):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(tmp).rglob('*') if p.is_file()}
 output=io.StringIO()
 with redirect_stdout(output):bootstrap['main'](str(config),preflight=True)
 report=json.loads(output.getvalue())
 assert report['startup_inputs_verified'] and report['snapshot_schema_verified'] and not report['listener_started'] and not report['production_ready']
 after={str(p.relative_to(Path(tmp))):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(tmp).rglob('*') if p.is_file()}
 assert before==after,'PREFLIGHT_MUTATED_INPUTS'
 print(json.dumps(dict(packaged_service_bootstrap_integrity=True,
   elapsed_seconds=time.monotonic()-started,fixture_store=True,service_started=False,
   production_installation=False)))
'''


def verify(args, progress=None):
    progress=progress or (lambda value:None)
    progress(dict(stage='extract_archive',outcome='RUNNING'))
    root=extract_checked(args.archive,args.archive_sha256,args.output)
    progress(dict(stage='initial_integrity',outcome='RUNNING'))
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
        progress(dict(stage='pin_host_and_runtime',outcome='RUNNING'))
        host_manifest=pin_package(pins,host,host_digest,args.source_commit)
        rows={row['path']:row['sha256'] for row in host_manifest['files']}
        content_digest=rows['runtime/python/U1_RUNTIME_CONTENT.json']
        if content_digest!=delivery['runtime_manifest_sha256']: raise ValueError('RUNTIME_BINDING')
        pin_python_runtime(pins,str(runtime/'U1_RUNTIME_CONTENT.json'),content_digest,str(runtime/'python.exe'))
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PIP_'))}
        commands=[
            [str(runtime/'python.exe'),'-I','-B','-c',IMPORT_PROBE,str(root/'payload/python')],
            [str(runtime/'python.exe'),'-I','-B','-m','pip','--isolated','--disable-pip-version-check','check'],
            [str(host/'service/RoktU1Bridge.exe'),'--validate-runtime',str(runtime/'U1_RUNTIME_CONTENT.json'),content_digest,str(runtime/'python.exe')],
            [str(runtime/'python.exe'),'-I','-B','-c',HTTP_PROBE,str(root/'payload/python'),str(root.parent)],
            [str(runtime/'python.exe'),'-I','-B','-c',BOOTSTRAP_PROBE,str(root),args.manifest_sha256,str(root.parent.parent)]]
        for command in commands:
            progress(dict(arguments=command[1:],outcome='RUNNING'))
            try:
                result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=120)
            except BaseException as exc:
                progress(dict(arguments=command[1:],outcome='UNKNOWN',error_type=type(exc).__name__,error=str(exc)))
                raise
            item=dict(arguments=command[1:],returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
                      outcome='PASSED' if result.returncode==0 else 'FAILED')
            results.append(item);progress(item)
            if result.returncode: raise ValueError('DELIVERY_PROBE_FAILED:'+json.dumps(results))
        progress(dict(stage='revalidate_input_pins',outcome='RUNNING'))
        pins.revalidate()
    # Recheck after subprocess probes to detect unexpected package writes.
    progress(dict(stage='final_integrity',outcome='RUNNING'))
    ReleaseStore(root)._verify(root,args.manifest_sha256)
    return dict(checks=results,manifest_files=len(manifest['files']),offline_entrypoint_imports_verified=True,
                discovery_business_imports_verified=True,
                packaged_service_bootstrap_integrity_verified=True,
                loopback_http_with_fixtures_verified=True,production_ports_verified=False,
                full_business_import_closure=False,bootstrap_arguments_verified=True,
                packaged_startup_preflight_verified=True,
                installation_verified=False,rollback_verified=False,provider_accepted=False)


def verify_with_report(args):
    with Path(args.report).open('x',encoding='utf-8') as record:
        state=dict(source_commit=args.source_commit,archive_sha256=args.archive_sha256,
                   manifest_sha256=args.manifest_sha256,outcome='RUNNING',
                   description_zh='仅离线入口导入、包内子进程和完整性；不证明正式业务、安装或回滚。',
                   description_en='Offline entrypoint imports, packaged subprocess and integrity only; not formal business, installation or rollback acceptance.',
                   allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,
                   production_ready=False,checks=[],active_check=None)
        def persist():
            record.seek(0);json.dump(state,record,indent=2,ensure_ascii=False)
            record.truncate();record.flush();os.fsync(record.fileno())
        persist()
        def progress(item):
            if item['outcome']=='RUNNING':state['active_check']=item
            else:
                state['checks'].append(item);state['active_check']=None
            persist()
        try: result=verify(args,progress=progress)
        except BaseException as exc:
            state.update(outcome='UNKNOWN' if isinstance(exc,(subprocess.TimeoutExpired,KeyboardInterrupt,SystemExit)) else 'FAILED',
                         error_type=type(exc).__name__,error=str(exc));persist();raise
        state.update(result,outcome='VERIFIED',active_check=None);persist()
        return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('archive','archive-sha256','manifest-sha256','source-commit','output','report'):
        parser.add_argument('--'+key,required=True)
    print(json.dumps(verify_with_report(parser.parse_args()),ensure_ascii=True))
