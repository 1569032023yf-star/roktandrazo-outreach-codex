# Disabled-only installation. No service start, scheduler, proxy or database operation.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedManifestSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ApprovedSourceCommit,
    [string]$RuntimePlan,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedRuntimePlanSha256,
    [switch]$RecoverAcl,
    [switch]$Upgrade,
    [switch]$RecoverInstall,
    [switch]$Rollback,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$OperationId,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedPreviousReceiptSha256,
    [switch]$Execute
)
$ErrorActionPreference='Stop'
# A package hash and an installer mutex do not exclude the original Inventory.
# No production-authoritative maintenance adapter is integrated in this pin.
# Fail before opening targets, creating journals, or entering any recovery path.
if ($Execute) { throw 'FORMAL_INVENTORY_MAINTENANCE_REQUIRED_STOP_AND_PRESERVE' }
. (Join-Path $PSScriptRoot 'Host-PackagePreparation.ps1')
Invoke-HostPackageTransaction @PSBoundParameters
