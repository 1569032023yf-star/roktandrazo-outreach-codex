# U1 Provider配置接线与真实安装包 / Provider configuration wiring and actual package

固定源码 / Fixed source: 594cd0a513af461baac867a00e1f431339de3d7d
时间 / Time: 2026-11-04T13:29:22.362233+00:00

中文：新增固定配置上下文到现有Google Places/browser_maps真实适配器的构造入口，不修改进程环境，不继承未批准的凭据、位置、direct模式或JSON输入。配置文件和祖先句柄持有至适配器上下文退出。修复browser_maps实例目录被全局CACHE_DIR覆盖的读写串用；构造不再创建缓存目录，仅实际保存结果时创建。复用原请求及认证实现，SerpAPI仍禁用。这不是业务Worker入口闭环或真实Provider验收。
English: A pinned configuration context now constructs existing real Google Places/browser_maps adapters without mutating process environment or inheriting unapproved credentials, locations, direct mode or JSON input. Configuration/ancestor handles remain pinned for the adapter context lifetime. Browser Maps reads/writes use the instance cache directory instead of the module-global directory; construction no longer creates a cache directory. Existing request/authentication implementations are reused; SerpAPI stays disabled. This does not complete the business Worker entrypoint or accept a live Provider.

中文：27项定向组合通过。首次27项中1个测试夹具缺少必填字段，修正夹具后通过，初始结果保留。新固定源码隔离全量848项，37FAIL/17ERROR与固定ec45401实测基线ID完全一致，新增失败/错误0；不是全绿。新根目录定向测试另行运行，不计入848项。基线与候选摘要和实际原始输出均保留。
English:27 targeted combination tests pass. The initial27-test run had one fixture missing required fields; the fixture was corrected and the initial result retained. A clean fixed-source full run executes848 tests with the same37 failure/17 error IDs as the measured ec45401 baseline, with zero added IDs; this is not an all-green suite. New root-level targeted tests run separately and are not counted in848. Digests and actual raw output are retained.

中文：已构建新5056文件AMD64禁用安装包，包含固定CPython和12个依赖wheel；包内真实CPython适配器探针通过，无网络请求、未安装服务。实际归档解压核验结果为VERIFIED，完成探针数4；只有VERIFIED才代表该离线核验通过。回滚归档4960个host组件逐文件对应，无差异；不是现场备份或实际回滚。构建先误用脚本路径入口，探针先误用运行时路径，均在启动前失败后修正，恢复记录保留。
English: A new5056-file AMD64 disabled install archive bundles pinned CPython and12 dependency wheels. The real packaged-CPython adapter probe passes without network requests or service installation. Actual extracted-archive verification outcome isVERIFIED, with4 completed probes; only VERIFIED establishes that offline verification. All4960 host components in the rollback archive match byte-for-byte; this is neither a site backup nor actual rollback. Initial script-entry and runtime-path invocation errors failed before launch and were corrected; recovery records are retained.

安装包 / Install archive: C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-adapter-594cd0a\install.zip
SHA256: 38497049c86b6bb2c76f474d45a98d22f90a938285d7420242b6559eaa0c8aba
回滚工具 / Rollback tools SHA256: aa6d36e3a390004c421c92e659767e02656ad770dfc20b771e21a44606f96f18
Manifest SHA256: 4abd7f23e3d1219ace575a9e6a17bb61ecda8b94443ecef151ce36d42e0a42fc

中文：独审PENDING；实际Worker接线、权威费用/终态/取消回执、真实Windows安装/启动/注销/Session0及7877/8791跨登录验收未完成。所有最终状态false，BUSINESS_GROWTH=UNKNOWN；allow_install/allow_dispatch/allow_cancel_dispatch/SMTP=false。没有改生产数据、触发Inventory或新增调度器。整轮无硬超时字段，不宣称强制45分钟；重型子进程有独立硬时限。
English: Independent review PENDING. Actual Worker wiring, authoritative cost/terminal/cancellation receipts, real Windows install/start/logoff/Session0 and7877/8791 across-login acceptance remain incomplete. All final states false, BUSINESS_GROWTH UNKNOWN and all four gates false. No production data changes, Inventory trigger or additional scheduler. The platform has no whole-turn hard-timeout field; a forced45-minute limit is not claimed. Heavy subprocesses have separate hard timeouts.

下一动作 / Next action:
将批准配置适配器上下文接入原Owner控制的实际业务Worker入口，继续保持费用/终态合同缺失时拒绝正式结算及UNKNOWN不重放。
Consume the approved-adapter context in the original owner-controlled business Worker entrypoint; reject formal settlement without authoritative cost/terminal contracts and never replay UNKNOWN.
