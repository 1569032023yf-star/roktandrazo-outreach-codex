# Shared lifecycle coordinator. Caller has pinned manifest, Python and helpers.
# No StartService, scheduler or database operation. The pinned publisher owns
# maintenance authority; this coordinator only asserts its bound live session.
function Invoke-HostInstallTransaction {
    param([switch]$Upgrade,[switch]$RecoverInstall,[switch]$Rollback,
          [string]$ApprovedPreviousReceiptSha256,[string]$OperationId,
          [object]$MaintenanceAuthority,[switch]$Execute)
    if (-not $RuntimePlan) { throw 'EXACT_RUNTIME_PLAN_REQUIRED' }
    $operation=if ($OperationId) {$OperationId} else {$ApprovedManifestSha256}
    if ($operation -cnotmatch '^[0-9a-f]{64}$') {throw 'EXACT_OPERATION_REQUIRED'}
    if (([int][bool]$Upgrade+[int][bool]$RecoverInstall+[int][bool]$Rollback) -gt 1) {throw 'EXACT_SINGLE_INSTALL_ACTION_REQUIRED'}
    $maintenanceAction=if ($Upgrade) {'upgrade'} elseif ($RecoverInstall) {'recover'} elseif ($Rollback) {'rollback'} else {'install'}
    $audit='C:\ProgramData\RoktU1InstallAudit'
    $journal=Join-Path $audit ('install-'+$operation+'.jsonl')
    $fileJournal=Join-Path $audit ('files-'+$operation+'.jsonl')
    $operationAcl=Join-Path $audit ('acl-'+$operation+'.jsonl')
    $image='"'+$code+'\service\RoktU1Bridge.exe"'
    $receiptPath=Join-Path $code 'config/installation.json'
    $pythonHelper=Join-Path $package 'host_file_transaction.py'
    function Assert-HostMaintenance {
        if ($null -eq $MaintenanceAuthority -or $null -eq $MaintenanceAuthority.PSObject.Methods['AssertHeld']) {
            throw 'FORMAL_INVENTORY_MAINTENANCE_REQUIRED_STOP_AND_PRESERVE'
        }
        $proof=$MaintenanceAuthority.AssertHeld($operation,$m.source_commit,$ApprovedManifestSha256,$maintenanceAction)
        if ($proof -isnot [bool] -or -not $proof) {throw 'STOP_AND_PRESERVE_MAINTENANCE_LOST'}
    }
    function Get-HostService {
        $s=Get-CimInstance Win32_Service -Filter "Name='$name'"
        if ($s -and ($s.StartMode -cne 'Disabled' -or $s.State -cne 'Stopped' -or $s.StartName -ine $account -or $s.PathName -cne $image)) { throw 'OWNED_DISABLED_STOPPED_SERVICE_REQUIRED' }
        return $s
    }
    function Invoke-HostFiles([string]$Action,$Request) {
        Assert-HostMaintenance
        if ($null -ne $Request) {
            $reply=($Request | ConvertTo-Json -Depth 12 -Compress) | & $plan.python -I -B $pythonHelper $Action --operation $operation
        } else {
            $reply=& $plan.python -I -B $pythonHelper $Action --operation $operation
        }
        if ($LASTEXITCODE -ne 0) { throw 'STOP_AND_PRESERVE_FILE_TRANSACTION' }
        Assert-HostMaintenance
        return ($reply | ConvertFrom-Json)
    }
    function Write-HostPhase([string]$Phase,$Extra=@{}) {
        Assert-HostMaintenance
        if ($log.Length -gt 0) {$null=Read-AclRecords $log}
        Write-AclRecord $log @{phase=$Phase;manifest=$ApprovedManifestSha256;operation_id=$operation;extra=$Extra}
    }
    function Get-CreatedRootObservations($Rows) {
        $expected=@{code=$null;state=$null;absent_allowed=@()}
        foreach ($key in @('code','state')) {
            $created=@($Rows | Where-Object {$_.phase -ceq ($key.ToUpperInvariant()+'_CREATE_VERIFIED')})
            if ($created.Count) {$expected[$key]=$created[-1].extra.identity}
            if (@($Rows | Where-Object {$_.phase -ceq ($key.ToUpperInvariant()+'_REMOVE_INTENT')}).Count) {$expected.absent_allowed+=@($key)}
        }
        return $expected
    }
    function Restore-HostInstall {
        $service=Get-HostService
        $rows=@(Read-AclRecords $log)
        if (-not $rows.Count) {throw 'STOP_AND_PRESERVE_EMPTY_INSTALL'}
        $header=$rows[0]
        if ($header.phase -cne 'PREPARED' -or $header.manifest -cne $ApprovedManifestSha256 -or $header.operation_id -cne $operation -or $header.extra.image -cne $image) { throw 'STOP_AND_PRESERVE_INSTALL_BINDING' }
        if ($header.extra.upgrade -and -not $service) {throw 'STOP_AND_PRESERVE_MISSING_OLD_SERVICE'}
        # Validate every affected file before touching ACL or registration.
        # In particular, an old committed journal cannot remove a newer service.
        $hasFilePlan=Test-Path -LiteralPath $fileJournal
        if ($hasFilePlan) {$null=Invoke-HostFiles 'check-rollback' $null}
        elseif (-not $header.extra.upgrade) {$null=Invoke-HostFiles 'check-empty-roots' (Get-CreatedRootObservations $rows)}
        if ($rows[-1].phase -ceq 'ROLLED_BACK') {
            if (-not $header.extra.upgrade -and $service) {throw 'STOP_AND_PRESERVE_UNEXPECTED_SERVICE'}
            if (Test-Path -LiteralPath $fileJournal) {$null=Invoke-HostFiles 'rollback' $null}
            return
        }
        if ($rows[-1].phase -ceq 'COMMITTED' -and -not $Rollback) { throw 'COMMITTED_REQUIRES_EXPLICIT_ROLLBACK' }
        Write-HostPhase 'ROLLBACK_INTENT'
        # Compensate ACL before files. Both helpers observe known bytes/DACL
        # and refuse unknown state. Neither helper repeats forward effects.
        if ((Test-Path -LiteralPath $operationAcl) -and (Test-Path -LiteralPath $code)) {
            $null=Invoke-AclTransaction -Code $code -State $state -Journal $operationAcl -ManifestHash $ApprovedManifestSha256 -Recover
            Write-HostPhase 'ACL_ROLLBACK_VERIFIED'
        } elseif ((Test-Path -LiteralPath $operationAcl) -and -not @($rows | Where-Object {$_.phase -ceq 'ACL_ROLLBACK_VERIFIED'}).Count) {
            throw 'STOP_AND_PRESERVE_MISSING_ACL_TARGET'
        }
        if (-not $header.extra.upgrade -and $service) {
            if (-not @($rows | Where-Object {$_.phase -ceq 'SERVICE_CREATE_INTENT'}).Count) { throw 'STOP_AND_PRESERVE_UNOWNED_SERVICE' }
            Write-HostPhase 'SERVICE_DELETE_INTENT'
            $r=Invoke-CimMethod -InputObject $service -MethodName Delete
            if ($r.ReturnValue -ne 0 -or (Get-CimInstance Win32_Service -Filter "Name='$name'")) { throw 'STOP_AND_PRESERVE_SERVICE_DELETE' }
            Write-HostPhase 'SERVICE_DELETE_VERIFIED'
        }
        if (Test-Path -LiteralPath $fileJournal) {
            $null=Invoke-HostFiles 'rollback' $null
            Write-HostPhase 'FILES_ROLLBACK_VERIFIED'
            if (-not $header.extra.upgrade) {
                Write-HostPhase 'ROOTS_REMOVE_INTENT'
                $null=Invoke-HostFiles 'prune-created-root' $null
                Write-HostPhase 'ROOTS_REMOVED'
            } else {
                Write-HostPhase 'CREATED_DIRECTORIES_REMOVE_INTENT'
                $null=Invoke-HostFiles 'prune-created-directories' $null
                Write-HostPhase 'CREATED_DIRECTORIES_REMOVED'
            }
        } elseif (-not $header.extra.upgrade) {
            foreach ($key in @('state','code')) {
                $observations=Get-CreatedRootObservations (@(Read-AclRecords $log))
                Write-HostPhase ($key.ToUpperInvariant()+'_REMOVE_INTENT') @{identity=$observations[$key]}
                $null=Invoke-HostFiles ('remove-empty-'+$key+'-root') $observations
                Write-HostPhase ($key.ToUpperInvariant()+'_REMOVED')
            }
        }
        Write-HostPhase 'ROLLED_BACK' @{state_preserved=[bool]$header.extra.upgrade;fresh_roots_restored_absent=(-not $header.extra.upgrade)}
        @{outcome='ROLLED_BACK';allow_start=$false;state_preserved=[bool]$header.extra.upgrade;fresh_roots_restored_absent=(-not $header.extra.upgrade)} | ConvertTo-Json
    }
    if (-not $Execute) {
        @{outcome='PLAN_ONLY';source_commit=$m.source_commit;installer_version=$m.installer_version;upgrade=[bool]$Upgrade;allow_start=$false;allow_dispatch=$false;state_preserved=$true} | ConvertTo-Json
        return
    }
    # This is an internal dependency supplied by the trusted pinned publisher,
    # not a public CLI switch, caller-written proof file or an installation grant.
    Assert-HostMaintenance
    $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ADMINISTRATOR_REQUIRED' }
    $mutex=New-Object Threading.Mutex($false,'Global\RoktU1BridgeInstall')
    $held=$false; $log=$null
    try {
        try { $held=$mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $held=$true }
        if (-not $held) { throw 'INSTALLATION_LOCKED' }
        Assert-AclAuditRoot $audit
        foreach ($p in @($code,$state,$journal,$fileJournal,$operationAcl)) { Assert-NoReparseAncestors $p }
        foreach ($other in @(Get-ChildItem -LiteralPath $audit -Filter 'install-*.jsonl' -File)) {
            if ($other.FullName -ceq $journal) {continue}
            Assert-NoReparseAncestors $other.FullName
            $otherLog=[IO.FileStream]::new($other.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
            try {
                Assert-AclJournalFile $otherLog
                $otherRows=@(Read-AclRecords $otherLog)
                if (-not $otherRows.Count -or $otherRows[0].phase -cne 'PREPARED' -or $otherRows[-1].phase -cnotin @('COMMITTED','ROLLED_BACK')) {throw 'STOP_AND_PRESERVE_OTHER_INSTALL_PENDING'}
            } finally {$otherLog.Dispose()}
        }
        $service=Get-HostService
        $recovering=$RecoverInstall -or $Rollback
        if (-not $recovering) {
        $previous=$null
        if ($Upgrade) {
            if (-not $service -or -not (Test-Path -LiteralPath $state) -or $ApprovedPreviousReceiptSha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'EXACT_UPGRADE_OWNERSHIP_REQUIRED' }
            $previous=[IO.File]::ReadAllBytes($receiptPath)
            if ((Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ApprovedPreviousReceiptSha256) { throw 'PREVIOUS_RECEIPT_HASH_MISMATCH' }
            $old=[Text.Encoding]::UTF8.GetString($previous) | ConvertFrom-Json
            if ($old.schema -cne 'rokt.disabled-host-install-receipt.v2' -or $old.service_name -cne $name -or $old.account -cne $account -or $old.image -cne $image -or -not $old.files) { throw 'EXACT_UPGRADE_OWNERSHIP_REQUIRED' }
        } elseif ($service -or (Test-Path -LiteralPath $code) -or (Test-Path -LiteralPath $state)) { throw 'TARGET_ALREADY_EXISTS' }
        }
        $mode=if ($recovering) {[IO.FileMode]::Open} else {[IO.FileMode]::CreateNew}
        $log=[IO.FileStream]::new($journal,$mode,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read,4096,[IO.FileOptions]::WriteThrough)
        Assert-AclJournalFile $log
        $openedLength=$log.Length
        if ($recovering) {
            Restore-HostInstall
            return
        }
        $rootsBefore=Invoke-HostFiles 'observe-roots' $null
        $aclBefore=if ($Upgrade) {@{code=(Get-DaclText $code);state=(Get-DaclText $state)}} else {$null}
        Write-HostPhase 'PREPARED' @{image=$image;upgrade=[bool]$Upgrade;previous_receipt_sha256=$ApprovedPreviousReceiptSha256;roots_before=$rootsBefore;acl_before=$aclBefore;code_before=$(if ($Upgrade) {'PRESENT'} else {'ABSENT'});state_before=$(if ($Upgrade) {'PRESENT'} else {'ABSENT'})}
        if (-not $Upgrade) {
            Write-HostPhase 'CODE_CREATE_INTENT'
            New-Item -ItemType Directory -Path $code | Out-Null
            $observed=Invoke-HostFiles 'observe-roots' $null
            Write-HostPhase 'CODE_CREATE_VERIFIED' @{identity=$observed.code}
            New-RecordedAclStateRoot -Path $state -Journal $operationAcl -ManifestHash $ApprovedManifestSha256
            $observed=Invoke-HostFiles 'observe-roots' $null
            Write-HostPhase 'STATE_CREATE_VERIFIED' @{identity=$observed.state}
        }
        $fileBytes=@{}; $fileHashes=@{}; $fileSources=@{}
        foreach ($f in $m.files) {
            # Package preparation retains read-only pins. The helper checks
            # each approved digest again before creating durable blob backups.
            $fileSources[$f.path]=@{path=(Join-Path $package $f.path);sha256=$f.sha256}
            $fileHashes[$f.path]=$f.sha256
        }
        foreach ($relative in $generated.Keys) {
            $bytes=$generated[$relative]
            $fileBytes[$relative]=[Convert]::ToBase64String($bytes)
            $hasher=[Security.Cryptography.SHA256]::Create()
            try {$fileHashes[$relative]=([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()} finally {$hasher.Dispose()}
        }
        $receipt=@{schema='rokt.disabled-host-install-receipt.v2';source_commit=$m.source_commit;installer_version=$m.installer_version;manifest_sha256=$ApprovedManifestSha256;operation_id=$operation;service_name=$name;account=$account;image=$image;wrapper_sha256=$fileHashes['service/RoktU1Bridge.exe'];files=$fileHashes;state_preserved=$true}
        $fileBytes['config/installation.json']=[Convert]::ToBase64String([Text.UTF8Encoding]::new($false).GetBytes(($receipt | ConvertTo-Json -Depth 8 -Compress)))
        $request=@{files=$fileBytes;file_sources=$fileSources;manifest_sha256=$ApprovedManifestSha256;root_created=(-not $Upgrade);previous_receipt=$(if ($previous) {[Convert]::ToBase64String($previous)} else {$null});previous_receipt_sha256=$(if ($Upgrade) {$ApprovedPreviousReceiptSha256} else {$null})}
        Write-HostPhase 'FILES_INTENT'
        $null=Invoke-HostFiles 'prepare-apply' $request
        Write-HostPhase 'FILES_VERIFIED'
        if (-not $Upgrade) {
            Write-HostPhase 'SERVICE_CREATE_INTENT'
            $createArguments=@{Name=$name;DisplayName='Rokt U1 Bridge (disabled candidate)';PathName=$image;ServiceType=[uint32]16;ErrorControl=[uint32]1;StartMode='Disabled';DesktopInteract=$false;StartName=$account;StartPassword=''}
            $r=Invoke-CimMethod -ClassName Win32_Service -MethodName Create -Arguments $createArguments
            if ($r.ReturnValue -ne 0) { throw 'SERVICE_CREATE_REJECTED' }
            if (-not (Get-HostService)) { throw 'SERVICE_CREATE_READBACK_FAILED' }
            Write-HostPhase 'SERVICE_CREATE_VERIFIED'
        }
        $sid=(New-Object Security.Principal.NTAccount($account)).Translate([Security.Principal.SecurityIdentifier])
        Write-HostPhase 'ACL_INTENT'
        $null=Invoke-AclTransaction -Code $code -State $state -ServiceSid $sid.Value -Journal $operationAcl -ManifestHash $ApprovedManifestSha256
        Write-HostPhase 'ACL_VERIFIED'
        if (-not (Get-HostService)) { throw 'SERVICE_FINAL_READBACK_FAILED' }
        $null=Invoke-HostFiles 'status' $null
        Write-HostPhase 'COMMITTED' @{service_start='Disabled';service_state='Stopped';allow_dispatch=$false}
        @{outcome='COMMITTED';upgrade=[bool]$Upgrade;installed=$true;allow_start=$false;allow_dispatch=$false;allow_cancel_dispatch=$false;state_preserved=$true} | ConvertTo-Json
    } catch {
        # Never guess which cross-resource effect completed. Persist the failure
        # when possible; explicit RecoverInstall performs known compensation.
        $originalFailure=$_
        if ($log) {
            try {
                $records=@(Read-AclRecords $log)
                if ($records.Count -and $records[0].phase -ceq 'PREPARED' -and -not $recovering) {
                    Write-HostPhase 'FAILURE_COMPENSATION_INTENT'
                    Restore-HostInstall
                } elseif (-not $recovering -or $log.Length -ne $openedLength) {Write-HostPhase 'STOP_AND_PRESERVE'}
            } catch {if (-not $recovering -or $log.Length -ne $openedLength) {try {Write-HostPhase 'STOP_AND_PRESERVE'} catch {}}}
        }
        throw $originalFailure
    } finally {
        if ($log) {$log.Dispose()}
        if ($held) {$mutex.ReleaseMutex()}; $mutex.Dispose()
    }
}
