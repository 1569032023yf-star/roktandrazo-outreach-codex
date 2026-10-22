"""Conservative process-instance lock recovery / 保守的进程实例锁恢复。"""
import ctypes
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import uuid
import json
import os
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
    path = Path(runtime) / 'supervisor.recovery.lock'
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    primary = None
    try:
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup_error = None
        for action in (lambda: os.close(fd), lambda: path.unlink()):
            try:
                action()
            except OSError as error:
                cleanup_error = cleanup_error or error
                if primary is not None:
                    primary.add_note('RECOVERY_GUARD_CLEANUP_FAILED')
        if primary is None and cleanup_error is not None:
            raise cleanup_error


def _write_state(lock, state):
    # The original token is immutable; no timestamp/PID-only recovery is supported.
    with lock.open('w', encoding='utf-8') as handle:
        json.dump(state, handle)
        handle.flush()
        os.fsync(handle.fileno())


def mark_tree(state):
    if state not in {'unverified', 'verified_closed'}:
        raise ValueError('INVALID_TREE_STATE')
    lease = _ACTIVE_LEASE.get()
    if lease is not None:
        lock, owned = lease
        with _guard(lock.parent):
            stored = json.loads(lock.read_bytes())
            if stored.get('token') != owned['token']:
                raise RuntimeError('LOCK_CHANGED')
            updated = dict(owned, tree_state=state)
            _write_state(lock, updated)
            owned['tree_state'] = state


@contextmanager
def exclusive_lock(runtime):
    runtime = Path(runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    lock = runtime / 'supervisor.lock'
    owned = {'schema_version': 2, 'pid': os.getpid(),
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
                if stored.get('token') != owned['token']:
                    raise RuntimeError('LOCK_CHANGED')
                if owned['tree_state'] not in {'not_started', 'verified_closed'}:
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
        if (state.get('schema_version') != 2 or not expected_token or
                state.get('token') != expected_token or
                not isinstance(state.get('process_identity'), str) or not state['process_identity'] or
                not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0):
            raise RuntimeError('LOCK_IDENTITY_UNPROVEN')
        if process_identity(pid) == state['process_identity']:
            raise RuntimeError('ORIGINAL_PROCESS_STILL_ALIVE')
        if state.get('tree_state') not in {'not_started', 'verified_closed'}:
            raise RuntimeError('ASSOCIATED_TREE_UNVERIFIED')
        if lock.read_bytes() != raw:
            raise RuntimeError('LOCK_CHANGED')
        lock.unlink()
        return {'recovered': True, 'token': expected_token, 'tree_state': state['tree_state']}
