# PHASE 4A.8U 城市超时恢复 / City timeout recovery

工程修复和最小候选包已提交并推送。正式通道未登记新 release_id，生产部署未执行，生产效果未验收。
The engineering fix and minimal candidate package were committed and pushed. The new release ID is not registered; production was not deployed and production effectiveness is unverified.

## 交付状态 / Delivery status

```text
FIX_IMPLEMENTED = true
TARGETED_TESTS = {"run": 13, "passed": 13, "failures": 0, "errors": 0}
NEW_REGRESSIONS = 0
PRODUCTION_DEPLOYED = false
PRODUCTION_EFFECTIVENESS_VERIFIED = false
COOPERSTOWN_FAMILIES = "UNKNOWN"
CITY_COMPLETION_CHECKS = "UNKNOWN"
COOPERSTOWN_CLOSED = "UNKNOWN"
LAKE_PLACID_ACTIVATED = "UNKNOWN"
PROVIDER_REQUESTS_NEXT_CITY = "UNKNOWN"
NEW_INDEPENDENT_ORGS = "UNKNOWN"
NEW_FIRST_PARTY_EMAILS = "UNKNOWN"
CURRENT_SAFE = "UNKNOWN"
INVENTORY_ACTIVE = true
EMAILS_SENT_BY_THIS_TASK = 0
SMTP_ENABLED = 0
COMMIT_SHA = "6e5a9916fd3cd974479b3e2bc5340f831ea12978"
PUSH_SUCCESS = true
```

`COMMIT_SHA` 指实现与候选包提交；本报告另行提交。`PUSH_SUCCESS` 已通过远端分支 SHA 匹配核实。
`COMMIT_SHA` identifies the implementation/package commit; this report is committed separately. `PUSH_SUCCESS` was verified by matching the remote branch SHA.

## 修复 / Fix

官网解析最多三次网络失败，每次间隔至少 30 分钟，重启后从 staging JSON 恢复计数、时间和错误历史。耗尽后保留人工复核状态，完整终态证据才能解除这条记录对城市自动收尾的阻塞。其他待处理任务及未完成分页继续 fail-closed。
Website resolution permits at most three network failures, at least 30 minutes apart. Counts, timestamps and error history survive service restarts in staging JSON. Exhaustion retains manual review; only complete terminal evidence removes this item from automatic city-completion work. Other unfinished work and pagination remain fail-closed.

重复 Provider 命中不会清除重试状态。超时和连接故障可按预算收敛；程序错误及本地依赖缺失不被伪装成网络终态。没有新增迁移，没有改客户资格、MX、历史、发送门禁、查询 cursor 或三页预算。
Duplicate provider hits retain retry state. Timeouts and connection failures can exhaust the budget; programming errors and missing local dependencies are not treated as network terminal outcomes. No migration was added; qualification, MX, history, send gates, query cursors and the three-page budget were unchanged.

## 测试与复核 / Tests and review

- 定向 / Targeted: 13/13 PASS。
- 基线完整测试 / Full baseline: 505 tests, 3 failed, 1 error.
- 候选完整测试 / Full candidate: 515 tests, 3 failed, 1 error.
- 新增回归 / New regressions: 0。完整测试并非全绿 / The full suite is not entirely green.
- 同一 Python 3.13、相同 `python -c` 启动、相同无凭据开发配置；基线为固定提交的独立归档。/ Same Python 3.13, `python -c` startup, credential-free development configuration, and a separately archived pinned baseline.
- 10 项新增测试覆盖重试、冷却、持久化、恢复、异常、重复命中、防饥饿、linked backlog、终态真实性和真实未完成工作。另修正三个旧测试的即时重试假设，未删除测试。/ Ten new tests cover retry bounds, cooldown, persistence, recovery, exceptions, duplicate hits, starvation, linked backlog, terminal evidence and unfinished work. Three existing immediate-retry assumptions were updated; no tests were deleted.

现存基线失败与错误 ID / Existing baseline failure and error IDs:

- `test_dashboard_consolidated.TestSourceAudit.test_archived_dashboards_have_disable_marker`
- `test_inventory_followup.TestInventoryArchival.test_archived_scripts_have_disable_marker`
- `test_phase4a3o_dev_db_routing.Phase4A3ODevDatabaseRoutingTests.test_explicit_development_copy_is_preserved_after_env_loader`
- `test_single_smtp_authority.TestSingleSmtpAuthority.test_archived_scripts_fail_closed`

三项归档相关检查中的失败/错误来自 Git 不包含的历史归档目录；开发数据库路径检查受 Windows 中文输出解码影响。基线与候选失败集合相同，本阶段未改写无关历史归档。
The archive-related failures/error come from historical directories absent from Git; the development-database path check is affected by Windows Chinese-output decoding. Baseline and candidate failure sets match. Unrelated historical archives were not rewritten.

单独代码复核发现并修复了重复命中覆盖重试记录，以及过宽异常捕获的问题。完成作者自检，不声称已取得独立第三方批准。正向补丁和反向回滚均逐字节通过；Git 传输补丁 SHA 已核对，补丁禁用换行自动转换。
A separate author review found and fixed retry-history loss on duplicate hits and overly broad exception handling. Author review is complete; independent third-party approval is not claimed. Forward and reverse patches passed exact-byte checks; the Git-transport patch SHA was verified and automatic newline conversion disabled.

离线数据库夹具得到 20/20、9/9、Cooperstown 关闭、Lake Placid 激活。这些仅是测试结果，不是生产观测值。
Offline database fixtures reached 20/20, 9/9, Cooperstown closure and Lake Placid activation. These are test results, not production observations.

## 实时通道证据 / Live channel evidence

2026-10-20 09:03 +08 只读检查：通道在线、生产模式、新 release 返回 `400 UNKNOWN_RELEASE_ID`。原 SAFE50 文件 SHA 仍为 `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903`；其旧 before-SHA 预检不匹配是已部署后的预期结果，没有重复 apply。
At 2026-10-20 09:03 +08, read-only checks showed the channel online in production mode and the new release returning `400 UNKNOWN_RELEASE_ID`. The deployed SAFE50 file still matched the SHA above. Its old before-SHA mismatch is expected after deployment; apply was not repeated.

SMTP=0，PreSend/Preflight/Outreach 均暂停；Inventory 标记 ACTIVE，运行锁健康且未持有。通道记录的下次计划时间为 `2026-10-20 01:52:42 +08`，已过期，安全窗口门禁未通过。没有手动触发 Inventory。
SMTP=0 and PreSend/Preflight/Outreach are paused. Inventory is marked ACTIVE; the run lock is healthy and unheld. The next-run timestamp shown above is overdue, so the safe-window gate failed. Inventory was not manually triggered.

用户报告的 SAFE=56 与 Cooperstown 20/20 保留为来源声明；本次未执行正式 MX 控制探针，不能把它们当最新实测。城市关闭、下一城市请求、组织和邮箱增长均保持 UNKNOWN。
The user-reported SAFE=56 and Cooperstown 20/20 remain attributed claims. No formal MX control probe was performed, so they are not current measurements. City closure, next-city requests, organization growth and first-party email growth remain UNKNOWN.

## 阻塞与接入 / Blockers and registration

登记申请 / Registration request: https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/2

- 正式通道返回 UNKNOWN_RELEASE_ID；需登记新的严格两文件发布，并提供批准的生产源码快照与 SHA。 / The formal channel returned UNKNOWN_RELEASE_ID; a new restricted two-file release and approved production snapshots/SHA values are required.
- 实时安全窗口未通过：Inventory 下次计划时间已过期，必须取得新的有效空闲窗口证据。 / The live safety-window gate failed because the next Inventory timestamp is overdue; fresh valid idle-window evidence is required.
- 指定的 2026-10-19 生产报告未取得；当前通道无运行日志读取操作，真实生产效果尚不能核验。 / The requested 2026-10-19 production report is unavailable; the channel exposes no runtime-log read operation, so production effectiveness remains unverified.

需由现有授权通道运维身份补齐批准源码指纹、严格两文件登记和有效安全窗口。Codex 未扩权、未直接调用受限生产执行器、未改生产数据库。登记申请不等于登记已完成。
The existing authorized channel operator must supply approved source fingerprints, a restricted two-file registration and a valid safety window. Codex did not expand permissions, directly invoke a restricted production executor, or modify the production database. A registration request is not completed registration.

接入后由 Codex 按候选包 README 的全文件预检、备份、锁内原子替换及完整回滚流程发布，再观察唯一正式 Inventory 的正常计划运行。运行证据取得前不宣称获客恢复。
Once connected, Codex will follow the package README for all-file preflight, backups, locked atomic replacements and complete rollback, then observe normal scheduled runs of the sole formal Inventory. Acquisition recovery will not be claimed before runtime evidence is available.
