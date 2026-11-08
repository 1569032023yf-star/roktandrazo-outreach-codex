"""Offline packaged Provider preflight; no requests or production state."""
import sys,subprocess,json
from pathlib import Path
from tools.verify_u1_delivery import BOOTSTRAP_PROBE
root=Path(sys.argv[1]);manifest=sys.argv[2]
probe=BOOTSTRAP_PROBE.replace(" config=Path(tmp)/'runtime.json'", " provider=Path(tmp)/'provider.json'\n provider.write_text(json.dumps(dict(schema='rokt.provider-environment.v1',environment={'WORKBUDDY_DISCOVERY_PROVIDER':'google_places'})),encoding='utf-8')\n config=Path(tmp)/'runtime.json'")
probe=probe.replace("allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)),", "provider_config=str(provider),provider_config_sha256=hashlib.sha256(provider.read_bytes()).hexdigest(),allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)),")
probe=probe.replace(" after={", " assert report['provider_adapter_verified'] and report['provider_name']=='google_places' and not report['provider_configured']\n after={")
python=root/'payload/host/runtime/python/python.exe'
r=subprocess.run([str(python),'-I','-B','-c',probe,str(root),manifest,str(root.parent.parent)],capture_output=True,text=True,timeout=120)
print(json.dumps(dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,external_requests_allowed=False)))
raise SystemExit(r.returncode)

