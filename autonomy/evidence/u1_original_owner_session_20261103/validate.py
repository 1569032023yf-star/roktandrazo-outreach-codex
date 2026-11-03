"""固定候选离线验证 / Fixed-candidate offline validation; never deployment."""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SOURCE='68788653c848659c63f85021075fedee4aca5b13'
BASELINE='4b0353cbc4a5c69998fdd597d2bb884f7f5da8d0'


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def targeted():
    previous=json.loads((ROOT/'autonomy/evidence/u1_original_owner_20261103/fixed-validation/TARGETED.json').read_text(encoding='utf-8'))
    authority=['test_inventory_maintenance','test_publisher_maintenance','test_publisher_install_maintenance','test_original_inventory_owner']
    groups=dict(host=[m for m in previous['modules'] if m not in authority],authority=authority)
    started=time.monotonic();results=[]
    for group,modules in groups.items():
        folder=HERE/'validation'/group;folder.mkdir(parents=True,exist_ok=True)
        code='''import json,sys,unittest
from pathlib import Path
root,destination,modules=sys.argv[1:]
sys.path.insert(0,root)
suite=unittest.defaultTestLoader.loadTestsFromNames(json.loads(modules))
result=unittest.TextTestRunner(verbosity=2).run(suite)
data=dict(tests_run=result.testsRun,failures=[t.id() for t,_ in result.failures],errors=[t.id() for t,_ in result.errors],skips=[t.id() for t,_ in result.skipped],passed=result.wasSuccessful())
Path(destination).write_text(json.dumps(data,indent=2),encoding='utf-8')
sys.exit(0 if data['passed'] else 1)
'''
        with (folder/'OUTPUT.txt').open('w',encoding='utf-8') as output:
            run=subprocess.run([sys.executable,'-B','-c',code,str(ROOT),str(folder/'RESULT.json'),json.dumps(modules)],
                cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,timeout=900)
        value=json.loads((folder/'RESULT.json').read_text(encoding='utf-8'))
        value.update(group=group,exit_code=run.returncode);results.append(value)
        print(group,value['tests_run'],value['passed'],flush=True)
    result=dict(source_commit=SOURCE,modules=[m for names in groups.values() for m in names],
        tests_run=sum(v['tests_run'] for v in results),passed=all(v['passed'] for v in results),
        failures=sum((v['failures'] for v in results),[]),errors=sum((v['errors'] for v in results),[]),
        skips=sum((v['skips'] for v in results),[]),groups=results,seconds=round(time.monotonic()-started,3),
        allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
    save(HERE/'validation/TARGETED.json',result)


def compare():
    root=Path(tempfile.mkdtemp(prefix='u1-original-session-compare-'))
    save(HERE/'comparison/ROOT.json',dict(root=str(root),baseline_commit=BASELINE,candidate_commit=SOURCE))
    for label,commit in (('baseline',BASELINE),('candidate',SOURCE)):
        target=root/label;target.mkdir()
        raw=subprocess.check_output(['git','archive','--format=zip',commit],cwd=ROOT)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:archive.extractall(target)
    def run(label):
        dest=HERE/'comparison'/label;dest.mkdir(parents=True)
        with (dest/'CONSOLE.txt').open('w',encoding='utf-8') as output:
            process=subprocess.run([sys.executable,'-B','tools/run_comparable_suite.py',str(dest)],
                cwd=root/label,stdout=output,stderr=subprocess.STDOUT,timeout=900)
        result=json.loads((dest/'result.json').read_text(encoding='utf-8'))
        result['exit_code']=process.returncode
        return label,result
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results=dict(executor.map(run,('baseline','candidate')))
    b=results['baseline'];c=results['candidate']
    result=dict(baseline_commit=BASELINE,candidate_commit=SOURCE,complete=True,
        baseline_run=b['run'],candidate_run=c['run'],baseline_failures=len(b['failures']),candidate_failures=len(c['failures']),
        baseline_errors=len(b['errors']),candidate_errors=len(c['errors']),
        failure_ids_identical=sorted(b['failures'])==sorted(c['failures']),
        error_ids_identical=sorted(b['errors'])==sorted(c['errors']),
        all_green=not any(b[k] or c[k] for k in ('failures','errors')))
    result['no_new_regression']=result['failure_ids_identical'] and result['error_ids_identical'] and b['run']==c['run']
    save(HERE/'comparison/COMPARISON.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=SOURCE:
        raise ValueError('FIXED_SOURCE_REQUIRED')
    {'targeted':targeted,'compare':compare}[sys.argv[1]]()
