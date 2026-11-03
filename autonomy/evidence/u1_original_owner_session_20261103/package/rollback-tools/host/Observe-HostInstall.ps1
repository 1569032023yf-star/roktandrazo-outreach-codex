# Read-only independent observation. The trusted parent pins this script and
# PowerShell identity; no arbitrary paths, installation or recovery switches.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$OperationId,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$Nonce
)
$ErrorActionPreference='Stop'
$audit='C:\ProgramData\RoktU1InstallAudit'
$code='C:\Program Files\RoktU1Bridge\v1'
$state='C:\ProgramData\RoktU1Bridge'
$handles=New-Object Collections.ArrayList
function Assert-ObservedPath([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {throw 'STOP_AND_PRESERVE_OBSERVER_REPARSE'}
        }
        $parent=[IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) {break};$cursor=$parent
    }
}
function Get-ObservedAcl([string]$Path) {
    Assert-ObservedPath $Path
    if (-not (Test-Path -LiteralPath $Path)) {return $null}
    if (-not (Get-Item -LiteralPath $Path -Force).PSIsContainer) {throw 'STOP_AND_PRESERVE_OBSERVER_ROOT_TYPE'}
    $acl=[IO.Directory]::GetAccessControl($Path)
    $aces=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
        @{sid=$_.IdentityReference.Value;type=$_.AccessControlType.ToString();rights=[long]$_.FileSystemRights;
          inheritance=[int]$_.InheritanceFlags;propagation=[int]$_.PropagationFlags}
    })
    return @{sddl=$acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access);
        protected=[bool]$acl.AreAccessRulesProtected;aces=$aces}
}
try {
    Assert-ObservedPath $audit
    $trust=@('S-1-5-18','S-1-5-32-544')
    $acl=[IO.Directory]::GetAccessControl($audit)
    if (-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cnotin $trust) {throw 'STOP_AND_PRESERVE_OBSERVER_AUDIT_OWNER'}
    $full=@{}
    foreach ($ace in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($ace.IdentityReference.Value -cnotin $trust -or $ace.AccessControlType -ne 'Allow') {throw 'STOP_AND_PRESERVE_OBSERVER_AUDIT_ACE'}
        if ($ace.PropagationFlags -eq 'None' -and ([int]$ace.InheritanceFlags -band 3) -eq 3 -and ([long]$ace.FileSystemRights -band 2032127) -eq 2032127) {$full[$ace.IdentityReference.Value]=$true}
    }
    if ($full.Count -ne 2) {throw 'STOP_AND_PRESERVE_OBSERVER_AUDIT_RIGHTS'}
    $journals=@{}
    $names=@{install=('install-'+$OperationId+'.jsonl');files=('files-'+$OperationId+'.jsonl');
        acl=('acl-'+$OperationId+'.jsonl');state_create=('acl-'+$OperationId+'.jsonl.state-create.jsonl')}
    foreach ($key in $names.Keys) {
        $path=Join-Path $audit $names[$key]
        Assert-ObservedPath $path
        if (-not (Test-Path -LiteralPath $path)) {$journals[$key]=$null;continue}
        $stream=[IO.FileStream]::new($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
        [void]$handles.Add($stream)
        if ($stream.Length -gt 67108864) {throw 'STOP_AND_PRESERVE_OBSERVER_JOURNAL_LENGTH'}
        $security=$stream.GetAccessControl()
        if ($security.GetOwner([Security.Principal.SecurityIdentifier]).Value -cnotin $trust) {throw 'STOP_AND_PRESERVE_OBSERVER_JOURNAL_OWNER'}
        foreach ($ace in $security.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
            if ($ace.IdentityReference.Value -cnotin $trust -or $ace.AccessControlType -ne 'Allow') {throw 'STOP_AND_PRESERVE_OBSERVER_JOURNAL_ACE'}
        }
        $hash=[Security.Cryptography.SHA256]::Create()
        try {$journals[$key]=([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant()} finally {$hash.Dispose()}
    }
    $services=@(Get-CimInstance Win32_Service -Filter "Name='RoktU1Bridge'")
    if ($services.Count -gt 1) {throw 'STOP_AND_PRESERVE_OBSERVER_SERVICE_COUNT'}
    $service=$null;$sid=$null
    if ($services.Count -eq 1) {
        $s=$services[0]
        $service=@{name=$s.Name;start_mode=$s.StartMode;state=$s.State;account=$s.StartName;image=$s.PathName}
        $sid=([Security.Principal.NTAccount]::new('NT SERVICE\RoktU1Bridge')).Translate([Security.Principal.SecurityIdentifier]).Value
    }
    @{schema='rokt.u1-install-observation.v1';operation_id=$OperationId;nonce=$Nonce;audit_trusted=$true;
      journals=$journals;roots=@{code=(Get-ObservedAcl $code);state=(Get-ObservedAcl $state)};
      service=$service;service_sid=$sid} | ConvertTo-Json -Depth 12 -Compress
} finally {foreach ($handle in $handles) {$handle.Dispose()}}
