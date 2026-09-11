# Phase 4A.1C — 新发现与已关联积压共存 / Discovery and linked backlog coexistence

## 范围与变更 / Scope and changes

仅开发环境，未部署、未恢复调度。此报告更新并取代 4A.1B 关于“只运行已关联积压”的当前设计结论，历史报告保留不改。 / Development only; no deployment or scheduler resume. This report supersedes the current design conclusion in 4A.1B that Inventory should run linked backlog only; historical reports remain intact.

生产源补丁仅含以下两个文件，相对于已审查提交 `03d13d899ad4bfd94c52dbfbf96cad591232bd22`： / The production-source patch contains only these two files relative to reviewed commit `03d13d899ad4bfd94c52dbfbf96cad591232bd22`:

| 文件 / File | 变更 / Change | 开发目标 SHA256 / Development target SHA256 |
|---|---|---|
| bd_orchestrator.py | 恢复有界 Discovery、网站解析、标准安全后处理，然后运行积压；仅 V2 SAFE 判定完成 / Restore bounded discovery, website resolution and normal safe postprocess before backlog; only V2 SAFE determines completion | 252ed6042b04837f6d429936771fa261889b5f556aa80140162b098894da4d05 |
| discovery/discovery_service.py | 增加可选 unlinked_only 过滤，防止正常通道绕过已关联安全检查；默认行为兼容其他调用 / Add optional unlinked_only filtering to prevent the normal lane bypassing linked safeguards; defaults preserve other callers | 45db60d94017c3cc7b68ffdaa6044bf6af5392f790568b8766fc4236bad0c356 |

未改变 V2/MX、证据规则、数据库结构、依赖或生产配置。不包含第三个生产源文件。验证脚本、测试和报告属于开发辅助资产，不可作为生产发布文件。 / No changes to V2/MX, evidence rules, database schema, dependencies or production configuration. No third production-source file. The validation script, tests and reports are development assets, not production deployment files.

## 执行顺序与安全 / Execution order and safety

SAFE 已达标时，在补库网络请求之前返回 completed/target_met。未达标时沿用 active state/city，依次运行 run_places_batch → run_website_resolution → run_staging_postprocess → run_linked_backlog → frozen V2 SAFE。未达标结果为 partial/safe_inventory_gap。 / When SAFE already meets the target, return completed/target_met before replenishment network calls. Otherwise use the existing active state/city and execute run_places_batch → run_website_resolution → run_staging_postprocess → run_linked_backlog → frozen V2 SAFE. A remaining gap yields partial/safe_inventory_gap.

正常通道仅处理尚未关联的 staging；已关联行保留 4A.1B 的历史、退信、抑制、身份及 first-party 证据保护。166 条未关联 lead 不建立合成 staging，不进行名称猜测式关联。 / Normal lanes process unlinked staging only; linked rows retain 4A.1B history, bounce, suppression, identity and first-party evidence safeguards. The 166 deferred unlinked leads receive no synthetic staging or name-guessed linkage.

BROAD_READY 仅信息展示；READ_ONLY_V2_SAFE_UNIQUE_ORGS 是库存完成依据；MATERIALIZED_FSP_PLANNED 单独展示，不创建 FSP 或授权。 / BROAD_READY is informational; READ_ONLY_V2_SAFE_UNIQUE_ORGS determines inventory completion; MATERIALIZED_FSP_PLANNED is separate and no FSP or authorization is created.

## 回归 / Regression

328 项测试及 76 项子测试通过，失败 0、错误 0。保留全部 4A.1B 测试，新增六项测试覆盖双通道顺序、34/1 假完成、零产出继续、达标跳过、新商户可见邮箱证据、已关联保护及无发送/计划副作用。 / 328 tests and 76 subtests passed, with zero failures and errors. All 4A.1B tests remain; six new tests cover both-lane ordering, false completion at 34/1, safe continuation after zero yield, target-met skipping, new-merchant visible email evidence, linked safeguards and absence of send/plan side effects.

新增副作用测试使用当前 canonical schema fixture，而非缺失授权表的旧夹具。冻结五文件 SHA256 与既有基线全部一致。 / The new side-effect test uses the current canonical schema fixture rather than an older fixture missing authorization tables. All five frozen SHA256 hashes match the existing baseline.

## 新鲜副本演练 / Fresh-copy rehearsal

运行 / Run: `phase4a1c-dev-20260911T022851Z`，仅一次标准 Inventory，源库以 SQLite mode=ro 打开并在线备份，备份完整性检查通过；所有后续写入均在开发副本。 / Exactly one canonical Inventory; the source database was opened with SQLite mode=ro for online backup, which passed integrity validation. All subsequent writes were confined to the development copy.

| 指标 / Metric | 结果 / Result |
|---|---:|
| BROAD_READY | 34 |
| NEW_DISCOVERY_PATH_EXECUTED | true |
| DISCOVERY_RESULTS_SEEN / NEW_UNIQUE_PLACES | 0 / 0 |
| WEBSITE_RESOLUTION_PROCESSED | 0 |
| NORMAL_STAGING_POSTPROCESS_PROCESSED | 0 |
| LINKED_BACKLOG_PATH_EXECUTED | true |
| LINKED_BACKLOG_ELIGIBLE / PROCESSED | 18 / 18 |
| Linked website / postprocess | 11 / 7 |
| NEW_VISIBLE_FIRST_PARTY_EMAILS / NEW_FULL_EVIDENCE_RECORDS | 0 / 0 |
| READ_ONLY_V2_SAFE_BEFORE / AFTER | 1 / 1 |
| MATERIALIZED_FSP_PLANNED | 0 |
| MATERIALIZED_FSP_CREATED / AUTHORIZATION_CREATED | 0 / 0 |
| SMTP / IMAP | 0 / 0 |
| PRODUCTION_DB_WRITES / PRODUCTION_FILES_CHANGED | 0 / 0 |
| SCHEDULER_CHANGES / FROZEN_FILES_CHANGED | 0 / 0 |

结果为 partial/safe_inventory_gap，目标 30、实际 1、缺口 29，不因 BroadReady=34 错报完成。所有原有未关联 lead 内容不变；发送、退信、抑制、FSP、授权及授权明细表内容哈希均不变。 / The outcome is partial/safe_inventory_gap: target 30, actual 1, gap 29, with no false completion from BroadReady=34. All pre-existing unlinked lead contents and hashes of send, bounce, suppression, FSP, authorization and authorization-entry tables remain unchanged.

### 必须保留的限制 / Required limitation disclosure

Maps 初始列表出现 18 条原始结果，但读取详情期间，开发进程 GBK 控制台编码无法输出 U+274C，供应商返回 `scrape_error`：`'gbk' codec can't encode character '\\u274c'`。因此本次证明新 Discovery 被真实调用、异常后仍安全继续积压恢复，**不证明本次成功获取新增商户，也不能解读为市场无商户**。正常解析与后处理实际调用但无可处理行。11 个积压 Maps 查询返回零列表结果。 / Maps initially displayed 18 raw list entries, but while reading details the development process's GBK console encoding could not emit U+274C, yielding `scrape_error`. This run demonstrates that new Discovery was actually invoked and backlog recovery continued safely after the error; **it does not demonstrate successful new-merchant acquisition and must not be interpreted as an empty market**. Normal resolution and postprocess were called with no eligible rows. Eleven backlog Maps queries returned zero list entries.

启动使用了 `-I`，因此设置 PYTHONIOENCODING 未控制本轮标准输出。若另行授权开发复验，应使用显式 `-X utf8`；本阶段未重跑第二次 Inventory、未修第三个生产文件，也未通过放宽规则制造结果。 / The invocation used `-I`, so PYTHONIOENCODING did not control stdout in this run. A separately authorized development recheck should use explicit `-X utf8`. This phase did not rerun Inventory, change a third production file, or weaken rules to manufacture results.

## 结论 / Decision

BROADREADY_FALSE_COMPLETION_FIXED = true

NEW_DISCOVERY_PRESERVED = true

LINKED_BACKLOG_RECONNECTED = true

LEGACY_SCANNER_USED_AS_SAFE_AUTHORITY = false

PATCH_FILES = bd_orchestrator.py, discovery/discovery_service.py

FULL_SUITE_PASS = 328

FROZEN_FILES_CHANGED = 0

READY_FOR_CONTROLLED_PRODUCTION_PATCH = true

“就绪”仅指用户规定的两文件路由修复：离线通过且一次副本演练中两条路径均执行、零产出安全继续。它不表示供应商成功、补库目标达成或部署授权。GBK 演练限制必须随补丁审查一起呈现；现有 Phase 3 发布包未更新，不应替代此两文件变更。 / Readiness is limited to the requested two-file routing fix: offline tests pass, both lanes execute in one copied-database run, and zero yield is handled safely. It does not imply provider success, inventory target attainment, or deployment authorization. The GBK rehearsal limitation must accompany patch review. The existing Phase 3 deployment package was not updated and must not substitute for these two-file changes.
