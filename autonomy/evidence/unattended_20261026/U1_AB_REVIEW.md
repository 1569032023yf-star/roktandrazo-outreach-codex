# U1 A/B 与签名适配独立审核 / Independent U1 A/B and signature-adapter review

日期 / Date: 2026-10-26 Asia/Taipei

Reviewer: /root/u1_review，未参与实现 / did not implement the reviewed modules.

固定版本 / Pinned revision: `66680a2f0f863431c200252483e6548d64c63ca9`，包括 A/B 初版 `a2181c814daea531f948d8a296bedc97938dac23`。审核期间这些目标文件对固定提交无差异 / reviewed files matched the pinned revision.

结论 / Verdict: **PASS_FOR_OFFLINE_AB_PROTOCOL_AND_SIGNED_ADAPTER_ONLY**。

整体 U1 审核 / Overall U1 review: **PENDING**。生产发布 / Production release: **NOT_APPROVED**。

## 范围与实际测试 / Scope and actual tests

审核 durable_slots.py、host_preparation.py、ledger_evidence.py、禁用 XML 及相关测试。初轮独立34项通过；新增签名适配固定后独立35项通过，2.300秒。命令：`python -B -m unittest test_durable_slots test_host_preparation test_unattended_policy test_bridge_acceptance test_unattended_ledger_model test_ledger_evidence -q`。未跑全量回归；未审核正在开发的增长/预算模块。

Reviewed durable_slots.py, host_preparation.py, ledger_evidence.py, disabled XML and related tests. The initial independent run passed34 tests; the pinned signed adapter increased the passing run to35 tests in2.300seconds. No full regression suite ran, and the concurrently developed growth/budget modules were excluded.

## 关键结论 / Key findings

持久账本使用BEGIN IMMEDIATE与唯一slot/due约束。claim同时检查当前epoch、pending和全局claimed/running/unknown排他；unknown没有lease超时重放路径。完成与失败均不可再次claim。恢复旧owner名称仍增加epoch，已发生的运行未排空不得切换。回执从可信验证器返回的payload读取，外层字段不用于状态授权；布尔/整数严格类型绑定。process-exit测试覆盖提交前后、外部合成副作用后的回执丢失及重新打开；二进程争抢只有一个成功claim。没有实际Provider调用。

The durable ledger uses BEGIN IMMEDIATE and unique slot/due constraints. Claim checks current epoch, pending state and global claimed/running/unknown exclusion. Unknown outcomes have no lease-expiry replay path. Completed and failed slots cannot be reclaimed. Restoring an old owner name advances epoch and cannot bypass undrained runs. Receipt authority comes from verified payloads, not outer fields, with strict type binding. Process-exit tests cover pre/post commit, lost receipts after a synthetic side effect and reopen; two competing processes produce one successful claim. No actual Provider was called.

初审发现A/B字段合同尚未连接；66680a2新增签名适配已解决此范围问题：签名校验之后才把inventory_id/observed_at_epoch/expires_at_epoch映射，拒绝输入中重复别名，强制显式expiry。集成测试真正签名→验证→authority→admit→claim，篡改签名payload和重复claim均被拒绝。没有从未签名外层补写授权字段。

The initial review found the A/B field contracts unconnected. Revision66680a2 resolves that scoped gap: mapping inventory_id/observed_at_epoch/expires_at_epoch occurs only after signature verification; duplicate aliases are rejected and explicit expiry is required. The integration test exercises signed evidence through authority, admission and claim, rejecting tampering and duplicate claims. No unsigned outer field is used to supplement authorization.

HMAC密钥来自预置信任源，不接受信封自带密钥；主体、来源、Inventory、schema、种类、时效及receipt格式均校验。HMAC仅证明可信采集者签发，不证明OS观测事实真实。CLI始终退出78且不派发；XML默认禁用、无触发器、禁止on-demand、LeastPrivilege、占位专用身份，不是可直接安装的生产配置。桥接四状态分别输出，两个端点不会升级跨登录或无人登录验收。

HMAC keys come from preconfigured trust sources rather than envelopes; identity, source, Inventory, schema, kind, lifetime and receipt format are checked. HMAC authenticates the collector, not the truth of OS observations. The CLI always exits78 without dispatch. XML is disabled, triggerless, disallows on-demand start, uses LeastPrivilege and placeholder dedicated identity; it is not an install-ready production task. Bridge statuses remain separate and endpoint observations never establish cross-logon or login-free acceptance.

## 必须保留的限制 / Required limitations

1. 账本不派发，也不自动持有原生产锁；调用方必须持续持有真实原运行锁并核验外部生产状态。现有测试验证的是本地协议，不能证明生产排他锁已经接入。
2. 可信OS采集器、信任根部署、专用身份/ACL、非交互7877替代或服务模式出口、正式执行adapter未部署。15项签名布尔值不是OS权限实测。
3. start成功不代表外部执行成功。崩溃后claimed/running必须对账，不得靠本报告授权重放。磁盘不足为注入OSError，非真实填满磁盘；进程退出不等于断电或硬件耐久验证。
4. 当前账本schema没有版本迁移及旧版本兼容迁移包；不能就此声明可回滚生产发布。claim与预算原子集成、增长账本、完整失败ID集合回归、受控发布器新增文件支持仍需最终审核。

1. The ledger neither dispatches nor automatically holds the production run lock. The caller must continuously hold that real lock and verify external state; local protocol tests do not establish production integration.
2. Trusted OS collection, trust-root provisioning, dedicated identity/ACLs, approved noninteractive egress and the formal execution adapter remain undeployed. Signed booleans are not OS permission measurements.
3. Successful start is not successful external execution. Claimed/running outcomes after crashes require reconciliation. Disk-full is an injected OSError, not a physically filled disk; process exit is not power-loss or hardware durability testing.
4. There is no versioned schema migration/old-version compatibility package yet. Atomic budget integration, growth ledger, full failure-ID-set regression and formal deployer new-file support require final review before production release or rollback readiness.

未执行生产操作、真实网络采集、SMTP、Windows安装/权限更改；只写本报告，不修改实现或提交。报告中英双语、数量及未验证项已自查，无客户资料或秘密。

No production operation, live collection, SMTP, Windows installation or permission change occurred. Only this report was written; implementation was not changed or committed. Bilingual scope/count/limitation checks passed with no customer data or secrets.
