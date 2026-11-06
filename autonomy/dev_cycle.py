"""Local Windows development coordination; never a production scheduler.

All cooperating clients must use the same local NTFS coordination directory.
Kernel byte-range locks, not the presence of lock files, indicate ownership.
"""
import argparse
import contextlib
import json
import msvcrt
import os
from pathlib import Path
import sys
import time
import uuid
from datetime import datetime, timezone


class Busy(RuntimeError):
    pass


class Coordinator:
    def __init__(self, root):
        from publisher_channel.install_inputs import InstallInputPins
        # Keep ordinary ancestors and the mutable lock file pinned for the
        # complete coordinator lifetime. Share writes, never replacement.
        self.pins = InstallInputPins()
        self.pins.__enter__()
        self.fd = None
        try:
            self.root = self.pins.path(str(root))
            # Require an already provisioned directory: no mkdir through an
            # unvalidated junction/reparse ancestor. No ACL/service changes.
            if not self.root.is_dir():
                raise ValueError('COORDINATION_DIRECTORY_MUST_EXIST')
            self.path = self.root / 'development.lock'
            self.pins._parents(self.path)
            try:
                created = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(created)
            self.pins.add_mutable_reference(str(self.path))
            self.fd = self._open_pinned(self.path)
            with self.lock(0, wait=5):
                size = os.fstat(self.fd).st_size
                if size < 4:
                    os.lseek(self.fd, size, os.SEEK_SET)
                    os.write(self.fd, b'\0' * (4 - size))
                    os.fsync(self.fd)
        except BaseException:
            self.close()
            raise

    def _open_pinned(self, path):
        identity = self.pins.add_mutable_reference(str(path))
        fd = os.open(path, os.O_RDWR | os.O_BINARY)
        try:
            if self.pins._identity(msvcrt.get_osfhandle(fd), False) != identity:
                raise ValueError('COORDINATION_FILE_IDENTITY_CHANGED')
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _read_json(self, path):
        with os.fdopen(self._open_pinned(path), 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_json(self, path, value, *, exclusive=False):
        # Creation is exclusive; existing ordinary files are opened through a
        # retained identity pin before truncation. Never follow a reparse point.
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_BINARY, 0o600)
        except FileExistsError:
            if exclusive:
                raise ValueError('DUPLICATE_RUN_ID')
        else:
            os.close(fd)
        with os.fdopen(self._open_pinned(path), 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())

    @contextlib.contextmanager
    def lock(self, byte, wait=0):
        if type(byte) is not int or byte not in (0, 1, 2, 3):
            raise ValueError('INVALID_COORDINATION_LOCK_BYTE')
        self.pins.revalidate()
        end = time.monotonic() + wait
        while True:
            try:
                os.lseek(self.fd, byte, os.SEEK_SET)
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if time.monotonic() >= end:
                    raise Busy('LOCK_BUSY') from exc
                time.sleep(.05)
        try:
            yield
        finally:
            os.lseek(self.fd, byte, os.SEEK_SET)
            msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)

    @contextlib.contextmanager
    def slot(self, run_id, worktree, branch, owner):
        if str(uuid.UUID(run_id)) != run_id:
            raise ValueError('RUN_ID_MUST_BE_UUID')
        worktree = str(Path(worktree).resolve(strict=True))
        if not branch or not owner:
            raise ValueError('BRANCH_AND_OWNER_REQUIRED')
        with self.lock(0, wait=5):
            record = self.root / ('run-' + run_id + '.json')
            if record.exists():
                raise ValueError('DUPLICATE_RUN_ID')
            chosen = None
            for index in (1, 2):
                held = self.lock(index)
                try:
                    held.__enter__()
                except Busy:
                    continue
                chosen = (index, held)
                break
            if chosen is None:
                raise Busy('ALL_SLOTS_BUSY')
            index, held = chosen
            try:
                stale = self.root / ('slot-%d.json' % index)
                if stale.exists():
                    prior = self._read_json(stale)
                    prior_record = self.root / ('run-' + str(uuid.UUID(prior['run_id'])) + '.json')
                    if prior_record.exists():
                        prior_data = self._read_json(prior_record)
                        if prior_data.get('status') == 'STOP_AND_PRESERVE':
                            raise Busy('PRIOR_TREE_CLEANUP_UNVERIFIED')
                        if prior_data.get('status') == 'RUNNING':
                            prior_data['status'] = 'ABANDONED_LOCK_RELEASED'
                            self._write_json(prior_record, prior_data)
                # Other occupied slots are authoritative only while locked.
                for other in (1, 2):
                    if other == index:
                        continue
                    try:
                        with self.lock(other):
                            continue
                    except Busy:
                        p = self.root / ('slot-%d.json' % other)
                        if not p.exists():
                            raise Busy('OCCUPIED_SLOT_METADATA_MISSING')
                        previous = self._read_json(p)
                        if os.path.normcase(previous['worktree']) == os.path.normcase(worktree):
                            raise Busy('WORKTREE_ALREADY_IN_USE')
                data = dict(run_id=run_id, slot=index, owner=owner, pid=os.getpid(),
                            started_at=datetime.now(timezone.utc).isoformat(),
                            worktree=worktree, branch=branch, status='RUNNING')
                self._write_json(record, data, exclusive=True)
                self._write_json(self.root / ('slot-%d.json' % index), data)
            except BaseException:
                held.__exit__(*sys.exc_info())
                raise
        failed = False
        preserve = False
        try:
            yield data
        except BaseException as error:
            failed = True
            preserve = getattr(error, 'cleanup_verified', True) is not True
            raise
        finally:
            try:
                with self.lock(0, wait=5):
                    data['status'] = ('STOP_AND_PRESERVE' if preserve else
                                      'FAILED' if failed or data.get('command_returncode', 0) != 0 else 'FINISHED')
                    data['finished_at'] = datetime.now(timezone.utc).isoformat()
                    self._write_json(record, data)
            finally:
                held.__exit__(None, None, None)

    def close(self):
        try:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
        finally:
            self.pins.__exit__(None, None, None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--run-id')
    p.add_argument('--worktree', required=True)
    p.add_argument('--branch')
    p.add_argument('--owner')
    p.add_argument('--git-lock', action='store_true', help='short git commit/integration command')
    p.add_argument('--timeout', type=int, default=2700)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    if not 1 <= args.timeout <= 2700 or not args.command:
        p.error('command and timeout between 1 and 2700 required')
    command = args.command[1:] if args.command[0] == '--' else args.command
    if not command:
        p.error('command required')
    coordinator = Coordinator(args.root)
    try:
        from autonomy.process_job import run_tree
        import subprocess
        def execute(data=None):
            try:
                result = run_tree(command, cwd=args.worktree, timeout=args.timeout)
                sys.stdout.write(result.stdout); sys.stderr.write(result.stderr)
                code = result.returncode
            except subprocess.TimeoutExpired as error:
                if getattr(error, 'cleanup_verified', False) is not True:
                    raise
                code = 124
            if data is not None:
                data['command_returncode'] = code
                data['command_outcome'] = 'TIMED_OUT' if code == 124 else 'EXITED'
            return code
        if args.git_lock:
            with coordinator.lock(3, wait=5):
                return execute()
        if not args.run_id or not args.branch or not args.owner:
            p.error('run-id, branch and owner required for a work slot')
        with coordinator.slot(args.run_id, args.worktree, args.branch, args.owner) as data:
            return execute(data)
    finally:
        coordinator.close()


if __name__ == '__main__':
    sys.exit(main())
