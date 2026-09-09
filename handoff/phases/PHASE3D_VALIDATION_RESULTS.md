# Phase 3D 验证报告 / Validation Results

## 结论 / Decision

已有 lead 安全关联已验证；可提交明确部署批准，尚未部署。
Existing-lead safe linkage is validated; ready for explicit deployment approval, not deployed.

## 复现与最小修复 / Reproduction and minimal fix

使用新的只读在线生产 DB 备份，在开发副本重放 Phase 3C 的官网证据。旧发布包的重复身份分支返回 identity_review、NULL，复现无法关联的问题。新鲜生产起点其实为 website_lookup_required 且 staging 已指向 1085；这不同于旧演练结束状态，未将两者混淆。
A fresh read-only online backup was used to replay Phase 3C official evidence in development. The old release duplicate-identity branch returned identity_review, NULL, reproducing the missing linkage. Fresh production started with website_lookup_required and a pre-existing staging link to 1085, distinct from the prior rehearsal's end state.

仅 discovery/discovery_service.py 新增规范关联 helper，同时服务正常 A0 和人工复核入口；没有第二套补库管线。SAVEPOINT 保护邮箱更新与 staging 关联的原子性。名称、城市州、同域以及地址或原始可信关联须匹配；组织冲突、多重匹配、发送/退信/抑制/拒绝历史均阻断。非空邮箱不自动替换，冲突进入 identity review。
Only discovery/discovery_service.py adds a canonical linkage helper shared by normal A0 and review paths, not a second pipeline. A SAVEPOINT protects email update and staging linkage atomically. Business identity, city/state, same domain, and address or established linkage must match. Organization conflicts, ambiguity, send/bounce/suppression/rejection history block merging. Nonempty emails are never automatically replaced; conflicts go to identity review.

完整证据必须通过第一方、字面可见邮箱、HTTP/TLS、时间与 hash 校验。已有组织和时区保留，仅补齐空值；UNSET 时区状态只在解析成功且时区一致时补齐。保留 A0 hygiene_failed/manual_review 标志，未放宽 Frozen V2/MX。已有线索关联不计为新增 lead。
Evidence requires first-party provenance, literal visible email, HTTP/TLS success, timestamp, and hash. Existing organization/timezone values are preserved; empty values are filled. UNSET timezone status is resolved only after successful matching resolution. A0 hygiene_failed/manual_review flags remain; frozen V2/MX is unchanged. Existing linkage is not counted as lead creation.

## 真实联网结果 / Real network results

最终 fresh DB: _audit_quarantine/phase3d/network_rc3.db，仅开发、被 Git 忽略。中间两轮仅复用同一商户的不同新副本，用于定位 review 入口及 UNSET 时区；不超过 20 个不同商户。
Final fresh DB: _audit_quarantine/phase3d/network_rc3.db, development-only and Git-ignored. Two earlier rounds used fresh copies for the same merchant to identify the review entrypoint and UNSET timezone issues; fewer than 20 distinct merchants.

REHEARSAL_MERCHANTS_SELECTED = 1
MERCHANT = Instant Replay Sports, Ithaca, NY
STAGING_ID = 293
EXISTING_LEAD_ID = 1085
GOOGLE_MAPS_REQUESTS = 1 logical provider invocation / 1 次逻辑 provider 调用
OFFICIAL_WEBSITE_REQUESTS = 16
DNS_MX_LOOKUPS = 1
NETWORK_ERRORS = 10
FULL_EVIDENCE_RECORDS = 1
LINKED_EXISTING_LEADS = 1
MX_RESULT = ok
V2_ACCEPTED = 1
DEV_SAFE_FSP_INSERTED = 1
SECOND_RUN_IDEMPOTENT = true

Maps 数量是 provider 调用数，不是浏览器底层 HTTP 请求数；provider 允许缓存。16 次官网请求包括重放；10 次失败是可选路径并且 fail-closed，不用于证据。成功首页提供完整证据。全部轮次仅 1 个不同商户。
Maps count represents provider calls, not browser-level HTTP traffic; provider caching is permitted. The 16 site requests include replay; 10 failed optional paths fail closed and do not supply evidence. The successful homepage supplies the full record. All rounds use one distinct merchant.

## 完整证据 / Complete evidence

requested_url = http://ithacainstantreplaysports.com
final_url = https://ithacainstantreplaysports.com/
http_status = 200
http_success = true
tls_success = true
fetched_at = 2026-09-09T06:37:36.603096+00:00
email = ithacainstantreplaysports@yahoo.com
email_source_type = official_page_visible
content_hash = c44dbf0f03495fdcbd76dcdbb5510b05078f10f1bf0f0dba323816cbcee73827
visible_text_excerpt = with WordPress managed by IONOS Triphammer 607.277.7366 | The Rink 607.216.0056 ithacainstantreplaysports@yahoo.com IthacaInstantReplaySports@yahoo.com Facebook Instagram Facebook Instagram Home About Us On Going Promoti

邮箱由正常官网抓取产生，未将邮箱种入网络演练 DB。证据保留在 raw_payload_json，并映射已有 lead 的 evidence 字段；无 live FSP 或授权。
The normal official-site fetch extracted the email; it was not seeded into the network rehearsal DB. Evidence remains in raw_payload_json and existing-lead evidence columns. No live FSP or authorization was created.

## 测试与安全 / Tests and safety

FULL_SUITE_PASS = 312
SUBTESTS_PASS = 59
FULL_SUITE_FAIL = 0
FULL_SUITE_ERROR = 0
FROZEN_FILES_CHANGED = 0
PRODUCTION_FILES_CHANGED = 0
PRODUCTION_DB_WRITES = 0
REAL_SMTP_CONNECTIONS = 0
REAL_IMAP_CONNECTIONS = 0
SCHEDULER_CHANGES = 0

新增 9 项测试覆盖空邮箱合并、同邮箱重放、不同邮箱、不同位置/组织、发送/抑制/退信/拒绝历史、失败 HTTP/TLS、关联失败回滚、review 入口和时区。原并发测试仍通过。未猜测邮箱、未接受隐藏脚本邮箱、未提升第三方/目录/身份不匹配证据。
Nine new tests cover empty-email merge, same-email replay, conflicting email, different location/organization, send/suppression/bounce/rejection history, failed HTTP/TLS, rollback on linkage failure, review entrypoint, and timezone. Existing concurrency tests pass. No guessed, hidden-script, third-party/directory, or identity-mismatched email was promoted.

## 发布包与复现 / Package and reproducibility

PHASE3_RELEASE_PACKAGE 仅含六个制品，bd_db.py 为选择性 patch；在隔离副本 git apply 成功，目标 SHA 匹配。无 schema 迁移。新的清单替代旧 Phase 3B/3C 目标 hash；旧报告仅历史参考。
PHASE3_RELEASE_PACKAGE contains six artifacts only, with a selective bd_db.py patch. git apply succeeded in an isolated copy and the target SHA matched. No schema migration. The new manifest supersedes old Phase 3B/3C target hashes; old reports are historical.

开发验证命令 / Development validation commands:
- python -m pytest -q
- python phase3d_validation.py network _audit_quarantine/phase3d/NEW_FRESH_COPY.db
- python -I build_phase3_release.py

第二条仅对新的只读在线备份产出的开发副本运行；需受控联网许可，最多固定该 1 个商户，禁止生产 DB 路径。生产备份与部署步骤沿用双语 Phase 3C runbook，执行前替换包路径和所有目标 hash；本次未执行部署命令。
Run the second command only against a development copy produced by a fresh read-only online backup, under controlled network authorization. It selects the fixed one merchant and rejects production DB paths. Use the bilingual Phase 3C runbook for backup/deployment after replacing package paths and all target hashes; no deployment command was executed.
