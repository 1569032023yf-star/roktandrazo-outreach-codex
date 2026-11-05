"""固定新版包构建 / Fixed candidate build; disabled, no installation."""
import subprocess,sys,json,time
from pathlib import Path
root=Path.cwd();e=Path(__file__).parent;package=root.parent/'u1-delivery-publisher-11bf1f9'
command=[sys.executable,'-X','utf8','-B','-m','autonomy.build_u1_delivery','--output',str(package),'--source-commit','11bf1f9da4c74d1653f3f491a8312b536992eff6','--python-runtime',str(root.parent/'u1-runtime-32f0246'),'--runtime-manifest-sha256','5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e']
start=time.monotonic()
with (e/'FINAL_BUILD_OUTPUT.txt').open('x',encoding='utf-8') as out:
 try:
  r=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=900);state=dict(returncode=r.returncode,outcome='TERMINAL',command=command)
 except subprocess.TimeoutExpired:state=dict(outcome='UNKNOWN_TIMEOUT',timeout_seconds=900,command=command)
state['elapsed_seconds']=round(time.monotonic()-start,3)
(e/'FINAL_BUILD_TERMINATION.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8');print(json.dumps(state))
