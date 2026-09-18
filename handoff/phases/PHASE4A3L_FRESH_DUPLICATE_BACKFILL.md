# Phase 4A.3L — Fresh BrowserMaps duplicate-backfill acceptance / 新鲜 BrowserMaps 重复回填验收

## Scope and safety / 范围与安全

- Started from `c0061917897ab3eb63efab5d2b02bf6ce40dab7a`; no production source file changed. / 从指定提交开始；没有修改任何生产源码文件。
- A SQLite online backup created a development-quarantine copy from the authoritative production DB. `PRAGMA integrity_check = ok`. / 通过 SQLite 在线备份从权威生产数据库创建开发隔离副本，完整性检查为 `ok`。
- Production DB writes, SMTP, IMAP, production FSP, production authorization, deployment, and scheduler changes were all zero. / 生产数据库写入、SMTP、IMAP、生产 FSP、生产授权、部署和调度变更均为零。

## Runtime parity / 运行时等价性

- `PROVIDER_CLASS = BrowserMapsProvider`; `PROVIDER_MODE = direct`; Playwright and Chromium were available. / 提供方类别为 BrowserMapsProvider，模式为 direct；Playwright 和 Chromium 均可用。
- The configured scraper route was present as `127.0.0.1:3213`; credentials were neither displayed nor recorded. / 配置的抓取代理路由为 `127.0.0.1:3213`；未显示或记录任何凭据。
- The deliberately bounded call was one active Ithaca, NY query family (`game store`), one page, `page_size=5`, on the copy only. / 受限调用仅针对副本中的 Ithaca, NY 活跃查询族（`game store`），一页，`page_size=5`。

## Measured result / 实测结果

- `PROVIDER_RESULTS_RETURNED = 0`; `NEW_UNIQUE = 0`; `DUPLICATES = 0`. / 提供方返回0条，新增唯一地点0，重复项0。
- `FRESH_PROVIDER_FACTS_OBTAINED = false`. The browser process never started: the development safety process guard allows an in-root virtual-environment Playwright Node driver but blocks the installed global Playwright Node driver. / 未取得新鲜提供方事实。浏览器进程未能启动：开发安全进程护栏只允许开发根目录虚拟环境中的 Playwright Node 驱动，却阻止了当前已安装的全局 Playwright Node 驱动。
- First, the transport guard correctly denied external transport before the explicit controlled-web flag. With the allowed controlled-web flag, the stricter process guard blocked the driver before browser navigation or any external request. / 首先，在显式受控 Web 标志前，传输护栏正确阻止了外部传输。启用获准的受控 Web 标志后，更严格的进程护栏在浏览器导航或任何外部请求之前阻止了驱动程序。
- Thus there are no incoming provider facts, no duplicate match, no real backfill, no postprocess, no official-email/evidence output, and no V2/MX recomputation to claim. / 因此没有传入提供方事实、没有重复匹配、没有真实回填、没有后处理、没有官网邮箱或证据产出，也没有可声称的 V2/MX 重算。

## Decision / 决策

- `DUPLICATE_BACKFILL_REAL_WORLD_PROVEN = false`. The Phase 4A.3K implementation remains code-and-test proven, but this fresh-provider measurement is blocked before provider fact collection. / Phase 4A.3K 实现仍已由代码和测试证明，但本次新鲜提供方测量在收集提供方事实前受阻。
- `REAL_BLOCKER = OTHER: DEVELOPMENT_SAFETY_PLAYWRIGHT_DRIVER_SUBPROCESS_ALLOWLIST_MISMATCH`. / 真实阻塞为 OTHER：开发安全 Playwright 驱动子进程允许名单不匹配。
- Per Phase 4A.3L, no source change was made to bypass this newly proven blocker. `READY_FOR_FINAL_INVENTORY_REHEARSAL = false`. / 按照 Phase 4A.3L，未为绕过这个新证实的阻塞而修改源码；尚未准备好最终 Inventory 演练。
