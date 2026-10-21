# 4A.8U 城市恢复闭环 / City recovery closure

结果 / Result: **DEPLOYED_AWAITING_NATURAL_PRODUCTION_ACCEPTANCE**

开发、回归、独立审核、可登记发布包、正式登记及部署均完成。尚未完成自然生产验收或证明真实业务增长。
Development, regression, independent review, registerable release bundle, official registration and deployment are complete. Natural production acceptance and actual business growth remain unproven.

## 发布与证据 / Release and evidence

- Release: `phase4a8u-city-recovery-production-rebase-20261022`
- Operation: `op-20261022-011811-4925c1`; applied `2026-10-22T01:18:11+08:00`.
- Patch SHA256: `a050aa91ed1b73c39e30b9ae4692d626964d62eb0dfbcd7a6632b6b5d67113cb`.
- 正式非测试通道登记成功，预检14/14，安全窗口约265分钟；正式Inventory锁持有及释放均有回执。仅修改两个文件，现场after SHA匹配候选；其余受监测代码SHA未改变。
  Official non-test registration succeeded, preflight 14/14, safety window approximately 265 minutes; official Inventory lock acquisition/release recorded. Only two files changed; live after hashes match the candidate and other monitored code hashes are unchanged.
- 正式逐文件备份已重新只读计算SHA，均匹配before；逐字节正反向校验通过。真实生产rollback未执行，不能称作生产回滚演练完成。
  Official per-file backups were independently rehashed read-only and match before hashes. Exact forward/reverse validation passed. Actual production rollback was not executed and is not claimed as a completed production drill.

SHA及回执索引 / Hashes and receipt index: `autonomy/evidence/city_4a8u_20261022/index.json`; 完整机器字段 / full machine fields: `CITY_4A8U_RELEASE_CLOSURE.json`.

## 修复及验证 / Repairs and validation

生产快照与开发源码逐函数核对后重建补丁，保留生产既有语义。独立Reviewer首审三项阻断均修复：1800秒持久化冷却及失败历史、重复Provider命中保护恢复字段、防止程序异常消耗网络预算。达到三次有效网络失败后转手工复核，不升级SAFE。保留事务及身份、历史、邮箱和发送门禁。
The patch was rebuilt function by function against pinned production snapshots, preserving existing production semantics. All three independent-review blockers were repaired: persistent 1800-second cooldown/failure history, recovery metadata preservation on repeated Provider hits, and exclusion of programming errors from the network budget. Three valid network failures lead to manual review, never SAFE. Transaction, identity, history, email and sending gates remain intact.

静态扫描仅按精确路径及文件SHA豁免独立非生产采集器；改字节或其他runtime直接INSERT仍报错。最终固定候选主回归84/84；失败路径20/20含18项重复恢复测试及2项新事务测试，合计104次调用、86项唯一测试。恢复18项，独立Reviewer子集22/22。基线80项中79通过、1项相同静态误报；新回归0。旧95计数包含重复导入fixture，不作为最终计数。
Static scanning exempts the isolated non-production collector only by exact path and file hash; changed bytes or other runtime direct INSERTs remain detected. Final pinned candidate primary regression: 84/84. Failure paths: 20/20, including 18 repeated recovery tests and two new transaction tests; 104 invocations, 86 unique tests. Recovery suite: 18; independent reviewer subset: 22/22. Baseline: 79/80 passed with one static false positive; new regressions: zero. Earlier 95-count runs included duplicate imported fixtures and are not the final count.

失败测试覆盖提交约束失败回滚、连接关闭放弃未提交事务；未做真实生产强杀进程或故障注入。
Failure tests cover commit-constraint rollback and connection-close abandonment of uncommitted transactions; no real production process kill or fault injection occurred.

## 业务状态与续接 / Business state and continuation

01:18:27 +08遥测：Cooperstown仍active，未见Lake Placid active；近24小时Provider请求0。leads总数1213、带邮箱652仅为存量，不等于已验证组织或本轮新增。无persisted SAFE快照，CURRENT_SAFE、新组织、新第一方邮箱及SAFE净增长均UNKNOWN。历史Inventory actual56不得计作本轮增长。
Telemetry at 01:18:27 +08: Cooperstown remains active; Lake Placid is not observed active; Provider requests over 24h: zero. Existing 1,213 leads and 652 leads with email do not establish verified organizations or new growth. With no persisted SAFE snapshot, current SAFE, new organizations, new first-party emails and SAFE net growth are UNKNOWN. Historical Inventory actual 56 is not this release's growth.

唯一原Inventory `1784775229336`下次预期 `2026-10-22T05:43:24+08:00`。已更新既有 `rokt-razo` 两小时心跳接续验收，未新增调度器或手动启动采集。后续读取真实post-deploy自然run_id、Cooperstown闭合原因、Lake Placid及城市级Provider证据；缺证继续UNKNOWN，按operation_id对账，禁止重复apply。
The sole original Inventory `1784775229336` is next expected at `2026-10-22T05:43:24+08:00`. The existing two-hour `rokt-razo` heartbeat was updated for continued acceptance; no scheduler or manual acquisition was added. It must inspect the actual post-deploy natural run ID, Cooperstown completion reason, Lake Placid and city-level Provider evidence; missing evidence remains UNKNOWN. Reconcile by operation ID and do not reapply.

SMTP=0、发送三任务暂停/已删除，部署前后total_sent保持517、sent_today=0；观测窗口未授权发送0，active Inventory数1。品牌、双来源实采及V6 QA保持原安全状态。无人值守持续性与业务验收未完成，AUTONOMOUS_OPERATIONS_ACTIVE=false。
SMTP=0; all three sending tasks are paused/deleted; total_sent stays 517 and sent_today=0 across deployment. Unauthorized sends in the observation window: zero; active Inventory count: one. Brand, dual-source acquisition and V6 QA remain in their existing safe state. Sustained unattended operation and business acceptance remain incomplete; AUTONOMOUS_OPERATIONS_ACTIVE=false.

当前无须额外授权运维方处理的阻塞；剩余依赖原计划时点及真实执行结果。未直接读写生产数据库、未扩展权限或任意命令接口。原有未提交启动器/锁修复文件未纳入本次提交。
No current blocker requires additional operator authority; remaining dependencies are the original scheduled time and actual execution. No direct production database access, privilege expansion or arbitrary-command interface was used. Existing uncommitted launcher/lock-repair files are excluded from this change.

自查 / Self-check: 中英双语、证据范围、未执行事项及下一步已列；未包含秘密。工程及发布包已推送 `4db2f5b`（实现 `475be19c0d149a8c0e5ffc2b3b3866908c185eaa`）；本报告及部署回执另作证据提交，可按本文件git history查得。
Bilingual content, evidence scope, unexecuted work and next actions are listed; no secrets included. Engineering/release bundle pushed at `4db2f5b` (implementation `475be19c0d149a8c0e5ffc2b3b3866908c185eaa`); this report and deployment receipts form a separate evidence commit discoverable through this file's Git history.


## 心跳观察 / Heartbeat observation — 2026-10-22 01:23 +08:00

正式通道复核部署状态及两文件SHA一致；原Inventory尚未到05:43:24自然运行时间。SMTP=0、今日发送0、唯一Inventory=1；当前SAFE及增长UNKNOWN。

Official channel confirms applied status and both file hashes. Original Inventory is not due until 05:43:24 +08:00. SMTP=0, sends today=0, one active Inventory; current SAFE and growth UNKNOWN.

Cycle: 326516b6-651e-40c4-b406-6df8e9e5b1e2; evidence: `autonomy/runtime/city_observation_20261021T172106`.


## 心跳观察 / Heartbeat observation — 2026-10-22 03:24 +08:00

03:24正式通道复核：APPLIED及两文件SHA一致，尚未到05:43:24原Inventory自然运行时间；Cooperstown仍active，未观察到部署后Inventory。SMTP=0、今日发送0、累计517未变、唯一Inventory=1、锁released。SAFE及增长UNKNOWN。连续两轮均为到期前观察，不构成自然生产或无人值守发布验收；继续既有心跳，不触发替代采集。

03:24 official-channel observation: APPLIED and both hashes match; original Inventory is not due until 05:43:24 +08:00. Cooperstown remains active; no post-deploy Inventory observed. SMTP=0, sends today=0, cumulative sends unchanged at 517, one active Inventory, lock released. SAFE and growth UNKNOWN. Both observations precede the due time and do not establish business or unattended release acceptance; continue existing heartbeats without substitute collection.

Cycle: 0dae5a0f-a555-49d6-b855-6a79b64087d2; evidence: `autonomy/runtime/city_observation_20261021T192338`.


## 心跳观察 / Heartbeat observation — 2026-10-22 05:24 +08:00

05:24正式只读复核：APPLIED及两文件SHA一致；05:43:24原Inventory尚未到期，未见部署后自然run。Cooperstown仍active；SMTP=0、今日发送0、累计517、唯一Inventory=1、锁released。SAFE及增长UNKNOWN。继续既有心跳等待自然运行证据；到期前观察不构成业务验收或无人值守发布验收。

05:24 official read-only check: APPLIED and both file hashes match. Original Inventory is not due until 05:43:24 +08:00; no post-deploy natural run observed. Cooperstown remains active; SMTP=0, sends today=0, total=517, one active Inventory, lock released. SAFE and growth UNKNOWN. Continue existing heartbeat for natural-run evidence; pre-window observations do not establish business or unattended release acceptance.

Cycle: c9b67309-8f9d-4193-a800-d99fbbe404a6; evidence: `autonomy/runtime/city_observation_20261021T212409`.


## 自然运行观察 / Natural-run observation — 2026-10-22 07:24 +08:00

07:24已观察到部署后Inventory inventory:2026-10-22:03b70e7a，completed/target_met，actual=56不计当前SAFE或新增。Cooperstown仍active，Lake Placid未激活，Provider过去24小时0；城市业务验收未通过。部署SHA一致，SMTP=0、今日发送0、累计517、唯一Inventory=1、锁released。正式遥测不含本次运行日志或城市级Provider明细，根因UNKNOWN；本地orchestrator与生产SHA不同，不能以本地逻辑推断生产提前退出。下一原Inventory预期11:58:01，继续既有心跳补证，不重部署或手动采集。

07:24 observed post-deploy Inventory inventory:2026-10-22:03b70e7a, completed/target_met; actual=56 is not current SAFE or growth. Cooperstown remains active, Lake Placid is not active, and Provider requests over 24h are zero; city business acceptance is not met. Deployed hashes match; SMTP=0, sends today=0, total=517, one active Inventory, lock released. Official telemetry lacks run logs and city-level Provider details; root cause UNKNOWN. Local orchestrator differs from production SHA and cannot establish production early-exit behavior. Next original Inventory is expected at 11:58:01 +08:00; continue existing heartbeat, no reapply or manual collection.

Cycle: ecc230f4-a4fc-4cc5-8737-1481a3643ba9; evidence: `autonomy/runtime/city_observation_20261021T232411`.
