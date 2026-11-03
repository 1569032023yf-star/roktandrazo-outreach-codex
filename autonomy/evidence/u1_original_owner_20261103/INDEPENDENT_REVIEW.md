# 原 Inventory 排他独立审核 / Independent original Inventory exclusion review

结论：`OFFLINE_SCOPED_REVIEW_PASSED`。固定源码 `4b0353cbc4a5c69998fdd597d2bb884f7f5da8d0`，审核基线 `cc6434e1fdff68c0069a5cd9a85fe22c4b9d994d`。本范围无未解决阻断；`RELEASE_READY=false`，所有生产门禁保持 false。

Conclusion: scoped offline review passed for the pinned source above. No unresolved blocker in the reviewed scope. This is not release, deployment, installation or production acceptance approval.

## 审核与发现闭环 / Review and finding closure

审核原 `bd_db.acquire_run_lock`、实际 `bd_orchestrator.stage_inventory` 的调用位置、事务及 finally，以及维护与 Publisher 准入。三个入口在各自同一 `BEGIN IMMEDIATE` 内调用共享只读 `inventory_lock_blocked`：精确 Inventory 前缀、忽略 `_acquired_at` 元数据、仅精确字符串 `released` 放行。NULL、空、异常、大小写不同、BLOB 和数值均封锁。跨日期不再通过 stale 时间抢占；非 Inventory 原空值/stale 合同保留。

Reviewed the actual owner call sites, transaction boundaries and finally behavior together with maintenance and Publisher admission. All three consult the same predicate inside their existing immediate transaction. Only exact string `released` admits; metadata keys are excluded. Cross-date Inventory locks cannot be stolen by age; non-Inventory behavior remains unchanged.

旧 68ec 候选的 P1 空值分歧已独立重现：原 owner 拒绝、maintenance 却准入。新 4b 的六值三入口探针确认修复。实际 stage 的 `BaseException` 路径保留锁；普通异常和 SystemExit 都拒绝下一日期重入，已知正常返回释放。未知业务结果没有被测试通过或进程退出自动解释为成功。

The former empty-value admission inconsistency was independently reproduced on 68ec and is closed on 4b. Actual stage BaseException handling preserves the lock; both ordinary exceptions and SystemExit block next-day admission, while known returns release it. Process exit is not interpreted as successful business completion.

## 独立验证 / Independent validation

- 新固定源码独跑 68 项，72.890 秒，0 failure / 0 error：`python -m unittest test_inventory_maintenance test_publisher_maintenance test_publisher_install_maintenance tests.test_phase4a8r_continuous_discovery tests.test_phase4a8s_production_patch -q`。
- 六种异常值 × 三准入均拒绝且只保留原行；精确 released 加异常时间元数据仍允许。
- 八个真实独立子进程争用不同日期，仅一个获锁；所有进程退出后，即使 stale 阈值为 -1 仍不重入。
- 从实际源码 AST 加载 stage、接真实原 SQLite acquire/release：Exception/SystemExit 保留 holder；known-return 释放。业务回调仍是隔离替身。

68 tests passed independently on the new pin (72.890 seconds). Additional probes cover the six-value matrix, eight real competing processes, and actual stage AST coupled to original SQLite lock functions. Discovery/provider callbacks remain test doubles. Earlier candidate runs are diagnostic only and are not counted for this pin.

## 产物核对 / Artifact verification

新版工程包 71 文件；两 ZIP SHA、逐 ZIP entry 字节、manifest 摘要和所有 payload 摘要一致；PE machine 为 AMD64 `0x8664`。新版 support 17 文件逐一匹配固定 Git blob、manifest、ZIP 摘要；独立临时解压后使用 Python `-I -B` 完成 import-only，无加载配置/凭据/监听/数据库。摘要详见 `INDEPENDENT_PACKAGE_RESULT.json`。

The 71-file engineering package and both archives were verified byte-for-byte against manifests; the executable is AMD64. All 17 support payloads match pinned Git blobs. Fresh isolated import-only execution passed without configuration, credentials, listener or database access.

companion patch SHA `4a4f12e70ea96a82850b53472dfd50af455b57fae395a08d200862239c0d9e7e`：对绑定的 `3bbb77d7f2cce774b3addfdbf851342ad09393c5` 两份严格 baseline Git blob 纯内存应用 diff，精确复现 4b 的 `bd_db.py` 和 `bd_orchestrator.py`，非过时单文件补丁。未应用现场更新。

The companion patch independently reconstructs both current files exactly from the two bound baseline blobs. No site update was applied. These artifacts are engineering/support bundles, not an authorized complete installer or updater.

## 范围限制 / Scope limitations

仅审核本轮 original-owner 相关路径，实际文件及 Git blob SHA256 列于 JSON。基线差异内 process_backend 工程不在本报告范围。没有生产操作。未知锁持续 STOP_AND_PRESERVE；没有自动解锁或重放授权。真实完整 Windows 安装、SCM/ACL 成功及实际业务采集仍待独立现场验收。

Review scope and exact file hashes are in the JSON. Unrelated process_backend changes are excluded. No production operation occurred. Unknown locks remain fenced, with no automatic unlock/replay authority. Complete Windows installation, actual SCM/ACL success and business collection remain pending independent acceptance.

## 测试合同更新复审 / Test contract update review

新固定源码产品四文件与9cbc逐字节相同，新增差异为测试及精确字节属性。两个当前 stage 异常预期改为不释放，符合业务副作用可能已经提交后的未知结果；历史 phase4a8s 用独立不可变夹具，未再把当前演进源码当作历史 AFTER。该夹具逐字节等于 cc6434e:bd_orchestrator.py，SHA256 为 e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903，与原 verifier.AFTER_SHA256 相同，未转换换行。历史 provider 异常与 invalid-budget 的释放断言仍在历史 patched 副本执行。未发现通过删除负例、改生产摘要或放宽产品门禁掩盖回归。

The four product files are byte-identical to 9cbc. Current exception expectations correctly preserve locks after potentially committed effects. Historical phase4a8s now uses an immutable exact-source fixture, equal to the pinned cc643 Git blob and the original verifier AFTER hash without newline normalization. Historical exception and invalid-budget release assertions remain on the historical patched copy. No negative contract, production fingerprint or product gate was weakened.

上述68项、新pin三入口异常矩阵、八真实进程竞争、实际stage+SQLite以及fixed-package/fixed-support核验均在4b上独立重新执行；9cbc与未固定工作树结果仅诊断，不计入新pin成绩。完整全量基线对比由主代理另行记录，本报告不将局部通过称为全量all-green。

All 68 tests and the additional admission, process, stage and fixed-artifact probes were rerun on 4b. Earlier 9cbc and working-tree runs are diagnostic only. Full baseline regression comparison is separately recorded by the main agent; this scoped pass does not assert an all-green full suite.
