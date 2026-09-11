# Phase 4A.1C — UTF-8 Discovery 演练 / UTF-8 Discovery rehearsal

## 结论 / Decision

在精确提交 `7013b335ad4b1eec33cd559825ece7d5aaead70c` 上，以 `python -X utf8 -I -` 执行了一次且仅一次标准 Inventory。`sys.flags.utf8_mode=1`，标准输出为 `utf-8`；先前 GBK 无法输出 U+274C 的失败已消除。新 Discovery provider 正常完成，故本次受控 provider 演练通过。 / Exactly one canonical Inventory was run at commit `7013b335ad4b1eec33cd559825ece7d5aaead70c` using `python -X utf8 -I -`. `sys.flags.utf8_mode=1` and stdout was `utf-8`; the previous GBK failure on U+274C was eliminated. The new Discovery provider completed normally, so the controlled provider rehearsal passes.

`PROVIDER_STATUS=paused_by_runtime_limit` 表示按配置处理一页后仍有下一页游标，是正常的有界暂停，不是 provider error；`PROVIDER_ERROR` 为空。 / `PROVIDER_STATUS=paused_by_runtime_limit` means the configured one-page bound was reached while a next-page cursor remained. It is a normal bounded pause, not a provider error; `PROVIDER_ERROR` is empty.

DISCOVERY_PROVIDER_REHEARSAL_PASS = true

READY_FOR_CONTROLLED_PRODUCTION_PATCH = true

此就绪结论仅表示两文件受控生产补丁可进入明确批准流程；不等于已部署，也不授权恢复调度。 / This readiness conclusion only permits the two-file controlled production patch to proceed to explicit approval; it does not mean deployment occurred or authorize scheduler resume.

## 固定代码与数据库副本 / Frozen code and database copy

- 运行前 HEAD 精确匹配指定提交，Git 工作区干净；业务代码、provider、V2/MX 与证据逻辑均未修改。 / Before the run, HEAD exactly matched the requested commit and the Git worktree was clean; business code, provider, V2/MX and evidence logic were unchanged.
- 使用 SQLite `mode=ro` 在线备份到新的开发目录；`PRAGMA integrity_check=ok`，生产数据库备份前后 SHA256 一致。 / A fresh development copy was made through SQLite online backup with the source opened in `mode=ro`; `PRAGMA integrity_check=ok` and the production database SHA256 was identical before and after backup.
- 所有 Inventory 写入仅发生在开发副本。运行标识：`phase4a1c-utf8-dev-20260911T025255Z`。 / All Inventory writes occurred only in the development copy. Run ID: `phase4a1c-utf8-dev-20260911T025255Z`.

## Discovery 与下游结果 / Discovery and downstream results

| 指标 / Metric | 结果 / Result |
|---|---:|
| UTF8_MODE_CONFIRMED | true |
| UTF8_ENCODING_ERROR | false |
| PROVIDER_INVOCATION_COUNT | 1 |
| RAW_LIST_RESULTS_SEEN | 18 |
| DETAIL_RESULTS_PARSED | 18 |
| DISCOVERY_RESULTS_SEEN | 18 |
| NEW_UNIQUE_PLACES | 10 |
| PROVIDER_STATUS | paused_by_runtime_limit |
| PROVIDER_ERROR | empty / 空 |
| NEW_DISCOVERY_PATH_EXECUTED | true |
| WEBSITE_RESOLUTION_PROCESSED | 2 |
| NORMAL_STAGING_POSTPROCESS_PROCESSED | 6 |
| LINKED_BACKLOG_PATH_EXECUTED | true |
| LINKED_BACKLOG_ELIGIBLE / PROCESSED | 20 / 20 |
| NEW_VISIBLE_FIRST_PARTY_EMAILS | 1 |
| NEW_FULL_EVIDENCE_RECORDS | 2 |
| READ_ONLY_V2_SAFE_BEFORE / AFTER | 1 / 3 |
| BROAD_READY（运行前 / before） | 34 |
| MATERIALIZED_FSP_PLANNED | 0 |

Discovery 18 条中，10 条为新的唯一地点、8 条重复；分类为网站待查 2、邮箱提取待处理 4、活动城市外 1、拒绝 3。正常后处理建立 4 条 lead，但 SAFE 只由冻结 V2/MX 诚实判定，最终从 1 墕至 3，目标仍未达到，作业为 `partial/safe_inventory_gap`。 / Of 18 Discovery results, 10 were new unique places and eight duplicates; classifications were two website-lookup pending, four email-extraction pending, one outside the active city and three rejected. Normal postprocess created four leads, but SAFE remained governed honestly by frozen V2/MX and increased only from 1 to 3. The target was not met and the job remained `partial/safe_inventory_gap`.

积压阶段有一条 Google Maps 请求出现真实 `ERR_NETWORK_CHANGED`，但它发生在新 Discovery 已正常完成之后，且没有形成编码错误或绕过安全规则。 / One linked-backlog Google Maps request encountered a genuine `ERR_NETWORK_CHANGED`, after new Discovery had already completed normally. It caused neither an encoding error nor a safety bypass.

## 安全与回归 / Safety and regression

LEGACY_SCANNER_USED_AS_SAFE_AUTHORITY = false

SMTP = 0

IMAP = 0

MATERIALIZED_FSP_CREATED = 0

AUTHORIZATION_CREATED = 0

PRODUCTION_FILES_CHANGED = 0

PRODUCTION_DB_WRITES = 0

SCHEDULER_CHANGES = 0

FROZEN_FILES_CHANGED = 0

CODE_CHANGED_DURING_REHEARSAL = false

受保护的发送、退信、抑制、FSP、授权及授权明细表内容哈希保持不变；原有未关联 lead 保持不变。完整测试为 328 项及 76 项子测试通过，失败与错误均为 0。 / Content hashes of protected send, bounce, suppression, FSP, authorization and authorization-entry tables remained unchanged, as did all pre-existing unlinked leads. The full suite passed 328 tests and 76 subtests with zero failures and errors.

机器可读原始结果见 `PHASE4A1C_UTF8_REHEARSAL_RESULT.json`。 / The machine-readable raw result is in `PHASE4A1C_UTF8_REHEARSAL_RESULT.json`.
