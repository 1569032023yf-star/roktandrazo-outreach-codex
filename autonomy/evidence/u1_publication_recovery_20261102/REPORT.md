# U1 发布中断恢复接线 / Publication interruption recovery wiring

时间 / Time: 2026-11-02T09:01:44.396442+00:00
固定源码 / Fixed source: `82031ac3391889f29fc5df3ecc994ecc95fe0f78`
恢复基线 / Restored baseline: `58b50947ea96f876b19b97bd1c4516daac0c5e6b`

中文：实际文件发布器原先在提交指针失败或提交后进程退出时只留下备份，后续调用仍可能再次发布。本轮先持久保存 pending 意图，再执行备份与原子指针提交，最后将意图改名为 receipt。未完成意图会阻止 stage、activate、rollback、delete-inactive；新增 recovery-status 仅观察指针与源/目标关系，始终不授权重放。宿主入口和独立服务引导器同步拒绝载入存在未决发布的版本。原有成功首装、升级及回滚路径继续工作。
English: Previously, a failed pointer commit or process exit after commit retained backups but could permit another publication. The actual publisher now durably records a pending intent before backup and atomic pointer commit, then renames it to a receipt. Pending intents fence stage, activate, rollback and delete-inactive. The new recovery-status entry point observes source/target pointer relationships without authorizing replay. Both the host entry point and standalone service bootstrap refuse unresolved publications. Successful first publication, upgrade and rollback paths remain functional.

验证 / Validation:
- 固定候选89项组合测试通过，31.079秒；涵盖真实指针提交后子进程突然退出、提交前失败、残缺意图、四入口封锁和宿主拒绝启动。89 targeted/combined tests passed in31.079s, including real child death after pointer commit, precommit failure, torn intent, all four mutation fences and host refusal.
- 基线与候选分别实际执行833项，均37 failures/17 errors，失败与错误ID完全一致，NO_NEW_REGRESSION=true；并非全绿。Fresh baseline and candidate runs each executed833 tests with identical37 failure/17 error IDs; no new regression, not all green.
- 从固定源码重建真实AMD64候选，60文件逐份哈希和ZIP清单校验通过。包内真实模块完成stage/activate/回滚ABSENT；真实提交后子进程exit27，状态仍UNKNOWN，引导与回滚拒绝重放。Rebuilt an actual AMD64 candidate from pinned source;60 exact files and ZIP/manifest hashes verified. Packaged modules exercised stage/activate/rollback-to-ABSENT; a child exited27 after a real commit, leaving UNKNOWN with bootstrap and replay blocked.
- 包含上一轮安装所有权凭据保护修复。最初包演练脚本的引号错误已修正后重跑；不是产品源码失败。Includes the preceding ownership-receipt repair. An initial exercise-script quoting error was corrected before the successful run; it was not a product-source failure.

安装ZIP / Install ZIP SHA256: `9a08ac645484ce0f9186e5e812890b18a1ae140cd132bd98c76b1f17a55818d3`
回滚工具ZIP / Rollback tools ZIP SHA256: `db38adab6842a1ed1eba941324565f44accd0d172c02d99c6caf3b0de1c82cb4`
逐文件清单 / Manifest SHA256: `9d3ad9f5490d3467a57038642004555045e4af7f08def1b26c673fa2add02fe2`

仅隔离目录执行，未安装服务。回滚工具包依赖现场versions/backups/transactions，不是完整现场备份。Only isolated directories were exercised; no service installation. Rollback tools require retained site versions/backups/transactions and are not a complete site backup.

边界 / Boundaries: 新意图机制不追认历史无意图记录的事务，不提供自动清除UNKNOWN的写入口；TARGET_CURRENT也不证明收到成功回执。文件/父目录身份、ACL、维护租约与断电持久性仍需部署级验证。SCM升级、完整文件回滚及原Inventory到正式backend执行链仍未完成。独立审核不可用，保持PENDING，未自行冒充独审。
The new intent mechanism does not retroactively certify legacy transactions without intents and provides no automatic UNKNOWN-clearing writer; TARGET_CURRENT does not prove a success receipt. File/ancestor identity, ACLs, maintenance exclusion and power-loss durability still require deployment-level verification. SCM upgrades, full-file rollback and the original Inventory-to-formal-backend chain remain incomplete. Independent review is unavailable and remains PENDING, with no self-review substituted.

正式指令已回读Issue2 comment6567493676的A部分；沿用原任务rokt-razo与每3小时频率，45分钟/最多两重型线仍为指令预算，无平台硬超时字段。本轮实际08:50Z启动。WorkBuddy远端main仍13d061a82568bc147efa689742a61b3e06d95a31，复用P1 commit0b096948及既有回执6561646296，不重发消费回执或索要合同。8791跨登录/无人登录持久性、7877非交互出口仍未验收。生产DB/账本/SMTP操作、Inventory触发、服务/ACL/调度变更均未执行。
Issue2 comment6567493676 sectionA was read back. Existing automation rokt-razo retains the three-hour cadence;45-minute/two-heavy-line limits remain prompt budgets without a platform hard-timeout field. Actual cycle start08:50Z. WorkBuddy remote main remains13d061a82568bc147efa689742a61b3e06d95a31; reuse P1 commit0b096948 and receipt6561646296 without duplicate receipts or contract requests.8791 cross-login/unattended persistence and7877 noninteractive egress remain unaccepted. No production database/ledger/SMTP operations, Inventory triggering, service/ACL or scheduler changes.

下一唯一动作：实现禁用服务升级与精确自有文件回滚路径，接入持久恢复记录；生产派发保持关闭。
Next single action: Implement the disabled-service upgrade and exact owned-file rollback path with durable recovery records; keep dispatch closed.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false
