# Codex 工程与部署责任制 / Codex Engineering and Deployment Charter

生效依据：用户于 2026-10-14 授予的长期工程与受控生产部署授权。后续正常工程阶段默认适用；历史报告保留当时事实，其旧责任划分不再约束新发布。

Authority: the user's continuing engineering and controlled production deployment authorization dated 2026-10-14. This charter governs subsequent routine engineering. Historical reports retain their facts; their former division of deployment responsibility does not govern new releases.

## 责任与工作流程 / Responsibility and workflow

Codex 是 rokt&razo BD 系统正常客户发现、官网验证、公开商务邮箱获取、历史去重和可靠性的主要开发与发布负责人。持续执行：分析 → 必要测试 → 开发 → 测试 → 自检修复 → 复测 → 独立审查 → 部署检查 → 备份 → 受控部署 → 正常生产计划验收 → 监控 → 必要时安全回滚 → 提交、推送与报告。普通工程发布通过门禁后无需逐次批准，不默认转交 WorkBuddy 部署。独立审查应单独复核最终差异和失败路径，不能以测试替代审查。

Codex owns development and release of routine customer discovery, official-site verification, public business email collection, history deduplication, and reliability. Persist through analysis, necessary tests, implementation, testing, self-review and repair, retesting, independent review, release checks, backup, controlled deployment, scheduled production acceptance, monitoring, safe rollback when needed, commits, pushes, and reporting. Routine gated releases require no repeated approval and are not assigned to WorkBuddy by default. Independently review final differences and failure paths; tests do not replace review.

WorkBuddy 保留正式运行环境、客户数据库和运行记录。唯一正式 Inventory 为 `1784775229336`，保持现有受控预算，不新建并行生产 Inventory 调度器。SAFE40、SAFE50 或更高数量不是停止发现的理由。

WorkBuddy remains the production runtime and custodian of the customer database and execution records. The sole production Inventory is `1784775229336`; preserve its controlled budget and add no parallel production Inventory scheduler. SAFE40, SAFE50, or higher totals must not stop discovery.

## 发送与数据边界 / Sending and data boundaries

持续发现真实新客户，全部商业邮件暂不发送。不得发送开发或测试商业邮件、开启 SMTP、恢复 PreSend / Preflight / Outreach、创建可执行发送授权或发送计划、降低 V1 / V2 / MX / 历史 / 退订 / 抑制标准、删除历史客户或既有 SAFE 批次、执行破坏性数据库迁移、修改真实发件账户、凭据或敏感权限。上述业务决策需要用户另行明确授权。三版 V6 短邮件保持候选，不部署、不发送。

Continue discovering real new customers while all commercial email remains frozen. Do not send development or test commercial email, enable SMTP, resume PreSend / Preflight / Outreach, create executable sending authorizations or schedules, weaken V1 / V2 / MX / history / unsubscribe / suppression standards, delete historical customers or existing SAFE batches, perform destructive database migrations, or modify real sender accounts, credentials, or sensitive permissions. These business decisions require separate explicit user authorization. All three V6 short-email variants remain candidates and must neither be deployed nor sent.

## 发布门禁与通道 / Release gates and channel

每次发布必须通过正式授权的生产执行入口核实：实际运行文件 SHA-256；生产版本与补丁精确兼容；备份完整性；最小修改范围；定向测试通过；无新增关键回归；当前安全部署窗口；运行锁正常；已验证回滚方案；SMTP 和发送任务仍关闭。优先精确补丁和原子替换，禁止整个工作树覆盖生产；指纹不匹配立即停止。最终检查至替换后核验期间，必须保持与正式 Inventory 协调的互斥，防止启动竞态；历史报告和单次无锁快照不能替代实时门禁。

Every release must use the authorized production entry point to verify actual runtime SHA-256, exact version compatibility, backup integrity, minimal scope, passing targeted tests, no new critical regressions, a current safe deployment window, healthy run locks, verified rollback, and frozen SMTP and sending tasks. Prefer exact patches and atomic replacement; never overwrite production with a whole working tree. Stop on fingerprint mismatch. Maintain exclusion coordinated with the official Inventory through final checks and post-replacement verification; historical reports and a single unlocked snapshot cannot replace live gates.

开发隔离继续有效，不得修改安全策略、禁网变量、访问控制或换执行环境绕过护栏获取生产权限。没有合法通道时，完成可安全执行的工作并报告具体阻塞，准备一次性接入。执行器在独立获授权环境运行，限定目标写入、自动备份、SHA 校验、原子替换、审计记录和安全回滚。初次凭据或管理员安装可由用户完成一次操作；后续普通版本无需逐次批准。

Development isolation remains effective. Do not alter security policies, network restriction variables, access controls, or execution environments to bypass guards and gain production permissions. If no authorized channel exists, finish safe independent work, report the blocker, and prepare one-time connection. The executor runs in an independently authorized environment with limited writes, automatic backup, SHA verification, atomic replacement, audit records, and safe rollback. Initial credential provisioning or administrator installation may require one user action; subsequent routine releases require no repeated approval.

## 优先级与真实验收 / Priorities and real acceptance

P1：发布已验证的 4A.8S 最小补丁，分支 `codex/phase4a8s-production-patch-preparation`，提交 `e1efb22023a37abae3d97bf78cb4ec80bc583bf4`。不得要求 WorkBuddy 重新开发补丁。P2：继续 4B.1G，分支 `codex/phase4b1g-official-site-email-conversion`，提交 `f84b61767746be84c05814862b132e4ebd26ea48`；真实组织身份、第一方邮箱、历史去重和生产隔离验收完成前不得部署。

P1: release the verified minimal 4A.8S patch from `codex/phase4a8s-production-patch-preparation`, commit `e1efb22023a37abae3d97bf78cb4ec80bc583bf4`; do not ask WorkBuddy to redevelop it. P2: continue 4B.1G from `codex/phase4b1g-official-site-email-conversion`, commit `f84b61767746be84c05814862b132e4ebd26ea48`; do not deploy before accepting real organization identity, first-party email, history deduplication, and production isolation.

部署后，通过原有 Inventory 正常计划运行检查真实 Provider 请求、新组织、新线索、官网第一方邮箱、SAFE 净增长、城市队列推进、异常和锁冲突，确认 SAFE≥50 仍实际采集。不得只凭 TESTS_PASSED 或 PATCH_APPLIED 宣称恢复。实际零产量照实记录；无法观察时记 UNKNOWN / NOT_MEASURED，不编造零值。对自身发布造成的故障，核实备份、当前指纹、窗口和锁后，通过同一正式通道安全回滚。

After deployment, inspect a normal scheduled run of the existing Inventory for actual provider requests, new organizations, new leads, first-party emails, net SAFE growth, city queue progress, exceptions, and lock conflicts; confirm actual collection at SAFE≥50. TESTS_PASSED or PATCH_APPLIED alone does not prove recovery. Report actual zero production truthfully; use UNKNOWN / NOT_MEASURED for unavailable observations. For faults introduced by the release, verify backups, current fingerprints, window, and locks before safe rollback through the same authorized channel.

## 交付规范 / Delivery contract

回复中文，报告中英双语；秘密不进入聊天、代码、Git 或报告。最终字段如下；区分开发、发布和生产验收，并区分发送冻结要求与运行状态核实结果。

Replies are Chinese; reports are bilingual Chinese and English. Keep secrets out of chat, code, Git, and reports. Use the following final fields, distinguishing development, deployment, production acceptance, and the sending-freeze requirement from verified runtime state.

```text
PHASE =
DEVELOPMENT_COMPLETED =
TESTS_PASSED =
PRODUCTION_DEPLOYED =
PRODUCTION_VALIDATION_PASSED =
ROLLBACK_AVAILABLE =
NEW_ORGANIZATIONS =
NEW_FIRST_PARTY_EMAILS =
SAFE_UNIQUE_ORGS =
SMTP_ENABLED = 0
EMAILS_SENT = 0
GIT_COMMIT =
PUSH_SUCCESS =
BLOCKERS =
NEXT_ACTION =
```

任务启动必读本规范，并按 PROJECT_SKILLS.md、GUARDRAILS.md 和 RUNBOOK.md 执行适用流程。接入要求见 [受控部署通道](CONTROLLED_DEPLOYMENT_CHANNEL.md)。

Read this charter at task startup and follow applicable workflows in PROJECT_SKILLS.md, GUARDRAILS.md, and RUNBOOK.md. See [Controlled deployment channel](CONTROLLED_DEPLOYMENT_CHANNEL.md) for connection requirements.
