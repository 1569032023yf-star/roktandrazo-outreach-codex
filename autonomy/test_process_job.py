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

    @unittest.skipUnless(os.name == 'nt', 'Windows API failure injection')
    def test_windows_assignment_and_query_failures(self):
        import ctypes
        real_dll = ctypes.WinDLL
        for name in ('AssignProcessToJobObject', 'QueryInformationJobObject', 'WaitForSingleObject'):
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
