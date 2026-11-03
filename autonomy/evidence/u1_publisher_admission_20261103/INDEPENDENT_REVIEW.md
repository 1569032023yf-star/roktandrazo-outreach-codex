# 独立离线安装维护调用链审核 / Independent offline install-maintenance call-chain review

固定源码 / Source: `d47e5d9f2f51bf0acc2f9dc4d3dc2a12b6287923`
基线 / Baseline: `061549f0a146606eec1a62f2634e56ecd99d5ea1`

结论：**OFFLINE_SCOPED_REVIEW_PASSED**。已扩展至当前连接的安装维护代码路径，未发现未关闭的新增阻断；这不等于真实Windows完整安装成功或生产验收通过。`RELEASE_READY=false`、`allow_install=false`、`FULL_CHAIN_ACCEPTANCE_PASSED=false`。

Conclusion: **OFFLINE_SCOPED_REVIEW_PASSED**. Review extends across the currently connected install-maintenance code path with no remaining new blocking findings. This is not successful complete real-Windows installation or production acceptance. `RELEASE_READY=false`, `allow_install=false`, `FULL_CHAIN_ACCEPTANCE_PASSED=false`.

## 原阻断闭环 / Closure of the original blocker

595dbe2558d1a1e7b8875f70fa30ce606e5c1ef1 虽29项测试通过，独立真实SQLite探针证明父RECOVERY_ADMITTED+子HELD提交后、子启动前退出，会因零进程记录而被入口永久拒绝补偿。因此旧版本判BLOCKED；旧双语报告/JSON保留于DIAGNOSTIC_595_*，不继承其成绩。

Although 29 tests passed on 595dbe2558d1a1e7b8875f70fa30ce606e5c1ef1, an independent real-SQLite probe showed that exit after committed parent RECOVERY_ADMITTED / child HELD but before child launch permanently blocked compensation due to zero process records. The old candidate was BLOCKED; its report/JSON remain in DIAGNOSTIC_595_* and its result is not inherited.

新修复将严格HELD+零进程事件证明域分离为NO_PROCESS_INTENT，绑定session.key/context/维护链尾摘要；补偿在同一BEGIN IMMEDIATE内再次核验并比较证明，防HELD推进至INSTALL_INTENT后沿用旧证明。只有严格原root三字段context可显式abandon，原子写ABORTED_NOT_STARTED+RELEASED并报告NOT_STARTED；补偿child带parent/recovery字段，不能放弃父事务维护权，只能新recid继续补偿。INSTALL_INTENT零事件及LAUNCH-only仍未知。上述三类独立探针全部通过，原阻断关闭。

The fix gives strictly HELD plus zero process events a domain-separated NO_PROCESS_INTENT proof bound to session.key/context/session-chain tail. Compensation rechecks and compares proof inside the same BEGIN IMMEDIATE, preventing stale HELD proof after advancement to INSTALL_INTENT. Only an original root with the strict three-field context may explicitly abandon, atomically recording ABORTED_NOT_STARTED+RELEASED with NOT_STARTED. A compensation child with parent/recovery fields cannot abandon its parent's exclusion and must hand off using a fresh recovery ID. INSTALL_INTENT with zero events and LAUNCH-only remain UNKNOWN. All three independent probe categories passed, closing the blocker.

## 已审核调用路径 / Inspected connected path

1. 原HTTP Bearer先认证；U1正文严格键集合/重复键/操作标识校验。HTTP不能传命令、路径、批准摘要或授权布尔值。非法body仅在inflight_begin实际成功后才end，避免误清另一活动计数。
2. 原executor seal检查后进入SealedChannel，实际固定cfg/scope/seal句柄，要求sealed=True且tampered=False、内存配置与磁盘公开字段相符、固定Inventory及原lock prefix；批准仅来自sealed cfg.u1_install.approvals。
3. status只读DB且不增加inflight；写连接mode=rw不创建替代正式DB。同invocation重复只返回链日志，目标/action变更拒绝。维护标记、墓碑、HELD在同一SQLite事务持久，并与原Inventory/Publisher run-lock的BEGIN IMMEDIATE准入互斥。
4. InstallCommand保持包/父目录/运行时/固定系统组件句柄，按独立批准摘要读取；普通包拒hardlink，系统例外仅六.NET组件和固定PS。固定内部命令不接受HTTP命令，公开Execute仍硬拒；私有入口先维护RPC ACK。expiry拒正向安装升级，补偿仍需实时维护权。
5. Windows Job先LAUNCH_INTENT，再挂起CreateProcess/AssignJob/真实PID+FILETIME+image持久化，再Resume。主线程watchdog与私有有界stdio IPC检查同一会话，协议错误sticky、ACK非阻塞、显式继承句柄；失败清理整树/readers并持久STOPPED，未知不释放。
6. PowerShell协调器在变更前持久根身份/原ACL，文件精确自有集合与前后字节/备份/哈希链，ACL非对称继承策略、SCM Disabled/Stopped/身份、历史回滚预检、未知全局fence和显式补偿保持。RPC是协调器阶段/调用边界检查，不声称每个底层文件/ACE操作均跨进程原子检查。
7. InstallVerifier不信stdout，绑定目标operation/source/manifest/实际receipt/files、根身份、独立SCM/ACL观察、两次nonce观察与进程终止证明，终态证据先持久，再由同事务FINAL_VERIFIED+维护释放+RELEASED完成。仅文件事务日志有sequence/previous哈希链；其他日志为受信目录与原始字节摘要绑定。中断只允许读回核验或新recovery_id同权补偿，父交接后不能晚到释放。

The inspected path covers (1) original Bearer authentication and strict U1 requests, including the corrected inflight lifetime; (2) actual cfg/scope/seal pins, strict original seal and memory/disk agreement, with approvals solely from sealed configuration; (3) read-only status, existing-only writable DB, journal-only duplicates and atomic exclusion shared with original Inventory/Publisher admission; (4) durable approved package/runtime/system-component pins and a fixed internal command, keeping public Execute closed and requiring private-entry RPC; (5) suspended Windows Job creation with durable process identity before Resume, live watchdog/IPC, bounded nonblocking acknowledgements and verified cleanup; (6) persistent file/ACL/SCM transactions, asymmetric ACL policy, exact ownership, rollback preflight and UNKNOWN preservation; and (7) independent target/process/terminal evidence followed by same-transaction verified release, or explicit same-exclusion compensation. RPC checks occur at coordinator stage/helper boundaries rather than atomically around every underlying file/ACE operation. Only the file transaction log has a sequence/previous chain; other logs use trusted storage and raw-byte digests.

## 独立实测 / Independent execution

固定新源码独立运行两组合，合计 **94/94通过，零errors/failures**；时间231.138秒是两组合测试耗时之和，不是并行墙钟耗时：

- `python -m unittest test_publisher_install_admission test_publisher_install_maintenance test_install_command test_install_process -v`：41项，40.348秒。
- `python -m unittest test_install_inputs test_maintenance_control test_host_install_transaction test_windows_acl_transaction test_install_verifier test_publisher_maintenance -v`：53项，190.790秒。

Both suites were independently run on the new pin: **94/94 passed, zero errors/failures**. The 231.138 seconds is the sum of suite durations, not parallel wall-clock time. Counts and durations are listed above.

覆盖真实隔离HTTP认证/seal/SQLite、实际Windows输入锁/Job/进程死亡、真实PS协调器与IPC、临时文件事务、真实临时DACL故障注入，以及SCM/ACL受限替身下的首装/升级/两次回滚与终态核验。HTTP正向安装/进程/final成功回调仍是明确替身，不能与另一个实际协调器测试拼成一次完整真实安装证据。

Coverage includes real isolated HTTP/auth/seal/SQLite, actual Windows input locks/Jobs/process death, the real PS coordinator and IPC, temporary file transactions and real temporary-DACL fault injection, plus install/upgrade/both rollbacks and terminal checks under bounded SCM/ACL doubles. Successful HTTP install/process/final callbacks remain explicit doubles and cannot be combined with the separate coordinator tests into evidence of one complete actual installation.

另在新pin执行六项独立探针：root未启动显式NOT_STARTED释放；重开未启动child禁止释放但可继续新补偿；旧证明到事务内变化拒绝交接；并发相同HTTP总安装回调一次且重复仅日志；执行期间真实配置写锁拒绝；五份原现场源码/候选来源SHA256匹配。未改产品源码、未读现场配置或凭据。

Six additional probes on the new pin verified root NOT_STARTED abandonment; reopened child no-release plus renewed compensation; refusal when proof changes before the transaction; one installer call under duplicate concurrent HTTP; actual configuration-write denial while pinned; and matching five original/candidate provenance SHA256 pairs. Product source was not changed and production configuration/credentials were not read.

## 工程包与配套闭包 / Engineering and support-package closure

独立验证工程包71条payload精确集合/摘要、外manifest与source绑定、install.zip/rollback-tools.zip每项与解包树逐字节一致、PE AMD64 0x8664。publisher-support.zip SHA256 `acb0db62e03128cd1dfe8434b65c98cd677e038b8f76c942f77bcffba617c2d9`，manifest `7639935e0c476a2ba1c58c165da4450734c85321da531014042ce827821bd73e`；17payload与固定Git blob逐字节一致，bin五文件expected_before为原精确SHA，其余十二路径ABSENT，布局严格bin/publisher_channel/autonomy。新隔离目录解压，Python -I -B实际导入全部入口/helper并确认模块来源为解压树；未load_config、读CredMan、启动监听或打开DB。Inventory companion patch/binding单独保留，不扩17文件白名单。

Independently verified exactly 71 engineering payload entries, outer manifest/source binding, byte-for-byte ZIP/tree equality and PE AMD64 0x8664. The support archive and manifest hashes shown above bind 17 payload files exactly matching pinned Git blobs: five bin files require original exact SHA before-images and twelve new paths require ABSENT. Layout is restricted to bin/publisher_channel/autonomy. Fresh temporary extraction imported all entry/helper modules under Python -I -B and verified their origin in that tree, without load_config, CredMan reads, listeners or DB access. The Inventory companion patch/binding remains separate and does not expand the 17-file whitelist.

support不包含配置/凭据或自动更新器，其expected_before只是工程交付条件，并非批准修改现场。DELIVERY与support的allow_install/production等门禁全部false。完整摘要及文件SHA256见JSON；所有审核文件与固定源码规范化匹配且无tracked diff。

Support contains no configuration, credentials or automatic updater. Its before-images are engineering delivery conditions, not approval to modify the site. DELIVERY/support installation/production gates remain false. Full hashes are in JSON; all reviewed files match the pin after line-ending normalization with no tracked diff.

## 待验收范围 / Pending acceptance

原发布器配置/批准seal刷新与现场部署未执行；固定系统Windows PowerShell完整私有入口的成功执行和真实生产SCM/ACL读回尚未验收，不能绕执行策略。LAUNCH-only未分配窗口仍UNKNOWN，不能声称挂起遗留进程已清理。整体状态不能提升到可安装、RELEASE_READY或生产验收通过；本轮无生产目录/ACL/服务/DB/Inventory写入，无策略修改。

Original publisher configuration/approval-seal refresh and site deployment were not performed. Successful complete private-entry execution under fixed system Windows PowerShell and real production SCM/ACL readback remain unaccepted; execution policy must not be bypassed. The unassigned LAUNCH-only window remains UNKNOWN and does not establish cleanup of a suspended orphan. This scope cannot be promoted to installability, RELEASE_READY or production acceptance. No production directories/ACLs/services/DB/Inventory were written and no policy was changed.

临时DACL集成范围：以当前用户SID替代服务SID，仅在隔离fixture替换审计目录/日志SYSTEM/Admin所有者门禁；原门禁另验证拒绝普通用户fixture，不是生产服务身份成功验收。

Temporary-DACL integration substitutes the current-user SID for the service SID and replaces audit/journal SYSTEM/Admin-owner gates only in isolated fixtures. Original gates separately reject ordinary-user fixtures; this is not production service-identity acceptance.
