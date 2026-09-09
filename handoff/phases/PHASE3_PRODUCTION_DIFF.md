# Phase 3A 生产差异审查 / Phase 3A Production Diff Review

审查日期 / Review date: 2026-09-08  
生产根目录 / Production root: `C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach`  
开发根目录 / Development root: `C:\Users\15690\Documents\ChatGPT\线下\roktandrazo-outreach-dev`

## 结论 / Conclusion

中文：生产目录仅被读取，没有部署、数据库写入、依赖安装、SMTP/IMAP 连接或调度器变更。开发与生产的全部差异不能整包复制。经排除开发守卫、测试、快照、报告、缓存及运行产物后，当前最小候选集为 **完整替换 4 个文件、对 1 个文件执行选择性补丁、新增 1 个文件、删除 0 个文件**。

English: Production was read only. No deployment, database write, dependency installation, SMTP/IMAP connection, or scheduler mutation occurred. The complete development delta must not be copied wholesale. After excluding development guards, tests, snapshots, reports, caches, and runtime artifacts, the minimum candidate is **four whole-file replacements, one selective file patch, one added file, and zero deletions**.

中文：本审查发现两个放行前缺口，因此此处提供的是“精确候选补丁清单”，不是已批准可执行的部署包：`bd_db.py` 的 stale takeover 在提交旧记录与插入新记录之间释放事务锁；常规库存链也没有把 Phase 2D 证据对象中的 `requested_url`、`final_url`、HTTP/TLS 状态和 `content_hash` 完整持久化。两项都必须先在开发中补齐并重新验证。

English: Two release blockers were found, so this is an exact candidate-patch inventory, not an approved deployable bundle: `bd_db.py` releases its transaction lock between committing stale cleanup and inserting the replacement run; and the normal inventory path does not persist the full Phase 2D evidence contract (`requested_url`, `final_url`, HTTP/TLS status, and `content_hash`). Both must be completed and revalidated in development first.

## 精确生产候选补丁 / Exact production candidate patch

| 操作 / Action | 文件 / File | 精确范围 / Exact scope | 原因 / Reason |
|---|---|---|---|
| 选择性修改 / Selective patch | `bd_db.py` | 仅 `insert_lead` 的 `organization_key`、`recipient_timezone`、`timezone_status` 映射；`acquire_run_lock` 原子 UTC 锁；holder 校验的 `release_run_lock`；修正后的单事务 `start_job_run`。不得包含文件顶部开发守卫或 `get_db()` 的开发 URI/路径逻辑。 / Only the three `insert_lead` mappings, atomic UTC `acquire_run_lock`, holder-checked `release_run_lock`, and a corrected single-transaction `start_job_run`. Do not include the top-level development guard or development URI/path behavior in `get_db()`. | Phase 2A 互斥、组织/时区字段完整性 / Phase 2A coordination and organization/timezone integrity |
| 完整替换 / Whole-file replacement | `bd_orchestrator.py` | SHA-256 目标 / target `49E38BB1D80832E65F33752D4F7B0E64F5DF41753DC6056B4D1A5A2446ACECDC` | holder-aware 解锁；重复作业 fail-closed；Inventory 接入 Website Resolver 后再做邮件提取。 / Holder-aware unlock, duplicate-job fail-closed, and Website Resolver before email extraction. |
| 完整替换 / Whole-file replacement | `discovery/discovery_service.py` | SHA-256 目标 / target `2751B6D0D2776B48E6E02A45E1C1EF7773558CE7DBAEA13074DC2C8181738412`，但证据持久化缺口修复后哈希必须重新登记。 / Hash applies only to the current candidate; it must be replaced after the evidence-persistence blocker is fixed. | Website resolution lane；只解析可见文本和 `mailto:`；隐藏/script 内容排除；HTTP/TLS/跨域失败关闭；补 organization/timezone；缺网站记录保留待补库。 / Website-resolution lane, visible-text-only email extraction, hidden/script exclusion, HTTP/TLS/cross-domain fail-closed behavior, organization/timezone enrichment, and pending retention for missing sites. |
| 完整替换 / Whole-file replacement | `discovery/providers/browser_maps.py` | SHA-256 目标 / target `245ED26C92A1624CB8F1BC1754F1DF1EFC887D4343B86BA0CEEF769DC040D31A` | 构造器默认值改为 `None`，让现有 `BROWSER_MAPS_MODE` 环境值真正生效。 / Constructor default becomes `None`, allowing the existing environment value to take effect. |
| 完整替换 / Whole-file replacement | `history_crosscheck.py` | SHA-256 目标 / target `0BA0D0CC25FE3BAA2404B31B8A01070AB02CB6D8CF8588CF3F68F527EFD60631` | 地址作为门店位置身份；共享电话不再错误合并不同实体门店；保留组织级历史阻断。 / Address defines location identity; shared phones no longer collapse distinct physical stores while organization-level history remains enforced. |
| 新增 / Add | `discovery/website_resolver.py` | SHA-256 `FFBCACDF68992217B6680B19E69713CED045684D2A48F7375DB1E092F667B33F`，证据契约补齐后若改动须重新登记。 / Re-register if the blocker fix changes it. | 通过既有 provider 二次查找官网；拒绝社交/目录域；名称、电话、城市州确定性评分，阈值 80。 / Re-query via the configured provider, reject social/directory domains, and score name/phone/city-state deterministically with threshold 80. |

中文：`bd_db.py` 的生产基线 SHA-256 为 `5C18DBD91871EEC3AE742C0730D65294F87E84DB720ADA3C2E86860F96B3ADAB`。部署包必须从该基线制作选择性补丁，不能以开发文件 `CCC5338393FED0018E9DA620355D32775809135E2DCE0864FA76F884F144F90B` 整体覆盖。

English: The production baseline SHA-256 of `bd_db.py` is `5C18DBD91871EEC3AE742C0730D65294F87E84DB720ADA3C2E86860F96B3ADAB`. The deployable file must be selectively patched from that baseline; the development file hash `CCC5338393FED0018E9DA620355D32775809135E2DCE0864FA76F884F144F90B` must not be copied wholesale.

## 按需求映射 / Requirement mapping

| 需求 / Requirement | 文件 / Files |
|---|---|
| Phase 2A 作业/锁协调 / job and lock coordination | `bd_db.py`, `bd_orchestrator.py` |
| BrowserMaps 配置修复 / configuration fix | `discovery/providers/browser_maps.py` |
| Website resolution / 官网解析 | `discovery/website_resolver.py`, `discovery/discovery_service.py`, `bd_orchestrator.py` |
| 官方邮箱提取/证据 / official email extraction/evidence | `discovery/discovery_service.py`；当前尚需补齐证据持久化契约 / evidence persistence still needs completion |
| 重试/补库流 / retry and replenishment | `discovery/discovery_service.py`, `bd_orchestrator.py` |
| Inventory SAFE funnel 语义 / semantics | `history_crosscheck.py`, `bd_db.py`, `discovery/discovery_service.py`; SAFE FSP 仍由冻结 V2 选择器与 Final Send Plan 形成，不新增生产 `safe_fsp` 表。 / SAFE FSP remains the derived frozen-V2/Final-Send-Plan eligible pool; no production `safe_fsp` table is added. |

## 明确排除 / Explicit exclusions

不得进入补丁 / Must not enter the patch:

- `development_safety.py`, `sitecustomize.py`, `.development-copy`, 开发 `.env` / development `.env`.
- `env_loader.py` 的开发副本守卫，以及 `send_phase2.py`、`send_phase3.py`、`sender.py` 的开发守卫导入 / development guard changes.
- `dev_fsp.py`, `safe_replenishment.py`, `dev_safe_fsp` 及任何开发/测试数据库 / any development or test database.
- `requirements-dev.txt`, `pytest.ini`, `tests/`, 测试 fixture、Phase 2C/2D harness / test fixtures and controlled harnesses.
- `audit_static.py`, 所有审计/报告 Markdown、browser cache、PID、status、日志及 runtime artifacts / audit reports, browser caches, PID/status/log/runtime artifacts.
- `migrations/migrate_city_outreach_40.py`：生产快照已具备本补丁当前使用的字段与表，不能为“保险”而重复带入。 / The production snapshot already contains the fields and tables used by this candidate; do not ship the migration defensively.

## 冻结链哈希 / Frozen-chain hashes

| 文件 / File | SHA-256（生产=开发） / SHA-256 (production = development) |
|---|---|
| `bd_sender.py` | `002D68A1E76D5F96AF6FDBABDCE54DA0AF3A93077D8A504DDD106A41FD018280` |
| `daily_session.py` | `F4559A34E87C9FCAB0C83FA92B6E4FBA4C0F5E284B77BB03F98AD1318C4088AF` |
| `preflight_gate.py` | `B1F44038C346BBF022A9D40575E330A1A73471A6DAFE0605D17EEACF3B8EF105` |
| `campaign_eligible_v2.py` | `1143BEDF563C0F76B883359362FFB2C2EA11C375FD923DC59768C5529CF3AD34` |
| `final_send_plan.py` | `26DE2F017390EDA767BEDDFE8FBD6BC438B78DDB430EEEBC4B96C72AA41D327F` |

`FROZEN_FILES_IN_PATCH = 0`

## 数据库影响 / Database impact

| 对象 / Object | REQUIRED | MIGRATION | ROLLBACK | BACKWARD_COMPATIBLE |
|---|---|---|---|---|
| `leads.organization_key` | true；新 lead 去重/组织语义 / new-lead organization identity | none；生产已有 / already present | 回滚代码，不删数据 / roll back code, retain data | true |
| `leads.recipient_timezone` | true | none；生产已有 / already present | 同上 / same | true |
| `leads.timezone_status` | true | none；生产已有 / already present | 同上 / same | true |
| `lead_discovery_results`, `lead_discovery_hits`, `lead_discovery_query_state`, `retail_city_queue` | true | none；生产已有当前契约 / current contract already present | 保留新增业务记录，回滚代码 / retain records, revert code | true |
| `job_runs` | true | none；生产已有 / already present | 将活动发布验证 run 标为 aborted/failed，回滚代码 / close validation run, revert code | true |
| `system_config` 动态锁键 / dynamic lock keys `run_lock:daily_outreach:<stage:date>` 与 `_acquired_at` | true at runtime | none；无需预置 / no pre-seed | 仅 holder 匹配时释放；不得批量删配置 / release only with matching holder; no bulk deletion | true |
| 新表/新列/新索引 / new table/column/index | false（当前候选） / current candidate | none | none | true |
| 完整抓取证据字段 / full fetch-evidence fields | true before release | **尚未设计 / not yet designed**；需先决定用现有列+结构化 JSON 还是向 discovery 记录加列 / decide existing structured storage vs added columns | 必须随最终方案定义 / must accompany final design | 待验证 / pending |

`DB_MIGRATION_REQUIRED = pending_evidence_contract`  
中文：现有候选自身不需要迁移；但证据持久化缺口解决前不能最终断言为 `false`。 / English: The current candidate requires no migration, but the final answer cannot be `false` until evidence persistence is designed.

## 生产依赖 / Production dependencies

`PRODUCTION_DEPENDENCIES_TO_ADD = []`

中文：候选新增代码仅使用 Python 标准库及现有 provider。历史生产验收材料已证明 Playwright、Chromium、`httpx` 可用；`dnspython` 已被生产现有 MX 路径使用。部署前只做 import/浏览器启动只读检查，不安装 `requirements-dev.txt`，也不把 `pytest`、`tzdata` 当作生产新增依赖。

English: Candidate code adds only standard-library use and the existing provider. Historical production acceptance evidence already records Playwright, Chromium, and `httpx` availability; `dnspython` is already used by the production MX path. Pre-deployment performs import/browser-launch verification only. Do not install `requirements-dev.txt`, and do not promote `pytest` or `tzdata` as new production dependencies.

## 生产配置 / Production configuration

`PRODUCTION_ENV_CHANGES = []`

中文：只读核对确认生产已配置 `DISCOVERY_PROVIDER=browser_maps`、`BROWSER_MAPS_MODE=direct` 和现有本机代理。BrowserMaps 代码修复的目的正是让现有模式生效。不得复制开发 `.env`，不得在报告或部署包中输出代理凭据。`WORKBUDDY_WEBSITE_RESOLUTION_MAX` 可继续使用代码默认值 20，不是发布必需配置。

English: Read-only inspection confirms production already has `DISCOVERY_PROVIDER=browser_maps`, `BROWSER_MAPS_MODE=direct`, and its existing local proxy setting. The BrowserMaps fix makes that existing mode effective. Do not copy the development `.env` or expose proxy credentials. `WORKBUDDY_WEBSITE_RESOLUTION_MAX` may remain at code default 20 and is not release-required configuration.

## 验证结果 / Verification result

开发全量测试 / Development full suite: `303 passed, 44 subtests passed in 44.34s`.  
生产写入 / Production writes: `0`. 真实 SMTP/IMAP / Real SMTP/IMAP: `0`.

## 最终字段 / Final fields

```text
PRODUCTION_FILES_TO_CHANGE = [bd_db.py (selective), bd_orchestrator.py, discovery/discovery_service.py, discovery/providers/browser_maps.py, history_crosscheck.py]
PRODUCTION_FILES_TO_ADD = [discovery/website_resolver.py]
PRODUCTION_FILES_TO_DELETE = []
FROZEN_FILES_IN_PATCH = 0
DB_MIGRATION_REQUIRED = pending_evidence_contract
PRODUCTION_DEPENDENCIES_TO_ADD = []
PRODUCTION_ENV_CHANGES = []
```
