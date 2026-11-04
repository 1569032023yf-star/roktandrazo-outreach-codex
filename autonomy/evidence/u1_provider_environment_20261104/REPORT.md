# U1 批准配置读取与实际禁用包 / Approved configuration loading and actual disabled package

固定源码 / Fixed source: ec45401ad7b0ca016fe6e1b15f58462e929623ff
基线 / Baseline: dedb987bffbb1462a8a7215833f330cd6d4ddea7

中文：本轮交付实际源码：env_loader优先读取显式绝对路径及SHA256绑定的外部Provider配置，代码根目录不再必须放置.env。复用Windows原生句柄固定文件及祖先身份，严格schema及白名单，只允许Google Places/browser_maps配置，拒绝重复JSON字段、硬链接、Mock/SerpAPI及安全开关注入。全部解析成功后才替换Provider环境，清除继承别名；开发副本拒绝外部凭据。未指定批准配置时保留原有.env路径。审批摘要须来自批准运行计划；本轮仅接入消费端，尚未把配置传播接入固定宿主及业务Worker，不把环境变量作为派发授权。
English: Actual source now lets env_loader read an explicit absolute external Provider configuration pinned by SHA256, removing the requirement to place .env in the code root. Existing Windows native input handles pin file and ancestor identities. Strict schema/allowlist admits Google Places/browser_maps configuration and rejects duplicate JSON keys, hard links, Mock/SerpAPI and security-switch injection. Provider variables replace inherited values only after full parsing; inherited aliases are cleared and development copies reject external credentials. Legacy .env behavior remains when no pinned configuration is supplied. The expected digest must originate in an approved runtime plan. This change implements the consumer only, not propagation through the pinned host/business Worker or dispatch authorization.

中文：14项配置/隔离测试及1项固定清单测试分进程通过；未提交源码BUILD_INPUT_NOT_PINNED及15项同进程组合的开发子进程护栏ERROR见INITIAL_FAILURES.md，均未隐瞒或绕过。干净detached基线和候选的tests/分别848项，37FAIL/17ERROR的ID一致，无新增；不是全绿。主树848项为37FAIL/19ERROR，多出的两项FileNotFoundError指向历史解压证据路径；原结果及后续干净比较均保留，不删除他人历史工作。
English:14 configuration/isolation checks and1 pinned-manifest check pass in separate processes. INITIAL_FAILURES.md retains the initial uncommitted-source rejection and the combined15-test development subprocess-guard error; neither was bypassed. Clean detached baseline and candidate tests/ suites each run848 tests with identical37 failure and17 error IDs, no additions; this is not a fully passing suite. The main-tree run has37 failures/19 errors, with two extra FileNotFoundErrors in historical extracted evidence paths. Original and clean comparison results are retained without deleting historical work.

中文：实际AMD64禁用包重建，5056个清单文件，包含新env_loader、Provider配置模块、CPython3.13.12和固定12个wheel。安装包和回滚归档哈希见BUILD.json及DELIVERY_MANIFEST.json。回滚包4964组件逐文件对应通过；它不是现场数据库/状态备份，也未执行实际回滚。最终解压CPython的独立配置探针通过，两个模块来源属于包内，未携带.env；仅fixture，禁止网络/数据库/邮件副作用，不是正式Provider验收。完整包验证最终结果以EXTRACTED_REPORT.json为准。
English: The actual AMD64 disabled package is rebuilt with5056 manifest files, including new env_loader, Provider configuration module, CPython3.13.12 and12 pinned wheels. BUILD.json and DELIVERY_MANIFEST.json record installation/rollback archive hashes.4964 rollback components match byte-for-byte; the archive is not a site database/state backup and no actual rollback was executed. The extracted CPython configuration probe passes with two packaged module origins and no .env in the code root, using fixtures and denying network/database/mail effects. It is not formal Provider acceptance. EXTRACTED_REPORT.json is authoritative for the complete package verification outcome.

中文：独审PENDING；不以自审或包内探针替代独审/Windows现场验收。正式费用、取消/终态回执仍CONTRACT_MISSING，不要求用户设计内部命名。下一动作唯一：将批准Provider配置路径和摘要通过固定宿主运行计划传播至原业务Worker，同时保持原Inventory锁及全部安全门禁关闭；随后补齐原入口包闭包与独审。不得为了接线放开offline_only或模拟费用。
English: Independent review remains PENDING. Implementation checks or packaged probes do not replace independent review or Windows acceptance. Authoritative charges/cancellation/terminal receipts remain CONTRACT_MISSING; internal naming needs no user decision. Single next action: propagate approved Provider configuration path and digest through the pinned host runtime plan to the original business Worker while retaining the original Inventory lock and all closed gates; then complete original-entry package closure and independent review. Do not relax offline_only or simulate charges to claim integration.

DEVELOPMENT_COMPLETE=false
PACKAGE_COMPLETE=false
PROVIDER_ACCEPTED=false
WINDOWS_ACCEPTED=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_install=false
allow_dispatch=false
allow_cancel_dispatch=false
smtp_enabled=false

中文：本轮最多两条重型工作线；没有平台整轮硬超时字段，不宣称已配置。回归及解压验证子进程各设600秒限时；45分钟内保存恢复点。不触发Inventory、生产采集、服务安装、ACL修改、生产DB或邮件。
English: At most two heavy workstreams were active. No platform-wide hard timeout field is available or claimed; regression and extracted-verification child runs have600-second limits. Recovery state is saved within the45-minute round. No Inventory trigger, production collection, service installation, ACL change, production DB or email action occurred.

中文：EXTRACTED_REPORT.json最终VERIFIED，5056文件，四项包内检查及最后逐文件完整性复核通过；验证子进程正常退出0，未超时。此结论仅限离线包完整性/入口来源/fixture认证。
English: EXTRACTED_REPORT.json finishes VERIFIED with5056 files, four packaged checks and final file-by-file integrity revalidation; child exits0 without timeout. This conclusion is scoped to offline package integrity, entry origins and fixture authentication.
