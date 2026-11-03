# Private stdio assertion bridge for a publisher-owned, Job-contained process.
# No endpoint, credentials, paths, install grant or lease-release operation.
function New-HostMaintenanceAuthority {
    $authority=[pscustomobject]@{Sequence=[long]0;Failed=$false}
    $authority | Add-Member -MemberType ScriptMethod -Name AssertHeld -Value {
        param([string]$Operation,[string]$Source,[string]$Manifest,[string]$Action)
        if ($this.Failed -or $this.Sequence -ge 4096 -or
            $Operation -cnotmatch '^[0-9a-f]{64}$' -or $Source -cnotmatch '^[0-9a-f]{40}$' -or
            $Manifest -cnotmatch '^[0-9a-f]{64}$' -or $Action -cnotin @('install','upgrade','recover','rollback')) {
            throw 'STOP_AND_PRESERVE_MAINTENANCE_CONTROL_CONTEXT'
        }
        try {
            $request=[ordered]@{schema='rokt.u1-maintenance-check.v1';sequence=$this.Sequence;
                target_operation_id=$Operation;source_commit=$Source;manifest_sha256=$Manifest;action=$Action}
            [Console]::Out.WriteLine('U1_MAINTENANCE:'+($request | ConvertTo-Json -Compress))
            [Console]::Out.Flush()
            $line=[Console]::In.ReadLine()
            if ($null -eq $line -or $line.Length -gt 128) {throw 'CONTROL_CLOSED_OR_LENGTH'}
            # Parent emits only this exact canonical acknowledgement. Reject
            # duplicate keys, extra fields, booleans-as-numbers and stale replies.
            $expected='{"sequence":'+$this.Sequence.ToString([Globalization.CultureInfo]::InvariantCulture)+',"held":true}'
            if ($line -cne $expected) {throw 'CONTROL_ACK_MISMATCH'}
            $this.Sequence++
            return $true
        } catch {
            $this.Failed=$true
            throw 'STOP_AND_PRESERVE_MAINTENANCE_CONTROL_LOST'
        }
    }
    return $authority
}
