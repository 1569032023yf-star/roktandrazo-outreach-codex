# 持源日志跨进程边界 / Held-source journal process boundaries

实际开始 / Actual start: 2026-11-01T22:46:49.6670223+08:00; recorded: 2026-11-01T14:49:02.796094+00:00.
恢复本地及远端 / Restored local and remote: 574575e9241edf85750f1a1c667fa5e30398d551.
固定候选 / Pinned candidate: ac0e9af1694447027ab4cb9128e4bcaca085e824.

新增3项真实Windows子进程测试，运行源码未改。子进程使用默认SourceIdentityGuard、真实exercise_install_contract/InstallJournal以及临时文件效果。exit42发生于STAGE意图fsync后：无效果、pending STAGE/0回执。exit43发生于STAGE回执fsync后：保留STAGE效果及1回执，无PUBLISH效果、pending null，整体UNKNOWN。活跃写入者持有源句柄与STAGE意图时，另一真实进程认领同operation被CREATE_NEW拒，adapter无调用；主进程普通源写入被拒，原日志字节不变。释放后exit44，持久日志继续未决且拒重放。退出后句柄释放不等于UNKNOWN解除。
Three new actual Windows subprocess tests, without runtime changes, use the default SourceIdentityGuard, real exercise_install_contract/InstallJournal and temporary file effects. Exit42 after STAGE intent fsync leaves no effect and pending STAGE/zero receipts. Exit43 after STAGE receipt fsync preserves the effect/one receipt, with no PUBLISH effect and pending null, overall UNKNOWN. While a live writer holds source handles and intent, another actual process cannot claim the same operation (CREATE_NEW), with no adapter calls; parent ordinary source writes are blocked and journal bytes unchanged. Release leads to exit44; durable pending state still cannot replay. Releasing OS handles on exit does not clear UNKNOWN.

3新增通过1.624s，112组合通过8.688s。组合timeout120s，子进程timeout20s、竞争进程15s；等待ready/release有8s/10s截止，只清理本轮创建子进程。命令/输出见TEST_OUTPUT.txt。未机械重跑未变化运行源码的833或继承旧全量结论。作者自检通过；当前固定候选独审PENDING，旧079792aa仅状态层审核。
3 new tests pass1.624s,112 combined pass8.688s. Combined timeout120s, child20s/rival15s; ready/release waits bounded8s/10s, cleaning only owned children. Command/output in TEST_OUTPUT.txt. No mechanical833 rerun on unchanged runtime or inherited full-suite result. Author self-check passes; current pinned independent review PENDING, older079792aa review only covers status inspection.

不代表正式租约、生产安装、目录成功rename、Windows全宿主退出或掉电。成功持源发布仍错误5；检查后替换窗口、ACL/既有可写映射、正式Inventory互斥、可信适配/backend/新文件删除回滚及成功后丢回执未通过。临时STAGE.effect不是安装文件。
Not formal lease, production installation, successful directory rename, whole-host death or power loss. Held-source publication remains error5; post-check replacement, ACL/existing writable mappings, formal Inventory exclusion, trusted adapter/backend/new-file deletion rollback and lost receipts after successful publication remain unaccepted. Temporary STAGE.effect is not an installed file.

WorkBuddy main本轮实际ls-remote仍3033463370e7adf62943e642632955c74394bc7c，回执6546897497不重发。历史SAFE69/69、严格24h/7d增长UNKNOWN；七firing五run两非执行、零漏跑UNKNOWN；Lake20/20 web pending5/9、Ithaca未解；8791历史session UP/bootfalse，无人登录持久性未过，7877非交互出口UNKNOWN。不推断当前生产健康/计划执行。
Actual WorkBuddy main ls-remote remains3033463370e7adf62943e642632955c74394bc7c; no duplicate receipt6546897497. Historical SAFE69/69, strict24h/7d growth UNKNOWN; seven firings/five runs/two nonexecutions, zero misses UNKNOWN; Lake20/20 web pending5/9, Ithaca unresolved;8791 historical session UP/bootfalse without unattended persistence acceptance,7877 noninteractive egress UNKNOWN. No current production health/scheduled outcome inferred.

下一项 / Next: 推进固定离线安装原语差异审阅及保护审计根的失败合同，正式租约/ACL/可信适配和成功持源发布仍阻塞；独审PENDING。
Continue pinned offline installation primitive diff review and protected-audit-root failure contracts; formal lease/ACL/trusted adapter and successful held-source publication remain blocked, independent review PENDING.

已读本地canonical、checkpoint、实现/测试及最新限定审核，核实主/宿主dirty、HEAD/remote、代理变量名及锁。启动其他Python进程均非此repo命令行匹配，不停止、不输出命令行；保留creator bridge9836、旧未跟踪取消证据/宿主候选和recovery guard。正确.codex附件可读仅作约束。仅核对释放本轮cycle锁。会话45分钟硬限制接口不可用，不建系统任务，有界测试并时限内保存。
Read local canonical/checkpoint/implementation/tests/scoped review and checked main/host dirty state, HEAD/remote, proxy names and locks. Other startup Python command lines did not match this repo; preserve them without exposing command lines or stopping them. Preserve creator bridge9836, old untracked cancellation/host candidates and recovery guard. Corrected.codex attachment readable for constraints only. Release only verified cycle-owned lock. Session45minute hard-limit interface unavailable; no system task created, bounded tests and completion within limit.

交付清单：新测试、此目录证据、canonical投影与U1 checkpoint；完整blob/SHA256见SOURCE_MANIFEST.json。离线回滚可git revert测试提交，保留journal/账本；无生产备份或回滚。未触生产DB/HTTP/SMTP、服务/任务/ACL/权限/代理/城市/配额，未采集/部署。
Delivery: new test, evidence directory, canonical projection and U1 checkpoint; exact blob/SHA256 in SOURCE_MANIFEST.json. Offline rollback may revert the test commit while preserving journals/ledgers; no production backup/rollback. No production DB/HTTP/SMTP, service/task/ACL/privilege/proxy/city/quota changes, collection or deployment.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN; allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.
