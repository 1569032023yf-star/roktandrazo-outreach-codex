import subprocess,sys,json
from pathlib import Path
out=Path(__file__).parent
root=Path(json.loads((out/'COMPARE_ROOT.json').read_text(encoding='utf-8'))['root'])
processes=[]
for label in ('baseline','candidate'):
 stream=(out/(label+'-console.txt')).open('w',encoding='utf-8')
 process=subprocess.Popen([sys.executable,'-B','tools/run_comparable_suite.py','comparison-result'],cwd=root/label,stdout=stream,stderr=subprocess.STDOUT)
 processes.append((label,process,stream))
for label,process,stream in processes:
 try: code=process.wait(timeout=600)
 except subprocess.TimeoutExpired:
  process.kill();process.wait();code='TIMEOUT'
 stream.close()
 result=root/label/'comparison-result/result.json'
 if result.exists():(out/(label.upper()+'_REGRESSION.json')).write_bytes(result.read_bytes())
 print(label,code,flush=True)
