# PHASE 4A.3T — Final Post-Fix Production-Copy Inventory Acceptance

## 中文

### 范围与安全

- 基线提交为 `05c0a41919167f0beed531ed7e6b1d40d89a36f1`；本阶段未修改任何源码。
- 从权威生产数据库执行一次只读 SQLite online backup，目标为隔离的开发路径；`PRAGMA integrity_check = ok`。
- 启动前确认 `bd_db.DB_PATH` 与该新鲜副本完全一致：`EFFECTIVE_DB_IS_INTENDED_COPY = true`。
- 只运行了一次标准 `inventory --live`，写入只发生在开发副本。未运行第二次 Inventory，未部署、未恢复调度、未使用 SMTP/IMAP、未创建新的 FSP 或授权。
- 生命周期检查仅按本开发工作区关联的命令行统计：遗留 Playwright 为 0，遗留 Chromium 为 0。

### 运行结果

| 指标 | 结果 |
|---|---:|
| INVENTORY_COMPLETED | true |
| INVENTORY_STATUS | partial |
| STOP_REASON | safe_inventory_gap |
| ACTIVE_CITY_BEFORE / AFTER | Ithaca, NY / Ithaca, NY |
| MAPS_RESULTS_SEEN | 8 |
| NEW_UNIQUE_PLACES / DUPLICATE_PLACES | 0 / 8 |
| QUERY_FAMILIES_COMPLETED / CITY_ADVANCED | 1 / false |
| WEBSITE_RESOLUTION_ATTEMPTS | 10 |
| WEBSITES_RESOLVED | 3 |
| WEBSITE_RESOLUTION_NETWORK_RETRY | 0 |
| WEBSITE_NOT_FOUND / IDENTITY_REVIEW | 2 / 5 |
| DUPLICATE_WEBSITE_BACKFILLED / DUPLICATE_SOURCE_URL_BACKFILLED | 0 / 0 |
| POSTPROCESS_ROWS | 12 |
| OFFICIAL_EMAILS_FOUND / PERSISTED | 1 / 1 |
| FULL_EVIDENCE_CREATED | 1 |
| EXISTING_LEADS_LINKED | 1 |
| V2_ELIGIBLE_UNSENT_BEFORE / AFTER | 0 / 1 |
| READ_ONLY_SAFE_UNIQUE_ORGS_BEFORE / AFTER | 0 / 1 |
| NEW_SAFE_UNIQUE_ORGS | 1 |
| MATERIALIZED_FSP_PLANNED_BEFORE / AFTER | 0 / 0 |
| AUTHORIZATION_CREATED / AUTHORIZATION_ENTRY_COUNT | 0 / 0 |

完整第一方证据的增量来自 Gourdlandia：官方主页可见邮箱被既有证据规则接受，并由冻结 V2 使一个唯一组织进入只读 SAFE 计数。没有因该阶段生成 FSP 或授权。

### 对比 Phase 4A.3P

| 比较项 | 4A.3P | 4A.3T | 增量 |
|---|---:|---:|---:|
| 网站解析网络重试 | 10 | 0 | -10（100% 降低） |
| 已解析官网 | 0 | 3 | +3 |
| 官方邮箱 | 0 | 1 | +1 |
| 完整证据 | 0 | 1 | +1 |
| 只读 SAFE 唯一组织 | 0 | 1 | +1 |

直接 Place 面板修复后，先前的 resolver 网络重试回归已实质消除；剩余的 2 条 `website_not_found` 和 5 条 `identity_review` 保持 fail-closed，没有被错误提升。

### 结论

- `REAL_DOMINANT_FUNNEL_BLOCKER = OFFICIAL_EMAIL_LOW_YIELD`：本轮官网解析已能前进，但只有一条通过完整可见第一方邮箱、证据和冻结 V2。
- `LEAD_FACTORY_THROUGHPUT_PROVEN = true`：有 3 个官网解析、1 个官方邮箱/完整证据、1 个已关联线索和 SAFE 从 0 到 1 的真实前进，且没有安全回归。
- `READY_FOR_CONTROLLED_PRODUCTION_PATCH = true`：单次标准 Inventory 完成、网络重试显著改善、既有正向对照的错误域名为 0、生命周期干净、V2/MX 未改且生产未触及。
- SAFE 为 1/50，故没有触发 40 收件人副本模拟；这不是生产补丁验收失败，而是后续发送验收的库存门槛尚未满足。

## English

### Scope and safety

- Baseline commit: `05c0a41919167f0beed531ed7e6b1d40d89a36f1`; no source code was changed in this phase.
- One read-only SQLite online backup was made from the authoritative production database into an isolated development path; `PRAGMA integrity_check = ok`.
- Before startup, `bd_db.DB_PATH` exactly matched that fresh copy: `EFFECTIVE_DB_IS_INTENDED_COPY = true`.
- Exactly one canonical `inventory --live` was run and all writes stayed in the development copy. There was no second Inventory, deployment, scheduler resume, SMTP/IMAP use, new FSP, or new authorization.
- Lifecycle counts are limited to command lines associated with this development workspace: orphan Playwright = 0 and orphan Chromium = 0.

### Run results

| Metric | Result |
|---|---:|
| INVENTORY_COMPLETED | true |
| INVENTORY_STATUS | partial |
| STOP_REASON | safe_inventory_gap |
| ACTIVE_CITY_BEFORE / AFTER | Ithaca, NY / Ithaca, NY |
| MAPS_RESULTS_SEEN | 8 |
| NEW_UNIQUE_PLACES / DUPLICATE_PLACES | 0 / 8 |
| QUERY_FAMILIES_COMPLETED / CITY_ADVANCED | 1 / false |
| WEBSITE_RESOLUTION_ATTEMPTS | 10 |
| WEBSITES_RESOLVED | 3 |
| WEBSITE_RESOLUTION_NETWORK_RETRY | 0 |
| WEBSITE_NOT_FOUND / IDENTITY_REVIEW | 2 / 5 |
| DUPLICATE_WEBSITE_BACKFILLED / DUPLICATE_SOURCE_URL_BACKFILLED | 0 / 0 |
| POSTPROCESS_ROWS | 12 |
| OFFICIAL_EMAILS_FOUND / PERSISTED | 1 / 1 |
| FULL_EVIDENCE_CREATED | 1 |
| EXISTING_LEADS_LINKED | 1 |
| V2_ELIGIBLE_UNSENT_BEFORE / AFTER | 0 / 1 |
| READ_ONLY_SAFE_UNIQUE_ORGS_BEFORE / AFTER | 0 / 1 |
| NEW_SAFE_UNIQUE_ORGS | 1 |
| MATERIALIZED_FSP_PLANNED_BEFORE / AFTER | 0 / 0 |
| AUTHORIZATION_CREATED / AUTHORIZATION_ENTRY_COUNT | 0 / 0 |

The full visible first-party evidence increment was for Gourdlandia. Its official-homepage email was accepted by the existing evidence rules and one unique organization entered the read-only SAFE count through frozen V2. No FSP or authorization was created in this phase.

### Comparison with Phase 4A.3P

| Comparison | 4A.3P | 4A.3T | Delta |
|---|---:|---:|---:|
| Website-resolution network retries | 10 | 0 | -10 (100% reduction) |
| Resolved official websites | 0 | 3 | +3 |
| Official emails | 0 | 1 | +1 |
| Full evidence records | 0 | 1 | +1 |
| Read-only SAFE unique organizations | 0 | 1 | +1 |

Following the direct-Place-panel repair, the prior resolver network-retry regression was materially removed. The remaining two `website_not_found` and five `identity_review` outcomes remain fail-closed and were not promoted.

### Decision

- `REAL_DOMINANT_FUNNEL_BLOCKER = OFFICIAL_EMAIL_LOW_YIELD`: website resolution now makes progress, but only one row completed the visible first-party email, evidence, and frozen-V2 path.
- `LEAD_FACTORY_THROUGHPUT_PROVEN = true`: three website resolutions, one official email/full evidence record, one linked existing lead, and SAFE growth from 0 to 1 demonstrate real progress without a safety regression.
- `READY_FOR_CONTROLLED_PRODUCTION_PATCH = true`: the single canonical Inventory completed, network retries materially improved, prior positive controls retained zero wrong-domain matches, lifecycle cleanup is clean, V2/MX are unchanged, and production was untouched.
- SAFE is 1/50, so the copy-only 40-recipient simulation was not triggered. This is not a production-patch acceptance failure; it remains an inventory prerequisite for later send acceptance.

### Required final fields / 最终字段

```text
EFFECTIVE_DB_IS_INTENDED_COPY = true
INVENTORY_COMPLETED = true
INVENTORY_STATUS = partial
STOP_REASON = safe_inventory_gap
MAPS_RESULTS_SEEN = 8
NEW_UNIQUE_PLACES = 0
DUPLICATE_PLACES = 8
WEBSITE_RESOLUTION_ATTEMPTS = 10
WEBSITES_RESOLVED = 3
WEBSITE_RESOLUTION_NETWORK_RETRY = 0
WEBSITE_NOT_FOUND = 2
IDENTITY_REVIEW = 5
OFFICIAL_EMAILS_FOUND = 1
OFFICIAL_EMAILS_PERSISTED = 1
FULL_EVIDENCE_CREATED = 1
EXISTING_LEADS_LINKED = 1
V2_ELIGIBLE_UNSENT_BEFORE = 0
V2_ELIGIBLE_UNSENT_AFTER = 1
READ_ONLY_SAFE_UNIQUE_ORGS_BEFORE = 0
READ_ONLY_SAFE_UNIQUE_ORGS_AFTER = 1
NEW_SAFE_UNIQUE_ORGS = 1
NETWORK_RETRY_REDUCTION = 10
WEBSITE_RESOLUTION_GAIN = 3
OFFICIAL_EMAIL_GAIN = 1
EVIDENCE_GAIN = 1
SAFE_GAIN = 1
MATERIALIZED_FSP_PLANNED = 0
AUTHORIZATION_CREATED = 0
AUTHORIZATION_ENTRY_COUNT = 0
REAL_DOMINANT_FUNNEL_BLOCKER = OFFICIAL_EMAIL_LOW_YIELD
LEAD_FACTORY_THROUGHPUT_PROVEN = true
READY_FOR_CONTROLLED_PRODUCTION_PATCH = true
ORPHAN_PLAYWRIGHT_PROCESS_COUNT = 0
ORPHAN_CHROMIUM_PROCESS_COUNT = 0
V2_POLICY_CHANGED = false
MX_POLICY_CHANGED = false
SMTP_CONNECTIONS = 0
IMAP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
```
