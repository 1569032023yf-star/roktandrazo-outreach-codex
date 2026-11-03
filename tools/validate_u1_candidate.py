"""Fixed-source isolated U1 validation / 固定源码隔离验证。"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parent.parent
MODULES=('test_windows_acl_transaction','test_disabled_host_package','test_install_journal',
 'test_install_contract','test_independent_install_plan','test_u1_provision','test_u1_manifest_closure',
 'test_u1_host_runtime','test_host_remediation','test_host_preparation','test_release_store',
 'test_process_backend','autonomy.test_process_job','test_single_slot_adapter','test_host_readonly_http','test_host_file_transaction',
 'test_host_install_transaction','test_inventory_event_bridge','test_maintenance_control','test_inventory_maintenance',
 'test_publisher_maintenance','test_publisher_install_maintenance')
GROUPS={'host':MODULES[:-3], 'authority':MODULES[-3:]}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--baseline');p.add_argument('--group',choices=tuple(GROUPS));a=p.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    sys.path.insert(0,str(ROOT))
    if not a.baseline:
        if not a.group:
            # bd_db installs process-wide development guards. Never remove or
            # relax them for host/ACL/HTTP fixtures: use distinct test processes.
            start=time.monotonic();results=[]
            for group in GROUPS:
                folder=out/group
                child=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),
                                      '--output',str(folder),'--group',group],cwd=ROOT,
                                     capture_output=True,text=True,timeout=600)
                result=json.loads((folder/'TARGETED.json').read_text(encoding='utf-8'))
                result['returncode']=child.returncode
                results.append(result)
            value=dict(source_commit=commit,modules=MODULES,tests_run=sum(r['tests_run'] for r in results),
                       failures=[x for r in results for x in r['failures']],errors=[x for r in results for x in r['errors']],
                       skips=[x for r in results for x in r['skips']],seconds=round(time.monotonic()-start,3),
                       passed=all(r['passed'] and r['source_commit']==commit and r['returncode']==0 for r in results),
                       isolation_groups=list(GROUPS),allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False)
            (out/'TARGETED.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
            (out/'TARGETED_OUTPUT.txt').write_text('\n'.join((out/g/'TARGETED_OUTPUT.txt').read_text(encoding='utf-8') for g in GROUPS),encoding='utf-8')
            print(json.dumps(value));return 0 if value['passed'] else 1
        stream=io.StringIO();start=time.monotonic()
        with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
            suite=unittest.defaultTestLoader.loadTestsFromNames(GROUPS[a.group])
            r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        (out/'TARGETED_OUTPUT.txt').write_text(stream.getvalue(),encoding='utf-8')
        value=dict(source_commit=commit,modules=GROUPS[a.group],tests_run=r.testsRun,failures=[t.id() for t,_ in r.failures],errors=[t.id() for t,_ in r.errors],skips=[t.id() for t,_ in r.skipped],seconds=round(time.monotonic()-start,3),passed=r.wasSuccessful(),allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False)
        (out/'TARGETED.json').write_text(json.dumps(value,indent=2),encoding='utf-8');print(json.dumps(value));return 0 if r.wasSuccessful() else 1
    baseline=subprocess.check_output(['git','rev-parse',a.baseline+'^{commit}'],cwd=ROOT,text=True).strip()
    work=Path(tempfile.mkdtemp(prefix='u1-compare-'));processes=[];results={}
    for label,sha in (('baseline',baseline),('candidate',commit)):
        folder=work/label;folder.mkdir()
        archive=work/(label+'.tar')
        with archive.open('wb') as f:subprocess.run(['git','archive',sha],cwd=ROOT,stdout=f,check=True)
        import tarfile
        with tarfile.open(archive) as t:t.extractall(folder,filter='data')
        (folder/'.development-copy').write_text('Offline regression only / 仅离线回归\n',encoding='utf-8')
        log=(out/(label+'-console.txt')).open('w',encoding='utf-8')
        child=subprocess.Popen([sys.executable,'-B','tools/run_comparable_suite.py','comparison-result'],cwd=folder,stdout=log,stderr=subprocess.STDOUT)
        processes.append((label,sha,folder,child,log))
    for label,sha,folder,child,log in processes:
        try:code=child.wait(timeout=600)
        except subprocess.TimeoutExpired:child.kill();child.wait();code='TIMEOUT'
        log.close();path=folder/'comparison-result/result.json'
        if path.exists():
            value=json.loads(path.read_text(encoding='utf-8'));value['source_commit']=sha;value['returncode']=code
            (out/(label.upper()+'_REGRESSION.json')).write_text(json.dumps(value,indent=2),encoding='utf-8');results[label]=value
    comparison=dict(baseline_commit=baseline,candidate_commit=commit,isolated_root=str(work),complete=set(results)=={'baseline','candidate'})
    if comparison['complete']:
        b,c=results['baseline'],results['candidate']
        comparison.update(baseline_run=b['run'],candidate_run=c['run'],baseline_failures=len(b['failures']),candidate_failures=len(c['failures']),baseline_errors=len(b['errors']),candidate_errors=len(c['errors']),failure_ids_identical=sorted(b['failures'])==sorted(c['failures']),error_ids_identical=sorted(b['errors'])==sorted(c['errors']),all_green=not any(c[k] for k in ('failures','errors')))
        comparison['no_new_regression']=not(set(c['failures'])-set(b['failures']) or set(c['errors'])-set(b['errors']))
    (out/'COMPARISON.json').write_text(json.dumps(comparison,indent=2),encoding='utf-8');print(json.dumps(comparison));return 0 if comparison.get('no_new_regression') else 1


if __name__=='__main__':sys.exit(main())
