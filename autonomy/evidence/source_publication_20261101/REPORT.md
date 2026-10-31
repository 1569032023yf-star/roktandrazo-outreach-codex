# U1持有源身份发布失败合同 / U1 held-source publication failure contract

固定源码 / Pinned source: `5f4ec4193f398e50df001a60bc972fa279dcec82`。恢复时主分支codex/autonomous-bd-supervisor，本地与实际远端HEAD均47aaf5bbd86be2bf6f621541c34871972d13e497。实际开始11/1 07:43:04.808+08，触发10/31 23:42:56.659Z。本地canonical autonomy/runtime/queue.json已实际读取；未用Git投影或历史附件替代当前状态。/ Branch and actual local/remote recovery HEAD47aaf5bbd86be2bf6f621541c34871972d13e497. Actual start07:43:04.808+08 Nov1, heartbeat23:42:56.659Z Oct31. Read actual local canonical queue; no substitution with Git projection or historical attachment.

## 发现和实现 / Finding and implementation

本轮在隔离临时目录实测SetFileInformationByHandle(FileRenameInfo)两类情况：空目录仅持源DELETE句柄可成功改名；持有子文件SHARE_READ（不共享删除）时目录改名被WinError5拒绝。不能把“持有源文件身份”和“目录发布成功”两项各自测试成功拼成整体成功，也不能关闭句柄再路径rename后声称竞态已经解决。

Actual isolated Windows experiments show empty-directory rename can succeed with an own DELETE source handle, while held child SHARE_READ handles without SHARE_DELETE cause directory rename to fail with WinError5. Separate identity/publication successes cannot establish joined success; releasing handles before a path rename would reopen the race.

新增source_publication.attempt_source_publication_offline，基类增加受保护_open_handle接点，原默认目录/文件共享模式不变；仅新内部目录类型给自持源句柄请求DELETE，仍不共享删除。使用完整UTF16目标路径、FileRenameInfo、ReplaceIfExists=false，一次尝试前后保留祖先/源/子文件句柄和hash/ID。若OS允许改名则定义同句柄重校验与目标名字对应ID读回；**该成功路径当前实机未通过**，不标可信发布。异常后退出并保留树，不自动关闭后重试、不复制、不覆盖、不回退旧路径发布函数。

New attempt_source_publication_offline adds a protected directory-open hook, retaining default directory/file sharing in existing guards. Only its internal source directory handle requests DELETE, without sharing delete. One FileRenameInfo attempt uses a full UTF16 target and ReplaceIfExists=false while retaining ancestors/source/child handles and hashes/IDs. A success branch defines retained-handle and named-destination identity checks, but **successful held-source publication is not verified on this filesystem**. Exceptions preserve trees; no close-and-retry, copy, overwrite or fallback to the older path-based primitive.

## 测试与日志 / Tests and journal

7新增测试通过0.102s：实际错误5且只尝试一次，源数据保留；改名失败前后同句柄身份/hash一致；既有空/非空目标保留；检查后出现竞争目标保留；hash不符不进入rename；越界/保留设备名/未offline拒绝；真实InstallJournal/driver接合保留completed_steps1、pending PUBLISH、observed UNKNOWN，原operation再次提交在任何adapter调用前拒绝。

Seven new tests pass0.102s: actual error5 with exactly one attempt and preserved source; retained identities/hashes before/after failure; existing empty/nonempty target preservation; competing target after check; hash rejection before rename; path/device/offline gates; actual journal/driver integration retains one completed step and UNKNOWN pending PUBLISH, rejecting the same operation before adapter calls.

组合94项通过5.607s，测试进程120s硬超时，原source identity、目录发布、日志、适配、HTTP/归因/恢复状态组合覆盖；命令记录在TEST_OUTPUT.txt。当前成功rename后丢失receipt/进程退出合同未在该持有子文件模式运行，不能冒用旧path-based发布exit23/29结果；无全量833重跑，不把旧NO_NEW_REGRESSION继承给本新固定源码。独立Reviewer未执行，PENDING；历史079792aa状态读取层和d7d424c1离线P0审核范围保留。

94 combined tests pass5.607s under a120s test-process timeout, combining source identity, directory publication, journal, adapter, HTTP/attribution and recovery contracts. Output in TEST_OUTPUT.txt. Post-success lost-receipt/crash contracts are not demonstrated in this held-child mode; older path-based exit23/29 tests cannot substitute.833 not rerun or inherited; independent review PENDING. Older079792aa/d7d424c1 reviews retain their original scopes.

## 下一项与边界 / Next action and boundaries

下一离线项：设计并故障注入验证允许rename时的子文件名字/持有ID对应关系与替换竞争检测，明确可写映射及目录命名空间竞态如何保持失败关闭；不直接弱化本已验证共享策略。源身份持续绑定的成功发布仍阻塞；正式Inventory维护租约、受保护ACL、可信Windows适配、backend、publisher新文件/删除回滚、掉电持久性及独立审核未完成。原版本化取消费用和reserve-before-intent已完模块不重做。

Next offline work: design/fault-test name-to-retained-ID checks and replacement-race detection under rename-compatible sharing, with explicit writable-mapping/namespace fail-closed limits. Do not simply weaken validated sharing. Successful source-bound publication remains blocked; formal Inventory lease, protected ACLs, trusted Windows adapter, backend, publisher new-file/deletion rollback, power-loss durability and review remain open. Do not reimplement completed cancellation-cost/reserve-before-intent modules.

WorkBuddy实时Git compare main仍3033463370e7adf62943e642632955c74394bc7c，沿用已逐字回读Issue2回执6546897497，不重复发布/合同请求。SAFE69/69、严格24h/7d增长UNKNOWN；七firing五真实run/两未执行、零漏跑UNKNOWN；Lake20/20 web pending完成5/9、Ithaca未解；8791仅session UP/bootfalse、7877无人登录出口UNKNOWN。没有新证据，不推断07:43时生产即时状态或04:20计划的结果。

WorkBuddy main unchanged at3033463370e7adf62943e642632955c74394bc7c by live compare. Reuse verbatim-read-back receipt6546897497; no duplicate receipt/request. Preserve prior SAFE69/69 with strict growth UNKNOWN, five real runs/two nonexecutions and zero misses UNKNOWN, Lake20/20 web pending5/9, Ithaca unresolved,8791 session UP/bootfalse and7877 logoff egress UNKNOWN. No new evidence establishes current production status or04:20 scheduled outcome.

未启动生产采集/Inventory，未连生产DB/HTTP/SMTP，未改服务/调度/ACL/权限/代理、未部署。creator bridge PID9836保留；上轮canary22948本轮检查未出现，未由本轮终止，原因不推断。主树旧未跟踪取消证据与宿主树未跟踪候选保留；合法recovery guard不删除，本轮独有cycle锁仅结束时核对后释放。原附件缺点路径不存在，正确.codex路径可读；仅约束参考。会话硬45分钟接口未提供，不新建系统任务，采用有界测试并在时限内保存退出。

No production collection/Inventory start, DB/HTTP/SMTP access, service/task/ACL/privilege/proxy mutation or deployment. Preserve creator bridge9836. Prior canary22948 absent at this check; not stopped by this cycle and cause not inferred. Preserve old untracked cancellation and host candidates and valid recovery guard; release only this cycle's verified lock. Malformed attachment path absent, corrected.codex path readable for constraints. Session hard45minute control unavailable; no new system task, bounded tests and completion within limit.

交付清单为四源码/测试文件、当前目录证据、canonical投影和U1 checkpoint；完整blob及SHA256见SOURCE_MANIFEST.json。没有生产备份/安装/回滚动作，离线代码回滚使用git revert固定源码提交，保留journal与数据，不恢复旧账本。

Delivery manifest: four source/test files, this evidence directory, canonical projection and U1 checkpoint. Exact blob/SHA256 in SOURCE_MANIFEST.json. No production backup/install/rollback; offline rollback uses git revert of source pin, preserving journals/data without restoring older ledgers.

API依据 / API basis: [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info), [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle). ReplaceIfExists=false语义依据官方文档，错误5和文件保留依据本机实测。Official docs define nonreplacement; error5/preservation come from actual local tests.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.

报告自检 / Report self-check: 中英双语、无敏感信息、实测与未运行成功路径分开、风险和下一步明确、不标未完成为完成。Bilingual, no secrets, actual results separated from unrun success path, risks/next action explicit and incomplete work not marked complete.
