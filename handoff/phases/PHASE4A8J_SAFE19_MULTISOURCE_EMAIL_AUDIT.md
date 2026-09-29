# PHASE 4A.8J — SAFE19 转化缺口与多来源第一方邮箱审计 / SAFE19 Conversion Gap and Multi-source First-party Email Audit

日期 / Date: 2026-09-29
范围 / Scope: 生产 `bd_leads.db` 只读连接、仓库静态代码审计与既有 Facebook 队列聚合。未运行 Inventory，未访问 Facebook/其他社交平台，未运行 DNS/MX 查询，未改代码或数据库。 / Production `bd_leads.db` read-only connection, static repository audit, and existing Facebook-queue aggregation. No Inventory, Facebook/other-social traversal, DNS/MX lookup, code change, or database write was performed.

## 1. 结论 / Executive conclusion

当前 SAFE=19 并不主要说明官网邮箱抽取不足。607 条带邮箱 lead 中，526 条（86.80%）被冻结规则首先判定为已发送邮箱、已发送组织或共享域组织历史；这批记录不能通过“再补一个邮箱”恢复为 SAFE。 / Current SAFE=19 does not primarily prove inadequate official-site extraction. Of 607 email-bearing leads, 526 (86.80%) are first blocked by frozen history rules for a previously sent email, previously sent organization, or shared-domain organization history; another email cannot safely recover those rows.

最有价值且尚未实现的**证据能力**是同主体官网的结构化数据解析（JSON-LD/schema.org `Organization` / `contactPoint`）以及有界的一层官网内部链接复核的效果量测；这两项均不要求把社交网络当作第一方。Facebook 代码是孤立、只读的实验性恢复工具，当前既不在标准 Inventory 内，也没有在其既有队列中产生公开邮箱。 / The highest-value unimplemented **evidence capability** is same-party structured-data parsing (JSON-LD/schema.org `Organization` / `contactPoint`) plus measured effectiveness of the bounded one-level official internal-link review; neither requires treating social media as first-party. Facebook code is an isolated, read-only experimental recovery tool, is not in canonical Inventory, and produced no public email in its existing queue.

## 2. 安全与方法 / Safety and method

- 生产库以 SQLite URI `mode=ro` 打开；`PRAGMA integrity_check = ok`。 / The production database was opened with SQLite URI `mode=ro`; `PRAGMA integrity_check = ok`.
- V1/V2 离线重放仅注入已有 MX 缓存；所有未缓存域名强制为 `dns_error`，因此不会调用 DNS 或写入 MX cache。 / Offline V1/V2 replay used only existing MX cache values; every uncached domain was forced to `dns_error`, so it could neither call DNS nor write MX cache.
- 因缓存中只有 60 个 `ok` 域、376 个域在本次无网络重放中为 `dns_error`，该重放只能用于阻塞结构，不可替代已确认的生产读数 `READ_ONLY_V2_SAFE_UNIQUE_ORGS=19`。 / Because only 60 domains were cached as `ok` and 376 were `dns_error` in this no-network replay, the replay is valid for blocker structure only and must not replace the confirmed production measurement `READ_ONLY_V2_SAFE_UNIQUE_ORGS=19`.
- 未采集或展示个人邮箱；Facebook 没有发生页面访问，故不存在新社交联系人数据。 / No personal email was collected or displayed; no Facebook pages were opened, so no new social-contact data exists.

## 3. 冻结规则漏斗 / Frozen-rule funnel

| 指标 / Metric | 数量 / Count | 说明 / Meaning |
|---|---:|---|
| TOTAL_LEADS | 1,130 | 当前生产快照 / Current production snapshot |
| EMAIL_PRESENT | 607 | `email` 非空 / non-empty `email` |
| FIRST_PARTY_OFFICIAL_EMAIL | 358 | 官方可见、官方 mailto、批发/供应商或官方搜索来源标识 / marked official-visible, official-mailto, wholesale/vendor, or official-search |
| BROAD_READY | 54 | 冻结 `is_broad_outreach_ready()` 只读评估 / frozen read-only evaluation |
| V1_CAMPAIGN_ELIGIBLE | 47 | 冻结 V1 只读评估 / frozen V1 read-only evaluation |
| V2_CAMPAIGN_ELIGIBLE | 19 | 已确认生产只读 SAFE 口径；本次不以缓存缺失的离线重放替换 / confirmed production read-only SAFE measure; not replaced by cache-limited replay |
| UNIQUE_SAFE_ORGS | 19 | 已确认生产读数 / confirmed production measure |

缓存限定的离线 V2 重放仅得到 1 条 / 1 个组织可通过，原因是 376 个域被刻意 fail-closed 为 `dns_error`；它不是 SAFE 从 19 降至 1 的新事实。 / The cache-limited offline V2 replay produces only 1 passing lead / 1 organization because 376 domains were intentionally fail-closed as `dns_error`; it is not evidence that SAFE fell from 19 to 1.

## 4. 非 SAFE 带邮箱 lead 的主阻塞因素 / Dominant blockers for non-SAFE email-bearing leads

基数为 606：607 个带邮箱 lead 减去已确认 SAFE 19；同一 lead 可能有多个规则失败，本表按以下优先级只计一次：发送/抑制/退信历史 → 组织重复 → 邮箱质量/归属 → MX → 证据 → 时区/组织键 → 人工审核。 / The denominator is 606: 607 email-bearing leads minus confirmed SAFE 19. A lead can fail multiple rules; this table assigns exactly one blocker in priority order: sent/suppression/bounce history → duplicate organization → email quality/ownership → MX → evidence → timezone/organization key → manual review.

| 主阻塞 / Dominant blocker | 数量 / Count | 占非 SAFE 带邮箱 lead / % |
|---|---:|---:|
| PREVIOUSLY_SENT | 526 | 86.80% |
| MX_DNS_ERROR | 40 | 6.60% |
| MX_NXDOMAIN | 19 | 3.14% |
| SUPPRESSED | 5 | 0.83% |
| MANUAL_REVIEW | 4 | 0.66% |
| PUBLIC_MAILBOX_NO_OFFICIAL_EVIDENCE | 4 | 0.66% |
| THIRD_PARTY_DOMAIN | 3 | 0.50% |
| MX_NO_ROUTE | 3 | 0.50% |
| EVIDENCE_STALE | 1 | 0.17% |
| EMAIL_INVALID | 1 | 0.17% |
| BOUNCED / DUPLICATE_ORG / MX_NULL_MX / EVIDENCE_MISSING / TIMEZONE / ORGANIZATION_KEY / BROAD_READY_HISTORY / OTHER | 0 | 0.00% |

说明：未缓存 MX 域被人工限定为 `MX_DNS_ERROR`，因此 40 不是 DNS 故障的生产断言；它是“本次无网络、无写入审计无法确认”的数量。原始冻结规则可同时记录 51 个 `mx:nxdomain`、6 个 `mx:no_mail_route`、1 个 `mx:null_mx`、287 个证据过期与 157 个 guessed-email 加强验证失败，但这些不是本表的主阻塞。 / Note: uncached domains were deliberately represented as `MX_DNS_ERROR`, so 40 is not a claim of production DNS failure; it means this no-network, no-write audit could not confirm them. Raw frozen rules also record 51 `mx:nxdomain`, 6 `mx:no_mail_route`, 1 `mx:null_mx`, 287 stale-evidence failures, and 157 guessed-email enhanced-verification failures, but those are not dominant blockers in the one-bucket table.

## 5. 官网邮箱抽取覆盖与缺口 / Official-site extraction coverage and gaps

### 已覆盖 / Currently covered

- 主页、`/contact`、`/about`、`/wholesale`、`/vendor`、`/partnership`、`/privacy`、`/terms`。 / Homepage and `/contact`, `/about`, `/wholesale`, `/vendor`, `/partnership`, `/privacy`, `/terms`.
- 变体：`/contact-us`、`/pages/contact`、`/about-us`、`/team`、`/staff`、`/sales`、`/business`、`/support`、`/customer-service`、`/vendors`、`/dealers`、`/distribution`、`/partnerships`。 / Variants: `/contact-us`, `/pages/contact`, `/about-us`, `/team`, `/staff`, `/sales`, `/business`, `/support`, `/customer-service`, `/vendors`, `/dealers`, `/distribution`, `/partnerships`.
- 首页中可见、同主体且带有 contact/about/team/staff/sales/business/wholesale/vendor/dealer/distribution/partnership/support/customer/service 提示的内部链接，单层、总预算最多 12 页。 / Visible same-party homepage links with contact/about/team/staff/sales/business/wholesale/vendor/dealer/distribution/partnership/support/customer/service hints, one level only, with a total budget of 12 pages.
- 可见文本邮箱、可见 `mailto:`、可见页头/页脚（HTML 可见文本解析器不排除 header/footer）、联系表单、HTTP 2xx/3xx、TLS、同主体 final URL、时间戳与内容哈希。 / Visible-text email, visible `mailto:`, visible header/footer (the HTML visible-text parser does not exclude them), contact forms, HTTP 2xx/3xx, TLS, same-party final URL, timestamp, and content hash.
- 静态抓取失败于 401/403、超时、重置或断连时，标准 `BrowserFallbackWebsiteFetcher` 可进行有界浏览器回退。 / On static failures of 401/403, timeout, reset, or disconnect, canonical `BrowserFallbackWebsiteFetcher` can perform bounded browser fallback.

### 未覆盖或不能证明覆盖 / Not covered or not provably covered

- JSON-LD/schema.org `Organization`、`contactPoint` 和其他 `<script type="application/ld+json">`：未解析；script 被可见文本规则排除。 / JSON-LD/schema.org `Organization`, `contactPoint`, and other `<script type="application/ld+json">`: not parsed; scripts are excluded by visible-text rules.
- PDF、catalog、line sheet、dealer application：默认 fetcher 拒绝非 text/html/xml 内容，未做 PDF 解析。 / PDFs, catalogs, line sheets, and dealer applications: the default fetcher rejects non text/html/xml content; no PDF parsing exists.
- 深层爬取、多层菜单、站内搜索：没有；这符合现有有界、安全设计。 / Deep crawling, multi-level menus, and on-site search: absent; this is consistent with the current bounded safety design.
- Instagram、LinkedIn、YouTube、X/Twitter、TikTok：没有官方链接提取或标准 Inventory 处理。 / Instagram, LinkedIn, YouTube, X/Twitter, and TikTok: no official-link extraction or canonical Inventory handling.

### 可量化现有恢复池 / Quantified existing recovery cohorts

| 队列 / Cohort | 数量 / Count | 审计含义 / Audit interpretation |
|---|---:|---|
| NO_EMAIL_WITH_OFFICIAL_WEBSITE | 141 | 最直接的官网补全候选，非已证明产出 / direct official-site enrichment candidates, not proven yield |
| GUESSED_EMAIL_WITH_OFFICIAL_WEBSITE | 167 | 不能转正；必须用独立第一方证据替代 / cannot be promoted; requires independent first-party evidence |
| STALE_EMAIL_EVIDENCE (>90 天) | 283 | 需要重新验证；324 条带邮箱证据在 90 天内 / requires revalidation; 324 email-bearing records are within 90 days |
| CONTACT_FORM_ONLY（无邮箱） | 22 | 不能自动变为收件人 / cannot automatically become a recipient |
| SOCIAL_ONLY_EMAIL | 0 | 当前 lead 中没有 social 来源邮箱 / no social-sourced email in current leads |
| official website + evidence URL but no email | 107 | 说明已有网页证据但尚未产出公开邮箱 / website evidence exists but no public email was produced |
| email_extraction_pending（discovery） | 7 | 最小、可控的待完成官网提取池 / smallest bounded pending official-site extraction cohort |
| linked_backlog_retry payload | 34 | 历史/恢复队列标记；不是 34 个可安全提升的承诺 / historical/recovery marker; not a promise of 34 safe promotions |

历史持久化状态不能无歧义重建“静态成功、浏览器尝试、浏览器成功/失败”的全量逐页计数，因此以下运行时分类均为 `NOT_MEASURED`，不能杜撰：`STATIC_FETCH_SUCCESS_EMAIL_FOUND`、`STATIC_FETCH_SUCCESS_NO_EMAIL`、`STATIC_FETCH_FAILED`、`BROWSER_FALLBACK_ATTEMPTED`、`BROWSER_FALLBACK_SUCCESS_EMAIL_FOUND`、`BROWSER_FALLBACK_SUCCESS_NO_EMAIL`、`BROWSER_FALLBACK_FAILED`、`AUTOMATION_RECOVERY_EXHAUSTED`。 / Durable historical fields cannot unambiguously reconstruct per-page static success, browser attempts, or browser success/failure totals, so all listed runtime classifications are `NOT_MEASURED` and must not be fabricated.

## 6. Facebook 与官方社媒审计 / Facebook and official-social audit

| 问题 / Question | 结论 / Finding |
|---|---|
| FACEBOOK_CODE_EXISTS | true — `fb_enrich.py`, `fb_batch_runner.py`, `b_pool_recovery_runner.py` |
| FACEBOOK_IN_CANONICAL_INVENTORY | false — `bd_orchestrator.py --stage inventory --live` 不导入或调用这些模块 / no import or call |
| FACEBOOK_DB_WRITE_ENABLED | false — 三个模块均以 `mode=ro` 连接 DB；仅写本地 checkpoint/audit JSON / all three connect `mode=ro`; only local checkpoint/audit JSON is written |
| FACEBOOK_EMAIL_CAN_BECOME_SAFE | false（当前政策）— social-only 来源为 `facebook_social`，没有第一方官网归属，不是 A0/SAFE / false under current policy; social-only `facebook_social` lacks official-site ownership proof |
| OFFICIAL_SITE_WITH_FB_LINK | 9（既有 `facebook_source=official_website_link` 队列事实） |
| FB_PAGE_OPENABLE / FB_LOGIN_REQUIRED / FB_CAPTCHA / FB_PAGE_NOT_FOUND | NOT_MEASURED（本阶段未打开 Facebook，且不规避登录/挑战） / NOT_MEASURED (no Facebook traversal and no bypass of login/challenges) |
| FB_PUBLIC_EMAIL_FOUND | 0（既有 20 条队列的持久化 `fb_email`） |
| FB_PUBLIC_WEBSITE_FOUND / FB_PUBLIC_PHONE_FOUND | NOT_MEASURED（现有队列不持久化可审计的完整聚合字段） / NOT_MEASURED (existing queue lacks complete auditable aggregate fields) |
| FB_NEW_EMAIL_NOT_IN_DB / FB_POTENTIAL_SAFE_ORGS | 0 / 0（没有发现的 Facebook 邮箱） |

现有队列共 20 条：3 条有 Facebook URL，9 条标记为官网链接来源，状态为 7 `no_facebook_link`、6 `failed_final`、5 `mismatch`、2 `no_facebook_final`；没有 `fb_email`，也没有匹配分数 ≥0.6 的记录。未报告逐条邮箱，因为没有发现此类邮箱。 / The existing queue has 20 rows: 3 with a Facebook URL, 9 marked as official-website-link sourced, and statuses of 7 `no_facebook_link`, 6 `failed_final`, 5 `mismatch`, and 2 `no_facebook_final`; none has `fb_email` or match score ≥0.6. No per-email report is provided because no such email was found.

其他社媒（Instagram/LinkedIn/YouTube/X/TikTok）没有存储的官方链接事实或标准处理路径。本阶段没有对外访问，因此其 `OFFICIAL_LINKS_FOUND`、`PUBLIC_EMAILS_FOUND`、`NEW_EMAILS_NOT_IN_DB`、`BUSINESS_IDENTITY_MATCHED` 与 `LIKELY_SAFE_AFTER_EXISTING_GATES` 均为 `NOT_MEASURED`，不是零产出的结论。登录依赖、CAPTCHA 或不稳定自动化的平台应归为 LOW-VALUE / UNSUITABLE，不能绕过访问控制。 / Other social platforms (Instagram/LinkedIn/YouTube/X/TikTok) have no stored official-link facts or canonical processing lane. This phase made no external requests, so their `OFFICIAL_LINKS_FOUND`, `PUBLIC_EMAILS_FOUND`, `NEW_EMAILS_NOT_IN_DB`, `BUSINESS_IDENTITY_MATCHED`, and `LIKELY_SAFE_AFTER_EXISTING_GATES` are `NOT_MEASURED`, not zero-yield findings. Platforms requiring login, CAPTCHA, or unstable automation are LOW-VALUE / UNSUITABLE and must not have access controls bypassed.

## 7. 官方合作伙伴与 Web Search 审计 / Official-partner and Web-search audit

- `wholesale_vendor_page` 已是 V1 官方证据类型；现有带邮箱 lead 中为 2 条。它可作为高质量 E4 官方合作伙伴证据，但不应把 Yelp、Yellow Pages 或通用目录升级为归属证据。 / `wholesale_vendor_page` is already a V1 official-evidence type; 2 current email-bearing leads use it. It can remain high-quality E4 official-partner evidence, but Yelp, Yellow Pages, and generic directories must not be elevated to ownership evidence.
- `web_search_official` 现有 6 条，6 条都有 evidence URL 和 snippet。搜索摘要本身不构成证据；必须落到同主体官方页面。 / There are 6 `web_search_official` leads, all 6 with evidence URL and snippet. A search snippet alone is not evidence; it must land on a same-party official page.
- `web_search_official` 的 V2/MX 通过数在本阶段为 `NOT_MEASURED`：为保持零 DNS/零写入，不以失效缓存替代实时 MX。 / `web_search_official` V2/MX pass count is `NOT_MEASURED`: to preserve zero DNS and zero write behavior, stale cache was not substituted for live MX.

## 8. 证据分级提案（不改变政策） / Evidence taxonomy proposal (no policy change)

| 层级 / Tier | 建议来源 / Proposed sources | 审计结论 / Audit position |
|---|---|---|
| E1_DIRECT_FIRST_PARTY | `official_page_visible`, `official_mailto`, `first_party_structured_data` | 适合自动化；结构化数据需先验证其邮箱和对象归属 / suitable for automation; structured data needs email and entity ownership validation |
| E2_OFFICIAL_SEARCH | `web_search_official` + 官方落地页 | 可接受，但摘要不是证据 / acceptable, but snippet is not proof |
| E3_OFFICIALLY_LINKED_SOCIAL | 官网直接链接 → 身份匹配社媒 → 可见完整邮箱 | 仅提案；现行规则不自动 SAFE / proposal only; current rules do not auto-SAFE |
| E4_OFFICIAL_PARTNER | `wholesale_vendor_page`、官方制造商/经销关系 | 高质量但需关系与身份独立验证 / high quality but requires independent relationship and identity validation |
| E5_HIGH_RISK | guessed、非关联社媒、第三方目录、无落地页的摘要 | 保持阻止 / remain blocked |

若日后评审 E3，最低证据须同时满足：官网直接链接、社媒业务身份/城市匹配、公开显示完整邮箱、URL+可见摘录、证据新鲜、MX pass、未发送、未抑制、未退信及唯一组织。该提案**不自动批准**，也不改变 V2。 / If E3 is reviewed later, it must require all of: direct official-site link, social business/city identity match, publicly visible full email, URL plus visible excerpt, fresh evidence, MX pass, unsent, non-suppressed, non-bounced, and unique organization. This proposal is **not automatically approved** and does not change V2.

## 9. 无写入产量模拟 / No-write yield simulation

模拟绝不放宽 V1、MX、证据新鲜度、发送/抑制/退信历史或唯一组织规则。当前没有从新路径实际得到一个满足这些规则的新邮箱，因此保守值必须为 0。 / The simulation never relaxes V1, MX, evidence freshness, sent/suppression/bounce history, or unique-organization rules. No new-path email satisfying these gates was actually obtained in this phase, so the conservative value must be 0.

| 渠道 / Channel | 保守新增 SAFE 组织 / Conservative | 有界中等情景 / Bounded moderate | 根据 / Basis |
|---|---:|---:|---|
| deeper_official_website | 0 | ≤7 | 7 条 `email_extraction_pending`；必须逐条实测、去重与过全部冻结门 / 7 pending rows; each must be measured, deduped, and pass all frozen gates |
| structured_data | 0 | NOT_ESTIMABLE | 当前不解析 JSON-LD，缺乏实测命中率 / no JSON-LD parsing or measured hit rate |
| officially_linked_facebook | 0 | 0 | 既有队列无公开邮箱 / existing queue has no public email |
| officially_linked_instagram | 0 | NOT_ESTIMABLE | 无官方链接事实或受控测量 / no official-link facts or controlled measurement |
| officially_linked_linkedin | 0 | NOT_ESTIMABLE | 同上 / same |
| official_partner_pages | 0 | ≤2 | 仅有 2 条现有高质量来源，不等同于新增组织 / only 2 existing high-quality sources; not new organizations |
| web_search_official | 0 | ≤6 | 6 条既有候选，不等同于新增或 MX/V2 通过 / 6 existing candidates; not new or proven MX/V2 pass |
| recoverable_existing_rows | 0 | ≤7 | 取最小可控 pending 池，避免同官网/同组织双计 / smallest controlled pending cohort; avoids site/org double count |

`POTENTIAL_SAFE_CONSERVATIVE = 0`。`POTENTIAL_SAFE_MODERATE = ≤7`，它是待验证上界而非预测或承诺，不能与上述渠道相加。 / `POTENTIAL_SAFE_CONSERVATIVE = 0`. `POTENTIAL_SAFE_MODERATE = ≤7` is a pending-validation upper bound, not a forecast or commitment, and channels must not be added together.

## 10. 标准 Inventory 实际调用路径 / Canonical Inventory actual lanes

| LANE | IMPLEMENTED | DEPLOYED / CALLED BY CANONICAL INVENTORY | READ_ONLY_OR_WRITEBACK | CURRENT_YIELD / BLOCKER |
|---|---|---|---|---|
| BrowserMaps discovery | 是 / yes | 是 / yes | 写回 discovery/staging / writes discovery/staging | 受城市矩阵与重复结果约束 / constrained by city matrix and duplicates |
| official-site resolution | 是 / yes | 是 / yes | 写回官网与状态 / writes website/status | 有界 provider 超时与身份审查 / bounded provider timeout and identity review |
| browser fallback | 是 / yes | 通过官网抓取器间接调用 / indirect via site fetcher | 写回后处理结果 / writes postprocess outcomes | 仅访问/传输失败触发 / only access/transport failures trigger it |
| staging postprocess | 是 / yes | 是 / yes | 写回证据、邮箱或终态 / writes evidence, email, or terminal state | 受 12 页、同主体、可见文本限制 / bounded 12 pages, same-party, visible text |
| linked backlog | 是 / yes | 是 / yes | 写回既有 staging/lead 状态 / writes existing staging/lead state | 有界 20；恢复行取决于官网可达 / bounded 20; recovery depends on official-site access |
| first-party email extraction | 是 / yes | 由 staging/backlog 调用 / through staging/backlog | 写回完整证据 / writes full evidence | 141 个无邮箱官网 lead 是候选，不是已证明可得 / 141 candidates, not proven yield |
| Facebook enrichment | 是 / yes | 否 / no | DB 只读；本地审计文件写入 / DB read-only; local audit writes | 现有队列 0 邮箱；不在标准路径 / 0 emails in existing queue; off canonical path |
| official social enrichment | 否 / no | 否 / no | 不适用 / N/A | 无测量 / unmeasured |
| web_search_official | 有来源类型 / source type exists | 未见标准 Inventory 专用调用 / no dedicated canonical invocation found | 现有 lead 数据 / existing lead data | 6 条，需官网落地页与 MX / 6 rows; needs official landing page and MX |
| wholesale/vendor evidence | 有来源类型 / source type exists | 未见标准 Inventory 专用搜集调用 / no dedicated canonical collection found | 现有 lead 数据 / existing lead data | 2 条；高质量但小样本 / 2 rows; high quality but small sample |
| structured-data extraction | 否 / no | 否 / no | 不适用 / N/A | 未测量、明确缺口 / unmeasured, explicit gap |

## 11. 优先级 / Prioritization

| 优先级 / Priority | 建议 / Recommendation | 原因 / Rationale |
|---|---|---|
| P0 | 对 7 条 `email_extraction_pending` 做受控开发副本复核，并量测现有 12 页官网路径的真实增量；不改策略。 / Replay the 7 `email_extraction_pending` rows on a controlled development copy and measure the existing 12-page official-site path; no policy change. | 最小队列、最高证据质量、无新平台依赖 / smallest cohort, highest evidence quality, no new platform dependency |
| P1 | 设计并以离线 fixture 验证 JSON-LD `Organization`/`contactPoint` 解析，只有可见或明确业务联系邮箱才进入同一证据链。 / Design and fixture-test JSON-LD `Organization`/`contactPoint` parsing; only visible or clearly business-contact emails can enter the same evidence chain. | 同主体、低访问风险；实际命中率仍未知 / same party, low access risk; real yield unknown |
| P2 | 评估官方链接 Facebook 的 E3 证据提案，仅在免登录、非 CAPTCHA、身份强匹配、公开完整邮箱时采集。 / Evaluate the official-site-linked Facebook E3 proposal only for no-login, no-CAPTCHA, strong identity-match, publicly visible full-email cases. | 当前产量为 0，平台不稳定 / current yield is 0 and platform is unstable |
| DO_NOT_AUTOMATE | 随机社媒搜索、绕过登录/CAPTCHA、第三方目录邮箱、批量 PDF 爬取或把 guessed email 转正。 / Random social search, bypassing login/CAPTCHA, third-party-directory email, bulk-PDF crawling, or promoting guessed email. | 高误报、合规/稳定性风险，或不满足归属证据 / high false-positive, compliance/stability risk, or fails ownership evidence |

## 12. 最终安全声明 / Final safety statement

- PRODUCTION_CODE_CHANGED = false
- PRODUCTION_DB_WRITES = 0
- V2_CHANGED = false
- MX_CHANGED = false
- SMTP_CONNECTIONS = 0
- EMAILS_SENT = 0
- INVENTORY_RUNS = 0
- SCHEDULER_CHANGES = 0

下一步必须先获得新的明确授权；本阶段仅交付审计与设计，不实施任何建议。 / Any next step requires new explicit authorization; this phase delivers audit and design only and implements none of the recommendations.
