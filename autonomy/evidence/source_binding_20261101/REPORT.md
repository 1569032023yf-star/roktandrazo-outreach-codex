# 子对象替换故障实验 / Child-object replacement fault experiment

实际开始 / Actual start: 2026-11-01T10:43:09.0286978+08:00; recorded: 2026-11-01T02:45:20.728641+00:00.
固定候选 / Pinned candidate: 7f083ff3d9bee5361ae90596c92fa518c4382a15. 恢复本地及远端 / Restored local and remote HEAD: e33ef426c62b7ac0d0595d76ed311bc69cc2b0bf.

本轮只新增测试夹具，运行源码未改；READ|DELETE共享仅在临时目录隔离实验注入，不改变已验证的默认不共享删除策略。不部署、不连生产DB/HTTP/SMTP、不改系统服务、任务、ACL或代理。
Only a test fixture was added. Runtime sources remain unchanged; READ|DELETE sharing is injected only in isolated temporary-directory experiments, leaving the default no-delete-sharing policy intact. No deployment, production DB/HTTP/SMTP access, service/task/ACL/proxy changes.

首次4项测试有2项错误：原假设允许删除共享可使目录rename成功，实际仍WinError5。修正为记录真实阻塞后4项通过0.029s，98项组合通过6.692s，测试子进程timeout120s。并非修复后成功发布。组合命令/输出见TEST_OUTPUT.txt；未重跑833，不继承旧候选全量结果。独立Reviewer未运行，保持PENDING。
Initial four-test run had two errors: permitting child delete sharing was expected to enable directory rename, but actual Windows still returned WinError5. Corrected contracts record the blocker: four tests pass in0.029s and98 combined pass in6.692s with120s subprocess timeout. This is not successful publication. See TEST_OUTPUT.txt;833 not rerun or inherited. Independent review not performed, PENDING.

真实文件系统验证：普通写入仍拒绝，但子文件rename可行；移走原文件并创建同名同内容文件，保留句柄的hash/identity以及exact names仍通过，而名字指向的file ID读回拒绝DESTINATION_IDENTITY_MISMATCH。已存在非空目标不覆盖。说明保持对象身份与绑定命名空间是不同条件，不能靠相同bytes证明同一对象。
Actual filesystem tests show ordinary writes remain blocked but child rename is possible. Moving the original and creating an equal-byte file at the same name passes retained-handle hash/identity and exact-name checks, while named file-ID readback rejects DESTINATION_IDENTITY_MISMATCH. Existing nonempty targets are preserved. Object identity and namespace binding are separate conditions; equal bytes do not prove equal objects.

该读回只观察某个时点，不关闭检查后替换窗口；目录成功改名、掉电、成功后丢回执/进程退出、可信适配、正式Inventory租约、受保护ACL、预先可写映射仍未验收。旧path-based退出测试不替代此模式。生产派发/取消保持关闭。
Readback observes one instant and does not close the post-check replacement window. Successful directory rename, power loss, post-success receipt loss/process exit, trusted adapter, formal Inventory lease, protected ACLs and existing writable mappings remain unaccepted. Older path-based crash tests do not substitute. Production/cancellation dispatch stay disabled.

WorkBuddy远端main本轮实际ls-remote仍3033463370e7adf62943e642632955c74394bc7c；沿用已发布并回读Issue2回执6546897497，不再重复。SAFE69/69、严格24h/7d净增长UNKNOWN；七firing五run两非执行，零漏跑UNKNOWN；Lake20/20 web待办、完成5/9，Ithaca未解；8791只有历史会话UP/bootfalse，无人登录持久性未过，7877非交互出口UNKNOWN。没有新证据不推断当前在线/计划执行结果。
WorkBuddy remote main is unchanged by actual ls-remote at3033463370e7adf62943e642632955c74394bc7c. Reuse published/read-back Issue2 receipt6546897497 without duplicate. Historical SAFE69/69, strict24h/7d growth UNKNOWN; seven firings/five runs/two nonexecutions, zero misses UNKNOWN; Lake20/20 web pending5/9, Ithaca unresolved;8791 historical session UP/bootfalse without unattended persistence acceptance,7877 noninteractive egress UNKNOWN. No fresh evidence establishes current health or scheduled outcomes.

下一项：离线实现受限命名空间验证合同，明确身份读回后的替换窗口与租约/ACL依赖；成功发布仍阻塞，固定候选独审PENDING。
Next: Implement an offline constrained-namespace validation contract, including post-readback replacement windows and lease/ACL dependencies; successful publication remains blocked and pinned review PENDING.

交付：固定测试文件、SOURCE_MANIFEST.json、TEST_OUTPUT.txt、本报告、canonical投影及checkpoint。离线回滚可revert固定候选，不改journal/账本；没有生产备份或回滚操作。保留主/宿主树旧未跟踪文件、recovery guard与creator bridge9836。会话45分钟硬限制接口未提供，不创建系统任务；本轮有界测试且时限内保存退出。
Delivery: pinned test file, source manifest, test output, report, canonical projection and checkpoint. Offline rollback may revert the pin while preserving journals/ledgers; no production backup/rollback operation. Preserve old untracked main/host files, recovery guard and creator bridge9836. No session45minute hard-limit interface is available; no system task created, bounded tests and saved completion within limit.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
