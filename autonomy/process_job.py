"""Bounded process trees / 有界进程树：输出只存在有界内存中。"""
from __future__ import annotations
import os
import subprocess
import threading
import time


class OutputLimitExceeded(RuntimeError):
    reason = 'OUTPUT_LIMIT'
    outcome = 'UNKNOWN'


class ProcessCleanupError(RuntimeError):
    reason = 'PROCESS_TREE_CLEANUP_UNVERIFIED'
    outcome = 'UNKNOWN'


class _Capture:
    def __init__(self, stdout_limit, stderr_limit, event_limit):
        self.limits = (stdout_limit, stderr_limit)
        self.event_limit = event_limit
        self.data = [bytearray(), bytearray()]
        self.threads = []
        self.failure = None
        self.cleanup_errors = []
        self.lock = threading.Lock()

    def fail(self, error):
        with self.lock:
            if self.failure is None:
                self.failure = error

    def start(self, streams):
        for index, stream in enumerate(streams):
            thread = threading.Thread(target=self.read, args=(index, stream), daemon=True)
            self.threads.append(thread)
            thread.start()

    def read(self, index, stream):
        line_size = 0
        total = 0
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
             cleanup_timeout=10):
    for value in (stdout_limit_bytes, stderr_limit_bytes, event_limit_bytes):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError('Output byte limits must be positive integers')
    if timeout <= 0 or cleanup_timeout <= 0:
        raise ValueError('Timeouts must be positive')
    capture = _Capture(stdout_limit_bytes, stderr_limit_bytes, event_limit_bytes)
    if os.name == 'nt':
        return _windows_job(args, timeout, cwd, capture, cleanup_timeout)
    return _posix_tree(args, timeout, cwd, capture, cleanup_timeout)


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


def _posix_tree(args, timeout, cwd, capture, cleanup_timeout):
    process = subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    primary = None
    errors = []
    try:
        capture.start((process.stdout, process.stderr))
        deadline = time.monotonic() + timeout
        while process.poll() is None:
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


def _windows_job(args, timeout, cwd, capture, cleanup_timeout):
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
        w.DWORD, c.c_void_p, w.LPCWSTR, c.POINTER(STARTUPINFO), c.POINTER(PROCESS_INFORMATION)]
    k.CreateProcessW.restype = w.BOOL
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
    try:
        job = checked(k.CreateJobObjectW(None, None))
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x2000
        checked(k.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)))
        input_file = open(os.devnull, 'rb')
        for _ in range(2):
            read_fd, write_fd = os.pipe()
            streams.append(os.fdopen(read_fd, 'rb', buffering=0))
            writes.append(os.fdopen(write_fd, 'wb', buffering=0))
        handles = [msvcrt.get_osfhandle(f.fileno()) for f in (input_file, *writes)]
        for handle in handles:
            os.set_handle_inheritable(handle, True)
        startup = STARTUPINFO()
        startup.cb = c.sizeof(startup)
        startup.dwFlags = 0x100
        startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
        command = c.create_unicode_buffer(subprocess.list2cmdline(args))
        checked(k.CreateProcessW(None, command, None, None, True, 0x4 | 0x08000000,
            None, str(cwd) if cwd else None, c.byref(startup), c.byref(info)))
        for stream in writes:
            stream.close()
        checked(k.AssignProcessToJobObject(job, info.hProcess))
        assigned = True
        capture.start(streams)
        if k.ResumeThread(info.hThread) == 0xFFFFFFFF:
            raise c.WinError(c.get_last_error())
        deadline = time.monotonic() + timeout
        while True:
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
    _finish(primary or capture.failure, errors)
    result = capture.result(args, code.value)
    result.cleanup_verified = True
    return result
