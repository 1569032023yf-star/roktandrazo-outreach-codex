# 交接变更日志 / Handoff Changelog

## Phase 4A.3M development Playwright allowlist and fresh duplicate-backfill rerun / 开发 Playwright 允许名单与新鲜重复回填重跑 — 2026-09-18

- 仅修改开发安全护栏：动态解析当前 Python 安装的 Playwright driver 树，且只在 `ROKT_DEV_CONTROLLED_WEB=1` 时允许其中的 `node.exe`；任意 Node、其他全局程序、SMTP/IMAP 与生产数据库路径仍被拒绝。定向安全测试9项通过。/ Changed only the development safety guard: dynamically resolves the active Python Playwright driver tree and allows only its `node.exe` when `ROKT_DEV_CONTROLLED_WEB=1`; arbitrary Node, other global programs, SMTP/IMAP, and production DB paths remain blocked. Nine targeted safety tests passed.
- 同参数的一页 BrowserMaps direct 演练首次实际获得5条新鲜事实：全部为重复项，均含合法官网与精确 Place 来源；真实 `_upsert_result` 仅对1条空官网执行回填，未覆盖已有官网或来源。/ The same one-page BrowserMaps-direct rehearsal collected five fresh facts: all were duplicates with legitimate websites and exact Place sources; real `_upsert_result` backfilled only one empty website and never overwrote existing website or source fields.
- 该回填记录未产生官方可见邮箱或完整证据，冻结 V2 对其无邮箱关联 lead 诚实拒绝且无需 MX。完整套件350通过及76子测试、失败/错误均0；生产源变更、生产写入、SMTP、IMAP、部署和调度变更均为0。/ That backfilled record produced no visible official email or full evidence; frozen V2 honestly rejected its no-email linked lead and required no MX. The full suite passed 350 plus 76 subtests with zero failures/errors; production-source changes, production writes, SMTP, IMAP, deployment, and scheduler changes were all zero.

## Phase 4A.3L fresh BrowserMaps duplicate-backfill acceptance / 新鲜 BrowserMaps 重复回填验收 — 2026-09-18

- 在生产数据库的新鲜 SQLite 在线备份副本上，按受限范围调用一个 BrowserMaps direct 查询族的一页、最多5条；副本完整性为 `ok`。/ On a fresh SQLite online-backup copy of the production database, invoked one bounded BrowserMaps-direct query family for one page and at most five records; copy integrity was `ok`.
- 未返回提供方结果：开发安全传输护栏先正确阻止未启用受控 Web 的调用；启用获准的受控 Web 后，开发安全子进程护栏又在浏览器导航前阻止全局安装的 Playwright Node 驱动。/ No provider results returned: the development transport guard correctly stopped the call before controlled Web was enabled; after the allowed controlled-Web flag, the development subprocess guard stopped the globally installed Playwright Node driver before browser navigation.
- 未修改源码来绕过此新阻塞，未产生回填、后处理、证据或 V2/MX 重算；生产写入、SMTP、IMAP、生产 FSP/授权、部署和调度变更均为0。/ No source change bypassed this new blocker; no backfill, postprocess, evidence, or V2/MX recomputation occurred; production writes, SMTP, IMAP, production FSP/authorization, deployment, and scheduler changes were all zero.

## Phase 4A.3K duplicate discovery website/provenance backfill / 重复发现官网与来源回填 — 2026-09-18

- 修复 `_upsert_result()` 的重复更新数据丢失：仅对空 `website` 回填合法、非 Google 自有 BrowserMaps 官网；仅对空 `source_url` 回填精确 Google Maps Place URL；已有字段绝不覆盖，证据、历史、验证状态、V2 和 MX 均未改变。 / Fixed duplicate-update data loss in `_upsert_result()`: only an empty `website` can receive a legitimate non-Google BrowserMaps website and only an empty `source_url` can receive an exact Google Maps Place URL; existing fields are never overwritten, and evidence, history, validation status, V2, and MX remain unchanged.
- BrowserMaps 外链过滤现在拒绝 `google.com`、`google.cn`、区域 Google 域名以及已识别的 Google 重定向/内部主机；保留既有明确允许的 `sites.google.com` 与 `*.business.site`。 / BrowserMaps external-link filtering now rejects `google.com`, `google.cn`, regional Google domains, and identified Google redirect/internal hosts; the existing explicit `sites.google.com` and `*.business.site` allowances remain.
- 新鲜生产副本仅重放一个匹配缓存记录：其无官网且已有精确来源 URL，因此没有实际字段回填、后处理、直达详情或 V2/MX 重算。定向测试27项及9子测试通过；最终完整套件346项及76子测试通过，失败/错误均0。 / A fresh production copy replayed only one matching cache record: it had no website and an already-present exact source URL, so no actual field backfill, postprocess, direct-detail test, or V2/MX recomputation ran. Targeted tests passed 27 plus 9 subtests; the final full suite passed 346 plus 76 subtests with zero failures/errors.

## Phase 4A.3J existing Maps Place URL reuse diagnosis / 既有 Maps Place URL 复用诊断 — 2026-09-18

- 在新鲜 SQLite 在线备份副本上仅审计固定 11 条 4A.3H/4A.3I cohort 并直达其既有 Maps Place URL；未搜索 Maps、未运行完整 Inventory、未写生产库或生产文件，SMTP/IMAP 均为0。 / On a fresh SQLite online-backup copy, audited only the fixed eleven-row 4A.3H/4A.3I cohort and navigated only its stored Maps Place URL; no Maps search or full Inventory ran, no production database/file was written, and SMTP/IMAP were both zero.
- cohort 中仅1/11有精确 Google Maps Place URL，10/11为空；三个既有正样本控制项亦无可复用的发现来源 URL。唯一的直达详情页在9870ms加载，但返回 Google 所有的 `google.cn`，不接受为商户第一方官网。 / Only 1/11 cohort rows had an exact Google Maps Place URL and 10/11 were empty; the three existing positive controls also had no reusable discovery provenance URL. The sole direct detail page loaded in 9870ms but returned Google-owned `google.cn`, which is not accepted as a first-party merchant website.
- 因未得到合法官网解析或正样本匹配，直达详情快速路径未获证明，未修改源码或生产补丁范围。定向生命周期测试2项通过；完整套件341项及76子测试通过，失败/错误均0；浏览器残留进程为0。 / Because no legitimate official-site resolution or known-positive match was obtained, the direct-detail fast path is not proven; no source or production-patch file was changed. Two targeted lifecycle tests passed; the full suite passed 341 plus 76 subtests with zero failures/errors; browser residual processes were zero.

## Phase 4A.3I website-resolver yield diagnosis / 网站解析器产出诊断 — 2026-09-17

- 静态审计确认 resolver 固定传入候选限制10，BrowserMaps会逐一打开最多10个详情页；最坏情况下无法可靠地完成45秒 deadline。但三条已知正样本控制不支持将候选扇出断言为主根因。 / Static audit confirms that the resolver passes candidate limit 10 and BrowserMaps opens up to ten detail pages; this cannot reliably fit the 45-second deadline in the worst case. However, three known-positive controls do not support asserting candidate fan-out as the primary cause.
- limit 1/3/10 的完整预期域名成功数分别为0/3、0/3和1/3。11条原4A.3H cohort 在候选生成前全部成为network_retry：8次resolver deadline、1次页面导航超时、2次socket错误；解析成功、真实未找到官网和identity review均为0。 / Fully resolved expected-domain successes at limits 1/3/10 were 0/3, 0/3 and 1/3. All eleven original 4A.3H cohort cases became network retries before candidate collection: eight resolver deadlines, one page-navigation timeout and two socket errors; resolved, genuine no-website and identity-review counts were all zero.
- 未修改源码或生产文件；生命周期定向测试2通过，完整套件341通过及76子测试、失败/错误均0。BrowserMaps/Playwright专用残留进程为0。最终Inventory演练仍未获准。 / No source or production files changed; two targeted lifecycle tests passed and the full suite passed 341 plus 76 subtests with zero failures/errors. Dedicated BrowserMaps/Playwright residual processes were zero. The final Inventory rehearsal remains unapproved.

## Phase 4A.3H final production-copy throughput acceptance / 最终生产副本吞吐验收 — 2026-09-17

- 在新鲜 SQLite 在线备份副本上完成一次且仅一次 BrowserMaps direct 标准 Inventory；来源生产库只读，`integrity_check=ok`，生产写入、SMTP、IMAP、生产 FSP/授权和调度变更均为0。 / Completed exactly one BrowserMaps-direct canonical Inventory on a fresh SQLite online-backup copy; the production source was read-only, `integrity_check=ok`, and production writes, SMTP, IMAP, production FSP/authorization and scheduler changes were all zero.
- Maps 读取8条但新增唯一地点0；18条可重试 linked backlog 全部处理，11次官网解析中0成功、6次在约45秒有界超时、5次官网未找到，后续记录继续处理，9条终态化。 / Maps read eight results but added zero unique places; all 18 retryable linked-backlog rows were processed. Of 11 website resolutions, zero succeeded, six timed out at about 45 seconds and five found no website; later rows continued and nine were terminalized.
- 新可见第一方邮箱、完整证据、V2 eligible、只读 SAFE 与计划 FSP 增量均为0；低于40时未运行 FSP/授权模拟。生命周期守卫活跃，运行后专用 Playwright/BrowserMaps 进程为0。 / New visible first-party emails, full evidence, V2 eligible results, read-only SAFE and planned FSP growth were all zero; no FSP/authorization simulation ran below 40. The lifecycle guard was active, with zero dedicated Playwright/BrowserMaps processes after the run.
- 结论：吞吐未获证明，不能准备受控生产补丁；真实主阻塞为 `WEBSITE_RESOLUTION_LOW_SUCCESS`，而非 V2/MX、发送或孤儿进程。遥测 JSON 在运行完成后因本地集合序列化失败，p50/p95明确记录为未捕获；未重跑网络或 Inventory。 / Decision: throughput is not proven and the controlled production patch is not ready; the real blocker is `WEBSITE_RESOLUTION_LOW_SUCCESS`, not V2/MX, sending or process orphans. The telemetry JSON failed after completion because of a local set-serialization issue, so p50/p95 are explicitly not captured; no network or Inventory was rerun.

## Phase 4A.3G BrowserMaps child lifecycle narrow fix / BrowserMaps 子进程生命周期窄修复 — 2026-09-17

- 单次生产等价诊断确认有效超时为45秒，`join(timeout)` 正常返回且 Python 子进程可终止；根因是 Playwright Node 与 Chromium 后代在 Python 子进程终止后仍存活。 / A single production-parity diagnosis confirmed the effective timeout is 45 seconds, `join(timeout)` returns, and the Python child terminates; the root cause is surviving Playwright Node and Chromium descendants.
- 仅修改 `discovery/website_resolver.py`：Windows 子进程进入带 `KILL_ON_JOB_CLOSE` 的 Job Object，resolver 返回或超时时关闭 Job Object 并清理其后代。 / Changed only `discovery/website_resolver.py`: Windows children enter a `KILL_ON_JOB_CLOSE` Job Object, which is closed on resolver return or timeout to clean descendants.
- 强制超时、超时后下一条线索和 BrowserMaps direct 单次真实解析均通过；真实尝试在45037ms返回，Playwright/Chromium 孤儿均为0。完整套件341通过及76子测试，0失败、0错误；未重跑完整 Inventory、未部署。 / Forced timeout, next-lead-after-timeout, and one real BrowserMaps direct attempt passed; the real attempt returned at 45037ms with zero Playwright/Chromium orphans. The full suite passed 341 plus 76 subtests, with zero failures and errors; no full Inventory was rerun and nothing was deployed.

## Phase 4A.3F BrowserMaps production-parity throughput / BrowserMaps 生产等价吞吐 — 2026-09-17

- 使用 BrowserMaps direct、已安装的 Playwright/Chromium 和生产抓取代理路由，对新鲜生产数据库副本进行唯一一次受控标准 Inventory 演练；未使用 Google Places。 / Ran the one controlled canonical Inventory rehearsal on a fresh production database copy with BrowserMaps direct, installed Playwright/Chromium, and the production scraper-proxy route; Google Places was not used.
- BrowserMaps 网站解析子进程超过八分钟仍存活，未能遵守现有有限单次时限，因此受控停止开发演练；未运行第二次 Inventory，所有未完成的吞吐/Safe 指标均记录为 `NOT_RUN`。 / A BrowserMaps website-resolution child remained alive for more than eight minutes and did not honor the existing finite per-attempt limit, so the development rehearsal was stopped; no second Inventory was run and incomplete throughput/SAFE metrics are recorded as `NOT_RUN`.
- 未写生产数据库或文件，SMTP、IMAP、生产 FSP/授权均为 0；该子进程生命周期问题是下一项具体 blocker，尚未准备受控生产补丁。 / No production database or file writes occurred; SMTP, IMAP, production FSP, and authorization were all zero. The child-process lifecycle issue is the next specific blocker; the controlled production patch is not ready.

## Phase 4A.3C measured production-copy throughput / 生产副本吞吐实测 — 2026-09-17

- 发布既有的生产副本测量结果，未重新执行 Discovery 或联网演练。 / Published the existing production-copy measurement without rerunning discovery or the network rehearsal.
- 批处理护栏已证实：18 条可重试积压均被处理，11 次外部解析配置失败后均继续处理下一条线索。 / The batch guardrail is proven: all 18 retryable backlog rows were processed, and each of the 11 external-resolution configuration failures continued to the next lead.
- `GOOGLE_MAPS_API_KEY` 未配置，属于 Provider 配置阻塞，并非超时、DNS/TLS 或 V2/MX 策略失败；因此尚未具备受控生产补丁条件。 / `GOOGLE_MAPS_API_KEY` is not configured. This is a Provider configuration blocker—not a timeout, DNS/TLS, or V2/MX policy failure—so the controlled production patch is not ready.

## Phase 4A.3 Lead Factory zero-yield fix / Lead Factory零产出修复 — 2026-09-16

- 修复重复 Maps cursor 的两页无新增耗尽推进，并将已关联积压的无网站/无公开邮箱结果持久化为终态；发送、V2、MX与生产均未改变。 / Fixed two-empty-page Maps cursor progression and terminalized linked backlog no-website/no-public-email results; sending, V2, MX, and production were unchanged.
- 定向测试20项及17子测试通过。生产副本网站解析演练超时，未声称40 SAFE产量，未部署。 / Targeted tests passed 20 plus 17 subtests. Production-copy website resolution timed out; no 40-SAFE yield was claimed and nothing was deployed.

## Phase 4A.2 MX-only selective proxy narrow fix — 2026-09-16 / 仅MX选择性代理窄修复 — 2026-09-16

- 确认根因：MX Worker 请求使用默认 `urllib` opener，因而会继承进程级 `HTTP_PROXY`、`HTTPS_PROXY` 或 `ALL_PROXY`；该风险与非 MX HTTP 流量共享。 / Confirmed root cause: the MX Worker request used urllib's default opener and therefore inherited process-wide `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY`; the risk was shared with non-MX HTTP traffic.
- 仅修改 `preflight_gate.py`：`query_mx` 现使用本地 opener；仅当配置 `BD_MX_HTTPS_PROXY` 时将它用于该 HTTPS Worker 请求，否则用空 `ProxyHandler` 直接连接并忽略全局代理。 / Changed only `preflight_gate.py`: `query_mx` now uses a local opener; it applies `BD_MX_HTTPS_PROXY` only to that HTTPS Worker request, or uses an empty `ProxyHandler` for direct traffic that ignores global proxies.
- 未改变 V2/MX 状态语义、资格策略、授权、发送、数据库 schema 或调度。6项选择性路由测试与V2传输回归通过；全套为335通过及76子测试、0失败、0错误。 / V2/MX status semantics, eligibility policy, authorization, sending, database schema, and scheduling were unchanged. Six selective-routing tests and the V2 transport regression passed; the full suite reported 335 passed plus 76 subtests, with zero failures and errors.
- 使用三个公开域名完成一次受控网络演练，显式设置冲突全局代理；MX Worker 三项均正常且仅使用 MX 专用代理。SMTP、IMAP、生产文件/数据库写入均为0；未部署。 / Completed one controlled network rehearsal over three public domains with deliberately conflicting global proxies; all three MX Worker results were normal and only the MX-specific proxy was used. SMTP, IMAP, production file/database writes were zero; nothing was deployed.

## Phase 4A.1C UTF-8 rehearsal — 2026-09-11 / UTF-8 演练 — 2026-09-11

- 在精确提交 `7013b335ad4b1eec33cd559825ece7d5aaead70c` 上，以 `python -X utf8` 对新鲜生产数据库只读副本执行一次且仅一次标准 Inventory；代码未变。 / Ran exactly one canonical Inventory with `python -X utf8` on a fresh read-only-derived production database copy at exact commit `7013b335ad4b1eec33cd559825ece7d5aaead70c`; code was unchanged.
- UTF-8 标志和输出编码确认成功，先前 U+274C/GBK 错误消失；provider 正常解析18/18条详情，新增唯一地点10。 / UTF-8 mode and stdout encoding were confirmed, eliminating the prior U+274C/GBK error; the provider normally parsed 18/18 details and found 10 new unique places.
- 正常网站解析2、安全后处理6、积压20/20；新增可见第一方邮箱1、完整证据2，冻结V2 SAFE从1增至3。 / Normal website resolution processed two, safe postprocess six, and backlog 20/20; one visible first-party email and two full evidence records were added, with frozen-V2 SAFE increasing from 1 to 3.
- Provider 状态 `paused_by_runtime_limit` 是单页有界执行后的正常暂停，错误为空；UTF-8 provider 演练通过。 / Provider status `paused_by_runtime_limit` is the expected bounded pause after one page, with an empty error; the UTF-8 provider rehearsal passed.
- 生产文件/数据库、调度、SMTP、IMAP、FSP、授权和冻结文件变化均为0；未部署。 / Production files/database, scheduling, SMTP, IMAP, FSP, authorization and frozen-file changes were all zero; nothing was deployed.

## Phase 4A.1C — 2026-09-11

- 恢复标准 Inventory 的有界新 Discovery、网站解析、安全后处理，再执行已关联积压；SAFE 达标提前跳过补库，BroadReady 仅展示。 / Restored bounded new discovery, website resolution and safe postprocess before linked backlog; skip replenishment when SAFE meets target, with BroadReady informational only.
- 生产源仅两文件，新增正常通道 unlinked_only 过滤；保留 4A.1B 保护及166条未关联 lead 的延后范围。 / Only two production-source files; added normal-lane unlinked_only filtering while preserving 4A.1B safeguards and deferral of 166 unlinked leads.
- 328测试及76子测试通过，冻结文件变化0。一次新鲜副本演练两条路径均执行，积压18/18，SAFE 1→1，新增证据0。 / 328 tests and 76 subtests passed, with zero frozen changes. One fresh-copy run executed both lanes, processed 18/18 backlog rows, retained SAFE 1→1 and created zero new evidence.
- 新 Discovery 的 GBK 输出编码异常导致 scrape_error，并非证明无商户；未重复 Inventory，限制写入详细报告。 / New Discovery returned scrape_error due to GBK output encoding, not proof of absent merchants; Inventory was not repeated and the limitation is disclosed in the detailed report.
- 未部署、未写生产、未发送邮件、未创建FSP/授权、未改变调度；仅提交开发代码与双语交接。 / No deployment, production writes, mail, FSP/authorization creation or scheduler changes; only development code and bilingual handoff are committed.

## Repository initialization — 2026-09-09 / 仓库初始化 — 2026-09-09

### 中文

- 在 `roktandrazo-outreach-dev` 内创建独立 Git 根，分支设为 `main`。
- 唯一远端设为私有 Codex 开发仓库 `roktandrazo-outreach-codex`；未指向或修改 WorkBuddy 生产备份仓库。
- 扩充 `.gitignore`，排除环境文件、数据库及生产派生副本、凭据、令牌、密钥、备份树、缓存、日志、PID 和运行时制品。
- 将 Phase 2/3 的关键双语报告归档至 `handoff/phases/`，并按当前真实 blocker 更新状态文件。
- 本条记录不代表生产发布批准；生产文件写入、生产数据库写入和真实 SMTP 均为 0。

### English

- Created an independent Git root inside `roktandrazo-outreach-dev` with branch `main`.
- Configured the private Codex development repository `roktandrazo-outreach-codex` as the sole remote; the WorkBuddy production-backup repository was neither targeted nor modified.
- Expanded `.gitignore` to exclude environment files, databases and production-derived copies, credentials, tokens, keys, backup trees, caches, logs, PID files, and runtime artifacts.
- Archived the key bilingual Phase 2/3 reports under `handoff/phases/` and updated the status artifacts with the current verified blocker.
- This entry does not authorize production deployment; production-file writes, production-database writes, and real SMTP connections remain zero.

## Phase 3C-NET — 2026-09-09

### 中文

- 建立仅含六个获批制品的发布包，并在全新生产源码副本中完成精确应用排练；六个目标 SHA 全部匹配 Phase 3B manifest。
- 验证开发专用导入、开发 DB 路径、测试专用导入、`dev_safe_fsp` 与 `safe_replenishment` 引用均为 0。
- 重新运行全套测试：303/303 通过；并发、负向安全和幂等定向测试为 5 passed、3 subtests passed。
- 使用 SQLite 只读 online backup 创建生产 DB 演练副本，`PRAGMA integrity_check=ok`；未写生产数据库。
- 完成 20 个商户上限的联网 Inventory 演练：16 次逻辑 Google Maps 请求、8 次官网请求、6 个 fail-closed 网络错误。
- 创建 1 条完整第一方可见邮箱证据：`Instant Replay Sports` / `ithacainstantreplaysports@yahoo.com`。
- 确认 blocker：完整证据留在 `lead_discovery_results.id=293`，但 `linked_lead_id=NULL`；已有同身份 `leads.id=1085` 未被安全更新，所以 V2/MX/SAFE FSP 均为 0。
- 未部署；SMTP、IMAP、生产文件写入、调度器变更、冻结文件变更均为 0。

### English

- Built a release package containing only the six approved artifacts and rehearsed its exact application to a fresh production source copy; all six target hashes match the Phase 3B manifest.
- Verified zero development-safety imports, development DB paths, test-only imports, `dev_safe_fsp` references, and `safe_replenishment` references in the package.
- Re-ran the complete suite: 303/303 passed; targeted concurrency, negative-safety, and idempotency validation reported 5 passed plus 3 subtests.
- Created the production DB rehearsal copy through a read-only SQLite online backup with `PRAGMA integrity_check=ok`; the live DB was never written.
- Completed the capped 20-merchant networked Inventory rehearsal: 16 logical Google Maps requests, 8 official-site requests, and 6 fail-closed network errors.
- Created one complete visible first-party evidence record for `Instant Replay Sports` / `ithacainstantreplaysports@yahoo.com`.
- Confirmed the blocker: complete evidence remained in `lead_discovery_results.id=293` with `linked_lead_id=NULL`; existing same-identity `leads.id=1085` was not safely updated, leaving V2/MX/SAFE FSP at zero.
- No deployment occurred; SMTP, IMAP, production-file writes, scheduler changes, and frozen-file changes were all zero.
## Phase 3D — 2026-09-09

- 中文：复现并修复已有线索官方证据关联；新增 9 项回归，312 项测试及 59 子测试通过。新鲜生产 DB 开发副本中关联 1085，真实 MX/V2 通过，开发 SAFE FSP 新增 1，重放幂等。重新生成六制品发布包与最终 SHA 清单。生产与冻结文件未改，未部署。
- English: Reproduced and fixed existing-lead official-evidence linkage. Added nine regressions; 312 tests and 59 subtests pass. A fresh development production-DB copy linked lead 1085, passed real MX/frozen V2, and inserted one development SAFE FSP idempotently. Regenerated six release artifacts and final SHA manifest. No production/frozen changes or deployment.
## Phase 4A — 2026-09-09

- 中文：只读部署前检查发现 Windows 与 WorkBuddy 的 PreSend/Outreach 重复 active 触发器，按手册中止；尚未暂停调度、备份、部署或运行生产 Inventory。生产写入为 0，等待维护与恢复范围确认。
- English: Read-only pre-deployment checks found overlapping active Windows and WorkBuddy PreSend/Outreach triggers. Aborted per runbook before any hold, backup, deployment, or live Inventory. Zero production writes; awaiting maintenance/resume scope clarification.
## Phase 4A 后续授权 / Follow-up authorization

- 中文：WorkBuddy 四个主要阶段已 PAUSED；禁用重复 Windows 任务遭操作系统拒绝，复核仍启用 2/2。未部署，等待管理员禁用；不恢复调度。
- English: Four main WorkBuddy stages are PAUSED. OS denied disabling duplicate Windows tasks; both remain enabled. No deployment; awaiting administrator action, with no scheduler resume.
## Phase 4A — 2026-09-10 部署 / Deployment

- 中文：按批准 commit 部署六个制品，目标6/6、冻结0变更，已建最新在线回滚备份。唯一一次生产 Inventory 完成，官网+2、可见第一方邮箱/完整证据各+1，无新增 lead/schema/发送记录。验收后91域名MX被安全审查拒绝，SAFE AFTER待测；调度不恢复。
- English: Deployed six artifacts from the approved commit with 6/6 target hashes, zero frozen changes and fresh online rollback backup. One production Inventory completed: two websites and one visible first-party email/full evidence record; no new lead/schema/send records. Safety review blocked post-run 91-domain MX; SAFE AFTER remains pending. Scheduling stays held.
## Phase 4A 最终验收 / Final acceptance — 2026-09-10

- 中文：按新增明确授权完成一次MX/V2测量。91原始域名字符串归一为90唯一域名，MX正常32、NXDOMAIN51、无路由7、DNS错误0。V2/SAFE均1，1085通过；冻结0变更，邮件/计划/授权/调度变更均0。调度继续暂停。
- English: Completed one explicitly authorized MX/V2 measurement. 91 raw domain strings normalize to 90 unique domains: 32 OK, 51 NXDOMAIN, 7 no route, 0 DNS errors. V2/SAFE both equal one; lead 1085 passes. Zero frozen, mail, plan, authorization or scheduler changes. Scheduling remains held.
## Phase 4A.1 — 2026-09-10 审计停止 / Audit stop

- 中文：离线复现BroadReady34/30误完成。新鲜副本全量空邮箱482，排除51联系表单/3已发送后为428；其中166无staging关联。已关联262条状态亦非直接安全消费状态。按第7节停止，无源码或生产更改，未执行修复测试/Inventory；冻结SHA未变。
- English: Reproduced BroadReady34/30 false completion offline. Fresh copy has482 empty emails, or428 excluding51 contact-form/3 sent;166 lack linked staging. All262 linked rows also lack directly consumable safe statuses. Stopped under section7 without source/production changes or fix tests/Inventory; frozen hashes unchanged.

## Phase 4A.1B — 2026-09-10 已关联积压重连 / Linked backlog reconnection

- 中文：完成262条精确路由审计；仅修改两个生产源文件，加入当前城市有界安全重入和冻结V2唯一组织完成信号。166条未关联待补库不变。322项及76子测试通过；冻结0变更。首轮开发驱动位置被护栏拦截，换用开发驱动和新副本后真实复验18条：解析11、后处理7、新邮箱/完整证据/关联增量均0，SAFE 1→1，BroadReady34但正确记录partial、gap29。未部署、未恢复调度，生产写入/邮件/FSP/授权均0。窄补丁可审查，不表示库存目标达成。
- English: Completed exact routing audit of262 rows; changed only two production source files for bounded current-city safe re-entry and frozen-V2 unique-org completion. The166 actionable unlinked leads are unchanged.322 tests and76 subtests pass; frozen changes0. Initial external driver location was blocked by guards; a development driver and fresh copy then processed18 real rows:11 resolution,7 postprocess, zero new email/full-evidence/linkage, SAFE1→1. BroadReady34 correctly yields partial with gap29. No deployment/resume or production/mail/FSP/authorization writes. The narrow patch is review-ready, not inventory-target-complete.
## Phase 4A.3N — 2026-09-18 最终生产副本 Inventory 验收 / Final production-copy Inventory acceptance

- 中文：按明确授权建立新鲜生产 DB 只读 online-backup 副本，完整性检查为 `ok`，并仅发起一次标准 Inventory 调用。该调用约23分钟仍未进入 `stage_inventory()`，副本中不存在本次 `job_run`；已停止该唯一隔离进程，未重跑。故没有 Maps/官网/邮箱/证据/关联/V2/MX/FSP 指标可用。真实阻塞为开发调用/导入的预阶段停滞；未部署，生产写入、SMTP、IMAP、FSP、授权、调度及冻结文件变化均为0。
- English: Under explicit authorization, created a fresh read-only online-backup copy of the production DB with `ok` integrity and started exactly one canonical Inventory invocation. After about 23 minutes it had not entered `stage_inventory()` and the copy contained no run record; that sole isolated process was stopped and not rerun. Consequently no Maps/site/email/evidence/linkage/V2/MX/FSP metrics exist. The real blocker is a pre-stage development invocation/import stall; no deployment, production write, SMTP, IMAP, FSP, authorization, scheduler, or frozen-file change occurred.
## Phase 4A.3O — 2026-09-18 开发 DB 路由与预阶段启动验证 / Verify dev DB routing and pre-stage startup

- 中文：确认根因 `DEV_DB_PATH_OVERRIDE`：开发护栏与 `.env` 会将显式安全副本路径替换为默认开发运行库。仅修复 `development_safety.py`，保存并在后续安装点恢复经验证的显式开发/临时 DB 路径，生产及外部路径仍拒绝。定向13项通过，全套 `354 passed + 76 subtests`，失败/错误均0。新鲜副本启动探针证明 `bd_db` 使用目标副本，诊断 job_run 仅写入后删除；未运行 Inventory。生产写入、SMTP、IMAP、BrowserMaps、调度与冻结文件变化均为0。
- English: Confirmed `DEV_DB_PATH_OVERRIDE`: the development guard and `.env` could replace an explicit safe-copy path with the default development runtime DB. Changed only `development_safety.py` to retain and restore a validated explicit development/temporary DB path; production and external paths remain blocked. Thirteen targeted tests pass and the full suite reports `354 passed + 76 subtests`, zero failures/errors. A fresh-copy startup probe proves `bd_db` uses the intended copy and writes then removes the diagnostic job only there; no Inventory ran. Production writes, SMTP, IMAP, BrowserMaps, scheduler, and frozen-file changes remain zero.

## Phase 4A.3P — 2026-09-18 最终生产副本 Inventory 重跑 / Final production-copy Inventory rerun

- 中文：在明确授权下，对新鲜生产 DB online-backup 副本执行一次且仅一次 BrowserMaps direct 标准 Inventory。启动前确认 `bd_db` 指向副本，`integrity_check=ok`，60秒内创建 job run；作业在约32分钟后自然结束为 `partial/safe_inventory_gap`。Maps 见8条、全为重复；已关联积压18条全部处理，10次官网解析全部为 `network_retry`，后处理8条。新增官网回填1，但新增官方邮箱/完整证据/关联/V2 SAFE/FSP均为0。主要已测量阻塞项是 `WEBSITE_RESOLUTION_NETWORK_RETRY`，并伴随本查询 Maps 零新增。未改代码、未部署、未写生产、未使用SMTP/IMAP、未创建FSP/授权、未改变调度或冻结文件。下一步必须停止，等待针对该窄阻塞项的新明确授权。
- English: Under explicit authorization, ran one and only one BrowserMaps-direct canonical Inventory on a fresh production-DB online-backup copy. `bd_db` was confirmed to target the copy before startup, `integrity_check=ok`, and a job run appeared within 60 seconds; the job completed naturally after about 32 minutes as `partial/safe_inventory_gap`. Maps saw eight results, all duplicates; all 18 linked-backlog rows were processed, with ten website-resolution attempts all retained as `network_retry` and eight postprocess rows. One duplicate website was backfilled, but new official emails, full evidence, linkage, V2 SAFE, and FSP were all zero. The primary measured blocker is `WEBSITE_RESOLUTION_NETWORK_RETRY`, alongside zero new Maps yield for this query. No code or production change, deployment, SMTP/IMAP, FSP/authorization creation, scheduler change, or frozen-file change occurred. Stop and await separate explicit authorization for a narrow diagnosis of this blocker.

## Phase 4A.3Q — 2026-09-18 官网解析网络重试根因与窄修复 / Website resolver network-retry root cause and narrow fix

- 中文：新鲜生产 DB 副本完整性为 `ok`，但在任何 Maps 或官网请求前停止。按当前相同 linked-backlog 资格规则得到18条可处理记录、其中11条缺官网；而4A.3P是在其副本内先回填一条重复官网后，记录10条进入 resolver。被回填的精确记录没有保留在已删除的副本制品中，无法从11条中安全推断10条。故 resolver 重现、计时、修复、控制项与测试均未运行；未改源码、未部署、未写生产、未使用SMTP/IMAP或改变调度。真实 blocker 为 `COHORT_PROVENANCE_GAP`，需明确授权测量确定性11条，或提供精确10条持久清单后再继续。
- English: The fresh production-DB copy passed integrity, but the phase stopped before any Maps or merchant-site request. The current identical linked-backlog eligibility rules yield 18 eligible rows, 11 without websites; Phase 4A.3P recorded 10 entering the resolver only after a duplicate website was backfilled inside its copy. The exact backfilled row was not preserved in the intentionally deleted copy artifacts, so ten cannot be safely inferred from eleven. Resolver reproduction, timing, fixes, controls, and tests were therefore not run; no source/production change, deployment, SMTP/IMAP, or scheduler change occurred. The actual blocker is `COHORT_PROVENANCE_GAP`: authorize a deterministic eleven-row measurement or provide a durable exact-ten manifest before continuing.

## Phase 4A.3R — 2026-09-18 确定性 11 条官网解析诊断 / Deterministic 11-row website resolver diagnosis

- 中文：按新授权从生产库只读在线备份建立开发副本（`integrity_check=ok`），在任何联网前写入11条 Ithaca 无官网 linked-backlog 持久化清单。仅运行这11条的 resolver：0 解析成功、4 个 provider 45 秒超时、1 个 Maps 导航超时、1 个 `ERR_NETWORK_CHANGED`、5 个 not_found。三条内存计时显示两条在约2秒完成搜索导航但收集到0候选卡、详情访问为0，另一条在45秒父级界限内未返回；实测根因是 BrowserMaps 搜索传输/零候选卡产出，而不是详情页扇出。正向对照有1条正确域名匹配、错误域名为0。没有实测依据修改源码，未增加超时、未运行 Inventory、未部署；生产写入、SMTP、IMAP、调度和冻结文件变化均为0。下一步必须单独授权针对搜索传输的窄诊断。
- English: Under the new authorization, created a development copy using a read-only production SQLite online backup (`integrity_check=ok`) and wrote a durable eleven-row Ithaca no-website linked-backlog manifest before any network request. Ran the resolver only for those eleven rows: zero resolutions, four provider 45-second timeouts, one Maps navigation timeout, one `ERR_NETWORK_CHANGED`, and five not-found results. In-memory timing of three representatives showed two completing search navigation in about two seconds with zero collected cards and zero detail visits; the other did not return before the 45-second parent boundary. The measured cause is BrowserMaps search transport/zero-card yield, not detail fanout. Known-positive controls produced one correct-domain match and zero wrong-domain matches. No source change was justified, no deadline was increased, Inventory was not run, and no deployment occurred; production writes, SMTP, IMAP, scheduler and frozen-file changes remain zero. A separate narrow authorization is required for any search-transport diagnosis.
