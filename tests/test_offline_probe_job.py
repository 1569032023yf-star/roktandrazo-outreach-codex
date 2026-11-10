import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from autonomy.process_job import run_tree


class OfflineProbeJobTests(unittest.TestCase):
    def test_environment_is_exact_and_unicode_safe(self):
        env = {'SystemRoot': os.environ['SystemRoot']} if os.name == 'nt' else {}
        env['U1_TEST_VALUE'] = '\u6e2c\u8a66'
        result = run_tree([sys.executable, '-I', '-c',
                           "import os; print(ascii(os.environ['U1_TEST_VALUE'])); print('PYTHONPATH' in os.environ)"],
                          env=env, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), [ascii('\u6e2c\u8a66'), 'False'])

    def test_environment_rejects_ambiguous_or_malformed_names(self):
        for env in ({'bad=key': 'v'}, {'key': '\x00'}, {'': 'v'}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                run_tree([sys.executable, '-c', 'pass'], timeout=2, env=env)
        if os.name == 'nt':
            with self.assertRaises(ValueError):
                run_tree([sys.executable, '-c', 'pass'], timeout=2, env={'Path': 'a', 'PATH': 'b'})

    @unittest.skipUnless(os.name == 'nt', 'Windows Job Object proof')
    def test_timeout_kills_grandchild_holding_inherited_pipes(self):
        import ctypes
        from ctypes import wintypes
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            pidfile = Path(td) / 'pid'
            grandchild = "import os,pathlib,time,sys; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
            parent = ("import pathlib,subprocess,sys,time; "
                      "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); "
                      "p=pathlib.Path(sys.argv[2]); "
                      "exec('while not p.exists():\\n time.sleep(0.01)'); time.sleep(30)")
            start = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                run_tree([sys.executable, '-I', '-c', parent, grandchild, str(pidfile)], timeout=2)
            self.assertTrue(caught.exception.cleanup_verified)
            self.assertLess(time.monotonic() - start, 8)
            self.assertTrue(pidfile.exists(), 'grandchild did not start before deadline')
            pid = int(pidfile.read_text())
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x100000, False, pid)
            if handle:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0, 'grandchild is still alive')
                finally:
                    kernel.CloseHandle(handle)


if __name__ == '__main__':
    unittest.main()
