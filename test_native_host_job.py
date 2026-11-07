"""Real x64 native host lifecycle checks; fixture children only, no SCM."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows native Job integration')
class NativeHostJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='u1-native-')
        self.root = Path(self.temp.name)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.children = []
        self.handles = []

    def tearDown(self):
        for p in self.children:
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=15)
        for h in self.handles:
            self.kernel.CloseHandle(h)
        self.temp.cleanup()

    def build(self, mode='normal'):
        source = (Path(__file__).parent / 'autonomy/windows/RoktU1Bridge.cs').read_text()
        if mode == 'suspended':
            source = source.replace('child.process=pi.process;',
                'child.process=pi.process;Console.WriteLine("SUSPENDED:"+pi.pid);Console.Out.Flush();Console.ReadLine();')
        if mode == 'unsupported':
            source = source.replace('new IntPtr(0x2000D)', 'new IntPtr(0x7FFFFFFF)')
        native = self.root / 'Host.cs'
        native.write_text(source)
        harness = self.root / 'Probe.cs'
        harness.write_text('using System; public class NativeJobProbe { public static int Main(string[] a) { try { using(var child=ServiceChild.FromConfig(a[0])) { Console.WriteLine("READY");Console.Out.Flush();Console.ReadLine(); } return 0; } catch(Exception e) { Console.WriteLine(e.Message);return 2; } } }')
        target = self.root / 'Probe.exe'
        compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        result = subprocess.run([str(compiler), '/nologo', '/target:exe', '/platform:x64',
            '/main:NativeJobProbe', '/reference:System.ServiceProcess.dll',
            '/reference:System.Web.Extensions.dll', '/out:'+str(target), str(native), str(harness)],
            capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace'))
        return target

    def config(self):
        marker = self.root / 'children.json'
        script = self.root / 'fixture.py'
        script.write_text("import json,os,subprocess,sys,time\np=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(120)'])\nopen(json.load(open(sys.argv[1]))['marker'],'w').write(json.dumps([os.getpid(),p.pid]))\ntime.sleep(120)\n")
        runtime_config = self.root / 'runtime.json'
        runtime_config.write_text(json.dumps(dict(marker=str(marker))))
        cfg = dict(schema='rokt.u1-supervisor.v1', inventory_id='1784775229336',
                   python=str(Path(sys.executable).resolve()), bootstrap=str(script), runtime_config=str(runtime_config))
        # Runtime config stays pinned; output is a separate fixture-only marker.
        marker.write_text('[]')
        for key in ('python','bootstrap','runtime_config'):
            cfg[key+'_sha256'] = hashlib.sha256(Path(cfg[key]).read_bytes()).hexdigest()
        path = self.root / 'supervisor.json'
        path.write_text(json.dumps(cfg))
        return path, marker

    def launch(self, target, config):
        p = subprocess.Popen([str(target), str(config)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.children.append(p)
        return p

    def observe(self, pid):
        handle = self.kernel.OpenProcess(0x100000, False, pid)
        self.assertTrue(handle, 'fixture child must exist before parent termination')
        self.handles.append(handle)
        return handle

    def test_dispose_kills_real_child_and_grandchild(self):
        p, handles = self.running_fixture()
        p.stdin.write('stop\n');p.stdin.flush()
        out, err = p.communicate(timeout=15)
        self.assertEqual(p.returncode, 0, out+err)
        for h in handles:
            self.assertEqual(self.kernel.WaitForSingleObject(h, 10000), 0)

    def running_fixture(self):
        target = self.build()
        config, marker = self.config()
        p = self.launch(target, config)
        self.assertEqual(p.stdout.readline().strip(), 'READY')
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                ids = json.loads(marker.read_text())
                if len(ids)==2:
                    return p, [self.observe(pid) for pid in ids]
            except (ValueError, OSError):
                pass
            time.sleep(.02)
        self.fail('fixture descendants not observed')

    def test_parent_death_kills_real_child_and_grandchild(self):
        p, handles = self.running_fixture()
        p.kill();p.communicate(timeout=15)
        for h in handles:
            self.assertEqual(self.kernel.WaitForSingleObject(h, 10000), 0)

    def test_parent_death_before_membership_check_kills_suspended_child(self):
        target = self.build('suspended')
        config, marker = self.config()
        p = self.launch(target, config)
        line = p.stdout.readline().strip()
        self.assertTrue(line.startswith('SUSPENDED:'), line)
        handle = self.observe(int(line.split(':')[1]))
        p.kill();p.communicate(timeout=15)
        self.assertEqual(self.kernel.WaitForSingleObject(handle, 10000), 0)
        self.assertEqual(json.loads(marker.read_text()), [])

    def test_unsupported_attribute_fails_before_child_creation(self):
        target = self.build('unsupported')
        config, marker = self.config()
        p = self.launch(target, config)
        out, err = p.communicate(timeout=15)
        self.assertEqual(p.returncode, 2, out+err)
        self.assertIn('JOB_ATTRIBUTE_BIND_FAILED', out)
        self.assertEqual(json.loads(marker.read_text()), [])


if __name__ == '__main__':
    unittest.main()
