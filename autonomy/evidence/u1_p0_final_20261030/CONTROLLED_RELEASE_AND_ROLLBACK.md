# U1受控发布与回滚 / U1 controlled release and rollback

固定源码 / Pinned source: `d7d424c120281981e70753ea1c15fe130134929f`。范围冻结见 `../unattended_20261026/U1_SCOPE_FREEZE_20261030.md`。本包是可审阅离线候选，不是生产执行授权。 / This is a reviewable offline candidate, not production authority.

## 交付对象与准确边界 / Deliverables and exact limits

`SOURCE_MANIFEST.json`固定25份源码/配置/脚本的Git blob及SHA256；`PINNED_SOURCE.zip`保存同字节，`PINNED_IMPORT.json`记录21模块隔离导入。`dev-package`由这些固定Git字节编译，含真实x64 PE、严格禁用配置、六项.NET依赖指纹及安装/回滚脚本。`DEV_PACKAGE_BUILD.json`记录清单及PE哈希。所有本地指纹是观察，不等于批准。 / The source manifest pins25 files, the archive preserves the same bytes, and isolated imports cover21 modules. The development package is compiled from those Git bytes and contains a real x64 PE, disabled configuration, six .NET dependency fingerprints and installation/rollback scripts. Build metadata records package/PE hashes. Local fingerprints are observations, not approval.

宿主仅写无签名本地heartbeat，不监听8791、不含Python或生产backend、不派发/取消Inventory，也不创建调度器。它尚不满足`host_remediation.py`的8791认证接口、Python/runtime和31项生产门禁。不得用此包替换既有桥接或声称无人登录业务已可用。 / The host only writes unsigned local heartbeats. It has no8791 listener, Python, production backend, Inventory dispatch/cancel or scheduler. It does not satisfy the existing authenticated8791/Python/runtime/31-gate production contract. It must not replace the existing bridge or be described as unattended business capability.

## 发布前门禁 / Pre-deployment gates

1. 整体固定候选独审及本轮基线/候选实际回归；37失败17错误的历史基线不是全绿，必须比较精确ID。 / Review the whole pinned candidate and actually compare baseline/candidate IDs; the baseline with37 failures/17 errors is not all green.
2. WorkBuddy只读验证：目标执行身份、实际有效ACL、服务虚拟身份能力、非交互网络出口、实际Python/SQLite/时区及.NET依赖，以及原发布器新增文件备份/原子替换/删除回滚能力。缺失项明确UNKNOWN，不以声明或签名代替OS事实。 / WorkBuddy verifies actual identity/effective ACLs, virtual-account capability, noninteractive egress, actual runtimes and publisher support for new-file backup/atomic replacement/removal rollback. Missing facts remain UNKNOWN; signed declarations do not establish OS facts.
3. 原Inventory `1784775229336`、原排他锁、唯一调度权威及维护窗口必须有正式绑定。新安装互斥锁只防重复安装，不代替生产排他锁。既有4A8U/V/W不重复apply，未知operation先status。 / Formally bind the original Inventory, exclusive lock, sole scheduling authority and maintenance window. The installation mutex only serializes installation. Do not reapply4A8U/V/W; query unknown operations before any replay.
4. 独立批准精确manifest哈希及脚本；传入哈希不能自行构成权限。正式安装只能由获准发布器执行，本轮不运行Execute。 / Independently approve exact manifest/script bytes. Passing a hash grants no authority. Only the authorized publisher may execute installation; this iteration does not run Execute.

## 一次性最小管理员授权草案 / Draft minimum administrator authorization

目前不请求执行：先完成WorkBuddy兼容核验，避免用户批准不完整对象。之后请求一个明确维护窗口内、一次受审固定哈希包的**禁用态安装**： / Not requested for execution yet: complete WorkBuddy compatibility validation first. Then request one reviewed exact-hash package's disabled installation in a specified window:

- 新服务仅`RoktU1Bridge`，虚拟账户`NT SERVICE\RoktU1Bridge`，不默认LocalSystem。已存在服务或目标目录即拒绝，不采用旧BDExecutionHost。 / Only the new named service and dedicated virtual account; no default LocalSystem. Existing service/target paths are rejected; no adoption of BDExecutionHost.
- 代码仅`C:\Program Files\RoktU1Bridge\v1`，状态仅`C:\ProgramData\RoktU1Bridge`；服务代码RX、状态Modify，管理员/SYSTEM保留管理权限，禁止junction/reparse祖先。 / Fixed code/state directories; service code RX/state Modify, administrative management retained, and reparse ancestors rejected.
- 只登记Disabled并回读Stopped/身份/映像，不启动、不启用、不新建Inventory/计划任务，不修改代理、SMTP、配额或生产数据库。 / Register Disabled and read back stopped state/account/image only. No start/enable, Inventory/task creation, proxy/SMTP/quota or production DB change.
- 允许失败时撤销本次新建且仍匹配的停止服务登记；保留代码、状态及审计。 / Permit removal only of this invocation's matching stopped registration on failure; preserve code/state/audit.

真正生产启动、原权威切换和无人登录验收需另一个具体可审核方案，不能暗含在禁用安装授权中。 / Actual activation, authority cutover and unattended acceptance require a separate concrete reviewed plan, never implicit in disabled installation approval.

## 安全回滚 / Safe rollback

安装回滚只在精确manifest、安装回执、身份、映像和PE哈希相符且服务停止后删除该登记；保留所有文件和账本。不恢复旧数据库，不退还UNKNOWN预留，不覆盖claim、首次资格历史或取消日志。 / Installation rollback only removes the matching stopped registration after verifying manifest/receipt/account/image/PE hash; it preserves all files and ledgers. Never restore old databases, refund UNKNOWN reservations or overwrite claims/qualification/cancellation history.

取消恢复新增独立schema1恢复日志，原取消journal不变。新guard使用`rokt.recovery-guard.v2`固定文件上的OS锁，进程退出释放；旧空guard不删除、不猜测陈旧。旧执行器O_EXCL遇到新marker拒绝，因此**回滚只能停用保留，不得恢复旧执行器继续运行**，直到兼容性重新获证。 / Cancellation recovery adds a separate schema1 recovery log and preserves the original journal. The v2 marker uses an OS-owned lock released on process exit. Legacy empty guards are retained and rejected. Legacy executors fail their O_EXCL acquisition against the new marker; rollback must therefore stop and preserve state, not resume an old executor without renewed compatibility proof.

`PREPARED`、费用已结算、原预算已结算或`COMPLETED`后中断均须用相同固定证据继续对账；活owner、未知存活、签名/路径/原token冲突一律拒绝。恢复身份硬拒绝普通execute/reconcile及新claim，不自动重放。超额费用及其重复回执保持unverified。 / Interrupted recovery resumes only with the same fixed evidence. Live/unknown owners and signature/path/token conflicts reject. Recovery-only identity cannot execute, use ordinary reconcile or claim new work. Overrun costs and duplicate overrun receipts retain the fence. No replay occurs.

## 验收与未执行 / Acceptance and non-actions

本地测试不证明实机安装、8791跨调用/跨登录、无人登录出口或业务增长。正式验收继续使用原Inventory自然运行，检查重启/注销/桌面关闭、唯一权威与原锁及至少两次真实自然周期；SAFE、唯一组织、官网、邮箱和净增长没有新鲜可比权威证据时仍UNKNOWN。 / Offline tests do not prove live installation, bridge persistence, login-free egress or business growth. Acceptance uses the original natural Inventory, reboot/logoff/desktop-closed evidence, sole authority/original lock and at least two real scheduled cycles. Business measures remain UNKNOWN without fresh comparable authoritative evidence.

本轮生产安装/启动/ACL修改/生产DB写入/采集/邮件均0。报告自检：中英双语、明确范围/风险/未执行及下一步，无凭据、客户资料或代理地址。 / Production installs/starts/ACL changes/DB writes/collection/mail this iteration: zero. Self-check: bilingual scope, risks, non-actions and next steps, with no credentials/customer data/proxy addresses.
