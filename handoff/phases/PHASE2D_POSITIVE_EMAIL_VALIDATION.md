# Phase 2D Positive Official Email Path Validation | Phase 2D 官方邮箱正向路径验证

## Final verdict | 最终判定

The missing positive first-party email evidence is now complete. The development release candidate is ready for **production promotion review**, but this result does not authorize deployment, production database changes, scheduler changes, or real outreach.

缺失的第一方官方邮箱正向证据现已补齐。开发发布候选现可进入**生产晋级评审**，但本结果不授权部署、生产数据库变更、调度器变更或真实外联。

```text
READY_FOR_PRODUCTION_PROMOTION_REVIEW = true
DEPLOYMENT_AUTHORIZED = false
```

## Deterministic merchant selection | 确定性商户选择

Noble Knight Games was selected because it is a real US tabletop-game retail merchant within the existing ICP and its official contact page independently publishes a visible contact email. The known email was used only to select the merchant. It was not present in the validation script, seeded into SQLite, passed to the extractor, or hardcoded into production logic.

选择 Noble Knight Games，是因为它属于现有 ICP 范围内的真实美国桌游零售商，且其官方联系页可独立确认公开显示联系邮箱。已知邮箱仅用于筛选商户；它没有出现在验证脚本中、没有预置进 SQLite、没有传给提取器，也没有硬编码进生产逻辑。

```text
MERCHANT = Noble Knight Games
MAPS_QUERY = board game store Fitchburg WI
KNOWN_EMAIL_SEEDED = false
```

The first exact-name Maps attempt returned zero result articles and stopped before website/MX/V2 processing. That evidence remains in `audit_evidence/phase2d_positive_email_validation.json`. RC2 retained the same merchant and used the existing standard query family; its successful evidence is in `audit_evidence/phase2d_positive_email_validation_rc2.json`.

首次精确名称 Maps 尝试返回零条结果，并在官网/MX/V2 处理前停止；证据保留于 `audit_evidence/phase2d_positive_email_validation.json`。RC2 保持同一商户不变，改用现有标准查询族；成功证据位于 `audit_evidence/phase2d_positive_email_validation_rc2.json`。

## Normal discovery and official identity | 正常发现与官网身份

BrowserMaps direct returned Noble Knight Games at 2835 Commerce Park Dr, Fitchburg, Wisconsin, with the merchant website. The normal Discovery path deduplicated and staged the merchant, and official identity verification passed using the same-party domain and merchant identity evidence.

BrowserMaps direct 返回位于 Wisconsin 州 Fitchburg、2835 Commerce Park Dr 的 Noble Knight Games 及其商户官网。正常 Discovery 路径完成去重与 staging，并通过同源域名及商户身份信号完成官网身份验证。

```text
REAL_MERCHANT_FOUND = true
OFFICIAL_WEBSITE_VERIFIED = true
OFFICIAL_WEBSITE = http://www.nobleknight.com
```

## Real visible official-email evidence | 真实可见官方邮箱证据

The existing extractor requested the normal `/contact` path. It followed the same-party HTTP-to-HTTPS redirect, received HTTP 200 with successful TLS verification, and extracted the email from visible page text. The literal evidence excerpt contains the extracted address.

现有提取器请求正常 `/contact` 路径，跟随同源 HTTP 到 HTTPS 重定向，收到 HTTP 200 且 TLS 验证成功，并从可见页面文本中提取邮箱。字面证据 excerpt 包含提取出的地址。

```text
requested_url = http://www.nobleknight.com/contact
final_url = https://www.nobleknight.com/contact
HTTP_STATUS = 200
HTTP_SUCCESS = true
TLS_SUCCESS = true
fetched_at = 2026-09-08T07:10:13.824897+00:00
email = contact@nobleknight.com
email_source_type = official_page_visible
content_hash = 84796bf0e33791f0b867b4ff82476053430efe8b22ea4125abba005b0604e50a
```

Literal visible excerpt / 字面可见 excerpt：

```text
ne 608-758-9901 Phone Hours: Mon-Fri 9am - 5pm CST Sat 9am - 12 Noon CST E-mail contact@nobleknight.com contact@nobleknight.com Storefront Click Here to see our Storefront Hours & Location Send us a message First Name La
```

```text
EMAIL_FOUND_FROM_PAGE = true
REAL_OFFICIAL_EMAIL_EXTRACTION_PASS = true
EXTRACTED_EMAIL = contact@nobleknight.com
EVIDENCE_URL = https://www.nobleknight.com/contact
VISIBLE_EVIDENCE_PASS = true
```

## Negative safety gates | 负向安全门禁

No guessed, script-only, directory, social-media, identity-mismatched, or failed HTTP/TLS evidence was accepted. No extraction or eligibility rule was weakened.

没有接受猜测邮箱、仅脚本可见邮箱、目录邮箱、社交媒体邮箱、身份不匹配记录或 HTTP/TLS 失败证据。提取与资格规则均未放宽。

```text
GUESSED_EMAIL_ACCEPTED = false
HIDDEN_SCRIPT_EMAIL_ACCEPTED = false
DIRECTORY_OR_SOCIAL_EMAIL_ACCEPTED = false
IDENTITY_MISMATCH_PROMOTED = false
FAILED_HTTP_OR_TLS_ACCEPTED = false
```

## Controlled MX and frozen V2 | 受控 MX 与冻结 V2

The extracted domain was resolved through the controlled public DNS path. The unchanged frozen `campaign_eligible_v2` returned Tier E1, no blockers, and the `CAMPAIGN_ELIGIBLE_V2` pool.

提取出的邮箱域名通过受控公共 DNS 路径解析。未改变的冻结 `campaign_eligible_v2` 返回 Tier E1、零 blocker，并进入 `CAMPAIGN_ELIGIBLE_V2` 池。

```text
CONTROLLED_MX_PATH_EXECUTED = true
MX_RESULT = ok
MX_PASS = true
V2_DECISION = eligible / CAMPAIGN_ELIGIBLE_V2 / E1
FROZEN_V2_PASS = true
```

## Development Safe FSP and idempotency | 开发 Safe FSP 与幂等性

The eligible candidate was materialized only into the development `dev_safe_fsp`. Replaying the exact same merchant produced one duplicate-place detection and no additional lead, organization, or FSP row.

合格候选仅物化到开发 `dev_safe_fsp`。对完全相同商户再次重放时识别为 duplicate place，没有新增 lead、organization 或 FSP 记录。

```text
DEV_SAFE_FSP_CREATED = 1
DUPLICATE_LEADS = 0
DUPLICATE_ORGS = 0
DUPLICATE_DEV_FSP = 0
SECOND_RUN_IDEMPOTENT = true
```

## Regression and frozen-chain verification | 回归与冻结链验证

```text
FULL_SUITE_TOTAL = 303
FULL_SUITE_PASS = 303
FULL_SUITE_FAIL = 0
FULL_SUITE_ERROR = 0
SUBTEST_PASS = 44
REAL_PHASE2_REGRESSIONS = 0
FROZEN_FILES_CHANGED = 0
```

All five frozen SHA-256 values match the Phase 2 baseline exactly. / 五个冻结文件的 SHA-256 均与 Phase 2 基线完全一致。

## Production safety | 生产安全

```text
REAL_SMTP_CONNECTIONS = 0
REAL_IMAP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
```

All writes were confined to the development root. The WorkBuddy production directory, production database, services, schedulers, automations, SMTP, and outreach were not modified or invoked.

所有写入均限制在开发根目录。WorkBuddy 生产目录、生产数据库、服务、调度器、自动化、SMTP 与外联均未被修改或调用。

## Final output | 最终输出

```text
REAL_MERCHANT_FOUND = true
OFFICIAL_WEBSITE_VERIFIED = true

REAL_OFFICIAL_EMAIL_EXTRACTION_PASS = true
EXTRACTED_EMAIL = contact@nobleknight.com
EVIDENCE_URL = https://www.nobleknight.com/contact
VISIBLE_EVIDENCE_PASS = true

CONTROLLED_MX_PATH_EXECUTED = true
MX_PASS = true
FROZEN_V2_PASS = true

DEV_SAFE_FSP_CREATED = 1

SECOND_RUN_IDEMPOTENT = true

FULL_SUITE_PASS = 303
FROZEN_FILES_CHANGED = 0

REAL_SMTP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0

READY_FOR_PRODUCTION_PROMOTION_REVIEW = true
```

STOP. Do not deploy. / 停止。不得部署。

