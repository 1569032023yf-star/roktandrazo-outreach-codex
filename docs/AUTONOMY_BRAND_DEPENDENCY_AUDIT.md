# 品牌依赖独立审核 / Independent brand dependency audit

时间 / Time: 2026-10-20T00:59:38.057775+00:00

固定来源 / Pinned source: `5e9b89de99a596b509426a596ef02fcc7521facc`
周期 / Cycle: `c35de6c2-5533-452f-9930-9ecead4457c3`
调度 / Scheduler: codex_heartbeat; trigger `2026-10-20T00:52:39.151Z`
输出证据SHA256 / Output evidence SHA256: `fe72fb227f340d7a3d6e9fb38d2e6e7a27f4217234463cd6d3fa03846b5ec739`

只读审核完成。固定提交5e9b89de99a596b509426a596ef02fcc7521facc可读取；当前HEAD为73af1bebe141c714beb40e858ad62176d4eb7805，工作树干净。已读取AGENTS.md、工程责任制、PROJECT_SKILLS.md、GUARDRAILS.md、RUNBOOK.md及5A/5A.1报告；用Git和AST检查15个品牌模块、4个入口、6个对应测试文件，以及本地传递导入依赖。25个迁移目标全部缺失，测试源码包含115个test方法；未运行测试或导入项目模块，未联网、读取候选原始数据、生产DB或凭据，未修改文件。静态接口未发现直接依赖缺失符号，但不证明运行兼容。下一项最小代码修改：仅新增这25个文件，保留当前共享依赖和5A代码；随后在允许临时写入的隔离环境执行定向离线测试，根据失败再精确合并，禁止整文件回退。

Read-only review completed. Fixed commit 5e9b89de99a596b509426a596ef02fcc7521facc is accessible; current HEAD is 73af1bebe141c714beb40e858ad62176d4eb7805 and the working tree is clean. Required governance documents and 5A/5A.1 reports were read. Git and AST inspection covered 15 brand modules, four entrypoints, six corresponding test files, and local transitive imports. All 25 migration targets are absent; test sources contain 115 test methods. No tests or project modules were executed/imported, no network, raw candidate data, production DB or credentials were accessed, and no files were changed. Direct dependency symbols resolve statically, which does not establish runtime compatibility. The next minimal code change is to add only these 25 files, retain current shared dependencies and 5A code, then run targeted offline tests in an isolated environment permitting temporary writes. Merge precise changes only when failures justify them; never replace newer files wholesale.

## high — brand_acquisition/

固定提交中的15个模块全部缺失，可作为新增文件迁移：__init__.py、capture_import.py、capture_manifest.py、diagnostics.py、directory_adapters.py、directory_pipeline.py、email_quality.py、history.py、models.py、official_site_resolver.py、pipeline.py、pipeline_types.py、providers.py、site_conversion.py、source_catalog.py。包初始化会导入pipeline，因此只迁移单个业务模块不能形成完整导入闭包。

All 15 fixed-commit modules are absent and eligible for additive migration: __init__.py, capture_import.py, capture_manifest.py, diagnostics.py, directory_adapters.py, directory_pipeline.py, email_quality.py, history.py, models.py, official_site_resolver.py, pipeline.py, pipeline_types.py, providers.py, site_conversion.py and source_catalog.py. Package initialization imports pipeline, so copying an individual business module does not provide a complete import closure.

## high — scripts/

可新增run_brand_acquisition_canary.py、run_brand_capture.py、run_industry_directory_canary.py、run_official_site_conversion.py。目录入口转调run_brand_capture.main(directory=True)。capture-public具备请求前网络/开发开关门禁；官网转换入口属于真实网络操作入口，不属于离线测试命令。本次未调用任何入口。现有5个phase4a8审计脚本与固定提交无差异，无需迁移。

The four absent entrypoints can be added: run_brand_acquisition_canary.py, run_brand_capture.py, run_industry_directory_canary.py and run_official_site_conversion.py. The directory wrapper delegates to run_brand_capture.main(directory=True). capture-public checks network/development gates before requests; the official-site conversion entrypoint is a live-network operation, not an offline test command. No entrypoint was invoked. The five existing phase4a8 audit scripts are unchanged and require no migration.

## high — discovery/discovery_service.py

这是存在差异的直接共享依赖。品牌代码使用BrowserFallbackWebsiteFetcher、_fetch_official_pages、_official_identity_match和_extract_email_evidence，当前均存在且签名保持兼容。当前文件新增网络重试终止、SAVEPOINT事务及不可达遥测；其导入的retail_city_queue.py也已有更新。现阶段没有证据要求修改这两个文件；如后续确需修改，必须精确合并，禁止用固定提交整文件覆盖。

This direct shared dependency differs. Brand code uses BrowserFallbackWebsiteFetcher, _fetch_official_pages, _official_identity_match and _extract_email_evidence; all exist with compatible signatures. Current changes include retry termination, SAVEPOINT transactions and unavailable-request telemetry. Its dependency retail_city_queue.py also differs. No demonstrated change to either file is currently necessary; any later modification must be merged precisely, never replaced wholesale from the fixed commit.

## info — email_hygiene.py; history_crosscheck.py; development_safety.py; discovery/normalizer.py

这些直接依赖与固定提交源码一致，hygiene_check(email)、check_mx_cached(domain)、cross_check(conn,candidate,exclude_lead_id=None)及normalized_domain可静态解析，不需复制或覆盖。传递依赖检查中未发现这些模块缺失；这不验证第三方包安装情况、运行时动态导入或数据库schema。

These direct dependencies match the fixed-commit source. hygiene_check(email), check_mx_cached(domain), cross_check(conn,candidate,exclude_lead_id=None) and normalized_domain resolve statically and require no copying or replacement. Transitive inspection found no missing instances of these modules. This does not validate installed third-party packages, runtime dynamic imports or database schemas.

## high — brand_acquisition/history.py:24

历史检查依赖history_crosscheck.cross_check，仅允许显式声明的开发只读副本，使用mode=ro和query_only；无副本、异常或不可用均返回UNKNOWN。site_conversion还要求实际HistoryChecker及可用副本，任意返回clean的回调不能代替。离线测试应覆盖UNKNOWN、已发送、抑制及退信分支；真实历史去重未验证，不得据目录记录或新增文件推断新客户资格。

History checking depends on history_crosscheck.cross_check and requires an explicitly designated development read-only copy, using mode=ro and query_only. Missing copies, failures or unavailable history return UNKNOWN. site_conversion additionally requires an actual HistoryChecker with an available copy; an arbitrary clean-returning callback is insufficient. Offline tests should cover UNKNOWN, previously sent, suppression and bounce cases. Real history deduplication remains unverified; directory records or added files establish no new-customer eligibility.

## high — brand_acquisition/pipeline.py:644; brand_acquisition/site_conversion.py:559

默认MX路径调用email_hygiene.check_mx_cached，可能执行真实DNS查询，离线验证必须注入或mock。两条品牌路径将Exchange归为MX ok，这仅代表路由检查，不能替代当前危险Microsoft 365/Exchange排除及完整发送链门禁。DNS错误、超时和无MX不得升级通过。

Default MX paths call email_hygiene.check_mx_cached and may perform real DNS queries; offline validation must inject or mock them. Both brand paths classify Exchange as MX ok. This is routing evidence only and cannot replace the current risky Microsoft 365/Exchange exclusion or complete sending-chain gates. DNS errors, timeouts and missing MX must not qualify.

## high — brand_acquisition/directory_pipeline.py:10

目录身份回调要求第一方HTTPS站点独立匹配组织名称，结果为ORGANIZATION_CONFIRMED，明确保留brand_ownership_verified=false及buyer_intent_verified=false。导入和fixture应保持discovery_only，不能计入真实获取产量。目录登记、目录存在、域名线索或组织确认均不等于品牌所有权、采购意图或发信资格。

Directory identity callbacks require independent organization-name matching on first-party HTTPS pages. They produce ORGANIZATION_CONFIRMED while explicitly retaining brand_ownership_verified=false and buyer_intent_verified=false. Imports and fixtures must remain discovery_only and excluded from live yield. Directory registration, directory existence, domain clues or organization confirmation establish neither brand ownership, purchasing intent nor sending eligibility.

## medium — tests/

可新增6个测试文件：test_brand_acquisition.py、test_brand_acquisition_offline.py、test_directory_live_layouts.py、test_directory_live_preflight.py、test_industry_directory_acquisition.py、test_phase4b1g_site_conversion.py，共115个test方法。最小覆盖本次完整迁移面的文件级离线集合就是这6个模块：解析/去重、来源降级、身份、第一方邮箱、历史/MX失败关闭、checkpoint及请求前门禁。迁移后可用python -B -c启动unittest并显式加载这6个tests模块；保持禁网，以合成fixture、mock传输及临时目录执行。测试会写临时文件，当前只读审核未运行，115不是通过数量。

Six absent test files can be added: test_brand_acquisition.py, test_brand_acquisition_offline.py, test_directory_live_layouts.py, test_directory_live_preflight.py, test_industry_directory_acquisition.py and test_phase4b1g_site_conversion.py, containing 115 test methods. These six modules form the minimal file-level offline set covering the complete migration surface: parsing/deduplication, provenance downgrades, identity, first-party email, history/MX fail-closed behavior, checkpoints and pre-request gates. After migration, launch unittest through python -B -c and explicitly load these six tests modules, retaining network restrictions and using synthetic fixtures, mocked transport and temporary directories. Tests write temporary files and were not executed during this read-only review; 115 is not a passing-test count.

## high — env_loader.py; bd_orchestrator.py; bd_sender.py; bd_template.py; final_send_plan.py; preflight_gate.py

这些现有文件与固定提交不同，不属于本次新增品牌包所需的直接替换项。env_loader含当前隔离工作树无.env时的安全启动兼容；其余文件承载较新5A发送链。不得通过整提交checkout、整目录或同名文件覆盖进行迁移；如后续触及，只允许逐块精确合并并保留现有V6锁、限额、内部QA、follow_up关闭等契约。当前对应5A测试也不得回退；应在品牌离线集合之后保留5A及隔离启动回归。

These existing files differ from the fixed commit and are not direct replacement requirements for the additive brand migration. env_loader contains current safe startup handling for isolated worktrees without .env; the other files carry newer 5A sending-chain behavior. Do not migrate through whole-commit checkout, directory replacement or same-name file overwrites. Any later changes require precise hunk-level merging while preserving current V6 locks, caps, internal QA and disabled follow_up contracts. Current 5A tests must also remain intact; retain 5A and isolated-startup regression coverage after the brand offline set.

## medium — CURRENT_STATUS.md; FILE_MANIFEST.md

PROJECT_SKILLS要求读取的这两个文件当前缺失，已以可读取的5A和5A.1报告核对约束，未猜测替代版本。审核结论仅覆盖源码导入及差异，不验证真实官网、候选真实性、生产历史、收件认证、发送状态或部署可行性；本次没有产生报告文件或任何文件修改。

These two startup documents required by PROJECT_SKILLS are absent. Available 5A and 5A.1 reports were used to check constraints without inventing replacement versions. Conclusions cover source imports and differences only, not live websites, candidate authenticity, production history, receiver authentication, sending state or deployment feasibility. No report artifact or file modification was produced.

## 后续与边界 / Next action and boundaries

下次真实心跳只新增上述25个文件及双语迁移报告，保留现有共享代码。完成禁网合成测试后仅进入needs_review，由另一周期独立审核。115仅是方法数，本轮品牌测试未执行；总控14项回归通过（含两类开发任务的自动审核排队子测试）。

The next genuine heartbeat adds only the 25 listed files and a bilingual integration report, retaining current shared code. Offline synthetic testing leads only to needs_review, followed by independent review in another cycle. 115 counts source methods, not passing tests; no brand tests ran this cycle. The 14 supervisor regression tests passed, including review-queue subtests for both developer task types.

本轮无生产数据库访问、部署、采集或发信。真实业务指标与历史资格仍UNKNOWN，旧SAFE56不算今日新增。高风险发现是迁移与资格约束，不代表运行兼容或生产验收。

No production database access, release, discovery or email sending occurred this cycle. Real business metrics and history eligibility remain UNKNOWN; historical SAFE56 is not new daily growth. High-severity findings describe integration and qualification constraints, not runtime compatibility or production acceptance.
