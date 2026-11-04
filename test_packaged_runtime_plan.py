"""Installed Python binding / 已安装Python路径绑定，仅临时配置生成。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(os.name=='nt','Windows paths')
class PackagedRuntimePlanTests(unittest.TestCase):
    def test_v3_config_binds_installed_runtime_and_rejects_external_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'package';runtime=package/'runtime/python';runtime.mkdir(parents=True)
            python=runtime/'python.exe';python.write_bytes(b'fixture not executable')
            manifest=runtime/'U1_RUNTIME_CONTENT.json';manifest.write_bytes(b'fixture manifest bytes')
            token=root/'token';token.write_bytes(b'offline fixture')
            snapshot=root/'snapshot';snapshot.write_bytes(b'offline snapshot')
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            plan=dict(schema='rokt.u1-provision-plan.v3',inventory_id='1784775229336',
                      python=str(python),python_sha256=digest(python),python_runtime_manifest=str(manifest),
                      python_runtime_manifest_sha256=digest(manifest),release_root=str(root),
                      token_file=str(token),token_sha256=digest(token),snapshot=str(snapshot),
                      snapshot_sha256=digest(snapshot),credential_expires_at=int(time.time())+3600)
            path=root/'plan.json';path.write_text(json.dumps(plan))
            source=Path('autonomy/windows/Host-PackagePreparation.ps1').read_text(encoding='utf-8')
            helper=source[source.index('$dependencyPins='):source.index("try {\n$name=")]
            block=source[source.index('# Generate exact supervisor'):source.index('# The helper is manifest-hashed')]
            script=root/'generate.ps1'
            script.write_text("param($RuntimePlan,$ApprovedRuntimePlanSha256,$package)\n$ErrorActionPreference='Stop'\n"
                "function Assert-NoReparseAncestors($p) {}\n$code='C:\\Program Files\\RoktU1Bridge\\v1'\n$state='C:\\ProgramData\\RoktU1Bridge'\n"
                "$m=@{schema='rokt.disabled-host-package.v2';files=@(@{path='service/u1_bootstrap.py';sha256=('a'*64)},"
                "@{path='runtime/python/python.exe';sha256='"+digest(python)+"'},"
                "@{path='runtime/python/U1_RUNTIME_CONTENT.json';sha256='"+digest(manifest)+"'})}\n"
                +helper+block+"\n[Text.Encoding]::UTF8.GetString($generated['config/supervisor.json'])\nforeach($pin in $dependencyPins){$pin.Dispose()}\n",encoding='utf-8-sig')
            def run():
                return subprocess.run(['pwsh','-NoProfile','-NonInteractive','-File',str(script),str(path),digest(path),str(package)],capture_output=True,text=True,encoding='utf-8',timeout=20)
            result=run();self.assertEqual(result.returncode,0,result.stderr)
            supervisor=json.loads(result.stdout)
            self.assertEqual(supervisor['python'],r'C:\Program Files\RoktU1Bridge\v1\runtime\python\python.exe')
            self.assertEqual(supervisor['python_runtime_manifest'],r'C:\Program Files\RoktU1Bridge\v1\runtime\python\U1_RUNTIME_CONTENT.json')
            self.assertEqual(supervisor['schema'],'rokt.u1-supervisor.v2')
            external=root/'python.exe';external.write_bytes(python.read_bytes())
            plan['python']=str(external);path.write_text(json.dumps(plan))
            bad=run();self.assertNotEqual(bad.returncode,0)
            self.assertIn('PYTHON_RUNTIME_MANIFEST_REQUIRED',bad.stderr)
