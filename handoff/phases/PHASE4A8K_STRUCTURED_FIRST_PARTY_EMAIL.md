# Phase 4A.8K — Structured First-Party Email Expansion + Conversion Telemetry
# Phase 4A.8K — 结构化第一方邮箱扩展与转化遥测

## Scope and safety / 范围与安全

- Development only. No production source/database write, production Inventory, SMTP, IMAP, FSP, scheduler change, or deployment occurred.
- 仅开发环境。未发生生产源码/数据库写入、生产 Inventory、SMTP、IMAP、FSP、调度变更或部署。
- A fresh production SQLite online-backup copy passed `PRAGMA integrity_check=ok`; every replay write remained in ignored development-copy databases.
- 新鲜生产 SQLite 在线备份副本通过 `PRAGMA integrity_check=ok`；所有重放写入均在被忽略的开发副本数据库内。

## Narrow implementation / 窄范围实现

`discovery/discovery_service.py` now parses JSON-LD only after the canonical official-page gate has accepted an HTTPS, HTTP-success, TLS-success, same-party page. It accepts only explicit `email` and `contactPoint.email` from identity-matched Schema.org business objects: Organization, LocalBusiness, Store, Corporation, ProfessionalService, and business subclasses. `@graph` and contact-point arrays are supported.

`discovery/discovery_service.py` 现在仅在标准官网页面门禁已接受 HTTPS、HTTP 成功、TLS 成功且同主体的页面后解析 JSON-LD。它只接受与身份匹配的 Schema.org 商业对象中明确的 `email` 与 `contactPoint.email`：Organization、LocalBusiness、Store、Corporation、ProfessionalService 和商业子类；支持 `@graph` 与 contact-point 数组。

Malformed JSON, Person/non-business schemas, business-name mismatch, arbitrary or hidden script `@` text, third-party final URLs, non-HTTPS structured pages, and invalid emails are rejected. Visible public email retains priority over structured data. The page budget remains 12.

畸形 JSON、Person/非商业 schema、商户名不匹配、任意或隐藏脚本 `@` 文本、第三方最终 URL、非 HTTPS 结构化页面和无效邮箱都会被拒绝。可见公开邮箱仍优先于结构化数据。页面预算保持 12。

Accepted structured evidence uses `email_source_type=first_party_structured_data`, includes the literal email in a bounded structured-data excerpt, and retains the full existing evidence contract.

被接受的结构化证据使用 `email_source_type=first_party_structured_data`，在有界结构化数据摘录中包含字面邮箱，并保留全部既有证据契约。

## Durable telemetry / 持久遥测

No migration is required. Existing `lead_discovery_results.raw_payload_json` records `website_enrichment_telemetry`: static/browser outcomes, recovery exhaustion, attempted/qualifying pages, visible/mailto/structured email flags, extracted-email count, contact-form-only, and no-email-on-accepted-page.

不需要迁移。既有 `lead_discovery_results.raw_payload_json` 记录 `website_enrichment_telemetry`：静态/浏览器结果、恢复耗尽、已尝试/合格页面、可见/mailto/结构化邮箱标记、提取数、仅联系表单和合格页面无邮箱。

## Controlled production-copy replay / 受控生产副本重放

The authoritative snapshot had seven `email_extraction_pending` rows. All seven were replayed serially against only their already stored public official websites; no Maps search or Inventory ran.

权威快照有 7 条 `email_extraction_pending` 记录。全部 7 条均仅对其已存储的公开官网串行重放；未运行 Maps 搜索或 Inventory。

| ID | Outcome / 结果 | Pages / 页面数 | Email result / 邮箱结果 |
|---|---|---:|---|
| 314 | `history_blocked` | 11 | none / 无 |
| 315 | `manual_review_needed` | 12 | visible `mailto`, not structured / 可见 `mailto`，非结构化 |
| 321 | `review_recovery` | 12 | none; browser recovery exhausted / 无；浏览器恢复耗尽 |
| 322 | `history_blocked` | 12 | none / 无 |
| 324 | `history_blocked` | 12 | none / 无 |
| 325 | `identity_review` | 12 | visible `mailto`, not structured / 可见 `mailto`，非结构化 |
| 329 | `identity_review` | 11 | visible `mailto`, not structured / 可见 `mailto`，非结构化 |

`STRUCTURED_EMAILS_FOUND=0`; visible/mailto emails found=3; `FULL_EVIDENCE_RECORDS_CREATED=0`; `V2_PASS_WITH_EXISTING_MX=NOT_APPLICABLE` because no new structured candidate reached V2. The prior production baseline is `SAFE_UNIQUE_ORGS=19`; no new eligible structured organization was produced, so simulated SAFE remains 19.

`STRUCTURED_EMAILS_FOUND=0`；发现可见/mailto 邮箱=3；`FULL_EVIDENCE_RECORDS_CREATED=0`；因没有新的结构化候选进入 V2，`V2_PASS_WITH_EXISTING_MX=NOT_APPLICABLE`。此前生产基线为 `SAFE_UNIQUE_ORGS=19`；未产生新的合格结构化组织，因此模拟 SAFE 仍为 19。

This is an honest low-yield sample result, not a policy failure. Fixture coverage proves that the path accepts only qualifying structured evidence and creates nothing by guesswork.

这是诚实的低产量样本结果，不是策略失败。fixture 覆盖证明该路径只接受合格结构化证据，且不会靠猜测创建任何内容。

## V1/V2/MX semantics / V1/V2/MX 语义

`campaign_eligible.py` changes only V1's explicit official-evidence allowlist to recognize `first_party_structured_data`. This is a source-type semantic extension, not a relaxed gate. V2 and MX code/policy are unchanged and V2 still requires its existing MX, history, freshness, and quality gates.

`campaign_eligible.py` 仅修改 V1 的明确官方证据白名单以识别 `first_party_structured_data`。这属于来源类型语义扩展，不是放宽门禁。V2 和 MX 代码/政策未变，V2 仍要求既有 MX、历史、新鲜度与质量门禁。

`V1_CHANGED=true` (isolated allowlist), `V2_CHANGED=false`, `MX_CHANGED=false`, `NO_POLICY_RELAXATION=true`.

`V1_CHANGED=true`（隔离白名单），`V2_CHANGED=false`，`MX_CHANGED=false`，`NO_POLICY_RELAXATION=true`。

## Tests / 测试

- Targeted regressions: 23 passed, 0 failures, 0 errors. Coverage includes business schemas, `@graph`, contact arrays, rejection cases, visible priority, mailto, cross-party rejection, HTTPS-only structured acceptance, telemetry, and V1 recognition.
- 定向回归：23 项通过，0 失败，0 错误。覆盖商业 schema、`@graph`、contact 数组、拒绝案例、可见优先级、mailto、跨主体拒绝、仅 HTTPS 的结构化接受、遥测和 V1 识别。
- Standard project unittest: 421 test methods passed, 0 failures, 0 errors. Changed Python files compiled and `git diff --check` is clean.
- 标准项目 unittest：421 个测试方法通过，0 失败，0 错误。已变更 Python 文件编译通过，`git diff --check` 通过。

## Future web-search hook / 未来 web-search 接入点

Not implemented in this phase. A future provider must return only official-URL candidates plus transparent provenance for `(business_name, city, state)`. The sole integration point is `DiscoveryService._postprocess_staged_result`: validate candidate URLs through the existing identity/HTTPS/TLS/HTTP/same-party/page-budget gates, then reuse `_fetch_official_pages` and the same evidence writer. Search-result email snippets must never be evidence or directly create leads.

本阶段不实现。未来 provider 只能为 `(business_name, city, state)` 返回官网 URL 候选及透明来源。唯一接入点是 `DiscoveryService._postprocess_staged_result`：先通过既有身份/HTTPS/TLS/HTTP/同主体/页面预算门禁验证候选 URL，再复用 `_fetch_official_pages` 和同一证据写入器。搜索结果邮箱摘要绝不能作为证据或直接创建 lead。

## Decision / 决策

`READY_FOR_PRODUCTION_REVIEW=true`; `READY_FOR_PRODUCTION=false`. The code is fixture- and regression-validated, but the first seven-row public-site sample yielded zero structured emails. Deployment remains an explicit decision; do not deploy or resume scheduling from this phase.

`READY_FOR_PRODUCTION_REVIEW=true`；`READY_FOR_PRODUCTION=false`。代码已通过 fixture 与回归验证，但首个 7 条公开官网样本的结构化邮箱产量为零。部署仍需明确决定；不得由本阶段部署或恢复调度。
