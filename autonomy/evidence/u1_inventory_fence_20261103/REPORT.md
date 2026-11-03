# U1 原Inventory维护排斥接线 / Original Inventory maintenance admission

时间 / Updated: 2026-11-03T00:01:50.143893+00:00
恢复远端 / Recovery remote: 3bbb77d7f2cce774b3addfdbf851342ad09393c5
固定源码 / Source: 3f92a49aa9a93e19ec37189b23cda9edb5cea436

中文：本轮进入原调度权威的真实源码接线：bd_db.acquire_run_lock 在原 BEGIN IMMEDIATE 内检查同库维护标记，与日常/Inventory锁争用保持原子。新增维护原语绑定唯一Inventory、operation/source/manifest/nonce；先检查所有原run-lock，不抢占任何历史未释放holder，再在同事务持久化全局标记和操作墓碑。标记无自动到期、跨业务日期继续阻止原Inventory；只有精确持有者且调用方完成最终验证时显式释放。异常不自动释放或重放；永久操作墓碑防丢失回执重入。
English: Real source integration now checks the shared maintenance marker inside bd_db.acquire_run_lock's original BEGIN IMMEDIATE transaction. Maintenance acquisition binds Inventory/operation/source/manifest/nonce, rejects every unreleased original run holder without stale takeover, and atomically persists the global marker and operation tombstone. The marker never auto-expires and fences admission across business dates. Only the exact owner may explicitly release after caller final verification; uncertainty never auto-releases or replays. Tombstones prevent operation reuse after lost receipts.

中文：这是原锁函数的真实实现增量，不是生产验收。24项定向测试实际调用原bd_db锁函数，但数据库严格为隔离目录。包内实际维护模块5项通过。覆盖跨日期、旧holder、重启、错误owner、malformed标记、释放commit失败。初次5项中1项夹具清理失败（SQLite context不关闭连接），已改closing后完整重跑通过，无生产访问。SQLite夹具不证明8791/服务/真实生产跨调用持久性。
English: This is actual original-lock source integration, not production acceptance. The24 targeted tests invoke the real bd_db lock function with an isolated database; five tests also import the packaged maintenance module. Coverage includes date rollover, old holders, restart, wrong owner, malformed marker and release commit failure. Initial cleanup failed because SQLite's context manager does not close connections; closing corrected the harness and the complete rerun passed. These fixtures do not prove bridge/service/production persistence.

中文：原发布器独立executor尚未接入同一标记，安装器持有/释放尚未接入；公开Execute继续hard拒绝。原bd_db变更未纳入宿主安装allowlist；另附固定SHA的精确companion patch，未apply、不自动扩大目标。formal_maintenance_integrated=false，不声明完整互斥或可安装。缺乏独立Reviewer，当前固定候选保持PENDING。
English: The separate publisher executor and installer ownership/release are not yet wired. Public Execute remains hard rejected. The original bd_db change is a separately pinned companion patch, not an automatically expanded host installation allowlist, and has not been applied. Formal maintenance integration remains false; no complete exclusion or installability is claimed. Independent review remains PENDING.

定向 / Targeted: {"command": ["python", "-B", "-m", "unittest", "test_inventory_maintenance", "tests.test_phase2a_safety_mutex", "tests.test_inventory_stage_trace"], "passed": true, "returncode": 0, "seconds": 1.907, "tests_run": 24, "runner_seconds": 1.596}
新可比回归 / Fresh comparable regression: {"baseline_commit": "3bbb77d7f2cce774b3addfdbf851342ad09393c5", "candidate_commit": "3f92a49aa9a93e19ec37189b23cda9edb5cea436", "isolated_root": "C:\\Users\\15690\\AppData\\Local\\Temp\\u1-compare-tvsi108a", "complete": true, "baseline_run": 833, "candidate_run": 833, "baseline_failures": 37, "candidate_failures": 37, "baseline_errors": 17, "candidate_errors": 17, "failure_ids_identical": true, "error_ids_identical": true, "all_green": false, "no_new_regression": true}
安装包 / Install SHA256: 0683278d7070afb515a4299d48cebce96ea126228dab0507e0458316da6893d8
回滚工具 / Rollback SHA256: ceee090a392ad1b5c43fb6e3fe3fb58a200e2fa17cf3f94be8e13bd97a7fb82a
清单 / Manifest SHA256: 3f573728d4710c65aaf54d8912e5e056b7563b41bbf3c767cc2a76ec8b4e5ba4
66文件逐SHA256、ZIP成员字节及AMD64 PE核验通过 / All66 file hashes, ZIP member bytes and AMD64 PE verified.

中文：已核实起始Git远端/branch/clean tracked、规范、本地canonical与checkpoint、Issue2/6567493676 A；无并行U1进程，旧recovery guard保留。WorkBuddy main仍10e269，复用既有6580465343证据消费，不重复索要或采集。自动化每3小时/45分钟预算/两重线不变；未配置或声称平台硬超时。
English: Verified real remote/branch/clean tracked recovery, rules, actual canonical/checkpoint and Issue2 directive A. No concurrent U1 worker; old recovery guard preserved. WorkBuddy main remains10e269; existing receipt6580465343 reused without duplicate requests or collection. Existing3-hour cadence/45-minute budget/two-heavy-line limit unchanged; no platform hard timeout claimed.

下一唯一动作 / Next: 把同一维护标记门禁接入原发布器executor的锁获取调用链，并完成安装器受控持有/最终核验/显式释放接线；全部接线审核完成前保留安装hard gate。
Wire the same maintenance marker into original publisher executor lock admission, then controlled installer ownership/final verification/explicit release; retain installation hard rejection until all consumers are integrated and reviewed.
DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false. 唯一原Inventory / Sole original Inventory:1784775229336.
无生产DB/账本/服务/ACL/调度/配额/邮件变更，无手动采集。No production DB, ledger, service, ACL, scheduling, quota, mail changes or manual collection.

工程回执已发布并精确回读 / Engineering receipt published and exact readback verified: https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/2#issuecomment-6591671132
