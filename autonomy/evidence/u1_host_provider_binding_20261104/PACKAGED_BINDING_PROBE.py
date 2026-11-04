"""真实包内配置接线探针，离线替身 / Actual packaged wiring, offline substitutes."""
import json,subprocess
from pathlib import Path
root=Path(r"C:\Users\15690\Documents\ChatGPT\线下\u1-host-extracted-69eb188")
probe=r"""
import sys,json,hashlib,os,tempfile,socket,sqlite3,smtplib
from pathlib import Path
from unittest.mock import patch
app=Path(sys.argv[1]).resolve();sys.path.insert(0,str(app))
def denied(*a,**k):raise RuntimeError('EXTERNAL_EFFECT_FORBIDDEN')
socket.socket.connect=denied;sqlite3.connect=denied;smtplib.SMTP=denied
from autonomy import provider_environment as env
from autonomy.windows import u1_bootstrap as bootstrap
from publisher_channel import install_verifier as verifier
for module in (env,bootstrap,verifier):assert Path(module.__file__).resolve().is_relative_to(app)
before=dict(os.environ)
with tempfile.TemporaryDirectory() as directory:
 root=Path(directory);config=root/'provider.json'
 config.write_text(json.dumps(dict(schema='rokt.provider-environment.v1',environment={'WORKBUDDY_DISCOVERY_PROVIDER':'google_places','GOOGLE_MAPS_API_KEY':'fixture-only'})))
 digest=hashlib.sha256(config.read_bytes()).hexdigest()
 with env.pinned_provider_environment(config,digest):
  try:config.write_bytes(b'changed')
  except OSError:pass
  else:raise AssertionError('WRITE_NOT_BLOCKED')
 assert dict(os.environ)==before
 runtime=root/'runtime.json'
 runtime.write_text(json.dumps(dict(schema='rokt.u1-python-runtime.v2',inventory_id='1784775229336',release_root=directory,state_root=directory,token_file=directory,token_sha256='a'*64,credential_expires_at=12345,snapshot=directory,snapshot_sha256='b'*64,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,provider_config=str(config),provider_config_sha256=digest)))
 captured=[]
 with patch.object(sys,'argv',list(sys.argv)),patch.object(sys,'path',list(sys.path)),patch.object(bootstrap,'resolve_release',return_value=app),patch.object(bootstrap.runpy,'run_module',side_effect=lambda *a,**k:captured.append(list(sys.argv))):bootstrap.main(str(runtime))
 assert captured[0][-4:]==['--provider-config',str(config),'--provider-config-sha256',digest]
 host_manifest=json.loads((app.parent/'host/manifest.json').read_bytes())
 files={row['path']:row['sha256'] for row in host_manifest['files']}
 files.update({'config/runtime.json':'a'*64,'config/supervisor.json':'b'*64})
 assert len(files)>512
 assert len(verifier.InstallVerifier(files,observe=lambda *a:None,confirm_stopped=lambda *a:None).files)==len(files)
print(json.dumps(dict(outcome='PASS',actual_packaged_origins=3,lifetime_write_blocked=True,bootstrap_arguments_forwarded=True,complete_scope_accepted=len(files),credentials_exported=False,fixture_only=True,worker_executed=False,installation_verified=False)))
"""
result=subprocess.run([str(root/'payload/host/runtime/python/python.exe'),'-I','-B','-c',probe,str(root/'payload/python')],capture_output=True,text=True,timeout=120)
record=dict(source_commit='69eb1887800f046b6d860cbefad6bd99f3c35169',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,provider_accepted=False,installation_verified=False)
(Path(__file__).parent/'PACKAGED_BINDING_REPORT.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record));raise SystemExit(result.returncode)
