# Phase 3C 生产部署执行手册 / Production Deployment Runbook

> 状态：仅供显式批准后的未来执行；本阶段没有执行以下部署命令。  
> Status: commands below are for a future explicitly approved deployment; none were executed in Phase 3C.

## 0. 固定变量与失败即停 / Fixed variables and fail-fast setup

在管理员 PowerShell 中逐段执行。任一步抛错都保持 maintenance hold 并停止。 / Run each block in an elevated PowerShell. Any exception means stop and keep the maintenance hold.

```powershell
$ErrorActionPreference = 'Stop'
$productionRoot = 'C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach'
$packageRoot = 'C:\Users\15690\Documents\ChatGPT\线下\roktandrazo-outreach-dev\PHASE3C_RELEASE_PACKAGE'
$python = 'C:\Users\15690\AppData\Local\Programs\Python\Python313\python.exe'
$deploymentRunId = 'phase3c-prod-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$backupRoot = Join-Path 'C:\Users\15690\WorkBuddy\deployment_backups\roktandrazo-outreach' $deploymentRunId
$liveDb = Join-Path $productionRoot 'data\bd_leads.db'
$dbBackup = Join-Path $backupRoot 'database\bd_leads.db'

if (-not (Test-Path -LiteralPath $productionRoot -PathType Container)) { throw 'PRODUCTION_ROOT_MISSING' }
if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) { throw 'RELEASE_PACKAGE_MISSING' }
New-Item -ItemType Directory -Path $backupRoot, (Join-Path $backupRoot 'database'), (Join-Path $backupRoot 'original_files'), (Join-Path $backupRoot 'secrets') | Out-Null
$deploymentRunId | Set-Content -LiteralPath (Join-Path $backupRoot 'deployment-run-id.txt') -Encoding utf8NoBOM
```

## 1. 调度器只读清点 / Read-only scheduler inventory

```powershell
$taskNames = @('RoktRazo-BD-PreSend','RoktRazo-BD-Outreach','RoktRazo-BD-PostSend','RoktRazo-BD-EndOfDay')
$taskInventory = foreach ($name in $taskNames) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskName $name -ErrorAction Stop
    [pscustomobject]@{ Name=$name; State=$task.State; Enabled=$task.Settings.Enabled; LastRunTime=$info.LastRunTime; NextRunTime=$info.NextRunTime; Actions=$task.Actions.Execute + ' ' + $task.Actions.Arguments }
}
$taskInventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backupRoot 'windows-scheduler-inventory.json') -Encoding utf8NoBOM
Get-ChildItem -LiteralPath (Join-Path $productionRoot '.workbuddy\automations') -Filter automation.toml -Recurse -ErrorAction SilentlyContinue |
    Select-Object FullName,Length,LastWriteTime,@{Name='SHA256';Expression={(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backupRoot 'workbuddy-automation-inventory.json') -Encoding utf8NoBOM
```

人工核验 / Operator verification:

- Inventory 的唯一权威必须是 WorkBuddy automation `1784775229336`，15:00 Asia/Shanghai。 / Inventory must have exactly one authority: WorkBuddy automation `1784775229336` at 15:00 Asia/Shanghai.
- PreSend、Outreach、PostSend、EndOfDay 必须分别只有上述一个 Windows task。 / Each remaining stage must have exactly the one Windows task listed above.
- 若发现重复 active trigger 或相关 `job_runs.status='running'`，立即中止。 / Abort on any duplicate active trigger or related running job.

## 2. 进入维护暂停 / Enter maintenance hold

先在 WorkBuddy UI 将 automation `1784775229336` 暂停并保存截图/审计记录；当前没有经验证的 WorkBuddy CLI，因此不得编造命令。随后： / First pause automation `1784775229336` in the WorkBuddy UI and retain audit evidence; no verified WorkBuddy CLI exists, so no command is invented. Then run:

```powershell
$taskNames | ForEach-Object { Disable-ScheduledTask -TaskName $_ -ErrorAction Stop | Out-Null }
$taskNames | ForEach-Object {
    if ((Get-ScheduledTask -TaskName $_).State -ne 'Disabled') { throw "MAINTENANCE_HOLD_FAILED: $_" }
}
```

确认没有运行中的阶段 / Confirm no stage is running:

```powershell
Set-Location -LiteralPath $productionRoot
& $python -c "import sqlite3,sys,json; c=sqlite3.connect('file:'+sys.argv[1].replace('\\','/')+'?mode=ro',uri=True); print(json.dumps([dict(zip(('run_id','stage','business_date','started_at'),r)) for r in c.execute(\"SELECT run_id,stage,business_date,started_at FROM job_runs WHERE status='running'\")],ensure_ascii=False)); c.close()" $liveDb
```

输出必须为 `[]`。 / Output must be `[]`.

## 3. SQLite 在线备份 / SQLite online backup

```powershell
& $python -c "import sqlite3,sys; s=sqlite3.connect('file:'+sys.argv[1].replace('\\','/')+'?mode=ro',uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.commit(); print('INTEGRITY_CHECK='+d.execute('PRAGMA integrity_check').fetchone()[0]); d.close(); s.close()" $liveDb $dbBackup
$dbHash = (Get-FileHash -LiteralPath $dbBackup -Algorithm SHA256).Hash
"$dbHash  database/bd_leads.db" | Set-Content -LiteralPath (Join-Path $backupRoot 'database-backup.sha256') -Encoding ascii
if ((& $python -c "import sqlite3,sys; c=sqlite3.connect('file:'+sys.argv[1].replace('\\','/')+'?mode=ro',uri=True); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()" $dbBackup) -ne 'ok') { throw 'DATABASE_BACKUP_INVALID' }
```

## 4. 原文件、配置和清单备份 / Original files, configuration, and manifests

```powershell
$existingFiles = @('bd_db.py','bd_orchestrator.py','discovery\discovery_service.py','discovery\providers\browser_maps.py','history_crosscheck.py')
foreach ($relative in $existingFiles) {
    $destination = Join-Path (Join-Path $backupRoot 'original_files') $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $productionRoot $relative) -Destination $destination
}
Copy-Item -LiteralPath (Join-Path $productionRoot '.env') -Destination (Join-Path $backupRoot 'secrets\.env')
(Get-Acl -LiteralPath (Join-Path $productionRoot '.env')) | Set-Acl -LiteralPath (Join-Path $backupRoot 'secrets\.env')
'discovery/website_resolver.py|PREVIOUSLY_MISSING' | Set-Content -LiteralPath (Join-Path $backupRoot 'new-files.txt') -Encoding ascii
$existingFiles | ForEach-Object { "{0}  {1}" -f (Get-FileHash -LiteralPath (Join-Path $productionRoot $_) -Algorithm SHA256).Hash,$_.Replace('\','/') } |
    Set-Content -LiteralPath (Join-Path $backupRoot 'production-baseline.sha256') -Encoding ascii
```

## 5. 基线 SHA 验证 / Baseline SHA validation

```powershell
$baseline = @{
 'bd_db.py'='5C18DBD91871EEC3AE742C0730D65294F87E84DB720ADA3C2E86860F96B3ADAB'
 'bd_orchestrator.py'='3B8DC6355C85476CD0277A1F484A09B94D10F8B89C4D3C82D57C58D389C3FE74'
 'discovery\discovery_service.py'='CC8D9C6B1E4E7C4FD72F43BDF61AD284BBADEC64FABD0FA1139E7F8755EF4627'
 'discovery\providers\browser_maps.py'='4530CD188E7ACA2AEE83CEF1CDA1B2324587B68342980B19ADCF5380591744C6'
 'history_crosscheck.py'='88FEF144EB4DCF88A318F8256FC1266F0B025350EC0BDC209DA4BF453D52F776'
}
foreach ($relative in $baseline.Keys) {
    if ((Get-FileHash -LiteralPath (Join-Path $productionRoot $relative) -Algorithm SHA256).Hash -ne $baseline[$relative]) { throw "BASELINE_SHA_MISMATCH: $relative" }
}
if (Test-Path -LiteralPath (Join-Path $productionRoot 'discovery\website_resolver.py')) { throw 'NEW_FILE_ALREADY_EXISTS' }
```

## 6. 应用精确补丁 / Apply exact patch

```powershell
Set-Location -LiteralPath $productionRoot
git -c core.autocrlf=false apply --check -- (Join-Path $packageRoot 'bd_db.py.patch')
git -c core.autocrlf=false apply -- (Join-Path $packageRoot 'bd_db.py.patch')
Copy-Item -LiteralPath (Join-Path $packageRoot 'bd_orchestrator.py') -Destination (Join-Path $productionRoot 'bd_orchestrator.py')
Copy-Item -LiteralPath (Join-Path $packageRoot 'history_crosscheck.py') -Destination (Join-Path $productionRoot 'history_crosscheck.py')
Copy-Item -LiteralPath (Join-Path $packageRoot 'discovery\discovery_service.py') -Destination (Join-Path $productionRoot 'discovery\discovery_service.py')
Copy-Item -LiteralPath (Join-Path $packageRoot 'discovery\providers\browser_maps.py') -Destination (Join-Path $productionRoot 'discovery\providers\browser_maps.py')
Copy-Item -LiteralPath (Join-Path $packageRoot 'discovery\website_resolver.py') -Destination (Join-Path $productionRoot 'discovery\website_resolver.py')
```

不得复制任何其他开发文件。 / Do not copy any other development file.

## 7. 目标 SHA 与冻结链验证 / Target SHA and frozen-chain validation

```powershell
$target = @{
 'bd_db.py'='C06FE7EBB3D6330BFCCF078634C5AB6DC16563423E8E975E44DA859AAA7CE0C7'
 'bd_orchestrator.py'='49E38BB1D80832E65F33752D4F7B0E64F5DF41753DC6056B4D1A5A2446ACECDC'
 'discovery\discovery_service.py'='B08761C83BA25A9E51CF45EA53DF8CAAA74FD29765469C6791672BFD65F5BAF3'
 'discovery\providers\browser_maps.py'='245ED26C92A1624CB8F1BC1754F1DF1EFC887D4343B86BA0CEEF769DC040D31A'
 'history_crosscheck.py'='0BA0D0CC25FE3BAA2404B31B8A01070AB02CB6D8CF8588CF3F68F527EFD60631'
 'discovery\website_resolver.py'='FFBCACDF68992217B6680B19E69713CED045684D2A48F7375DB1E092F667B33F'
}
$frozen = @{
 'bd_sender.py'='002D68A1E76D5F96AF6FDBABDCE54DA0AF3A93077D8A504DDD106A41FD018280'
 'daily_session.py'='F4559A34E87C9FCAB0C83FA92B6E4FBA4C0F5E284B77BB03F98AD1318C4088AF'
 'preflight_gate.py'='B1F44038C346BBF022A9D40575E330A1A73471A6DAFE0605D17EEACF3B8EF105'
 'campaign_eligible_v2.py'='1143BEDF563C0F76B883359362FFB2C2EA11C375FD923DC59768C5529CF3AD34'
 'final_send_plan.py'='26DE2F017390EDA767BEDDFE8FBD6BC438B78DDB430EEEBC4B96C72AA41D327F'
}
foreach ($set in @($target,$frozen)) { foreach ($relative in $set.Keys) { if ((Get-FileHash -LiteralPath (Join-Path $productionRoot $relative) -Algorithm SHA256).Hash -ne $set[$relative]) { throw "TARGET_OR_FROZEN_SHA_MISMATCH: $relative" } } }
```

## 8. 仅 Inventory 实时验证 / Inventory-only live validation

只有收到生产部署与生产写入的再次明确批准后才能执行。保持四个发送相关 task 与 WorkBuddy Inventory automation 暂停；该命令是唯一人工启动。 / Execute only after renewed explicit approval for deployment and production writes. Keep all schedulers paused; this is the only manual start.

```powershell
Set-Location -LiteralPath $productionRoot
& $python bd_orchestrator.py --stage inventory --live 2>&1 | Tee-Object -LiteralPath (Join-Path $backupRoot 'inventory-validation.log')
if ($LASTEXITCODE -ne 0) { throw 'INVENTORY_VALIDATION_FAILED' }
```

禁止运行 sender、SMTP、IMAP、`send-now` 或 Wrangler remote write。 / Never run sender, SMTP, IMAP, `send-now`, or Wrangler remote writes.

## 9. 证据复核 / Evidence review

```powershell
& $python -c "import sqlite3,json,sys; c=sqlite3.connect('file:'+sys.argv[1].replace('\\','/')+'?mode=ro',uri=True); c.row_factory=sqlite3.Row; rows=c.execute(\"SELECT id,linked_lead_id,website,source_url,validation_status,raw_payload_json FROM lead_discovery_results WHERE json_extract(raw_payload_json,'$.official_email_evidence.email') IS NOT NULL ORDER BY id DESC LIMIT 20\").fetchall(); print(json.dumps([dict(r) for r in rows],ensure_ascii=False,indent=2)); c.close()" $liveDb | Set-Content -LiteralPath (Join-Path $backupRoot 'evidence-review.json') -Encoding utf8NoBOM
```

人工逐项要求：十个证据字段齐全；excerpt 字面包含 email；HTTP/TLS 为 true；不得是猜测、脚本隐藏、目录/社媒或身份不匹配。 / Operator must verify all ten fields, literal email in excerpt, HTTP/TLS true, and no guessed, hidden, directory/social, or identity-mismatched source.

## 10. SAFE FSP 增量复核 / SAFE FSP delta review

在 Inventory 前后各运行一次并保存不同文件；这是 V2/MX 选择，不发送邮件。 / Run once before and once after Inventory and save to different files; this performs V2/MX selection but sends no mail.

```powershell
Set-Location -LiteralPath $productionRoot
& $python -c "import sqlite3,json; from campaign_eligible_v2 import select_candidates_for_plan_v2; from bd_db import DB_PATH; c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; x=select_candidates_for_plan_v2(c,200); print(json.dumps({'count':len(x),'lead_ids':[r['id'] for r in x]},ensure_ascii=False)); c.close()" |
    Set-Content -LiteralPath (Join-Path $backupRoot 'safe-fsp-after.json') -Encoding utf8NoBOM
```

中止条件 / Abort signals: duplicate leads/orgs, guessed or third-party email promotion, bad official-site match, any SMTP/IMAP connection, production exception, duplicate scheduler/job, target/frozen SHA drift, or evidence contract loss.

## 11. 回滚 / Rollback

默认只回滚代码并保留数据库作事故审计；如 incident commander 明确要求恢复数据库，再执行可选 DB restore。 / Default to code rollback while retaining the DB for incident audit; restore DB only with explicit incident-commander approval.

```powershell
$taskNames | ForEach-Object { Disable-ScheduledTask -TaskName $_ -ErrorAction SilentlyContinue | Out-Null }
foreach ($relative in $existingFiles) {
    Copy-Item -LiteralPath (Join-Path (Join-Path $backupRoot 'original_files') $relative) -Destination (Join-Path $productionRoot $relative) -Force
}
Remove-Item -LiteralPath (Join-Path $productionRoot 'discovery\website_resolver.py') -Force
foreach ($relative in $baseline.Keys) { if ((Get-FileHash -LiteralPath (Join-Path $productionRoot $relative) -Algorithm SHA256).Hash -ne $baseline[$relative]) { throw "ROLLBACK_SHA_MISMATCH: $relative" } }
```

可选、破坏性 DB 恢复（必须再次明确批准，且所有进程停止） / Optional destructive DB restore (requires renewed explicit approval and all processes stopped):

```powershell
& $python -c "import sqlite3,sys; s=sqlite3.connect('file:'+sys.argv[1].replace('\\','/')+'?mode=ro',uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.commit(); print(d.execute('PRAGMA integrity_check').fetchone()[0]); d.close(); s.close()" $dbBackup $liveDb
```

## 12. 恢复调度 / Resume schedulers

仅当 Inventory、证据、SAFE FSP、冻结哈希均通过且 Ian 再次明确批准后： / Only after Inventory, evidence, SAFE FSP, and frozen hashes pass and Ian explicitly approves resumption:

```powershell
$taskNames | ForEach-Object { Enable-ScheduledTask -TaskName $_ -ErrorAction Stop | Out-Null }
$taskNames | ForEach-Object { if (-not (Get-ScheduledTask -TaskName $_).Settings.Enabled) { throw "SCHEDULER_RESUME_FAILED: $_" } }
```

最后在 WorkBuddy UI 恢复唯一 Inventory automation `1784775229336`；再次只读清点，确认每阶段仅一个 authority。不得手工 SMTP。 / Finally resume only Inventory automation `1784775229336` in WorkBuddy UI; repeat read-only inventory and prove one authority per stage. No manual SMTP.

