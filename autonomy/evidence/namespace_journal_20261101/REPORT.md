# 源身份与持久日志接合 / Source identity and durable journal integration

实际开始 / Actual start: 2026-11-01T16:41:14.6014706+08:00; recorded: 2026-11-01T08:43:19.720138+00:00.
恢复本地/远端HEAD / Restored local/remote HEAD: 6dcd4248c52c6481d67dc5e41ae200d1db99d493.
固定完整候选 / Full pinned candidate: b0eac7720aa21400874bc18c92b0c451413dc785.

新增测试通过既有continue_offline钩子调用真实SourceIdentityGuard.revalidate，联接既有exercise_install_contract/InstallJournal；运行源码未修改。共享删除的源替换仅在隔离夹具内注入，默认源保护不弱化。效果为临时目录文件，不是服务安装/发布。
New tests invoke real SourceIdentityGuard.revalidate through the existing continue_offline hook and join exercise_install_contract/InstallJournal without runtime changes. Delete-sharing replacement is injected only in isolated fixtures, leaving default source protection unchanged. Effects are temporary files, not service installation/publication.

四项实测：意图fsync后替换源，STAGE未执行而意图保留；STAGE效果/读回后替换源，不写回执、UNKNOWN保留；PUBLISH效果后注入条件丢失，保留一个STAGE回执和PUBLISH未决；真实子进程持有默认源句柄，STAGE效果后exit37，保留UNKNOWN且句柄释放。每项逐字比较重试前后日志字节，相同operation被CREATE_NEW拒绝、adapter.calls为空，已有效果不清理/不重放。条件丢失不是正式租约发行/撤销证据。
Four actual tests cover replacement after intent fsync (pending STAGE, no effect); replacement after STAGE effect/readback (no receipt, UNKNOWN); injected-condition loss after PUBLISH effect (one STAGE receipt and pending PUBLISH); real child exit37 after STAGE while holding default source handles (UNKNOWN retained, handles released). Each compares exact journal bytes before/after rejected same-operation retry, with zero new adapter calls, preserving effects without replay. Condition loss is not evidence of formal lease issuance/revocation.

4新增通过0.424s、105组合通过6.528s。测试进程timeout120s，子进程timeout20s，命令/输出见TEST_OUTPUT.txt。仅新增离线集成测试，不重跑未变化运行源码的833全量，不继承其结论。作者自检通过；独立Reviewer未执行，当前固定候选PENDING；旧079792aa审核仅状态读取层，不能覆盖本轮。
4 new tests pass0.424s and105 combined pass6.528s. Test subprocess timeout120s, child timeout20s; command/output in TEST_OUTPUT.txt. Only offline integration tests changed; no mechanical833 rerun on unchanged runtime sources or inherited conclusion. Author self-check passes; independent review not performed, pinned candidate PENDING. Older079792aa review only covers status inspection.

尚未完成：检查返回后的替换窗口仍存在，持续命名空间排他/ACL/正式Inventory租约、可信Windows适配、成功持源目录发布（错误5）、已有可写映射、掉电持久性、成功后丢回执、backend与新文件/删除回滚未通过。未运行真实安装，不把模拟PUBLISH.effect当真实目录rename。
Open: post-check replacement window, continuous namespace exclusion/ACL/formal Inventory lease, trusted Windows adapter, successful held-source directory publication(error5), existing writable mappings, power-loss durability, lost receipts after success, backend and new-file/deletion rollback remain unaccepted. No real installation; PUBLISH.effect is not actual directory rename.

WorkBuddy main实际ls-remote仍3033463370e7adf62943e642632955c74394bc7c，沿用Issue2已消费回执6546897497，不重复请求或发回执。历史SAFE69/69、严格24h/7d净增长UNKNOWN；七firing五run两非执行、零漏跑UNKNOWN；Lake20/20 web待办5/9、Ithaca未解；8791历史session UP/bootfalse、无人登录持久性未过，7877非交互出口UNKNOWN。无新证据不推断当前健康或计划执行。
Actual WorkBuddy main ls-remote remains3033463370e7adf62943e642632955c74394bc7c. Reuse consumed Issue2 receipt6546897497 without duplicate request/receipt. Historical SAFE69/69, strict24h/7d growth UNKNOWN; seven firings/five runs/two nonexecutions and zero misses UNKNOWN; Lake20/20 web pending5/9, Ithaca unresolved;8791 historical session UP/bootfalse without unattended persistence acceptance,7877 noninteractive egress UNKNOWN. No new evidence establishes current health/scheduled outcomes.

下一项 / Next: 补齐源身份guard复核失败后的停用/复用合同和跨边界故障覆盖；正式租约/ACL/可信适配与成功持源发布仍阻塞，固定独审PENDING。
Complete source-guard invalidation/reuse contracts after validation failure and cross-boundary faults; formal lease/ACL/trusted adapter and successful held-source publication remain blocked, pinned review PENDING.

启动已实际读取canonical队列，核实主/宿主树、锁、HEAD/remote、进程及代理变量名；正确.codex附件可读，历史约束不覆盖当前事实。保留原未跟踪取消证据和宿主候选、creator bridge9836、recovery guard；仅核对释放本轮cycle锁。不改SMTP、生产DB、城市、配额、服务、系统任务、ACL、权限或代理，无采集/部署。会话45分钟硬限制接口不可用，不建新任务，测试有界且本轮时限内保存。
Startup read local canonical queue and checked main/host trees, locks, HEAD/remote, processes and proxy names; corrected.codex attachment readable for constraints only. Preserve old untracked cancellation/host candidates, creator bridge9836 and recovery guard; release only verified cycle-owned lock. No SMTP/production DB/city/quota/service/task/ACL/privilege/proxy changes, collection or deployment. No session45minute hard-limit interface available; no new scheduled task, bounded tests and saved completion within limit.

发布清单：新增测试、此目录证据、canonical投影和checkpoint，完整blob/SHA256见SOURCE_MANIFEST.json。回滚仅可git revert固定测试提交，保留journal/账本，不进行生产备份或回滚。
Delivery manifest: new test, this evidence directory, canonical projection and checkpoint; exact blob/SHA256 in SOURCE_MANIFEST.json. Offline rollback may revert the pinned test commit while preserving journals/ledgers; no production backup/rollback.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN; allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false.
