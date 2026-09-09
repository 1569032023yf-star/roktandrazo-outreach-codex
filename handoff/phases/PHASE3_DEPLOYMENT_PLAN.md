# Phase 3A 可逆部署计划 / Phase 3A Reversible Deployment Plan

状态 / Status: **PLAN ONLY — DO NOT DEPLOY / 仅计划，不部署**

## 放行前条件 / Preconditions

中文：在取得显式生产部署批准之前，先在开发中完成并验证两项：把 stale `job_runs` 清理与替代 run 插入置于同一 `BEGIN IMMEDIATE` 事务；把正常库存链的抓取证据完整持久化（requested/final URL、HTTP/TLS、fetched_at、可见摘录、content hash、email、source type）。之后重新生成生产基线选择性补丁、哈希清单，并再次通过 303 测试及正/负/幂等受控测试。

English: Before explicit production approval, complete and validate two development fixes: keep stale `job_runs` cleanup and replacement-run insertion in one `BEGIN IMMEDIATE` transaction; and persist the normal inventory fetch evidence contract (requested/final URL, HTTP/TLS, fetched_at, visible excerpt, content hash, email, and source type). Then regenerate the production-baseline selective patch and hash manifest, and rerun the 303-test suite plus positive, negative, and idempotency tests.

## 单一调度权威 / Single scheduler authority

`AUTHORITATIVE_TRIGGER_PER_STAGE =`

| Stage | 唯一权威 / Intended sole authority | 命令入口 / Entrypoint |
|---|---|---|
| Inventory | WorkBuddy automation `1784775229336`, 15:00 Asia/Shanghai | `bd_orchestrator.py --stage inventory --live` |
| PreSend | Windows Scheduled Task `RoktRazo-BD-PreSend`, 22:30 | `bd_orchestrator.py --stage pre-send --live` |
| Outreach | Windows Scheduled Task `RoktRazo-BD-Outreach`, 23:00 | `bd_orchestrator.py --stage outreach --live` |
| PostSend | Windows Scheduled Task `RoktRazo-BD-PostSend`, 00:10 | `bd_orchestrator.py --stage post-send --live` |
| EndOfDay | Windows Scheduled Task `RoktRazo-BD-EndOfDay`, 00:25 | `bd_orchestrator.py --stage end-of-day --live` |

中文：这是代码与历史生产证据支持的目标所有权，不是当前实时注册状态证明。部署执行前必须只读枚举 WorkBuddy 与 Windows Scheduler，证明每个 stage 恰好一个 active trigger；历史/一次性/周末重复 Inventory 若仍 active 必须中止部署，不能在本阶段擅自停用。

English: This is intended ownership supported by code and historical evidence, not proof of current live registration. Before deployment, enumerate WorkBuddy and Windows Scheduler read-only and prove exactly one active trigger per stage. If legacy, one-off, or weekend duplicate Inventory triggers remain active, abort; do not disable them under this phase's authority.

`SCHEDULER_CHANGE_REQUIRED = false_if_live_audit_confirms_single_authority`  
中文：不需要永久拓扑变更；部署窗口内的临时 maintenance hold/pause 需要另行明确操作批准。 / English: No permanent topology change is intended; a temporary maintenance hold/pause requires separate explicit operational approval.

## 八步部署序列 / Eight-step deployment sequence

### STEP 1 — 备份与基线 / Backup and baseline

中文：选择无发送阶段运行的维护窗口。只读确认单一调度权威、无 `running` 的相关 `job_runs`/run lock。使用 SQLite online backup API 生成带时间戳的数据库备份；备份 5 个现有目标文件、生产 `.env`（不展示内容）、当前哈希、依赖版本和调度器清单。验证备份可读取并记录恢复路径。冻结链再次哈希。

English: Choose a maintenance window with no send stage running. Read-only verify sole scheduler ownership and no relevant running job/run lock. Use SQLite's online backup API for a timestamped database backup; back up the five existing target files, production `.env` without exposing it, hashes, dependency versions, and scheduler inventory. Verify the backup is readable and record its restore path. Rehash the frozen chain.

### STEP 2 — 部署上游补库代码 / Deploy upstream replenishment code

中文：仅应用最终签名 manifest 中的选择性 `bd_db.py` 补丁、4 个批准替换文件及 1 个新增 resolver。应用前逐个校验生产基线哈希，任何漂移立即停止。禁止携带开发守卫、测试、数据库、报告或 runtime 文件。

English: Apply only the final signed-manifest selective `bd_db.py` patch, four approved replacements, and one resolver addition. Verify every production baseline hash immediately before applying; stop on any drift. Do not ship development guards, tests, databases, reports, or runtime files.

### STEP 3 — 配置与依赖 / Configuration and dependencies

中文：不复制 `.env`，不批量安装依赖。只读验证现有 `DISCOVERY_PROVIDER=browser_maps`、`BROWSER_MAPS_MODE=direct`、代理存在；使用生产 Python 执行 import 和 Playwright Chromium 启动/关闭 smoke check。预期新增依赖与环境变更均为 0。

English: Do not copy `.env` or bulk-install dependencies. Read-only verify existing provider/mode/proxy settings and run production-Python import plus Playwright Chromium launch/close smoke checks. Expected added dependencies and environment changes are both zero.

### STEP 4 — 数据迁移 / Migration

中文：若最终证据设计复用现有字段，则显式记录 `NO-OP`；若最终设计要求新列，必须先单独审批包含前置 schema assertion、幂等迁移、迁移后 assertion 与逆向兼容性检查的脚本。当前不得运行 `migrate_city_outreach_40.py`。

English: Record an explicit no-op if the final evidence design reuses existing fields. If it needs new columns, obtain separate approval for an idempotent migration with pre/post schema assertions and backward-compatibility checks. Do not run `migrate_city_outreach_40.py` as part of the current candidate.

### STEP 5 — 仅 Inventory 生产验证 / Inventory-only production validation

中文：在显式部署及生产写入批准后，保持 PreSend/Outreach/PostSend/EndOfDay maintenance hold，只执行一次 `bd_orchestrator.py --stage inventory --live`。不得调用 sender、SMTP、IMAP、send-now 或 Wrangler remote write。记录运行前后计数、run_id、provider/mode、每个漏斗状态和拒绝原因。

English: After explicit deployment and production-write approval, keep PreSend/Outreach/PostSend/EndOfDay under maintenance hold and execute exactly one `bd_orchestrator.py --stage inventory --live`. Do not invoke sender, SMTP, IMAP, send-now, or Wrangler remote writes. Record before/after counts, run_id, provider/mode, funnel states, and rejection reasons.

### STEP 6 — 官网/邮箱/证据核验 / Verify website, email, and evidence records

中文：人工抽查至少 5 个真实结果：名称、官网、final URL、身份证据、邮箱、可见摘录、content hash、source type。要求目录站为官网=0、猜测邮箱=0、隐藏脚本邮箱=0、身份错配提升=0、HTTP/TLS 失败提升=0。证据摘录必须逐字包含邮箱。

English: Inspect at least five real results for name, official website, final URL, identity evidence, email, visible excerpt, content hash, and source type. Require zero directory-as-official, guessed email, hidden-script email, identity-mismatch promotion, and HTTP/TLS-failure promotion. The evidence excerpt must literally contain the email.

### STEP 7 — 验证 SAFE FSP 增长 / Verify SAFE FSP growth

中文：生产没有 `dev_safe_fsp` 表，也不应新增同名表。SAFE FSP 定义为冻结 `select_candidates_for_plan_v2`/`campaign_eligible_check_v2` 实际接受、且可进入 Final Send Plan 的唯一组织集合。以同一只读选择查询记录验证前后 eligible unique organizations；增长必须来自本次新证据记录，并满足 MX、历史、抑制、时区与 V2。重复运行相同输入不得增加 lead/org/eligible 重复数。

English: Production has no `dev_safe_fsp` table and must not gain one. SAFE FSP is the unique-organization set accepted by the frozen V2 selector/check and eligible for a Final Send Plan. Record before/after eligible unique organizations using the same read-only selection path; growth must trace to the new evidence records and pass MX, history, suppression, timezone, and V2. Replaying the same input must add no duplicate lead, organization, or eligible entry.

### STEP 8 — 恢复正常调度 / Resume normal scheduling

中文：只有 Steps 5–7 全部通过、冻结哈希不变、无中止信号并由 Ian 明确批准恢复后，才解除临时 maintenance hold。不得手工 SMTP；后续仍由既定 Outreach scheduler 与冻结 Preflight/V2/MX/授权/时间窗/40-day quota 控制。

English: Release the temporary maintenance hold only after Steps 5–7 pass, frozen hashes remain unchanged, no abort signal exists, and Ian explicitly approves resumption. Do not use manual SMTP; subsequent sending remains under the designated Outreach scheduler and frozen Preflight/V2/MX/authorization/window/40-per-day controls.

## Inventory-only 验收字段 / Acceptance fields

```text
PROVIDER_MODE = browser_maps/direct
INVENTORY_RUNS_STARTED = 1
CONCURRENT_OR_DUPLICATE_RUNS = 0
NEW_UNIQUE_PLACES >= 0
WEBSITE_VERIFIED >= 1
VISIBLE_FIRST_PARTY_EMAILS >= 1
FULL_EVIDENCE_RECORDS >= 1
DIRECTORY_AS_OFFICIAL_SITE = 0
GUESSED_EMAILS_PROMOTED = 0
THIRD_PARTY_EMAILS_PROMOTED = 0
IDENTITY_MISMATCH_PROMOTED = 0
DUPLICATE_LEADS = 0
DUPLICATE_ORGS = 0
SAFE_FSP_UNIQUE_ORG_DELTA >= 1
REAL_SMTP_CONNECTIONS = 0
FROZEN_FILES_CHANGED = 0
```

## 当前就绪状态 / Current readiness

`INVENTORY_ONLY_VALIDATION_PLAN_READY = true`  
`READY_FOR_EXPLICIT_DEPLOYMENT_APPROVAL = false`

中文：计划已就绪，但补丁仍有两个开发级放行缺口，当前不应请求执行生产部署。 / English: The plan is ready, but two development release blockers remain; production execution approval should not yet be requested.
