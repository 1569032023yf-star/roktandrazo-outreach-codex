# U1最终组合实现缺口 / Final U1 integration implementation gaps

本次仅静态组合核验及5个Git blob哈希核对，未运行重型测试。主代理提供的38项与12项通过、候选全suite运行状态不作为本Reviewer独立执行结果。 / Static integration inspection and five Git blob hash checks only. Parent-reported test results and ongoing full-suite execution are not independent executions by this reviewer.

## 清单核验 / Manifest verification

SOURCE_CANDIDATE_MANIFEST.json固定41a5516370766464fa5a2a501203f5b406bfcf92。五个条目Git字节SHA256全部匹配，且当前HEAD对应文件字节相同。故后续runner/tests变化未使此五文件源码清单漂移。该清单明确是source inventory且production_target=UNAPPROVED，不是可安装发布包。 / All five manifest Git-byte SHA256 hashes match revision41a5516 and current HEAD. Later runner/test changes did not drift those source files. This is explicitly a source inventory with unapproved targets, not an installable release package.

## 应优先实现的缺口 / Implementation priorities

1. **P0：正式执行组合adapter尚未实现。** host_admission无条件增加FORMAL_EXECUTION_ADAPTER_NOT_INSTALLED并禁止dispatch；main固定exit78。非测试代码搜索只有DurableSlots/GrowthLedger定义，无实际执行消费者。缺少正式一次调度入口把批准schedule/host证据、唯一生产锁、authority epoch、预算reserve、slot claim/start、既有Inventory执行、终态或UNKNOWN回执及费用settle组合。下一实现建议：先构建依赖注入的有界single-slot执行adapter，使用禁止生产调用的fake executor验证崩溃边界；不要修改默认禁用或注册任务。 / No formal execution adapter exists: admission always denies and main exits78. Implement an injected bounded single-slot orchestrator linking approved evidence, sole lock, epoch, budget, claim/start, the existing Inventory executor and reconciliation/settlement. Develop it against an inert fake executor without enabling production.

2. **P0：生产证据生产端及锁身份绑定仍缺。** 当前consumer验证调用者提供的签名事实，未实现批准的Windows身份/非交互出口/进程排空/唯一调度权威观测collector及信任根加载。_ACTIVE_LEASE存在只证明某个本地锁上下文，未把批准锁路径/身份与签名授权绑定。需要正式只读证据adapter合同，缺信息时明确UNKNOWN；不得以签名事实替代真实观测。 / Consumers verify supplied assertions; approved Windows/egress/drain/authority collectors and trust provisioning are absent. Presence of an active lease does not identify the approved sole production lock. Bind the authorized lock identity and fail closed on missing observations.

3. **P1：新账本引入与回滚兼容未落地。** growth schema v2拒绝旧schema是良好失败关闭，但不是迁移器。需只读导入计划、隔离副本迁移/验证、持久claim与UNKNOWN及预算保留、旧执行器不读新账本时禁止恢复派发的rollback gate。全历史组织/资格/站点/邮箱证据转换尚无正式adapter，不能用空历史或SAFE总数替代。 / Schema rejection is not migration. Implement evidence-backed history import, isolated-copy validation and rollback compatibility that preserves claims, unknowns and budgets; an old executor ignoring the ledger must remain disabled.

4. **P1：发布依赖闭包和新增文件协议未完成。** 五文件依赖autonomy.unattended_policy、bridge_acceptance、lock_recovery及包/runtime环境，但source manifest不声明这些既存依赖的生产版本/哈希兼容。需要production target路径、依赖批准指纹、发布器新增文件备份/移除及失败回滚合同。默认禁用XML含三处占位值、空trigger且动作只跑拒绝入口，适合作为模板，不能声称已经有可运行生产任务。 / The source inventory lacks approved production fingerprints for imported policy/bridge/lock modules and runtime dependencies. Add dependency closure, target paths and publisher new-file/rollback support. Disabled XML has placeholders, empty triggers and a deny-only action; it is a safe template, not a runnable production host.

5. **P1：跨登录/无人登录证据聚合仍不足。** bridge_acceptance只把同会话两调用置VERIFIED，CROSS_LOGON_VERIFIED与NO_LOGIN_BOOT_VERIFIED保持NOT_VERIFIED。需明确多会话/boot证据组合同一服务身份、持久存活、自然登录/重启链条的判定器及正式采集来源。维护窗口/管理员操作依用户授权后执行；判定器可先离线实现。 / Bridge acceptance only promotes same-session calls; cross-logon and no-login remain unverified. Implement multi-session/boot evidence aggregation and source contracts before authorized operational testing.

## 下一任务建议 / Recommended next task

先实现第1项纯离线single-slot adapter和第2项严格锁/证据输入合同；其明确依赖可同时驱动第3/4项发布兼容清单。禁止提前接上真实Inventory或打开host_admission。完整回归继续由主代理串行完成，不能靠再加若干测试替代上述缺失执行代码。 / Prioritize the inert single-slot adapter and strict lock/evidence input contract; use its explicit dependencies to drive migration and packaging. Keep real Inventory disconnected and admission disabled. Parent-managed full regression proceeds independently; additional tests do not substitute for missing execution integration.

结论 / Conclusion: **SOURCE_MANIFEST_BYTES_MATCH=true; END_TO_END_EXECUTION_IMPLEMENTED=false; RELEASE_READY=false**。未修改实现、未提交、未触碰生产。 / No implementation edits, commit or production actions.
