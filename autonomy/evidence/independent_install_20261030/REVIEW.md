# 独立审核 / Independent review

结论 / Verdict: **APPROVED_DESIGN_ONLY**

固定源码与设计提交 / Pinned source and design commit: `57bccd47e1b9be19945a57b153ada45ca949c2f1`.

中文：审核者为独立子代理 independent_install_review，未参与被审三文件编写。阅读独立安装设计、离线plan消费者和测试，并对照现有 disabled_host_package.py、Install-DisabledHost.ps1、Rollback-DisabledHost.ps1。该方案可作为用户允许的“独立安装路径设计”交付；它没有修复旧发布器，也没有完成可安装的新执行器。原脚本尚缺原Inventory实时租约验证、持久安装日志和原子首次发布，不能凭本审核执行。

English: An independent child reviewer, independent_install_review, did not author the three reviewed files. Review covered the design, offline plan consumer and tests, compared with the existing package builder and install/rollback scripts. The proposal is acceptable as the user's alternative independent-installation-path design. It neither repairs the legacy publisher nor completes an installable executor. Existing scripts still lack live Inventory-lease enforcement, durable installation journaling and atomic first publication; this review cannot authorize their execution.

## 验证 / Validation

独立执行 / Independently executed:

`python -X utf8 -B -m unittest test_independent_install_plan test_disabled_host_package`

结果 / Result: **11 tests passed, 0.710 seconds**. 没有执行管理员脚本、SCM变更、ACL变更或生产操作。 / No administrator script, SCM mutation, ACL mutation or production operation was executed.

中文：消费者仅返回计划数据；所有返回路径拒绝install/dispatch，恢复动作只允许“审阅撤销注册”，不自动重放或删除。严格True门禁拒绝未知值和整数替代。测试覆盖缺席前态、错误身份/指纹、五个阶段的保全分类和运行中/缺失租约拒绝。阶段循环是策略测试，不是真实持久恢复、崩溃注入或Windows安装测试。

English: The consumer returns plan data only. Every returned path denies installation/dispatch; recovery permits only review of registration rollback, never replay or deletion. Strict-True gates reject unknown values and integer substitutes. Tests cover absent preconditions, incorrect identity/fingerprints, preservation at five named stages, and running/missing-lease rejection. Enumerating stages is policy testing, not durable recovery, crash injection or Windows installation testing.

## 设计边界 / Design boundaries

中文：首次安装和新增类型由精确批准的新包及专用缺席目录承载；旧发布器白名单保持原样。回滚选择是撤销Disabled服务注册并保留全部代码、状态和审计，不是删除回滚，也不恢复安装前磁盘完全缺席；文档明确披露此取舍。删除代码、升级既有目录、开启服务、切换执行权均未批准。维护租约必须与唯一Inventory原排他锁绑定，安装互斥不能替代；未知副作用保全并只读对账，禁止恢复旧数据库覆盖新历史。生产入口继续禁用。

English: First installation and new file types are carried by an exact approved separate package into absent dedicated roots, without widening the old whitelist. Rollback removes only a Disabled service registration and retains all code, state and audit. It is neither deletion rollback nor restoration of original disk absence; this tradeoff is explicitly disclosed. Code deletion, existing-directory upgrades, service start and authority transfer are excluded. The maintenance lease must bind to the original unique Inventory exclusion lock; an installer mutex cannot replace it. Preserve unknown effects and reconcile read-only; never overwrite new history with an old database. Production remains disabled.

## 固定审阅字节 / Reviewed byte fingerprints

| File | SHA-256 |
|---|---|
| autonomy/independent_install_plan.py | 0b1ccf06b4d8db524dffd83807abfc3c9f53715712ce96f4cf8e92eaa64cc22f |
| test_independent_install_plan.py | ba301c90c5b69233535992a336ce3b9c2c786508f210f2836236e109940bf6ad |
| DESIGN.md | 91b9c0c305d2f42e057cb74894d696cfd8a23b368ca544d9454f3ea9f84f3180 |

中文：摘要针对本次工作树字节；Git换行转换后若字节不同须重新封签，不能混用包SHA。本次不宣称当前候选NO_NEW_REGRESSION、RELEASE_READY或生产验收。

English: Hashes identify the reviewed working-tree bytes. Git newline conversion requires resealing if bytes change; do not confuse source/package fingerprints. This review makes no current-candidate NO_NEW_REGRESSION, RELEASE_READY or production-acceptance claim.
