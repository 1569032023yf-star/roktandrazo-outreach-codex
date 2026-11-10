"""Offline rollback archive parity and isolated pointer exercise; never installs."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import zipfile

from autonomy.release_store import safe_path
from publisher_channel.install_inputs import InstallInputPins


POINTER_PROBE = r'''
import importlib.util,json,pathlib,subprocess,sys
script=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2])
spec=importlib.util.spec_from_file_location('offline_release_store',script)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
store=root/'store';store.mkdir();s=module.ReleaseStore(store)
old=module.build_bundle(root/'old',{'fixture.txt':b'old'},'a'*40)
new=module.build_bundle(root/'new',{'fixture.txt':b'new'},'b'*40)
s.stage(root/'old',old);s.activate(old,expected_current=None)
s.stage(root/'new',new);receipt=s.activate(new,expected_current=old)
result=subprocess.run([sys.executable,'-I','-B',str(script),'--root',str(store),
                       'rollback',receipt['transaction'],'--expected-current',new],
                      cwd=root,capture_output=True,text=True,timeout=20,check=True)
record=json.loads(result.stdout)
assert record['outcome']=='POINTER_COMMITTED' and record['before']==new and record['after']==old
assert s.status()['version']==old
assert (store/'versions'/old/'payload/fixture.txt').read_bytes()==b'old'
print('ISOLATED_POINTER_ROLLBACK_OK')
'''


def verify_rollback(archive, expected, manifest, python, scratch):
    """Check approved ZIP and fixture pointer rollback; not service rollback."""
    if not re.fullmatch('[0-9a-f]{64}',expected or ''):raise ValueError('ROLLBACK_APPROVAL_REQUIRED')
    expected_host={name:digest for name,digest in manifest['files'].items() if name.startswith('host/')}
    script_digest=manifest['files'].get('python/autonomy/release_store.py')
    if not expected_host or not script_digest:raise ValueError('ROLLBACK_MANIFEST_INCOMPLETE')
    archive=Path(archive).absolute()
    with InstallInputPins() as pins:
        pins.add_verified(archive,expected)
        with zipfile.ZipFile(archive) as z:
            rows=z.infolist();names=[];total=0
            if not 1<=len(rows)<=8300:raise ValueError('ROLLBACK_ARCHIVE_COUNT')
            for row in rows:
                name=safe_path(row.filename)
                mode=(row.external_attr>>16)&0o170000
                if (row.orig_filename!=row.filename or '\\' in row.orig_filename or row.is_dir() or
                    mode not in (0,stat.S_IFREG) or row.flag_bits&1 or
                    not 0<=row.file_size<=256*1024*1024):raise ValueError('ROLLBACK_ARCHIVE_ENTRY')
                total+=row.file_size;names.append(tuple(name.casefold().split('/')))
            if total>1024*1024*1024:raise ValueError('ROLLBACK_ARCHIVE_TOTAL')
            names.sort()
            if any(len(a)<=len(b) and a==b[:len(a)] for a,b in zip(names,names[1:])):
                raise ValueError('ROLLBACK_ARCHIVE_COLLISION')
            hosts={row.filename for row in rows if row.filename.startswith('host/')}
            if hosts!=set(expected_host):raise ValueError('ROLLBACK_HOST_SET_MISMATCH')
            if 'release_store.py' not in z.namelist():raise ValueError('ROLLBACK_TOOL_MISSING')
            for row in rows:
                target=expected_host.get(row.filename)
                if row.filename=='release_store.py':target=script_digest
                if target is None:continue
                digest=hashlib.sha256();count=0
                with z.open(row) as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):
                        count+=len(chunk)
                        if count>row.file_size:raise ValueError('ROLLBACK_ARCHIVE_SIZE')
                        digest.update(chunk)
                if count!=row.file_size or digest.hexdigest()!=target:raise ValueError('ROLLBACK_CONTENT_MISMATCH')
            if z.getinfo('release_store.py').file_size>2*1024*1024:raise ValueError('ROLLBACK_TOOL_SIZE')
            tool=z.read('release_store.py')
        pins.revalidate()
        with tempfile.TemporaryDirectory(prefix='u1-rollback-fixture-',dir=scratch) as tmp:
            script=Path(tmp)/'release_store.py';script.write_bytes(tool)
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','PIP_'))}
            result=subprocess.run([str(python),'-I','-B','-c',POINTER_PROBE,str(script),tmp],
                                  cwd=tmp,env=env,capture_output=True,text=True,timeout=45)
            if result.returncode or result.stdout.strip()!='ISOLATED_POINTER_ROLLBACK_OK':
                raise ValueError('ROLLBACK_FIXTURE_FAILED:'+result.stderr[-2000:])
        pins.revalidate()
    return dict(rollback_archive_sha256=expected,rollback_host_files=len(hosts),
                rollback_archive_parity_verified=True,isolated_pointer_rollback_verified=True,
                rollback_verified=False,installation_verified=False,production_ready=False)
