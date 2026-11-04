# U1 Provider 适配器与交付整合 / Provider adapters and delivery integration

中文：固定源码 d209c53d6d3211cdca732d137fb2ebcfbec50f61。内部命名由工程自行决定，沿用 SearchProvider、GooglePlacesProvider、BrowserMapsProvider；没有命名依赖或待用户提供文件名。新增不可变 ProviderContract，由现有适配器统一暴露传输、认证、状态查询/幂等/取消/权威费用能力和精确缺失字段。Google Places 保留既有 HTTPS POST、API key、field mask 和 UNKNOWN 不重试实现；browser_maps 保留独立适配器并区分 file/browser。SerpAPI 原请求路径已经禁用，本次使 configured 在有密钥时也为 false。cost_units 明确为本地预算单位，非真实金额，不制造费用或回执。

English: Fixed source d209c53d6d3211cdca732d137fb2ebcfbec50f61. Engineering owns internal naming, retaining SearchProvider, GooglePlacesProvider and BrowserMapsProvider; no naming or filename dependency remains. Immutable ProviderContract is exposed through existing adapters for transport, authentication, lookup/idempotency/cancel/authoritative-cost capabilities and exact missing fields. Google Places retains existing HTTPS POST, API key, field mask and UNKNOWN no-retry behavior. browser_maps remains independent and distinguishes file/browser transport. SerpAPI already refused requests; configured now remains false even with a key. cost_units denotes local budget units, never a monetary receipt.

中文：Publisher 配套交付构建器现在从固定 Git 打包 discovery Python 源码，避免适配器停留在旧运行时。解压验证器导入真实 Provider 模块并检查模块来源均在包内，不执行搜索。重用已校验 CPython 3.13.12 AMD64 和12个业务wheel，运行时清单 SHA256=5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e。新构建位置 C:/Users/15690/Documents/ChatGPT/线下/u1-delivery-provider-d209c53；实际构建结果另见 BUILD.json，不将构建启动当作成功。第一次相对输入路径被 ORDINARY_LOCAL_PATH_REQUIRED 拒绝，保留原目录；第二次使用精确绝对路径，不放宽安全校验。

English: The Publisher companion delivery builder now packages discovery Python sources from fixed Git, rather than leaving adapters in an older runtime. Extracted verification imports real Provider modules and checks package-contained origins without searching. It reuses verified CPython 3.13.12 AMD64 and12 business wheels, with runtime-manifest SHA256=5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e. New build location: C:/Users/15690/Documents/ChatGPT/线下/u1-delivery-provider-d209c53. BUILD.json records the actual outcome; starting is not completion. Initial relative input was rejected with ORDINARY_LOCAL_PATH_REQUIRED and preserved; the second attempt uses exact absolute paths without weakening checks.

## 官方核验与具体缺失 / Official verification and exact gaps

- [Text Search REST](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places/searchText)：同步 POST 返回 places 和分页 token；所列接口未提供按 U1 operation_id 查询、幂等提交或取消终态机制。/ Synchronous POST returns places and pagination; the documented method provides no U1 operation lookup, idempotent submit or cancel-terminal mechanism.
- [Usage and billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing)：field mask 决定适用最高 SKU，本地 cost_units=1 不能换算实际账单。/ Field masks determine the highest applicable SKU; local units do not establish a billed amount.
- [Reporting](https://developers.google.com/maps/reporting-and-monitoring/reporting)：项目/凭据的用量、配额和账单报表可用，但不等同单次请求的终态回执。/ Project and credential usage/quota/billing reports are not individual operation-terminal receipts.
- [Billing export schema](https://cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/standard-usage)：包含账号、项目、SKU、用量、金额、币种及抵扣；尚无本项目获权导出及其与 run/claim 的绑定证据。/ Includes account, project, SKU, usage, cost, currency and credits; authorized project export and run/claim binding evidence are absent.
- [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies)：须遵守来源使用、缓存和归属要求；未授权扩大采集或缓存。/ Source-use, caching and attribution requirements remain applicable; no expanded acquisition or caching is authorized.

中文：CONTRACT_MISSING 具体字段为 operation_id_to_run_claim_binding、authoritative_terminal_status、idempotency_guarantee、cancellation_receipt_and_fee、billing_account_project_sku_binding、usage_period_quantity_unit、billed_amount_currency_credits、billing_evidence_reference；browser_maps 另缺 source_usage_authorization 和 browser_request_receipt。这是运行/计费证据缺失，不是内部命名阻塞。

English: CONTRACT_MISSING fields are operation_id_to_run_claim_binding, authoritative_terminal_status, idempotency_guarantee, cancellation_receipt_and_fee, billing_account_project_sku_binding, usage_period_quantity_unit, billed_amount_currency_credits and billing_evidence_reference. browser_maps additionally lacks source_usage_authorization and browser_request_receipt. These are execution/billing evidence gaps, not internal naming blockers.

中文：将来真正需外部确认的事项仅为新增付费服务/账单账号及额度授权、浏览器来源使用的商业授权、生产服务身份和维护窗口；本轮不提出命名问题、不申请启用任何服务。现有证据可读即可复用，不要求搬运或重复提交。
English: Future external decisions are limited to new paid services/billing accounts and spending authority, browser-source commercial authorization, and production service identity/maintenance window. No naming question or service-enablement request is raised now. Reuse existing accessible evidence without requesting resubmission.

## 验证与门禁 / Validation and gates

- python -B -m unittest test_provider_contracts tests.test_google_places_unknown -q: 7 PASS / 0.800s.
- python -B -m unittest test_delivery_documents test_bootstrap_arguments test_u1_provision -q: 6 PASS / 11.195s. 文档/Provider入包使用编译替身；不冒充真实宿主归档验收。/ Document/Provider inclusion uses a compiler fixture, not actual host-archive acceptance.
- python -B -m unittest test_delivery_verification -q: 3 PASS / 0.246s.
- git diff --check: PASS.

中文：独审 PENDING；新候选全量回归未运行，不继承旧833项结果。旧 a3ce4a5 HTTP WinError10013 仍为未解决历史失败，不绕权限。安装包构建、解压导入、服务安装、正式 Provider 业务、真实回滚、生产验收分别记录。
English: Independent review PENDING; full regression not run for this candidate, with no inheritance from old833 results. Prior a3ce4a5 HTTP WinError10013 remains an unresolved historical failure; permissions are not bypassed. Archive building, extracted imports, service installation, formal Provider business, actual rollback and production acceptance are distinct.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.

中文：补充组合检查 python -B -m unittest tests.test_discovery_service -q：20项，1 ERROR / 24.380s。失败ID test_static_scan_fails_on_unauthorized_direct_lead_inserts；扫描既有旧证据 final-isolated-store/versions/867679.../cancellation_terminal_bundle.py 时 FileNotFoundError。未修改历史证据或掩盖失败，未宣称零回归；其余19项未报告失败。
English: Additional combination check:20 tests,1 ERROR /24.380s. Failing ID: test_static_scan_fails_on_unauthorized_direct_lead_inserts; FileNotFoundError while scanning an existing historical final-isolated-store/versions/867679.../cancellation_terminal_bundle.py evidence file. Historical evidence was not modified and failure is preserved; no zero-regression claim. The remaining19 tests report no failure.

中文：实际归档前预检 STAGED_IMPORT.json 返回0；固定CPython隔离导入36个应用模块（包括两种Provider和SerpAPI禁用模块），全部模块源位于暂存待打包目录，子进程返回 ISOLATED_CHILD_OK。这是暂存源码组合预检，不是最终归档或服务验收。平台未设置本轮硬超时字段；不宣称45分钟由平台强制执行。
English: Actual pre-archive preflight STAGED_IMPORT.json returns0. Pinned CPython imports36 application modules in isolation, including both adapters and disabled SerpAPI; all application origins are within staged payload, and child returns ISOLATED_CHILD_OK. This is staged-source preflight, not final archive or service acceptance. No platform hard-timeout field is configured; no enforced45-minute claim is made.

## 实际成对归档 / Actual paired archives
中文：真实 x64 禁用包构建返回0，5045文件；已包含本轮Provider、凭据哈希绑定及双语离线说明。安装清单SHA256=cb809f27c8c9d1a520264143565df2827a3091b0bb8240389d8a90f553aa3d40。安装包SHA256=25ee2160fdac40d95a3eca38aa1907671b61a447a115ed2feee39465873b0c94；回滚工具包SHA256=67ff4c7c12b7f997add396e7682df12a46ba3a972a68cf1359e48d254286269c。package_complete/production_ready仍false。EXTRACTED_REPORT.json与ROLLBACK_PARITY.json分别记录实际解压验证和组件对应；回滚工具归档不等于现场备份或实际回滚验收。
English: Actual x64 disabled package build exits0 with5045 files, including current Provider sources, credential digest binding and bilingual offline guide. ManifestSHA256=cb809f27c8c9d1a520264143565df2827a3091b0bb8240389d8a90f553aa3d40. InstallSHA256=25ee2160fdac40d95a3eca38aa1907671b61a447a115ed2feee39465873b0c94; rollback-toolsSHA256=67ff4c7c12b7f997add396e7682df12a46ba3a972a68cf1359e48d254286269c. package_complete/production_ready remain false. EXTRACTED_REPORT.json and ROLLBACK_PARITY.json separately record extracted verification and component parity; the rollback-tools archive is neither a site backup nor actual rollback acceptance.

中文：实际解压验证四项子检查均返回0：固定应用/Provider隔离导入与包内子进程、pip check、原生 VALID_PINNED_RUNTIME、临时回环HTTP未认证401/认证200。旧a3ce4a5的WinError10013作为历史失败保留；本轮未修改权限或网络策略，当前成功仅适用于此候选临时fixture，不证明正式8791端口、跨登录、服务自动启动或Provider业务。验证器最终运行后文件复核仍须收取最终outcome，不以四项成功提前宣称整体通过。
English: Four actual extracted subchecks return0: isolated fixed application/Provider imports and packaged child, pip check, native VALID_PINNED_RUNTIME, and temporary loopback HTTP401 unauthenticated/200 authenticated. The older a3ce4a5 WinError10013 remains historical evidence. No permissions/network policy were changed; current success applies only to this candidate fixture, not formal8791, cross-login, automatic service startup or Provider business. Final post-run file revalidation still requires collection of the overall outcome.

中文：最终解压验证会话32027返回0，EXTRACTED_REPORT.json outcome=VERIFIED，5045文件最终复核通过；四项包内检查均通过。回滚对应会话94395返回0，4964组件对应通过；rollback_verified=false。正式生产端口、完整业务入口依赖闭包、服务安装及真实业务仍未验收。独审PENDING。
English: Final extracted verification session32027 exits0, outcome=VERIFIED, with final revalidation of5045 files; all four packaged checks pass. Rollback parity session94395 exits0 with4964 matched components; rollback_verified=false. Production ports, full business-entrypoint dependency closure, service installation and actual business remain unaccepted. Independent review PENDING.
