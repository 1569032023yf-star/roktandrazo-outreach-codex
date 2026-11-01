# 源guard失败停用 / Source guard invalidation

实际开始 / Actual start: 2026-11-01T19:44:47.8292126+08:00; recorded: 2026-11-01T11:46:24.124116+00:00.
恢复本地/远端HEAD / Restored local/remote HEAD: eb35c8648b435f6511f424d791b8d4ef8b7bdf48.
固定完整源码 / Full pinned source: 2fe05bb1114cbf09944baa28a1a9aed1bc2f58a6.

此前revalidate在普通名字/hash/读取失败后仍保持_active=true，修复文件后同一上下文可能再次返回有效快照。本轮将整个活动复核包进BaseException处理，任意失败或中断均置_active=false后原样抛出；不自动关闭句柄、不自动重试、不恢复旧journal。后续revalidate拒NO_ACTIVE_SOURCE_HANDLES，__enter__仍GUARD_SINGLE_USE。明确close或上下文退出才释放保留句柄；新guard只允许新的离线观察，不解除已记录UNKNOWN或授权重放。
Previously ordinary name/hash/read failures left _active=true, allowing a repaired namespace to produce another snapshot in the same context. This cycle wraps active validation in BaseException handling, deactivating on every failure/interruption while re-raising the original exception. No automatic handle close, retry or old-journal restoration. Later revalidate rejects NO_ACTIVE_SOURCE_HANDLES and __enter__ remains GUARD_SINGLE_USE. Explicit close/context exit releases retained handles; a new guard is only a new offline observation, never clearance of journal UNKNOWN or replay authority.

新增4项真实Windows隔离测试：替换后恢复原对象仍停用；删除额外名字仍停用；注入读取异常保持原异常及句柄；KeyboardInterrupt停用且退出后释放。32定向通过0.930s，109组合通过6.173s，命令/输出见TEST_OUTPUT.txt，组合子进程timeout120s。包含既有真实进程exit37/UNKNOWN日志集成；并未新增真实进程中断采集或安装。作者自检通过，独审PENDING，旧079792aa状态层审核不覆盖此源码。按本次隔离guard变更运行直接依赖组合测试，不运行/继承旧833全量或声称NO_NEW_REGRESSION。
Four new actual Windows tests cover restoring the original object after substitution, removing an extra name, preserving the original injected read error and retained handles, and KeyboardInterrupt invalidation with release on exit.32 targeted pass0.930s,109 combined pass6.173s; command/output in TEST_OUTPUT.txt, subprocess timeout120s. Existing real exit37/UNKNOWN journal integration is included; no new production process interruption or installation. Author self-check passes, independent review PENDING; older079792aa status-layer review does not cover this source. Direct-dependency combined regression covers the isolated guard change; old833 full-suite results are neither run nor inherited, and NO_NEW_REGRESSION is not claimed.

检查后的替换窗口未关闭，命名空间不可变/ACL/已有可写映射/正式Inventory维护租约/可信Windows适配/成功持源发布（错误5）/掉电持久性/backend/成功后丢回执/新文件删除回滚仍未通过。停用是当前进程上下文状态，不是持久跨进程fence；持久保护继续依靠既有journal且UNKNOWN不重放。
Post-check replacement remains possible; namespace immutability, ACLs, existing writable mappings, formal Inventory lease, trusted Windows adapter, successful held-source publication(error5), power-loss durability, backend, post-success receipt loss and new-file/deletion rollback remain unaccepted. Invalidation is in-process context state, not a durable cross-process fence; persistent protection still relies on the existing journal without UNKNOWN replay.

WorkBuddy远端main实际ls-remote仍3033463370e7adf62943e642632955c74394bc7c，无新证据，不重复Issue2回执6546897497。历史SAFE69/69、严格24h/7d增长UNKNOWN；七firing五run两非执行、零漏跑UNKNOWN；Lake20/20 web pending完成5/9、Ithaca未解；8791历史session UP/bootfalse，无人登录持久性未过，7877非交互出口UNKNOWN。不能推断本轮生产即时健康或计划结果。
Actual WorkBuddy remote main ls-remote remains3033463370e7adf62943e642632955c74394bc7c. No fresh evidence or duplicate Issue2 receipt6546897497. Historical SAFE69/69, strict24h/7d growth UNKNOWN; seven firings/five runs/two nonexecutions, zero misses UNKNOWN; Lake20/20 web pending5/9, Ithaca unresolved;8791 historical session UP/bootfalse without unattended persistence acceptance,7877 noninteractive egress UNKNOWN. Current production health/scheduled outcomes are not inferred.

下一项 / Next: 继续离线验证安装前源检查与日志意图的跨进程失败边界，固定候选独审PENDING；正式租约/ACL/可信适配和成功持源发布仍未通过。
Continue offline cross-process failure boundaries between pre-install source checks and journal intents; pinned review PENDING, formal lease/ACL/trusted adapter and successful held-source publication remain unaccepted.

已实际读取canonical本地队列、当前checkpoint/实现/测试和限定独审，核实HEAD/远端、主/宿主dirty及进程/代理变量名/锁；正确.codex附件可读仅作约束。保留原取消证据和宿主未跟踪文件、creator bridge9836及recovery guard。仅释放本轮核对cycle锁，不覆盖其他开发者工作。会话级45分钟硬限制接口未提供，不创建系统任务，本轮有界测试并时限内保存退出。
Actual local canonical queue, checkpoint/implementation/tests and scoped independent review were read; HEAD/remote, main/host dirty files, processes, proxy names and locks checked. Corrected.codex attachment read for constraints only. Preserve existing cancellation/host untracked files, creator bridge9836 and recovery guard. Release only verified cycle-owned lock, preserving others' work. Session-level45minute hard limit interface unavailable; no new system task, bounded tests and saved completion within limit.

交付清单：两个固定源码/测试文件、此目录证据、canonical投影及U1 checkpoint。离线回滚可git revert固定源码，保留journal/账本；不执行生产备份/回滚。未触生产DB/HTTP/SMTP、城市/配额、服务/调度/ACL/权限/代理，未采集/部署。
Delivery manifest: two pinned source/test files, evidence directory, canonical projection and checkpoint. Offline rollback may revert the source pin while preserving journals/ledgers; no production backup/rollback. No production DB/HTTP/SMTP, city/quota, service/task/ACL/privilege/proxy changes, collection or deployment.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN; allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.
