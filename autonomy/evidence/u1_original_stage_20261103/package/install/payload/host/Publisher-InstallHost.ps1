# Internal fixed command for the authenticated, source-pinned publisher only.
# Parent must pin this script, preparation/helpers and all approved references.
# No listener, arbitrary command or public Execute grant. Stdio is assertion-only.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedManifestSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ApprovedSourceCommit,
    [Parameter(Mandatory=$true)][string]$RuntimePlan,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedRuntimePlanSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$OperationId,
    [Parameter(Mandatory=$true)][ValidateSet('install','upgrade','recover','rollback')][string]$Action,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedPreviousReceiptSha256
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Maintenance-Authority.ps1')
. (Join-Path $PSScriptRoot 'Host-PackagePreparation.ps1')
$parameters=@{}+ $PSBoundParameters
$parameters.Remove('Action')
$parameters['MaintenanceAuthority']=New-HostMaintenanceAuthority
$parameters['Execute']=$true
if ($Action -ceq 'upgrade') {$parameters['Upgrade']=$true}
if ($Action -ceq 'recover') {$parameters['RecoverInstall']=$true}
if ($Action -ceq 'rollback') {$parameters['Rollback']=$true}
Invoke-HostPackageTransaction @parameters
