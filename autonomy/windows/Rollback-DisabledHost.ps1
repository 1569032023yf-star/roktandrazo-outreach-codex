# Registration-only rollback. Retain all code, credentials and durable state.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedManifestSha256,[switch]$Execute)
$ErrorActionPreference='Stop'
$name='RoktU1Bridge'
$image='"C:\Program Files\RoktU1Bridge\v1\service\RoktU1Bridge.exe"'
function Assert-NoReparseAncestors([string]$Path) {
    $cursor=[IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'REPARSE_PATH_REJECTED' }
        }
        $parent=[IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }; $cursor=$parent
    }
}
$receiptPath='C:\ProgramData\RoktU1Bridge\installation.json'
$wrapper='C:\Program Files\RoktU1Bridge\v1\service\RoktU1Bridge.exe'
function Assert-OwnedRegistration {
    foreach ($p in @($receiptPath,$wrapper)) { Assert-NoReparseAncestors $p }
    $receipt=Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    if ($receipt.schema -cne 'rokt.disabled-host-install-receipt.v1' -or $receipt.manifest_sha256 -cne $ApprovedManifestSha256 -or
        $receipt.service_name -cne $name -or $receipt.account -cne 'NT SERVICE\RoktU1Bridge' -or $receipt.image -cne $image -or
        (Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash.ToLowerInvariant() -cne $receipt.wrapper_sha256) { throw 'INSTALLATION_RECEIPT_MISMATCH' }
}
$svc=Get-CimInstance Win32_Service -Filter "Name='$name'"
if (-not $svc) { @{outcome='ALREADY_ABSENT';state_preserved=$true} | ConvertTo-Json; return }
Assert-OwnedRegistration
if ($svc.PathName -cne $image -or $svc.StartName -ine 'NT SERVICE\RoktU1Bridge') { throw 'FOREIGN_REGISTRATION_REJECTED' }
if ($svc.State -cne 'Stopped') { throw 'DRAIN_AND_STOP_THROUGH_FORMAL_CHANNEL_REQUIRED' }
if (-not $Execute) { @{outcome='PLAN_ONLY';allow_start=$false;state_preserved=$true} | ConvertTo-Json; return }
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ADMINISTRATOR_REQUIRED' }
$mutex=New-Object Threading.Mutex($false,'Global\RoktU1BridgeInstall')
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); throw 'INSTALLATION_LOCKED' }
try {
    Assert-OwnedRegistration
    $svc=Get-CimInstance Win32_Service -Filter "Name='$name'"
    if (-not $svc) { throw 'REGISTRATION_CHANGED' }
    if ($svc.PathName -cne $image -or $svc.StartName -ine 'NT SERVICE\RoktU1Bridge' -or $svc.State -cne 'Stopped') { throw 'REGISTRATION_CHANGED' }
    $disabled=Invoke-CimMethod -InputObject $svc -MethodName ChangeStartMode -Arguments @{StartMode='Disabled'}
    if ($disabled.ReturnValue -ne 0) { throw 'DISABLE_REJECTED' }
    $deleted=Invoke-CimMethod -InputObject $svc -MethodName Delete
    if ($deleted.ReturnValue -ne 0) { throw 'DELETE_REJECTED' }
    if (Get-CimInstance Win32_Service -Filter "Name='$name'") { throw 'DELETE_READBACK_FAILED' }
    @{outcome='REGISTRATION_REMOVED';state_preserved=$true;code_preserved=$true;allow_dispatch=$false} | ConvertTo-Json
} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
