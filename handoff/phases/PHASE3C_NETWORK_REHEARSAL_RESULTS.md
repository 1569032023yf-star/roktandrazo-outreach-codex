# Phase 3C-NET 受控联网演练结果 / Controlled Network Rehearsal Results

## 判定 / Decision

中文：受控联网 Inventory 演练本身通过，20 个商户上限与所有安全边界均满足。正常流程创建了 1 条完整的官网可见邮箱证据，但 staging 记录没有关联到已存在的同身份 lead，因而冻结 V2 无 lead 可评估、MX 未触发、SAFE FSP 候选为 0。按验收公式，当前不能批准生产部署。

English: The controlled networked Inventory rehearsal passed and respected the 20-merchant cap and every safety boundary. The normal flow created one complete visible official-site email evidence record, but the staging record was not linked to the existing same-identity lead. Frozen V2 therefore had no lead to evaluate, MX was not triggered, and SAFE FSP candidates remained zero. The acceptance formula does not permit production deployment.

## 实际计数 / Actual counts

```text
REHEARSAL_MERCHANTS_SELECTED = 20
GOOGLE_MAPS_REQUESTS = 16
OFFICIAL_WEBSITE_REQUESTS = 8
DNS_MX_LOOKUPS = 0

NETWORK_ERRORS = 6

NEW_UNIQUE_PLACES = 0
WEBSITE_VERIFIED = 1
VISIBLE_FIRST_PARTY_EMAILS = 1
FULL_EVIDENCE_RECORDS = 1

V2_ACCEPTED = 0
MX_ACCEPTED = 0
SAFE_FSP_CANDIDATES_AFTER_REHEARSAL = 0
```

`NETWORK_ERRORS=6` 为真实、fail-closed 的 Maps/官网请求错误；其中观察到一次 Google Maps `ERR_NETWORK_CHANGED`。它们没有导致越界接受。 / `NETWORK_ERRORS=6` contains real fail-closed Maps/site request errors, including one observed Google Maps `ERR_NETWORK_CHANGED`; none caused unsafe promotion.

## 正向证据 / Positive evidence

```text
BUSINESS_NAME = Instant Replay Sports
OFFICIAL_WEBSITE = http://ithacainstantreplaysports.com
REQUESTED_URL = http://ithacainstantreplaysports.com
FINAL_URL = https://ithacainstantreplaysports.com/
HTTP_STATUS = 200
HTTP_SUCCESS = true
TLS_SUCCESS = true
EMAIL = ithacainstantreplaysports@yahoo.com
EMAIL_SOURCE_TYPE = official_page_visible
CONTENT_HASH = c44dbf0f03495fdcbd76dcdbb5510b05078f10f1bf0f0dba323816cbcee73827
VISIBLE_EXCERPT_CONTAINS_EMAIL = true
SAME_PARTY_FINAL_URL = true
```

中文：邮箱为免费邮箱域名，但确实逐字显示在已验证的第一方官网页面，因此证据本身符合现有 E3 路径要求；未猜测、未从脚本隐藏内容或第三方目录提取。 / English: Although the address uses a free-mail domain, it is literally visible on the verified first-party official site and therefore satisfies the existing E3 evidence path. It was not guessed or extracted from hidden script content or a third-party directory.

## 安全结果 / Safety results

```text
GUESSED_EMAIL = 0
THIRD_PARTY_EMAIL = 0
DIRECTORY_SOCIAL_AS_OFFICIAL = 0
IDENTITY_MISMATCH = 0

REAL_SMTP_CONNECTIONS = 0
REAL_IMAP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
SCHEDULER_CHANGES = 0
FROZEN_FILES_CHANGED = 0
```

## 唯一真实 blocker / Sole real blocker

中文：`lead_discovery_results.id=293` 获得完整 `official_email_evidence`，但 `linked_lead_id` 仍为 `NULL`。DB 副本中已有 `leads.id=1085`（同名、同官网），其邮箱为空且处于 `manual_review_needed / identity_review`。插入路径因现有身份记录而未创建/更新 lead，证据只保留在 staging JSON 中。结果是本次证据无法进入 frozen V2/MX。

English: `lead_discovery_results.id=293` received complete `official_email_evidence`, but `linked_lead_id` remained `NULL`. The DB copy already contains `leads.id=1085` with the same identity and official site, an empty email, and `manual_review_needed / identity_review`. The insert path did not create or update the lead because that identity already existed, leaving evidence only in staging JSON. Consequently, the evidence could not enter frozen V2/MX.

没有手工复制证据、手工更新 lead、创建 live authorization 或 Final Send Plan。 / No evidence was manually copied, no lead was manually updated, and no live authorization or Final Send Plan was created.

```text
INVENTORY_REHEARSAL_PASS = true
READY_FOR_PRODUCTION_DEPLOYMENT = false
```

原始机器可读结果 / Raw machine-readable result: `audit_evidence/phase3c_network_rehearsal.json`.

