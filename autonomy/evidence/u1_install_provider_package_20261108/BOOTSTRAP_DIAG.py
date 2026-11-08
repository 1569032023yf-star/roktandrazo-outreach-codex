
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
 print('STAGE:stage',flush=True)
 store=ReleaseStore(Path(tmp));store.stage(root,sys.argv[2])
 print('STAGE:activate',flush=True)
 store.activate(sys.argv[2],expected_current=None)
 print('STAGE:resolve',flush=True)
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
 print('STAGE:before_hash',flush=True)
 before={str(p.relative_to(Path(tmp))):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(tmp).rglob('*') if p.is_file()}
 output=io.StringIO()
 print('STAGE:host_preflight',flush=True)
 with redirect_stdout(output):bootstrap['main'](str(config),preflight=True)
 report=json.loads(output.getvalue())
 assert report['startup_inputs_verified'] and report['snapshot_schema_verified'] and not report['listener_started'] and not report['production_ready']
 print('STAGE:after_hash',flush=True)
 after={str(p.relative_to(Path(tmp))):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(tmp).rglob('*') if p.is_file()}
 assert before==after,'PREFLIGHT_MUTATED_INPUTS'
 print(json.dumps(dict(packaged_service_bootstrap_integrity=True,
   elapsed_seconds=time.monotonic()-started,fixture_store=True,service_started=False,
   production_installation=False)))
