"""Explicit Phase 4A execution support / 显式授权的 Phase 4A 部署支持。

Does not run Inventory or resume schedulers / 不运行 Inventory，不恢复调度。
"""
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROD = Path(r'C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach')
COMMIT = 'f67c785031075b8f3a55b5a8ab5b07191dec5b6d'
PACKAGE = ROOT / 'PHASE3_RELEASE_PACKAGE'
FROZEN = json.loads((ROOT/'handoff/phases/FROZEN_SHA256.json').read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper() if path.exists() else 'MISSING'

def git(*args):
    return subprocess.check_output(['git', '-c', 'safe.directory='+ROOT.as_posix(), *args], cwd=ROOT)

def ro(path):
    return sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)

def main():
    mode = sys.argv[1]
    manifest = (ROOT/'PHASE3_FINAL_PATCH_MANIFEST.md').read_bytes()
    assert manifest.replace(b'\r\n', b'\n') == git('show',COMMIT+':PHASE3_FINAL_PATCH_MANIFEST.md').replace(b'\r\n',b'\n')
    entries = re.findall(r'PATH = (.*?)\nACTION = (.*?)\nPRODUCTION_BASELINE_SHA256 = (\w+)\nTARGET_SHA256 = (\w+)', manifest.decode().replace('\r\n','\n'))
    assert len(entries)==6
    for name,action,baseline,target in entries:
        artifact = name+'.patch' if action=='SELECTIVE_PATCH_ONLY' else name
        assert (PACKAGE/artifact).read_bytes() == git('show',COMMIT+':PHASE3_RELEASE_PACKAGE/'+artifact), 'UNAPPROVED_ARTIFACT:'+name
    assert all(sha(PROD/n)==h.upper() for n,h in FROZEN.items()), 'FROZEN_DRIFT'
    if mode == 'prepare':
        actual={n:sha(PROD/n) for n,_,_,_ in entries}
        assert all(actual[n]==b for n,_,b,_ in entries), 'BASELINE_DRIFT:'+json.dumps(actual)
        with ro(PROD/'data/bd_leads.db') as c:
            running=c.execute("SELECT run_id,stage FROM job_runs WHERE status='running' AND stage<>'status'").fetchall()
            assert not running, 'ACTIVE_JOBS:'+repr(running)
        run_id='phase4a-prod-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=ROOT/'_audit_quarantine'/'phase4a'/run_id
        backup.mkdir(parents=True, exist_ok=False)
        (backup/'database').mkdir()
        for n,_,b,_ in entries:
            if b!='MISSING':
                dest=backup/'original_files'/n
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(PROD/n,dest)
                assert sha(dest)==b
        with ro(PROD/'data/bd_leads.db') as source, sqlite3.connect(backup/'database/bd_leads.db') as dest:
            source.backup(dest)
            assert dest.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        record={'run_id':run_id,'backup_root':str(backup),'baseline':actual,'targets':{n:t for n,_,_,t in entries},'frozen':FROZEN,'env_sha256':sha(PROD/'.env'),'database_sha256':sha(backup/'database/bd_leads.db'),'new_files':[n for n,_,b,_ in entries if b=='MISSING'],'rollback_ready':True}
        (backup/'rollback_manifest.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        print(json.dumps(record))
    elif mode=='apply':
        backup=Path(sys.argv[2]).resolve()
        assert backup.is_relative_to(ROOT/'_audit_quarantine'/'phase4a')
        record=json.loads((backup/'rollback_manifest.json').read_text())
        assert sha(backup/'database/bd_leads.db')==record['database_sha256']
        assert sha(PROD/'.env')==record['env_sha256']
        assert all(sha(PROD/n)==b for n,_,b,_ in entries)
        assert (backup/'scheduler_inventory.json').exists(), 'SCHEDULER_INVENTORY_REQUIRED'
        subprocess.run(['git','-c','safe.directory='+PROD.parent.as_posix(),'-c','core.autocrlf=false','apply','--check',str(PACKAGE/'bd_db.py.patch')],cwd=PROD,check=True)
        subprocess.run(['git','-c','safe.directory='+PROD.parent.as_posix(),'-c','core.autocrlf=false','apply',str(PACKAGE/'bd_db.py.patch')],cwd=PROD,check=True)
        for n,action,_,target in entries:
            if action!='SELECTIVE_PATCH_ONLY':
                shutil.copyfile(PACKAGE/n,PROD/n)
            assert sha(PROD/n)==target, 'TARGET_MISMATCH:'+n
        assert all(sha(PROD/n)==h.upper() for n,h in FROZEN.items())
        assert sha(PROD/'.env')==record['env_sha256']
        print('TARGET_HASH_MATCH=6/6; FROZEN_FILES_CHANGED=0; ENV_CHANGED=false')
    else:
        raise ValueError(mode)

if __name__=='__main__':
    main()
