"""Standalone pinned service bootstrap / 独立固定版本服务引导器.

No scheduler, writer backend or collection. Trusted ACL remains a release gate.
"""
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys


def read(path,limit):
    p=Path(path)
    if not p.is_absolute():raise ValueError('ABSOLUTE_PATH_REQUIRED')
    for x in (p,*p.parents):
        if x.is_symlink() or x.stat().st_file_attributes & 0x400:raise ValueError('REPARSE_PATH')
    if p.stat().st_nlink!=1:raise ValueError('HARDLINK_FILE')
    with p.open('rb') as f:raw=f.read(limit+1)
    if len(raw)>limit:raise ValueError('READ_LIMIT')
    return raw


def resolve_release(root):
    root=Path(root)
    transactions=root/'transactions'
    if transactions.exists() or transactions.is_symlink():
        if transactions.is_symlink() or transactions.stat().st_file_attributes & 0x400:
            raise ValueError('REPARSE_PATH')
        if not transactions.is_dir() or any(transactions.glob('*.pending.json')):
            raise ValueError('STOP_AND_PRESERVE_PENDING_PUBLICATION')
    pointer=json.loads(read(root/'active.json',4096))
    if (set(pointer)!={'schema','inventory_id','version'} or pointer['schema']!='rokt.release-store.v1' or
        pointer['inventory_id']!='1784775229336' or not re.fullmatch('[0-9a-f]{64}',pointer['version'] or '')):
        raise ValueError('ACTIVE_RELEASE_REQUIRED')
    folder=root/'versions'/pointer['version'];raw=read(folder/'manifest.json',131072)
    if hashlib.sha256(raw).hexdigest()!=pointer['version']:raise ValueError('MANIFEST_HASH')
    m=json.loads(raw)
    if (set(m)!={'schema','inventory_id','source_commit','files'} or m['schema']!='rokt.release-store.v1' or
        m['inventory_id']!='1784775229336' or not re.fullmatch('[0-9a-f]{40}',m['source_commit']) or
        type(m['files']) is not dict or not 1<=len(m['files'])<=512):raise ValueError('MANIFEST_SCHEMA')
    seen=set();total=0
    reserved={'CON','PRN','AUX','NUL'}|{f'{p}{i}' for p in ('COM','LPT') for i in range(1,10)}
    for name,digest in m['files'].items():
        if (type(name) is not str or not re.fullmatch('[A-Za-z0-9_./-]+',name) or
            any(x in ('','.','..') or x.endswith('.') or x.split('.')[0].upper() in reserved for x in name.split('/')) or
            not re.fullmatch('[0-9a-f]{64}',digest)):raise ValueError('ARTIFACT_PATH')
        lower=name.casefold()
        if any(lower==x or lower.startswith(x+'/') or x.startswith(lower+'/') for x in seen):raise ValueError('PATH_COLLISION')
        seen.add(lower);data=read(folder/'payload'/name,128*1024*1024);total+=len(data)
        if total>128*1024*1024 or hashlib.sha256(data).hexdigest()!=digest:raise ValueError('ARTIFACT_HASH')
    required={'python/autonomy/u1_host_runtime.py','python/autonomy/host_readonly_http.py','python/autonomy/release_store.py'}
    if not required<=set(m['files']):raise ValueError('HOST_MISSING')
    # Reject unmanifested importable files before putting this directory on sys.path.
    actual=set()
    for p in folder.rglob('*'):
        if p.is_symlink() or p.stat().st_file_attributes & 0x400:raise ValueError('REPARSE_PATH')
        if p.is_file():actual.add(p.relative_to(folder).as_posix())
    if actual!={'manifest.json'}|{'payload/'+x for x in m['files']}:raise ValueError('UNMANAGED_FILES')
    return folder/'payload/python'


def main(config):
    c=json.loads(read(config,8192))
    keys={'schema','inventory_id','release_root','state_root','token_file','credential_expires_at','snapshot','snapshot_sha256','allow_dispatch','allow_cancel_dispatch','smtp_enabled'}
    if (set(c) not in (keys,keys|{'event_runtime'}) or c['schema']!='rokt.u1-python-runtime.v1' or c['inventory_id']!='1784775229336' or
        any(c[k] is not False for k in ('allow_dispatch','allow_cancel_dispatch','smtp_enabled')) or
        type(c['credential_expires_at']) is not int):raise ValueError('RUNTIME_CONFIG_REJECTED')
    folder=resolve_release(c['release_root']);sys.path.insert(0,str(folder))
    sys.argv=['autonomy.u1_host_runtime','--release-root',c['release_root'],'--state-root',c['state_root'],
              '--token-file',c['token_file'],'--credential-expires-at',str(c['credential_expires_at']),
              '--snapshot',c['snapshot'],'--snapshot-sha256',c['snapshot_sha256']]
    if 'event_runtime' in c:
        if type(c['event_runtime']) is not str or not Path(c['event_runtime']).is_absolute():
            raise ValueError('EVENT_RUNTIME_REQUIRED')
        sys.argv+=['--event-runtime',c['event_runtime']]
    runpy.run_module('autonomy.u1_host_runtime',run_name='__main__')


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('EXACT_RUNTIME_CONFIG_REQUIRED')
    main(sys.argv[1])
