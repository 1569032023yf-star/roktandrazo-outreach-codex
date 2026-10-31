# Read-only evidence; never creates a directory or changes an ACL.
$ErrorActionPreference = 'Stop'
$paths = @('C:\', 'C:\ProgramData', 'C:\ProgramData\RoktU1InstallAudit')
$nodes = @()
foreach ($path in $paths) {
    $node = [ordered]@{ path=$path; exists=$false; directory=$null; reparse_point=$null }
    try {
        $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        $node.exists = $true
        $node.directory = [bool]$item.PSIsContainer
        $node.reparse_point = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
        if ($node.reparse_point -or -not $node.directory) {
            $node.error = 'UNSAFE_PATH_STOP'
            $nodes += $node
            break
        }
        $acl = Get-Acl -LiteralPath $path -ErrorAction Stop
        $node.owner_sid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
        $node.protected = [bool]$acl.AreAccessRulesProtected
        $node.aces = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
            [ordered]@{
                sid=$_.IdentityReference.Value
                type=$_.AccessControlType.ToString()
                rights=[int64]$_.FileSystemRights
                inherit_only=[bool]($_.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly)
            }
        })
    } catch {
        # Exception messages may contain local account/path data; emit type only.
        $node.error = $_.Exception.GetType().Name
        $nodes += $node
        break
    }
    $nodes += $node
}
[ordered]@{
    schema='rokt.install-audit-root-observation.v1'
    sampled_at=[DateTimeOffset]::Now.ToString('o')
    nodes=$nodes
    allow_install=$false
    allow_dispatch=$false
    production_execution=$false
} | ConvertTo-Json -Depth 8
