"""Rollback archive parity only / 回滚归档对应核验，不执行回滚或安装。"""
import argparse
import hashlib
from pathlib import Path

from autonomy.release_store import ReleaseStore,ordinary
from tools.verify_u1_runtime_host import extract_checked


def verify_parity(install,manifest_sha256,source_commit,rollback):
    install=Path(install);rollback=Path(rollback)
    manifest=ReleaseStore(install)._verify(install,manifest_sha256)
    if manifest['source_commit']!=source_commit:raise ValueError('SOURCE_MISMATCH')
    expected={name:digest for name,digest in manifest['files'].items() if name.startswith('host/')}
    expected['release_store.py']=manifest['files']['python/autonomy/release_store.py']
    # The README is archive-hash-bound; it is not an executable component.
    allowed=set(expected)|{'README.md'}
    for name in manifest['files']:
        if name=='README.md' or name.startswith('dependencies/'):
            target='OFFLINE-DELIVERY.md' if name=='README.md' else name
            expected[target]=manifest['files'][name];allowed.add(target)
    actual=set()
    for p in rollback.rglob('*'):
        ordinary(p)
        if p.is_file():
            if p.stat().st_nlink!=1:raise ValueError('HARDLINK_REJECTED')
            actual.add(p.relative_to(rollback).as_posix())
    if actual!=allowed:raise ValueError('ROLLBACK_FILE_SET_MISMATCH')
    for name,digest in expected.items():
        h=hashlib.sha256()
        with (rollback/name).open('rb') as f:
            for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
        if h.hexdigest()!=digest:raise ValueError('ROLLBACK_COMPONENT_MISMATCH:'+name)
    return dict(source_commit=source_commit,matched_components=len(expected),
                description_zh='仅验证回滚归档与固定安装清单对应；没有执行安装或回滚。',
                description_en='Rollback archive parity against fixed install manifest only; no installation or rollback performed.',
                rollback_archive_parity_verified=True,rollback_verified=False,
                allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)


def verify(args):
    rollback=extract_checked(args.archive,args.archive_sha256,args.output)
    return verify_parity(args.install,args.manifest_sha256,args.source_commit,rollback)


if __name__=='__main__':
    import json,os
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('archive','archive-sha256','output','install','manifest-sha256','source-commit','report'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    with Path(args.report).open('x',encoding='utf-8') as record:
        state=dict(outcome='RUNNING',source_commit=args.source_commit,archive_sha256=args.archive_sha256,
                   rollback_verified=False,allow_install=False,allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
        def persist():
            record.seek(0);json.dump(state,record,indent=2,ensure_ascii=False)
            record.truncate();record.flush();os.fsync(record.fileno())
        persist()
        try:state.update(verify(args),outcome='VERIFIED')
        except BaseException as exc:
            state.update(outcome='UNKNOWN' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'FAILED',error_type=type(exc).__name__,error=str(exc));persist();raise
        persist()
