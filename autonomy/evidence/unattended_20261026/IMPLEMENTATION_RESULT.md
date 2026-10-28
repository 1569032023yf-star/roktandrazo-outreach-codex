# Phase U1 工程实现结果 / Engineering implementation result

日期 / Date: 2026-10-28 Asia/Taipei.
本次起点 / Refresh baseline: `1c8a7fdbae8866f6eadd8de9fd935b873a5b5033`.
最终源码 / Final source: `3f03417ba46f565525b2b254fdbc559667ab96a9`.

## 实际代码与验证 / Implementation and validation

本轮继承远端已存在的持久slot、签名证据、预算与首次资格账本、历史导入、快照检查、离线单槽适配器、桥接跨会话分类及回滚准入，没有重新创建生产调度。先核对远端HEAD和本地清洁状态，再读取指定护栏与历史报告。

Existing durable slots, authenticated evidence, budget/first-qualification accounting, history import, snapshot inspection, inert single-slot composition, bridge-session classification and rollback admission were retained. Remote HEAD and the clean checkout were verified before editing. No production scheduler was created.

独立审核复现底层预算结算缺陷：仅匹配request_id时，另一run的签名零费用回执可能释放原预留。`GrowthLedger.settle`现在对known和unknown回执都要求匹配持久run；已绑定claim还逐项核对固定Inventory、slot、epoch、owner、run/request及claim_token_hash。claim确认缺失继续占额，不退款、不重放。新增回归实际重开SQLite，证明错误回执后第二次预留仍被额度拒绝，正确回执可幂等结算。

Independent review reproduced a settlement defect: matching request IDs alone allowed a signed zero-cost receipt for a different run to release reserved funds. Settlement now binds both known and unknown receipts to the persisted run and, for claim-bound requests, all persisted operation fields and claim-token digest. Missing claim acknowledgement retains funds. Reopen tests verify that rejected receipts cannot free capacity and correct receipts settle idempotently.

新增`inspect_release_contract(consumer,envelope,now,expected)`消费正式兼容合同候选：核对独立批准上下文、源码/包/运行时/发布器指纹、目标文件原hash或ABSENT、唯一backend/锁、schema及16项能力。缺失、不支持、过期、篡改或不匹配一律拒绝；拒绝Windows设备路径、大小写和文件祖先冲突。签名只证明来源，不证明真实OS事实；即使合同通过，allow_install与allow_dispatch始终false，仍须正式发布器现场核对窗口、锁和备份。

The new compatibility consumer validates an independently approved context, immutable source/package/runtime/publisher fingerprints, previous file hashes or ABSENT, sole backend/lock, schema and 16 capabilities. Missing, unsupported, stale, tampered or mismatched contracts fail closed. Windows device names, case collisions and file/ancestor conflicts are rejected. Provenance does not prove OS truth. Successful inspection always leaves installation and dispatch disabled; live window, exclusion and backup gates belong to the authorized publisher.

最终113项定向测试通过，0失败0错误，9.153秒；机器结果及逐项ID见U1_REFRESH_VALIDATION.json。其中包括多进程claim、提交前后退出、外部回执丢失、预算并发/跨日/重启、429、身份合并、规则不可比、历史导入、包隔离导入和本轮回执绑定修复。模拟磁盘写错误不等于实物磁盘耗尽验收；开发Windows运行时不等于生产身份/runtime验收。

All 113 targeted tests passed with zero failures/errors in 9.153 seconds; exact IDs are recorded in U1_REFRESH_VALIDATION.json. Coverage includes process contention, exit around commits, lost receipts, concurrent/cross-day/reopened budgets, 429, identity merges, incomparable rules, history import, isolated package import and the settlement repair. Injected storage errors do not prove physical disk-exhaustion recovery. Development runtime results do not establish production identity/runtime acceptance.

业务日保留既有outreach_batch_date的上海01:00边界，与现行编排一致，不擅自更改生产日期语义；首测冻结及partial_day仍按该既有边界判定。增长账本在完整可信历史和规则可比时可独立区分新组织、首次合格新组织和既有组织新合格；缺少正式完整历史时真实数值UNKNOWN。

The existing Shanghai 01:00 outreach batch boundary is preserved, matching the orchestrator rather than silently changing production semantics. Baseline freezing and partial_day use that existing boundary. With authenticated complete history and comparable rules, the ledger separates new organizations, newly qualified new organizations and existing-candidate conversions. Actual growth remains UNKNOWN without formal complete history.

## 未执行、风险与下一步 / Exclusions, risks and next steps

Issue #2已实查，最新仍6435605069，未重复6402130583消费回执或兼容合同请求。8791未进行新现场验收，跨调用/跨登录/无人登录均不能升级；7877非交互出口未证明。Provider候选8d63d2d/包30fccc9保持原审核范围，仍缺scraper批准生产字节/封签及精确Service兼容。没有手动采集、实际任务安装、用户/ACL变更、生产DB写入、SMTP或商业发信。

Issue #2 still ends at 6435605069; neither the consumption acknowledgement nor contract request was duplicated. No fresh live 8791 acceptance occurred; cross-call/logon/login-free status cannot be promoted. Noninteractive egress remains unproven. Provider source 8d63d2d/package 30fccc9 retain their existing scope but lack approved scraper bytes/seal scope and exact Service compatibility. No manual collection, task installation, user/ACL change, production database writes, SMTP or business mail occurred.

下一步是通过既有交接消费正式backend、硬时限/取消/回执、唯一锁、runtime及发布器新增文件/保留账本回滚合同，并用本轮消费者核对；不能以调用方布尔值或开发hash替代真实批准。完成可审核可回滚生产包后，才提出专用低权限身份、ACL、禁用任务及维护窗口的最小一次性管理员申请。

Next consume the requested formal backend, deadline/cancellation/receipt, sole-lock, runtime and new-file/ledger-preserving publisher contracts through the existing handoff and validate them using this consumer. Caller booleans and development hashes cannot replace approval. Only after a reviewable rollback-capable production package exists should minimal identity/ACL/disabled-task/window authorization be requested.

报告自检：中英双语、实际结果与限制、未执行、风险、数量及下一步明确；无凭据、客户原文或完整商务邮箱。整体DEVELOPMENT_COMPLETE和RELEASE_READY仍false，不以局部通过冒充端到端完成。

Report self-check: bilingual, explicit performed/unperformed work, risks, counts, limitations and next steps, without credentials or customer content. Overall development completion and release readiness remain false; scoped passes do not establish end-to-end completion.


完整回归核对：基线1c8a7fd与候选各833项、37失败17错误，失败/错误ID集合完全一致，NO_NEW_REGRESSION=true；不是全量全绿。最终源码相对运行启动版本仅新增合同路径拒绝变更，已单独覆盖113项最终专项。 / Full regression: baseline and candidate each833 tests,37 failures and17 errors with identical ID sets, NO_NEW_REGRESSION=true, not all green. Changes after runner startup only harden contract paths, covered by the final113 targeted tests.
