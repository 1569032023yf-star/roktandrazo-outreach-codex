中文：本轮核查真实Publisher安装调用链并修复安装前只验证Provider外层配置的问题：现复用宿主的真实适配器构造验证，Google位置配置为数组时在安装前拒绝。保留配置哈希/文件锁及所有安装门禁，无网络请求。24项定向组合通过（15.473秒），覆盖真实安装器拒绝、无进程启动、输入不变及失败释放锁。固定源码c2e81ff6e333ae64c2af1a2160ddcd972953bd74；独审PENDING，新源码包未构建，主树/canonical未改。所有最终状态与生产门禁false。下一步固定源码包验证与独审。

English: Audited the real Publisher install chain and fixed outer-only Provider validation: installer now reuses host real-adapter construction admission, rejecting Google location arrays before installation. Configuration hashes and locks and all install gates remain in force; no requests.24 targeted combined tests pass in15.473s, including real installer rejection, no process launch, unchanged inputs and released handles after failure. Source:c2e81ff6e333ae64c2af1a2160ddcd972953bd74. Independent review PENDING. New source archive NOT_BUILT; previous package applies only to70d85c6. Main/canonical unchanged because shared chat-entry coordination is unverified; Git queue is projection only. DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false. Billing/terminal evidence CONTRACT_MISSING. Next: fixed-source package verification and independent review, then coordinated main integration; no production installation.
Report: autonomy/evidence/u1_install_provider_admission_20261108/REPORT.md

中文：本轮完成固定70d85c6ec56901d644c5d7e6dd984de2aaf081a6的真实x64/CPython安装和回滚工具归档，5058文件完整性/5项包内探针VERIFIED，4960回滚组件逐字节一致。额外真实包内隔离Python经bootstrap传入browser_maps绝对缓存/JSON路径，预检通过（10.229秒），不存在的目标未创建，前后文件不变，外部请求/SMTP/文件DB均禁止。只证明配置与离线接线，不把configured当成数据可用、费用或业务验收。未改业务源码，不重复上一36项单测。独审PENDING；未安装/启用服务、未执行真实回滚/采集/邮件，正式费用回执仍CONTRACT_MISSING。主树和canonical未改，Git队列仅投影。所有最终状态与门禁false，BUSINESS_GROWTH UNKNOWN。下一步核查已有Publisher→维护IPC→原Owner会话的真实调用链与剩余P0接线，不重复重建此SHA包。报告不含凭据。

English: Built real x64/CPython install and rollback-tools archives for fixed 70d85c6ec56901d644c5d7e6dd984de2aaf081a6.5058-file integrity and five packaged probes VERIFIED;4960 rollback components byte-identical. An extra real isolated packaged-Python bootstrap passed absolute browser_maps cache/JSON configuration; preflight passed(10.229s), absent targets stayed absent and input bytes unchanged. External requests/SMTP/file databases denied. Configuration and offline wiring only; configured is not data availability,billing or business acceptance. No business-source change or repeat of prior36 unit tests. Independent review PENDING; no installation/service enablement, real rollback, collection or email. Formal billing receipts CONTRACT_MISSING. Main/canonical unchanged;Git queue is a projection. All final states/gates false;BUSINESS_GROWTH UNKNOWN. Next: audit existing Publisher→maintenance IPC→original-owner session call chain and remaining P0 integration, without rebuilding this unchanged SHA. No credentials recorded.

中文：固定70d85c6ec56901d644c5d7e6dd984de2aaf081a6修复browser_maps正式配置依赖启动目录的缺陷：宿主服务与Python Worker可能从不同目录启动，同一个已签配置此前可指向不同缓存/JSON文件。正式配置入口现拒绝相对路径、驱动器相对路径与空缓存目录；显式空JSON保持“未设置”，缺省模块相对缓存策略不改。复用真实适配器，无新Provider或调度器。36项定向组合通过（8.923秒），包括真实适配器参数绑定及缺失目标不被创建。此检查只消除CWD歧义，不声称路径已获授权、内容已固定或通过ACL/来源验收。独审PENDING，新源码包未构建，上一包仅对应99d60197版本。主树/canonical未改；Git队列是投影，跨聊天接入未确认。未安装、未采集、未写生产、未发送邮件。所有最终状态和门禁false，BUSINESS_GROWTH UNKNOWN。下一步新固定源码包与browser_maps包内启动验证及独审。无凭据输出。

English: Fixed 70d85c6ec56901d644c5d7e6dd984de2aaf081a6 removes launch-directory dependence from formal browser_maps configuration. Service and Worker may start in different directories, previously resolving the same pinned configuration to different cache/JSON files. Formal admission now rejects relative and drive-relative paths and empty cache directories; explicitly empty JSON remains unset and the existing module-root default is preserved. Existing real adapter reused, no new Provider/scheduler.36 combined tests pass (8.923 seconds), including actual adapter parameters and no creation of missing data targets. This removes CWD ambiguity only; it does not establish path authority, pinned data contents or ACL/source acceptance. Review PENDING; no fresh archive for changed source, previous package binds only99d60197. Main/canonical unchanged; Git queue is a projection because cross-chat adoption is unverified. No installation, collection, production writes or email. All final states/gates false;BUSINESS_GROWTH UNKNOWN. Next: fresh pinned archive/browser_maps packaged startup validation and independent review. No credentials exposed.

中文：本轮交付固定99d60197a7bae19f53303afbcad87d52848bac2a真实x64/CPython安装与回滚工具包；5058文件完整性及5项包内探针VERIFIED，4960回滚组件逐字节一致。额外包内隔离Python通过真实bootstrap传入固定Google配置，真实适配器校验成功，未配置API密钥状态正确保留false；禁止外部网络/SMTP/文件DB，预检前后文件不变。首次构建遗漏运行时绑定被拒绝，补齐后成功；首次额外探针因临时路径过长被拒绝，缩短测试路径后通过，未绕过路径门禁。失败及成功回执均保留。无新业务源码改动，不机械重跑已通过的35项单测。独审PENDING，不证明安装、回滚执行或真实Provider成功；未安装服务、未采集、未改生产。canonical/main保持未改，Git队列仅投影。全部交付最终状态false，BUSINESS_GROWTH=UNKNOWN。下一步固定版本独审与安全接入主线；正式费用/终态回执仍CONTRACT_MISSING。报告无凭据。

English: Delivered real x64/CPython install and rollback-tools archives for fixed source 99d60197a7bae19f53303afbcad87d52848bac2a. All5058 files and five packaged probes VERIFIED;4960 rollback components are byte-identical. An extra isolated packaged-Python probe passed pinned Google configuration through the actual bootstrap and constructed the real adapter, preserving unconfigured credentials as false. External network/SMTP/file databases were denied and inputs remained unchanged. Missing runtime-binding arguments initially rejected the build; corrected arguments succeeded. The extra probe initially hit the existing path-length gate; a shorter fixture directory passed without bypass. Both failures and successes are retained. No business-source change or mechanical rerun of prior35 unit tests. Review PENDING; no installation/rollback execution or live Provider acceptance asserted. Main/canonical unchanged; Git queue is a projection. All final delivery states false;BUSINESS_GROWTH UNKNOWN. Next: independent fixed-version review and safely coordinated main integration. Formal billing/terminal receipts remain CONTRACT_MISSING. No credentials recorded.

中文：固定源码99d60197a7bae19f53303afbcad87d52848bac2a将已有真实Provider适配器构造接入宿主启动，提前拒绝无法解析的Google位置对象；此前宿主仅验证外层配置，Worker稍后才会失败。只读预检明确输出适配器身份、是否配置与是否验证，不授予派发权限。35项定向组合通过（7.879秒），包含真实适配器构造、拒绝早于Owner/状态创建、文件无变化。独审PENDING；新包尚未构建，不继承上一版本包的验收。主树与canonical未改：共同锁仅证明合作进程，跨聊天接入仍未确认。安装/派发/取消/SMTP全部false。Provider真实费用与终态回执仍CONTRACT_MISSING。下一步构建新固定包并验证隔离Python预检，安排固定版本独审。

English: Fixed source 99d60197a7bae19f53303afbcad87d52848bac2a constructs the existing real Provider adapter before host startup, rejecting malformed Google location objects before owner/state access. Previously the host validated only the outer configuration and deferred adapter failure to the Worker. Read-only preflight exposes adapter identity, configuration and validation without dispatch authority. 35 targeted combined tests pass (7.879 seconds), including real construction, early rejection and unchanged files. Independent review PENDING; no fresh package was built or old acceptance inherited. Main/canonical remain unchanged because cross-chat coordination adoption is unverified. Installation, dispatch, cancellation and SMTP remain disabled. Authoritative billing/terminal receipts remain CONTRACT_MISSING. Next: build/verify a new pinned archive with isolated-Python preflight and obtain fixed-version review.

中文：固定9e2446fefc52e083430debec278886223b22716b将真实独立SQLite/schema完整性检查接入宿主启动和只读预检；33项通过，新5058文件CPython包五探针VERIFIED。独审PENDING，main/canonical未改，全部生产门禁false。
English: Fixed 9e2446fefc52e083430debec278886223b22716b wires real standalone SQLite/schema integrity checks into host startup/preflight;33 pass and fresh5058-file CPython archive five probes VERIFIED. Review PENDING;main/canonical unchanged;gates false.
Report: autonomy/evidence/u1_snapshot_admission_20261108/REPORT.md

中文：固定d43209c01e8ec21da578b62c0b6c9de2b0850399接通包内只读启动preflight，拒绝过期凭据/改变快照/重复配置键/相对路径；24项通过，新5058文件CPython包五探针VERIFIED。独审PENDING，main/canonical未改，生产门禁false。
English: Fixed d43209c01e8ec21da578b62c0b6c9de2b0850399 wires packaged read-only startup preflight and rejects expired credentials, changed snapshots, duplicate keys and relative paths;24 pass and fresh5058-file CPython package five probes VERIFIED. Review PENDING;main/canonical unchanged;gates false.
Report: autonomy/evidence/u1_startup_preflight_20261107/REPORT.md

中文：固定4fc6db7c22e16885d68b81e7309d51286e7609b7修复原生宿主创建至Job分配的崩溃窗口；20项组合与2项包内真实EXE生命周期核验通过，新5058文件CPython包五探针VERIFIED。独审PENDING，main/canonical未改，门禁false。见autonomy/evidence/u1_native_job_20261107/REPORT.md。
English:Fixed 4fc6db7c22e16885d68b81e7309d51286e7609b7 binds native child Job during creation;20 combined and2 packaged-EXE checks pass;fresh5058-file CPython archive five probes VERIFIED. Review PENDING;main/canonical unchanged;gates false. See report above.

中文：固定afbf24f263e42304d3d73f90e564e3eb48692154修复真实独立宿主启动的大分配及平方级路径扫描；27项通过，新5058文件实际CPython包五探针及最终完整性VERIFIED，引导解析3.374秒。独审PENDING，主树/canonical未改，全部生产门禁false。见autonomy/evidence/u1_bootstrap_read_20261107/REPORT.md。
English: Fixed afbf24f263e42304d3d73f90e564e3eb48692154 bounds real standalone bootstrap reads/path checks;27 pass and fresh5058-file runtime archive with five probes/final integrity VERIFIED; bootstrap3.374s. Review PENDING; main/canonical unchanged; production gates false. See autonomy/evidence/u1_bootstrap_read_20261107/REPORT.md.

中文：固定f5073c523c4d79abca82210d53b8ddae7510f330修复256MiB重复读取分配；27项通过。新真实5058文件CPython包提取完整核验VERIFIED/0，44.776278秒，回滚4960组件对应。独审PENDING，未安装，所有门禁及最终状态false。见autonomy/evidence/u1_bounded_read_20261107/REPORT.md。
English: Fixed f5073c523c4d79abca82210d53b8ddae7510f330 bounds artifact reads;27 pass. Fresh5058-file runtime archive extracted verification VERIFIED/0 in44.776278s,4960 rollback components match. Review PENDING; no installation; final states/gates false. See autonomy/evidence/u1_bounded_read_20261107/REPORT.md.

中文：固定6acaee48e045fa735862142637f0182ecf5b128e修复清单平方级碰撞扫描并持久化验收活动阶段；25项不同测试通过。旧包不含此源码，超时根因仍UNKNOWN，独审/新包PENDING，门禁false。见autonomy/evidence/u1_manifest_collision_20261107/REPORT.md。
English: Fixed 6acaee48e045fa735862142637f0182ecf5b128e bounds manifest collision checks and persists verification stages;25 distinct tests pass. Old package excludes this source; timeout cause UNKNOWN, review/new package PENDING, gates false. See autonomy/evidence/u1_manifest_collision_20261107/REPORT.md.

2026-11-07 CPython成对包已实际构建；5058归档摘要通过，4探针通过，但最终提取复核600秒超时，整体UNKNOWN / Runtime archives built, final extraction recheck UNKNOWN_TIMEOUT. Source 621955624b5b87b630ee1938d75a08d5fce0a49a; review PENDING; gates false; canonical unchanged.
Report: autonomy/evidence/u1_provider_runtime_20261107/REPORT.md

2026-11-07 固定 Provider x64 禁用归档已构建并核验114文件 / Built and checked fixed Provider x64 disabled archives. Source 2cca3f3891de2dc2e79765f96c92702a67e58009; CPython NOT_BUNDLED; review PENDING; main/canonical unchanged.
Report: autonomy/evidence/u1_provider_package_20261107/REPORT.md

2026-11-07 已集成 Provider 桥接与后端准入候选 / Integrated Provider bridge and backend candidate: 204d299ebfb137310ba8b348f9e0dd9f1721a0b6; 42 PASS; review PENDING. Main/canonical unchanged; gates false.
Report: autonomy/evidence/u1_provider_integrated_20261107/REPORT.md

2026-11-06 Provider backend admission: source 077967705772ef9fc994e6e30a49f7e647da99ba; 31 PASS; review PENDING. 隔离分支已修复 Provider 请求在持久意图前的校验；主线/canonical 未修改，生产门禁保持关闭。
Report: autonomy/evidence/u1_provider_backend_admission_20261106/REPORT.md

中文：独立分支创建时 Job 绑定修复固定 ed1f89fe95c7e5d4d955a632df895beac4c5e79c，36 项组合通过，独审 PENDING。未合并主线/修改 canonical；详见 autonomy/evidence/u1_job_creation_binding_20261106/REPORT.md。全部生产门禁 false。
English: Isolated creation-time Job binding fix ed1f89fe95c7e5d4d955a632df895beac4c5e79c passed 36 combined tests; independent review PENDING. Not merged; canonical unchanged. See report above. All production gates false.

中文：独立分支协调修复固定 688beeb67b089a8bd0545c9b9fbd5818f8b36870，32 项组合通过；独审 PENDING，未合并主线，canonical 未修改。锁/祖先身份、失败记录和清理不确定保留已修复；跨聊天共同接入与创建到 Job 绑定窗口仍待验收。详见 autonomy/evidence/u1_coordination_hardening_20261106/REPORT.md。全部门禁 false。
English: Isolated coordination fix 688beeb67b089a8bd0545c9b9fbd5818f8b36870 passed 32 combined checks; independent review PENDING, not merged and canonical unchanged. Identity pinning and failure/uncertain-cleanup recording are fixed; shared chat adoption and creation-to-Job crash acceptance remain open. All gates false. See report above.

中文：2026-11-06 开发协调候选固定源码 f2640e425bbc9c244ce59f98cfca593920e83526；本机多进程四项通过。候选在独立分支 codex/u1-dev-coordination-20261106，未合并主线、独审 PENDING；跨环境共享、锁文件身份和总控接入尚未验证。详见 autonomy/evidence/u1_dev_coordination_20261106/REPORT.md。生产门禁不变。
English: The development-coordination candidate is pinned at f2640e425bbc9c244ce59f98cfca593920e83526; four local multiprocess checks passed. It is on branch codex/u1-dev-coordination-20261106, not merged to main; independent review is PENDING. Cross-environment sharing, lock-file identity and controller integration remain unverified. See autonomy/evidence/u1_dev_coordination_20261106/REPORT.md. Production gates remain unchanged.

中文：固定13d0b150701a0b8975875ae89db970a64a23edde修复Worker不完整Owner摘要关联及缺失业务查询的准入边界，30项组合通过；独审PENDING、新包未构建，不继承旧包验收。所有门禁false。详见autonomy/evidence/u1_worker_admission_20261106/REPORT.md。
English: Fixed 13d0b150701a0b8975875ae89db970a64a23edde rejects partial owner joins and missing Provider search before adapter construction;30 combined tests pass. Review PENDING, no new package or inherited acceptance; all gates false. See autonomy/evidence/u1_worker_admission_20261106/REPORT.md.

中文：固定373899370dcc55037c5f7f89654657a41389c56c分阶段宿主/归档构建；24项定向通过。真实终态见autonomy/evidence/u1_build_phases_20261105/REPORT.md。独审PENDING，最终状态与门禁false。
English: Fixed 373899370dcc55037c5f7f89654657a41389c56c phased host/archive build;24 targeted pass. Actual outcomes: autonomy/evidence/u1_build_phases_20261105/REPORT.md; independent review PENDING, final statuses/gates false.

中文：固定fe51fbd05ed17eee727a25e2cd3a7b3430643249直接归档构建修复；22定向通过，其余终态见autonomy/evidence/u1_direct_archive_20261105/REPORT.md。独审PENDING，所有最终状态/门禁false。
English: Fixed fe51fbd05ed17eee727a25e2cd3a7b3430643249 direct-archive build fix;22 targeted pass. Outcomes: autonomy/evidence/u1_direct_archive_20261105/REPORT.md; review PENDING, final statuses/gates false.

中文：固定11bf1f9发布器路径元数据优化完成；20定向通过，848全量保留37FAIL/17ERROR且ID与基线一致。新包及核验结果见autonomy/evidence/u1_install_namespace_20261105/validation/REPORT.md；独审PENDING，所有最终状态与门禁false。
English: Fixed11bf1f9 reduces publisher path metadata probes;20 targeted pass,848 retains37 failures/17 errors with unchanged IDs. Package/verification evidence: autonomy/evidence/u1_install_namespace_20261105/validation/REPORT.md; review PENDING, all final states/gates false.

中文：固定1bf8d59aa1d9ce8ecb78da6590626bcf4380962f修复正式安装输入的平方级路径冲突扫描；20项定向通过，新源码全量/新包/独审PENDING。全部最终状态及门禁false。详见autonomy/evidence/u1_install_namespace_20261105/REPORT.md。
English: Fixed1bf8d59aa1d9ce8ecb78da6590626bcf4380962f removes quadratic namespace scans in formal installer validation;20 targeted pass. New-source full regression/package/review PENDING; all final states/gates false. Seeautonomy/evidence/u1_install_namespace_20261105/REPORT.md.

中文：固定21568c8267d7d20b3127eab8d3f5c866202868fd接通信任签名中的Provider查询参数与后端幂等摘要，46项定向通过；全量848项37FAIL/17ERROR，见ID对比。新禁用包解压UNKNOWN，包内操作探针PASSED。独审/正式业务闭环PENDING，全部最终状态及门禁false，BUSINESS_GROWTH=UNKNOWN。见autonomy/evidence/u1_search_binding_20261105/REPORT.md。
English: Fixed21568c8267d7d20b3127eab8d3f5c866202868fd wires signed Provider search arguments into the backend idempotency digest;46 targeted pass, full848 with37 failures/17 errors per ID comparison. Disabled archive extractionUNKNOWN, packaged operation probePASSED. Review/business closure PENDING, final states/gates false, BUSINESS_GROWTH UNKNOWN. Seeautonomy/evidence/u1_search_binding_20261105/REPORT.md.

中文：固定6de5cf3d421e0073be905a57e0dd3cd2cc1024a6接入有界Worker操作解析和原claim摘要绑定，24项定向通过；全量848项37FAIL/17ERROR，见ID对比。新禁用包解压VERIFIED，包内操作探针PASSED。独审/正式业务闭环PENDING，全部最终状态及门禁false，BUSINESS_GROWTH=UNKNOWN。见autonomy/evidence/u1_worker_operation_20261105/REPORT.md。
English: Fixed6de5cf3d421e0073be905a57e0dd3cd2cc1024a6 wires bounded Worker operation parsing and original-claim digest binding;24 targeted pass, full848 with37 failures/17 errors per ID comparison. Disabled archive extractionVERIFIED, packaged operation probePASSED. Review/business closure PENDING, final states/gates false, BUSINESS_GROWTH UNKNOWN. Seeautonomy/evidence/u1_worker_operation_20261105/REPORT.md.

中文：固定9d5ecb6b8062f916ac7869957eb6589665ce9113接通真实适配器Worker预检与ProcessBackend工厂，默认合同缺失exit78且不请求/不签回执，UNKNOWN禁止重放。20定向通过；全量848项37FAIL/17ERROR见ID比较。新5057文件禁用包解压VERIFIED，包内Worker探针PASSED。独审及业务闭环PENDING，所有最终状态及门禁false，BUSINESS_GROWTH=UNKNOWN。见autonomy/evidence/u1_provider_worker_20261105/REPORT.md。
English: Fixed 9d5ecb6b8062f916ac7869957eb6589665ce9113 wires real-adapter Worker preflight and ProcessBackend factory; missing contracts exit78 without requests/receipts and UNKNOWN cannot replay.20 targeted pass; full 848 with 37 failures/17 errors per ID comparison. New 5057-file disabled archive extraction VERIFIED, packaged Worker probe PASSED. Review/business closure PENDING, final states/gates false, BUSINESS_GROWTH UNKNOWN. See autonomy/evidence/u1_provider_worker_20261105/REPORT.md.

中文：固定240f614fd694d48eb19edcfd8f8d3e187722875d修复执行文件和Worker替换竞态，句柄持有到清理及持久化。22项定向通过，Bridge/Owner独立7/12通过；同进程18项6护栏ERROR保留。全量848项37FAIL/17ERROR与实测基线ID一致。新包解压核验VERIFIED，独审及Worker入口PENDING，所有最终状态和门禁false，BUSINESS_GROWTH=UNKNOWN。详见autonomy/evidence/u1_executable_pins_20261104/REPORT.md。
English: Fixed 240f614fd694d48eb19edcfd8f8d3e187722875d pins executable/Worker through cleanup and persistence. 22 targeted pass; separate Bridge/Owner 7/12 pass; combined 18 retains 6 guard errors. Full 848 has unchanged 37 failure/17 error IDs. New archive verification VERIFIED; review/Worker PENDING; all final states/gates false, BUSINESS_GROWTH UNKNOWN. See autonomy/evidence/u1_executable_pins_20261104/REPORT.md.

中文：固定594cd0a513af461baac867a00e1f431339de3d7d接入批准配置真实适配器，修复browser_maps实例缓存串用和构造写目录。27项定向通过；隔离848项37FAIL/17ERROR与实测基线ID一致。新5056文件禁用包及包内适配器探针完成；解压核验VERIFIED，回滚4960个host组件对应。独审PENDING、Worker入口PENDING、权威费用终态CONTRACT_MISSING；所有最终状态与门禁false，BUSINESS_GROWTH=UNKNOWN。详见autonomy/evidence/u1_adapter_binding_20261104/REPORT.md。
English: Fixed594cd0a513af461baac867a00e1f431339de3d7d constructs real adapters from approved configuration and fixes browser_maps instance cache leakage/construction writes.27 targeted pass; clean848 has identical37 failure/17 error IDs to measured baseline. New5056-file disabled archive and packaged adapter probe complete; extracted verificationVERIFIED;4960 rollback host components match. Review/Worker entrypoint PENDING, authoritative cost/terminal contracts missing; all final states/gates false and BUSINESS_GROWTH UNKNOWN. Seeautonomy/evidence/u1_adapter_binding_20261104/REPORT.md.

中文：固定f85a5f070a848823ffd5abe438afe4a41687583a新增ProcessBackend批准Provider引用的启动前校验、全执行期固定、CLI转发与持久执行绑定；38项组合通过，初轮期限失败已保留。宿主实际构造与正式Worker入口仍待接通；新源码全量/新包/独审PENDING，不继承69eb包/测试。所有最终状态与门禁false，BUSINESS_GROWTH=UNKNOWN。详见autonomy/evidence/u1_worker_reference_20261104/REPORT.md。
English: Fixedf85a5f070a848823ffd5abe438afe4a41687583a adds pre-intent validation, execution-lifetime pins, CLI forwarding and durable Provider-reference binding to ProcessBackend.38 combined tests pass; initial deadline failure is retained. Actual host construction/formal Worker entrypoint remain pending; new-source full regression/package/review PENDING, without inheriting69eb evidence. All final statuses/gates false, BUSINESS_GROWTH UNKNOWN. Seeautonomy/evidence/u1_worker_reference_20261104/REPORT.md.

中文：固定69eb1887800f046b6d860cbefad6bd99f3c35169接通安装计划至宿主Provider引用/终身固定，修复Publisher外置块和完整包容量阻断。42项组合通过；干净tests/848项37FAIL/17ERROR与固定ec45401基线ID一致。新真实5056文件禁用包四项运行和包内接线探针通过；最终完整性复核600秒超时UNKNOWN，回滚4964组件对应通过。独审PENDING，Worker传播未实现，权威费用回执CONTRACT_MISSING；所有最终状态与安全门禁false，BUSINESS_GROWTH=UNKNOWN。详见autonomy/evidence/u1_host_provider_binding_20261104/REPORT.md。
English: Fixed69eb1887800f046b6d860cbefad6bd99f3c35169 wires Provider references from installation plan to host lifetime pins and repairs Publisher blob-backed/full-package acceptance.42 combination tests pass; clean tests/848 has matching37 failure/17 error IDs against fixed ec45401. New actual5056-file disabled archive passes four runtime checks and packaged wiring probe; final integrity is UNKNOWN after600-second timeout;4964 rollback components match. Review PENDING, Worker propagation unimplemented, authoritative cost/receipt contracts missing; all final states/gates false and BUSINESS_GROWTH UNKNOWN. Seeautonomy/evidence/u1_host_provider_binding_20261104/REPORT.md.

中文：固定源码ec45401ad7b0ca016fe6e1b15f58462e929623ff接入外部Provider批准配置绝对路径/SHA256读取，并纳入真实5056文件AMD64禁用包。14+1项分进程通过，包内配置探针及四项包内检查/最终完整性复核通过，回滚4964组件对应通过。干净固定基线/候选各848项，37FAIL/17ERROR的ID一致，不称全绿；主树额外历史路径ERROR保留。独审PENDING，宿主到Worker配置传播尚未实现，权威费用/回执CONTRACT_MISSING。所有最终交付状态及安全开关false，BUSINESS_GROWTH=UNKNOWN。唯一下一动作：固定宿主计划向原业务Worker传播批准配置路径/摘要。详见autonomy/evidence/u1_provider_environment_20261104/REPORT.md。
English: Fixed ec45401ad7b0ca016fe6e1b15f58462e929623ff adds external approved Provider configuration loading by absolute path/SHA256 and ships it in the actual5056-file AMD64 disabled archive.14+1 tests pass separately; packaged configuration probe, four packaged checks/final integrity, and4964 rollback-component parity pass. Clean baseline/candidate each run848 tests with identical37 failure/17 error IDs, not a fully passing suite; extra main-tree historical-path errors are retained. Review PENDING, host-to-Worker propagation unimplemented, authoritative cost/receipt contracts CONTRACT_MISSING. All final states/gates false; BUSINESS_GROWTH UNKNOWN. Single next action: propagate approved configuration path/digest through pinned host plan to original Worker. See autonomy/evidence/u1_provider_environment_20261104/REPORT.md.

中文：正式Provider跳转边界修复固定5dde9061ee97eeb756ed52f40b30b18afd2ddb8b，8项离线测试通过；真实请求/权威费用/结算尚未验收。独审PENDING，无新包，三板块所有最终状态false，安全开关false。详见autonomy/evidence/u1_provider_redirect_20261104/REPORT.md。
English: Real Provider redirect fix pinned at 5dde9061ee97eeb756ed52f40b30b18afd2ddb8b;8 offline tests pass. Actual requests, authoritative charges and settlement remain unaccepted; review PENDING, no new archive, all final states and gates false. See autonomy/evidence/u1_provider_redirect_20261104/REPORT.md.

中文：固定源码5b56b3d1a903f10726304599d0d9bfd1c1df698b移除原bd_orchestrator导入时output创建，加入显式绝对--output-dir，仅报告写入时创建。14项离线组合通过；21项扩展中6项被DEVELOPMENT_EXTERNAL_TRANSPORT_DISABLED拒绝，未绕过。未重建包；独审PENDING，所有交付/生产状态和开关仍false。下一步批准配置加载分离及固定宿主参数接线。详见 autonomy/evidence/u1_orchestrator_output_20261104/REPORT.md。
English: Fixed 5b56b3d1a903f10726304599d0d9bfd1c1df698b removes original-entry output creation on import and adds explicit absolute --output-dir with creation only at report writing.14 offline combination tests pass;6 of21 expanded tests hit the retained development transport guard. No rebuilt archive; review PENDING, delivery/production states and gates remain false. Next separate approved configuration loading and wire pinned host arguments. See autonomy/evidence/u1_orchestrator_output_20261104/REPORT.md.

中文：固定源码3f02af1b95b45cad7ecbf942b2c252022f046e1a修复真实发现入口缺少9个根模块的安装包缺陷。旧固定包同探针缺bd_db失败，新包5054文件、46模块来源、四项包内检查和最终文件复核全部通过；回滚4964组件对应通过，不代表实际回滚。7项定向通过；新SHA全量NOT_RUN，独审PENDING，外部合同CONTRACT_MISSING。所有开发/发布/生产状态仍false，BUSINESS_GROWTH=UNKNOWN，allow_install/allow_dispatch/allow_cancel_dispatch/SMTP=false。下一步分离原bd_orchestrator入口的批准配置与可写状态目录，完成原owner到业务worker安全接线。详见 autonomy/evidence/u1_business_dependencies_20261104/REPORT.md。
English: Fixed 3f02af1b95b45cad7ecbf942b2c252022f046e1a repairs nine missing root dependencies of the real discovery engine. The same probe fails on the old archive with missing bd_db; the new5054-file archive passes46 application origins, four packaged checks and final integrity revalidation.4964 rollback components match without actual rollback.7 targeted tests pass; full regression NOT_RUN, independent review PENDING, external contracts CONTRACT_MISSING. All development/release/production states and safety gates remain false; BUSINESS_GROWTH UNKNOWN. Next separate approved configuration and writable state for the original bd_orchestrator entry and complete safe original-owner-to-worker wiring. See autonomy/evidence/u1_business_dependencies_20261104/REPORT.md.

中文：固定源码d209c53d6d3211cdca732d137fb2ebcfbec50f61统一现有Provider合同声明；复用Google Places/browser_maps并保持SerpAPI禁用，内部命名不再阻断。实际x64禁用安装包5045文件包含CPython、12个wheel、Provider及token哈希绑定；包SHA256=25ee2160fdac40d95a3eca38aa1907671b61a447a115ed2feee39465873b0c94，回滚工具SHA256=67ff4c7c12b7f997add396e7682df12a46ba3a972a68cf1359e48d254286269c。实际解压四项与最终复核通过；回滚归档4964组件对应通过，不代表真实回滚。16项定向通过；20项发现组合中1项旧证据路径静态扫描ERROR保留。权威计费/操作终态等精确字段CONTRACT_MISSING，独审PENDING，开发/发布/生产部署/生产验收状态均false，BUSINESS_GROWTH=UNKNOWN。见 autonomy/evidence/u1_provider_contracts_20261104/REPORT.md。
English: Fixed d209c53d6d3211cdca732d137fb2ebcfbec50f61 exposes unified existing Provider contracts, reuses Google Places/browser_maps and keeps SerpAPI disabled; internal naming is no blocker. Actual x64 disabled package has5045 files including CPython,12 wheels, Providers and token digest binding. InstallSHA256=25ee2160fdac40d95a3eca38aa1907671b61a447a115ed2feee39465873b0c94; rollback-toolsSHA256=67ff4c7c12b7f997add396e7682df12a46ba3a972a68cf1359e48d254286269c. Four extracted checks and final revalidation pass;4964 rollback components match, without actual rollback.16 targeted checks pass; one historical evidence-path static-scan ERROR remains in20 discovery combination tests. Exact authoritative billing/operation-terminal fields remain CONTRACT_MISSING; independent review PENDING; all development/release/deployment/production-acceptance states false and BUSINESS_GROWTH UNKNOWN. See autonomy/evidence/u1_provider_contracts_20261104/REPORT.md.

# U1 安装认证绑定 / Installed credential binding

时间 / Time: 2026-11-04T06:15:03.486948+00:00
固定源码 / Fixed source: c3ef1fcc94d1792421a8e15aa6e916be16cd67de

中文：安装器现在生成rokt.u1-python-runtime.v2，将批准计划的token_sha256纳入已固定runtime.json。bootstrap严格要求v2摘要并传入--token-sha256；宿主对同一次读取的原始token字节校验后才解码、访问快照/原owner或启动监听。变更后的token不能仅凭格式合法成为新的认证凭据。历史v1配置及直接CLI保留旧兼容路径，不把它们声明为新增摘要绑定。没有自动轮换凭据或提升权限。
English: Installer generation now emits rokt.u1-python-runtime.v2 and carries approved token_sha256 into pinned runtime.json. Bootstrap requires and forwards the v2 digest. The host checks the exact bytes from a single token read before decoding, snapshot/owner access or listener startup. A replacement token cannot become the credential merely by having valid syntax. Historical v1 configuration and direct CLI retain legacy compatibility and are not claimed to have the new binding. No automatic credential rotation or privilege grant was added.

验证 / Validation:
- python -B -m unittest test_bootstrap_arguments test_u1_provision test_u1_host_runtime.HostRuntimeTests.test_changed_provisioned_token_rejects_before_listener_or_state -q: 6 PASS / 4.740s.
- python -B -m unittest test_packaged_runtime_plan test_install_command test_bootstrap_arguments test_u1_provision -q: 13 PASS / 11.707s.
中文：包含实际PowerShell配置生成、独立Python进程拒绝token替换/非法摘要且不创建状态目录、缺失v2绑定拒绝、v1及原owner参数兼容。未重复受权限拒绝的HTTP监听测试。没有新源码全量回归或独审，均不得继承旧SHA结论。
English: Checks cover actual PowerShell generation, isolated Python rejection of token replacement/invalid digests without creating state, missing v2 binding rejection, and v1/original-owner argument compatibility. Permission-denied HTTP listener tests were not mechanically repeated. Full regression and independent review were not performed for this source and old-SHA results are not inherited.

既有证据 / Existing evidence: a3ce4a5安装包SHA256 1e753098a2424745b8423a10b74b03dc1244ca5091d6b53674b0c977ed39917b，回滚归档SHA256 52f9c951623b8bcc3c0237046d56e345ec7501377dcbe9d8a328da1087169e8d。新源码未入这两个旧包。既有ROLLBACK_A3CE4A5_PARITY_REPORT.json已完成VERIFIED/4961对应组件，仅归档清单一致性；rollback_verified仍false。旧72208会话句柄不可恢复，依实际持久报告更新定位状态，不声称执行过回滚。旧解压验证仍FAILED/WinError10013。
The prior a3ce4a5 archive hashes above do not contain this source. Durable rollback parity now reports VERIFIED for4961 components, scoped to archive/manifest parity only; rollback_verified stays false. Session72208 is no longer available; durable output, not an inferred process exit, establishes the result. Extracted delivery acceptance remains FAILED with WinError10013.

独审 / Independent review: PENDING. 全量 / Full regression: NOT_RUN_FOR_THIS_SHA.
DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; smtp_enabled=false.

未执行 / Not performed: 生产安装、服务启用、Inventory采集、生产数据库写入、发信、权限或网络门禁修改 / production installation, service enablement, Inventory collection, production DB writes, email, permission or network-gate changes.
风险 / Risk: 完整包重建与服务启动未验收；旧v1为兼容入口，不提供新增摘要保证 / full rebuild and service startup remain unaccepted; legacy v1 does not provide the added digest guarantee.
敏感信息检查 / Sensitive-data check: 仅临时fixture token，报告不含实际token或密钥 / fixture tokens only; no actual credentials or secrets in this report.
运行限制 / Runtime limits: 3小时周期、45分钟提示上限、最多两条重线保持；平台无硬超时字段，未宣称强制配置 / three-hour schedule,45-minute prompt limit and at most two heavy workstreams retained; no platform hard-timeout field claimed.

下一动作 / Next action: 将新固定源码整合进完整运行时归档并验证安装配置到服务启动链；独审保持PENDING，回环HTTP权限故障及正式Provider合同仍未解决。
Integrate the new fixed source into full-runtime archives and validate installer configuration through service startup; review remains PENDING, loopback HTTP permission failure and formal Provider contracts remain unresolved.

---

中文：a3ce4a5真实成对归档构建退出0，5028清单文件，安装SHA256 1e753098a2424745b8423a10b74b03dc1244ca5091d6b53674b0c977ed39917b；回滚SHA256 52f9c951623b8bcc3c0237046d56e345ec7501377dcbe9d8a328da1087169e8d；外层清单SHA256 d940f542ab2d074f8b07def277697ffd5a46747af152ff072b9e5e28aab3786a。独立解压80348退出1：入口导入/包内子进程、pip check、原生运行时均通过；回环HTTP失败WinError10013，整体FAILED。不得宣布整包通过。回滚逐组件核对72208运行中，不执行实际回滚。所有最终状态与门禁false。

English: Actual a3ce4a5 paired archives built with exit0 and5028 manifest files. Install SHA256 1e753098a2424745b8423a10b74b03dc1244ca5091d6b53674b0c977ed39917b; rollback SHA256 52f9c951623b8bcc3c0237046d56e345ec7501377dcbe9d8a328da1087169e8d; outer manifest SHA256 d940f542ab2d074f8b07def277697ffd5a46747af152ff072b9e5e28aab3786a. Independent extraction80348 exits1: entrypoint imports/packaged child, pip check and native runtime validation pass, but loopback HTTP fails with WinError10013; overall FAILED. Package acceptance is not established. Rollback component parity72208 is running without performing rollback. All acceptance states and gates remain false.

中文：固定eae57b2后续构建器将双语离线生命周期说明及CPython/业务wheel锁文件从固定Git纳入安装清单和回滚归档。定向文档入包测试1项通过（8.874秒），宿主编译为测试替身，不是实际运行时整包证据。说明明确维护授权、六字段、非对称ACL、回滚工具非备份、UNKNOWN保护及所有关闭门禁。正在运行的a3ce4a5旧固定构建29556不含此新增内容；句柄仍确认运行，不能热改或冒用新版。下一步先收取旧构建并独立核验，再决定新固定候选整合。

English: Fixed eae57b2 future builder includes the bilingual offline lifecycle guide and CPython/business wheel locks from pinned Git in install manifest and rollback archive. One document-inclusion test passes in8.874s with a host compiler fixture, not actual full-runtime package evidence. Guide states maintenance authority, six-field bindings, asymmetric ACLs, tooling-not-backup limits, UNKNOWN preservation and closed gates. Live older a3ce4a5 build29556 does not contain these additions and remains confirmed running; no hot changes or newer-source claims. Next collect and independently verify that build before integrating a new fixed candidate.

中文：验证器固定d897067逐项持久化检查开始/结束与输出，后续失败保留此前证据；5项相关测试通过（0.371秒）。新增实际预检：a3ce4a5的67个待打包应用Python文件逐字节匹配Git；使用旧03eca14解压包内CPython隔离导入六个入口，28个已加载仓库模块来源均位于待打包应用目录，包内隔离子进程返回ISOLATED_CHILD_OK，整体返回0。APP_IMPORT_PREFLIGHT.json明确这是旧运行时与固定应用的组合预检，不是最终归档验收。构建29556仍运行，所有最终状态与门禁false。

English: Fixed verifier d897067 persists each check start/completion/output and preserves evidence after later failures; five related tests pass in0.371s. Actual preflight compares all67 staged a3ce4a5 application Python files byte-for-byte against Git, then uses the older03eca14 extracted CPython for isolated imports of six entrypoints. All28 loaded repository module origins remain within staged application files; an isolated packaged child returns ISOLATED_CHILD_OK; overall exit0. APP_IMPORT_PREFLIGHT.json explicitly scopes this to an old-runtime/fixed-application preflight, not final archive acceptance. Build29556 remains running; all acceptance states and gates false.

中文：固定2c52595：Bootstrap三种Owner模式参数逐项转发与关闭门禁/互斥Owner拒绝测试2项通过（0.089秒）；run_module仅入口捕获替身，不是真实服务验收。整包验证器增加仅回环HTTP临时fixture探测：开发解释器实际运行客户端遭WinError10013，退出1；线程退出清理完成，保留原始失败HTTP_PROBE_DEVELOPMENT_OUTPUT.txt，不放宽权限或跳过检查。此失败不证明业务缺陷，原因仍未定位；7877/8791未验证。归档构建29556仍确认运行，不能继承源码测试或宣称完成。

English: Fixed2c52595: two Bootstrap tests pass in0.089s for exact owner-mode forwarding and closed-gate/mutual-owner rejection. run_module is an entrypoint capture fixture, not service acceptance. Delivery verifier adds temporary loopback HTTP fixtures. Actual development-interpreter probe fails with client WinError10013 and exit1; server thread cleanup completed. Raw HTTP_PROBE_DEVELOPMENT_OUTPUT.txt retained without relaxing permissions or skipping checks. This does not establish a business defect; cause remains unlocalized, and ports7877/8791 are unverified. Archive build29556 is confirmed live; source-test results cannot establish package completion.

中文：固定验证器b51b08e新增整包独立解压只读验证：先校验外层清单/源码/关闭门禁，再固定宿主和Python内容清单，用包内-I -B导入六个离线入口并核对仓库模块来源，验证包内子进程、pip check和原生运行时，执行后复核整包。失败/超时持久化FAILED/UNKNOWN，已有报告不覆盖。5项安全边界测试通过（0.407秒），均为测试输入，不是实际整包通过。a3ce4a5成对归档构建29556仍确认运行；install目录已出现，尚无终态。下一步收取构建结果后对该固定包运行验证器。正式合同CONTRACT_MISSING，所有最终验收及门禁保持false。

English: Fixed verifier b51b08e adds read-only extracted delivery checks: outer manifest/source/closed gates, pinned host and Python content, packaged -I -B imports of six offline entrypoints with origin checks, packaged child process, pip check and native integrity; package rechecked afterward. Failure/timeout persist FAILED/UNKNOWN, existing reports are immutable. Five safety-boundary tests pass in0.407s using test inputs, not actual delivery acceptance. Paired a3ce4a5 archive build29556 is confirmed live; install directory has appeared without terminal result. Next run the verifier against that fixed completed archive. Formal contract remains CONTRACT_MISSING; all acceptance states/gates false.

中文：固定deeec72完整tests/回归结束：基线842项/37失败/19错误；候选847项/37失败/18错误。逐ID比较无新增失败或错误；减少一项基线错误不构成根因修复证明。5项原生检查通过。全套仍未通过，结果不继承至a3ce4a5；根目录测试另计。成对归档构建29556仍在运行。

English: Fixed deeec72 tests/ regression completed: baseline842/37 failures/19 errors; candidate847/37 failures/18 errors. ID comparison shows no added failures/errors; one absent baseline error is not proof of a root-cause fix. Five native checks pass. The suite remains failing, results do not transfer to a3ce4a5, and root-level tests are separate. Paired archive build29556 remains running.

中文：真实独立解压验证完成：03eca14归档解压到新目录，包内CPython3.13.12以-I -B启动、关键依赖导入、pip check、原生--validate-runtime均返回0；sys.path全部位于包内运行时。报告EXTRACTED_03ECA14_REPORT.json outcome=VERIFIED。此证据仅覆盖旧候选运行时，不覆盖完整业务闭包、应用发布、安装/回滚或新版源码。新源码a3ce4a5开始整合应用、Publisher、宿主、完整Python到安装/回滚两份归档，句柄29556运行中；完整回归7375/65011仍运行。所有最终状态与门禁false。

English: Actual independent extraction verified:03eca14 archive extracted to a new directory; packaged CPython3.13.12 starts with-I -B, key dependency imports, pip check and native--validate-runtime all return0; all sys.path entries are within packaged runtime. EXTRACTED_03ECA14_REPORT.json outcome=VERIFIED. Evidence covers only that older runtime, not complete business closure, application publication, install/rollback or newer source. New fixed sourcea3ce4a5 starts paired archives containing application, Publisher, host and full Python under live handle29556. Full regressions7375/65011 remain running. All final acceptance states and gates false.

中文：后续收取结果：03eca14宿主运行时组包退出0，4950文件。压缩包SHA256 6017c9239f31e0c64dffe51dbf906427e62726a95465e70c28807835706f048d；清单SHA256 7961bc615fa7c92da4e849cec88832753a80babbf808bcd0b2b1761790f41dbc。真实解压验证刚启动，未判定完成。以上更正紧前构建RUNNING快照，保留历史。

English: Later terminal observation:03eca14 host/runtime build exited0 with4950 files. Archive SHA256 6017c9239f31e0c64dffe51dbf906427e62726a95465e70c28807835706f048d; manifest SHA256 7961bc615fa7c92da4e849cec88832753a80babbf808bcd0b2b1761790f41dbc. Actual extracted verification has started and is not yet complete. This supersedes the immediately preceding RUNNING snapshot while preserving history.

中文：固定代码75024e3：解压验证在任何操作前以新文件独占预留报告；失败记录FAILED，超时/中断记录UNKNOWN，全部门禁false，已有报告禁止覆盖。3项边界及失败状态测试通过（0.155秒）。另固定deeec72回归执行器先运行原生准入，再发现业务测试，不卸载保护、每个测试只计一次；候选5项原生准入已通过，剩余回归运行中。基线5a8394d受跟踪文件无差异，两端使用同一执行器；句柄7375/65011。03eca14组包句柄39800仍运行。完整回归与真实解压验收均未完成。

English: Fixed code75024e3 reserves a new report before extraction, records FAILED or timeout/interruption UNKNOWN, retains false gates, and refuses existing reports. Three boundary/failure-state tests pass in0.155s. Separately, fixed deeec72 regression runner executes offline native admission before business discovery without uninstalling guards or dropping test counts. Five candidate native checks pass; remaining regression is running. Baseline5a8394d has no tracked differences and both sides use the same runner under handles7375/65011. Older03eca14 build handle39800 remains running. Neither full regression nor actual extracted acceptance is complete.

中文：固定源码3c7395e：新增独立解压验证工具，批准压缩包摘要后检查ZIP成员再解压；随后固定宿主/运行时清单，用包内Python隔离导入及pip check，并调用原生只读运行时校验。真实压缩包尚未产出，以上真实包验证未执行。解压边界2项通过（0.090秒）；首次测试失败因Windows ZIP写入器规范化反斜杠样本，修正原始成员名称后通过，初次失败保留。03eca14旧构建句柄39800仍运行，不能重复启动或继承旧SHA结果。

English: Fixed source3c7395e adds independent extracted verification: approved archive digest, ZIP boundary validation, pinned host/runtime manifests, isolated imports/pip check using packaged Python, and native read-only runtime verification. Real archive probes have NOT run because the archive is not yet available. Two extraction boundary tests pass in0.090s. Initial failure arose because the Windows ZIP writer normalized the raw backslash attack fixture; preserving its raw member name fixes the fixture. Initial failure is retained. Older03eca14 build handle39800 remains running; no restart or cross-SHA result inheritance.

中文：固定源码1b14f6e：运行时组包使用已有固定句柄读取源文件，仍复核摘要并最终重验证全部身份；阶段日志progress.jsonl在关键阶段与每128文件记录并fsync，区分输入固定、布局核验、复制、最终重核与压缩。定向2项通过（1.746秒），仅证明小型测试输入行为，不证明完整CPython组包性能或完成。旧固定03eca14构建句柄39800仍确认运行，无阶段日志，不重启、不判定失败或完成。

English: Fixed source1b14f6e reads runtime sources through existing pinned handles, retains digest checks and final identity revalidation. Durable progress.jsonl records major stages and every128 files with fsync, distinguishing pinning, layout validation, copying, final validation and archive creation. Two focused tests pass in1.746s; these small fixtures do not prove full CPython assembly completion or performance. Older03eca14 build handle39800 remains confirmed running without stage logs; it is neither restarted nor declared failed/complete.

中文：固定源码c7124cc：显式v3运行计划用包内Python执行安装辅助程序，生成Supervisor v2固定到Code Root/runtime/python/python.exe及其内容清单。Publisher将计划中的源路径与宿主v2清单摘要交叉绑定，批准六字段不变、安装门禁保持关闭。3项配置生成/旧计划兼容通过；首次Publisher验证因内容清单2MiB与通用256MiB固定上限冲突失败，修复为专用2MiB后2项通过，初次失败原始输出保留。真实宿主构建仍是旧固定03eca14，句柄39800运行中，不能继承为c7124cc验收。补充CIM进程观测被本机权限拒绝，未提升权限；句柄轮询仍确认运行。

English: Fixed source c7124cc: explicit v3 plan uses packaged Python for installation helper execution and generates Supervisor v2 bound to Code Root/runtime/python/python.exe and its content manifest. Publisher cross-binds plan source paths/digests to host-v2 entries. Six approval fields remain unchanged and installation stays gated off. Three config/legacy compatibility tests pass. Initial Publisher check failed due2MiB versus generic256MiB pin limits; a dedicated2MiB manifest limit fixes this and two tests pass. Initial raw failure retained. Real host build remains pinned to older03eca14 under live handle39800; results cannot be inherited by c7124cc. Additional CIM process observation was denied; no elevation attempted. Handle polling still confirms running.

中文：固定源码03eca14：宿主v2组包工具已纳入，固定宿主清单及完整运行时摘要，逐文件复制；Publisher接受显式v2和零字节依赖，允许合法加号路径，仍检查文件摘要与所有权保留路径。b008663发布/Bootstrap及原发布回滚10项通过（182.509秒）；本轮宿主v2组包/Publisher及实际PowerShell请求2项通过（8.779秒）。真实CPython宿主组包运行中，句柄39800。该宿主包尚未含完整应用发布包，运行计划安装路径绑定仍待完成；不标记PACKAGE_COMPLETE。

English: Fixed source03eca14 adds pinned host-v2 assembly from host/runtime manifests, copying one file at a time. Publisher supports explicit v2, empty dependency files and legitimate plus paths while retaining digest and reserved ownership checks. b008663 release/Bootstrap and original publication rollback:10 tests passed in182.509s. Current host-v2/Publisher and actual PowerShell request:2 tests passed in8.779s. Real CPython host assembly is running under handle39800. This host candidate is not the complete application release; installed runtime-plan path binding remains pending. PACKAGE_COMPLETE remains false.

中文：固定源码b008663：新增显式rokt.release-manifest.v2，最多8192文件、总1GiB、单文件256MiB；逐文件构建，旧v1仍512文件/128MiB。Bootstrap同步识别v2与规范化清单，允许合法加号路径，保留逐文件哈希及未列文件拒绝。原宿主包及Publisher仍待统一；未生成完整安装包，最新完整回归与独审未完成。

English: Fixed source b008663: explicit rokt.release-manifest.v2 supports8192 files,1GiB total and256MiB per file with file-at-a-time construction. Legacy v1 retains512 files/128MiB. Bootstrap shares v2 and canonical manifest checks, permits legitimate plus paths, and retains digest/unlisted-file rejection. Host package and Publisher alignment, complete installation archive, full regression and independent review remain pending.

中文：固定代码8525fb7：原PowerShell安装事务已传递file_sources路径与已批准SHA256；Python接收端逐文件复核后进入原磁盘备份事务。生成配置和安装回执仍随原请求传递，维护授权与补偿顺序未更改。5项Python请求/磁盘事务测试通过；实际PowerShell请求生成块与Python安装/回滚测试通过（不运行服务安装）。完整CPython仍受包清单、发布仓库和Bootstrap容量/路径协议限制，完整运行时安装尚未验收。最新SHA完整回归、独立审核、真实Windows生命周期未完成。

English: Fixed code8525fb7: original PowerShell installer passes file_sources paths with approved SHA256; Python verifies each file before entering the original disk-backed transaction. Generated configuration and installation receipt remain in the original request; maintenance authority and compensation order are unchanged. Five Python request/disk transaction tests pass; actual PowerShell request construction plus Python apply/rollback passes, without service installation. Complete CPython integration still requires package, release-store and Bootstrap manifest capacity/path contracts. Full-runtime installation is NOT ACCEPTED; full regression for this SHA, independent review and real Windows lifecycle remain incomplete.

中文：追加结果：df4327e原文件事务14项、0失败1错误（76.059秒）。错误为旧硬链接注入os.link触发WinError5；5a8394d基线单独复现同项同错。新增3项通过不等于全组通过。全组原始输出保留在工具会话74455，未保存原始输出文件。

English: Additional result:df4327e original file suite ran14 tests,0 failures/1 error in76.059s. Legacy hardlink injection raises WinError5 at os.link; targeted baseline5a8394d reproduces the same error. Three new passing tests do not establish a green full group. Full raw output exists in tool session74455; no raw file was captured.

中文：新增原文件事务磁盘备份模式，17MiB文件安装/回滚、备份篡改拦截、写入后中断且禁止向前重放：3项定向测试通过。固定代码df4327e。原内嵌模式限制保持；磁盘备份模式每侧最多1GiB、单文件256MiB，日志记录摘要和备份目录身份。尚未接入PowerShell安装入口；全CPython事务、独立审核、最新整包与完整回归未完成。

English: Original file transaction now supports disk-backed payloads. Three focused tests pass:17MiB apply/rollback, blob tamper rejection, and post-effect interruption compensation with no forward replay. Fixed code df4327e. Inline limits remain unchanged; disk-backed mode permits1GiB per side and256MiB per file with digest references and store identity in the journal. PowerShell installer integration, full CPython transaction, independent review, updated package and full regression remain incomplete.

中文：完整回归已结束：候选05783f2与基线均运行842项，均37项失败；候选19项错误，基线18项错误。新增测试初始化被开发子进程保护阻止，完整回归未通过。原始输出已保留，不放宽保护。运行时安装事务待开发，Provider CONTRACT_MISSING，全部门禁及最终验收状态false。

English: Full regression ended: candidate05783f2 ran842 tests with37 failures/19 errors; baseline5a8394d ran842 with37 failures/18 errors. New setUpClass is blocked by development subprocess protection on git. Full regression NOT ACCEPTED. Raw outputs preserved; protection unchanged. Runtime installation transaction remains pending; Provider CONTRACT_MISSING. All gates and final acceptance states false.

中文：当前05783f2。C#启动Python前与Publisher固定清单4943文件校验通过；26项定向测试通过。旧服务子进程测试在基线和候选都失败，未抹去。当前完整回归运行中（74787/12397）。完整运行时安装事务未集成，独审PENDING，所有状态及门禁false。详见u1_runtime_integrity_20261104/REPORT.md。

English: Current05783f2. Native pre-Python and Publisher integrity validation passes on4943 files;26 focused tests pass. Legacy service-child test fails on baseline and candidate and is preserved. Full regression running(74787/12397). Full runtime installation remains unintegrated; independent review PENDING; all acceptance states and gates false. Seeu1_runtime_integrity_20261104/REPORT.md.

中文：当前e110302；32f0246完成12个固定wheel离线装配，4942文件237213734字节，pip check及关键导入通过，5项准入测试通过。浏览器610文件735085650字节已下载；驱动启动25秒超时，进程树清理核验通过，根因UNKNOWN。完整运行时安装事务及Bootstrap绑定未完成，未继承旧完整回归，独审PENDING。所有门禁false。

English: Current sourcee110302;32f0246 assembles12 pinned wheels offline:4942 files/237213734 bytes, passing pip check, key imports and five admission tests. Browser inputs:610 files/735085650 bytes downloaded. Driver start times out after25seconds; process-tree cleanup verified, root cause UNKNOWN. Full-runtime install transactions and Bootstrap binding remain incomplete. No inherited full-regression result; review PENDING. All gates false.

中文：追加实测：CPython3658文件独立启动通过；37c694c工程包84文件，独立Python下6个包内模块导入成功。运行时尚未接入Bootstrap安装事务，依赖闭包及独审/完整回归仍待完成；PACKAGE_COMPLETE=false。

English: Additional evidence:3658-file CPython starts independently; source37c694c produces84 package files with six imports passing under that runtime. Bootstrap installation binding, dependency closure, independent review and full regression remain pending; PACKAGE_COMPLETE=false.

# 2026-11-04 离线继续推进 / Offline development continues

中文：Provider合同CONTRACT_MISSING；独立离线开发继续。9abe85a回归837项37失败18错误，与基线相同ID，未全绿。665f499新增CPython准备工具4项准入测试通过，新SHA完整回归未执行。组合安装链72项1失败15错误；未安装，全部门禁false。详见 u1_provider_unknown_20261104/REPORT.md。

English: Provider contract CONTRACT_MISSING; independent offline work continues. 9abe85a regression:837 tests,37 failures,18 errors, same baseline IDs, not all green. 665f499 adds CPython preparation with four admission tests passing; full regression not run for that SHA. Combined installer chain:72 tests,1 failure,15 errors. Not installed; all gates false. See u1_provider_unknown_20261104/REPORT.md.

---


## 全量发现的新失败及修复 / Full-suite finding and repair
中文：前一候选032e219全量tests/836项，38失败/18错误；基线44b0ec9为833项、37失败/18错误。新增失败是UNKNOWN持久拒绝测试。根因为test_city_legacy_retry在导入时将discovery.discovery_service替换为固定历史快照，新增测试误测旧源码。未修改旧快照、未取消该测试；新增测试改用私有模块名加载并核对当前候选文件，不污染兼容套件。预加载该legacy模块后4项通过（1.092秒）；legacy与新测试共27项通过（14.671秒），详见PRELOADED_LEGACY_OUTPUT.txt及POLLUTION_REPRO_OUTPUT.txt。032e219失败证据保留，不将其称为无新增回归。
English: Previous candidate 032e219 ran836 tests with38 failures/18 errors, versus baseline44b0ec9 with833 and37/18. The new persisted-UNKNOWN failure was caused by test_city_legacy_retry replacing the canonical discovery module with a pinned historical snapshot at import. The test now privately loads and verifies current source without altering that snapshot or suppressing the compatibility test. All4 checks passed after legacy preloading (1.092s), and27 combined legacy/new checks passed (14.671s). Failed032e219 evidence is retained; no no-new-regression claim applies to it.

中文：最终测试源码固定9abe85a2bdb3227078ec87514727625ec5fec4e6，业务源码修复79262d7；最终tests/全量及Publisher/Installer/Host组合已重新启动。实际session分别54579和31239；完成前不声明通过，RUNNING_HANDLES.json仅为定位记录，续跑必须实查进程句柄。所有门禁仍false。
English: Final test source is9abe85a2bdb3227078ec87514727625ec5fec4e6 with business fixes from79262d7. Final tests/ regression and Publisher/Installer/Host checks are rerunning under sessions54579 and31239. No pass is claimed before completion. RUNNING_HANDLES.json is only a locator; continuation must poll live handles. All gates remain false.

---
# U1 UNKNOWN 补漏与版本同步 / U1 UNKNOWN follow-up and version reconciliation

固定源码 / Fixed source: 79262d79f870ecd30966184aa3b7d56349311429
日期 / Date: 2026-11-04

## 执行结果 / Results
中文：复核前轮032e219发现直接TimeoutError、连接重置和响应解析异常仍被标为普通错误，可能由后续周期重试。已去除重试循环，配置max_retries仅保留兼容；请求尝试后的普通异常一律provider_outcome_unknown，不泄露原始异常。继续复用DiscoveryService的持久UNKNOWN拒绝，不新增锁或Inventory。
English: Review of 032e219 found direct timeouts, resets and parsing failures still classified as ordinary errors. The retry loop is removed; max_retries remains configuration-compatible only. Exceptions after a request attempt become provider_outcome_unknown without exposing exception text. Existing persisted UNKNOWN admission is reused without adding locks or an Inventory.

中文：发现canonical runtime队列没有前轮进度字段，投影中U1主任务仍引用旧candidate_commit及独审通过状态。现同步两处当前源码、报告、下一动作和PENDING审核状态，旧交付保留为previous；未改任务租约或业务门禁，历史内容另存PREVIOUS_QUEUE_CURRENT_METADATA.json。QUEUE_SYNC.json记录读回一致性。
English: The canonical runtime queue lacked the previous progress fields, while its projected main task retained an old candidate and passed review status. Both now reference the current source, report, next action and pending review. Previous delivery metadata is preserved; leases and business gates are unchanged. QUEUE_SYNC.json records readback agreement.

## 验证与范围 / Validation and scope
中文：最终源码4项定向测试通过，0失败/错误，1.330秒；覆盖URLError、HTTPError、直接超时、连接重置、远端断连、非法JSON/UTF-8/结果结构、重建服务后的持久UNKNOWN拒绝以及无配置零调用。全部是离线fixture，不是正式Provider或真实费用证据。原始输出TARGETED_OUTPUT.txt。前一固定源码032e219与44b0ec9的完整tests/回归正在运行，不继承其结果至本SHA。
English: Four final-source focused tests passed with zero failures/errors in 1.330 seconds. Cases include URL/HTTP errors, direct timeouts, resets, disconnects, invalid JSON/UTF-8/shape, persisted UNKNOWN across service instances and no submission without configuration. These are offline fixtures, not Provider or billing acceptance. Raw output is TARGETED_OUTPUT.txt. Full tests/ regression for previous source 032e219 and baseline 44b0ec9 is running and cannot be inherited by this SHA.

## 正式合同核对 / Formal contract audit
中文：通过现有GitHub插件只读刷新Issue #2共34条评论，未发现正式Provider费用/状态查询/取消合同；未发布新消息或重复消费回执。当前源码的Google Text Search搜索接口不等于U1正式Provider合同。已向用户询问正式服务名称与现有协议位置，不要求密钥。官方Text Search REST文档列出搜索请求/结果，Cloud Billing标准导出另有费用、币种和用量字段；据此不能把内部cost_units=1或本地幂等键认作Provider权威费用或请求身份。
English: Read-only refresh of 34 Issue #2 comments through the existing GitHub connector found no formal cost/status/cancellation contract. No message or repeated receipt was posted. The current Google Text Search adapter is not a complete U1 Provider contract. The user was asked for the formal service and protocol location, without credentials. Official Text Search REST describes search requests/results, while Cloud Billing export defines separate usage, cost and currency fields. Internal counters and local idempotency keys cannot prove authoritative cost or Provider request identity.

来源 / Sources:
- https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places/searchText
- https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/standard-usage
- https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/2

## 未执行、风险和下一步 / Not executed, risks and next steps
中文：尚未覆盖发送后、UNKNOWN落盘前的崩溃窗口；未把legacy搜索路径升级为正式执行链。进程中断仍须原owner intent与既有ProcessBackend持久记录共同保护；不通过更改offline协议或门禁假装接通。正式Worker、可信签名、SAFE真实来源、权威请求/费用对账、完整包、独审和Windows验收未完成。下一步完成固定源码回归，基于确认的正式协议实现worker和费用接线。
English: The send-to-UNKNOWN-persistence crash window remains open on the legacy search path. This is not formal execution-chain completion. Original-owner intent and existing ProcessBackend persistence must protect interruption; offline protocol and gates are not changed to simulate integration. Formal worker, trusted signing, real SAFE provenance, authoritative request/cost reconciliation, complete packaging, independent review and Windows acceptance remain incomplete. Next: fixed-source regression, then worker and cost integration against the confirmed protocol.

中文：未执行真实Provider请求、收费操作、生产数据库/ACL/服务/Inventory操作、安装、派发、取消或SMTP。独审PENDING；本SHA全量NOT_RUN。保守UNKNOWN可能降低可用性，需要可信对账，不能自动解除。报告不含密钥、账号或客户数据；执行结果、限制和历史失败均保留。
English: No real Provider request, charge, production DB/ACL/service/Inventory action, install, dispatch, cancellation or SMTP occurred. Review PENDING; full regression NOT_RUN for this SHA. Conservative UNKNOWN reduces availability pending trusted reconciliation and cannot be automatically cleared. No credentials, account or customer data are included; results, limitations and prior failures are preserved.

DEVELOPMENT_COMPLETE=false; PACKAGE_COMPLETE=false; PROVIDER_ACCEPTED=false; WINDOWS_ACCEPTED=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; smtp_enabled=false.

---

## 干净源码对照复验 / Clean-source comparison
中文：固定基线20项通过（28.041秒）；固定候选23项通过（28.211秒），包含新增3项。使用各自Git固定源码的独立目录，未跳过静态扫描、未更改白名单，旧缺文件错误未复现。仅本组无新增失败；不是完整回归或独立审核。
English: Pinned baseline passed 20 tests in 28.041 seconds; candidate passed 23 in 28.211 seconds, including three new tests. Separate pinned Git trees were used, without skipping the static scanner or changing its allowlist. The old missing-file error did not reproduce. No new failure in this group only; not full regression or independent review.

# U1 三阶段连续开发核对 / U1 continuous-development reconciliation

中文：2026-11-04当前工程源码固定为032e2198d124fea2e40ace2f109574e9a92016a8，已含6c60dba Publisher修复。第一阶段完成一个范围明确的UNKNOWN传输修复，3项定向测试通过；正式Provider、权威费用、SAFE来源及崩溃窗口仍未完成。详见autonomy/evidence/u1_provider_transport_20261104/REPORT.md，所有历史证据保留。
English: Current engineering source is 032e2198d124fea2e40ace2f109574e9a92016a8, including the Publisher fix. Phase 1 adds a scoped UNKNOWN transport fix with three focused passing tests. Formal Provider, authoritative cost, SAFE provenance and the crash window remain incomplete. See autonomy/evidence/u1_provider_transport_20261104/REPORT.md; all historical evidence is retained.

中文：任务队列中的3fbaa5e包只保留为历史产物；当前已知owner服务工程包基线59acb7a，二者都不是当前完整发布包。当前候选包NOT_BUILT，CPython和完整依赖未集成。独审PENDING；最终全量NOT_RUN。Windows和费用请求均无新授权。
English: Queue references to the 3fbaa5e package are historical artifacts. The known owner-service engineering archive baseline is 59acb7a; neither is a complete current release. Current package NOT_BUILT, with CPython and full dependencies outstanding. Review PENDING; final full regression NOT_RUN. No new Windows-install or chargeable-request authority.

DEVELOPMENT_COMPLETE=false; PACKAGE_COMPLETE=false; PROVIDER_ACCEPTED=false; WINDOWS_ACCEPTED=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; smtp_enabled=false.

---

# U1 发布器原owner配置接线 / Publisher original-owner plan wiring

时间 / Time: 2026-11-04T00:14:46.188985+00:00
固定源码 / Fixed source: 6c60dba1f70f998ad933510750aba865597c8c12

修复正式发布器拒绝 original_owner_db 的实际阻断项，使其与安装器及服务bootstrap已经支持的计划一致。event_runtime 与 original_owner_db 继续互斥。原数据库以Windows只读访问句柄固定文件身份，共享读写但拒绝删除；不读取、哈希、复制、迁移或修改数据库。保持祖先目录固定、普通文件与单硬链接校验，并在执行前重新验证。安装与派发门禁不变。
Fixed a real publisher admission blocker: original_owner_db plans now reach the existing installer and bootstrap path. Owner sources remain mutually exclusive. A Windows read-access handle pins database identity while sharing reads/writes and denying deletion. No database bytes are read, hashed, copied, migrated or changed. Ancestor identity, ordinary-file and single-link checks remain enforced and are revalidated before execution. Installation and dispatch gates remain closed.

定向验证 / Targeted validation:
- python -B -m unittest test_install_command test_install_inputs test_u1_provision test_u1_host_runtime -q: 17 PASS, 9.726s (before final added link/missing-path test).
- python -B -m unittest test_install_inputs test_install_command -q: 13 PASS, 5.686s (final source).
- python -B -m unittest test_install_contract test_install_journal test_install_process test_install_verifier test_publisher_install_admission test_publisher_install_maintenance -q: 54 PASS, 75.812s.

真实临时SQLite连接在固定期间提交写入成功；unlink/rename拒绝，释放固定且关闭数据库后rename成功；双owner配置、硬链接、缺失路径及冲突固定被拒绝，缺失数据库不创建。
An actual temporary SQLite connection committed writes while pinned; unlink/rename failed until pin release and database close. Dual-owner configuration, hardlinks, absent paths and conflicting pins were rejected without creating an absent database.

故障记录 / Fault record: initial attribute-only handle did not reliably exclude deletion; changed to read-access handle and reran real Windows checks successfully. 初版属性句柄未能拒绝删除，已改为只读访问句柄并通过真实Windows复验。

独审 / Independent review: PENDING. 全量 / Full regression: NOT_RUN_FOR_THIS_SHA. 不继承旧833及独审结论 / No inherited 833-test or review acceptance.
本次修改正式发布器源码，不重建未包含publisher_channel的既有宿主工程包；旧包固定源码59acb7a1c422841b71f82019cd52a5e66daa6d7e，安装SHA b3b79f6e526dc9055d4b8916c39931a01853e3374715b103be6508de89c4d5f8，回滚工具SHA 6521f8e0c2c2303016ef2d95ea012316f2f18d2ed1e664d5c4f5864e083ee116。它们不代表本次发布器版本已打包验收。
This change is publisher source only; the existing host archives do not contain publisher_channel and were not rebuilt. The above existing archive hashes remain scoped to their prior source and do not certify this publisher revision.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; smtp_enabled=false.

未运行生产采集、服务安装、启用、生产DB操作；唯一Inventory不变。未配置平台硬45分钟超时，平台任务无该字段。
No production collection, service install/enablement or production DB operations were performed; the sole Inventory is unchanged. No platform hard 45-minute timeout was configured because the task has no such field.

GitHub指令评论本轮刷新失败（gh未安装，网页读取cache miss）；按用户当前明确冻结范围继续离线修复，未推断新增权限。
The instruction comment could not be refreshed (gh unavailable; web cache miss). Offline work stayed within the user's explicit current frozen scope without inferring new authority.

下一动作 / Next action: 验证固定服务bootstrap生命周期并完成发布器、安装器及宿主链独审；正式Provider及实测费用仍待接通，生产安装未授权。
Validate the fixed service bootstrap lifecycle and obtain independent review of the publisher/installer/host chain; formal Provider execution and measured costs remain outstanding. No production installation is authorized.

---

# U1 原owner服务工程包 / Original-owner service engineering package

固定源码 / Fixed source: 59acb7a1c422841b71f82019cd52a5e66daa6d7e | 2026-11-03T21:10:57.755730+00:00

重建真实AMD64禁用工程包，纳入原数据库只读入口、runtime plan到bootstrap参数传递。73份manifest文件逐SHA256核验，安装及回滚zip逐字节对照解包树通过，PE machine AMD64。包内源码经隔离Python路径加载，15项HTTP/子进程/预算/配置测试通过，11.722s；外层12.185s。结果见VALIDATION.json及PACKAGED_TEST_OUTPUT.txt。
Rebuilt the actual AMD64 disabled engineering package with original-DB read-only bootstrap and runtime-plan argument propagation. All 73 manifest files passed SHA256 checks, both archives matched their staging bytes, and the PE machine is AMD64. Isolated Python loading of packaged source passed 15 HTTP/process/budget/configuration tests in 11.722s (12.185s outer wall time). See validation and output files.

安装包 / Install SHA256: b3b79f6e526dc9055d4b8916c39931a01853e3374715b103be6508de89c4d5f8
回滚工具 / Rollback SHA256: 6521f8e0c2c2303016ef2d95ea012316f2f18d2ed1e664d5c4f5864e083ee116
Manifest SHA256: bd16b71edde13711eac7ecf78a304f3ed9db996d0e4012e76e9d74b927c7c0b0

本次交付为工程包，未捆绑CPython或完整业务依赖。未运行真实服务启动、正式Provider或实际费用验收。独审PENDING，全量回归NOT_RUN_FOR_THIS_SHA；不继承旧审核及833项结果。
This engineering archive does not bundle CPython or complete business dependencies. Real service startup, formal Provider and measured-cost acceptance were not run. Independent review PENDING and full regression NOT_RUN_FOR_THIS_SHA; previous reviews and 833-test results are not inherited.

下一步 / Next: 完成此固定包的服务bootstrap生命周期验证与独审，再接通正式Provider和实测费用；生产安装未授权。
Complete pinned service-bootstrap lifecycle validation and independent review for this fixed package, then integrate formal Provider execution and measured costs. No production installation is authorized.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.

无生产数据库、ACL、服务或Inventory操作；本地测试均为临时fixture，现有WorkBuddy证据复用。
No production database, ACL, service or Inventory operation occurred. Local tests used temporary fixtures and existing WorkBuddy evidence was reused.

---
# U1 服务原所有者配置 / Service original-owner configuration

固定源码 / Fixed source: 229c48c2d44cf18a12e9c6f9049d40847349e9ec | 2026-11-03T18:10:57.037585+00:00

实际接线：安装准备器从独立hash绑定的runtime plan提取original_owner_db，生成runtime.json并纳入supervisor的runtime_config_sha256；固定bootstrap将该引用传至宿主--original-owner-db。原owner与离线event_runtime互斥。准备器验证绝对规范路径、存在文件及reparse祖先；不复制、hash锁定或写入可变原数据库。
Implementation: installation preparation propagates original_owner_db from the separately hash-bound runtime plan into runtime.json and the supervisor runtime_config_sha256. The pinned bootstrap forwards it to the host --original-owner-db argument. Original-owner and offline event_runtime references are mutually exclusive. Preparation checks canonical absolute existing-file paths and reparse ancestors without copying, hash-locking or writing mutable database bytes.

验证 / Validation: python -B -m unittest test_u1_provision test_u1_host_runtime -q: 5 PASS, 5.188s. Actual PowerShell config generation verifies propagation, source bytes preserved and dual-authority rejection. Complete service bootstrap execution was not tested this round.

本SHA独审PENDING；全量NOT_RUN；安装包未重建，旧审核/包不继承。非完整发布验收。
Independent review PENDING for this SHA; full regression NOT_RUN; packages not rebuilt and previous reviews/archives not inherited. This is not complete release acceptance.

下一步 / Next: 通过完整固定bootstrap核验生成的服务配置，重建候选并独审；继续完成正式Provider及实测费用接线。
Validate the generated service configuration through the complete pinned bootstrap, rebuild the fixed candidate and obtain independent review; formal Provider and measured-cost integration remain required.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
未修改生产数据库、ACL或服务，未触发Inventory；复用WorkBuddy既有证据。
No production database, ACL or service changed; no Inventory triggered. Existing WorkBuddy evidence reused.

---
# U1 原所有者启动接线 / Original-owner bootstrap wiring

固定源码 / Fixed source: 748ccb0196786884611cb98fab97888e6a12d231 | 2026-11-03T15:10:42.508166+00:00

启动入口新增互斥--original-owner-db与--event-runtime，将原数据库只读连接接到既有open_host原owner观察器；不再仅能通过测试内注入连接工厂。绝对路径、普通文件、单硬链接、启动时文件身份固定及连接前后复验；mode=ro和query_only禁止建库、迁移及写入。
The host CLI now accepts mutually exclusive --original-owner-db and --event-runtime, routing a read-only original database connection to the existing owner observer instead of requiring test-only connection injection. It requires an absolute ordinary single-link file, captures file identity and checks it around connections. mode=ro and query_only prevent database creation, migration and writes.

路径身份检查依赖受信配置和受保护目录，不声明对敌对目录的完整TOCTOU防护。未放开生产执行或服务安装；固定服务runtime plan及supervisor参数仍待接线，正式Provider及实测费用仍未完成。
Path checks depend on trusted configuration and protected directories; they do not establish complete TOCTOU protection against hostile directory mutation. Production execution and service installation remain disabled. Pinned runtime-plan and supervisor arguments, formal Provider and measured costs remain incomplete.

验证 / Validation: python -B -m unittest test_u1_host_runtime test_original_process_backend test_inventory_event_bridge -q: 13 PASS, 7.775s. Actual SQLite missing-file/no-creation, write rejection and file-replacement checks plus existing HTTP/child/settlement integration.

本SHA独审PENDING，全量回归NOT_RUN，安装包未重建；不继承3fbaa5e审核或旧包。
Independent review PENDING for this SHA, full regression NOT_RUN, packages not rebuilt. The 3fbaa5e review and old packages are not inherited.

下一步 / Next: 把获准原owner数据库引用接入固定服务runtime plan与supervisor参数；完成正式Provider与实测费用合同后重建并审核完整发布版。
Wire the approved original-owner DB reference into the pinned service runtime plan and supervisor arguments; complete formal Provider and measured-cost contracts before rebuilding and reviewing the complete release.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336.

本轮未操作生产数据库、服务、ACL或Inventory；复用既有WorkBuddy证据，不重复消费回执。平台硬超时未配置，不声明已强制45分钟。
No production database, service, ACL or Inventory operation occurred. Existing WorkBuddy evidence was reused without duplicate receipts. No platform hard timeout was configured or claimed.

---
# U1 原执行链交付 / Original execution-chain delivery

固定源码 / Fixed source: `3fbaa5ec42cb0655ecd1c811ccd8d02b1fc837bb`

中文：已将原stage接入持有既有Inventory权利的事件消费者，路径为原stage→HTTP→原owner适配器→受控子进程→预算结算→原job终态与释放同事务。错误owner、日期、原DB身份及非running任务均在调用backend前拒绝。子进程运行期间持续检查原owner，丢权时终止进程树并保留UNKNOWN。未知收据或丢ACK不重放、不回落旧业务入口。

English: The original stage now consumes events under its existing Inventory authority: original stage → HTTP → original-owner adapter → controlled child → budget settlement → atomic original-job finalization and release. Incorrect owner, date, DB identity or non-running jobs are rejected before backend invocation. Runtime owner loss stops the process tree and preserves UNKNOWN. Unknown receipts and lost ACKs authorize neither replay nor fallback to the legacy body.

中文：独审发现的先提交job成功、后发现释放失败问题已修复。写入失败及释放零行均回滚整个事务；原job保持running、原锁保留、backend只执行一次。实际进程树控制已测试；业务worker、签名及SAFE库存计数仍为隔离fixture，正式Provider和真实费用合同尚未接通。

English: Independent review found premature job success before release verification. Both job-write failure and a zero-row release now roll back the complete transaction, preserving the running job and original lock with only one backend invocation. Real process-tree control was tested; business workers, signatures and SAFE counts remain isolated fixtures. Formal Provider execution and measured-cost contracts remain incomplete.

组合测试 / Combined tests: 271 tests; passed=True; failures=0; errors=0; skips=0. 每项结果见validation；新候选重新运行。 / Per-test output is under validation; this candidate was rerun.

独立审核 / Independent review: OFFLINE_SCOPED_REVIEW_PASSED; {'count': 76, 'duration_seconds': 30.374, 'duration_basis': 'sum of two independent unittest runner durations, not elapsed wall time', 'failures': 0, 'errors': 0, 'runs': [{'command': 'python -m unittest test_original_stage_event test_original_inventory_owner test_inventory_maintenance tests.test_inventory_stage_trace tests.test_phase4a8r_continuous_discovery -q', 'count': 60, 'duration_seconds': 18.916}, {'command': 'python -m unittest test_original_process_backend test_process_backend test_inventory_event_bridge -q', 'count': 16, 'duration_seconds': 11.458}]}. 详见review-3fbaa5e，旧候选失败报告保留。 / See review-3fbaa5e; previous failed-candidate reports are retained.

可比全量 / Comparable full regression: baseline `68788653c848659c63f85021075fedee4aca5b13` / candidate `3fbaa5ec42cb0655ecd1c811ccd8d02b1fc837bb`; tests 833/833; failures 37/37; errors 17/17; NO_NEW_REGRESSION=True; ALL_GREEN=False. 不宣称全绿。 / No all-green claim.

真实AMD64工程包 / Actual AMD64 engineering package: 73 payload files.
- install.zip SHA256: `16410c14c094ee3452abe0506257236b61de2e1769447e282503e7fcaa17ccb7`
- rollback-tools.zip SHA256: `0614261b9c1ddaa2dee43be28c4390db9d1b32f11bc6a26b0ea058751ad4395b`
- host manifest SHA256: `85a59889bdeaa4097e92393525f3ad87ceda70090b28d2246cb20a430d397bec`
- 17-file companion SHA256: `c4adf386d86b8a70b8833c51e51148cee1ea74ffee0858e08b41777dddb6bab7`
- companion manifest SHA256: `c7e0b3aa943cd06ae1948745d14a03c58375ff37f4cb9d12c879585e764b59cb`

中文：每文件摘要见ARTIFACT_MANIFEST.json；独立包审核见review-3fbaa5e。配套包只含固定路径源码，不是更新器，不扩大旧Publisher白名单；expected_before来自固定Git基线，不是现场证据。未捆绑外部CPython及完整业务依赖，不是完整可安装发布版。

English: ARTIFACT_MANIFEST.json records per-file digests; review-3fbaa5e contains independent package checks. The companion includes fixed source paths only; it is not an updater and does not expand the old Publisher allowlist. expected_before comes from a pinned Git baseline, not site evidence. External CPython and complete business dependencies are not bundled; this is not a complete installable release.

待完成及真实安装门禁 / Remaining engineering and installation gates:
完成正式Provider执行、费用实测和受信运行配置，随后对完整候选审核；经授权后由WorkBuddy进行隔离Windows首次安装、升级、进程退出恢复、回滚中断恢复及Disabled/Stopped验收。不得用测试worker或SAFE替身代替业务验收。

Complete formal Provider execution, measured costs and trusted runtime configuration, then review the complete candidate. After authorization, WorkBuddy verifies isolated Windows first installation, upgrade, process-exit recovery, interrupted rollback and Disabled/Stopped state. Test workers and SAFE fixtures are not business acceptance.

中文：本轮未安装/启动服务、未修改生产ACL/数据库/账本/Inventory。现有安装器事务测试不等同于WorkBuddy真实Windows无人值守成功验收。保留已接受的非对称ACL裁决。

WorkBuddy后续具体核验（完整候选审完且另行授权后） / Specific later WorkBuddy checks (after complete-candidate review and separate authorization):
1. 隔离Windows核对固定commit、安装包/manifest/运行时身份；保留安装前文件和ACL快照。 / In isolated Windows, verify commit, archive/manifest/runtime identities and retain pre-install file/ACL snapshots.
2. 首装核对两个根目录的非对称ACL、自有文件收据以及服务Disabled/Stopped；升级覆盖新增、替换、删除。 / Check asymmetric root ACLs, owned-file receipts and Disabled/Stopped registration; upgrade must cover creation, replacement and deletion.
3. 在持久intent、实际写入、回执与回滚边界注入退出，再重启安装进程；ABSENT须恢复，未知状态必须STOP_AND_PRESERVE。 / Terminate at durable-intent, mutation, receipt and rollback boundaries, then restart the installer; restore ABSENT and preserve unknown states.
4. 核实维护权取得、持续持有、最终读回和精确释放；原Inventory占用或UNKNOWN时不得取得安装权。 / Verify maintenance acquisition, continuous holding, final readback and exact release; a held/UNKNOWN original Inventory must deny installation authority.
5. 不触发生产Inventory；无人值守业务验收必须待正式Provider链与独立授权完成，单独记录实际请求、费用、取消和结算证据。 / Do not trigger production Inventory; unattended business acceptance awaits the formal Provider chain and authorization, with separate actual request, cost, cancellation and settlement evidence.

English: No service was installed/started and no production ACL, DB, ledger or Inventory was modified. Installer transaction tests do not establish WorkBuddy's real Windows unattended acceptance. The accepted asymmetric ACL ruling remains unchanged.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
