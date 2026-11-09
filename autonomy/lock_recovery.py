"""Conservative process-instance lock recovery / 保守的进程实例锁恢复。"""
import ctypes
import errno
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import uuid
import json
import os
import tempfile
from pathlib import Path


def process_identity(pid):
    """Return creation identity, None if absent; raise if inspection is uncertain."""
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return None
            raise OSError('PROCESS_IDENTITY_UNAVAILABLE')
        try:
            wait = kernel.WaitForSingleObject(handle, 0)
            if wait == 0:
                return None  # An exited process object may remain while another handle exists.
            if wait != 258:
                raise OSError('PROCESS_LIVENESS_UNAVAILABLE')
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                raise OSError('PROCESS_IDENTITY_UNAVAILABLE')
            return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    try:
        stat = Path('/proc', str(pid), 'stat').read_text()
        start = stat.rsplit(')', 1)[1].split()[19]
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return boot + ':' + start
    except FileNotFoundError:
        if Path('/proc').is_dir():
            return None
        raise OSError('PROCESS_IDENTITY_UNAVAILABLE')


_ACTIVE_LEASE = ContextVar('supervisor_active_lease', default=None)


@contextmanager
def _guard(runtime):
    """Versioned kernel-owned guard; process exit releases the OS lock.

    Never unlink this file: removing a locked inode permits a parallel lock.
    Legacy empty O_EXCL markers are rejected, never guessed stale or deleted.
    Once initialized, legacy executors fail their O_EXCL acquisition safely.
    """
    path = Path(runtime) / 'supervisor.recovery.lock'
    marker=b'rokt.recovery-guard.v2\n'
    try:
        fd=os.open(path,os.O_RDWR)
    except FileNotFoundError:
        # Publish a complete marker atomically. Never expose an empty file that
        # a concurrent initializer could mistake for an abandoned legacy guard.
        temp_fd,temp_path=tempfile.mkstemp(prefix='.recovery-guard-',dir=path.parent)
        try:
            try:
                os.write(temp_fd,marker);os.fsync(temp_fd)
            finally:os.close(temp_fd)
            try:os.link(temp_path,path)
            except FileExistsError:pass
        finally:os.unlink(temp_path)
        fd=os.open(path,os.O_RDWR)
    locked=False
    try:
        try:
            if os.name=='nt':
                import msvcrt
                os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error:
            # Preserve the existing public contention contract. Do not relabel
            # open failures, malformed guards or unrelated kernel errors.
            if error.errno in (errno.EACCES,errno.EAGAIN) or getattr(error,'winerror',None)==33:
                raise FileExistsError('RECOVERY_GUARD_BUSY') from None
            raise
        locked=True
        os.lseek(fd,0,os.SEEK_SET)
        raw=os.read(fd,len(marker)+1)
        if raw!=marker:
            raise RuntimeError('LEGACY_OR_UNKNOWN_RECOVERY_GUARD')
        yield
    finally:
        try:
            if locked:
                if os.name=='nt':
                    os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
                else:fcntl.flock(fd,fcntl.LOCK_UN)
        finally:os.close(fd)


def _write_state(lock, state):
    # The original token is immutable; no timestamp/PID-only recovery is supported.
    with lock.open('w', encoding='utf-8') as handle:
        json.dump(state, handle)
        handle.flush()
        os.fsync(handle.fileno())


def _tree_fence(lock):
    return lock.with_name('supervisor.tree-unverified')


def _create_tree_fence(lock, token):
    with _tree_fence(lock).open('x', encoding='utf-8') as fence:
        fence.write(token)
        fence.flush()
        os.fsync(fence.fileno())


def _bound_lease(binding, claim_hash=None, *, action):
    """Atomically bind a single request/claim to a cooperative local lease."""
    import re
    if (type(binding) is not str or not re.fullmatch(r'[0-9a-f]{64}', binding)
            or (claim_hash is not None and
                (type(claim_hash) is not str or not re.fullmatch(r'[0-9a-f]{64}', claim_hash)))):
        raise ValueError('TREE_BINDING_REJECTED')
    lease = _ACTIVE_LEASE.get()
    if lease is None:
        raise RuntimeError('EXPECTED_LOCK_REQUIRED')
    lock, owned = lease
    with _guard(lock.parent):
        stored = json.loads(lock.read_bytes())
        if stored != owned or stored.get('pid') != os.getpid() or process_identity(os.getpid()) != stored.get('process_identity'):
            raise RuntimeError('LOCK_CHANGED')
        if action == 'begin':
            if stored.get('recovery_only',False) is not False or stored.get('recovery_required',False) is not False:
                raise RuntimeError('RECOVERY_ONLY_NO_NEW_TREE')
            if stored.get('tree_state') not in ('not_started', 'verified_closed'):
                raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
            if stored.get('tree_binding') == binding and stored.get('tree_aborted') is not True:
                raise RuntimeError('DUPLICATE_TREE_BINDING')
            # A separate durable fence survives a failed close-state fsync.
            # It is never removed unless the close-state fsync succeeded.
            _create_tree_fence(lock, stored['token'])
            attempt = uuid.uuid4().hex
            updated = dict(stored, tree_state='unverified', tree_binding=binding, tree_claim_hash=None,
                           tree_attempt=attempt)
            updated.pop('tree_aborted', None)
            updated.pop('tree_generic_token', None)
        elif action == 'claim':
            if (stored.get('tree_state') != 'unverified' or stored.get('tree_binding') != binding
                    or 'tree_claim_hash' not in stored or stored['tree_claim_hash'] is not None
                    or claim_hash is None):
                raise RuntimeError('TREE_CLAIM_BINDING_MISMATCH')
            updated = dict(stored, tree_claim_hash=claim_hash)
            updated.pop('tree_attempt', None)
        else:
            raise ValueError('TREE_ACTION_REJECTED')
        # On a partial write or failed fsync, in-memory cleanup must fail closed.
        owned.clear(); owned.update(updated)
        _write_state(lock, updated)
        if action == 'begin':
            return attempt


def begin_bound_tree(binding):
    return _bound_lease(binding, action='begin')


def abort_unclaimed_tree(binding, attempt):
    """Close only a proven pre-dispatch attempt; no ledger or budget changes."""
    lease = _ACTIVE_LEASE.get()
    if lease is None or type(attempt) is not str or not attempt:
        raise RuntimeError('TREE_ATTEMPT_REJECTED')
    lock, owned = lease
    with _guard(lock.parent):
        stored = json.loads(lock.read_bytes())
        if (stored != owned or stored.get('pid') != os.getpid()
                or process_identity(os.getpid()) != stored.get('process_identity')
                or stored.get('schema_version') != 3
                or stored.get('tree_state') != 'unverified'
                or stored.get('tree_binding') != binding
                or stored.get('tree_claim_hash', 'missing') is not None
                or stored.get('tree_attempt') != attempt):
            raise RuntimeError('TREE_ATTEMPT_REJECTED')
        fence = _tree_fence(lock)
        if fence.read_text(encoding='utf-8') != stored['token']:
            raise RuntimeError('TREE_FENCE_IDENTITY_MISMATCH')
        updated = dict(stored, tree_state='verified_closed', tree_aborted=True)
        updated.pop('tree_attempt', None)
        _write_state(lock, updated)
        owned.clear(); owned.update(updated)
        fence.unlink()


def bind_tree_claim(binding, claim_hash):
    _bound_lease(binding, claim_hash, action='claim')


def mark_tree(state, *, binding=None, claim_hash=None, tree_token=None):
    if state not in {'unverified', 'verified_closed'}:
        raise ValueError('INVALID_TREE_STATE')
    lease = _ACTIVE_LEASE.get()
    if lease is not None:
        lock, owned = lease
        with _guard(lock.parent):
            stored = json.loads(lock.read_bytes())
            if stored != owned:
                raise RuntimeError('LOCK_CHANGED')
            generic = binding is None and claim_hash is None
            updated = dict(owned, tree_state=state)
            if generic:
                if state == 'unverified':
                    if stored.get('recovery_only',False) is not False or stored.get('recovery_required',False) is not False:
                        raise RuntimeError('RECOVERY_ONLY_NO_NEW_TREE')
                    if tree_token is not None or stored['tree_state'] not in ('not_started','verified_closed'):
                        raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
                    if os.path.lexists(_tree_fence(lock)):
                        raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
                    tree_token=uuid.uuid4().hex
                    updated.pop('tree_binding',None); updated.pop('tree_claim_hash',None)
                    updated['tree_generic_token']=tree_token
                elif (type(tree_token) is not str or tree_token != stored.get('tree_generic_token')
                      or stored['tree_state'] != 'unverified'):
                    raise RuntimeError('TREE_CLAIM_BINDING_MISMATCH')
            elif 'tree_binding' in stored:
                if (tree_token is not None or binding != stored['tree_binding'] or claim_hash is None
                      or claim_hash != stored.get('tree_claim_hash')):
                    raise RuntimeError('TREE_CLAIM_BINDING_MISMATCH')
            else:
                raise RuntimeError('LEGACY_TREE_BINDING_MISSING')
            fence = _tree_fence(lock)
            if state == 'unverified' and stored['tree_state'] in ('not_started','verified_closed') and not os.path.lexists(fence):
                _create_tree_fence(lock, stored['token'])
            if fence.read_text(encoding='utf-8') != stored['token']:
                raise RuntimeError('TREE_FENCE_IDENTITY_MISMATCH')
            # Unverified is recorded before attempting its durable write.
            if state == 'unverified':
                owned.clear(); owned.update(updated)
            _write_state(lock, updated)
            owned['tree_state'] = state
            if state == 'verified_closed':
                fence.unlink()
            if generic and state == 'unverified':
                return tree_token


@contextmanager
def exclusive_lock(runtime):
    runtime = Path(runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    lock = runtime / 'supervisor.lock'
    # v3 prevents older v2 recovery code from treating the new sidecar as optional.
    owned = {'schema_version': 3, 'pid': os.getpid(),
             'started_at': datetime.now(timezone.utc).isoformat(),
             'process_identity': process_identity(os.getpid()),
             'token': uuid.uuid4().hex, 'tree_state': 'not_started'}
    with _guard(runtime):
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(owned, handle)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException as error:
            # An incomplete lock remains blocked for explicit operator investigation.
            error.add_note('LOCK_INITIALIZATION_UNVERIFIED')
            raise
    token = _ACTIVE_LEASE.set((lock, owned))
    primary = None
    try:
        yield owned
    except BaseException as error:
        primary = error
        raise
    finally:
        _ACTIVE_LEASE.reset(token)
        try:
            with _guard(runtime):
                stored = json.loads(lock.read_bytes())
                if stored != owned:
                    raise RuntimeError('LOCK_CHANGED')
                if owned['tree_state'] not in {'not_started', 'verified_closed'}:
                    raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
                if os.path.lexists(_tree_fence(lock)):
                    raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
                lock.unlink()
        except BaseException as error:
            if primary is not None:
                primary.add_note('LOCK_CLEANUP_FAILED')
            else:
                raise


def recover_lock(runtime, expected_token):
    """Explicit only. Legacy locks or unverified associated trees remain blocked."""
    runtime = Path(runtime)
    with _guard(runtime):
        lock = runtime / 'supervisor.lock'
        raw = lock.read_bytes()
        state = json.loads(raw)
        pid = state.get('pid')
        if (state.get('schema_version') not in (2, 3) or not expected_token or
                state.get('token') != expected_token or
                not isinstance(state.get('process_identity'), str) or not state['process_identity'] or
                not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0):
            raise RuntimeError('LOCK_IDENTITY_UNPROVEN')
        if process_identity(pid) == state['process_identity']:
            raise RuntimeError('ORIGINAL_PROCESS_STILL_ALIVE')
        if state.get('tree_state') not in {'not_started', 'verified_closed'}:
            raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
        if os.path.lexists(_tree_fence(lock)):
            raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
        if lock.read_bytes() != raw:
            raise RuntimeError('LOCK_CHANGED')
        lock.unlink()
        return {'recovered': True, 'token': expected_token, 'tree_state': state['tree_state']}
