"""Pre-Python integrity admission / Python启动前完整性准入，无服务安装。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from autonomy.build_dev_disabled_host import build_development
from publisher_channel.install_inputs import InstallInputPins,pin_python_runtime


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@unittest.skipUnless(os.name=='nt','Windows handle tests')
class RuntimeContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory()
        source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        build_development(Path(cls.build.name)/'host',source)
        cls.exe=Path(cls.build.name)/'host/service/RoktU1Bridge.exe'

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'python';self.root.mkdir()
        for name,data in {'python.exe':b'fixture exe','python313.dll':b'fixture dll',
                          'Lib/core.py':b'VALUE=1','Lib/__init__.py':b'',
                          'Lib/GMT+0':b'legitimate timezone data'}.items():
            p=self.root/name;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
        self.manifest=self.root/'U1_RUNTIME_CONTENT.json'
        self.data=dict(schema='rokt.u1-runtime-content.v1',python='python.exe',
                       files={p.relative_to(self.root).as_posix():sha(p) for p in self.root.rglob('*') if p.is_file()})
        self.manifest.write_text(json.dumps(self.data),encoding='utf-8');self.digest=sha(self.manifest)

    def tearDown(self):
        self.temp.cleanup()

    def native(self,digest=None):
        return subprocess.run([str(self.exe),'--validate-runtime',str(self.manifest),digest or self.digest,
                               str(self.root/'python.exe')],capture_output=True,text=True,timeout=20)

    def test_matching_tree_native_and_publisher(self):
        self.assertEqual(self.native().returncode,0)
        with InstallInputPins() as pins:
            pin_python_runtime(pins,str(self.manifest),self.digest,str(self.root/'python.exe'))
            with self.assertRaises(PermissionError):
                (self.root/'python313.dll').write_bytes(b'tamper while held')
            pins.revalidate()

    def test_dll_and_standard_library_tamper_rejected_before_launch(self):
        for name in ('python313.dll','Lib/core.py'):
            p=self.root/name;before=p.read_bytes();p.write_bytes(b'tampered')
            self.assertNotEqual(self.native().returncode,0)
            with InstallInputPins() as pins:
                with self.assertRaises(ValueError):
                    pin_python_runtime(pins,str(self.manifest),self.digest,str(self.root/'python.exe'))
            p.write_bytes(before)

    def test_unlisted_import_hook_and_manifest_hash_rejected(self):
        self.assertNotEqual(self.native('0'*64).returncode,0)
        (self.root/'extra.pth').write_bytes(b'unlisted startup hook')
        self.assertNotEqual(self.native().returncode,0)
        with InstallInputPins() as pins:
            with self.assertRaisesRegex(ValueError,'UNMANAGED'):
                pin_python_runtime(pins,str(self.manifest),self.digest,str(self.root/'python.exe'))

    def test_traversal_and_duplicate_case_rejected(self):
        for name in ('../outside.py','PYTHON.EXE'):
            data=dict(self.data,files=dict(self.data['files'],**{name:'a'*64}))
            self.manifest.write_text(json.dumps(data),encoding='utf-8');digest=sha(self.manifest)
            self.assertNotEqual(self.native(digest).returncode,0)
            with InstallInputPins() as pins:
                with self.assertRaises(ValueError):
                    pin_python_runtime(pins,str(self.manifest),digest,str(self.root/'python.exe'))

    def test_provision_v2_emits_bound_supervisor_without_installing(self):
        token=self.root.parent/'token';token.write_bytes(b'offline fixture token')
        snapshot=self.root.parent/'snapshot';snapshot.write_bytes(b'offline fixture snapshot')
        plan=dict(schema='rokt.u1-provision-plan.v2',inventory_id='1784775229336',
                  python=str(self.root/'python.exe'),python_sha256=sha(self.root/'python.exe'),
                  release_root=str(self.root.parent),token_file=str(token),token_sha256=sha(token),
                  credential_expires_at=int(time.time())+3600,snapshot=str(snapshot),snapshot_sha256=sha(snapshot),
                  python_runtime_manifest=str(self.manifest),python_runtime_manifest_sha256=self.digest)
        path=self.root.parent/'plan.json';path.write_text(json.dumps(plan),encoding='utf-8')
        source=Path('autonomy/windows/Host-PackagePreparation.ps1').read_text(encoding='utf-8')
        helper=source[source.index('$dependencyPins='):source.index("try {\n$name=")]
        block=source[source.index('# Generate exact supervisor'):source.index('# The helper is manifest-hashed')]
        pre="param($RuntimePlan,$ApprovedRuntimePlanSha256)\n$ErrorActionPreference='Stop'\nfunction Assert-NoReparseAncestors($p) {}\n$code='C:\\Program Files\\RoktU1Bridge\\v1'\n$state='C:\\ProgramData\\RoktU1Bridge'\n$m=@{files=@(@{path='service/u1_bootstrap.py';sha256=('a'*64)})}\n"
        script=pre+helper+block+"\n[Text.Encoding]::UTF8.GetString($generated['config/supervisor.json'])\nforeach ($pin in $dependencyPins) {$pin.Dispose()}"
        command='& { '+script+" } '"+str(path).replace("'","''")+"' '"+sha(path)+"'"
        r=subprocess.run(['pwsh','-NoProfile','-Command',command],capture_output=True,text=True,
                         encoding='utf-8',errors='replace',timeout=20)
        self.assertEqual(r.returncode,0,r.stderr)
        supervisor=json.loads(r.stdout)
        self.assertEqual(supervisor['schema'],'rokt.u1-supervisor.v2')
        self.assertEqual(supervisor['python_runtime_manifest_sha256'],self.digest)
        self.assertEqual(supervisor['python_runtime_manifest'],str(self.manifest))


if __name__=='__main__':
    unittest.main()
