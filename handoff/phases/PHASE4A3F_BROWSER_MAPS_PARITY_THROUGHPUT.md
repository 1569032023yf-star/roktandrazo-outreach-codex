# Phase 4A.3F BrowserMaps production-parity throughput acceptance / BrowserMaps 生产等价吞吐验收

## Scope and parity / 范围与等价性

The rehearsal used a fresh online SQLite backup of the authoritative production database into the development workspace. `PRAGMA integrity_check = ok`. It used only `DISCOVERY_PROVIDER=browser_maps` and `BROWSER_MAPS_MODE=direct`; Google Places was not loaded or used. / 本次演练通过 SQLite online backup 将权威生产数据库复制到开发工作区，且 `PRAGMA integrity_check = ok`。仅使用 `DISCOVERY_PROVIDER=browser_maps` 与 `BROWSER_MAPS_MODE=direct`；未加载或使用 Google Places。

`PROVIDER_CLASS = BrowserMapsProvider`; `PROVIDER_MODE = direct`; `PLAYWRIGHT_IMPORTABLE = true`; `CHROMIUM_AVAILABLE = true`。

`SCRAPER_PROXY_PRESENT = true`; `SCRAPER_PROXY_ROUTE = 127.0.0.1:3213`。Only the host and port are recorded; no proxy credential was emitted or stored in this report. / 仅记录主机和端口；本报告未输出或保存代理凭据。

## Result / 结果

The one permitted canonical Inventory rehearsal did not complete. Its BrowserMaps website-resolution child process remained alive for more than eight minutes, despite the resolver's configured finite per-attempt timeout. The development-only rehearsal process was stopped after its exact command line was verified. No second Inventory was run. / 唯一获准的标准 Inventory 演练未完成。尽管 resolver 配置了有限的单次时限，其 BrowserMaps 网站解析子进程仍存活超过八分钟。核验精确命令行后，已停止仅开发环境的演练进程；未运行第二次 Inventory。

The fresh copy remains integrity-valid after the controlled stop. No completed per-attempt telemetry or post-run SAFE measurement exists, so values below are explicitly `NOT_RUN`, not zero. / 受控停止后，新鲜副本仍通过完整性检查。未生成完成的逐条尝试遥测或运行后 SAFE 测量，因此下列值明确为 `NOT_RUN`，而非零。

| Field / 字段 | Value / 值 |
| --- | --- |
| `TOTAL_ATTEMPTS` | `NOT_RUN` |
| `RESOLVED` | `NOT_RUN` |
| `WEBSITE_NOT_FOUND` | `NOT_RUN` |
| `NETWORK_RETRY_TIMEOUT` | `NOT_RUN` |
| `NETWORK_RETRY_OTHER` | `NOT_RUN` |
| `TIMEOUTS` | `NOT_RUN` |
| `P50_MS` / `P95_MS` / `MAX_MS` | `NOT_RUN` |
| `TIMEOUT_STALLS_WHOLE_BATCH` | `NOT_PROVEN`; the observed child-process hang prevented continuation / 未证实；观察到的子进程挂起阻止后续处理 |
| `RETRYABLE_TOTAL` / existing-site reuse fields | `NOT_RUN` |
| Maps, evidence, linkage, timezone/history, MX and frozen V2 counts | `NOT_RUN` |
| `V2_SAFE_BEFORE` / `V2_SAFE_AFTER` / `NEW_SAFE_UNIQUE_ORGS` | `NOT_RUN` |
| `FSP_40_SIMULATION_PASS` / `FSP_40_UNIQUE_ORGS` | `NOT_RUN` |

## Safety / 安全

`REAL_SMTP_CONNECTIONS = 0`; `REAL_IMAP_CONNECTIONS = 0`; `PRODUCTION_DB_WRITES = 0`; `PRODUCTION_FILES_CHANGED = 0`; `PRODUCTION_FSP_OR_AUTH_CREATED = 0`; `V2_POLICY_CHANGED = false`; `MX_POLICY_CHANGED = false`; `GOOGLE_PLACES_USED = false`。

## Decision / 决策

`REAL_BOTTLENECK = BROWSERMAPS_PROCESS_LIFECYCLE_TIMEOUT_ENFORCEMENT`. The existing measurement does not prove that a failed or slow BrowserMaps resolution allows the next lead to proceed. This is a specific production-parity execution blocker, not a yield, V2, MX, evidence, or Google API configuration conclusion. / `REAL_BOTTLENECK = BROWSERMAPS_PROCESS_LIFECYCLE_TIMEOUT_ENFORCEMENT`。现有测量无法证明慢或失败的 BrowserMaps 解析后会继续处理下一条线索。这是具体的生产等价执行阻塞，不是产量、V2、MX、证据或 Google API 配置结论。

`LEAD_FACTORY_THROUGHPUT_PROVEN = false`; `READY_FOR_CONTROLLED_PRODUCTION_PATCH = false`。
