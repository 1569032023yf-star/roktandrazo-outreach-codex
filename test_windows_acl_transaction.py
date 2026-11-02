"""Real Windows temporary-directory DACLs; no production paths or service APIs.

The audit-root and journal SYSTEM/Admin ownership gates are replaced in the harness,
because tests run without elevation. Production's gate is separately rejected
against this ordinary-user-owned fixture. No transaction or ACL adapter is mocked
except the named fault injection wrapper around the actual Set-DaclText.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).parent / 'autonomy/windows/Acl-Transaction.ps1'


@unittest.skipUnless(os.name == 'nt', 'Windows DACL integration')
class WindowsAclTransactionTests(unittest.TestCase):
    def run_ps(self, code, expected=0):
        bootstrap = "try { & ([scriptblock]::Create([Console]::In.ReadToEnd())); exit 0 } catch { Write-Error $_; exit 1 }"
        encoded = base64.b64encode(bootstrap.encode('utf-16le')).decode('ascii')
        p = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                            '-EncodedCommand', encoded], input=code.encode('utf-8'), capture_output=True,
                           timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(p.returncode, expected, p.stderr.decode(errors='replace'))
        return p.stdout.decode('utf-8-sig', errors='replace').strip()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='u1-acl-isolated-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        q = lambda x: str(x).replace("'", "''")
        self.common = f"""
$ErrorActionPreference='Stop'
Import-Module -Assembly ([Reflection.Assembly]::LoadWithPartialName('Microsoft.PowerShell.Security'))
{HELPER.read_text(encoding='utf-8')}
$root='{q(self.root)}'
$code=Join-Path $root 'code'
$state=Join-Path $root 'state'
$journal=Join-Path $root 'acl.jsonl'
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$manifest='{'a'*64}'
function Assert-Isolated([string]$Path) {{
    if (-not ([IO.Path]::GetFullPath($Path)).StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) {{ throw 'TEST_PATH_ESCAPE' }}
}}
"""
        self.fixture = self.common + """
$acl=Get-Acl -LiteralPath $root
foreach ($ace in @($acl.Access)) { $acl.RemoveAccessRuleSpecific($ace) }
$acl.SetAccessRuleProtection($true,$false)
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-32-545'),'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
[IO.Directory]::SetAccessControl($root,$acl)
$null=New-Item -ItemType Directory -Path $code,$state
$before=@{code=(Get-DaclText $code);state=(Get-DaclText $state)}
$before | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'before.json')
"""
        self.run_ps(self.fixture)
        self.harness = self.common + """
# Test-only audit ownership substitution. Transaction and DACL calls stay real.
function Assert-AclAuditRoot([string]$Root) {
    if ($Root -cne $root) { throw 'TEST_AUDIT_ESCAPE' }
    Assert-AclPath $Root
}
function Assert-AclJournalFile($Stream) {
    if (-not $Stream.Name.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'TEST_JOURNAL_ESCAPE' }
}
$actualSet=${function:Set-DaclText}
function Set-DaclText([string]$Path,[string]$Sddl) {
    Assert-Isolated $Path
    & $actualSet $Path $Sddl
}
"""
        self.invoke = 'Invoke-AclTransaction -Code $code -State $state -ServiceSid $sid -Journal $journal -ManifestHash $manifest'
        self.recover = 'Invoke-AclTransaction -Code $code -State $state -Journal $journal -ManifestHash $manifest -Recover'
        self.check_before = """
$before=Get-Content -Raw -LiteralPath (Join-Path $root 'before.json') | ConvertFrom-Json
if ((Get-DaclText $code) -cne $before.code -or (Get-DaclText $state) -cne $before.state) { throw 'TEST_ROLLBACK_MISMATCH' }
"""

    def test_both_success_inheritance_and_exact_aces_then_explicit_rollback(self):
        out = self.run_ps(self.harness + self.invoke + """
if ((Get-Acl $code).AreAccessRulesProtected) { throw 'TEST_CODE_INHERITANCE' }
if (-not (Get-Acl $state).AreAccessRulesProtected) { throw 'TEST_STATE_PROTECTION' }
$rules=@((Get-Acl $state).GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
if ($rules.Count -ne 3 -or @($rules | Where-Object {$_.IdentityReference.Value -eq 'S-1-5-32-545'}).Count) { throw 'TEST_STATE_ACE' }
""")
        self.assertIn('COMMITTED', out)
        self.run_ps(self.harness + self.recover + self.check_before)
        rows = [json.loads(x) for x in (self.root/'acl.jsonl').read_text().splitlines()]
        self.assertEqual([r['index'] for r in rows if r['kind']=='VERIFIED'], [0, 1])
        self.assertEqual(rows[-1]['kind'], 'ABORTED')
        self.run_ps(self.harness + self.recover + self.check_before)

    def test_second_apply_failure_compensates_code(self):
        self.run_ps(self.harness + """
function Set-DaclText([string]$Path,[string]$Sddl) {
    Assert-Isolated $Path
    if ($Path -ceq $state) { throw 'INJECT_SECOND_SET_FAILURE' }
    & $actualSet $Path $Sddl
}
try {
""" + self.invoke + """
    throw 'TEST_EXPECTED_FAILURE'
} catch { if ($_.Exception.Message -cne 'INJECT_SECOND_SET_FAILURE') { throw } }
""" + self.check_before)
        rows = [json.loads(x) for x in (self.root/'acl.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['kind'], 'ABORTED')

    def crash_and_recover(self, boundary):
        self.run_ps(self.harness + f"""
$writeRecord=${{function:Write-AclRecord}}
function Write-AclRecord($Stream,$Record) {{
    & $writeRecord $Stream $Record
    if ($Record.kind -ceq '{boundary[0]}' -and $Record.index -eq {boundary[1]}) {{ [Environment]::Exit(71) }}
}}
""" + self.invoke, expected=71)
        self.run_ps(self.harness + self.recover + self.check_before)

    def test_exit_after_first_readback(self):
        self.crash_and_recover(('VERIFIED', 0))

    def test_exit_before_second_write(self):
        self.crash_and_recover(('APPLY_INTENT', 1))

    def test_exit_after_second_set_before_readback(self):
        self.run_ps(self.harness + """
function Set-DaclText([string]$Path,[string]$Sddl) {
    Assert-Isolated $Path
    & $actualSet $Path $Sddl
    if ($Path -ceq $state) { [Environment]::Exit(72) }
}
""" + self.invoke, expected=72)
        self.run_ps(self.harness + self.recover + self.check_before)

    def test_unknown_acl_no_automatic_reapply_or_rollback(self):
        self.run_ps(self.harness + self.invoke)
        self.run_ps(self.harness + """
$acl=Get-Acl $code
$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-32-545'),'Write','Allow'))
[IO.Directory]::SetAccessControl($code,$acl)
$snapshot=Get-DaclText $code
function Set-DaclText { throw 'TEST_UNEXPECTED_WRITE' }
try {
""" + self.recover + """
    throw 'TEST_EXPECTED_UNKNOWN'
} catch { if ($_.Exception.Message -cne 'ACL_UNKNOWN_RECONCILIATION_REQUIRED') { throw } }
if ((Get-DaclText $code) -cne $snapshot) { throw 'TEST_UNKNOWN_CHANGED' }
""")

    def test_partial_journal_refuses_all_writes(self):
        self.run_ps(self.harness + self.invoke)
        with (self.root/'acl.jsonl').open('ab') as f:
            f.write(b'{"kind":')
        self.run_ps(self.harness + """
function Set-DaclText { throw 'TEST_UNEXPECTED_WRITE' }
try {
""" + self.recover + """
    throw 'TEST_EXPECTED_UNKNOWN'
} catch { if ($_.Exception.Message -cne 'ACL_JOURNAL_UNKNOWN_TRUNCATED') { throw } }
""")

    def test_production_audit_gate_rejects_ordinary_user_fixture(self):
        self.run_ps(self.common + """
try { Assert-AclAuditRoot $root; throw 'TEST_EXPECTED_REJECT' }
catch { if ($_.Exception.Message -cne 'ACL_AUDIT_ROOT_UNTRUSTED') { throw } }
""")

    def test_existing_journal_never_replays(self):
        self.run_ps(self.harness + self.invoke)
        before = (self.root/'acl.jsonl').read_bytes()
        self.run_ps(self.harness + 'try { ' + self.invoke + "; throw 'TEST_REPLAY' } catch { if ($_.Exception.Message -eq 'TEST_REPLAY') { throw } }")
        self.assertEqual(before, (self.root/'acl.jsonl').read_bytes())

    def test_exit_during_rollback_can_finish_without_reapplying(self):
        self.run_ps(self.harness + self.invoke)
        self.run_ps(self.harness + """
function Set-DaclText([string]$Path,[string]$Sddl) {
    Assert-Isolated $Path
    & $actualSet $Path $Sddl
    [Environment]::Exit(73)
}
""" + self.recover, expected=73)
        self.run_ps(self.harness + self.recover + self.check_before)
        rows = [json.loads(x) for x in (self.root/'acl.jsonl').read_text().splitlines()]
        self.assertEqual(len([x for x in rows if x['kind']=='APPLY_INTENT']), 2)

    def test_rollback_failure_retained_and_explicit_recovery(self):
        self.run_ps(self.harness + self.invoke)
        self.run_ps(self.harness + """
function Set-DaclText { throw 'INJECT_ROLLBACK_FAILURE' }
try {
""" + self.recover + """
    throw 'TEST_EXPECTED_FAILURE'
} catch { if ($_.Exception.Message -cne 'INJECT_ROLLBACK_FAILURE') { throw } }
""")
        self.run_ps(self.harness + self.recover + self.check_before)

    def test_prepared_flush_failure_has_no_acl_effects(self):
        self.run_ps(self.harness + """
function Write-AclRecord { throw 'INJECT_PERSIST_FAILURE' }
function Set-DaclText { throw 'TEST_UNEXPECTED_WRITE' }
try {
""" + self.invoke + """
    throw 'TEST_EXPECTED_FAILURE'
} catch { if ($_.Exception.Message -cne 'INJECT_PERSIST_FAILURE') { throw } }
""" + self.check_before)

    def test_wrong_manifest_recovery_refuses_all_writes(self):
        self.run_ps(self.harness + self.invoke)
        self.run_ps(self.harness + "$manifest='" + 'b'*64 + "';" + """
function Set-DaclText { throw 'TEST_UNEXPECTED_WRITE' }
try {
""" + self.recover + """
    throw 'TEST_EXPECTED_FAILURE'
} catch { if ($_.Exception.Message -cne 'ACL_JOURNAL_BINDING_REJECTED') { throw } }
""")

    def test_production_file_gate_rejects_user_owned_existing_file(self):
        self.run_ps(self.common + """
$stream=[IO.FileStream]::new($journal,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
try {
    try { Assert-AclJournalFile $stream; throw 'TEST_EXPECTED_REJECT' }
    catch { if ($_.Exception.Message -cne 'ACL_JOURNAL_UNTRUSTED') { throw } }
} finally { $stream.Dispose() }
""")

    def test_atomic_state_creation_has_durable_intent_and_secure_initial_dacl(self):
        self.run_ps(self.harness + """
$fresh=Join-Path $root 'new-state'
try {
    New-RecordedAclStateRoot -Path $fresh -Journal $journal -ManifestHash $manifest
    $dacl=[IO.Directory]::GetAccessControl($fresh,[Security.AccessControl.AccessControlSections]::Access)
    if (-not $dacl.AreAccessRulesProtected) { throw 'TEST_INITIAL_PROTECTION' }
    $rules=@($dacl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 2 -or @($rules | Where-Object {$_.IdentityReference.Value -notin @('S-1-5-18','S-1-5-32-544')}).Count) { throw 'TEST_INITIAL_ACE' }
} finally {
    $restore=[IO.Directory]::GetAccessControl($root,[Security.AccessControl.AccessControlSections]::Access)
    $restore.SetSecurityDescriptorSddlForm($restore.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access),[Security.AccessControl.AccessControlSections]::Access)
    [IO.Directory]::SetAccessControl($fresh,$restore)
}
""")
        rows = [json.loads(x) for x in (self.root/'acl.jsonl.state-create.jsonl').read_text().splitlines()]
        self.assertEqual([r['kind'] for r in rows], ['STATE_CREATE_INTENT', 'STATE_CREATE_VERIFIED'])
        self.assertEqual(rows[0]['before'], 'ABSENT')

    def test_production_trust_gates_synthetic_positive_and_untrusted_ace(self):
        self.run_ps(self.common + """
$trusted=[Security.AccessControl.DirectorySecurity]::new()
$trusted.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
$trusted.SetAccessRuleProtection($true,$false)
foreach ($id in @('S-1-5-18','S-1-5-32-544')) {
    $trusted.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($id),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
}
function Get-Acl { $trusted }
Assert-AclAuditRoot $root
$fakeStream=New-Object PSObject
$fakeStream | Add-Member ScriptMethod GetAccessControl { $trusted }
Assert-AclJournalFile $fakeStream
$trusted.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-32-545'),'Write','Allow'))
try { Assert-AclAuditRoot $root; throw 'TEST_EXPECTED_REJECT' }
catch { if ($_.Exception.Message -cne 'ACL_AUDIT_ROOT_UNTRUSTED') { throw } }
try { Assert-AclJournalFile $fakeStream; throw 'TEST_EXPECTED_REJECT' }
catch { if ($_.Exception.Message -cne 'ACL_JOURNAL_UNTRUSTED') { throw } }
""")

    def test_recovery_admission_requires_unfinished_stopped_disabled_identity(self):
        self.run_ps(self.common + """
Assert-AclRecoveryAdmission -Code $code -Service $null
$service=[pscustomobject]@{StartMode='Disabled';State='Stopped';StartName='NT SERVICE\RoktU1Bridge';PathName=('"'+$code+'\service\RoktU1Bridge.exe"')}
Assert-AclRecoveryAdmission -Code $code -Service $service
foreach ($pair in @(@('StartMode','Auto'),@('State','Running'),@('StartName','wrong'),@('PathName','wrong'))) {
    $old=$service.($pair[0]); $service.($pair[0])=$pair[1]
    try { Assert-AclRecoveryAdmission -Code $code -Service $service; throw 'TEST_EXPECTED_REJECT' }
    catch { if ($_.Exception.Message -cne 'ACL_RECOVERY_SERVICE_UNSAFE') { throw } }
    $service.($pair[0])=$old
}
$null=New-Item -ItemType Directory -Path (Join-Path $code 'config')
[IO.File]::WriteAllText((Join-Path $code 'config/installation.json'),'{}')
try { Assert-AclRecoveryAdmission -Code $code -Service $service; throw 'TEST_EXPECTED_REJECT' }
catch { if ($_.Exception.Message -cne 'ACL_COMPLETED_INSTALL_RECOVERY_REJECTED') { throw } }
""")


if __name__ == '__main__':
    unittest.main()
