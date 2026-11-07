"""Exercise ServiceChild from the extracted release EXE; no service install."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

repo=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(repo))
from test_native_host_job import NativeHostJobTests
binary=repo/'extracted/payload/host/service/RoktU1Bridge.exe'
expected=sys.argv[1]
assert hashlib.sha256(binary.read_bytes()).hexdigest()==expected

class PackagedNativeJobTests(NativeHostJobTests):
    def build(self,mode='normal'):
        assert mode=='normal'
        copied=self.root/'RoktU1Bridge.exe'
        shutil.copyfile(binary,copied)
        assert hashlib.sha256(copied.read_bytes()).hexdigest()==expected
        harness=self.root/'Probe.cs'
        harness.write_text('using System; public class NativeJobProbe { public static int Main(string[] a) { try { using(var child=ServiceChild.FromConfig(a[0])) { Console.WriteLine("READY");Console.Out.Flush();Console.ReadLine(); } return 0; } catch(Exception e) { Console.WriteLine(e.Message);return 2; } } }')
        target=self.root/'Probe.exe'
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        result=subprocess.run([str(compiler),'/nologo','/target:exe','/platform:x64',
            '/reference:'+str(copied),'/reference:System.ServiceProcess.dll',
            '/reference:System.Web.Extensions.dll','/out:'+str(target),str(harness)],
            capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace'))
        return target

suite=unittest.TestSuite(PackagedNativeJobTests(name) for name in (
    'test_dispose_kills_real_child_and_grandchild',
    'test_parent_death_kills_real_child_and_grandchild'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
report=dict(binary_sha256=expected,tests=result.testsRun,passed=result.wasSuccessful(),
            production_service_started=False,production_installation=False,
            allow_install=False,allow_dispatch=False,SMTP=False)
print(json.dumps(report))
(repo/'PACKAGED_NATIVE.json').write_text(json.dumps(report,indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
