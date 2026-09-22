# PHASE 4A.8E — Canonical fetcher state wiring / 标准 fetcher 状态接线

## Confirmed defect and fix / 已确认缺陷与修复

The canonical `run_linked_backlog(..., fetcher=None)` call previously let `run_staging_postprocess()` create a local `BrowserFallbackWebsiteFetcher`, then checked the original `None` reference. Its `last_site_automation_recovery_exhausted` state was therefore unavailable to the deferment decision.

标准 `run_linked_backlog(..., fetcher=None)` 调用此前让 `run_staging_postprocess()` 在内部创建局部 `BrowserFallbackWebsiteFetcher`，随后却检查原始的 `None` 引用。因此，`last_site_automation_recovery_exhausted` 状态无法传递到延后决策。

The only production-candidate source change is `discovery/discovery_service.py`: each linked-backlog invocation creates or reuses one `linked_fetcher`, passes that exact object into postprocess, then reads the same object’s exhaustion state. Caller-injected fetchers remain unchanged. No retry ceiling, terminal fact, V2/MX rule, city policy, DB schema, or other production source file changed.

唯一的生产候选源码修改是 `discovery/discovery_service.py`：每次 linked-backlog 调用创建或复用同一个 `linked_fetcher`，将该对象传入后处理，并读取同一对象的耗尽状态。调用方注入的 fetcher 行为保持不变。未新增重试上限、事实性终结结论、V2/MX 规则、城市策略、数据库 schema，也没有修改其他生产源码。

## Regression / 回归

- Canonical `fetcher=None` static access failure → eligible browser attempt → no qualifying same-party HTTP-success evidence now yields `automation_deferred=1`.
- 标准 `fetcher=None` 的静态访问失败 → 符合条件的浏览器尝试 → 无同主体 HTTP 成功证据，现在会得到 `automation_deferred=1`。
- The marker is persisted in `raw_payload_json.linked_backlog_retry.automation_terminal_outcome` as `access_unreachable`; a second canonical call selects zero rows.
- 标记写入既有 JSON 元数据；第二次标准调用不会再次选取该行。
- The lead remains empty-email, `manual_review_needed`, and `email_verified_on_official_site=0`.
- 线索仍无邮箱、保持 `manual_review_needed`，且 `email_verified_on_official_site=0`。
- Existing evidence-success, transient/static-only, and explicitly injected-fetcher regressions remain covered.
- 既有的证据成功、暂态/仅静态失败、显式注入 fetcher 回归仍被覆盖。

## Fresh production-copy canonical replay / 新鲜生产副本标准重放

Safety / 安全：a fresh SQLite online backup from the post-4A.5D production DB passed `PRAGMA integrity_check=ok`. The replay called only `run_linked_backlog(city, resolver, max_results=20)` with no fetcher argument. All fixed rows already had websites, so the resolver was guarded against Maps use; only public official-site requests occurred. Production writes, SMTP, IMAP, Inventory, FSP/auth creation, and scheduler changes were all zero. No replay-owned Playwright/Chromium process remained after completion.

使用 post-4A.5D 生产数据库建立新鲜 SQLite online backup，`PRAGMA integrity_check=ok`。重放仅调用 `run_linked_backlog(city, resolver, max_results=20)`，未传入 fetcher。固定队列均已有官网，resolver 被保护为不触发 Maps；只访问公开官网。生产写入、SMTP、IMAP、Inventory、FSP/授权创建和调度变更均为 0；结束后没有本次重放遗留的 Playwright/Chromium 进程。

| Metric / 指标 | Result / 结果 |
| --- | --- |
| LINKED_RETRY_BEFORE | 11 |
| AUTOMATION_DEFERRED | 10 |
| LINKED_RETRY_AFTER | 1 (`362`) |
| EMAILS_CREATED | 0 |
| EVIDENCE_CREATED | 0 |
| SAFE_GAIN | 0 |
| City completion checks / 城市完成检查 | 5/9 true |
| Ithaca status / Ithaca 状态 | `active` |
| Next city / 下一城市 | none / 无 |

`discovery_id=362` is the single legitimate remaining automatic retry. Its official site `http://www.sciencenter.org` produced static HTTP 400. Existing fallback policy deliberately does not classify HTTP 400 as an allowed access/transport failure, so browser fallback was not attempted and the required static-plus-browser exhaustion proof is absent. It was not forced into `access_unreachable`, `no_public_email`, or any factual terminal state.

`discovery_id=362` 是唯一合法保留的自动重试。其官网 `http://www.sciencenter.org` 的静态响应为 HTTP 400。既有回退策略刻意不将 HTTP 400 视为允许的访问/传输失败，因此没有尝试浏览器回退，也就缺少“静态+浏览器恢复均耗尽”的必要证明。该记录未被强制写为 `access_unreachable`、`no_public_email` 或任何事实性终结状态。

Consequently city advancement remains correctly fail-closed; no code or policy was weakened to force Ithaca to advance.

因此城市推进继续正确地失败关闭；没有为了强制推进 Ithaca 而弱化任何代码或策略。

## Tests and decision / 测试与决策

- Targeted regression: 47 passed, 0 failed, 0 errors.
- 定向回归：47 项通过，失败 0，错误 0。
- Full project unittest: 409 passed, 0 failed, 0 errors.
- 完整项目 unittest：409 项通过，失败 0，错误 0。
- Frozen files changed: 0 / 冻结文件变更：0。

`CANONICAL_FETCHER_WIRING_FIXED = true`. `READY_FOR_PRODUCTION_REVIEW = true` for this narrow wiring patch only. City advancement is not yet achieved on the current copy because the honest HTTP-400 row remains actual automatic work. This report does not authorize deployment.

`CANONICAL_FETCHER_WIRING_FIXED = true`。该窄接线补丁 `READY_FOR_PRODUCTION_REVIEW = true`。由于真实 HTTP-400 行仍是实际自动工作，当前副本尚未实现城市推进。本报告不授权部署。
