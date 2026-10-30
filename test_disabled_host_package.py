import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from autonomy.disabled_host_package import build_package, validate_inputs, PackageError, canonical, RUNTIME_PATHS


class DisabledPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-disabled-package-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.artifacts={
            'service/RoktU1Bridge.exe':b'MZsynthetic-not-an-executable',
            'runtime/dependencies.json':canonical(dict(schema='rokt.disabled-host-runtime.v1',framework='.NET Framework 4 x64',files={k:dict(path=v,sha256='a'*64,version='4.8.0.0') for k,v in RUNTIME_PATHS.items()})),
            'config/host.json':canonical(dict(schema='rokt.disabled-host-config.v1',inventory_id='1784775229336',service_name='RoktU1Bridge',allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,scheduler_created=False))}
        self.hashes={k:hashlib.sha256(v).hexdigest() for k,v in self.artifacts.items()}
    def test_real_staging_exact_files_and_no_install_authority(self):
        result=build_package(self.root/'package',self.artifacts,self.hashes,source_commit='a'*40)
        self.assertFalse(result['allow_install']);self.assertFalse(result['production_ready'])
        self.assertEqual(result['manifest']['start_type'],'Disabled')
        self.assertEqual(result['manifest']['account'],r'NT SERVICE\RoktU1Bridge')
        raw=(self.root/'package'/'manifest.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),result['manifest_sha256'])
        self.assertEqual(len(list((self.root/'package').rglob('*.*'))),6)
        with self.assertRaises(FileExistsError):build_package(self.root/'package',self.artifacts,self.hashes,source_commit='a'*40)
    def test_missing_or_changed_dependency_rejected_before_writes(self):
        for missing in self.artifacts:
            data=dict(self.artifacts);data.pop(missing)
            with self.assertRaises(PackageError):build_package(self.root/'out',data,self.hashes,source_commit='a'*40)
        changed=dict(self.artifacts);changed['service/RoktU1Bridge.exe']+=b'changed'
        with self.assertRaisesRegex(PackageError,'HASH_MISMATCH'):build_package(self.root/'out',changed,self.hashes,source_commit='a'*40)
        self.assertFalse((self.root/'out').exists())
    def test_paths_collisions_and_missing_approval_rejected(self):
        for path in ('runtime/../secret','runtime/CON.txt','runtime/x.','/runtime/x','runtime/x:y','runtime\\x'):
            data=dict(self.artifacts);data[path]=b'x';hashes={k:hashlib.sha256(v).hexdigest() for k,v in data.items()}
            with self.assertRaises(PackageError):validate_inputs(data,hashes,source_commit='a'*40)
        data=dict(self.artifacts);data['RUNTIME/dependencies.json']=b'x'
        with self.assertRaises(PackageError):validate_inputs(data,{k:hashlib.sha256(v).hexdigest() for k,v in data.items()},source_commit='a'*40)
        hashes=dict(self.hashes);hashes['service/RoktU1Bridge.exe']=None
        with self.assertRaisesRegex(PackageError,'APPROVED_HASH'):validate_inputs(self.artifacts,hashes,source_commit='a'*40)
    def test_enabled_config_rejected_even_with_matching_hash(self):
        for key in ('allow_dispatch','allow_cancel_dispatch','smtp_enabled','scheduler_created'):
            data=dict(self.artifacts);config=json.loads(data['config/host.json']);config[key]=True
            data['config/host.json']=canonical(config)
            with self.assertRaisesRegex(PackageError,'UNSAFE_HOST_CONFIG'):
                validate_inputs(data,{k:hashlib.sha256(v).hexdigest() for k,v in data.items()},source_commit='a'*40)
    @unittest.skipUnless(os.name=='nt','Windows compiler/parser test')
    def test_powershell_actual_parser_and_no_start_or_state_delete(self):
        scripts=Path(__file__).parent/'autonomy/windows'
        # Parser-only: never invoke the installer/rollback or their OS operations.
        code="param($root);foreach($p in Get-ChildItem -LiteralPath $root -Filter *.ps1){$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile($p.FullName,[ref]$t,[ref]$e)|Out-Null;if($e.Count){throw $e[0].Message}}"
        import base64
        code="$root='"+str(scripts).replace("'","''")+"';"+code.removeprefix('param($root);')
        encoded=base64.b64encode(code.encode('utf-16le')).decode('ascii')
        p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'))
        for script in scripts.glob('*.ps1'):
            text=script.read_text()
            self.assertNotIn('Start-Service',text);self.assertNotIn('Remove-Item',text)
            self.assertNotIn('LocalSystem',text);self.assertNotIn('BDExecutionHost',text)
    @unittest.skipUnless(os.name=='nt','Windows compiler test')
    def test_real_pe_compiles_and_config_cli_is_fail_closed(self):
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        target=self.root/'RoktU1Bridge.exe'
        p=subprocess.run([str(compiler),'/nologo','/target:exe','/platform:x64','/reference:System.ServiceProcess.dll','/reference:System.Web.Extensions.dll','/out:'+str(target),str(Path(__file__).parent/'autonomy/windows/RoktU1Bridge.cs')],capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(p.returncode,0,p.stdout.decode(errors='replace'))
        self.assertTrue(target.read_bytes().startswith(b'MZ'))
        for raw,code in ((self.artifacts['config/host.json'],0),(b'{}',2),(b'{"allow_dispatch":true}',2)):
            p=subprocess.run([str(target),'--validate-config'],input=raw,capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(p.returncode,code)
        p=subprocess.run([str(target),'--run-inventory'],capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(p.returncode,2)


if __name__=='__main__':unittest.main()
