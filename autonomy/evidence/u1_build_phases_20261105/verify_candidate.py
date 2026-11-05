import subprocess,json,time,datetime,sys
from pathlib import Path
r=Path.cwd();e=Path(__file__).parent;package=r.parent/'u1-delivery-phased-3738993';build=json.loads((package/'BUILD.json').read_text(encoding='utf-8'));(e/'BUILD.json').write_bytes((package/'BUILD.json').read_bytes())
remaining=(datetime.datetime.fromisoformat('2026-11-05T11:24:03+08:00')-datetime.datetime.now().astimezone()).total_seconds();timeout=min(900,int(remaining-150));assert timeout>30,'NO_VERIFICATION_BUDGET'
command=[sys.executable,'-X','utf8','-B','-m','tools.verify_u1_delivery','--archive',str(package/'install.zip'),'--archive-sha256',build['artifacts']['install.zip'],'--manifest-sha256',build['manifest_sha256'],'--source-commit',build['source_commit'],'--output',str(r.parent/'u1-phased-extracted-3738993'),'--report',str(e/'EXTRACTED_REPORT.json')]
start=time.monotonic()
with (e/'VERIFY_OUTPUT.txt').open('x',encoding='utf-8') as out:
 try:
  result=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=timeout);state=dict(outcome='TERMINAL',returncode=result.returncode)
 except subprocess.TimeoutExpired:
  state=dict(outcome='UNKNOWN_TIMEOUT',timeout_seconds=timeout)
  p=e/'EXTRACTED_REPORT.json'
  if p.exists():
   s=json.loads(p.read_text(encoding='utf-8'));s.update(outcome='UNKNOWN',parent_driver_timeout=True,final_integrity_verified=False);p.write_text(json.dumps(s,indent=2),encoding='utf-8')
state['elapsed_seconds']=time.monotonic()-start;(e/'VERIFY_TERMINATION.json').write_text(json.dumps(state,indent=2),encoding='utf-8');print(state)
