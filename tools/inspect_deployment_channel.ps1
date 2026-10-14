# 仅查询通道元数据，不部署、不改权限、不启动服务。
# Read channel metadata only; no deployment, permission changes, or service starts.
$ErrorActionPreference = 'Stop'
$channelReport = [ordered]@{
    description_zh = '部署通道只读诊断；不是部署执行器或生产门禁证明'
    description_en = 'Read-only channel diagnostics; not a release executor or proof of production gates'
    observed_at_utc = [DateTime]::UtcNow.ToString('o')
    services = @()
    endpoints = @()
    errors = @()
    production_deployed = $false
    smtp_enabled_required = 0
    smtp_runtime_verified = $false
    emails_sent_by_this_script = 0
}
try {
    $channelReport.services = @(Get-CimInstance Win32_Service -Filter "Name = 'BDExecutionHost' OR Name = 'RoktDeploymentExecutor'" |
        Select-Object Name, State, StartMode)
} catch {
    $channelReport.errors += 'SERVICE_QUERY_FAILED / 服务查询失败'
}
try {
    $channelReport.endpoints = @(Get-PSSessionConfiguration -Name 'RoktDeployment' -ErrorAction Stop |
        Select-Object Name, PSVersion)
} catch [System.UnauthorizedAccessException] {
    $channelReport.errors += 'ENDPOINT_QUERY_ACCESS_DENIED / 端点查询需要管理员权限；存在性未知'
} catch {
    $channelReport.errors += 'ENDPOINT_QUERY_UNVERIFIED / 端点查询未确认；需管理员核实存在性及访问权'
}
$channelReport | ConvertTo-Json -Depth 5
