"""Actual request construction only / 仅验证真实请求生成，不执行安装。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from autonomy.host_file_transaction import HostFileTransaction, prepare_request, read


@unittest.skipUnless(os.name=='nt','Windows PowerShell request construction')
class HostInstallSourcesTests(unittest.TestCase):
    def test_actual_powershell_request_and_python_compensation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);package=root/'package';package.mkdir()
            (package/'service').mkdir();payload=package/'service/RoktU1Bridge.exe'
            payload.write_bytes(b'MZ isolated package fixture')
            code=root/'code';code.mkdir();audit=root/'audit';audit.mkdir()
            source=Path('autonomy/windows/Host-InstallTransaction.ps1').read_text(encoding='utf-8')
            block=source[source.index('        $fileBytes=@{}'):source.index("        Write-HostPhase 'FILES_INTENT'")]
            script=root/'request.ps1'
            script.write_text("param($package)\n$ErrorActionPreference='Stop'\n"
                "$m=@{source_commit=('a'*40);installer_version='1.1.1';files=@(@{path='service/RoktU1Bridge.exe';sha256=(Get-FileHash -LiteralPath (Join-Path $package 'service/RoktU1Bridge.exe')).Hash.ToLowerInvariant()})}\n"
                "$generated=@{'config/runtime.json'=[Text.Encoding]::UTF8.GetBytes('generated fixture')}\n"
                "$ApprovedManifestSha256='b'*64;$operation='c'*64;$name='RoktU1Bridge';$account='fixture';$image='fixture';$Upgrade=$false;$previous=$null\n"
                +block+"\n$request|ConvertTo-Json -Depth 12 -Compress\n",encoding='utf-8-sig')
            result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-File',str(script),str(package)],
                                  capture_output=True,text=True,encoding='utf-8',timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            request=json.loads(result.stdout);request['root_created']=False
            self.assertNotIn('service/RoktU1Bridge.exe',request['files'])
            self.assertEqual(request['file_sources']['service/RoktU1Bridge.exe']['sha256'],hashlib.sha256(payload.read_bytes()).hexdigest())
            transaction=HostFileTransaction(code,audit/'operation.jsonl')
            prepare_request(transaction,request);transaction.apply()
            self.assertEqual(read(code/'service/RoktU1Bridge.exe'),payload.read_bytes())
            self.assertEqual(read(code/'config/runtime.json'),b'generated fixture')
            receipt=json.loads(read(code/'config/installation.json'))
            self.assertEqual(receipt['wrapper_sha256'],hashlib.sha256(payload.read_bytes()).hexdigest())
            self.assertIn('service/RoktU1Bridge.exe',receipt['files'])
            transaction.rollback()
            self.assertFalse((code/'service/RoktU1Bridge.exe').exists())
