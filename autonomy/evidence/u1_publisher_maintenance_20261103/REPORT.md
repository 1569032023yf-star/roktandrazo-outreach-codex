# U1 原发布器维护接线进展 / Original publisher maintenance integration progress

时间 / Time: 2026-11-03T10:05:29.868174+08:00
固定当前源码 / Current fixed source: `1006e2ff91757e5be6e31b2d9940c500703a82d3`
独审产品源码 / Independently reviewed product: `a90b28fdfb7da4caca97fab33b2d414aee8e1919`

本轮实际完成原 Publisher Executor 的维护标记准入和安装维护会话核心，目标仍在执行，尚未完成完整可安装版本。
This run implements original-publisher maintenance admission and the install-session core. The goal remains active; the complete installable release is unfinished.

## 实际工程 / Implemented engineering

- 在现场原发布器的离线副本中，仅向原 inventory_acquire 的 BEGIN IMMEDIATE 事务增加同库维护标记检查；单/多文件 apply 与 rollback 均经过该函数。过期日期、stale 参数、NULL 或异常标记不能绕过。现场 executor 哈希仍为 `a3c271424131b4d42d8b0ed3f46e8355e3ff9d0556406e2199a5da093043105b`，与已消费证据一致；未修改现场文件、seal、认证或白名单。
  The offline copy adds the shared-marker check inside original atomic admission. All four mutating paths use it; stale/date/malformed states do not bypass exclusion. The original publisher bytes remain unchanged; no site seal, authentication or allowlist changed.
- 维护权、永久操作墓碑和完整 HELD 上下文原子写入；绑定唯一 Inventory、source、manifest、nonce、目标事务和实际动作。安装各阶段持续核验；最终核验凭据和释放同事务提交，异常不自动释放。
  Exclusion, replay tombstone and complete HELD context commit atomically. Bindings include Inventory/source/manifest/nonce/target/action; phase checks persist through verification and atomic release, with no finally-release.
- 未知部分应用支持确认旧进程结束后的显式 recover 子会话，在同一维护权下补偿；补偿中断可继续新的显式恢复请求。父子交接后迟到的旧回执、状态写入和最终核验不能重新激活或释放父会话。
  Explicit recovery retains the same exclusion after the previous process stops; interrupted compensation can recover again. Transactional handoff/state checks reject late parent transitions and verifier replies.
- PowerShell 内部协调器增加绑定维护权核验；公开 Execute hard gate 原样保留。没有增加外部解锁开关，没有把回调当作正式安装授权。
  The internal coordinator checks bound authority. Public Execute remains hard rejected, with no external unlock switch or callback-based installation grant.

## 测试与独审 / Tests and review

当前 `1006e2ff91757e5be6e31b2d9940c500703a82d3` 实际组合 **173 PASS / 174.415s**，失败、错误、跳过均为0，详见 final/TARGETED.json 及逐项输出。宿主与数据库权威分进程运行，保持开发护栏完整。
The current source actually passed 173 combined tests with zero failures/errors/skips. Host and authority groups run in separate processes without removing development guards.

首次混合进程尝试导入 bd_db 后，原开发护栏按设计阻止 PowerShell/HTTP 等测试操作；该失败记录保留为根目录 TARGETED.json/OUTPUT，不能算验收通过。修复仅隔离测试编排，没有放宽 guard、环境或产品门禁。
The initial mixed-process attempt activated bd_db's existing process guard and was blocked. Raw failed output is retained and not counted as acceptance. Only test process grouping changed; guards/environment/product gates were not weakened.

独审 **29 PASS**，`OFFLINE_SCOPED_REVIEW_PASSED`，5类发现全部修复：动作绑定、取得权与上下文原子性、部分应用恢复、交接迟到竞态、child HELD退出cut。独审固定 a90b28f；后续1006e2f仅改变测试编排，产品与被审测试字节相同，不能把它描述为完整调用链审核通过。
Independent review passed 29 tests and closed five finding classes. It reviewed product a90b28f; 1006e2f changes only test orchestration, with identical reviewed product/test bytes. This is a scoped source review, not complete-chain approval.

真实进程退出覆盖 acquire事务中exit42、写部分文件后exit41、handoff提交且child intent前exit43；另覆盖释放commit失败/成功但回执丢失、重复调用、跨日期、双方争用、错误动作、旧线程回执和补偿再次中断。
Actual process exits cover acquire transaction death, partial-file death and the handoff-before-child-intent cut; tests also cover release failures/lost replies, duplicates, dates, contention, action mismatch, stale replies and interrupted compensation.

本轮未重跑833项全量，也未制作新安装包：完整适配尚未完成，不能移植旧候选的成绩或包哈希。已有833项37failures/17errors的历史结果保留原pin，不宣称全绿。
No new 833-test regression or installation package is claimed for this in-progress source. Historical 37 failures/17 errors retain their original pins and are not all green.

## 剩余顺序与验收门禁 / Remaining sequence and gates

1. Codex继续原认证Publisher入口到受控安装进程的正式适配，包括固定身份/命令/包、进程约束、真实旧进程终止复验，以及独立目标文件、日志、SCM、ACL最终核验器。当前注入callback测试不是这些工程的替代物。
   Complete the supported authenticated publisher adapter, exact process/package identity/containment, prior-process termination checks and independent file/journal/SCM/ACL final verifier. Callback fixtures do not substitute for this integration.
2. 补齐后对完整调用链独审，修复问题，再冻结真正可安装版本，重建AMD64包/逐文件manifest并运行首装、升级、退出恢复、回滚及可比全量回归。
   Review and fix the complete chain, then freeze the installable source, rebuild AMD64 artifacts/manifests and rerun lifecycle and comparable regression tests.
3. 完整审核及授权后才进入WorkBuddy Windows真实无人值守验收；不索要已提交P1资料。生产部署和业务采集验收仍在最后，不能提前执行。
   Actual Windows unattended acceptance follows complete review/authorization without requesting accepted P1 evidence again. Production deployment and business acceptance remain last.

## 状态、未执行与敏感信息 / State, non-execution and sensitive information

`DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false`

`allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336`

未修改生产DB、账本、ACL、服务、注册表、代理、系统任务或现场发布器；未启动Inventory、服务或SMTP；未创建第二调度器；未提取凭据。源码/报告不含真实凭据或客户数据。回滚仅限开发Git提交，不删除持久维护或安装证据。
No production DB/ledger/ACL/service/registry/proxy/task/publisher writes, Inventory/service/SMTP starts, second scheduler or credential extraction occurred. Source/reports contain no real credentials or customer data. Development rollback is Git-only and must preserve durable maintenance/install evidence.
