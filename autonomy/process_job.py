"""Bounded process trees / 有界进程树：输出只存在有界内存中。"""
from __future__ import annotations
import os
import math
import subprocess
import threading
import time
import tempfile
import hashlib
import json
import secrets
from contextlib import ExitStack
from autonomy.process_control import MaintenanceControl


class OutputLimitExceeded(RuntimeError):
    reason = 'OUTPUT_LIMIT'
    outcome = 'UNKNOWN'


class ProcessCleanupError(RuntimeError):
    reason = 'PROCESS_TREE_CLEANUP_UNVERIFIED'
    outcome = 'UNKNOWN'


class ProcessAuthorityLost(RuntimeError):
    reason = 'PROCESS_AUTHORITY_LOST'
    outcome = 'UNKNOWN'


def _assert_live(assert_live):
    # Runs on the calling thread: SQLite maintenance connections are thread-bound.
    # Exceptions retain their cause; false/None/truthy objects are never grants.
    if assert_live is not None and assert_live() is not True:
        raise ProcessAuthorityLost('STOP_AND_PRESERVE_PROCESS_AUTHORITY_LOST')


class _Capture:
    def __init__(self, stdout_limit, stderr_limit, event_limit, control=None):
        self.limits = (stdout_limit, stderr_limit)
        self.event_limit = event_limit
        self.data = [bytearray(), bytearray()]
        self.threads = []
        self.failure = None
        self.cleanup_errors = []
        self.lock = control.lock if control is not None else threading.Lock()
        self.control = control

    def fail(self, error):
        with self.lock:
            if self.failure is None:
                self.failure = error
            if self.control is not None and self.control.failure is None:
                self.control.failure = error

    def start(self, streams):
        for index, stream in enumerate(streams):
            thread = threading.Thread(target=self.read, args=(index, stream), daemon=True)
            self.threads.append(thread)
            thread.start()

    def read(self, index, stream):
        line_size = 0
        total = 0
        pending = bytearray()
        try:
            while True:
                chunk = os.read(stream.fileno(), 8192)
                if not chunk:
                    break
                total += len(chunk)
                parts = chunk.split(b'\n')
                longest = max([line_size + len(parts[0])] + [len(p) for p in parts[1:]])
                line_size = line_size + len(chunk) if len(parts) == 1 else len(parts[-1])
                if total > self.limits[index] or longest > self.event_limit:
                    self.fail(OutputLimitExceeded('OUTPUT_LIMIT: ' + ('stdout' if index == 0 else 'stderr')))
                if self.failure is None:
                    self.data[index].extend(chunk)
                    if index == 0 and self.control is not None:
                        pending.extend(chunk)
                        while b'\n' in pending:
                            line, _, remaining = pending.partition(b'\n')
                            pending = bytearray(remaining)
                            self.control.offer(bytes(line).rstrip(b'\r'))
            if pending and self.control is not None:
                # Normal output may end without LF, but a control request may not.
                from autonomy.process_control import PREFIX, ControlProtocolError
                if pending.startswith(PREFIX):
                    raise ControlProtocolError('STOP_AND_PRESERVE_TORN_CONTROL')
        except BaseException as error:
            self.fail(error)
        finally:
            try:
                stream.close()
            except BaseException as error:
                with self.lock:
                    self.cleanup_errors.append(type(error).__name__)

    def finish(self, timeout):
        deadline = time.monotonic() + timeout
        for thread in self.threads:
            thread.join(max(0, deadline - time.monotonic()))
        if self.cleanup_errors:
            error = ProcessCleanupError('OUTPUT_STREAM_CLOSE_FAILED')
            error.reason = 'OUTPUT_STREAM_CLOSE_FAILED'
            error.cleanup_errors = tuple(self.cleanup_errors)
            raise error
        if any(thread.is_alive() for thread in self.threads):
            raise ProcessCleanupError('OUTPUT_READERS_CLEANUP_UNVERIFIED')

    def result(self, args, code):
        return subprocess.CompletedProcess(args, code, *(bytes(x).decode('utf-8', errors='replace') for x in self.data))


def _cleanup_codes(step, error):
    # Fixed classifications only; never persist exception messages or child output.
    codes = [step, type(error).__name__]
    reason = getattr(error, 'reason', None)
    if reason in {'OUTPUT_STREAM_CLOSE_FAILED', 'PROCESS_TREE_CLEANUP_UNVERIFIED'}:
        codes.append(reason)
    codes.extend(code for code in getattr(error, 'cleanup_errors', ())
                 if isinstance(code, str) and code.isidentifier())
    return codes


def _finish(primary, cleanup_errors):
    if primary is None and cleanup_errors:
        primary = ProcessCleanupError('PROCESS_TREE_CLEANUP_UNVERIFIED')
    if primary is not None:
        primary.cleanup_verified = not cleanup_errors
        primary.cleanup_errors = tuple(cleanup_errors)
        raise primary


def run_tree(args, *, timeout, cwd=None, stdout_limit_bytes=4*1024*1024,
             stderr_limit_bytes=1024*1024, event_limit_bytes=256*1024,
             cleanup_timeout=10, stdin_bytes=None, assert_live=None, maintenance_handler=None,
             lifecycle=None, env=None):
    """Supervise a tree; an optional trusted authority check must return True.

    Checks precede launch, precede Windows resume, run during execution and
    follow verified tree cleanup. Failure kills the tree, never releases a lease.
    This is a parent watchdog, not a replacement for per-mutation child checks.
    """
    if assert_live is not None and not callable(assert_live):
        raise ValueError('Callable live authority required')
    if lifecycle is not None and (not callable(lifecycle) or os.name!='nt' or
            not isinstance(args,(list,tuple)) or not args or not all(type(x) is str for x in args) or
            not os.path.isabs(args[0])):
        raise ValueError('Windows lifecycle requires absolute executable and callable durable sink')
    if maintenance_handler is not None and (not callable(maintenance_handler) or stdin_bytes is not None):
        raise ValueError('Private maintenance control requires callable handler and exclusive stdin')
    for value in (stdout_limit_bytes, stderr_limit_bytes, event_limit_bytes):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError('Output byte limits must be positive integers')
    # Keep Windows DWORD waits finite and match the backend wall bound.
    if any(type(value) not in (int, float) or not 0 < value <= 3600 or not math.isfinite(value)
           for value in (timeout, cleanup_timeout)):
        raise ValueError('Timeouts must be finite positive numbers at most 3600 seconds')
    if env is not None:
        if not isinstance(env, dict) or any(type(k) is not str or type(v) is not str or not k or '=' in k or '\x00' in k or '\x00' in v for k, v in env.items()):
            raise ValueError('Environment must contain valid string keys and values')
        if os.name == 'nt' and len({k.upper() for k in env}) != len(env):
            raise ValueError('Environment keys must be case insensitive unique')
        env = dict(env)
    _assert_live(assert_live)
    if stdin_bytes is not None and (type(stdin_bytes) is not bytes or len(stdin_bytes)>65536):
        raise ValueError('Bounded bytes input required')
    # Bounded temporary stdin handle, deleted on close; no tokens in argv.
    # Windows may back this with a named temporary file; production ACL remains required.
    with ExitStack() as stack:
        control = None
        if maintenance_handler is None:
            input_stream = stack.enter_context(tempfile.TemporaryFile())
            if stdin_bytes is not None:
                input_stream.write(stdin_bytes);input_stream.seek(0)
        else:
            read_fd, write_fd = os.pipe()
            input_stream = stack.enter_context(os.fdopen(read_fd, 'rb', buffering=0))
            writer = stack.enter_context(os.fdopen(write_fd, 'wb', buffering=0))
            # A child that sends checks without consuming acknowledgements must
            # never block the supervising thread or defeat its timeout/cleanup.
            os.set_blocking(write_fd, False)
            control = MaintenanceControl(maintenance_handler, writer)
        capture = _Capture(stdout_limit_bytes, stderr_limit_bytes, event_limit_bytes, control)
        def tick():
            _assert_live(assert_live)
            if capture.failure is not None:
                raise capture.failure
            if control is not None:
                control.poll()
            return True
        if os.name == 'nt':
            result = _windows_job(args, timeout, cwd, capture, cleanup_timeout, input_stream, tick, lifecycle, env)
        else:
            result = _posix_tree(args, timeout, cwd, capture, cleanup_timeout, input_stream, tick, env)
        try:
            _assert_live(assert_live)
            if control is not None:
                control.assert_drained()
        except BaseException as error:
            # Reaching here means the entire tree and output readers are gone.
            _finish(error, [])
        return result


def _posix_cleanup(process, timeout):
    import signal
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=timeout)
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        if time.monotonic() >= deadline:
            raise ProcessCleanupError('PROCESS_GROUP_CLEANUP_UNVERIFIED')
        time.sleep(0.02)


def _posix_tree(args, timeout, cwd, capture, cleanup_timeout, input_stream, assert_live=None, env=None):
    process = subprocess.Popen(args, cwd=cwd, stdin=input_stream,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, env=env)
    primary = None
    errors = []
    try:
        capture.start((process.stdout, process.stderr))
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            _assert_live(assert_live)
            if capture.failure:
                raise capture.failure
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(args, timeout)
            time.sleep(0.01)
    except BaseException as error:
        primary = error
    finally:
        for step, action in (('PROCESS_GROUP_CLEANUP', lambda: _posix_cleanup(process, cleanup_timeout)),
                             ('OUTPUT_READERS_CLEANUP', lambda: capture.finish(cleanup_timeout))):
            try:
                action()
            except BaseException as error:
                errors.extend(_cleanup_codes(step, error))
    _finish(primary or capture.failure, errors)
    result = capture.result(args, process.returncode)
    result.cleanup_verified = True
    return result


def _windows_job(args, timeout, cwd, capture, cleanup_timeout, input_stream, assert_live=None, lifecycle=None, env=None):
    import ctypes as c
    from ctypes import wintypes as w
    import msvcrt

    class STARTUPINFO(c.Structure):
        _fields_ = [('cb', w.DWORD), ('lpReserved', w.LPWSTR), ('lpDesktop', w.LPWSTR),
            ('lpTitle', w.LPWSTR), ('dwX', w.DWORD), ('dwY', w.DWORD), ('dwXSize', w.DWORD),
            ('dwYSize', w.DWORD), ('dwXCountChars', w.DWORD), ('dwYCountChars', w.DWORD),
            ('dwFillAttribute', w.DWORD), ('dwFlags', w.DWORD), ('wShowWindow', w.WORD),
            ('cbReserved2', w.WORD), ('lpReserved2', c.POINTER(c.c_ubyte)),
            ('hStdInput', w.HANDLE), ('hStdOutput', w.HANDLE), ('hStdError', w.HANDLE)]

    class PROCESS_INFORMATION(c.Structure):
        _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE),
                    ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]

    class STARTUPINFOEX(c.Structure):
        _fields_ = [('StartupInfo', STARTUPINFO), ('lpAttributeList', c.c_void_p)]

    class BASIC_LIMIT(c.Structure):
        _fields_ = [('PerProcessUserTimeLimit', c.c_longlong), ('PerJobUserTimeLimit', c.c_longlong),
            ('LimitFlags', w.DWORD), ('MinimumWorkingSetSize', c.c_size_t),
            ('MaximumWorkingSetSize', c.c_size_t), ('ActiveProcessLimit', w.DWORD),
            ('Affinity', c.c_size_t), ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]

    class IO_COUNTERS(c.Structure):
        _fields_ = [(name, c.c_ulonglong) for name in ('ReadOperationCount', 'WriteOperationCount',
            'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class EXTENDED_LIMIT(c.Structure):
        _fields_ = [('BasicLimitInformation', BASIC_LIMIT), ('IoInfo', IO_COUNTERS),
            ('ProcessMemoryLimit', c.c_size_t), ('JobMemoryLimit', c.c_size_t),
            ('PeakProcessMemoryUsed', c.c_size_t), ('PeakJobMemoryUsed', c.c_size_t)]

    class ACCOUNTING(c.Structure):
        _fields_ = [('TotalUserTime', c.c_longlong), ('TotalKernelTime', c.c_longlong),
            ('ThisPeriodTotalUserTime', c.c_longlong), ('ThisPeriodTotalKernelTime', c.c_longlong),
            ('TotalPageFaultCount', w.DWORD), ('TotalProcesses', w.DWORD),
            ('ActiveProcesses', w.DWORD), ('TotalTerminatedProcesses', w.DWORD)]

    k = c.WinDLL('kernel32', use_last_error=True)
    k.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
    k.CreateJobObjectW.restype = w.HANDLE
    k.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
    k.SetInformationJobObject.restype = w.BOOL
    k.QueryInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p]
    k.QueryInformationJobObject.restype = w.BOOL
    k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    k.AssignProcessToJobObject.restype = w.BOOL
    k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    k.TerminateJobObject.restype = w.BOOL
    k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL,
        w.DWORD, c.c_void_p, w.LPCWSTR, c.c_void_p, c.POINTER(PROCESS_INFORMATION)]
    k.CreateProcessW.restype = w.BOOL
    k.InitializeProcThreadAttributeList.argtypes = [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)]
    k.InitializeProcThreadAttributeList.restype = w.BOOL
    k.UpdateProcThreadAttribute.argtypes = [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p,
                                          c.c_size_t, c.c_void_p, c.c_void_p]
    k.UpdateProcThreadAttribute.restype = w.BOOL
    k.DeleteProcThreadAttributeList.argtypes = [c.c_void_p]
    k.DeleteProcThreadAttributeList.restype = None
    k.ResumeThread.argtypes = [w.HANDLE]
    k.ResumeThread.restype = w.DWORD
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    k.WaitForSingleObject.restype = w.DWORD
    k.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    k.GetExitCodeProcess.restype = w.BOOL
    k.CloseHandle.argtypes = [w.HANDLE]
    k.CloseHandle.restype = w.BOOL
    k.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    k.TerminateProcess.restype = w.BOOL
    k.GetProcessTimes.argtypes = [w.HANDLE,c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME),c.POINTER(w.FILETIME)]
    k.GetProcessTimes.restype = w.BOOL
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
    k.QueryFullProcessImageNameW.restype = w.BOOL

    def checked(value):
        if not value:
            raise c.WinError(c.get_last_error())
        return value

    job = None
    info = PROCESS_INFORMATION()
    primary = None
    errors = []
    code = w.DWORD()
    assigned = False
    streams = []
    writes = []
    input_file = None
    attributes = None
    attributes_initialized = False
    contained = None
    try:
        job_name='Global\\RoktU1Install-'+secrets.token_hex(32) if lifecycle is not None else None
        if lifecycle is not None:
            payload=json.dumps(dict(args=list(args),cwd=str(cwd) if cwd else None),sort_keys=True,separators=(',',':')).encode()
            parent_times=[w.FILETIME() for _ in range(4)]
            checked(k.GetProcessTimes(w.HANDLE(-1),*(c.byref(t) for t in parent_times)))
            parent_created=(parent_times[0].dwHighDateTime<<32)|parent_times[0].dwLowDateTime
            if lifecycle(dict(phase='LAUNCH_INTENT',job_name=job_name,command_sha256=hashlib.sha256(payload).hexdigest(),
                              supervisor_pid=os.getpid(),supervisor_creation_filetime=parent_created)) is not True:
                raise ProcessCleanupError('DURABLE_LAUNCH_INTENT_REQUIRED')
        c.set_last_error(0)
        job = checked(k.CreateJobObjectW(None, job_name))
        if job_name is not None and c.get_last_error()==183:
            raise ProcessCleanupError('PROCESS_JOB_NAME_COLLISION')
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x2000
        checked(k.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)))
        input_file = input_stream
        for _ in range(2):
            read_fd, write_fd = os.pipe()
            streams.append(os.fdopen(read_fd, 'rb', buffering=0))
            writes.append(os.fdopen(write_fd, 'wb', buffering=0))
        handles = [msvcrt.get_osfhandle(f.fileno()) for f in (input_file, *writes)]
        for handle in handles:
            os.set_handle_inheritable(handle, True)
        extended = STARTUPINFOEX()
        size = c.c_size_t()
        k.InitializeProcThreadAttributeList(None, 1, 0, c.byref(size))
        if not size.value or size.value > 65536:
            raise ProcessCleanupError('PROCESS_HANDLE_LIST_SIZE')
        attributes = c.create_string_buffer(size.value)
        checked(k.InitializeProcThreadAttributeList(attributes, 1, 0, c.byref(size)))
        attributes_initialized = True
        allowed_handles = (w.HANDLE*len(handles))(*handles)
        checked(k.UpdateProcThreadAttribute(attributes, 0, 0x20002, allowed_handles,
                                           c.sizeof(allowed_handles), None, None))
        extended.lpAttributeList = c.cast(attributes, c.c_void_p)
        startup = extended.StartupInfo
        startup.cb = c.sizeof(extended)
        startup.dwFlags = 0x100
        startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
        command = c.create_unicode_buffer(subprocess.list2cmdline(args))
        environment = None
        flags = 0x4 | 0x08000000 | 0x80000
        if env is not None:
            block = '\x00'.join(k + '=' + v for k, v in sorted(env.items(), key=lambda row: row[0].upper())) + '\x00\x00'
            if len(block.encode('utf-16-le')) > 65534:
                raise ValueError('Windows environment is too large')
            environment = c.create_unicode_buffer(block)
            flags |= 0x400
        checked(k.CreateProcessW(args[0] if lifecycle is not None else None, command, None, None, True, flags,
            c.cast(environment, c.c_void_p) if environment is not None else None, str(cwd) if cwd else None, c.byref(extended), c.byref(info)))
        for stream in writes:
            stream.close()
        checked(k.AssignProcessToJobObject(job, info.hProcess))
        assigned = True
        capture.start(streams)
        if lifecycle is not None:
            times=[w.FILETIME() for _ in range(4)]
            checked(k.GetProcessTimes(info.hProcess,*(c.byref(t) for t in times)))
            image=c.create_unicode_buffer(32768);length=w.DWORD(len(image))
            checked(k.QueryFullProcessImageNameW(info.hProcess,0,image,c.byref(length)))
            contained=dict(phase='CONTAINED',job_name=job_name,pid=info.dwProcessId,
                           creation_filetime=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime,image=image.value)
            if lifecycle(contained) is not True:
                raise ProcessCleanupError('DURABLE_PROCESS_IDENTITY_REQUIRED')
        _assert_live(assert_live)
        if k.ResumeThread(info.hThread) == 0xFFFFFFFF:
            raise c.WinError(c.get_last_error())
        deadline = time.monotonic() + timeout
        while True:
            _assert_live(assert_live)
            if capture.failure:
                raise capture.failure
            wait = k.WaitForSingleObject(info.hProcess, 10)
            if wait == 0:
                checked(k.GetExitCodeProcess(info.hProcess, c.byref(code)))
                break
            if wait != 258:
                raise c.WinError(c.get_last_error())
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(args, timeout)
    except BaseException as error:
        primary = error
    finally:
        if attributes_initialized:
            k.DeleteProcThreadAttributeList(attributes)
        # Every failure, including suspended assignment failure, uses verified cleanup.
        if info.hProcess:
            try:
                if assigned:
                    checked(k.TerminateJobObject(job, 125))
                    deadline = time.monotonic() + cleanup_timeout
                    while True:
                        accounting = ACCOUNTING()
                        checked(k.QueryInformationJobObject(job, 1, c.byref(accounting), c.sizeof(accounting), None))
                        if accounting.ActiveProcesses == 0:
                            break
                        if time.monotonic() >= deadline:
                            raise ProcessCleanupError('JOB_CLEANUP_UNVERIFIED')
                        time.sleep(0.02)
                else:
                    checked(k.TerminateProcess(info.hProcess, 125))
                if k.WaitForSingleObject(info.hProcess, int(cleanup_timeout*1000)) != 0:
                    raise ProcessCleanupError('PARENT_CLEANUP_UNVERIFIED')
            except BaseException as error:
                errors.append(type(error).__name__)
        # Closing the job is a final kill-on-close fallback, but is not verification.
        for handle in (job, info.hThread, info.hProcess):
            if handle:
                try:
                    checked(k.CloseHandle(handle))
                except BaseException as error:
                    errors.append(type(error).__name__)
        for stream in [input_file, *writes]:
            if stream:
                try:
                    stream.close()
                except BaseException as error:
                    errors.append(type(error).__name__)
        try:
            capture.finish(cleanup_timeout)
        except BaseException as error:
            errors.extend(_cleanup_codes('OUTPUT_READERS_CLEANUP', error))
        if not capture.threads:
            for stream in streams:
                try:
                    stream.close()
                except BaseException as error:
                    errors.extend(_cleanup_codes('UNSTARTED_OUTPUT_CLOSE_FAILED', error))
    if lifecycle is not None and contained is not None and not errors:
        try:
            if lifecycle(dict(contained,phase='STOPPED',tree_empty=True,readers_closed=True)) is not True:
                raise ProcessCleanupError('DURABLE_PROCESS_STOP_REQUIRED')
        except BaseException as error:
            primary=primary or error
    _finish(primary or capture.failure, errors)
    result = capture.result(args, code.value)
    result.cleanup_verified = True
    return result
