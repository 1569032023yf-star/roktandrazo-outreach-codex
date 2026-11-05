"""最终固定包离线验证 / Final fixed archive offline verification."""
import json,subprocess,sys,datetime,time
from pathlib import Path
root=Path.cwd();e=Path(__file__).parent;package=root.parent/'u1-delivery-publisher-11bf1f9';build=json.loads((package/'BUILD.json').read_text(encoding='utf-8'))
assert build['source_commit']=='11bf1f9da4c74d1653f3f491a8312b536992eff6'
(e/'FINAL_BUILD.json').write_bytes((package/'BUILD.json').read_bytes())
deadline=datetime.datetime.fromisoformat('2026-11-05T10:20:30+08:00');remaining=(deadline-datetime.datetime.now().astimezone()).total_seconds();timeout=min(900,int(remaining-180))
if timeout<120:raise SystemExit('NO_VERIFICATION_BUDGET_PRESERVE_PACKAGE')
report=e/'FINAL_EXTRACTED_REPORT.json';command=[sys.executable,'-X','utf8','-B','-m','tools.verify_u1_delivery','--archive',str(package/'install.zip'),'--archive-sha256',build['artifacts']['install.zip'],'--manifest-sha256',build['manifest_sha256'],'--source-commit',build['source_commit'],'--output',str(root.parent/'u1-publisher-extracted-11bf1f9'),'--report',str(report)]
start=time.monotonic()
with (e/'FINAL_EXTRACTED_OUTPUT.txt').open('x',encoding='utf-8') as output:
 try:
  result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,timeout=timeout);termination=dict(returncode=result.returncode,timeout_seconds=timeout,outcome='TERMINAL')
 except subprocess.TimeoutExpired:
  termination=dict(returncode=None,timeout_seconds=timeout,outcome='UNKNOWN_TIMEOUT')
  if report.exists():
   s=json.loads(report.read_text(encoding='utf-8'));s.update(outcome='UNKNOWN',parent_driver_timeout=True,final_integrity_verified=False);report.write_text(json.dumps(s,indent=2)+'\n',encoding='utf-8')
termination['elapsed_seconds']=round(time.monotonic()-start,3)
(e/'FINAL_VERIFY_TERMINATION.json').write_text(json.dumps(termination,indent=2)+'\n',encoding='utf-8');print(json.dumps(termination))
