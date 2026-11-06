"""进程输出和清理回归 / Process output and cleanup regressions."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from autonomy import process_job as p


class ProcessTests(unittest.TestCase):
    def run_code(self, code, **kwargs):
        return p.run_tree([sys.executable, '-c', code], timeout=kwargs.pop('timeout', 3), **kwargs)

    def test_success_and_nonzero(self):
        result = self.run_code('import sys; print("ok"); print("err",file=sys.stderr);sys.exit(7)')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout.strip(), 'ok')
        self.assertEqual(result.stderr.strip(), 'err')

    def test_limits_each_stream_and_both(self):
        for targets in ('(1,)', '(2,)', '(1,2)'):
            with self.subTest(targets=targets):
                code = 'import os\nwhile True:\n for fd in '+targets+': os.write(fd,b"x"*100+b"\\n")'
                with self.assertRaises(p.OutputLimitExceeded) as caught:
                    self.run_code(code, stdout_limit_bytes=4096, stderr_limit_bytes=4096)
                self.assertEqual(caught.exception.outcome, 'UNKNOWN')
                self.assertTrue(caught.exception.cleanup_verified)

    def test_single_event_limit(self):
        with self.assertRaises(p.OutputLimitExceeded) as caught:
            self.run_code('import os,time;os.write(1,b"x"*20000);time.sleep(10)', event_limit_bytes=1024)
        self.assertTrue(caught.exception.cleanup_verified)

    def test_capture_memory_is_bounded(self):
        capture = p._Capture(100, 100, 100)
        with tempfile.TemporaryFile() as source:
            source.write(b'x'*50000)
            source.seek(0)
            capture.read(0, source)
        self.assertLessEqual(len(capture.data[0]), 100)
        self.assertIsInstance(capture.failure, p.OutputLimitExceeded)

    def test_timeout_and_success_remove_descendant(self):
        for timeout in (True, False):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as folder:
                marker = Path(folder)/'escaped'
                child = 'import time,pathlib;time.sleep(0.8);pathlib.Path('+repr(str(marker))+').write_text("bad")'
                code = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);'
                if timeout:
                    with self.assertRaises(subprocess.TimeoutExpired) as caught:
                        self.run_code(code+'time.sleep(10)', timeout=.2)
                    self.assertTrue(caught.exception.cleanup_verified)
                else:
                    self.run_code(code)
                time.sleep(1)
                self.assertFalse(marker.exists())

    def test_primary_failure_retained(self):
        original = subprocess.TimeoutExpired('child', 1)
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            p._finish(original, ['OSError'])
        self.assertIs(caught.exception, original)
        self.assertFalse(original.cleanup_verified)
        self.assertEqual(original.cleanup_errors, ('OSError',))

    def test_authority_denied_before_launch_has_no_child_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'forbidden'
            for denied in (False, None, 1, 'true'):
                with self.subTest(denied=denied), self.assertRaises(p.ProcessAuthorityLost):
                    self.run_code('from pathlib import Path;Path('+repr(str(marker))+').touch()',
                                  assert_live=lambda: denied)
                self.assertFalse(marker.exists())

    def test_lost_authority_kills_running_descendants_on_calling_thread(self):
        import threading
        from autonomy.lock_recovery import process_identity
        import json
        owner = threading.get_ident()
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'pids.json'
            def check():
                self.assertEqual(threading.get_ident(), owner)
                return not marker.exists()
            code = ('import subprocess,sys,time,json,os,pathlib;'
                    'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
                    'p=pathlib.Path('+repr(str(marker))+');'
                    'tmp=p.with_suffix(".tmp");tmp.write_text(json.dumps([os.getpid(),child.pid]));os.replace(tmp,p);'
                    'time.sleep(30)')
            with self.assertRaises(p.ProcessAuthorityLost) as caught:
                self.run_code(code, assert_live=check)
            self.assertTrue(caught.exception.cleanup_verified)
            for pid in json.loads(marker.read_text()):
                self.assertIsNone(process_identity(pid))

    def test_post_cleanup_check_prevents_false_success(self):
        # Even an immediately-exiting child requires a fresh final assertion.
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'done'
            with self.assertRaises(p.ProcessAuthorityLost) as caught:
                self.run_code('from pathlib import Path;Path('+repr(str(marker))+').touch()',
                              assert_live=lambda: not marker.exists())
            self.assertTrue(caught.exception.cleanup_verified)

    @unittest.skipUnless(os.name == 'nt', 'Windows API failure injection')
    def test_windows_assignment_and_query_failures(self):
        import ctypes
        real_dll = ctypes.WinDLL
        for name in ('IsProcessInJob', 'QueryInformationJobObject', 'WaitForSingleObject', 'UpdateProcThreadAttribute'):
            class Wrapper:
                def __init__(self, fn):
                    self.fn = fn
                    self.count = 0
                def __call__(self, *args):
                    self.count += 1
                    if self.count == 1:
                        return 0xFFFFFFFF if name == 'WaitForSingleObject' else 0
                    return self.fn(*args)
            dll = real_dll('kernel32', use_last_error=True)
            setattr(dll, name, Wrapper(getattr(dll, name)))
            with self.subTest(name=name), patch.object(ctypes, 'WinDLL', return_value=dll):
                with self.assertRaises((OSError, subprocess.TimeoutExpired)) as caught:
                    self.run_code('import time;time.sleep(10)', timeout=.1)
                if name == 'QueryInformationJobObject':
                    self.assertIsInstance(caught.exception, subprocess.TimeoutExpired)
                    self.assertFalse(caught.exception.cleanup_verified)
                else:
                    self.assertTrue(caught.exception.cleanup_verified)

    @unittest.skipUnless(os.name == 'nt', 'Windows creation-time Job containment')
    def test_creation_job_attribute_failure_prevents_launch(self):
        import ctypes
        dll = ctypes.WinDLL('kernel32', use_last_error=True)
        real_update = dll.UpdateProcThreadAttribute
        class RejectJob:
            def __call__(self, *args):
                if args[2] == 0x2000D:
                    return 0
                return real_update(*args)
        dll.UpdateProcThreadAttribute = RejectJob()
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'must-not-execute'
            with patch.object(ctypes, 'WinDLL', return_value=dll):
                with self.assertRaises(OSError) as caught:
                    self.run_code('from pathlib import Path;Path('+repr(str(marker))+').touch()')
            self.assertTrue(caught.exception.cleanup_verified)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows creation-time Job containment')
    def test_supervisor_death_immediately_after_creation_kills_suspended_child(self):
        import json
        from autonomy.lock_recovery import process_identity
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'created.json'
            effect = Path(folder) / 'must-not-execute'
            script = Path(folder) / 'supervisor.py'
            script.write_text(
                'import ctypes,sys,time,json\n'
                'from pathlib import Path\n'
                'from unittest.mock import patch\n'
                'from autonomy.process_job import run_tree\n'
                'dll=ctypes.WinDLL("kernel32",use_last_error=True)\n'
                'original=dll.CreateProcessW\n'
                'class PauseAfterCreate:\n'
                ' def __call__(self,*args):\n'
                '  result=original(*args)\n'
                '  if result:\n'
                '   Path(sys.argv[1]).write_text(json.dumps(args[-1]._obj.dwProcessId))\n'
                '   time.sleep(30)\n'
                '  return result\n'
                'dll.CreateProcessW=PauseAfterCreate()\n'
                'with patch.object(ctypes,"WinDLL",return_value=dll):\n'
                ' run_tree([sys.executable,"-c","from pathlib import Path;Path("+repr(sys.argv[2])+").touch()"],timeout=10)\n',
                encoding='utf-8')
            # Absolute script needs the repository explicitly on its import path.
            env = dict(os.environ, PYTHONPATH=str(Path.cwd()))
            supervisor = subprocess.Popen([sys.executable, '-B', str(script), str(marker), str(effect)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            child_handle = None
            try:
                deadline = time.monotonic() + 10
                while not marker.exists() and supervisor.poll() is None and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(marker.exists(), 'creation hook did not run')
                pid = json.loads(marker.read_text())
                self.assertIsNotNone(process_identity(pid))
                import ctypes
                from ctypes import wintypes
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel.OpenProcess.restype = wintypes.HANDLE
                kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                child_handle = kernel.OpenProcess(1, False, pid)
                self.assertTrue(child_handle)
                self.assertFalse(effect.exists())
                supervisor.kill(); supervisor.wait(timeout=10)
                deadline = time.monotonic() + 10
                while process_identity(pid) is not None and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertIsNone(process_identity(pid), 'suspended child survived supervisor death')
                self.assertFalse(effect.exists())
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                supervisor.communicate(timeout=10)
                if child_handle:
                    # Clean up the exact test child on assertion failure too;
                    # retaining a handle avoids terminating a reused PID.
                    kernel.TerminateProcess(child_handle, 125)
                    kernel.CloseHandle(child_handle)

    @unittest.skipUnless(os.name == 'nt', 'Windows handle inheritance')
    def test_only_declared_standard_handles_are_inherited(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as folder:
            sentinel=Path(folder)/'must-not-inherit.bin'
            with sentinel.open('wb') as stream:
                handle=msvcrt.get_osfhandle(stream.fileno())
                os.set_handle_inheritable(handle,True)
                code=('import ctypes as c;from ctypes import wintypes as w;'
                      'k=c.WinDLL("kernel32",use_last_error=True);'
                      'k.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD];'
                      'b=c.create_unicode_buffer(4096);'
                      'n=k.GetFinalPathNameByHandleW('+str(handle)+',b,4096,0);'
                      'print(b.value if n else "NOT_INHERITED")')
                result=self.run_code(code)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertNotIn(sentinel.name,result.stdout)
                self.assertTrue(result.cleanup_verified)


    def test_reader_close_failure_is_captured_and_primary_timeout_retained(self):
        original_read = p._Capture.read
        class CloseFailure:
            def __init__(self, stream): self.stream = stream
            def fileno(self): return self.stream.fileno()
            def close(self):
                self.stream.close()
                raise OSError('synthetic close failure')
        def failing_read(capture, index, stream):
            return original_read(capture, index, CloseFailure(stream))
        with patch.object(p._Capture, 'read', failing_read):
            with self.assertRaises(p.ProcessCleanupError) as success_case:
                self.run_code('print("done")')
            self.assertFalse(success_case.exception.cleanup_verified)
            self.assertIn('ProcessCleanupError', success_case.exception.cleanup_errors)
            self.assertIn('OUTPUT_STREAM_CLOSE_FAILED', success_case.exception.cleanup_errors)
            self.assertIn('OSError', success_case.exception.cleanup_errors)
            with self.assertRaises(subprocess.TimeoutExpired) as timeout_case:
                self.run_code('import time;time.sleep(10)', timeout=.15)
            self.assertFalse(timeout_case.exception.cleanup_verified)
            self.assertIn('ProcessCleanupError', timeout_case.exception.cleanup_errors)
            self.assertIn('OUTPUT_STREAM_CLOSE_FAILED', timeout_case.exception.cleanup_errors)
            self.assertIn('OSError', timeout_case.exception.cleanup_errors)

    def test_parent_and_child_pid_gone_after_timeout(self):
        from autonomy.lock_recovery import process_identity
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'pids.json'
            child = 'import time;time.sleep(30)'
            code = ('import subprocess,sys,time,json,os,pathlib;'
                    'child=subprocess.Popen([sys.executable,"-c",'+repr(child)+']);'
                    'pathlib.Path('+repr(str(marker))+').write_text(json.dumps([os.getpid(),child.pid]));'
                    'time.sleep(30)')
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                self.run_code(code, timeout=1)
            self.assertTrue(caught.exception.cleanup_verified)
            import json
            pids = json.loads(marker.read_text())
            for pid in pids:
                self.assertIsNone(process_identity(pid), 'surviving process PID '+str(pid))


if __name__ == '__main__':
    unittest.main()
