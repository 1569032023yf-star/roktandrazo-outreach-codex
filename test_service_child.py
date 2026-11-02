"""真实Windows服务子进程Job监督 / Real Windows service child Job supervision."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from autonomy.build_dev_disabled_host import build_development

@unittest.skipUnless(os.name=='nt','Windows only')
class ServiceChildTests(unittest.TestCase):
    def test_real_suspended_job_launch_and_descendant_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);build_development(root/'dev','1b527d557674a4abd18a389c56851b6164c45dc5')
            service=root/'dev/service';script=root/'child.py';marker=root/'pids.json';config=root/'runtime.json'
            script.write_text('import subprocess,sys,os,time,json\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(120)"])\nPath(sys.argv[1]).write_text(json.dumps([os.getpid(),p.pid]))\ntime.sleep(120)\n')
            # ServiceChild passes the exact runtime-config path as argv[1].
            config.write_text('{}');script.write_text(script.read_text().replace('Path(sys.argv[1])','Path('+repr(str(marker))+')'))
            sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
            supervisor=root/'supervisor.json';supervisor.write_text(json.dumps(dict(schema='rokt.u1-supervisor.v1',inventory_id='1784775229336',python=sys.executable,python_sha256=sha(sys.executable),bootstrap=str(script),bootstrap_sha256=sha(script),runtime_config=str(config),runtime_config_sha256=sha(config))))
            harness=service/'Harness.cs';harness.write_text('using System;using System.IO;using System.Threading;class Harness { static int Main(string[] a) { using(var c=ServiceChild.FromConfig(a[0])) { for(int i=0;i<500 && !File.Exists(a[1]);i++) Thread.Sleep(10); if(!File.Exists(a[1]) || c.HasExited) return 2; } Console.WriteLine("JOB_TREE_CLEANED");return 0; }}')
            compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe';exe=service/'Harness.exe'
            subprocess.run([str(compiler),'/nologo','/reference:'+str(service/'RoktU1Bridge.exe'),'/out:'+str(exe),str(harness)],check=True,capture_output=True,timeout=30)
            r=subprocess.run([str(exe),str(supervisor),str(marker)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=20)
            self.assertEqual(r.returncode,0,r.stderr);self.assertIn('JOB_TREE_CLEANED',r.stdout)
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            for pid in json.loads(marker.read_text()):
                h=kernel.OpenProcess(0x100000,False,pid)
                if h:
                    try:self.assertEqual(kernel.WaitForSingleObject(h,1000),0)
                    finally:kernel.CloseHandle(h)
            c=json.loads(supervisor.read_text());c['bootstrap_sha256']='0'*64;supervisor.write_text(json.dumps(c));marker.unlink()
            r=subprocess.run([str(exe),str(supervisor),str(marker)],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=20)
            self.assertNotEqual(r.returncode,0);self.assertFalse(marker.exists())

if __name__=='__main__':unittest.main()
