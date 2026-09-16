# Phase 4A.3 / 第4A.3阶段：Lead Factory 零产出

## Findings / 结论

`ROOT_CAUSE_ZERO_YIELD = true`：已关联积压的合法终态没有推进，且 Maps cursor 重复页仅被计数、未完成查询。 / Legitimate linked-backlog outcomes were not advanced, and repeated Maps cursor pages were counted but did not complete the query.

Ithaca 的 `game store` 状态为 cursor `8`、240 seen、208 duplicates、23 consecutive empty pages；因此每次仍激活同一查询。18 条可重试积压中，11 条为 website not found、4 条为 no-public-email 类终态。 / Ithaca `game store` was cursor `8`, 240 seen, 208 duplicates, and 23 consecutive empty pages; the same query was reactivated. Of 18 retry-eligible backlog rows, 11 were website-not-found and 4 were no-public-email-type terminal outcomes.

## Narrow fix / 窄修复

Production patch scope is two files: `discovery/discovery_service.py` and `outreach_control.py`.

生产补丁仅两文件：`discovery/discovery_service.py` 和 `outreach_control.py`。

- 两个连续无新增页面后完成当前 query family；网络/provider 错误仍保留 checkpoint 并可重试。 / Complete the current query family after two consecutive no-new-place pages; retain checkpoints and retry for network/provider errors.
- 将 `website_not_found` 和 `no_public_email` 写入既有 `validation_status`，并保留 retry provenance；终态不再进入 linked backlog。 / Persist `website_not_found` and `no_public_email` in the existing `validation_status`, retaining retry provenance; terminal rows no longer enter linked backlog.
- weekday SAFE inventory target defaults to `NEW_OUTREACH_TARGET + 10 = 50`, configurable through `SAFE_INVENTORY_TARGET`; send quota remains frozen at 40. / Weekday SAFE inventory defaults to 50, configurable through `SAFE_INVENTORY_TARGET`; send quota stays frozen at 40.

## Validation / 验证

Production DB read-only copy integrity was `ok`. A bounded real linked-backlog run started with 18 rows and terminalized 3 `no_public_email` rows. On identical-pass selection, `PASS2_REPROCESSED_TERMINAL = 0`; remaining retryable rows = 15. The run was safely terminated when real website resolution exceeded the controlled time limit; no second Inventory was run.

生产库只读副本完整性为 `ok`。一次有界真实积压运行从18条开始，终态化3条 `no_public_email`；相同第二次选择中终态重处理为0，剩余可重试15条。真实网站解析超过受控时限后安全停止；未运行第二次 Inventory。

`TARGETED_TESTS = 20 passed + 17 subtests`。此前全套回归为 `337 passed + 76 subtests`，其中两项仅因 30→50 的已批准库存目标而失败，已修正为配置化断言；需要在提交前重新运行全套。

`TARGETED_TESTS = 20 passed + 17 subtests`. The prior full suite was `337 passed + 76 subtests`; two failures were stale assertions of the approved 30→50 inventory target and were corrected to configuration-aware assertions; the full suite must be rerun before commit.

`V2_POLICY_CHANGED = false`; `MX_POLICY_CHANGED = false`; `FSP_40_SIMULATION_PASS = not_run (SAFE < 40)`; `READY_FOR_CONTROLLED_PRODUCTION_PATCH = false`.
