# 交接变更日志 / Handoff Changelog

## Repository initialization — 2026-09-09 / 仓库初始化 — 2026-09-09

### 中文

- 在 `roktandrazo-outreach-dev` 内创建独立 Git 根，分支设为 `main`。
- 唯一远端设为私有 Codex 开发仓库 `roktandrazo-outreach-codex`；未指向或修改 WorkBuddy 生产备份仓库。
- 扩充 `.gitignore`，排除环境文件、数据库及生产派生副本、凭据、令牌、密钥、备份树、缓存、日志、PID 和运行时制品。
- 将 Phase 2/3 的关键双语报告归档至 `handoff/phases/`，并按当前真实 blocker 更新状态文件。
- 本条记录不代表生产发布批准；生产文件写入、生产数据库写入和真实 SMTP 均为 0。

### English

- Created an independent Git root inside `roktandrazo-outreach-dev` with branch `main`.
- Configured the private Codex development repository `roktandrazo-outreach-codex` as the sole remote; the WorkBuddy production-backup repository was neither targeted nor modified.
- Expanded `.gitignore` to exclude environment files, databases and production-derived copies, credentials, tokens, keys, backup trees, caches, logs, PID files, and runtime artifacts.
- Archived the key bilingual Phase 2/3 reports under `handoff/phases/` and updated the status artifacts with the current verified blocker.
- This entry does not authorize production deployment; production-file writes, production-database writes, and real SMTP connections remain zero.

## Phase 3C-NET — 2026-09-09

### 中文

- 建立仅含六个获批制品的发布包，并在全新生产源码副本中完成精确应用排练；六个目标 SHA 全部匹配 Phase 3B manifest。
- 验证开发专用导入、开发 DB 路径、测试专用导入、`dev_safe_fsp` 与 `safe_replenishment` 引用均为 0。
- 重新运行全套测试：303/303 通过；并发、负向安全和幂等定向测试为 5 passed、3 subtests passed。
- 使用 SQLite 只读 online backup 创建生产 DB 演练副本，`PRAGMA integrity_check=ok`；未写生产数据库。
- 完成 20 个商户上限的联网 Inventory 演练：16 次逻辑 Google Maps 请求、8 次官网请求、6 个 fail-closed 网络错误。
- 创建 1 条完整第一方可见邮箱证据：`Instant Replay Sports` / `ithacainstantreplaysports@yahoo.com`。
- 确认 blocker：完整证据留在 `lead_discovery_results.id=293`，但 `linked_lead_id=NULL`；已有同身份 `leads.id=1085` 未被安全更新，所以 V2/MX/SAFE FSP 均为 0。
- 未部署；SMTP、IMAP、生产文件写入、调度器变更、冻结文件变更均为 0。

### English

- Built a release package containing only the six approved artifacts and rehearsed its exact application to a fresh production source copy; all six target hashes match the Phase 3B manifest.
- Verified zero development-safety imports, development DB paths, test-only imports, `dev_safe_fsp` references, and `safe_replenishment` references in the package.
- Re-ran the complete suite: 303/303 passed; targeted concurrency, negative-safety, and idempotency validation reported 5 passed plus 3 subtests.
- Created the production DB rehearsal copy through a read-only SQLite online backup with `PRAGMA integrity_check=ok`; the live DB was never written.
- Completed the capped 20-merchant networked Inventory rehearsal: 16 logical Google Maps requests, 8 official-site requests, and 6 fail-closed network errors.
- Created one complete visible first-party evidence record for `Instant Replay Sports` / `ithacainstantreplaysports@yahoo.com`.
- Confirmed the blocker: complete evidence remained in `lead_discovery_results.id=293` with `linked_lead_id=NULL`; existing same-identity `leads.id=1085` was not safely updated, leaving V2/MX/SAFE FSP at zero.
- No deployment occurred; SMTP, IMAP, production-file writes, scheduler changes, and frozen-file changes were all zero.
## Phase 3D — 2026-09-09

- 中文：复现并修复已有线索官方证据关联；新增 9 项回归，312 项测试及 59 子测试通过。新鲜生产 DB 开发副本中关联 1085，真实 MX/V2 通过，开发 SAFE FSP 新增 1，重放幂等。重新生成六制品发布包与最终 SHA 清单。生产与冻结文件未改，未部署。
- English: Reproduced and fixed existing-lead official-evidence linkage. Added nine regressions; 312 tests and 59 subtests pass. A fresh development production-DB copy linked lead 1085, passed real MX/frozen V2, and inserted one development SAFE FSP idempotently. Regenerated six release artifacts and final SHA manifest. No production/frozen changes or deployment.
## Phase 4A — 2026-09-09

- 中文：只读部署前检查发现 Windows 与 WorkBuddy 的 PreSend/Outreach 重复 active 触发器，按手册中止；尚未暂停调度、备份、部署或运行生产 Inventory。生产写入为 0，等待维护与恢复范围确认。
- English: Read-only pre-deployment checks found overlapping active Windows and WorkBuddy PreSend/Outreach triggers. Aborted per runbook before any hold, backup, deployment, or live Inventory. Zero production writes; awaiting maintenance/resume scope clarification.
## Phase 4A 后续授权 / Follow-up authorization

- 中文：WorkBuddy 四个主要阶段已 PAUSED；禁用重复 Windows 任务遭操作系统拒绝，复核仍启用 2/2。未部署，等待管理员禁用；不恢复调度。
- English: Four main WorkBuddy stages are PAUSED. OS denied disabling duplicate Windows tasks; both remain enabled. No deployment; awaiting administrator action, with no scheduler resume.
## Phase 4A — 2026-09-10 部署 / Deployment

- 中文：按批准 commit 部署六个制品，目标6/6、冻结0变更，已建最新在线回滚备份。唯一一次生产 Inventory 完成，官网+2、可见第一方邮箱/完整证据各+1，无新增 lead/schema/发送记录。验收后91域名MX被安全审查拒绝，SAFE AFTER待测；调度不恢复。
- English: Deployed six artifacts from the approved commit with 6/6 target hashes, zero frozen changes and fresh online rollback backup. One production Inventory completed: two websites and one visible first-party email/full evidence record; no new lead/schema/send records. Safety review blocked post-run 91-domain MX; SAFE AFTER remains pending. Scheduling stays held.
## Phase 4A 最终验收 / Final acceptance — 2026-09-10

- 中文：按新增明确授权完成一次MX/V2测量。91原始域名字符串归一为90唯一域名，MX正常32、NXDOMAIN51、无路由7、DNS错误0。V2/SAFE均1，1085通过；冻结0变更，邮件/计划/授权/调度变更均0。调度继续暂停。
- English: Completed one explicitly authorized MX/V2 measurement. 91 raw domain strings normalize to 90 unique domains: 32 OK, 51 NXDOMAIN, 7 no route, 0 DNS errors. V2/SAFE both equal one; lead 1085 passes. Zero frozen, mail, plan, authorization or scheduler changes. Scheduling remains held.
## Phase 4A.1 — 2026-09-10 审计停止 / Audit stop

- 中文：离线复现BroadReady34/30误完成。新鲜副本全量空邮箱482，排除51联系表单/3已发送后为428；其中166无staging关联。已关联262条状态亦非直接安全消费状态。按第7节停止，无源码或生产更改，未执行修复测试/Inventory；冻结SHA未变。
- English: Reproduced BroadReady34/30 false completion offline. Fresh copy has482 empty emails, or428 excluding51 contact-form/3 sent;166 lack linked staging. All262 linked rows also lack directly consumable safe statuses. Stopped under section7 without source/production changes or fix tests/Inventory; frozen hashes unchanged.

## Phase 4A.1B — 2026-09-10 已关联积压重连 / Linked backlog reconnection

- 中文：完成262条精确路由审计；仅修改两个生产源文件，加入当前城市有界安全重入和冻结V2唯一组织完成信号。166条未关联待补库不变。322项及76子测试通过；冻结0变更。首轮开发驱动位置被护栏拦截，换用开发驱动和新副本后真实复验18条：解析11、后处理7、新邮箱/完整证据/关联增量均0，SAFE 1→1，BroadReady34但正确记录partial、gap29。未部署、未恢复调度，生产写入/邮件/FSP/授权均0。窄补丁可审查，不表示库存目标达成。
- English: Completed exact routing audit of262 rows; changed only two production source files for bounded current-city safe re-entry and frozen-V2 unique-org completion. The166 actionable unlinked leads are unchanged.322 tests and76 subtests pass; frozen changes0. Initial external driver location was blocked by guards; a development driver and fresh copy then processed18 real rows:11 resolution,7 postprocess, zero new email/full-evidence/linkage, SAFE1→1. BroadReady34 correctly yields partial with gap29. No deployment/resume or production/mail/FSP/authorization writes. The narrow patch is review-ready, not inventory-target-complete.
