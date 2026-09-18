# Phase 4A.3M — Development Playwright driver allowlist and 4A.3L rerun / 开发 Playwright 驱动允许名单与 4A.3L 重跑

## Development-only safety repair / 仅开发环境安全修复

- `PYTHON_EXECUTABLE = C:\Users\15690\AppData\Local\Programs\Python\Python313\python.exe`. / 当前 Python 解释器如上。
- `PLAYWRIGHT_PACKAGE_PATH = ...\Python313\Lib\site-packages\playwright`; its `driver\node.exe` exists and is inside the active interpreter's installed Playwright package. / Playwright 包位于当前解释器的 site-packages；其 `driver\node.exe` 存在且处于当前解释器安装的 Playwright 包内。
- `development_safety.py` now resolves the active interpreter's `playwright` package using import resolution and permits only `node.exe` below its legitimate `driver` tree when `ROKT_DEV_CONTROLLED_WEB=1`. It keeps the safe-CWD check, production-DB block, SMTP/IMAP blocks, and every other subprocess restriction. / `development_safety.py` 现在使用导入解析定位当前解释器的 `playwright` 包，仅在 `ROKT_DEV_CONTROLLED_WEB=1` 时允许其合法 `driver` 树内的 `node.exe`；安全工作目录检查、生产数据库阻止、SMTP/IMAP 阻止和所有其他子进程限制均保留。
- Targeted regression: `9 passed`. It proves active-environment driver allowance is flag-gated; arbitrary Node and non-Playwright global executables remain blocked; SMTP, IMAP, production DB paths, and safe-Python behavior remain fail-closed/unchanged. / 定向回归9项通过，证明活跃环境驱动的允许由标志控制；任意 Node 和非 Playwright 全局可执行文件仍被阻止；SMTP、IMAP、生产数据库路径以及安全 Python 行为保持原有限制。

## Exact bounded fresh-provider rerun / 精确有界新鲜提供方重跑

- Fresh authoritative-production SQLite copy: `PRAGMA integrity_check = ok`; production remained read-only. / 从权威生产库创建新鲜 SQLite 副本，完整性检查为 `ok`；生产库保持只读。
- Runtime: `BrowserMapsProvider`, `direct`, Ithaca NY, `game store`, `page_size=5`, `max_pages=1`; cache reads and writes were disabled so facts were fresh. / 运行时为 BrowserMapsProvider direct、Ithaca NY、`game store`、`page_size=5`、`max_pages=1`；禁用缓存读写以确保事实新鲜。
- `PROVIDER_RESULTS_RETURNED = 5`; `NEW_UNIQUE = 0`; `DUPLICATES = 5`. All five duplicates carried a legitimate non-Google website and an exact Google Maps Place source URL. / 提供方返回5条，新增唯一地点0，重复5条；全部5条重复项都携带合法非 Google 官网和精确 Google Maps Place 来源 URL。
- `WEBSITE_BACKFILLED = 1` and `SOURCE_URL_BACKFILLED = 0`; `NONEMPTY_WEBSITE_OVERWRITTEN = 0`; `NONEMPTY_SOURCE_URL_OVERWRITTEN = 0`. The one empty website was filled only by the real `_upsert_result` path. / 官网回填1条、来源 URL 回填0条；未覆盖任何非空官网或来源 URL。唯一空官网仅通过真实 `_upsert_result` 路径回填。

## Downstream result and decision / 下游结果与决策

- The exact backfilled record had no official visible email or full evidence after the existing postprocess attempt. Frozen V2 evaluated that linked no-email lead as ineligible; MX was not needed for a no-email lead. / 回填记录在既有后处理尝试后没有官方可见邮箱或完整证据。冻结 V2 将该关联的无邮箱线索判为不合格；无邮箱线索无需 MX。
- `OFFICIAL_EMAILS_FOUND = 0`; `FULL_EVIDENCE_CREATED = 0`; no FSP, authorization, SMTP, IMAP, deployment, scheduler change, or production write occurred. / 官方邮箱发现0、完整证据创建0；未发生 FSP、授权、SMTP、IMAP、部署、调度变更或生产写入。
- `FRESH_PROVIDER_FACTS_OBTAINED = true`; `DUPLICATE_BACKFILL_REAL_WORLD_PROVEN = true`; `READY_FOR_FINAL_INVENTORY_REHEARSAL = true`. This proves the narrow duplicate-backfill path, not downstream email yield. / 已取得新鲜提供方事实，真实世界重复回填已证明，已准备进行最终 Inventory 演练。这证明的是窄范围重复回填路径，而非下游邮箱产出。

## Regression and scope / 回归与范围

- Full suite: `350 passed, 76 subtests passed`, `0 failed`, `0 errors`. / 完整套件350项及76子测试通过，失败和错误均为0。
- Production source files changed: `0`. Development-only files changed: `development_safety.py` and `tests/test_phase4a3m_dev_playwright_allowlist.py`. / 生产源码变更0；仅开发文件 `development_safety.py` 与对应测试发生变更。
