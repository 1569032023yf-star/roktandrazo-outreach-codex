# U1 固定Provider Worker入口 / Pinned Provider Worker entrypoint

固定源码 / Fixed source: 9d5ecb6b8062f916ac7869957eb6589665ce9113
时间 / Time: 2026-11-04T19:24:52.977716+00:00

中文：新增包内 provider_worker.py 入口，使用 -I -B 可从任意当前目录加载固定树中的真实Google Places/browser_maps适配器和批准配置；配置上下文及祖先句柄持续持有。ProcessBackend.for_provider_worker 将后端、固定Worker路径和批准的配置/源码摘要接线，不自算可信摘要。--preflight仅输出无凭据能力信息，不请求服务或创建缓存。默认执行路径返回CONTRACT_MISSING和缺失字段，exit78，不发送外部请求、不签slot/budget回执。后端据此保留持久UNKNOWN且不重放；不是正式业务执行完成。
English: The packaged provider_worker.py runs with -I -B from any working directory and constructs real Google Places/browser_maps adapters from approved pinned configuration. Configuration and ancestor handles remain held. ProcessBackend.for_provider_worker wires the backend to the fixed Worker path and caller-approved configuration/source digests, without calculating trusted digests itself. --preflight exposes credential-free capabilities only, without service requests or cache creation. Default execution returns CONTRACT_MISSING and missing fields with exit78, starts no external request and signs no slot/budget receipts. The backend preserves durable UNKNOWN and rejects replay. This does not complete formal business execution.

中文：20项定向通过，包含真实子进程入口、篡改配置摘要拒绝且不泄露配置、后端真实Worker拒绝后UNKNOWN持久化与禁止重放及原后端/配置组合。初次引用测试夹具类名称错误1ERROR，修正后通过；原始结果保留。隔离全量848项，37FAIL/17ERROR；新增失败ID[]、新增错误ID[]，详见固定240f614实测基线对比；不是全绿。
English: 20 targeted tests pass, including a real subprocess entrypoint, tampered-config rejection without disclosure, durable UNKNOWN/no replay after real Worker refusal, and existing backend/configuration combinations. An initial fixture-class import error was corrected; its original result remains. Clean full regression runs 848 tests with 37 failures/17 errors; added failure IDs [] and added error IDs []. The measured fixed240f614 comparison is retained; this is not all green.

中文：新包5057文件，AMD64禁用态，含固定CPython及12依赖wheel。实际解压核验VERIFIED；包内实际Worker探针PASSED；回滚组件对应VERIFIED，不等于实际备份或回滚。未安装服务、未触发Inventory、未写生产数据库或发信。
English: The new 5057-file AMD64 disabled archive bundles pinned CPython and12 dependency wheels. Actual extraction verification VERIFIED; packaged real Worker probe PASSED; rollback component parity VERIFIED, which is not a site backup or actual rollback. No service installation, Inventory trigger, production database writes or email occurred.

Install SHA256: 5965f7d3a08dd732a0cfca75a67e47eda949457fe32920d0e5e392cae2881383
Rollback tools SHA256: 62b31347b14cce96e5a6e17b6f3dc5f8b9ba8f1e0af241998c11c078abac7dfc
Manifest SHA256: 0814a7bd48fc4e65184b2bc7a62eeb031093cdcf2087d744747c4a119d289f02

中文：缺少权威operation/run/claim绑定、终态、幂等、取消费用、账单账户/project/SKU、使用量周期/数量/单位、金额/币种/credits和账单证据引用；browser_maps另缺来源授权和请求回执。未用缓存计数或模拟费用替代。独审PENDING，原Owner到业务请求/权威回执闭环、真实Windows安装启动注销/Session0/跨登录验收未完成。所有最终状态false，BUSINESS_GROWTH=UNKNOWN，安装/派发/取消/SMTP均false。整轮无平台硬超时字段；本轮实际02:51:29启动，03:36:29截止，子进程单独硬限，最多两条重型工作线。
English: Missing contracts cover operation/run/claim binding, terminal status, idempotency, cancellation fees, billing account/project/SKU, usage period/quantity/unit, amount/currency/credits and billing evidence references; browser_maps additionally lacks source authorization and request receipts. Cache counters or simulated costs do not substitute. Independent review PENDING. Original-owner-to-business-request/authoritative-receipt closure and real Windows install/start/logoff/Session0/across-login acceptance remain incomplete. All final states false, BUSINESS_GROWTH UNKNOWN, install/dispatch/cancel/SMTP false. No platform whole-turn hard-timeout field; actual cycle02:51:29 to03:36:29 with individually bounded subprocesses and at most two heavy workstreams.

下一动作 / Next action: 接入原Owner约束的Worker操作解析及业务请求映射；权威费用、终态和取消合同缺失继续拒绝外部请求，不签伪造回执。
Wire original-owner-bound operation parsing and business request mapping; keep external requests blocked without authoritative cost, terminal and cancellation contracts and never fabricate receipts.

自检 / Self-check: 双语、数量、风险、未执行项、下一步齐备；无凭据、未冒称完成。 Bilingual, counts, risks, omissions and next action present; no credentials or false completion claims.
