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
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'development.lock'
        # Never replace or unlink this file: all clients must lock the same inode.
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        if os.fstat(self.fd).st_size < 4:
            os.lseek(self.fd, 0, os.SEEK_END)
            os.write(self.fd, b'\0' * (4 - os.fstat(self.fd).st_size))

    @contextlib.contextmanager
    def lock(self, byte, wait=0):
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
                    prior = json.loads(stale.read_text(encoding='utf-8'))
                    prior_record = self.root / ('run-' + str(uuid.UUID(prior['run_id'])) + '.json')
                    if prior_record.exists():
                        prior_data = json.loads(prior_record.read_text(encoding='utf-8'))
                        if prior_data.get('status') == 'RUNNING':
                            prior_data['status'] = 'ABANDONED_LOCK_RELEASED'
                            prior_record.write_text(json.dumps(prior_data, ensure_ascii=False), encoding='utf-8')
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
                        previous = json.loads(p.read_text(encoding='utf-8'))
                        if os.path.normcase(previous['worktree']) == os.path.normcase(worktree):
                            raise Busy('WORKTREE_ALREADY_IN_USE')
                data = dict(run_id=run_id, slot=index, owner=owner, pid=os.getpid(),
                            started_at=datetime.now(timezone.utc).isoformat(),
                            worktree=worktree, branch=branch, status='RUNNING')
                with record.open('x', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                (self.root / ('slot-%d.json' % index)).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            except BaseException:
                held.__exit__(*sys.exc_info())
                raise
        try:
            yield data
        finally:
            with self.lock(0, wait=5):
                data['status'] = 'FINISHED'
                data['finished_at'] = datetime.now(timezone.utc).isoformat()
                record.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
                held.__exit__(None, None, None)

    def close(self):
        os.close(self.fd)


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
        def execute():
            try:
                result = run_tree(command, cwd=args.worktree, timeout=args.timeout)
                sys.stdout.write(result.stdout); sys.stderr.write(result.stderr)
                return result.returncode
            except subprocess.TimeoutExpired:
                return 124
        if args.git_lock:
            with coordinator.lock(3, wait=5):
                return execute()
        if not args.run_id or not args.branch or not args.owner:
            p.error('run-id, branch and owner required for a work slot')
        with coordinator.slot(args.run_id, args.worktree, args.branch, args.owner):
            return execute()
    finally:
        coordinator.close()


if __name__ == '__main__':
    sys.exit(main())
