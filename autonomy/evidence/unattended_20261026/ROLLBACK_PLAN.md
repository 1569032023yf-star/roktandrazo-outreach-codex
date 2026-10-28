# 保留账本的双向回滚计划 / Ledger-preserving bidirectional rollback plan

PLAN_ONLY=true; INSTALL_ALLOWED=false; PRODUCTION_EXECUTED=false.

中文：当前缺正式新增文件发布和旧执行器兼容合同，因此这是可审核准备方案，不能当作已验证生产回滚。没有生产目标SHA时不生成或执行替换/删除命令；所有动作只能由正式发布入口在获准窗口、唯一Inventory互斥下执行。

English: New-file publishing and old-executor compatibility contracts remain absent. This is a reviewable preparation plan, not verified production rollback. No replacement/removal command is generated or executed without approved target hashes. All actions require the formal publisher, authorized window and exclusion with the sole Inventory.

1. 中文：切换前停止原权威的新派发，等待既有进程树排空；读取当前slot、UNKNOWN、未结算预算和历史账本，正式对账后冻结精确快照指纹。任何未知或锁冲突保持关闭。 / English: Stop old dispatch, drain the process tree, inspect slots/unknowns/unsettled budgets/history, reconcile formally and pin exact snapshot fingerprints. Unknown state or lock conflict keeps dispatch disabled.
2. 中文：正式发布器在同一互斥内核对原文件SHA；既有文件备份并核对备份SHA，新增文件记ABSENT，不把开发HEAD整树覆盖生产。受控原子替换与安装失败的恢复必须支持多文件一致性。 / English: Under the same exclusion, verify original hashes, hash-check backups, record ABSENT for new files and require controlled atomic installation/failure recovery. Never overwrite production with a checkout.
3. 中文：新身份、出口、runtime、trusted collector和backend合同通过后才允许申请切换；authority epoch单调递增，原逻辑Inventory身份不变。不以lease超时恢复UNKNOWN。 / English: Identity, egress, runtime, trusted collectors and backend contracts must pass before requesting cutover. Advance authority epoch monotonically while preserving Inventory identity. Lease expiry never clears UNKNOWN.
4. 中文：回滚先停止新派发并排空。保留已提交claim、UNKNOWN、预算预留、首次资格、基线和审计；不得恢复旧DB快照抹除外部副作用。通过rollback_admission检查当前schema/epoch、排空与零未决，以及旧执行器理解当前账本。只允许审核计划，非自动执行。 / English: Stop/drain the new host first. Preserve claims, unknowns, budget reservations, first qualification, baselines and audit; never restore stale databases over external effects. Check current schema/epoch, drained zero-unresolved state and old-executor compatibility through rollback_admission. This admits a plan only.
5. 中文：正式发布器按after SHA核对待回滚文件，再恢复已核验旧字节；只移除本次新增且after SHA一致的文件。未知文件、版本漂移或不支持新增文件移除时停止，不能自行复制。记录operation_id并先查status再重试。 / English: Verify installed hashes before restoring backups; remove only release-created files matching installed hashes. Unknown files, drift or unsupported removal stop rollback. Record operation_id and reconcile status before retrying.
6. 中文：重新核对当前账本、唯一锁、SMTP关闭、旧权威兼容后，以新epoch恢复旧权威；旧执行器不能读ledger时保持关闭。通过原Inventory自然运行及OS启动/登录审计验收，不手动补采集。 / English: Recheck preserved ledgers, sole lock, disabled SMTP and old compatibility before resuming old authority with a new epoch. An executor ignoring the ledger stays disabled. Accept through natural Inventory cycles and OS boot/logon audit, without manual collection.

中文：本轮仅隔离源码与测试，可用Git固定字节恢复开发候选；生产备份、实时互斥、授权窗口、发布器与回滚执行均未验证/未执行。数量：生产写0、发信0、新Inventory0。下一步消费既有Issue2合同。报告自检中英双语、无客户资料与秘密、状态真实。

English: This iteration changes isolated source/tests only; pinned Git bytes recover development candidates. Production backups, live exclusion, window, publisher and rollback execution remain unverified/unperformed. Production writes, mail and new Inventories: zero. Next consume the existing Issue2 contract. Bilingual self-check passed without customer data/secrets or overstated status.
