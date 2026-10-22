# 共享报告写入补修 / Shared-report write repair

独立临时目录复现：无互斥日报read-modify-write会覆盖并发新增历史。现修复observer和CLI共享supervisor实例互斥，HTTP留在锁外；日报临时文件flush/fsync后原子替换，失败保留旧完整文件。工作线状态在锁内读取后更新，保留其他进度。
Independent temporary-directory reproduction: unlocked report read-modify-write can erase concurrently appended history. Observer and CLI now share supervisor instance exclusion, with HTTP outside the lock. Reports flush/fsync a temporary file before atomic replacement; failure preserves the previous complete file. Workstream state is read and updated under the lock, retaining unrelated progress.

独立初审要求两项补修：部分发布后不能依据latest的时间延长旧认证段；public dashboard(receipt)不得绕过时间顺序。现以成功发布的observed_at和实际文件字节SHA保护新鲜段，public路径统一持久化入口，拒绝逆序。Windows真实复现又发现CRLF与内存LF哈希不符，已改为持锁读取实际文件字节计算；新增真实发布→无回执CLI的回归。
Independent review required two follow-ups: partial publication must not extend an old authenticated section from latest alone; public dashboard(receipt) must not bypass ordering. Fresh-section protection now binds successful publication time and actual report-byte SHA. Public calls use the same persistence path and reject older observations. Real Windows reproduction found CRLF versus in-memory LF hash mismatch; hashing now uses actual bytes under the lock, with a real publication-to-no-receipt CLI regression.

父级42项定向测试通过，最终独立复审另列证据。测试为离线临时目录、实际本地文件与故障注入，不访问生产DB或SMTP，不将测试视作无人值守生产验收。
Parent targeted tests:42 passed; final independent review is recorded separately. Tests use offline temporary directories, real local files and injected failures without production DB or SMTP access. They do not establish unattended production acceptance.

各本地文件不宣称跨文件事务：immutable回执保留，latest已落盘而衍生报告失败时可由同一认证回执显式恢复；无成功发布证明则降级UNKNOWN。互斥冲突拒绝本次写入，不强删旧锁、不盲重跑业务操作。所有报告/状态写者必须遵循相同互斥，无法保护绕过协议的外部编辑器。
No cross-file transaction is claimed. Immutable receipts persist; when latest succeeds but derived publication fails, the same authenticated receipt can explicitly repair local reports. Missing publication proof yields UNKNOWN. Lock contention rejects the write without forcibly deleting stale locks or replaying business operations. All report/state writers must follow the same exclusion; external editors bypassing it are outside the guarantee.

C3仍缺多个真实心跳中开发、测试、独立审核、获准发布及生产验收的完整成果链；当前goal续接是manual，不能改记codex_heartbeat。两个摘要/报告周期不能代替该证据。三个awaiting任务由原生App接续，不强制queued进入旧CLI固定白名单。two_unattended_cycles保持拒绝，不以恒true掩盖证据不足。
C3 still lacks the complete artifact chain across multiple real heartbeats covering development, tests, independent review, authorized release and production acceptance. This goal continuation is manual and must not be relabeled codex_heartbeat. Two summary/report cycles cannot replace that evidence. Three awaiting tasks use native App continuation and are not forced into the old CLI allowlist. two_unattended_cycles stays rejecting rather than hiding missing evidence with unconditional approval.

下一步：独立复审通过后提交，使用正式只读observer验证共享报告实际发布；继续既有受限交接，不重apply。未修改客户数据、发送、权限或自动化。敏感检查：无凭据或客户明细。
Next: after final independent approval, commit and verify actual shared publication through the supported read-only observer. Continue the existing bounded handoff without reapplying. No customer-data, sending, permission or automation changes. Sensitive check: no credentials or customer records.
