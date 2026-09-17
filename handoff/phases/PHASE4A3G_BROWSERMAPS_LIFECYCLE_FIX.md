# Phase 4A.3G BrowserMaps child lifecycle diagnosis and fix / BrowserMaps 子进程生命周期诊断与修复

## Effective timeout truth / 实际超时值

`WEBSITE_RESOLUTION_TIMEOUT_SECONDS_ENV_PRESENT = false`; `WEBSITE_RESOLUTION_TIMEOUT_SECONDS_ENV_VALUE = <unset>`; `RESOLVER_TIMEOUT_SECONDS_EFFECTIVE = 45.0`。Production and development non-secret environment inspection both found no override. / 生产与开发的非敏感环境检查均未发现覆盖值。

## One-attempt production-parity diagnosis / 单次生产等价诊断

One legitimate retryable merchant was selected from a fresh online SQLite backup of the authoritative production database: `DISCOVERY_ID = 283`, `LEAD_ID = 1080`. The resolver used `BrowserMapsProvider` in `direct` mode, with Playwright/Chromium available and the production-equivalent scraper proxy route `127.0.0.1:3213`. No credential was recorded. / 从权威生产数据库的新鲜 online SQLite 备份中选择了一条合法可重试商户记录。resolver 使用 `direct` 模式的 `BrowserMapsProvider`；Playwright/Chromium 可用，并复现生产抓取代理路由；未记录凭据。

| Instrument / 观测点 | UTC timestamp / UTC 时间 |
| --- | --- |
| `PARENT_START` | `2026-09-17T07:49:57.480310+00:00` |
| `PROCESS_START_RETURNED` | `2026-09-17T07:49:57.524384+00:00` |
| `JOIN_START` | `2026-09-17T07:49:57.525022+00:00` |
| `JOIN_RETURNED` | `2026-09-17T07:50:42.526587+00:00` |
| `TERMINATE_CALLED` | `2026-09-17T07:50:42.542178+00:00` |
| `TERMINATE_RETURNED` | `2026-09-17T07:50:42.542943+00:00` |
| `POST_TERMINATE_JOIN_RETURNED` | `2026-09-17T07:50:42.552324+00:00` |
| `RESOLVE_RETURNED` | `2026-09-17T07:50:42.566640+00:00` |

`PARENT_PID = 55764`; `CHILD_PID = 40600`. `IS_ALIVE_AFTER_JOIN = true`; `DIRECT_CHILD_ALIVE_AT_TIMEOUT = true`; `DESCENDANTS_ALIVE_AT_TIMEOUT = true`. The direct Python child terminated after `terminate()`, but one `node.exe` Playwright driver and six `chrome-headless-shell.exe` descendants remained alive. / Python 子进程在 `terminate()` 后结束，但一个 Playwright `node.exe` driver 与六个 Chromium 后代仍然存活。

`DIRECT_CHILD_ALIVE_AFTER_TERMINATE = false`; `DESCENDANTS_ALIVE_AFTER_TERMINATE = true` under the pre-fix path.

`TIMEOUT_ROOT_CAUSE = PLAYWRIGHT_DESCENDANT_PROCESS_TREE`. `process.join(timeout)` returned normally and the 45-second timeout was effective; the failure was not an environment override or a parent-join stall. / `process.join(timeout)` 正常返回且 45 秒超时生效；失败不是环境覆盖或父进程 join 卡死。

## Narrow fix / 窄修复

Only [discovery/website_resolver.py](../../discovery/website_resolver.py) changed in production scope. On Windows, each resolver-owned Python child is assigned to a `KILL_ON_JOB_CLOSE` Job Object immediately after it starts. Closing the Job Object in the resolver's `finally` block terminates its Playwright driver and Chromium descendants whether the resolver completes or times out. Non-Windows behavior remains unchanged. / 生产范围仅修改 `discovery/website_resolver.py`。Windows 上，每个 resolver 所有的 Python 子进程启动后立即被分配到带 `KILL_ON_JOB_CLOSE` 的 Job Object；resolver 的 `finally` 关闭该 Job Object，无论正常完成或超时，都会结束其 Playwright driver 与 Chromium 后代。非 Windows 行为不变。

Timeout results remain `network_retry`; they are never converted to `website_not_found` or `no_public_email`.

## Acceptance / 验收

| Test / 测试 | Result / 结果 |
| --- | --- |
| Forced hanging provider / 强制挂起 Provider | Passed; returns in under 3 seconds with a 0.3-second configured deadline / 通过；0.3 秒时限下 3 秒内返回 |
| Sequential leads / 连续两条线索 | Passed; first timeout returns `network_retry`, second starts and returns `not_found` / 通过；第一条超时返回 `network_retry`，第二条实际启动并返回 `not_found` |
| BrowserMaps direct real single attempt / BrowserMaps direct 单次真实尝试 | Passed; `resolve()` returned `network_retry` at `45037ms` and parent control returned / 通过；`resolve()` 在 `45037ms` 返回 `network_retry`，父进程恢复控制 |
| Orphan process check / 孤儿进程检查 | Passed; `ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0`; `ORPHAN_CHROMIUM_PROCESS_COUNT = 0` after Job Object close / 通过；关闭 Job Object 后 Playwright 与 Chromium 孤儿进程数均为 0 |

`TIMEOUT_RETURNS_CONTROL = true`; `NEXT_LEAD_AFTER_TIMEOUT_RUNS = true`。

`TARGETED_TESTS = 2 passed`; `FINAL_FULL_SUITE = 341 passed, 76 subtests passed`; `FAILED = 0`; `ERRORS = 0`。

`V2_POLICY_CHANGED = false`; `MX_POLICY_CHANGED = false`; `PRODUCTION_DB_WRITES = 0`; `REAL_SMTP_CONNECTIONS = 0`; `REAL_IMAP_CONNECTIONS = 0`; `FULL_INVENTORY_RERUN = false`。

`READY_FOR_FINAL_THROUGHPUT_REHEARSAL = true`. This is not production deployment authorization. / 这不构成生产部署授权。
