# 原 Inventory 排他独立审核 / Independent original Inventory exclusion review

结论：`OFFLINE_SCOPED_REVIEW_PASSED`。固定源码 `9cbcbbfedbf97dbddae02b7134e3b404962c5034`，审核基线 `cc6434e1fdff68c0069a5cd9a85fe22c4b9d994d`。本范围无未解决阻断；`RELEASE_READY=false`，所有生产门禁保持 false。

Conclusion: scoped offline review passed for the pinned source above. No unresolved blocker in the reviewed scope. This is not release, deployment, installation or production acceptance approval.

## 审核与发现闭环 / Review and finding closure

审核原 `bd_db.acquire_run_lock`、实际 `bd_orchestrator.stage_inventory` 的调用位置、事务及 finally，以及维护与 Publisher 准入。三个入口在各自同一 `BEGIN IMMEDIATE` 内调用共享只读 `inventory_lock_blocked`：精确 Inventory 前缀、忽略 `_acquired_at` 元数据、仅精确字符串 `released` 放行。NULL、空、异常、大小写不同、BLOB 和数值均封锁。跨日期不再通过 stale 时间抢占；非 Inventory 原空值/stale 合同保留。

Reviewed the actual owner call sites, transaction boundaries and finally behavior together with maintenance and Publisher admission. All three consult the same predicate inside their existing immediate transaction. Only exact string `released` admits; metadata keys are excluded. Cross-date Inventory locks cannot be stolen by age; non-Inventory behavior remains unchanged.

旧 68ec 候选的 P1 空值分歧已独立重现：原 owner 拒绝、maintenance 却准入。新 9cbc 的六值三入口探针确认修复。实际 stage 的 `BaseException` 路径保留锁；普通异常和 SystemExit 都拒绝下一日期重入，已知正常返回释放。未知业务结果没有被测试通过或进程退出自动解释为成功。

The former empty-value admission inconsistency was independently reproduced on 68ec and is closed on 9cbc. Actual stage BaseException handling preserves the lock; both ordinary exceptions and SystemExit block next-day admission, while known returns release it. Process exit is not interpreted as successful business completion.

## 独立验证 / Independent validation

- 新固定源码独跑 38 项，8.030 秒，0 failure / 0 error：`python -m unittest test_inventory_maintenance test_publisher_maintenance test_publisher_install_maintenance -v`。
- 六种异常值 × 三准入均拒绝且只保留原行；精确 released 加异常时间元数据仍允许。
- 八个真实独立子进程争用不同日期，仅一个获锁；所有进程退出后，即使 stale 阈值为 -1 仍不重入。
- 从实际源码 AST 加载 stage、接真实原 SQLite acquire/release：Exception/SystemExit 保留 holder；known-return 释放。业务回调仍是隔离替身。

38 tests passed independently on the new pin (8.030 seconds). Additional probes cover the six-value matrix, eight real competing processes, and actual stage AST coupled to original SQLite lock functions. Discovery/provider callbacks remain test doubles. Earlier candidate runs are diagnostic only and are not counted for this pin.

## 产物核对 / Artifact verification

新版工程包 71 文件；两 ZIP SHA、逐 ZIP entry 字节、manifest 摘要和所有 payload 摘要一致；PE machine 为 AMD64 `0x8664`。新版 support 17 文件逐一匹配固定 Git blob、manifest、ZIP 摘要；独立临时解压后使用 Python `-I -B` 完成 import-only，无加载配置/凭据/监听/数据库。摘要详见 `INDEPENDENT_PACKAGE_RESULT.json`。

The 71-file engineering package and both archives were verified byte-for-byte against manifests; the executable is AMD64. All 17 support payloads match pinned Git blobs. Fresh isolated import-only execution passed without configuration, credentials, listener or database access.

companion patch SHA `4a4f12e70ea96a82850b53472dfd50af455b57fae395a08d200862239c0d9e7e`：对绑定的 `3bbb77d7f2cce774b3addfdbf851342ad09393c5` 两份严格 baseline Git blob 纯内存应用 diff，精确复现 9cbc 的 `bd_db.py` 和 `bd_orchestrator.py`，非过时单文件补丁。未应用现场更新。

The companion patch independently reconstructs both current files exactly from the two bound baseline blobs. No site update was applied. These artifacts are engineering/support bundles, not an authorized complete installer or updater.

## 范围限制 / Scope limitations

仅审核本轮 original-owner 相关路径，实际文件及 Git blob SHA256 列于 JSON。基线差异内 process_backend 工程不在本报告范围。没有生产操作。未知锁持续 STOP_AND_PRESERVE；没有自动解锁或重放授权。真实完整 Windows 安装、SCM/ACL 成功及实际业务采集仍待独立现场验收。

Review scope and exact file hashes are in the JSON. Unrelated process_backend changes are excluded. No production operation occurred. Unknown locks remain fenced, with no automatic unlock/replay authority. Complete Windows installation, actual SCM/ACL success and business collection remain pending independent acceptance.
