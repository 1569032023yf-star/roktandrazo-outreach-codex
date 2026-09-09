# Phase 3A 回滚与中止计划 / Phase 3A Rollback and Abort Plan

状态 / Status: **PLAN ONLY — NO PRODUCTION ACTION TAKEN / 仅计划，未执行生产动作**

## 客观中止标准 / Objective abort criteria

下列任一项成立即停止 Inventory 验证、保持发送 maintenance hold，并进入回滚判定。 / If any condition below is true, stop Inventory validation, keep the send maintenance hold, and enter rollback assessment.

| 信号 / Signal | 客观阈值 / Objective threshold | 处理 / Action |
|---|---|---|
| 重复 lead / Duplicate leads | 同一 provider result/place id、同一规范化业务+地址，或同一 location key 新增超过 1 条 / more than one new row for the same identity | ABORT + rollback code; quarantine new run rows / 中止、回滚代码、隔离本 run 新数据 |
| 重复 org / Duplicate organizations | 同一 `organization_key` 产生多个新组织身份，或不同地址被共享电话错误合并 / duplicate org identity or shared-phone location collapse | ABORT |
| 错误官网匹配 / Bad official-site match | 任何已提升记录的官网与业务身份不符 / any promoted identity mismatch | ABORT |
| 目录/第三方作为官网 / Directory or third-party site promoted | `> 0` | ABORT |
| 猜测邮箱 / Guessed email promoted | `> 0`，包括未在可见摘录逐字出现 / including email absent from literal visible excerpt | ABORT |
| 隐藏/script 邮箱 / Hidden or script-only email promoted | `> 0` | ABORT |
| HTTP/TLS/跨域失败仍提升 / Failed fetch promoted | `> 0` | ABORT |
| 证据契约缺失 / Incomplete evidence | 任一 promoted email 缺 requested/final URL、成功 HTTP/TLS、fetched_at、可见摘录、content hash、source type / any required field absent | ABORT |
| 生产错误 / Production error | 未捕获异常、DB locked/corrupt、provider 持续失败、异常错误率，或 run 未正常关闭 / unhandled exception, DB lock/corruption, sustained provider failure, abnormal error rate, or unclosed run | ABORT |
| 调度器重复 / Scheduler duplication | 同 stage/date 同时运行 >1、同一窗口出现第二个 active trigger、或非权威入口执行 / concurrent runs, second active trigger, or non-authoritative entrypoint | ABORT |
| 冻结链漂移 / Frozen-chain drift | 任一冻结 SHA 与基线不同 / any frozen hash differs | ABORT before send |
| SMTP/IMAP 连接 / SMTP/IMAP connection | Inventory-only 窗口任何连接 `> 0` | INCIDENT + ABORT |

## 回滚准备物 / Rollback assets

中文：执行部署前必须具备并校验以下材料：SQLite online backup；5 个被修改现有文件的原始副本及 SHA；新增 `discovery/website_resolver.py` 的“原先不存在”清单；原 `.env` 哈希和保密备份；调度器枚举；部署 run_id、起止时间与新增记录 ID 清单。备份不得放入会被应用扫描/执行的生产代码目录。

English: Before deployment, require and verify: a SQLite online backup; original copies and SHA hashes of all five modified existing files; a manifest proving `discovery/website_resolver.py` did not previously exist; protected `.env` backup and hash; scheduler inventory; and the deployment run_id/time range/new-record ID list. Do not place backups in a production code path that the application scans or executes.

`ROLLBACK_READY = false_until_backup_and_final_patch_manifest_exist`

## 回滚顺序 / Rollback sequence

1. 中文：维持 PreSend/Outreach/PostSend/EndOfDay maintenance hold，禁止手工 SMTP。English: Keep all send-related stages on maintenance hold; no manual SMTP.

2. 中文：采集只读故障证据：日志、run/job lock、变更前后计数、异常记录 ID、调度器状态和全部目标文件哈希。English: Capture read-only incident evidence: logs, run/job locks, before/after counts, affected IDs, scheduler state, and target-file hashes.

3. 中文：恢复 5 个既有文件的原始字节，删除本次新增的 `discovery/website_resolver.py`；删除仅限该 manifest 中“部署前不存在”的文件。English: Restore original bytes for the five existing files and remove the newly deployed resolver only if the manifest proves it did not exist before deployment.

4. 中文：重新计算生产文件与冻结链哈希；冻结文件不得从备份“顺带恢复”，因为它们从未属于补丁。English: Recompute production and frozen-chain hashes. Never restore frozen files incidentally; they were never patch members.

5. 中文：数据库优先采用“保留业务记录、回滚代码”的兼容路径。只把部署 run 留下的 `running` job 标为 `failed/aborted`，并只用 matching holder 释放其 lock。不得批量删除 `system_config`、leads 或 discovery 数据。English: Prefer the compatible path: retain business records and revert code. Mark only the deployment run's still-running job as failed/aborted and release only its holder-matching lock. Never bulk-delete system_config, leads, or discovery data.

6. 中文：只有在数据污染已被证明且精确行级逆向不可安全执行时，才从 SQLite online backup 整库恢复；这会丢失备份后的合法写入，必须另行取得明确批准并先导出差异。English: Restore the whole SQLite backup only if proven contamination cannot be reversed safely at row level. Because this loses legitimate post-backup writes, obtain separate explicit approval and export the delta first.

7. 中文：用开发/隔离数据库验证原生产代码可启动、schema 可读、冻结选择器可读执行；不得在回滚验证中发送。English: Validate the original production code against a development/isolated DB for startup, schema readability, and frozen selector execution; do not send during rollback validation.

8. 中文：输出事故报告并由 Ian 决定是否恢复正常 scheduler。WorkBuddy/Codex 不得自行恢复发送。English: Produce an incident report and let Ian decide whether normal scheduling resumes. WorkBuddy/Codex must not self-resume sending.

## 数据逆向原则 / Data reversal rules

- 中文：以 `run_id`、时间窗口、provider result id、linked lead id 和审计记录构造精确候选清单；先导出，再隔离，不直接删除。English: Build an exact candidate set using run_id, time window, provider result id, linked lead id, and audit records; export first, quarantine before deletion.
- 中文：若新记录未污染且旧代码可忽略新增字段/状态，则保留。English: Retain clean new records when old code can safely ignore their fields/statuses.
- 中文：任何已发送、被回复、bounce、suppression、授权或计划事实不得因代码回滚而抹除。English: Never erase send, reply, bounce, suppression, authorization, or plan facts during code rollback.
- 中文：若最终证据方案引入 schema，必须在最终迁移中单独给出 downgrade 能力或明确声明 forward-only；本审查不假定可自动删列。English: If the final evidence design introduces schema, its migration must separately define downgrade support or explicitly be forward-only; this review does not assume automatic column removal.

## 回滚完成判定 / Rollback completion criteria

```text
ORIGINAL_CODE_HASHES_RESTORED = true
NEW_RESOLVER_REMOVED_IF_DEPLOYED = true
FROZEN_FILES_CHANGED = 0
ACTIVE_DEPLOYMENT_JOB_RUNS = 0
DEPLOYMENT_LOCKS_HELD = 0
DATABASE_INTEGRITY_CHECK = PASS
REAL_SMTP_CONNECTIONS_DURING_ROLLBACK = 0
SCHEDULER_RESUME_APPROVED_BY_IAN = true/false
```

中文：最后一项为 `false` 时，系统保持发送暂停；回滚技术完成不等于自动恢复发送。 / English: If the final field is false, sending remains held. Technical rollback completion does not authorize automatic send resumption.

## 当前状态 / Current status

`ROLLBACK_READY = false`  
中文：回滚计划已完成，但只有在最终补丁 manifest、生产备份路径、备份可读性验证和实时 scheduler 清单均存在后，执行层面才可标为 ready。 / English: The rollback plan is complete, but operational readiness requires the final patch manifest, production backup path, readable-backup verification, and live scheduler inventory.
