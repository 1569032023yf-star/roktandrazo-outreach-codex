# 只读候选核查 / Read-only candidate inspection. No install, start, network or signing.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$name = 'RoktU1Bridge'
$expectedImage = 'C:\Program Files\RoktU1Bridge\v1\service\RoktU1Bridge.exe'
$svc = Get-CimInstance Win32_Service -Filter "Name='$name'"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
$result = [ordered]@{
    schema='rokt.local-disabled-service-observation.v1'
    observed_utc=[DateTime]::UtcNow.ToString('o')
    observer_session_id=$session
    service_name=$name
    registration='ABSENT'
    disabled=$null
    stopped=$null
    account_match=$null
    image_match=$null
    runtime_sha256=$null
    wrapper_sha256=$null
    code_sddl=$null
    state_sddl=$null
    bridge_cross_call_persistence='UNKNOWN'
    bridge_logoff_reboot_persistence='UNKNOWN'
    noninteractive_proxy_egress='UNKNOWN'
    outside_agent_job='UNKNOWN'
    service_logon_right='UNKNOWN'
    signature='NOT_SIGNED_LOCAL_OBSERVATION'
    allow_install=$false
    allow_dispatch=$false
    allow_cancel_dispatch=$false
}
if ($null -ne $svc) {
    $result.registration='OBSERVED'
    $result.disabled=($svc.StartMode -ceq 'Disabled')
    $result.stopped=($svc.State -ceq 'Stopped')
    $result.account_match=($svc.StartName -ieq 'NT SERVICE\RoktU1Bridge')
    # No arguments, alternate interpreter or legacy module accepted.
    $result.image_match=($svc.PathName -ceq ('"' + $expectedImage + '"'))
}
$runtime='C:\Program Files\RoktU1Bridge\v1\runtime\python.exe'
if (Test-Path -LiteralPath $runtime -PathType Leaf) {
    $result.runtime_sha256=(Get-FileHash -LiteralPath $runtime -Algorithm SHA256).Hash.ToLowerInvariant()
}
if (Test-Path -LiteralPath $expectedImage -PathType Leaf) {
    $result.wrapper_sha256=(Get-FileHash -LiteralPath $expectedImage -Algorithm SHA256).Hash.ToLowerInvariant()
}
$code='C:\Program Files\RoktU1Bridge\v1'
$state='C:\ProgramData\RoktU1Bridge'
if (Test-Path -LiteralPath $code -PathType Container) { $result.code_sddl=(Get-Acl -LiteralPath $code).Sddl }
if (Test-Path -LiteralPath $state -PathType Container) { $result.state_sddl=(Get-Acl -LiteralPath $state).Sddl }
# Raw SDDL is observation, not an ACL or no-customer-DB-access acceptance decision.
$result | ConvertTo-Json -Depth 5
