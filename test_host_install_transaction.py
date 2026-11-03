"""Actual coordinator/files with isolated SCM/ACL doubles / 隔离协调器与真实文件。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class HostInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-install-isolated-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.code=self.root/'code';self.state=self.root/'state';self.audit=self.root/'audit';self.audit.mkdir()
        self.package=self.root/'package';self.package.mkdir()
        helper=Path('autonomy/host_file_transaction.py').read_text(encoding='utf-8')
        helper=helper.replace("r'C:\\Program Files\\RoktU1Bridge\\v1'",repr(str(self.code))).replace("r'C:\\ProgramData\\RoktU1InstallAudit'",repr(str(self.audit))).replace("r'C:\\ProgramData\\RoktU1Bridge'",repr(str(self.state)))
        (self.package/'host_file_transaction.py').write_text(helper,encoding='utf-8')

    def run_coordinator(self, *, upgrade=False, recover=False, rollback=False, fail='', death='', manifest='a', previous=None, operation=None, authority=True, maintenance_fail='', authority_action=None):
        source=Path('autonomy/windows/Host-InstallTransaction.ps1').read_text(encoding='utf-8')
        source=source.replace("$audit='C:\\ProgramData\\RoktU1InstallAudit'","$audit="+self.q(self.audit))
        source=source.replace("$mutex=New-Object Threading.Mutex($false,'Global\\RoktU1BridgeInstall')", "$mutex=New-Object Threading.Mutex($false,'Local\\U1Test"+hashlib.sha256(str(self.root).encode()).hexdigest()+"')")
        source=source.replace("    $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())\n    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ADMINISTRATOR_REQUIRED' }",'    # Isolated fixture replaces only elevation admission; production source retains it.')
        source=source.replace("$sid=(New-Object Security.Principal.NTAccount($account)).Translate([Security.Principal.SecurityIdentifier])","$sid=[pscustomobject]@{Value='isolated-service-sid'}")
        source=source.replace("Write-AclRecord $log @{phase=$Phase;manifest=$ApprovedManifestSha256;operation_id=$operation;extra=$Extra}","Write-AclRecord $log @{phase=$Phase;manifest=$ApprovedManifestSha256;operation_id=$operation;extra=$Extra}; if ($Phase -ceq $death) {[Environment]::Exit(31)}")
        if maintenance_fail:
            source=source.replace("if ($Phase -ceq $death)","if ($Phase -ceq '"+maintenance_fail+"') {$script:authorityLost=$true}; if ($Phase -ceq $death)")
        service_file=self.root/'service.json'
        pre="$ErrorActionPreference='Stop'\n$code="+self.q(self.code)+"; $state="+self.q(self.state)+"; $package="+self.q(self.package)+"; $serviceFile="+self.q(service_file)+"; $RuntimePlan='isolated'; $name='RoktU1Bridge'; $account='NT SERVICE\\RoktU1Bridge'; $ApprovedManifestSha256='"+manifest*64+"'; $plan=@{python="+self.q(sys.executable)+"}; $generated=@{}; $fail="+self.q(fail)+"; $death="+self.q(death)+"\n"
        pre+=r'''
function Assert-AclAuditRoot($p) {if (-not (Test-Path $p)) {throw 'AUDIT_MISSING'}}
function Assert-AclJournalFile($s) {}
function Assert-NoReparseAncestors($p) {}
function Write-AclRecord($s,$r) {$b=[Text.Encoding]::UTF8.GetBytes(($r | ConvertTo-Json -Depth 12 -Compress)+"`n");$s.Position=$s.Length;$s.Write($b,0,$b.Length);$s.Flush($true)}
function Read-AclRecords($s) {$s.Position=0;$b=New-Object byte[] ([int]$s.Length);$null=$s.Read($b,0,$b.Length);$raw=[Text.Encoding]::UTF8.GetString($b);if(-not $raw.EndsWith("`n")){throw 'TORN'};@($raw.TrimEnd("`n").Split("`n") | ForEach-Object {$_ | ConvertFrom-Json})}
function New-RecordedAclStateRoot {param($Path,$Journal,$ManifestHash);[IO.Directory]::CreateDirectory($Path) | Out-Null}
function Invoke-AclTransaction {param($Code,$State,$ServiceSid,$Journal,$ManifestHash,[switch]$Recover);if($fail -ceq 'ACL' -and -not $Recover){throw 'INJECTED_ACL_FAILURE'};if(-not $Recover){[IO.File]::WriteAllText($Journal,'isolated-acl')};'COMMITTED'}
function Get-CimInstance {param($ClassName,$Filter);if(Test-Path $serviceFile){Get-Content $serviceFile -Raw | ConvertFrom-Json}}
function Invoke-CimMethod {param($ClassName,$MethodName,$Arguments,$InputObject);if($MethodName -ceq 'Create'){@{StartMode='Disabled';State='Stopped';StartName=$Arguments.StartName;PathName=$Arguments.PathName} | ConvertTo-Json | Set-Content $serviceFile}elseif($MethodName -ceq 'Delete'){[IO.File]::Delete($serviceFile)}else{throw 'UNEXPECTED_SCM_OPERATION'};[pscustomobject]@{ReturnValue=0}}
'''
        files={'service/RoktU1Bridge.exe':b'MZ-'+manifest.encode(),'config/host.json':b'{}'}
        if manifest=='a':files['config/obsolete.json']=b'old'
        else:files['runtime/new.json']=b'new'
        rows=[]
        for n,b in files.items():
            p=self.package/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
            rows.append(dict(path=n,sha256=hashlib.sha256(b).hexdigest()))
        pre+="$m='"+json.dumps(dict(files=rows),separators=(',',':'))+"' | ConvertFrom-Json\n"
        # Lifecycle fixtures double authority alongside SCM/ACL. Dedicated
        # publisher tests exercise the real shared DB authority separately.
        expected_action=authority_action or ('upgrade' if upgrade else 'recover' if recover else 'rollback' if rollback else 'install')
        pre+="\n$expectedAction='"+expected_action+"'; $script:authorityLost=$false; $maintenance=[pscustomobject]@{}; $maintenance | Add-Member -MemberType ScriptMethod -Name AssertHeld -Value {param($op,$source,$manifest,$action); if($manifest -cne $ApprovedManifestSha256 -or $action -cne $expectedAction){throw 'BINDING_MISMATCH'}; if($script:authorityLost){return $false}; return $true}\n"
        call='\nInvoke-HostInstallTransaction -Execute'
        if authority:call+=' -MaintenanceAuthority $maintenance'
        for flag,value in (('Upgrade',upgrade),('RecoverInstall',recover),('Rollback',rollback)):
            if value:call+=' -'+flag
        if operation:call+=' -OperationId '+operation
        if previous:call+=' -ApprovedPreviousReceiptSha256 '+previous
        path=self.root/'run.ps1';path.write_text(pre+source+call,encoding='utf-8-sig')
        return subprocess.run(['pwsh','-NoProfile','-File',str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)

    @staticmethod
    def q(s):return "'"+str(s).replace("'","''")+"'"

    def assert_ok(self,r):self.assertEqual(r.returncode,0,r.stderr+r.stdout)

    def test_missing_maintenance_authority_refuses_before_any_target_creation(self):
        r=self.run_coordinator(authority=False)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('FORMAL_INVENTORY_MAINTENANCE_REQUIRED',r.stderr)
        self.assertFalse(self.code.exists()); self.assertFalse(self.state.exists())
        self.assertFalse(list(self.audit.iterdir()))

    def test_wrong_action_or_multiple_actions_refused_before_target_creation(self):
        r=self.run_coordinator(rollback=True,authority_action='install')
        self.assertNotEqual(r.returncode,0); self.assertIn('BINDING_MISMATCH',r.stderr)
        r=self.run_coordinator(rollback=True,upgrade=True)
        self.assertNotEqual(r.returncode,0); self.assertIn('EXACT_SINGLE_INSTALL_ACTION_REQUIRED',r.stderr)
        self.assertFalse(self.code.exists()); self.assertFalse(self.state.exists())
        self.assertFalse(list(self.audit.iterdir()))

    def test_lost_maintenance_after_files_preserves_state_without_scm_or_compensation(self):
        r=self.run_coordinator(maintenance_fail='FILES_VERIFIED')
        self.assertNotEqual(r.returncode,0)
        self.assertIn('STOP_AND_PRESERVE_MAINTENANCE_LOST',r.stderr)
        self.assertTrue(self.code.exists()); self.assertTrue(self.state.exists())
        self.assertFalse((self.root/'service.json').exists())
        rows=[json.loads(x) for x in (self.audit/('install-'+'a'*64+'.jsonl')).read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[-1]['phase'],'FILES_VERIFIED')
        self.assertNotIn('FAILURE_COMPENSATION_INTENT',[x['phase'] for x in rows])

    def test_install_upgrade_full_rollback_and_duplicate(self):
        self.assert_ok(self.run_coordinator())
        previous=(self.code/'config/installation.json').read_bytes()
        r=self.run_coordinator();self.assertNotEqual(r.returncode,0)
        self.assertEqual((self.code/'config/installation.json').read_bytes(),previous)
        self.assert_ok(self.run_coordinator(upgrade=True,manifest='b',previous=hashlib.sha256(previous).hexdigest()))
        self.assertFalse((self.code/'config/obsolete.json').exists());self.assertTrue((self.code/'runtime/new.json').exists())
        current=(self.code/'config/installation.json').read_bytes()
        self.assertNotEqual(self.run_coordinator(rollback=True).returncode,0)
        self.assertTrue((self.root/'service.json').exists())
        self.assertEqual((self.code/'config/installation.json').read_bytes(),current)
        self.assert_ok(self.run_coordinator(rollback=True,manifest='b'))
        self.assertEqual((self.code/'config/installation.json').read_bytes(),previous)
        self.assertEqual((self.code/'service/RoktU1Bridge.exe').read_bytes(),b'MZ-a')
        self.assertFalse((self.code/'runtime/new.json').exists())
        self.assert_ok(self.run_coordinator(rollback=True))
        self.assertFalse((self.root/'service.json').exists());self.assertFalse(self.code.exists());self.assertFalse(self.state.exists())

        self.assert_ok(self.run_coordinator(operation='f'*64))
        self.assertTrue((self.code/'service/RoktU1Bridge.exe').exists())

    def test_acl_failure_compensates_actual_files_and_registration(self):
        r=self.run_coordinator(fail='ACL');self.assertNotEqual(r.returncode,0)
        self.assertFalse((self.root/'service.json').exists());self.assertFalse(any(p.is_file() for p in self.code.rglob('*')))
        rows=[json.loads(l) for l in (self.audit/('install-'+'a'*64+'.jsonl')).read_text().splitlines()]
        self.assertEqual(rows[-1]['phase'],'ROLLED_BACK')

    def test_real_coordinator_process_exit_recovery_no_forward_replay(self):
        self.assertEqual(self.run_coordinator(death='FILES_VERIFIED').returncode,31)
        self.assertTrue((self.code/'service/RoktU1Bridge.exe').exists());self.assertFalse((self.root/'service.json').exists())
        self.assertNotEqual(self.run_coordinator().returncode,0)
        self.assert_ok(self.run_coordinator(recover=True))
        self.assertFalse(any(p.is_file() for p in self.code.rglob('*')))

    def test_early_root_creation_process_exit_restores_absent(self):
        for n,phase in enumerate(('CODE_CREATE_VERIFIED','STATE_CREATE_VERIFIED'),start=1):
            operation=format(n,'064x')
            with self.subTest(phase=phase):
                self.assertEqual(self.run_coordinator(death=phase,operation=operation).returncode,31)
                self.assert_ok(self.run_coordinator(recover=True,operation=operation))
                self.assertFalse(self.code.exists());self.assertFalse(self.state.exists())

    def test_unknown_state_content_preserved_before_registration_or_acl_rollback(self):
        self.assert_ok(self.run_coordinator())
        marker=self.state/'unknown.sqlite';marker.write_bytes(b'unmanaged-state')
        receipt=(self.code/'config/installation.json').read_bytes()
        self.assertNotEqual(self.run_coordinator(rollback=True).returncode,0)
        self.assertTrue((self.root/'service.json').exists());self.assertEqual(marker.read_bytes(),b'unmanaged-state')
        self.assertEqual((self.code/'config/installation.json').read_bytes(),receipt)


if __name__=='__main__':unittest.main()
