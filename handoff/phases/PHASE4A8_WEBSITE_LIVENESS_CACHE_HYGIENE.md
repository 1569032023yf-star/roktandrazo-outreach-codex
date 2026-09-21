# PHASE 4A.8 — 官网解析活性与 BrowserMaps 缓存卫生 / Website-resolution Liveness and BrowserMaps Cache Hygiene

## 范围与安全 / Scope and safety

本阶段仅修改 `discovery/discovery_service.py`、`discovery/providers/browser_maps.py` 与测试。未修改城市完成规则、V2、MX、模板、sender、数据库 schema、表或 provider。没有生产部署、生产 Inventory、生产数据库写入、SMTP、IMAP、授权或调度变更。

This phase changes only `discovery/discovery_service.py`, `discovery/providers/browser_maps.py`, and tests. It does not change city-completion rules, V2, MX, templates, sender, database schema, tables, or providers. There was no production deployment, production Inventory, production database write, SMTP, IMAP, authorization, or scheduler change.

PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
PRODUCTION_INVENTORY_RUNS = 0
SMTP = 0
IMAP = 0
SCHEDULER_CHANGES = 0
FROZEN_FILES_CHANGED = 0

## 缺陷 1：官网未找到的活性 / Defect 1: website-not-found liveness

原行为仅在 resolver 返回 `not_found` 时写入 `rejection_reason`，使记录永久保留为 `website_lookup_pending` 并被每次 canonical Inventory 重新选择。

The prior behavior wrote only `rejection_reason` when the resolver returned `not_found`, leaving the row forever in `website_lookup_pending` and selected by every canonical Inventory.

修正为：`resolver.status == "not_found"` 会持久化既有终态 `website_not_found`，同时保留 `website_resolution:not_found:...` provenance。`network_retry`、`network_error` 和 timeout 不改变状态，继续可重试且失败关闭。linked-backlog 仍使用既有 `_linked_backlog_terminal_outcome` / `_terminalize_linked_backlog` 终结路径。

The correction persists the existing terminal status `website_not_found` for `resolver.status == "not_found"` while preserving `website_resolution:not_found:...` provenance. `network_retry`, `network_error`, and timeout do not change status; they remain retryable and fail closed. Linked backlog continues to use the existing `_linked_backlog_terminal_outcome` / `_terminalize_linked_backlog` path.

NOT_FOUND_BECOMES_TERMINAL = true
NOT_FOUND_NOT_RESELECTED = true
NETWORK_RETRY_REMAINS_RETRYABLE = true
LINKED_NOT_FOUND_USES_EXISTING_TERMINAL_PATH = true

## 缺陷 2：BrowserMaps 缓存文件名卫生 / Defect 2: BrowserMaps cache filename hygiene

缓存键现会移除控制字符与 Unicode 私有区 glyph、折叠 CR/LF 和重复空白、替换 Windows 非法文件名字符，并保留既有小写、确定性与长度/hash fallback。BrowserMaps 缓存加载与 direct 结果在新的 typed text 字段进入 Discovery 前也会执行相同文本清理；身份评分及 V2/MX/模板/发送语义均未改变。

The cache key now removes control characters and Unicode private-use glyphs, collapses CR/LF and repeated whitespace, replaces Windows-invalid filename characters, and retains the existing lowercase, deterministic, and length/hash fallback behavior. BrowserMaps cached and direct typed text fields are sanitized before entering Discovery; identity scoring and V2/MX/template/send semantics are unchanged.

PRIVATE_USE_GLYPH_CACHE_SAFE = true
NEWLINE_CACHE_SAFE = true
WINDOWS_INVALID_FILENAME_CHARS_SAFE = true

## 生产副本重放 / Production-copy replay

从生产 SQLite 建立新的 read-only online-backup 开发副本，`PRAGMA integrity_check = ok`。重放写入只发生在副本事务中，并已 rollback。

A fresh development copy was created with a read-only production SQLite online backup; `PRAGMA integrity_check = ok`. Replay writes occurred only inside copy transactions and were rolled back.

| 指标 / Metric | 结果 / Result |
|---|---:|
| 重放前 open staged pending / before | 8 |
| 重放前 retryable network / before | 1 |
| 原始城市推进 / original city advancement | blocked |
| 既有真正 `not_found` 行 / genuine existing not-found rows | 7 |
| 已终结为 `website_not_found` / terminalized | 7 |
| 受污染行 / poisoned row | discovery_id 374 |
| BrowserMaps 页面状态 / BrowserMaps page status | `ok` |
| BrowserMaps 结果数 / result count | 1 |
| 页面中的官方官网数 / official website count | 0 |
| 受污染行真实结果 / real outcome | `website_not_found` |

`discovery_id=374` 的历史 `formatted_address` 和 `phone` 含私有区 Maps UI glyph 与换行。修复后，BrowserMaps 可使用清理后的缓存键得到实际 `ok` provider 页面；页面唯一结果没有官网，因此按照既有 resolver 语义得到真实 `not_found`，没有 `OSError [Errno 22] Invalid argument`。

Historical `formatted_address` and `phone` for `discovery_id=374` contain private-use Maps UI glyphs and newlines. After the fix, BrowserMaps obtains a real `ok` provider page via the sanitized cache key; its sole result has no website, so the existing resolver semantics produce genuine `not_found`, with no `OSError [Errno 22] Invalid argument`.

EXISTING_POISONED_ROW_QUERY_NO_OSERROR = true

## 如实限制与当前阻塞 / Truthful limitation and current blocker

在 8 条 website pending 被处理后，城市完成检查的查询耗尽和来源门槛通过，但仍有 12 条独立、既有的 linked-backlog 重试记录：1 条 `manual_review_needed` 与 11 条 `review_recovery`。它们不是本阶段 `not_found` 活性缺陷造成的假 pending，继续按既有失败关闭语义阻止城市推进。

After the eight website-pending rows are processed, the city checks for query exhaustion and source completion pass, but 12 independent existing linked-backlog retries remain: one `manual_review_needed` and 11 `review_recovery`. They are not false pending caused by this phase's `not_found` liveness defect and continue to block city advancement under existing fail-closed semantics.

尝试在副本上调用有界 canonical linked-backlog lane 时，一个已验证为隔离开发 replay 的 Python 进程持续持有 SQLite 副本锁；该非生产进程已终止以阻止额外网站访问，事务自动回滚。没有为了得到 ALL TRUE 而修改 `retail_city_queue.py` 或终结真实 retry。

When attempting the bounded canonical linked-backlog lane on the copy, a verified isolated-development replay Python process retained the SQLite-copy lock; that non-production process was terminated to stop additional site access and the transaction rolled back automatically. `retail_city_queue.py` was not changed and genuine retries were not terminalized merely to obtain ALL TRUE.

CITY_ADVANCEMENT_AFTER_REPLAY = blocked
CURRENT_BLOCKER = 12 independent legitimate linked-backlog retries require separate controlled bounded validation

## 测试 / Tests

定向测试覆盖：非 linked `not_found` 转终态且不会被官网解析/后处理重选；network retry 可重试；linked `not_found` 使用既有终结路径；私有区 glyph、换行和 Windows 非法字符产生有效确定性缓存路径；缓存结果文本在使用前被清理。

Targeted tests cover: non-linked `not_found` terminalization and non-reselection by resolution/postprocess; retryability of network retry; linked `not_found` through the existing terminal path; valid deterministic cache paths for private-use glyphs, newlines, and Windows-invalid characters; and cached result-text cleanup before use.

TARGETED_TESTS = 13 passed; 0 failed; 0 errors
FULL_PROJECT_UNITTEST = 362 passed; 0 failed; 0 errors

## 决定 / Decision

PHASE4A8_CODE_FIX_VALIDATED = true
READY_FOR_PRODUCTION = false

下一步：评审仅含两个允许生产源文件的窄补丁，并在另行明确授权后，对 12 条剩余 linked-backlog 重试执行有界受控验证。停止；不得部署、恢复调度、运行生产 Inventory 或发送。

Next: review the narrow patch containing only the two allowed production source files, then under separate explicit authorization run bounded controlled validation of the 12 remaining linked-backlog retries. Stop; do not deploy, resume scheduling, run production Inventory, or send.
