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
import stat
import uuid

SCHEMA = 'rokt.release-store.v1'
INVENTORY = '1784775229336'
MAX_TOTAL = 128 * 1024 * 1024
LARGE_SCHEMA = 'rokt.release-manifest.v2'
MAX_LARGE_TOTAL = 1024 * 1024 * 1024
MAX_FILE = 256 * 1024 * 1024
MAX_MANIFEST = 2 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ordinary(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        try:
            st = item.lstat()
        except FileNotFoundError:
            continue
        # One non-following query preserves dangling-link/reparse rejection.
        # Other inspection errors must propagate rather than imply absence.
        if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_file_attributes', 0) & 0x400:
            raise ValueError('REPARSE_PATH')
    return path


def safe_path(name):
    if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_./+-]+', name):
        raise ValueError('UNSAFE_PATH')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{n}' for p in ('COM','LPT') for n in range(1,10)}
    if any(p in ('', '.', '..') or p.endswith('.') or p.split('.')[0].upper() in reserved
           for p in name.split('/')):
        raise ValueError('UNSAFE_PATH')
    return name


def checked_manifest(raw):
    m = json.loads(raw)
    if (set(m) != {'schema','inventory_id','source_commit','files'} or m['schema'] not in (SCHEMA,LARGE_SCHEMA) or
        m['inventory_id'] != INVENTORY or not re.fullmatch('[0-9a-f]{40}', m['source_commit']) or
        type(m['files']) is not dict or not 1 <= len(m['files']) <= (8192 if m['schema']==LARGE_SCHEMA else 512)):
        raise ValueError('INVALID_MANIFEST')
    paths = []
    for name, digest in m['files'].items():
        safe_path(name)
        if not re.fullmatch('[0-9a-f]{64}', digest): raise ValueError('INVALID_HASH')
        paths.append(tuple(name.casefold().split('/')))
    # A component tuple sorts immediately before all of its descendants.
    # Compare adjacent tuples, rather than every pair of complete paths.
    paths.sort()
    for previous, current in zip(paths, paths[1:]):
        if len(previous) <= len(current) and current[:len(previous)] == previous:
            raise ValueError('PATH_COLLISION')
    if raw != canonical(m): raise ValueError('NONCANONICAL_MANIFEST')
    return m


def read_file(path, limit=MAX_FILE):
    path = ordinary(path)
    if path.stat().st_nlink != 1: raise ValueError('HARDLINK_REJECTED')
    with path.open('rb') as f:
        # A single bytes allocation sized to the opened file avoids both the
        # limit-sized allocation for small files and a second full-size copy.
        # Read one extra byte and recheck the handle size to detect growth.
        for attempt in range(3):
            size = os.fstat(f.fileno()).st_size
            if size > limit: raise ValueError('FILE_TOO_LARGE')
            if attempt: f.seek(0)
            data = f.read(size + 1)
            if len(data) > limit: raise ValueError('FILE_TOO_LARGE')
            after = os.fstat(f.fileno()).st_size
            if after > limit: raise ValueError('FILE_TOO_LARGE')
            if len(data) == size == after: return data
            # Drop the old buffer before retrying; never hold two large reads.
            del data
        raise ValueError('FILE_CHANGED_DURING_READ')


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


def build_bundle_from_paths(destination, files, source_commit):
    """Large-runtime packaging, one bounded file at a time; never installs.

    The new manifest schema is explicit; legacy size/count limits remain intact.
    Sources are checked again while copied. A failed destination is retained.
    """
    if type(files) is not dict or not 1<=len(files)<=8192:
        raise ValueError('EXACT_FILE_SOURCES_REQUIRED')
    hashes={};total=0
    for name,path in files.items():
        safe_path(name);raw=read_file(path);total+=len(raw)
        if total>MAX_LARGE_TOTAL:raise ValueError('PACKAGE_TOO_LARGE')
        hashes[name]=sha(raw)
    manifest=canonical(dict(schema=LARGE_SCHEMA,inventory_id=INVENTORY,
                            source_commit=source_commit,files=hashes))
    if len(manifest)>MAX_MANIFEST:raise ValueError('MANIFEST_TOO_LARGE')
    checked_manifest(manifest)
    dest=ordinary(destination);dest.mkdir()
    for name,path in files.items():
        raw=read_file(path)
        if sha(raw)!=hashes[name]:raise ValueError('SOURCE_CHANGED')
        target=dest/'payload'/name;target.parent.mkdir(parents=True,exist_ok=True)
        durable_new(target,raw)
    durable_new(dest/'manifest.json',manifest)
    return sha(manifest)


def build_archive_from_paths(destination, files, source_commit, *, source_reader=None):
    """Write the same v2 payload directly to an exclusive archive, without staging.

    Failed archives are preserved and are never evidence of a completed build.
    Every source is read again against its precomputed manifest digest.
    """
    import zipfile
    if type(files) is not dict or not 1 <= len(files) <= 8192:
        raise ValueError('EXACT_FILE_SOURCES_REQUIRED')
    read_source = read_file if source_reader is None else source_reader
    hashes = {}; total = 0
    for name, path in files.items():
        safe_path(name); raw = read_source(path); total += len(raw)
        if total > MAX_LARGE_TOTAL: raise ValueError('PACKAGE_TOO_LARGE')
        hashes[name] = sha(raw)
    manifest = canonical(dict(schema=LARGE_SCHEMA, inventory_id=INVENTORY,
        source_commit=source_commit, files=hashes))
    if len(manifest) > MAX_MANIFEST: raise ValueError('MANIFEST_TOO_LARGE')
    checked_manifest(manifest)
    destination = ordinary(destination)
    with destination.open('xb') as output:
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path in files.items():
                raw = read_source(path)
                if sha(raw) != hashes[name]: raise ValueError('SOURCE_CHANGED')
                archive.writestr('payload/' + name, raw)
            archive.writestr('manifest.json', manifest)
        output.flush(); os.fsync(output.fileno())
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
        raw = read_file(folder/'manifest.json', MAX_MANIFEST)
        if sha(raw) != version: raise ValueError('MANIFEST_HASH_MISMATCH')
        m = checked_manifest(raw); total = 0
        for name, digest in m['files'].items():
            data = read_file(folder/'payload'/name); total += len(data)
            if total > (MAX_LARGE_TOTAL if m['schema']==LARGE_SCHEMA else MAX_TOTAL) or sha(data) != digest: raise ValueError('ARTIFACT_MISMATCH')
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

    def _validate_layout(self, folder, manifest):
        # Staging uses a shorter UUID than the final SHA directory. Validate the
        # final spelling before creating anything, without assuming LongPathsEnabled.
        if os.name != 'nt': return
        def units(path): return len(str(path.absolute()).encode('utf-16-le'))//2
        for relative in ['manifest.json']+['payload/'+n for n in manifest['files']]:
            target=folder/relative
            if units(target)>=260:raise ValueError('WINDOWS_TARGET_PATH_TOO_LONG')
            for parent in (target.parent,*target.parent.parents):
                if units(parent)>=248:raise ValueError('WINDOWS_TARGET_DIRECTORY_TOO_LONG')

    def _assert_no_pending(self):
        transactions = ordinary(self.root/'transactions')
        if transactions.exists() and any(transactions.glob('*.pending.json')):
            raise ValueError('STOP_AND_PRESERVE_PENDING_PUBLICATION')

    def recovery_status(self):
        """Inspect uncertain publications; pointer equality never authorizes replay.

        A crash after the pointer commit but before the receipt remains UNKNOWN.
        This is an inspection entry point, not an automatic recovery writer.
        """
        with self.locked():
            transactions = ordinary(self.root/'transactions')
            pending = []
            for path in sorted(transactions.glob('*.pending.json')) if transactions.exists() else []:
                item = dict(transaction=path.name.removesuffix('.pending.json'),
                            observed='UNKNOWN', pointer_relation='UNKNOWN')
                try:
                    raw = read_file(path, 4096)
                    record = json.loads(raw)
                    if (not re.fullmatch('[0-9a-f]{32}', item['transaction']) or
                        type(record) is not dict or
                        set(record) != {'schema','inventory_id','before','after','reason'} or
                        record['schema'] != SCHEMA or record['inventory_id'] != INVENTORY or
                        record['reason'] not in ('ACTIVATE','ROLLBACK') or raw != canonical(record)):
                        raise ValueError('INVALID_TRANSACTION')
                    for version in (record['before'],record['after']):
                        if version is not None: self._verify(self._version(version),version)
                    pointer = self._pointer()
                    current = pointer['version'] if pointer else None
                    item.update(before=record['before'],after=record['after'],
                                pointer_relation=('TARGET_CURRENT' if current == record['after'] else
                                                  'SOURCE_CURRENT' if current == record['before'] else 'DIVERGED'))
                except (ValueError,OSError,TypeError,KeyError,RecursionError):
                    pass
                pending.append(item)
            return dict(schema=SCHEMA,inventory_id=INVENTORY,pending=pending,
                        action='STOP_AND_PRESERVE' if pending else 'NO_PENDING_PUBLICATION_RECORDED',
                        allow_replay=False,allow_dispatch=False,production_accepted=False)

    def stage(self, package, approved_manifest_sha256):
        """Copy new or upgraded file sets into a fresh immutable version."""
        with self.locked():
            self._assert_no_pending()
            package = ordinary(package); m = self._verify(package, approved_manifest_sha256)
            dest = self._version(approved_manifest_sha256)
            self._validate_layout(dest,m)
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
        self._assert_no_pending()
        current = self._pointer(); actual = current['version'] if current else None
        if actual != expected: raise ValueError('CURRENT_VERSION_CHANGED')
        if actual is not None: self._verify(self._version(actual), actual)
        if version is not None: self._verify(self._version(version), version)
        record = dict(schema=SCHEMA, inventory_id=INVENTORY, before=actual, after=version, reason=reason)
        tx = uuid.uuid4().hex
        transactions = ordinary(self.root/'transactions'); transactions.mkdir(exist_ok=True)
        pending = ordinary(transactions/(tx+'.pending.json'))
        # Persist uncertainty BEFORE any publication side effect. Never clear this
        # intent in an exception handler: lost receipts require status inspection.
        durable_new(pending, canonical(record))
        backups = ordinary(self.root/'backups'); backups.mkdir(exist_ok=True)
        durable_new(backups/(tx+'.json'), canonical(record))
        temp = self.root/('pointer-'+tx+'.tmp')
        durable_new(temp, canonical(dict(schema=SCHEMA,inventory_id=INVENTORY,version=version)))
        # Sole commit point. Crash after replace: inspect pointer; do not replay.
        os.replace(temp, ordinary(self.root/'active.json'))
        # A rename failure or abrupt exit leaves the pending marker intact and
        # fences every subsequent mutating entry point. Do not infer a receipt.
        os.rename(pending, ordinary(transactions/(tx+'.receipt.json')))
        return dict(record, transaction=tx, outcome='POINTER_COMMITTED', service_changed=False)

    def activate(self, version, *, expected_current):
        with self.locked(): return self._switch(version, expected_current, 'ACTIVATE')

    def rollback(self, transaction, *, expected_current):
        if not re.fullmatch('[0-9a-f]{32}', transaction): raise ValueError('INVALID_TRANSACTION')
        with self.locked():
            self._assert_no_pending()
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
            self._assert_no_pending()
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
    sub.add_parser('recovery-status')
    args = parser.parse_args(); store = ReleaseStore(args.root)
    if args.command == 'stage': result = store.stage(args.package,args.manifest_sha256)
    elif args.command == 'status': result = store.status()
    elif args.command == 'recovery-status': result = store.recovery_status()
    elif args.command == 'delete-inactive': result = store.delete_inactive(args.version)
    else:
        expected = None if args.expected_current == 'ABSENT' else args.expected_current
        result = store.activate(args.version,expected_current=expected) if args.command == 'activate' else store.rollback(args.transaction,expected_current=expected)
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__': main()
