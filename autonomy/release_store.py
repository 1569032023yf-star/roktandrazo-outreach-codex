"""Versioned file publisher. No service, scheduler, SMTP or database operations.

Publication changes only this store's active.json; consumers must resolve it.
Trusted destination ACL and Inventory maintenance exclusion remain caller duties.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

SCHEMA = 'rokt.release-store.v1'
INVENTORY = '1784775229336'
MAX_TOTAL = 128 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ordinary(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            st = item.lstat()
            if item.is_symlink() or getattr(st, 'st_file_attributes', 0) & 0x400:
                raise ValueError('REPARSE_PATH')
    return path


def safe_path(name):
    if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_./-]+', name):
        raise ValueError('UNSAFE_PATH')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{n}' for p in ('COM','LPT') for n in range(1,10)}
    if any(p in ('', '.', '..') or p.endswith('.') or p.split('.')[0].upper() in reserved
           for p in name.split('/')):
        raise ValueError('UNSAFE_PATH')
    return name


def checked_manifest(raw):
    m = json.loads(raw)
    if (set(m) != {'schema','inventory_id','source_commit','files'} or m['schema'] != SCHEMA or
        m['inventory_id'] != INVENTORY or not re.fullmatch('[0-9a-f]{40}', m['source_commit']) or
        type(m['files']) is not dict or not 1 <= len(m['files']) <= 512):
        raise ValueError('INVALID_MANIFEST')
    seen = set()
    for name, digest in m['files'].items():
        safe_path(name)
        if not re.fullmatch('[0-9a-f]{64}', digest): raise ValueError('INVALID_HASH')
        lower = name.casefold()
        if any(lower == x or lower.startswith(x+'/') or x.startswith(lower+'/') for x in seen):
            raise ValueError('PATH_COLLISION')
        seen.add(lower)
    if raw != canonical(m): raise ValueError('NONCANONICAL_MANIFEST')
    return m


def read_file(path, limit=MAX_TOTAL):
    path = ordinary(path)
    if path.stat().st_nlink != 1: raise ValueError('HARDLINK_REJECTED')
    with path.open('rb') as f: data = f.read(limit+1)
    if len(data) > limit: raise ValueError('FILE_TOO_LARGE')
    return data


def durable_new(path, raw):
    with Path(path).open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())


def build_bundle(destination, files, source_commit):
    """Build from exact caller-selected bytes; this is packaging, not approval."""
    manifest = canonical(dict(schema=SCHEMA, inventory_id=INVENTORY,
                              source_commit=source_commit, files={n:sha(b) for n,b in files.items()}))
    checked_manifest(manifest)
    if sum(map(len, files.values())) > MAX_TOTAL: raise ValueError('PACKAGE_TOO_LARGE')
    dest = ordinary(destination); dest.mkdir()
    for name, raw in files.items():
        target = dest/'payload'/name; target.parent.mkdir(parents=True, exist_ok=True)
        durable_new(target, raw)
    durable_new(dest/'manifest.json', manifest)
    return sha(manifest)


class ReleaseStore:
    def __init__(self, root):
        self.root = ordinary(root)
        if not self.root.is_dir(): raise ValueError('EXISTING_STORE_DIRECTORY_REQUIRED')

    @contextmanager
    def locked(self):
        ordinary(self.root)
        lock = ordinary(self.root/'publisher.lock')
        with lock.open('a+b') as f:
            if f.tell() == 0: f.write(b'0'); f.flush()
            f.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                f.seek(0)
                if os.name == 'nt': msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(f, fcntl.LOCK_UN)

    def _version(self, version):
        if type(version) is not str or not re.fullmatch('[0-9a-f]{64}', version):
            raise ValueError('INVALID_VERSION')
        return ordinary(self.root/'versions'/version)

    def _verify(self, folder, version):
        raw = read_file(folder/'manifest.json', 131072)
        if sha(raw) != version: raise ValueError('MANIFEST_HASH_MISMATCH')
        m = checked_manifest(raw); total = 0
        for name, digest in m['files'].items():
            data = read_file(folder/'payload'/name); total += len(data)
            if total > MAX_TOTAL or sha(data) != digest: raise ValueError('ARTIFACT_MISMATCH')
        actual = set()
        for p in folder.rglob('*'):
            ordinary(p)
            if p.is_file(): actual.add(p.relative_to(folder).as_posix())
        if actual != {'manifest.json'} | {'payload/'+n for n in m['files']}:
            raise ValueError('UNMANAGED_FILES')
        return m

    def _pointer(self):
        p = ordinary(self.root/'active.json')
        if not p.exists(): return None
        raw = read_file(p, 4096); value = json.loads(raw)
        if (set(value) != {'schema','inventory_id','version'} or value['schema'] != SCHEMA or
            value['inventory_id'] != INVENTORY): raise ValueError('BAD_POINTER')
        if value['version'] is not None: self._version(value['version'])
        return value

    def stage(self, package, approved_manifest_sha256):
        """Copy new or upgraded file sets into a fresh immutable version."""
        with self.locked():
            package = ordinary(package); m = self._verify(package, approved_manifest_sha256)
            dest = self._version(approved_manifest_sha256)
            if dest.exists(): self._verify(dest, approved_manifest_sha256); return approved_manifest_sha256
            versions = ordinary(self.root/'versions'); versions.mkdir(exist_ok=True)
            stage = ordinary(versions/('staging-'+uuid.uuid4().hex)); stage.mkdir()
            # Partial staging remains for diagnosis, never a usable version.
            for name in ['manifest.json'] + ['payload/'+n for n in m['files']]:
                target = stage/name; target.parent.mkdir(parents=True, exist_ok=True)
                durable_new(target, read_file(package/name))
            self._verify(stage, approved_manifest_sha256)
            os.rename(stage, dest)
            return approved_manifest_sha256

    def _switch(self, version, expected, reason):
        current = self._pointer(); actual = current['version'] if current else None
        if actual != expected: raise ValueError('CURRENT_VERSION_CHANGED')
        if actual is not None: self._verify(self._version(actual), actual)
        if version is not None: self._verify(self._version(version), version)
        record = dict(schema=SCHEMA, inventory_id=INVENTORY, before=actual, after=version, reason=reason)
        tx = uuid.uuid4().hex
        backups = ordinary(self.root/'backups'); backups.mkdir(exist_ok=True)
        durable_new(backups/(tx+'.json'), canonical(record))
        temp = self.root/('pointer-'+tx+'.tmp')
        durable_new(temp, canonical(dict(schema=SCHEMA,inventory_id=INVENTORY,version=version)))
        # Sole commit point. Crash after replace: inspect pointer; do not replay.
        os.replace(temp, ordinary(self.root/'active.json'))
        return dict(record, transaction=tx, outcome='POINTER_COMMITTED', service_changed=False)

    def activate(self, version, *, expected_current):
        with self.locked(): return self._switch(version, expected_current, 'ACTIVATE')

    def rollback(self, transaction, *, expected_current):
        if not re.fullmatch('[0-9a-f]{32}', transaction): raise ValueError('INVALID_TRANSACTION')
        with self.locked():
            record = json.loads(read_file(self.root/'backups'/(transaction+'.json'), 4096))
            if (set(record) != {'schema','inventory_id','before','after','reason'} or
                record['schema'] != SCHEMA or record['inventory_id'] != INVENTORY or
                record['after'] != expected_current): raise ValueError('ROLLBACK_BINDING_MISMATCH')
            return self._switch(record['before'], expected_current, 'ROLLBACK')

    def status(self):
        with self.locked():
            current = self._pointer(); version = current['version'] if current else None
            if version: self._verify(self._version(version), version)
            return dict(schema=SCHEMA, inventory_id=INVENTORY, version=version,
                        allow_dispatch=False, production_accepted=False)

    def delete_inactive(self, version):
        """Explicit removal only; reject active or backup-referenced versions."""
        with self.locked():
            p = self._pointer()
            if p and p['version'] == version: raise ValueError('ACTIVE_VERSION')
            backups = ordinary(self.root/'backups')
            if backups.exists():
                for f in backups.glob('*.json'):
                    r = json.loads(read_file(f,4096))
                    if version in (r['before'],r['after']): raise ValueError('BACKUP_REFERENCED')
            folder = self._version(version); m = self._verify(folder, version)
            for name in m['files']: ordinary(folder/'payload'/name).unlink()
            (folder/'manifest.json').unlink()
            for p in sorted(folder.rglob('*'), key=lambda p:len(p.parts), reverse=True): p.rmdir()
            folder.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    stage = sub.add_parser('stage'); stage.add_argument('package'); stage.add_argument('manifest_sha256')
    activate = sub.add_parser('activate'); activate.add_argument('version'); activate.add_argument('--expected-current',required=True)
    rollback = sub.add_parser('rollback'); rollback.add_argument('transaction'); rollback.add_argument('--expected-current',required=True)
    delete = sub.add_parser('delete-inactive'); delete.add_argument('version')
    sub.add_parser('status')
    args = parser.parse_args(); store = ReleaseStore(args.root)
    if args.command == 'stage': result = store.stage(args.package,args.manifest_sha256)
    elif args.command == 'status': result = store.status()
    elif args.command == 'delete-inactive': result = store.delete_inactive(args.version)
    else:
        expected = None if args.expected_current == 'ABSENT' else args.expected_current
        result = store.activate(args.version,expected_current=expected) if args.command == 'activate' else store.rollback(args.transaction,expected_current=expected)
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__': main()
