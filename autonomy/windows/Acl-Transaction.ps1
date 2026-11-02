# DACL-only transaction. Callers hold the installer mutex; the journal also has
# an exclusive OS file lock. Recovery compensates, never replays installation.
function Assert-AclPath([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        $item=Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'ACL_REPARSE_REJECTED' }
        $cursor=[IO.Path]::GetDirectoryName($cursor)
    }
}
function Get-DaclText([string]$Path) {
    Assert-AclPath $Path
    (Get-Acl -LiteralPath $Path).GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
}
function Set-DaclText([string]$Path,[string]$Sddl) {
    Assert-AclPath $Path
    $acl=[IO.Directory]::GetAccessControl($Path,[Security.AccessControl.AccessControlSections]::Access)
    $acl.SetSecurityDescriptorSddlForm($Sddl,[Security.AccessControl.AccessControlSections]::Access)
    [IO.Directory]::SetAccessControl($Path,$acl)
}
function Assert-AclAuditRoot([string]$Root) {
    Assert-AclPath $Root
    $acl=Get-Acl -LiteralPath $Root
    $trusted=@('S-1-5-18','S-1-5-32-544')
    if (-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $trusted) { throw 'ACL_AUDIT_ROOT_UNTRUSTED' }
    $full=@{}
    foreach ($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($ace.IdentityReference.Value -notin $trusted -or $ace.AccessControlType -ne 'Allow') { throw 'ACL_AUDIT_ROOT_UNTRUSTED' }
        if ($ace.PropagationFlags -eq 'None' -and ($ace.InheritanceFlags -band 3) -eq 3 -and ($ace.FileSystemRights -band 2032127) -eq 2032127) { $full[$ace.IdentityReference.Value]=$true }
    }
    if ($full.Count -ne 2) { throw 'ACL_AUDIT_ROOT_UNTRUSTED' }
}
function Assert-AclJournalFile($Stream) {
    $acl=$Stream.GetAccessControl()
    $trusted=@('S-1-5-18','S-1-5-32-544')
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $trusted) { throw 'ACL_JOURNAL_UNTRUSTED' }
    foreach ($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($ace.IdentityReference.Value -notin $trusted -or $ace.AccessControlType -ne 'Allow') { throw 'ACL_JOURNAL_UNTRUSTED' }
    }
}
function Assert-AclRecoveryAdmission([string]$Code,$Service) {
    if (Test-Path -LiteralPath (Join-Path $Code 'config/installation.json')) { throw 'ACL_COMPLETED_INSTALL_RECOVERY_REJECTED' }
    if ($Service -and ($Service.StartMode -cne 'Disabled' -or $Service.State -cne 'Stopped' -or $Service.StartName -ine 'NT SERVICE\RoktU1Bridge' -or $Service.PathName -cne ('"'+$Code+'\service\RoktU1Bridge.exe"'))) { throw 'ACL_RECOVERY_SERVICE_UNSAFE' }
}
function New-RecordedAclStateRoot([string]$Path,[string]$Journal,[string]$ManifestHash) {
    # Atomic initial DACL prevents a writable ProgramData inheritance window.
    # Creation is recorded separately; it is never silently retried or deleted.
    Assert-AclAuditRoot ([IO.Path]::GetDirectoryName($Journal))
    Assert-AclPath ([IO.Path]::GetDirectoryName($Path))
    if (Test-Path -LiteralPath $Path) { throw 'ACL_STATE_ALREADY_EXISTS' }
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($id in @('S-1-5-18','S-1-5-32-544')) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($id),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    $recordPath=$Journal+'.state-create.jsonl'
    $stream=[IO.FileStream]::new($recordPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
    try {
        Assert-AclJournalFile $stream
        $sddl=$acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)
        Write-AclRecord $stream @{kind='STATE_CREATE_INTENT';before='ABSENT';path=$Path;after=$sddl;manifest=$ManifestHash}
        $null=[IO.Directory]::CreateDirectory($Path,$acl)
        if ((Get-DaclText $Path) -cne $sddl) { throw 'ACL_STATE_CREATE_READBACK_FAILED' }
        Write-AclRecord $stream @{kind='STATE_CREATE_VERIFIED';path=$Path;observed=$sddl;allow_replay=$false}
    } finally { $stream.Dispose() }
}
function Write-AclRecord($Stream,$Record) {
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Record | ConvertTo-Json -Depth 12 -Compress)+"`n")
    $Stream.Position=$Stream.Length
    $Stream.Write($bytes,0,$bytes.Length)
    $Stream.Flush($true)
}
function Read-AclRecords($Stream) {
    $Stream.Position=0
    $bytes=New-Object byte[] ([int]$Stream.Length)
    if ($Stream.Read($bytes,0,$bytes.Length) -ne $bytes.Length) { throw 'ACL_JOURNAL_SHORT_READ' }
    $raw=[Text.UTF8Encoding]::new($false,$true).GetString($bytes)
    if (-not $raw.EndsWith("`n")) { throw 'ACL_JOURNAL_UNKNOWN_TRUNCATED' }
    @($raw.TrimEnd("`n").Split("`n") | ForEach-Object { $_ | ConvertFrom-Json -ErrorAction Stop })
}
function Restore-AclTransaction($Stream,$Header) {
    # Precheck BOTH observations before compensating either. Unexpected ACLs
    # need reconciliation, not a speculative overwrite or repeated Set-Acl.
    foreach ($target in $Header.targets) {
        $actual=Get-DaclText $target.path
        if ($actual -cne $target.before -and $actual -cne $target.after) { throw 'ACL_UNKNOWN_RECONCILIATION_REQUIRED' }
    }
    for ($i=1;$i -ge 0;$i--) {
        $target=$Header.targets[$i]
        $actual=Get-DaclText $target.path
        if ($actual -ceq $target.before) { continue }
        if ($actual -cne $target.after) { throw 'ACL_UNKNOWN_RECONCILIATION_REQUIRED' }
        Write-AclRecord $Stream @{kind='ROLLBACK_INTENT';index=$i;observed=$actual}
        Set-DaclText $target.path $target.before
        if ((Get-DaclText $target.path) -cne $target.before) { throw 'ACL_ROLLBACK_READBACK_FAILED' }
        Write-AclRecord $Stream @{kind='ROLLED_BACK';index=$i;observed=$target.before}
    }
    Write-AclRecord $Stream @{kind='ABORTED';allow_replay=$false}
}
function Invoke-AclTransaction {
    param([string]$Code,[string]$State,[string]$ServiceSid,[string]$Journal,
          [string]$ManifestHash,[switch]$Recover)
    Assert-AclAuditRoot ([IO.Path]::GetDirectoryName($Journal))
    foreach ($p in @($Code,$State)) { Assert-AclPath $p }
    if ([IO.Path]::GetFullPath($Code) -eq [IO.Path]::GetFullPath($State)) { throw 'ACL_TARGET_COLLISION' }
    if (Test-Path -LiteralPath $Journal) { Assert-AclPath $Journal }
    $mode=if ($Recover) {[IO.FileMode]::Open} else {[IO.FileMode]::CreateNew}
    $stream=[IO.FileStream]::new($Journal,$mode,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
    try {
        Assert-AclJournalFile $stream
        if ($Recover) {
            $records=@(Read-AclRecords $stream)
            $header=$records[0]
            if ($header.kind -cne 'PREPARED' -or $header.schema -cne 'rokt.acl-transaction.v1' -or $header.manifest -cne $ManifestHash -or @($header.targets).Count -ne 2 -or $header.targets[0].path -cne $Code -or $header.targets[1].path -cne $State) { throw 'ACL_JOURNAL_BINDING_REJECTED' }
            if ($records[-1].kind -ceq 'ABORTED') {
                foreach ($target in $header.targets) { if ((Get-DaclText $target.path) -cne $target.before) { throw 'ACL_UNKNOWN_RECONCILIATION_REQUIRED' } }
                return 'ABORTED_NO_REPLAY'
            }
            # COMMITTED may still be compensated explicitly after installer
            # interruption; recovery never creates/deletes/starts a service.
            Restore-AclTransaction $stream $header
            return 'ABORTED_NO_REPLAY'
        }
        $sid=[Security.Principal.SecurityIdentifier]::new($ServiceSid)
        if ($ServiceSid -in @('S-1-5-18','S-1-5-32-544')) { throw 'ACL_SERVICE_IDENTITY_REJECTED' }
        $beforeCode=Get-DaclText $Code
        $beforeState=Get-DaclText $State
        $codeAcl=Get-Acl -LiteralPath $Code
        if ($codeAcl.AreAccessRulesProtected) { throw 'CODE_INHERITANCE_REQUIRED' }
        $codeAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
        $stateAcl=Get-Acl -LiteralPath $State
        foreach ($ace in @($stateAcl.Access)) { $stateAcl.RemoveAccessRuleSpecific($ace) }
        $stateAcl.SetAccessRuleProtection($true,$false)
        foreach ($pair in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@($ServiceSid,'Modify'))) {
            $stateAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($pair[0]),$pair[1],'ContainerInherit,ObjectInherit','None','Allow'))
        }
        $section=[Security.AccessControl.AccessControlSections]::Access
        $header=@{kind='PREPARED';schema='rokt.acl-transaction.v1';manifest=$ManifestHash;operation_id=[guid]::NewGuid().ToString();targets=@(
            @{path=$Code;before=$beforeCode;after=$codeAcl.GetSecurityDescriptorSddlForm($section)},
            @{path=$State;before=$beforeState;after=$stateAcl.GetSecurityDescriptorSddlForm($section)})}
        Write-AclRecord $stream $header
        try {
            for ($i=0;$i -lt 2;$i++) {
                $target=$header.targets[$i]
                if ((Get-DaclText $target.path) -cne $target.before) { throw 'ACL_PRECONDITION_CHANGED' }
                Write-AclRecord $stream @{kind='APPLY_INTENT';index=$i}
                Set-DaclText $target.path $target.after
                $actual=Get-DaclText $target.path
                if ($actual -cne $target.after) { throw 'ACL_APPLY_READBACK_FAILED' }
                Write-AclRecord $stream @{kind='VERIFIED';index=$i;observed=$actual}
            }
            Write-AclRecord $stream @{kind='COMMITTED';allow_replay=$false}
            return 'COMMITTED'
        } catch {
            # A failed/partial journal write is not safe to append to. Recovery
            # validates its complete bytes before taking any compensating action.
            $null=Read-AclRecords $stream
            Restore-AclTransaction $stream $header
            throw
        }
    } finally { $stream.Dispose() }
}
