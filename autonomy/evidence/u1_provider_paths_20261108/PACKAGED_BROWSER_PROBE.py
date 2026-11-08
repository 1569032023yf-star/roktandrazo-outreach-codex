"""Run actual packaged bootstrap with absolute browser_maps file configuration."""
import sys,subprocess,json,os
from pathlib import Path
from tools.verify_u1_delivery import BOOTSTRAP_PROBE
root=Path(sys.argv[1]);manifest=sys.argv[2]
probe=BOOTSTRAP_PROBE.replace(" config=Path(tmp)/'runtime.json'", " provider=Path(tmp)/'provider.json'\n cache=Path(tmp)/'missing-cache';data=Path(tmp)/'missing.json'\n provider.write_text(json.dumps(dict(schema='rokt.provider-environment.v1',environment={'WORKBUDDY_DISCOVERY_PROVIDER':'browser_maps','BROWSER_MAPS_CACHE_DIR':str(cache),'BROWSER_MAPS_JSON_FILE':str(data),'BROWSER_MAPS_MODE':'file'})),encoding='utf-8')\n config=Path(tmp)/'runtime.json'")
probe=probe.replace("allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)),", "provider_config=str(provider),provider_config_sha256=hashlib.sha256(provider.read_bytes()).hexdigest(),allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)),")
probe=probe.replace(" after={", " assert report['provider_adapter_verified'] and report['provider_name']=='browser_maps'\n assert not cache.exists() and not data.exists()\n after={")
python=root/'payload/host/runtime/python/python.exe'
env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PIP_'))}
r=subprocess.run([str(python),'-I','-B','-c',probe,str(root),manifest,str(root.parent.parent)],cwd=root,env=env,capture_output=True,text=True,timeout=120)
print(json.dumps(dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,external_requests_allowed=False,data_files_created=False if r.returncode==0 else None)))
raise SystemExit(r.returncode)
