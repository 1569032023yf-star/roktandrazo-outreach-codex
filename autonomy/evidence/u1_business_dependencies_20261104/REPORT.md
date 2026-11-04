# U1 真实业务依赖入包 / Real business dependencies in delivery

时间 / Time: 2026-11-04T09:19:47.779419+00:00
固定源码 / Fixed source: 3f02af1b95b45cad7ecbf942b2c252022f046e1a

中文：真实发现入口discovery.discovery_service依赖9个根目录模块，旧构建只收集autonomy、publisher_channel与discovery目录，遗漏bd_db、history_crosscheck、lead_hygiene_gate、outreach_control、retail_city_queue、broad_outreach_gate、email_hygiene、timezone_resolver与development_safety。构建器现在从同一固定Git提交读取这9个精确文件并纳入逐文件清单，未打包其他根目录入口、数据库、凭据或环境文件。已有请求、认证和业务协议不变；SerpAPI继续禁用。
English: discovery.discovery_service depends on nine repository-root modules. The earlier builder included only autonomy, publisher_channel and discovery, omitting the nine named modules above. The builder now reads exactly those files from the same pinned Git commit into the per-file manifest, without shipping unrelated root entrypoints, databases, credentials or environment files. Existing request/authentication/business protocols remain unchanged; SerpAPI stays disabled.

中文：安装包探测现在实际导入discovery.discovery_service，并核对8个被加载根模块及所有应用包模块来源都在包内；development_safety按原有条件懒加载，已入包但不假称本次实际导入。探测禁止socket连接、SQLite连接和SMTP构造，不调用搜索、采集、数据库函数或发信。完整业务运行闭包仍不因此自动通过。
English: The archive probe now imports discovery.discovery_service, checks origins of eight loaded root modules and all application package modules, and denies socket connections, SQLite connections and SMTP construction. development_safety remains conditionally imported as before; it is bundled but not claimed as loaded by this probe. No search, collection, database function or email is invoked. Complete business execution closure is not established by imports alone.

## 验证 / Validation

- python -B -m unittest test_delivery_documents test_delivery_verification test_provider_contracts -q: 7 PASS / 7.454s. 入包定向测试使用宿主编译替身 / targeted packaging test uses a host compiler fixture.
- BASELINE_BUSINESS_IMPORT.json: 旧固定d209c53实际解压包，用相同增强探测退出1，ModuleNotFoundError: bd_db / previous fixed extracted archive exits1 with missing bd_db under the same enhanced probe.
- STAGED_BUSINESS_IMPORT.json: 新固定Git暂存应用、既有CPython3.13.12AMD64，退出0，46个应用模块来源核验通过及隔离子进程通过 / fixed staged application and existing packaged CPython exit0,46 application origins and isolated child verified. 非新最终归档验收 / not final new archive acceptance.
- git diff --check: PASS.
- 新SHA全量回归 / full regression for this SHA: NOT_RUN. 上一轮组合静态扫描错误保留，不宣称已修复或全量全绿 / prior combination static-scan error remains, with no fix or all-green claim.

## 构建及边界 / Build and boundaries

中文：真实x64禁用成对归档构建会话56784，定位见BUILD_LOCATOR.json。最终SHA、解压验证及回滚组件对应必须收取真实终态，不能继承旧包通过结果。独审PENDING，外部费用/终态合同CONTRACT_MISSING；内部命名不是阻断。
English: Actual x64 disabled paired archives are building under session56784, tracked in BUILD_LOCATOR.json. Final hashes, extracted checks and rollback component parity require actual terminal evidence and cannot inherit old archive results. Review PENDING and external billing/terminal contracts CONTRACT_MISSING; internal naming is no blocker.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.

中文：未执行生产安装、服务启用、Inventory触发、数据库写入、客户邮件、ACL或网络策略修改；不创建第二Inventory。风险为完整运行入口/持久数据协议、浏览器运行时和正式外部合同尚未全部验收。下一步核验新归档后继续原Inventory业务到宿主的安全执行接线；等待固定候选独审，非要求用户设计命名。报告不含凭据。平台无硬超时字段，本轮不宣称已强制配置45分钟；不新建系统定时任务。
English: No production installation, service enablement, Inventory trigger, database write, customer email, ACL or network-policy change; no second Inventory. Full execution/data protocol, browser runtime and formal external contracts remain unaccepted risks. Next verify these archives, then continue safe original-Inventory-to-host execution wiring and fixed-candidate independent review; no naming decision is requested. No credentials are reported. No platform hard-timeout field exists; no enforced45-minute limit or new system task is claimed.

## 原调度入口后续阻断 / Remaining original-orchestrator blocker

中文：已只读核对bd_orchestrator.py：原Inventory stage已有OriginalStageEvent接线，但其模块导入依赖env_loader立即读取本地.env并创建output目录。它不在本轮安装包的业务发现依赖范围；不复制生产.env、不伪造配置、不在导入探测中触发原stage。后续需将原入口所需的批准配置与安装状态目录解耦，并核验原owner到受控业务worker的完整闭包。本轮不将46模块导入通过表述为原调度入口验收。
English: Read-only inspection confirms bd_orchestrator.py already wires the original Inventory stage to OriginalStageEvent, but import eagerly invokes env_loader to read .env and creates output. This orchestrator is outside this candidate discovery-engine dependency scope. No production .env is copied, no configuration fabricated, and no original stage invoked by the import probe. Follow-up must separate approved configuration and installed state paths and verify the original owner through the controlled business worker. The46-module result is not original-orchestrator acceptance.

## 实际固定归档 / Actual fixed archives

中文：构建56784退出0，共5054文件，CPython及12个业务wheel已整合。安装包SHA256=2cbbf4312a9d7fed687acfcef8457120da02496f5d643a54c801198c3dc740a8；回滚工具SHA256=efdb0c52b0b16163c64db30a91c8685d81a1cb7b6911a2d1f4a3f0099661a4ae；安装清单SHA256=7d4d116a813a836c7aba9fac92d32a05b84c5297e921a8092f1e206d69edba85。实际解压验证83342与回滚组件核验24070已启动；终态见相应JSON，不继承旧包结果。
English: Build56784 exits0 with5054 files, bundled CPython and12 business wheels. The exact install/rollback/manifest hashes are listed above. Extracted verifier83342 and rollback parity24070 have started; their JSON terminal results establish scope without inheriting older results.

## 最终收取 / Final terminal results

中文：实际解压验证83342退出0，outcome=VERIFIED，5054文件最终复核通过；四项子检查全部退出0。真实发现入口及46个应用模块来源位于包内，隔离子进程通过；pip check、原生VALID_PINNED_RUNTIME、临时HTTP未认证401/认证200通过。回滚组件核验24070退出0，4964组件对应通过，rollback_verified=false。完整原调度器业务闭包、正式8791、跨登录/重启、服务安装、真实Provider及实际回滚仍未验收；独审PENDING。
English: Actual extracted verifier83342 exits0 with outcome VERIFIED and final revalidation of5054 files. All four subchecks exit0: real discovery entrypoint and46 application origins are inside the archive; isolated child, pip check, native VALID_PINNED_RUNTIME and temporary HTTP401/200 pass. Rollback parity24070 exits0 with4964 matched components; rollback_verified=false. Complete original-orchestrator business closure, production8791, cross-login/reboot, installation, real Provider and actual rollback remain unaccepted. Review PENDING.
