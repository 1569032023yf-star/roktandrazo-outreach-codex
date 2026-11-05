import subprocess,sys,json,time,datetime
from pathlib import Path
r=Path.cwd();e=Path(__file__).parent;source=subprocess.check_output(['git','rev-parse','3738993^{commit}'],text=True).strip();phase=sys.argv[1]
command=[sys.executable,'-X','utf8','-B','-m','autonomy.build_u1_delivery','--source-commit',source,'--python-runtime',str(r.parent/'u1-runtime-32f0246'),'--runtime-manifest-sha256','5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e']
prepared=r.parent/'u1-host-phase-3738993'
if phase=='prepare':command+=['--output',str(prepared),'--prepare-only']
elif phase=='archive':
 state=json.loads((prepared/'HOST_INPUT.json').read_text(encoding='utf-8'));assert state['source_commit']==source
 command+=['--output',str(r.parent/'u1-delivery-phased-3738993'),'--prepared-host',state['prepared_host'],'--prepared-host-manifest-sha256',state['manifest_sha256']]
else:raise ValueError('UNKNOWN_PHASE')
remaining=(datetime.datetime.fromisoformat('2026-11-05T11:24:03+08:00')-datetime.datetime.now().astimezone()).total_seconds();timeout=min(900,int(remaining-180));assert timeout>120
start=time.monotonic()
with (e/(phase.upper()+'_OUTPUT.txt')).open('x',encoding='utf-8') as out:
 try:
  result=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=timeout);s=dict(outcome='TERMINAL',returncode=result.returncode)
 except subprocess.TimeoutExpired:s=dict(outcome='UNKNOWN_TIMEOUT',timeout_seconds=timeout)
s.update(source_commit=source,elapsed_seconds=time.monotonic()-start,command=command);(e/(phase.upper()+'_TERMINATION.json')).write_text(json.dumps(s,indent=2),encoding='utf-8');print(json.dumps(s))
