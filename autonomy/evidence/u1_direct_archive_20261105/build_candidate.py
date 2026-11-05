import subprocess,sys,json,time
from pathlib import Path
r=Path.cwd();e=Path(__file__).parent;source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source.startswith('fe51fbd')
command=[sys.executable,'-X','utf8','-B','-m','autonomy.build_u1_delivery','--output',str(r.parent/'u1-delivery-direct-fe51fbd'),'--source-commit',source,'--python-runtime',str(r.parent/'u1-runtime-32f0246'),'--runtime-manifest-sha256','5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e']
start=time.monotonic()
with (e/'BUILD_OUTPUT.txt').open('x',encoding='utf-8') as out:
 try:
  result=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=600);state=dict(outcome='TERMINAL',returncode=result.returncode)
 except subprocess.TimeoutExpired:state=dict(outcome='UNKNOWN_TIMEOUT',timeout_seconds=600)
state.update(source_commit=source,elapsed_seconds=time.monotonic()-start,command=command);(e/'BUILD_TERMINATION.json').write_text(json.dumps(state,indent=2),encoding='utf-8');print(json.dumps(state))
