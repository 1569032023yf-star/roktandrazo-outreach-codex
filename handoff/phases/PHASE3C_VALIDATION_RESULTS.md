# Phase 3C 最终部署前验证 / Final Pre-deployment Validation

## 结论 / Conclusion

中文：精确六文件发布包已建立；在新鲜生产源码副本上的应用和字节级目标 SHA 校验通过；冻结链未变化；开发专用制品扫描为零；全套 303 项测试及定向安全回归通过。生产数据库已通过只读 SQLite online backup 复制并校验完整性。随后获授权的联网演练在 20 个商户上限内完成并创建 1 条完整证据，但该 staging 证据未关联到已有同身份 lead，V2/MX 和 SAFE 候选因此仍为 0，当前不得标记为可部署。

English: The exact six-artifact release package was built and applied to a fresh production source copy with byte-for-byte target SHA matches. Frozen files remained unchanged, development-only artifact scans were zero, and all 303 tests plus targeted safety regressions passed. The production DB was copied using a read-only SQLite online backup and passed integrity validation. The subsequently authorized network rehearsal completed within a 20-merchant cap and created one complete evidence record, but that staging evidence was not linked to the existing same-identity lead; V2/MX and SAFE eligibility therefore remained zero. Production readiness cannot be marked true.

## 发布包 / Release package

`PHASE3C_RELEASE_PACKAGE` 恰好包含 / contains exactly:

1. `bd_db.py.patch`
2. `bd_orchestrator.py`
3. `discovery/discovery_service.py`
4. `discovery/providers/browser_maps.py`
5. `history_crosscheck.py`
6. `discovery/website_resolver.py`

所有六个目标 SHA 均与 `PHASE3B_FINAL_PATCH_MANIFEST.md` 一致。`bd_db.py` 使用 selective patch；应用时强制 `core.autocrlf=false`，避免 Windows 换行改写导致字节漂移。 / All six target hashes match the Phase 3B manifest. `bd_db.py` is applied selectively with `core.autocrlf=false` to prevent Windows line-ending drift.

```text
DEVELOPMENT_SAFETY_IMPORTS = 0
DEVELOPMENT_DB_PATHS = 0
TEST_ONLY_IMPORTS = 0
DEV_SAFE_FSP_REFERENCES = 0
SAFE_REPLENISHMENT_REFERENCES = 0
```

## 验证结果 / Validation results

```text
PATCH_REHEARSAL_PASS = true
SOURCE_COPY_TARGET_HASHES_MATCH = 6/6
FROZEN_FILES_CHANGED = 0

PRODUCTION_DB_ONLINE_BACKUP_INTEGRITY = ok
OFFLINE_INVENTORY_JOB_STATUS = completed
OFFLINE_INVENTORY_BROAD_READY = 33/30
OFFLINE_MAIL_CONNECTIONS = 0
OFFLINE_NEW_EVIDENCE_ROWS = 0
OFFLINE_SAFE_FSP_CANDIDATES = 0

FULL_SUITE_PASS = 303
FULL_SUITE_FAIL = 0
FULL_SUITE_ERROR = 0
TARGETED_NEGATIVE_IDEMPOTENCY_CONCURRENCY = 5 passed, 3 subtests passed

POSITIVE_PATH_PASS = true
POSITIVE_MERCHANT = Noble Knight Games
EXTRACTED_EMAIL = contact@nobleknight.com
EVIDENCE_URL = https://www.nobleknight.com/contact
VISIBLE_EVIDENCE_PASS = true
MX_PASS = true
FROZEN_V2_PASS = true
SECOND_RUN_IDEMPOTENT = true
DEV_SAFE_FSP_CREATED = 1
```

正向用例使用固定公开商户，不读取生产 DB；结果位于 `audit_evidence/phase3c_positive_email_validation_rc2.json`。 / The positive case used a fixed public merchant and did not read the production DB; its result is in `audit_evidence/phase3c_positive_email_validation_rc2.json`.

## 联网演练与唯一 blocker / Network rehearsal and sole blocker

```text
PRODUCTION_COPY_NETWORK_PROVIDER_TEST = completed
REHEARSAL_MERCHANTS_SELECTED = 20
GOOGLE_MAPS_REQUESTS = 16
OFFICIAL_WEBSITE_REQUESTS = 8
DNS_MX_LOOKUPS = 0
NETWORK_ERRORS = 6
REAL_OFFICIAL_EMAIL_EVIDENCE_CREATED_IN_PRODUCTION_COPY = 1
FULL_EVIDENCE_RECORDS = 1
V2_ACCEPTED = 0
MX_ACCEPTED = 0
SAFE_FSP_CANDIDATES_AFTER_NETWORKED_REHEARSAL = 0
```

中文：唯一 blocker 是完整 staging 证据未关联到已有的同身份、空邮箱 lead，导致 frozen V2/MX 没有输入。详见 `PHASE3C_NETWORK_REHEARSAL_RESULTS.md`。 / English: The sole blocker is that complete staging evidence was not linked to the existing same-identity lead with an empty email, leaving frozen V2/MX without input. See `PHASE3C_NETWORK_REHEARSAL_RESULTS.md`.

```text
REAL_SMTP_CONNECTIONS = 0
PRODUCTION_DB_WRITES_BY_PHASE3C = 0
PRODUCTION_FILES_CHANGED = 0
READY_FOR_PRODUCTION_DEPLOYMENT = false
```
