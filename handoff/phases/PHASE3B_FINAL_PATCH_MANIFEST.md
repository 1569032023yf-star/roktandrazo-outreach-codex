# Phase 3B 最终生产补丁清单 / Phase 3B Final Production Patch Manifest

生成时间 / Generated: 2026-09-08  
生产根目录 / Production root: `C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach`  
开发根目录 / Development root: `C:\Users\15690\Documents\ChatGPT\线下\roktandrazo-outreach-dev`  
状态 / Status: **REVIEW ARTIFACT ONLY — NOT DEPLOYED / 仅供审查，未部署**

## 放行结论 / Release-blocker conclusion

中文：Phase 3A 的两个 blocker 已在开发中关闭。stale job cleanup 与 replacement insertion 现在位于同一个 `BEGIN IMMEDIATE` 事务中，中间没有 commit/release gap；完整官方邮箱证据使用现有 `lead_discovery_results.raw_payload_json` 的独立 `official_email_evidence` 对象持久化，不需要 schema 变更。重复 provider upsert 会合并新 provider payload 并保留该证据对象。

English: Both Phase 3A blockers are closed in development. Stale job cleanup and replacement insertion now share one `BEGIN IMMEDIATE` transaction with no intervening commit/release gap. The complete official-email evidence contract is persisted in a dedicated `official_email_evidence` object inside the existing `lead_discovery_results.raw_payload_json`, requiring no schema change. Duplicate provider upserts merge new provider payload while preserving this evidence object.

## 最终生产文件清单 / Final production file manifest

### 1. `bd_db.py`

```text
PATH = bd_db.py
ACTION = SELECTIVE_PATCH_ONLY
PRODUCTION_BASELINE_SHA256 = 5C18DBD91871EEC3AE742C0730D65294F87E84DB720ADA3C2E86860F96B3ADAB
TARGET_SHA256 = C06FE7EBB3D6330BFCCF078634C5AB6DC16563423E8E975E44DA859AAA7CE0C7
```

`PATCH_SCOPE =`

- 中文：在 `insert_lead` 写入映射中加入既有列 `organization_key`、`recipient_timezone`、`timezone_status`。English: Map the existing organization/timezone columns during lead insertion.
- 中文：用 `BEGIN IMMEDIATE`、UTC 时间和 holder ownership 实现 `acquire_run_lock`/`release_run_lock`。English: Use `BEGIN IMMEDIATE`, UTC timestamps, and holder ownership for run locks.
- 中文：`start_job_run` 在同一事务内读取 active run、严格按 `age > stale_after_seconds` 判 stale、标记旧 run terminal、插入 replacement，再一次性 commit；异常统一 rollback。English: In one transaction, inspect the active run, apply the strict UTC stale boundary, mark stale terminal, insert the replacement, then commit once; any exception rolls the whole transaction back.
- 中文：`now_utc`/`stale_after_seconds` 仅为确定性测试 seam，现有调用保持兼容。English: `now_utc` and `stale_after_seconds` are deterministic test seams; existing callers remain compatible.

**禁止 / Forbidden:** 不得整文件复制开发版 `bd_db.py`；不得带入 `.development-copy` 检测、`development_safety` 导入、开发 DB path/URI guard 或只读 URI 特例。目标哈希通过“生产文件 `def init_db()` 之前的原始前缀 + 开发文件从 `def init_db()` 起的已批准生产逻辑”按 UTF-8 无 BOM 计算。 / Do not copy the development file wholesale or include development guards. The target hash is calculated from the untouched production prefix before `def init_db()` plus approved development logic from `def init_db()` onward, encoded as UTF-8 without BOM.

### 2. `bd_orchestrator.py`

```text
PATH = bd_orchestrator.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = 3B8DC6355C85476CD0277A1F484A09B94D10F8B89C4D3C82D57C58D389C3FE74
TARGET_SHA256 = 49E38BB1D80832E65F33752D4F7B0E64F5DF41753DC6056B4D1A5A2446ACECDC
PATCH_SCOPE = holder-aware unlock; duplicate job fail-closed; Inventory Discovery -> Website Resolution -> Staging Postprocess
```

中文：重复 stage/date 作业在进入业务 stage 前退出；Inventory 复用同一连接和 service，并在邮件提取前运行官网解析。 / English: Duplicate stage/date jobs exit before business execution; Inventory reuses one connection/service and runs website resolution before email extraction.

### 3. `discovery/discovery_service.py`

```text
PATH = discovery/discovery_service.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = CC8D9C6B1E4E7C4FD72F43BDF61AD284BBADEC64FABD0FA1139E7F8755EF4627
TARGET_SHA256 = B08761C83BA25A9E51CF45EA53DF8CAAA74FD29765469C6791672BFD65F5BAF3
PATCH_SCOPE = website resolution; visible-only extraction; HTTP/TLS/same-party fail-closed; complete evidence persistence; replay-safe metadata merge; organization/timezone enrichment
```

中文：纯字符串 fetch 结果不能证明 HTTP/TLS，禁止作为 first-party evidence；只有成功的结构化 fetch、同源 final URL 和可见文本中的字面邮箱才可生成 `official_email_evidence`。 / English: Plain-string fetch results cannot prove HTTP/TLS and cannot become first-party evidence. Only a successful structured fetch, same-party final URL, and a literal email in visible text can create `official_email_evidence`.

### 4. `discovery/providers/browser_maps.py`

```text
PATH = discovery/providers/browser_maps.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = 4530CD188E7ACA2AEE83CEF1CDA1B2324587B68342980B19ADCF5380591744C6
TARGET_SHA256 = 245ED26C92A1624CB8F1BC1754F1DF1EFC887D4343B86BA0CEEF769DC040D31A
PATCH_SCOPE = constructor mode default None so existing BROWSER_MAPS_MODE is authoritative
```

### 5. `history_crosscheck.py`

```text
PATH = history_crosscheck.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = 88FEF144EB4DCF88A318F8256FC1266F0B025350EC0BDC209DA4BF453D52F776
TARGET_SHA256 = 0BA0D0CC25FE3BAA2404B31B8A01070AB02CB6D8CF8588CF3F68F527EFD60631
PATCH_SCOPE = address-based location identity; do not collapse distinct locations on shared chain phone; retain organization history controls
```

### 6. `discovery/website_resolver.py`

```text
PATH = discovery/website_resolver.py
ACTION = ADD
PRODUCTION_BASELINE_SHA256 = MISSING
TARGET_SHA256 = FFBCACDF68992217B6680B19E69713CED045684D2A48F7375DB1E092F667B33F
PATCH_SCOPE = deterministic provider website resolution; directory/social rejection; name/phone/city-state identity scoring; minimum score 80
```

## 证据持久化契约 / Persisted evidence contract

存储位置 / Storage location:

```text
lead_discovery_results.raw_payload_json
└── official_email_evidence
    ├── requested_url
    ├── final_url
    ├── http_status
    ├── http_success
    ├── tls_success
    ├── fetched_at
    ├── visible_text_excerpt
    ├── content_hash
    ├── email
    └── email_source_type
```

中文：该命名空间与 provider 原始字段分离，无字段含义冲突；现有 reader 会忽略未知 JSON key，现有 lead 列继续保存 `evidence_url`、`evidence_snippet`、`evidence_method`、`evidence_checked_at`、`email` 与 `email_source_type`，因此向后兼容且不丢失。`content_hash` 是 UTF-8 可见文本的 SHA-256。 / English: The namespace is separate from provider fields and unambiguous. Existing readers ignore unknown JSON keys, while the existing lead evidence/email columns remain populated, so storage is backward-compatible and lossless. `content_hash` is SHA-256 of UTF-8 visible text.

`DB_MIGRATION_REQUIRED = false`

中文：不新增表、列、索引或 `system_config` 预置键；无需生成或运行 migration。 / English: No new table, column, index, or pre-seeded `system_config` key is required; no migration is generated or run.

## 验证证据 / Validation evidence

### 全量回归 / Full regression

```text
FULL_SUITE_PASS = 303
FULL_SUITE_FAIL = 0
FULL_SUITE_ERROR = 0
SUBTESTS_PASS = 47
DURATION = 44.27s
```

### 事务并发 / Transaction concurrency

中文：覆盖 fresh 两线程注册、stale 两线程 takeover、严格 UTC 7200/7201 秒边界、重复 run_id 导致 INSERT 失败时 stale UPDATE 整体 rollback。两线程 takeover 恰好一个 winner；fresh loser 不新增 job，也不更新 system state。 / English: Coverage includes fresh two-thread registration, stale two-thread takeover, strict UTC 7200/7201-second boundary, and full stale-update rollback when replacement insertion fails. Exactly one takeover contender wins; a fresh loser creates no job and does not update system state.

```text
STALE_TAKEOVER_ATOMIC = true
CONCURRENCY_PASS = true
```

### 真实正向路径 / Real positive path

证据文件 / Evidence file: `audit_evidence/phase3b_positive_email_validation_final.json`

```text
MERCHANT = Noble Knight Games
REAL_MERCHANT_FOUND = true
OFFICIAL_WEBSITE_VERIFIED = true
EXTRACTED_EMAIL = contact@nobleknight.com
REQUESTED_URL = http://www.nobleknight.com/contact
FINAL_URL = https://www.nobleknight.com/contact
HTTP_STATUS = 200
HTTP_SUCCESS = true
TLS_SUCCESS = true
VISIBLE_EXCERPT_CONTAINS_EMAIL = true
CONTENT_HASH_LENGTH = 64
EMAIL_SOURCE_TYPE = official_page_visible
MX_PASS = true
FROZEN_V2_PASS = true
DEV_SAFE_FSP_CREATED = 1
EVIDENCE_PERSISTED_AFTER_SECOND_RUN = true
POSITIVE_PATH_PASS = true
```

### 负向安全与幂等 / Negative safety and idempotency

中文：单元/子测试验证 HTTP 失败、TLS 失败、跨域 redirect、隐藏/script-only 邮箱、directory/social URL、identity mismatch 均不提升；真实 one-shot 报告也确认所有负向标志为 false。 / English: Unit/subtests prove that failed HTTP, failed TLS, cross-domain redirects, hidden/script-only email, directory/social URLs, and identity mismatch are never promoted. The real one-shot also reports every negative flag as false.

```text
NEGATIVE_SAFETY_PASS = true
DUPLICATE_LEADS = 0
DUPLICATE_ORGS = 0
DUPLICATE_DEV_FSP = 0
IDEMPOTENCY_PASS = true
REAL_SMTP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
```

## 冻结链 / Frozen chain

| 文件 / File | SHA-256（生产=开发） / SHA-256 (production = development) |
|---|---|
| `bd_sender.py` | `002D68A1E76D5F96AF6FDBABDCE54DA0AF3A93077D8A504DDD106A41FD018280` |
| `daily_session.py` | `F4559A34E87C9FCAB0C83FA92B6E4FBA4C0F5E284B77BB03F98AD1318C4088AF` |
| `preflight_gate.py` | `B1F44038C346BBF022A9D40575E330A1A73471A6DAFE0605D17EEACF3B8EF105` |
| `campaign_eligible_v2.py` | `1143BEDF563C0F76B883359362FFB2C2EA11C375FD923DC59768C5529CF3AD34` |
| `final_send_plan.py` | `26DE2F017390EDA767BEDDFE8FBD6BC438B78DDB430EEEBC4B96C72AA41D327F` |

`FROZEN_FILES_CHANGED = 0`  
`FROZEN_FILES_IN_PATCH = 0`

## 部署时回滚资产精确检查表 / Exact deployment-time rollback asset checklist

本阶段不创建下列生产资产。 / None of the following production assets is created in this phase.

| 资产 / Asset | 部署时精确位置或要求 / Exact deployment-time location or requirement | 验证 / Verification |
|---|---|---|
| Deployment run ID | `phase3b-prod-<YYYYMMDDTHHMMSSZ>` | 全局唯一，写入部署日志及 Inventory 验证记录 / globally unique and recorded in deployment and Inventory logs |
| 备份根目录 / Backup root | `C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\phase3b_release_backups\<DEPLOYMENT_RUN_ID>\` | 必须在生产项目目录之外 / must remain outside production project root |
| 数据库备份 / DB backup | `<backup root>\database\bd_leads.db`，源为 `<PRODUCTION_ROOT>\data\bd_leads.db`，使用 SQLite online backup API / source via SQLite online backup API | 备份连接 `PRAGMA integrity_check = ok`；核心表/schema assertion；记录 SHA-256 与字节数 / integrity, core schema, hash and size |
| 原始文件副本 / Original files | `<backup root>\original_files\` 下保存上述 5 个既有文件的原始相对路径 / original relative paths for five existing files | 每个副本 SHA 等于本 manifest 的 production baseline / each copy matches baseline SHA |
| Hash manifest | `<backup root>\production-baseline.sha256` 与 `<backup root>\production-target.sha256` | 应用前/后分别逐项精确匹配 / exact pre/post match |
| 新文件 manifest | `<backup root>\new-files.txt` | 仅一行 `discovery/website_resolver.py|PREVIOUSLY_MISSING` / exactly one entry |
| Scheduler inventory | `<backup root>\scheduler-inventory.json` | 同时枚举 WorkBuddy + Windows Tasks；Inventory/PreSend/Outreach/PostSend/EndOfDay 每阶段恰好一个 active authority / enumerate both systems and prove one authority per stage |
| `.env` 保护副本 / Protected `.env` copy | `<backup root>\secrets\.env` | ACL 限制、只记录 hash、不在日志输出内容 / restricted ACL, hash only, never log contents |
| Runtime snapshot | `<backup root>\runtime-state.json` | 无相关 running `job_runs`、无活动 run lock、记录依赖版本与冻结哈希 / no active run/lock; versions and frozen hashes recorded |

中文：只有上述资产全部存在、可读且验证通过后，部署执行时的 `ROLLBACK_READY` 才能设为 true。当前只完成计划，不创建生产备份。 / English: Operational `ROLLBACK_READY` becomes true only after every asset exists, is readable, and passes verification. This phase finalizes the plan only and creates no production backup.

## 排除项 / Exclusions

不得部署 / Must not deploy: `development_safety.py`, `sitecustomize.py`, development `.env`, `dev_fsp.py`, `safe_replenishment.py`, test DBs, `dev_safe_fsp`, tests/fixtures, Phase 2C/2D/3B harnesses, reports, browser caches, PID/status/log/runtime artifacts, or `requirements-dev.txt`.

## 最终状态 / Final status

```text
STALE_TAKEOVER_ATOMIC = true
FULL_EVIDENCE_PERSISTENCE = true
DB_MIGRATION_REQUIRED = false

FULL_SUITE_PASS = 303
FULL_SUITE_FAIL = 0
FULL_SUITE_ERROR = 0
POSITIVE_PATH_PASS = true
NEGATIVE_SAFETY_PASS = true
IDEMPOTENCY_PASS = true
CONCURRENCY_PASS = true

FROZEN_FILES_CHANGED = 0

FINAL_PATCH_MANIFEST_READY = true
READY_FOR_EXPLICIT_DEPLOYMENT_APPROVAL = true
```

**STOP — DO NOT DEPLOY / 停止，不部署。**
