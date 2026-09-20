# PHASE 4A.7 — City Queue Automatic Advancement Wiring / 城市队列自动推进接线

## Scope / 范围

中文：仅在开发仓库接入既有 `retail_city_queue.complete_if_exhausted()`、`outreach_control.all_city_completion_conditions_met()` 与 `activate_next_city()`。未修改 Lead Factory 补全、V2、MX、模板、发送器或任何生产资源。

English: Development-only wiring of the existing `retail_city_queue.complete_if_exhausted()`, `outreach_control.all_city_completion_conditions_met()`, and `activate_next_city()` assets. No Lead Factory enrichment, V2, MX, template, sender, or production resource was changed.

## Root cause / 根因

中文：标准 Inventory 原先直接调用 `activate_next_city()`，没有先将已满足真实完成条件的活动城市终结；本轮完成最后一个积压项后也没有再次检查。因此 `places_matrix_completed_web_pending` 会被重新设为 `active`，并长期占用队列。

English: Canonical Inventory previously called `activate_next_city()` directly. It neither terminalized an active city that had already met genuine completion conditions before work began, nor rechecked after the final backlog item completed. Consequently, `places_matrix_completed_web_pending` could be reactivated and keep the queue pinned.

## Implementation / 实现

| File / 文件 | Change / 变更 |
| --- | --- |
| `retail_city_queue.py` | Added a read-only, fail-closed `city_completion_checks()` evaluator and `complete_active_city_if_exhausted()` wrapper. It requires the complete query matrix, a durable web-directory completion/reason, and no pending staging, retryable network, or linked-backlog retry rows. `complete_if_exhausted()` now accurately uses `rowcount` and may terminalize the documented holding state only after every condition passes. / 新增只读、失败关闭的完成检查与活动城市终结包装器；要求完整查询矩阵、持久化目录完成原因，以及不存在待处理 staging、可重试网络或已关联积压重试。终结函数改用准确的 `rowcount`，仅在全部条件通过后才可终结文档定义的 holding 状态。 |
| `bd_orchestrator.py` | Runs the existing completion path immediately before city activation and after normal discovery/website/staging/linked-backlog work. The next standard Inventory selects the next pending city through the existing queue. / 在激活城市前及常规发现、官网、staging、已关联积压处理后运行既有完成路径；下一次标准 Inventory 通过既有队列选择下一待处理城市。 |
| `tests/test_phase4a7_city_queue_advancement.py` | Added seven regressions. / 新增七项回归测试。 |

No schema, table, provider, lead, email, evidence, V2, or MX mutation was added. / 未新增 schema、表、provider，也未新增 lead、邮箱、证据、V2 或 MX 写入。

## Acceptance evidence / 验收证据

| Required behavior / 要求行为 | Result / 结果 |
| --- | --- |
| Productive active city remains active / 仍有产出的活动城市保持活动 | PASS — incomplete query matrix retains Ithaca. / 通过——未完成查询矩阵时 Ithaca 保持活动。 |
| Pending query family blocks completion / 待处理查询族阻止完成 | PASS |
| Retryable network row blocks completion / 可重试网络记录阻止完成 | PASS |
| Unprocessed staging row blocks completion / 未处理 staging 记录阻止完成 | PASS |
| Linked backlog retry blocks completion / 已关联积压重试阻止完成 | PASS — lead row is asserted unchanged. / 通过——同时断言 lead 行未变化。 |
| Genuinely exhausted city terminalizes / 真正耗尽城市终结 | PASS — `search_matrix_exhausted`. |
| Next priority NY city activates / 下一优先级纽约城市激活 | PASS — Ithaca → Saratoga Springs. |
| No manual lead/email/evidence/V2 mutation / 不手工修改 lead/邮箱/证据/V2 | PASS — completion check reads staging/lead state and only updates queue terminal state. / 通过——完成检查仅读取 staging/lead 状态，仅更新队列终结状态。 |
| Full suite / 完整测试套件 | PASS — 354 passed, 0 failed, 0 errors. |

Targeted city regression: 23 passed, 0 failed, 0 errors. / 城市定向回归：23 项通过，失败与错误均为 0。

## Safety / 安全

| Metric / 指标 | Result / 结果 |
| --- | --- |
| Production deployment / 生产部署 | 0 / not performed / 未执行 |
| Production DB writes / 生产数据库写入 | 0 |
| Production files changed / 生产文件变更 | 0 |
| SMTP / IMAP | 0 / 0 |
| Inventory against production / 针对生产的 Inventory | 0 |
| V2 policy changed / V2 策略变更 | false |
| MX policy changed / MX 策略变更 | false |

## Decision / 决策

中文：开发验证通过。Ithaca 在仍有未完成查询、可重试网络、staging 或 linked backlog 工作时绝不会自动推进；只有既有完成语义全部满足后，城市才终结，并在下一次标准 Inventory 激活 Saratoga Springs。等待独立的生产评审和明确部署授权。

English: Development validation passes. Ithaca cannot auto-advance while unfinished queries, retryable network work, staging work, or linked-backlog work remains. Only after all existing completion semantics pass is the city terminalized; the next canonical Inventory then activates Saratoga Springs. Await separate production review and explicit deployment authorization.
