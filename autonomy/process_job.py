"""Bounded process trees / 有界进程树；Windows uses a kill-on-close Job Object."""
from __future__ import annotations

import os
import subprocess
import tempfile
import time


def run_tree(args, *, timeout, cwd=None):
    if os.name == 'nt':
        return _windows_job(args, timeout, cwd)
    import signal
    with subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        # Do not allow tool descendants to outlive a successfully exited parent.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return subprocess.CompletedProcess(args, process.returncode,
            stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace'))


def _windows_job(args, timeout, cwd):
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

    job = checked(k.CreateJobObjectW(None, None))
    info = PROCESS_INFORMATION()
    try:
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        checked(k.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)))
        # Only temporary, unlinked output captures; nothing is retained in audit logs.
        with open(os.devnull, 'rb') as input_file, tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
            handles = [msvcrt.get_osfhandle(f.fileno()) for f in (input_file, output, error)]
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            startup = STARTUPINFO()
            startup.cb = c.sizeof(startup)
            startup.dwFlags = 0x100  # STARTF_USESTDHANDLES
            startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
            command = c.create_unicode_buffer(subprocess.list2cmdline(args))
            # Suspend before assigning to the job: descendants cannot escape assignment.
            checked(k.CreateProcessW(None, command, None, None, True, 0x4 | 0x08000000,
                None, str(cwd) if cwd else None, c.byref(startup), c.byref(info)))
            try:
                checked(k.AssignProcessToJobObject(job, info.hProcess))
                if k.ResumeThread(info.hThread) == 0xFFFFFFFF:
                    raise c.WinError(c.get_last_error())
                wait = k.WaitForSingleObject(info.hProcess, int(timeout * 1000))
                if wait not in (0, 258):
                    raise c.WinError(c.get_last_error())
                timed_out = wait == 258
                checked(k.TerminateJobObject(job, 124 if timed_out else 0))
                deadline = time.monotonic() + 10
                while True:
                    accounting = ACCOUNTING()
                    checked(k.QueryInformationJobObject(job, 1, c.byref(accounting), c.sizeof(accounting), None))
                    if accounting.ActiveProcesses == 0:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('PROCESS_TREE_CLEANUP_UNVERIFIED')
                    time.sleep(0.02)
                if timed_out:
                    raise subprocess.TimeoutExpired(args, timeout)
                code = w.DWORD()
                checked(k.GetExitCodeProcess(info.hProcess, c.byref(code)))
                output.seek(0)
                error.seek(0)
                return subprocess.CompletedProcess(args, code.value,
                    output.read().decode('utf-8', errors='replace'),
                    error.read().decode('utf-8', errors='replace'))
            finally:
                # Also fail closed on assignment failure while the process is suspended.
                k.TerminateProcess(info.hProcess, 125)
                k.WaitForSingleObject(info.hProcess, 10000)
    finally:
        if info.hThread:
            k.CloseHandle(info.hThread)
        if info.hProcess:
            k.CloseHandle(info.hProcess)
        k.CloseHandle(job)
