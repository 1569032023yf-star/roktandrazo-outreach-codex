# U1源对象身份与打开文件hash / U1 source identity and opened-file hashing

固定源码 / Pinned source: `8f775825d51624d68e39b8afb0ad9514af418ee1`。本轮实际开始11/1 04:37:30.988+08，触发10/31 20:37:24.071Z。恢复时主分支/远端均7d18195f063a225f29b189ddd7597c430b586565，本地canonical queue实际读取成功，未用Git投影代替；旧目录identity6dafc860及最新SAFE窗口d143702保持各自范围。/ Actual start04:37:30.988+08 Nov1, triggered20:37:24.071Z Oct31. Local/remote recovery HEAD7d18195f063a225f29b189ddd7597c430b586565. Read actual local canonical queue, not a Git projection; earlier identity/SAFE pins retain their scopes.

## 实现与实测 / Implementation and evidence

新增SourceIdentityGuard，只接受显式offline_only、当地绝对普通路径和精确平面manifest；绑定root→源目录句柄，再持有每个文件GENERIC_READ/SHARE_READ、OPEN_REPARSE_POINT句柄。使用同一已打开句柄读取FileIdInfo/AttributeTagInfo/StandardInfo，再ReadFile计算SHA256，重复读取重置文件指针；检查链接数1、普通文件、非待删、16MiB单文件/64MiB总量、精确文件集合。拒保留设备名、大小写碰撞和不合法manifest。异常释放已获得句柄，CloseHandle失败则保留失败句柄待显式清理，不伪报释放。

New SourceIdentityGuard requires explicit offline_only, local absolute ordinary paths and exact flat manifest. Hold root-to-source directory handles, then each file with GENERIC_READ/SHARE_READ and OPEN_REPARSE_POINT. Query FileIdInfo/AttributeTagInfo/StandardInfo and hash through ReadFile on that same open handle; reset pointer for repeat reads. Require one link, ordinary nonpending-delete files,16MiB per-file/64MiB total and exact names. Reject reserved devices/case collisions/invalid manifest. Release partial acquisitions on failure; retain failed CloseHandle handles for explicit cleanup.

10项新增实际Windows测试通过0.357s：同句柄重复hash、同/跨进程写删改名拒绝、既有writer冲突保留外部writer、错误hash与部分打开清理、硬链接/目录拒绝、额外文件检测、大小界限、读失败清理、CloseHandle失败保留、真实子进程突然退出后释放。组合87项通过5.455s，命令由subprocess120s超时限制；测试只触隔离临时目录。没有全量833重跑，新增组件未接生产路径，执行受影响组件组合；旧833不继承到新固定候选。测试记录见TEST_OUTPUT.txt，源码和依赖指纹见CHECKPOINT.json。

Ten new actual Windows tests pass in0.357s: repeated same-handle hashes; same/cross-process write/delete/rename rejection; existing writer preserved on conflict; wrong hash/partial acquisition cleanup; hardlink/directory rejection; extra names; size limits; read failure cleanup; failed close retention; actual abrupt child exit releases handles.87 combined pass in5.455s under a120s test-process timeout, using isolated temporary directories. No full833 rerun: this additive guard is outside production paths and affected components were combined-tested. Old833 verdict not inherited. TEST_OUTPUT.txt and CHECKPOINT.json retain evidence and source fingerprints.

## 未完成及下一项 / Open work and next action

该组件会阻止源目录改名，尚未接first_publication。不能关闭句柄后再rename并声称原竞态已解。下一步先设计并离线验证持有源身份至同卷首次发布的接合合同，包含目录rename允许模式/源身份后验、空目标竞争与receipt丢失；其后才考虑正式安装适配，不释放UNKNOWN后重放。

This guard prevents renaming the source directory and is not joined to first_publication. Closing handles before rename would reopen the race. Next design/test a contract retaining source identity through same-volume first publication, including rename-compatible sharing/source identity readback, competing empty target and lost receipt. Formal installer integration follows later; never release/replay UNKNOWN.

ACL/有效访问权、预先建立的可写映射、文件系统trust、正式Inventory维护租约、掉电持久性、生产backend和发布器依赖/回滚未验收；当前并非不可变内容或可信安装证明。实际PowerShell观察器既有ExecutionPolicy阻塞不重试/不绕过。最新独立审核仅固定079792aa状态读取层及d7d424c1原离线P0，不覆盖本新源码；本轮没有独立Reviewer，PENDING，不以自检冒充PASS。

ACL/effective access, pre-existing writable mappings, filesystem trust, formal Inventory lease, power-loss durability, backend and publisher dependency/rollback remain unaccepted. No universal immutability/trusted-install claim. Existing PowerShell ExecutionPolicy blocker unchanged without retry/bypass. Independent reviews at079792aa/d7d424c1 cover their original status/P0 scopes only; no independent reviewer for this source, PENDING.

## 生产与恢复检查 / Production and recovery checks

WorkBuddy远端main实际compare仍3033463370e7adf62943e642632955c74394bc7c，无新证据，不重复Issue2回执6546897497或backend请求。沿用消费：SAFE69/69、严格24h/7d增长UNKNOWN；七firing五真实run/两未执行、零漏跑UNKNOWN；Lake20/20 web待办5/9、Ithaca未解；8791仅会话UP/bootfalse、7877无人登录出口UNKNOWN。本轮不调用生产HTTP/DB/SMTP、不启动Inventory/不部署，不能推断04:20计划已真实执行。

Live Git compare shows WorkBuddy main still3033463370e7adf62943e642632955c74394bc7c. No new evidence; retain existing receipt6546897497 and backend request. Existing consumption: SAFE69/69, strict growth UNKNOWN; seven firings/five runs/two nonexecutions and zero misses UNKNOWN; Lake20/20 web pending5/9, Ithaca unresolved;8791 session UP/bootfalse and7877 logoff egress UNKNOWN. No production HTTP/DB/SMTP calls, Inventory start or deployment; scheduled04:20 run cannot be inferred to have executed.

预先存在PID22948 run_inventory_canary3.py（04:28:46启动）与creator bridge9836保留；未能仅凭命令名确认canary授权/生产效果，未终止或重启，也不当本轮U1进程。主树旧未跟踪取消证据及宿主树未跟踪文件保留。原recovery-guard.v2保留；本轮单独cycle锁结束后只删除自己的锁。根CURRENT_STATUS.md/FILE_MANIFEST.md不存在，已读handoff/CURRENT_STATUS.md（历史4A8P不能覆盖当前U1）及现有源码manifest；未创建伪旧状态。附件原缺点路径不存在，正确.codex路径可读，仅作约束参考。

Preserve pre-existing canary PID22948 started04:28:46 and creator bridge9836. Command name alone cannot establish canary authority/effects; neither stop/restart nor count it as this U1 process. Preserve pre-existing untracked cancellation/host files. Keep original recovery guard, remove only this cycle's own lock at completion. Root CURRENT_STATUS.md/FILE_MANIFEST.md absent; read historical handoff status and existing source manifests without overriding canonical U1. Original malformed attachment path absent, corrected.codex path readable for constraints only.

发布清单仅autonomy/source_identity.py、test_source_identity.py、本目录测试/报告/manifest、canonical队列投影与checkpoint。没有生产备份/安装/发布动作；离线回滚为git revert固定源码提交，保留全部状态与日志，不恢复旧账本。会话硬45分钟控制接口不可用，未创建系统任务，采用有界测试及到时停止领取；本轮在限时内保存结束。

Delivery manifest is limited to two new code/test files, this evidence directory, queue projection and checkpoint. No production backup/install/release action. Offline rollback uses git revert of source pin, preserving all state/journals and not restoring old ledgers. Session-level hard45minute control unavailable; no new system task, bounded tests and stop-before-deadline used.

官方API依据 / Official API references: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [FILE_STANDARD_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info), [ReadFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile). 分享模式与字段依据官方文档，跨进程结果依据本地实际测试。Sharing/fields follow official docs; cross-process outcomes come from actual local tests.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.

报告自检 / Report self-check: 中英双语、无敏感凭据、执行与未执行项/风险/下一步明确、未完成不标完成、BD生产边界保留。Bilingual, no credentials, executed/nonexecuted work, risks and next action stated; incomplete work not marked complete, BD production boundaries preserved.
