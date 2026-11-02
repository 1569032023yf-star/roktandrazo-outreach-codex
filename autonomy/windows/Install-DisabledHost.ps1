# Disabled-only installation. No service start, scheduler, proxy or database operation.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedManifestSha256,
    [string]$RuntimePlan,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$ApprovedRuntimePlanSha256,
    [switch]$Execute
)
$ErrorActionPreference='Stop'
$dependencyPins=New-Object Collections.ArrayList
function Pin-Reference([string]$Path,[string]$Expected) {
    Assert-NoReparseAncestors $Path
    $stream=New-Object IO.FileStream($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
        $hash=[Security.Cryptography.SHA256]::Create()
        try { $actual=([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }
        if ($actual -cne $Expected) { throw 'PINNED_REFERENCE_HASH' }
        [void]$dependencyPins.Add($stream)
    } catch { $stream.Dispose(); throw }
}
try {
$name='RoktU1Bridge'
$account='NT SERVICE\RoktU1Bridge'
$code='C:\Program Files\RoktU1Bridge\v1'
$state='C:\ProgramData\RoktU1Bridge'
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
foreach ($p in @($PackageRoot,$code,$state)) { Assert-NoReparseAncestors $p }
$package=(Get-Item -LiteralPath $PackageRoot).FullName
$manifestPath=Join-Path $package 'manifest.json'
if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedManifestSha256) { throw 'MANIFEST_HASH_MISMATCH' }
Pin-Reference $manifestPath $ApprovedManifestSha256
$m=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($m.schema -cne 'rokt.disabled-host-package.v1' -or $m.inventory_id -cne '1784775229336' -or
    $m.service_name -cne $name -or $m.account -cne $account -or $m.start_type -cne 'Disabled' -or
    $m.code_root -cne $code -or $m.state_root -cne $state -or
    $m.allow_start -isnot [bool] -or $m.allow_start -or $m.allow_dispatch -isnot [bool] -or $m.allow_dispatch -or
    $m.allow_cancel_dispatch -isnot [bool] -or $m.allow_cancel_dispatch -or
    $m.scheduler_created -isnot [bool] -or $m.scheduler_created -or $m.rollback_preserves_state -cne $true) { throw 'UNSAFE_MANIFEST' }
$entries=@($m.files)+@($m.scripts)
$seen=@{}
foreach ($f in $entries) {
    if ($f.path -isnot [string] -or $f.path -cnotmatch '^[A-Za-z0-9_./-]+$' -or $f.path.Contains('..') -or $f.path.StartsWith('/') -or $seen.ContainsKey($f.path.ToLowerInvariant())) { throw 'UNSAFE_PACKAGE_PATH' }
    $seen[$f.path.ToLowerInvariant()]=$true
    $p=Join-Path $package $f.path
    Assert-NoReparseAncestors $p
    $item=Get-Item -LiteralPath $p
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -ne $f.size -or
        (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant() -cne $f.sha256) { throw 'ARTIFACT_MISMATCH' }
    Pin-Reference $p $f.sha256
}
foreach ($required in @('service/RoktU1Bridge.exe','runtime/dependencies.json','config/host.json','Install-DisabledHost.ps1','Rollback-DisabledHost.ps1')) {
    if (-not $seen.ContainsKey($required.ToLowerInvariant())) { throw 'MISSING_DEPENDENCY' }
}
$deps=Get-Content -LiteralPath (Join-Path $package 'runtime/dependencies.json') -Raw | ConvertFrom-Json
if ($deps.schema -cne 'rokt.disabled-host-runtime.v1' -or $deps.framework -cne '.NET Framework 4 x64') { throw 'RUNTIME_CONTRACT_REJECTED' }
$runtimePaths=@{
    'clr'='Microsoft.NET/Framework64/v4.0.30319/clr.dll'
    'mscorlib'='Microsoft.NET/Framework64/v4.0.30319/mscorlib.dll'
    'System'='Microsoft.NET/Framework64/v4.0.30319/System.dll'
    'System.Core'='Microsoft.NET/Framework64/v4.0.30319/System.Core.dll'
    'System.ServiceProcess'='Microsoft.NET/Framework64/v4.0.30319/System.ServiceProcess.dll'
    'System.Web.Extensions'='Microsoft.NET/assembly/GAC_MSIL/System.Web.Extensions/v4.0_4.0.0.0__31bf3856ad364e35/System.Web.Extensions.dll'
}
if (@($deps.files.PSObject.Properties).Count -ne $runtimePaths.Count) { throw 'RUNTIME_CONTRACT_REJECTED' }
foreach ($key in $runtimePaths.Keys) {
    $f=$deps.files.$key
    if ($f.path -cne $runtimePaths[$key]) { throw 'RUNTIME_PATH_REJECTED' }
    $path=Join-Path ([Environment]::GetFolderPath('Windows')) $f.path
    Assert-NoReparseAncestors $path
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $f.sha256 -or
        [Diagnostics.FileVersionInfo]::GetVersionInfo($path).FileVersion -cne $f.version) { throw 'RUNTIME_MISMATCH' }
}
# Generate exact supervisor/runtime bytes before any installation effect.
# The plan contains references, never credentials; its hash is separately approved.
$generated=@{}
if ($RuntimePlan) {
    Assert-NoReparseAncestors $RuntimePlan
    if (-not $ApprovedRuntimePlanSha256 -or (Get-FileHash -LiteralPath $RuntimePlan -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedRuntimePlanSha256) { throw 'RUNTIME_PLAN_HASH' }
    Pin-Reference $RuntimePlan $ApprovedRuntimePlanSha256
    $plan=Get-Content -LiteralPath $RuntimePlan -Raw | ConvertFrom-Json
    $keys=@('schema','inventory_id','python','python_sha256','release_root','token_file','token_sha256','credential_expires_at','snapshot','snapshot_sha256')
    if (@($plan.PSObject.Properties.Name).Count -ne $keys.Count -or @($plan.PSObject.Properties.Name | Where-Object {$_ -cnotin $keys}).Count -ne 0 -or $plan.schema -cne 'rokt.u1-provision-plan.v1' -or $plan.inventory_id -cne '1784775229336') { throw 'RUNTIME_PLAN_SCHEMA' }
    foreach ($key in @('python','token_file','snapshot','release_root')) {
        $value=$plan.$key
        if ($value -isnot [string] -or -not [IO.Path]::IsPathRooted($value) -or $value -match '["\r\n]' -or [IO.Path]::GetFullPath($value) -cne $value) { throw 'RUNTIME_PLAN_PATH' }
        Assert-NoReparseAncestors $value
    }
    foreach ($key in @('python','token_file','snapshot')) {
        $hashKey=if ($key -ceq 'token_file') {'token_sha256'} else {$key+'_sha256'}
        if ($plan.$hashKey -cnotmatch '^[0-9a-f]{64}$' -or (Get-FileHash -LiteralPath $plan.$key -Algorithm SHA256).Hash.ToLowerInvariant() -cne $plan.$hashKey) { throw 'RUNTIME_REFERENCE_HASH' }
        Pin-Reference $plan.$key $plan.$hashKey
    }
    if ($plan.credential_expires_at -isnot [long] -and $plan.credential_expires_at -isnot [int]) { throw 'CREDENTIAL_EXPIRY_TYPE' }
    if ($plan.credential_expires_at -le [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) { throw 'CREDENTIAL_EXPIRED' }
    $bootstrapEntry=@($m.files | Where-Object {$_.path -ceq 'service/u1_bootstrap.py'})
    if ($bootstrapEntry.Count -ne 1) { throw 'BOOTSTRAP_REQUIRED' }
    $runtime=[ordered]@{schema='rokt.u1-python-runtime.v1';inventory_id='1784775229336';release_root=$plan.release_root;state_root=$state;token_file=$plan.token_file;credential_expires_at=$plan.credential_expires_at;snapshot=$plan.snapshot;snapshot_sha256=$plan.snapshot_sha256;allow_dispatch=$false;allow_cancel_dispatch=$false;smtp_enabled=$false}
    $utf8=New-Object Text.UTF8Encoding($false)
    $runtimeBytes=$utf8.GetBytes(($runtime | ConvertTo-Json -Compress))
    $hasher=[Security.Cryptography.SHA256]::Create()
    try { $runtimeHash=([BitConverter]::ToString($hasher.ComputeHash($runtimeBytes))).Replace('-','').ToLowerInvariant() } finally { $hasher.Dispose() }
    $supervisor=[ordered]@{schema='rokt.u1-supervisor.v1';inventory_id='1784775229336';python=$plan.python;python_sha256=$plan.python_sha256;bootstrap=($code+'\service\u1_bootstrap.py');bootstrap_sha256=$bootstrapEntry[0].sha256;runtime_config=($code+'\config\runtime.json');runtime_config_sha256=$runtimeHash}
    $generated['config/runtime.json']=$runtimeBytes
    $generated['config/supervisor.json']=$utf8.GetBytes(($supervisor | ConvertTo-Json -Compress))
    if (@($m.files | Where-Object {$generated.ContainsKey($_.path)}).Count -ne 0) { throw 'GENERATED_CONFIG_COLLISION' }
}
if ($Execute -and -not $RuntimePlan) { throw 'EXACT_RUNTIME_PLAN_REQUIRED' }
if (Get-CimInstance Win32_Service -Filter "Name='$name'") { throw 'SERVICE_ALREADY_EXISTS' }
if ((Test-Path -LiteralPath $code) -or (Test-Path -LiteralPath $state)) { throw 'TARGET_ALREADY_EXISTS' }
$result=[ordered]@{schema='rokt.disabled-host-install-result.v1';preflight=$true;installed=$false;start_type='Disabled';allow_start=$false;allow_dispatch=$false;allow_cancel_dispatch=$false;state_preserved=$true}
if (-not $Execute) { $result | ConvertTo-Json; return }
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ADMINISTRATOR_REQUIRED' }
# The invoking formal publisher must hold its approved maintenance/exclusion lease.
# A hash argument is an exact-byte gate, not a substitute for publisher authority.
$mutex=New-Object Threading.Mutex($false,'Global\RoktU1BridgeInstall')
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); throw 'INSTALLATION_LOCKED' }
$created=$false
try {
    # Repeat mutable preconditions under the installation mutex. Never adopt old services.
    if ((Get-CimInstance Win32_Service -Filter "Name='$name'") -or (Test-Path -LiteralPath $code) -or (Test-Path -LiteralPath $state)) { throw 'TARGET_CHANGED' }
    foreach ($p in @($package,$code,$state)) { Assert-NoReparseAncestors $p }
    New-Item -ItemType Directory -Path $code -Force | Out-Null
    New-Item -ItemType Directory -Path $state | Out-Null
    foreach ($f in $m.files) {
        $source=Join-Path $package $f.path
        Assert-NoReparseAncestors $source
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -cne $f.sha256) { throw 'SOURCE_CHANGED' }
        $dest=Join-Path $code $f.path
        Assert-NoReparseAncestors $dest
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($dest)) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $dest
        if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -cne $f.sha256) { throw 'COPY_MISMATCH' }
    }
    foreach ($relative in $generated.Keys) {
        $destination=Join-Path $code $relative
        Assert-NoReparseAncestors $destination
        # CreateNew refuses an unexpected artifact; never overwrite on retry.
        $stream=New-Object IO.FileStream($destination,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $stream.Write($generated[$relative],0,$generated[$relative].Length); $stream.Flush($true) } finally { $stream.Dispose() }
        $actual=[IO.File]::ReadAllBytes($destination)
        if ([Convert]::ToBase64String($actual) -cne [Convert]::ToBase64String($generated[$relative])) { throw 'GENERATED_CONFIG_READBACK' }
    }
    $args=@{Name=$name;DisplayName='Rokt U1 Bridge (disabled candidate)';PathName=('"'+$code+'\service\RoktU1Bridge.exe"');ServiceType=[uint32]16;ErrorControl=[uint32]1;StartMode='Disabled';DesktopInteract=$false;StartName=$account;StartPassword=''}
    $reply=Invoke-CimMethod -ClassName Win32_Service -MethodName Create -Arguments $args
    if ($reply.ReturnValue -ne 0) { throw 'SERVICE_CREATE_REJECTED' }
    $created=$true
    $sid=(New-Object Security.Principal.NTAccount($account)).Translate([Security.Principal.SecurityIdentifier])
    foreach ($target in @(@($code,'ReadAndExecute'),@($state,'Modify'))) {
        $acl=New-Object Security.AccessControl.DirectorySecurity
        $acl.SetAccessRuleProtection($true,$false)
        foreach ($pair in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@($sid.Value,$target[1]))) {
            $identity=New-Object Security.Principal.SecurityIdentifier($pair[0])
            $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,$pair[1],'ContainerInherit,ObjectInherit','None','Allow')
            $acl.AddAccessRule($rule)
        }
        Set-Acl -LiteralPath $target[0] -AclObject $acl
    }
    $svc=Get-CimInstance Win32_Service -Filter "Name='$name'"
    if ($svc.StartMode -cne 'Disabled' -or $svc.State -cne 'Stopped' -or $svc.StartName -ine $account -or $svc.PathName -cne $args.PathName) { throw 'DISABLED_SERVICE_READBACK_FAILED' }
    $receipt=[ordered]@{schema='rokt.disabled-host-install-receipt.v1';manifest_sha256=$ApprovedManifestSha256;service_name=$name;account=$account;image=$args.PathName;wrapper_sha256=($m.files | Where-Object {$_.path -ceq 'service/RoktU1Bridge.exe'}).sha256;state_preserved=$true}
    # Ownership evidence belongs to the administrator-controlled code tree,
    # never the service-writable durable state tree. Refuse replacement on retry.
    $receiptPath=Join-Path $code 'config/installation.json'
    Assert-NoReparseAncestors $receiptPath
    $receiptBytes=[Text.UTF8Encoding]::new($false).GetBytes(($receipt | ConvertTo-Json -Compress))
    $receiptStream=[IO.FileStream]::new($receiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $receiptStream.Write($receiptBytes,0,$receiptBytes.Length); $receiptStream.Flush($true) } finally { $receiptStream.Dispose() }
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($receiptPath)) -cne [Convert]::ToBase64String($receiptBytes)) { throw 'INSTALLATION_RECEIPT_READBACK_FAILED' }
    $result.installed=$true
    $result['runtime_configured']=($generated.Count -eq 2)
    $result | ConvertTo-Json
} catch {
    # Only this invocation's fresh registration may be removed. Keep binaries and
    # every state byte after failure for audit; never restore a database snapshot.
    if ($created) {
        $svc=Get-CimInstance Win32_Service -Filter "Name='$name'"
        if ($svc -and $svc.State -ceq 'Stopped' -and $svc.PathName -ceq $args.PathName) {
            Invoke-CimMethod -InputObject $svc -MethodName ChangeStartMode -Arguments @{StartMode='Disabled'} | Out-Null
            Invoke-CimMethod -InputObject $svc -MethodName Delete | Out-Null
        }
    }
    throw
} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }

} finally { foreach ($pin in $dependencyPins) { $pin.Dispose() } }
