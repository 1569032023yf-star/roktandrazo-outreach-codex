"""实际包内配置验证，仅fixture / Packaged configuration check, fixtures only."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
root=Path(r"C:\Users\15690\Documents\ChatGPT\线下\u1-config-extracted-ec45401")
evidence=Path(__file__).resolve().parent
probe = r'''import sys,os,json,socket,sqlite3,smtplib
from pathlib import Path
def denied(*a,**k):raise RuntimeError("EXTERNAL_EFFECT_REJECTED")
socket.socket.connect=denied
sqlite3.connect=denied
smtplib.SMTP=denied
app=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(app))
import env_loader,autonomy.provider_environment
assert Path(env_loader.__file__).resolve()==app/'env_loader.py'
assert Path(autonomy.provider_environment.__file__).resolve()==app/'autonomy/provider_environment.py'
assert os.environ['WORKBUDDY_DISCOVERY_PROVIDER']=='google_places'
assert os.environ['GOOGLE_MAPS_API_KEY']=='fixture-only-not-a-credential'
assert 'DISCOVERY_PROVIDER' not in os.environ
assert not (app/'.env').exists()
print(json.dumps(dict(outcome='PASS',application_origins_verified=2,code_root_env_present=False,fixture_only=True,formal_provider_called=False)))
'''
with tempfile.TemporaryDirectory(prefix='u1-config-fixture-') as temp:
 config=Path(temp)/'provider.json'
 config.write_text(json.dumps(dict(schema='rokt.provider-environment.v1',environment={'WORKBUDDY_DISCOVERY_PROVIDER':'google_places','GOOGLE_MAPS_API_KEY':'fixture-only-not-a-credential'})),encoding='utf-8')
 env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PIP_'))}
 env.update(ROKT_U1_PROVIDER_CONFIG=str(config),ROKT_U1_PROVIDER_CONFIG_SHA256=hashlib.sha256(config.read_bytes()).hexdigest(),GOOGLE_MAPS_API_KEY='inherited-rejected',DISCOVERY_PROVIDER='mock')
 result=subprocess.run([str(root/'payload/host/runtime/python/python.exe'),'-I','-B','-c',probe,str(root/'payload/python')],env=env,cwd=root,capture_output=True,text=True,timeout=120)
 report=dict(source_commit='ec45401ad7b0ca016fe6e1b15f58462e929623ff',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,fixture_only=True,host_configuration_propagation_verified=False,provider_accepted=False)
 (evidence/'PACKAGED_CONFIG_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report))
 raise SystemExit(result.returncode)
