# U1 执行文件固定修复 / Executable pinning fix

固定源码 / Fixed source: 240f614fd694d48eb19edcfd8f8d3e187722875d
时间 / Time: 2026-11-04T16:28:35.547978+00:00

中文：ProcessBackend 在写执行意图前固定 CPython 可执行文件和 Worker 源文件以及祖先路径句柄，持续持有到子进程清理和结果持久化结束，并在记录输出前重新核验。关闭构造后至启动前替换文件的竞态。复用安装器原生文件固定实现；不扩大为整个 DLL 或导入依赖闭包固定。未完成实际业务 Worker 接线。
English: ProcessBackend pins the CPython executable, Worker source and ancestor handles before execution intent, retains them through child cleanup/result persistence, and revalidates before recording output. This closes the file-replacement window after construction and before launch. Existing native installer pins are reused; this does not pin the complete DLL/import closure or complete business Worker wiring.

中文：22项定向通过，包含 Windows 句柄阻止写入/改名、意图前拒绝替换及原超时/UNKNOWN恢复。Bridge与Owner独立进程分别7项、12项通过。Stage和Bridge同进程组合18项有6ERROR，均为既有开发网络护栏拒绝；原始失败保留，未解除护栏，也不声明组合通过。初次测试类缩进错误已修正，首次失败记录保留。
English: 22 targeted tests pass, including Windows handle write/rename denial, pre-intent replacement rejection and existing timeout/UNKNOWN recovery. Separate Bridge and Owner processes pass 7 and 12 tests. The combined Stage/Bridge process has 6 errors in 18 tests, all rejected by the existing development transport guard. Raw failures are retained; the guard was not removed and this combination is not claimed passing. An initial test-class indentation error was corrected and its failure retained.

中文：固定候选隔离全量848项，37FAIL/17ERROR与实测594cd0a基线ID一致，无新增或消除ID；不是全绿。根目录定向不并入848。新包离线解压核验结果：VERIFIED。5056文件AMD64包，含固定CPython和12个依赖wheel；4960个回滚host组件对应。构建和核验详情见同目录 BUILD.json、EXTRACTED_REPORT.json；只有 VERIFIED 才表示该离线核验通过。回滚组件对应不代表现场回滚。
English: The clean fixed candidate runs 848 tests with the same 37 failure and 17 error IDs as measured baseline 594cd0a; no IDs are added or resolved. This is not all green. Root-level targeted tests are separate from 848. New archive extraction verification: VERIFIED. The 5056-file AMD64 archive bundles pinned CPython and 12 dependency wheels; 4960 rollback host components match. BUILD.json and EXTRACTED_REPORT.json record details; only VERIFIED establishes offline verification. Component parity does not establish a site rollback.

中文：独立审核 PENDING，真实 Worker、权威费用/终态/取消合同、Windows安装/启动/注销/Session0及跨登录验收仍未完成。未安装、未触发Inventory、未写生产DB、未发邮件。所有最终状态及门禁false，BUSINESS_GROWTH=UNKNOWN。整轮无平台硬超时字段；子进程有独立时限。
English: Independent review PENDING. Actual Worker wiring, authoritative cost/terminal/cancellation contracts, Windows install/start/logoff/Session0 and across-login acceptance remain incomplete. No installation, Inventory trigger, production database writes or email. All final states and gates remain false; BUSINESS_GROWTH UNKNOWN. No platform whole-turn hard-timeout field exists; subprocesses have individual limits.

安装包 / Install archive SHA256: fde8581e29e4395820a1b5ba8c7d0ac3f3c8a1ac44bd45b5aa5f176dbf6a4020
回滚包 / Rollback tools SHA256: 3783b939a76fda00e21b71586b62dd5f1b87feeed4ee605b82a5e5cc9bfcfd31
Manifest SHA256: 9e681a1f7d761526ca593918c1405725d1cfc42d80f431876a908a6ef6dc799d

下一动作 / Next action: 将批准配置适配器上下文接入原Owner控制的业务Worker入口，费用和终态合同缺失时继续拒绝正式结算。
Wire the approved adapter context into the original owner-controlled business Worker; reject formal settlement without authoritative cost and terminal contracts.

自检 / Self-check: 双语、数量及失败已明确；未执行项和风险已记录；无凭据。 Bilingual, counts and failures explicit; omissions/risks recorded; no credentials.
