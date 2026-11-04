"""有界离线包核验 / Bounded offline package verification."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

root = Path.cwd()
evidence = Path(__file__).resolve().parent
package = root.parent / 'u1-delivery-worker-9d5ecb6'
build = json.loads((package/'BUILD.json').read_text())
assert build['source_commit'] == '9d5ecb6b8062f916ac7869957eb6589665ce9113'
(evidence/'BUILD.json').write_bytes((package/'BUILD.json').read_bytes())
deadline = datetime.fromisoformat('2026-11-05T03:36:29+08:00')
remaining = (deadline-datetime.now().astimezone()).total_seconds()
timeout = min(840, int(remaining-180))
if timeout < 120:
    raise SystemExit('NO_VERIFICATION_BUDGET_PRESERVE_PACKAGE')
report = evidence/'EXTRACTED_REPORT.json'
command = [sys.executable,'-X','utf8','-B','-m','tools.verify_u1_delivery',
 '--archive',str(package/'install.zip'),
 '--archive-sha256',build['artifacts']['install.zip'],
 '--manifest-sha256',build['manifest_sha256'],
 '--source-commit',build['source_commit'],
 '--output',str(root.parent/'u1-worker-extracted-9d5ecb6'),
 '--report',str(report)]
with (evidence/'EXTRACTED_OUTPUT.txt').open('w',encoding='utf-8') as output:
    try:
        result=subprocess.run(command,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
        termination={'returncode':result.returncode,'timeout_seconds':timeout,'driver_outcome':'COMPLETE'}
    except subprocess.TimeoutExpired:
        termination={'returncode':None,'timeout_seconds':timeout,'driver_outcome':'UNKNOWN_TIMEOUT'}
        if report.exists():
            state=json.loads(report.read_text())
            state.update(outcome='UNKNOWN',parent_driver_timeout=True,final_integrity_verified=False)
            report.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(evidence/'VERIFICATION_TERMINATION.json').write_text(json.dumps(termination,indent=2)+'\n',encoding='utf-8')
print(json.dumps(termination))
