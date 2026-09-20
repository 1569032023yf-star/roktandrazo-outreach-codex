# Phase 4A.6 — First-Party Email Enrichment Expansion / 第一方邮箱补全扩展

## Scope and safety / 范围与安全

- **Development only / 仅开发环境：** A fresh SQLite online-backup copy of production data was used. The production database and production files were not written.
- **Network boundary / 联网边界：** The deterministic cohort contained four existing official sites; only ordinary public HTTP/HTTPS requests to those sites were made. No directory, social network, search snippet, SMTP, IMAP, recipient creation, FSP, authorization, scheduler, or deployment action occurred.
- **Allowed source scope / 源码范围：** `discovery/discovery_service.py` only. `bd_template.py` from Phase 4A.5 was not modified.
- **Frozen chain / 冻结链：** `campaign_eligible_v2.py`, `preflight_gate.py`, `bd_sender.py`, `daily_session.py`, `final_send_plan.py`, `outreach_control.py`, `discovery/website_resolver.py`, and BrowserMaps provider code remain byte-for-byte unchanged.

## Change / 变更

The existing `UrlLibWebsiteFetcher`, visible-text parser, identity check, evidence object, and staging postprocess are retained. The narrow change adds:

- a hard **12-attempt per official-site** budget / 每个官网最多 12 次页面尝试；
- homepage-first, one-level visible same-party internal-link discovery, then existing fixed-path probes and documented contact/about/team/staff/sales/business/wholesale/vendor/dealer/distribution/partnership/support/customer-service variants / 先主页、再一层可见同主体内部链接、随后既有固定路径和有限变体；
- URL canonicalization and deduplication, with external, social, directory, marketplace, tracking, and cross-party destinations rejected / URL 规范化去重，拒绝外域、社交、目录、市场、追踪及跨主体地址；
- explicit human-visible `name [at] domain [dot] tld` decoding only when the complete expression appears in the same visible text window / 仅当完整表达式位于同一可见文本窗口时解析显式混淆邮箱；
- evidence linkage accepting a same-party `www`/apex redirect while retaining HTTPS, TLS, HTTP-success, visible-text, content-hash, and first-party requirements / 在保持 HTTPS、TLS、HTTP 成功、可见文本、内容哈希与第一方要求的条件下，允许同主体 `www`/根域跳转。

No identity threshold, V2, MX, history, suppression, bounce, quota, authorization, or send policy changed. / 未改变身份阈值、V2、MX、历史、退订、退信、配额、授权或发送策略。

## Deterministic cohort / 确定性样本

Pre-network manifest: four nonterminal, linked, confirmed-official-site rows with empty email, selected deterministically from the development production-data copy.

| Metric / 指标 | Baseline / 基线 | After change / 变更后 |
|---|---:|---:|
| Cohort / 样本数 | 4 | 4 |
| Accepted fetched pages / 合格抓取页面 | 11 | 19 |
| Visible first-party emails / 可见第一方邮箱 | 0 | 1 |
| Full evidence records persisted / 已持久化完整证据 | 0 | 1 |
| Recovered by discovered internal link / 由发现的内部链接恢复 | 0 | 1 |
| Third-party or guessed promotions / 第三方或猜测提升 | 0 | 0 |

The positive result was **Cantrip Cards & Games** (`lead_id=1103`, `discovery_id=306`):

- Email / 邮箱: `contact@cantripcards.com`
- Requested and final URL / 请求及最终 URL: `https://cantripcards.com/pages/contact`
- Method / 方法: `official_discovered_internal_link`
- Evidence / 证据: HTTP 200, HTTP success true, TLS success true, fresh timestamp, SHA-256 content hash present, and a literal visible excerpt containing the email.

The canonical development-copy evidence-linkage rehearsal persisted all ten required evidence fields. It returned `manual_review_needed`, not sendable, because existing hygiene/V2 controls remain in force. / 规范的开发副本证据关联演练写入了全部十项必需字段。它返回 `manual_review_needed`，并未变为可发送状态，因为既有卫生与 V2 控制仍然生效。

## Frozen MX/V2 measurement / 冻结 MX/V2 测量

For the single newly evidenced domain, the existing MX path returned `dns_error`. Frozen V2 therefore returned `eligible=false`, `pool=BLOCKED`. This is an honest fail-closed result; no cache, V2, or MX policy was weakened. / 对唯一新增证据域名，既有 MX 路径返回 `dns_error`，冻结 V2 因此返回 `eligible=false`、`pool=BLOCKED`。这是诚实的失败关闭结果；没有放宽缓存、V2 或 MX 策略。

## Tests / 测试

- Targeted: 10 passed, 0 failed, 0 errors (`test_first_party_email_enrichment` and Phase 4A.5 routing regression).
- Full project unittest suite: **346 passed, 0 failed, 0 errors**.
- Coverage includes same-party discovery, external/social/directory rejection, deduplication, 12-attempt cap, TLS and cross-party redirect rejection, hidden content rejection, mailto/plain-text acceptance, explicit obfuscation acceptance, inference rejection, complete evidence fields, and Phase 4A.5 generic inbox routing/hash preservation.

## Decision / 决策

`OFFICIAL_EMAIL_LOW_YIELD` is narrowed: the fixed extractor missed a real first-party contact page that is now recovered through bounded same-party discovery. The exact current blocker for promotion is not code safety; it is production review and explicit deployment authorization. The newly evidenced record itself remains fail-closed on MX DNS error. / `OFFICIAL_EMAIL_LOW_YIELD` 已被缩小：原固定路径提取器遗漏了一个真实第一方联系页，现可通过有界同主体发现恢复。当前进入生产的阻塞不是代码安全，而是生产评审及明确部署授权。新增证据记录本身因 MX DNS 错误仍保持失败关闭。
