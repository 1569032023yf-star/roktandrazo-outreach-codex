"""Exact owned-file transactions. No SCM, ACL, Inventory or database mutation.

The caller must hold installation exclusion and independently validate the
administrator-controlled audit/code roots. Recovery compensates known bytes;
it never resumes forward publication after an interrupted intent.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def name(value):
    if type(value) is not str or not re.fullmatch(r'(service|runtime|config)/[A-Za-z0-9_./-]+', value):
        raise ValueError('OWNED_PATH_REQUIRED')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {x+str(n) for x in ('COM', 'LPT') for n in range(1, 10)}
    if any(p in ('', '.', '..') or p.endswith('.') or p.casefold().endswith('.u1-new') or p.split('.')[0].upper() in reserved for p in value.split('/')):
        raise ValueError('OWNED_PATH_REQUIRED')
    return value


def ordinary(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.exists() or p.is_symlink():
            s = p.lstat()
            if p.is_symlink() or getattr(s, 'st_file_attributes', 0) & 0x400:
                raise ValueError('REPARSE_REJECTED')
    return path


def read(path):
    p = ordinary(path)
    if not p.exists():
        return None
    s = p.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_size > 256*1024*1024:
        raise ValueError('ORDINARY_FILE_REQUIRED')
    with p.open('rb') as f:
        before = os.fstat(f.fileno())
        raw = f.read(256*1024*1024+1)
        after = os.fstat(f.fileno())
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('FILE_CHANGED')
    if len(raw) > 256*1024*1024:
        raise ValueError('FILE_TOO_LARGE')
    return raw


def fingerprint(raw):
    return 'ABSENT' if raw is None else digest(raw)


class HostFileTransaction:
    """One immutable plan and append-only journal per approved operation.

    Directory ownership is deliberately separate from file ownership: empty
    directories are retained on rollback. Unlisted files are never removed.
    """
    def __init__(self, root, journal, *, fault=lambda phase, item: None):
        self.root = ordinary(root)
        self.journal = ordinary(journal)
        if (not self.root.is_dir() and not self.journal.exists()) or not self.journal.parent.is_dir():
            raise ValueError('PREPROVISIONED_ROOT_REQUIRED')
        self.fault = fault

    def _rows(self):
        raw = read(self.journal)
        if raw is None:
            return []
        if not raw.endswith(b'\n'):
            raise ValueError('STOP_AND_PRESERVE_TORN_JOURNAL')
        rows = [json.loads(line) for line in raw.splitlines()]
        for i, row in enumerate(rows):
            if row.get('sequence') != i or row.get('previous') != (digest(canonical(rows[i-1])) if i else None):
                raise ValueError('STOP_AND_PRESERVE_JOURNAL_CHAIN')
        return rows

    def _append(self, **fields):
        rows = self._rows()
        row = dict(sequence=len(rows), previous=digest(canonical(rows[-1])) if rows else None, **fields)
        ordinary(self.journal)
        with self.journal.open('ab' if rows else 'xb') as f:
            s = os.fstat(f.fileno())
            if s.st_nlink != 1:
                raise ValueError('JOURNAL_HARDLINK')
            f.write(canonical(row)+b'\n'); f.flush(); os.fsync(f.fileno())
        if self._rows()[-1] != row:
            raise ValueError('STOP_AND_PRESERVE_JOURNAL_READBACK')

    def prepare(self, files, *, manifest_sha256, previous_receipt=None, previous_receipt_sha256=None, root_created=False, state_root=None):
        if self._rows():
            raise ValueError('EXISTING_OPERATION_RECONCILE_ONLY')
        if type(root_created) is not bool or (root_created and any(self.root.iterdir())):
            raise ValueError('NEW_EMPTY_ROOT_REQUIRED')
        state=None
        if state_root is not None:
            state=ordinary(state_root)
            if not root_created or not state.is_dir() or any(state.iterdir()):
                raise ValueError('NEW_EMPTY_STATE_REQUIRED')
        if not re.fullmatch('[0-9a-f]{64}', manifest_sha256 or ''):
            raise ValueError('APPROVED_MANIFEST_REQUIRED')
        owned = {}
        if previous_receipt is not None:
            if (type(previous_receipt) is not bytes or fingerprint(previous_receipt) != previous_receipt_sha256 or
                    read(self.root/'config/installation.json') != previous_receipt):
                raise ValueError('PINNED_OWNERSHIP_RECEIPT_REQUIRED')
            receipt = json.loads(previous_receipt)
            if receipt.get('schema') != 'rokt.disabled-host-install-receipt.v2' or type(receipt.get('files')) is not dict:
                raise ValueError('EXACT_OWNERSHIP_RECEIPT_REQUIRED')
            owned = dict(receipt['files'])
            if 'config/installation.json' in owned:
                raise ValueError('RECEIPT_SELF_REFERENCE')
            owned['config/installation.json'] = previous_receipt_sha256
        elif previous_receipt_sha256 is not None:
            raise ValueError('PINNED_OWNERSHIP_RECEIPT_REQUIRED')
        if type(files) is not dict or not files or len(files)+len(owned)>512:
            raise ValueError('EXACT_FILE_MANIFEST_REQUIRED')
        if owned and not re.fullmatch('[0-9a-f]{64}', previous_receipt_sha256 or ''):
            raise ValueError('PINNED_OWNERSHIP_RECEIPT_REQUIRED')
        names = sorted(set(files)|set(owned))
        if any(n.casefold().endswith('.u1-new') for n in names):
            raise ValueError('RESERVED_STAGING_PATH')
        if sum(len(v) for v in files.values() if type(v) is bytes)>16*1024*1024:
            raise ValueError('HOST_PAYLOAD_TOO_LARGE')
        folded = []
        plan = []
        backup_total = 0
        for n in names:
            name(n)
            lower = n.casefold()
            if any(lower == x or lower.startswith(x+'/') or x.startswith(lower+'/') for x in folded):
                raise ValueError('OWNED_PATH_COLLISION')
            folded.append(lower)
            old = read(self.root/n)
            backup_total += 0 if old is None else len(old)
            if backup_total > 16*1024*1024:
                raise ValueError('HOST_BACKUPS_TOO_LARGE')
            if n in owned:
                if not re.fullmatch('[0-9a-f]{64}', owned[n]) or fingerprint(old) != owned[n]:
                    raise ValueError('OWNERSHIP_HASH_MISMATCH')
            elif old is not None:
                raise ValueError('UNOWNED_FILE_COLLISION')
            new = files.get(n)
            if new is not None and (type(new) is not bytes or len(new)>256*1024*1024):
                raise ValueError('INVALID_FILE_BYTES')
            plan.append(dict(path=n, before=fingerprint(old), after=fingerprint(new),
                             backup=None if old is None else base64.b64encode(old).decode(),
                             content=None if new is None else base64.b64encode(new).decode()))
        self._append(phase='PREPARED', root=str(self.root), manifest_sha256=manifest_sha256,
                     root_identity=[self.root.stat().st_dev,self.root.stat().st_ino],root_created=root_created,
                     state_root=None if state is None else str(state),state_identity=None if state is None else [state.stat().st_dev,state.stat().st_ino],
                     directories={str(p.relative_to(self.root)).replace('\\','/'):
                                  ('PRESENT' if p.is_dir() else 'ABSENT')
                                  for n in names for p in (self.root/n).parents if p!=self.root and self.root in p.parents},
                     previous_receipt_sha256=previous_receipt_sha256, plan=plan)

    def _plan(self):
        ordinary(self.root)
        rows = self._rows()
        if not rows or rows[0].get('phase') != 'PREPARED' or rows[0].get('root') != str(self.root):
            raise ValueError('STOP_AND_PRESERVE_PLAN_BINDING')
        if self.root.exists():
            if [self.root.stat().st_dev,self.root.stat().st_ino]!=rows[0]['root_identity']:
                raise ValueError('STOP_AND_PRESERVE_ROOT_CHANGED')
        elif not (rows[0]['root_created'] and rows[-1]['phase'] in ('ROOT_REMOVE_INTENT','ROOT_REMOVED','STATE_REMOVE_INTENT','STATE_REMOVED') and all(i['before']=='ABSENT' for i in rows[0]['plan'])):
            raise ValueError('STOP_AND_PRESERVE_ROOT_MISSING')
        for item in rows[0]['plan']:
            name(item['path'])
            for field, blob in (('before','backup'),('after','content')):
                raw = None if item[blob] is None else base64.b64decode(item[blob], validate=True)
                if fingerprint(raw) != item[field]:
                    raise ValueError('STOP_AND_PRESERVE_BACKUP_HASH')
        return rows, rows[0]['plan']

    def _change(self, item, backwards=False):
        p = ordinary(self.root/item['path'])
        expected = item['after' if backwards else 'before']
        target = item['before' if backwards else 'after']
        if fingerprint(read(p)) != expected:
            raise ValueError('STOP_AND_PRESERVE_FILE_CHANGED')
        raw = item['backup' if backwards else 'content']
        if raw is None:
            p.unlink()
        else:
            # Deterministic sibling staging is recorded by intent. Never adopt
            # an unexpected staging artifact after a prior process exits.
            stage = ordinary(p.with_name(p.name+'.u1-new'))
            for parent in reversed(tuple(p.parents)):
                if self.root not in parent.parents or parent.exists():continue
                self._append(phase='DIRECTORY_CREATE_INTENT',path=parent.relative_to(self.root).as_posix())
                parent.mkdir()
                self._append(phase='DIRECTORY_CREATED',path=parent.relative_to(self.root).as_posix(),identity=[parent.stat().st_dev,parent.stat().st_ino])
            with stage.open('xb') as f:
                f.write(base64.b64decode(raw)); f.flush(); os.fsync(f.fileno())
            if fingerprint(read(p)) != expected:
                raise ValueError('STOP_AND_PRESERVE_FILE_CHANGED')
            os.replace(stage, p)
        self.fault('ROLLBACK_EFFECT' if backwards else 'APPLY_EFFECT', item['path'])
        if fingerprint(read(p)) != target:
            raise ValueError('STOP_AND_PRESERVE_READBACK')

    def apply(self):
        rows, plan = self._plan()
        if rows[-1]['phase'] == 'FILES_APPLIED':
            if any(fingerprint(read(self.root/i['path'])) != i['after'] for i in plan):
                raise ValueError('STOP_AND_PRESERVE_FILE_CHANGED')
            return self.receipt()
        if len(rows) != 1:
            raise ValueError('STOP_AND_PRESERVE_NO_FORWARD_REPLAY')
        for i in plan:
            if i['before'] == i['after']:
                continue
            self._append(phase='APPLY_INTENT', path=i['path'])
            self.fault('APPLY_INTENT', i['path'])
            self._change(i)
            self._append(phase='APPLY_VERIFIED', path=i['path'])
        self._append(phase='FILES_APPLIED')
        return self.receipt()

    def receipt(self):
        rows, plan = self._plan()
        if rows[-1]['phase'] != 'FILES_APPLIED' or any(fingerprint(read(self.root/i['path'])) != i['after'] for i in plan):
            raise ValueError('VERIFIED_FILE_PHASE_REQUIRED')
        return dict(schema='rokt.u1-owned-files.v1', manifest_sha256=rows[0]['manifest_sha256'],
                    files={i['path']:i['after'] for i in plan if i['after']!='ABSENT'})

    def check_rollback(self):
        rows, plan = self._plan()
        if rows[-1]['phase'] in ('ROLLED_BACK','ROOT_REMOVE_INTENT','ROOT_REMOVED','DIRECTORY_REMOVE_INTENT','DIRECTORY_REMOVED','DIRECTORIES_PRUNED','STATE_REMOVE_INTENT','STATE_REMOVED'):
            if any(fingerprint(read(self.root/i['path'])) != i['before'] for i in plan):
                raise ValueError('STOP_AND_PRESERVE_FILE_CHANGED')
            self._check_directories(rows,plan)
            return rows, plan
        touched = {r['path'] for r in rows if r['phase'] in ('APPLY_INTENT','ROLLBACK_INTENT')}
        # Validate the entire observation before compensating any file.
        for i in plan:
            actual = fingerprint(read(self.root/i['path']))
            if actual not in ({i['before'],i['after']} if i['path'] in touched else {i['before']}):
                raise ValueError('STOP_AND_PRESERVE_UNKNOWN_FILE')
            if (self.root/i['path']).with_name(Path(i['path']).name+'.u1-new').exists():
                raise ValueError('STOP_AND_PRESERVE_STAGING_ARTIFACT')
        self._check_directories(rows,plan)
        return rows, plan

    def _check_directories(self,rows,plan):
        if rows[0]['state_root'] is not None:
            state=ordinary(rows[0]['state_root'])
            if not state.exists() and not any(r['phase']=='STATE_REMOVE_INTENT' for r in rows):
                raise ValueError('STOP_AND_PRESERVE_STATE_MISSING')
            if state.exists() and (not state.is_dir() or [state.stat().st_dev,state.stat().st_ino]!=rows[0]['state_identity'] or any(state.iterdir())):
                raise ValueError('STOP_AND_PRESERVE_STATE_NOT_EMPTY_OR_CHANGED')
        created={r['path']:r['identity'] for r in rows if r['phase']=='DIRECTORY_CREATED'}
        targets={i['path'] for i in plan}
        for relative,before in rows[0]['directories'].items():
            p=ordinary(self.root/relative)
            if before=='ABSENT' and p.exists():
                if not p.is_dir() or relative not in created or [p.stat().st_dev,p.stat().st_ino]!=created[relative]:
                    raise ValueError('STOP_AND_PRESERVE_DIRECTORY_UNKNOWN')
        if self.root.exists():
            for p in self.root.rglob('*'):
                ordinary(p);relative=p.relative_to(self.root).as_posix()
                in_scope=rows[0]['root_created'] or any(relative==d or relative.startswith(d+'/') for d in created)
                if in_scope and ((p.is_file() and relative not in targets) or (p.is_dir() and relative not in created)):
                    raise ValueError('STOP_AND_PRESERVE_UNOWNED_ROOT_CONTENT')

    def rollback(self):
        rows, plan = self.check_rollback()
        if rows[-1]['phase'] in ('ROLLED_BACK','ROOT_REMOVE_INTENT','ROOT_REMOVED','DIRECTORY_REMOVE_INTENT','DIRECTORY_REMOVED','DIRECTORIES_PRUNED','STATE_REMOVE_INTENT','STATE_REMOVED'):
            return
        for i in reversed(plan):
            if fingerprint(read(self.root/i['path'])) == i['before']:
                continue
            self._append(phase='ROLLBACK_INTENT', path=i['path'])
            self.fault('ROLLBACK_INTENT', i['path'])
            self._change(i, True)
            self._append(phase='ROLLBACK_VERIFIED', path=i['path'])
        self._append(phase='ROLLED_BACK')

    def prune_created_directories(self):
        rows,plan=self.check_rollback()
        if rows[-1]['phase'] not in ('ROLLED_BACK','DIRECTORY_REMOVE_INTENT','DIRECTORY_REMOVED','DIRECTORIES_PRUNED'):
            raise ValueError('VERIFIED_DIRECTORY_ROLLBACK_REQUIRED')
        if self.root.exists():
            directories=sorted(rows[0]['directories'],key=lambda n:(n.count('/'),n),reverse=True)
            for relative in directories:
                p=ordinary(self.root/relative)
                if not p.exists() or rows[0]['directories'][relative]!='ABSENT':continue
                if any(p.iterdir()):
                    raise ValueError('STOP_AND_PRESERVE_DIRECTORY_NOT_EMPTY')
                self._append(phase='DIRECTORY_REMOVE_INTENT',path=relative)
                self.fault('DIRECTORY_REMOVE_INTENT',relative)
                p.rmdir()
                self.fault('DIRECTORY_REMOVE_EFFECT',relative)
                self._append(phase='DIRECTORY_REMOVED',path=relative)
        self._append(phase='DIRECTORIES_PRUNED')

    def prune_created_root(self):
        rows,plan=self.check_rollback()
        if not rows[0]['root_created'] or rows[-1]['phase'] not in ('ROLLED_BACK','DIRECTORY_REMOVE_INTENT','DIRECTORY_REMOVED','DIRECTORIES_PRUNED','ROOT_REMOVE_INTENT','ROOT_REMOVED','STATE_REMOVE_INTENT','STATE_REMOVED'):
            raise ValueError('VERIFIED_NEW_ROOT_ROLLBACK_REQUIRED')
        if rows[-1]['phase']=='ROOT_REMOVED':return
        if self.root.exists():
            if rows[-1]['phase']!='ROOT_REMOVE_INTENT':self.prune_created_directories()
            if any(self.root.iterdir()):raise ValueError('STOP_AND_PRESERVE_ROOT_NOT_EMPTY')
            self._append(phase='ROOT_REMOVE_INTENT')
            self.fault('ROOT_REMOVE_INTENT',str(self.root))
            self.root.rmdir()
            self.fault('ROOT_REMOVE_EFFECT',str(self.root))
        if rows[0]['state_root'] is not None:
            state=ordinary(rows[0]['state_root'])
            if state.exists():
                self._append(phase='STATE_REMOVE_INTENT')
                self.fault('STATE_REMOVE_INTENT',str(state))
                state.rmdir()
                self.fault('STATE_REMOVE_EFFECT',str(state))
                self._append(phase='STATE_REMOVED')
        self._append(phase='ROOT_REMOVED')


def main():
    """Pinned installer helper: roots are constants, not caller-controlled paths."""
    import argparse
    import sys
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare-apply', 'check-rollback', 'rollback', 'prune-created-root','prune-created-directories', 'status','observe-roots','check-empty-roots','remove-empty-code-root','remove-empty-state-root'))
    p.add_argument('--operation', required=True)
    a = p.parse_args()
    if not re.fullmatch('[0-9a-f]{64}', a.operation):
        raise ValueError('OPERATION_HASH_REQUIRED')
    if os.name != 'nt':
        raise ValueError('WINDOWS_ONLY')
    roots={'code':ordinary(r'C:\Program Files\RoktU1Bridge\v1'),'state':ordinary(r'C:\ProgramData\RoktU1Bridge')}
    if a.action=='observe-roots':
        print(json.dumps({k:None if not v.exists() else [v.stat().st_dev,v.stat().st_ino] for k,v in roots.items()}));return
    if a.action in ('check-empty-roots','remove-empty-code-root','remove-empty-state-root'):
        expected=json.loads(sys.stdin.buffer.read(4096))
        if set(expected)!= {'code','state','absent_allowed'} or type(expected['absent_allowed']) is not list:
            raise ValueError('EXACT_ROOT_IDENTITIES_REQUIRED')
        for key,path in roots.items():
            if path.exists():
                if expected[key] is None or not path.is_dir() or [path.stat().st_dev,path.stat().st_ino]!=expected[key] or any(path.iterdir()):
                    raise ValueError('STOP_AND_PRESERVE_ROOT_UNKNOWN_OR_NOT_EMPTY')
            elif expected[key] is not None and key not in expected['absent_allowed']:
                raise ValueError('STOP_AND_PRESERVE_ROOT_MISSING')
        if a.action!='check-empty-roots':
            key='code' if a.action=='remove-empty-code-root' else 'state'
            if roots[key].exists():roots[key].rmdir()
        print(json.dumps(dict(observation='KNOWN',allow_dispatch=False)));return
    transaction = HostFileTransaction(r'C:\Program Files\RoktU1Bridge\v1',
        Path(r'C:\ProgramData\RoktU1InstallAudit')/('files-'+a.operation+'.jsonl'))
    if a.action == 'prepare-apply':
        request = json.loads(sys.stdin.buffer.read(32*1024*1024+1))
        if set(request) != {'files','previous_receipt','manifest_sha256','previous_receipt_sha256','root_created'}:
            raise ValueError('EXACT_REQUEST_REQUIRED')
        files = {name(k):base64.b64decode(v,validate=True) for k,v in request['files'].items()}
        previous = None if request['previous_receipt'] is None else base64.b64decode(request['previous_receipt'],validate=True)
        transaction.prepare(files, manifest_sha256=request['manifest_sha256'],previous_receipt=previous,
                            previous_receipt_sha256=request['previous_receipt_sha256'],root_created=request['root_created'],
                            state_root=r'C:\ProgramData\RoktU1Bridge' if request['root_created'] else None)
        print(json.dumps(transaction.apply()))
    elif a.action == 'check-rollback':
        transaction.check_rollback()
        print(json.dumps(dict(compensation_observation='KNOWN',replay_allowed=False)))
    elif a.action == 'rollback':
        transaction.rollback()
        print(json.dumps(dict(outcome='ROLLED_BACK',allow_dispatch=False)))
    elif a.action == 'prune-created-root':
        transaction.prune_created_root()
        print(json.dumps(dict(root='ABSENT',allow_dispatch=False)))
    elif a.action == 'prune-created-directories':
        transaction.prune_created_directories()
        print(json.dumps(dict(created_directories='ABSENT',allow_dispatch=False)))
    else:
        rows, _ = transaction._plan()
        if rows[-1]['phase'] == 'FILES_APPLIED':
            transaction.receipt()
        print(json.dumps(dict(phase=rows[-1]['phase'],replay_allowed=False)))


if __name__ == '__main__':
    main()
