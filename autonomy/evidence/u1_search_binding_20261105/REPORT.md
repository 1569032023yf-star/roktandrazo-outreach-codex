# U1 Provider签名业务请求接线 / Signed Provider business request wiring

固定源码 / Fixed source: 21568c8267d7d20b3127eab8d3f5c866202868fd
时间 / Time: 2026-11-05T01:26:56.171104+00:00

中文：新增既有search_places参数校验，将签名admission内provider_request原样传入ProcessBackend操作并纳入幂等摘要；仅支持Google Places/browser_maps，不接收凭据、任意额外字段或隐式默认值。参数在预算预留/claim前校验，Worker消费时再次校验并拒绝与固定配置不符的Provider。原Owner事件摘要继续覆盖签名admission，不另造所有权或调度器。无provider_request的历史离线fixture保持兼容，但不能作为真实业务验收。
English: Existing search_places arguments in signed admission provider_request now pass unchanged into the ProcessBackend operation and idempotency digest. Only Google Places/browser_maps are supported; credentials, extra fields and implicit defaults are rejected. Validation precedes budget reservation/claim, repeats in the Worker and rejects a provider inconsistent with pinned configuration. The original-owner event digest continues covering signed admission without new ownership or a scheduler. Legacy offline fixtures without provider_request remain compatible, without qualifying as real business acceptance.

中文：46项定向测试通过；首次新增测试故意UNKNOWN后未收口，触发ASSOCIATED_TREE_UNVERIFIED退出错误；修正测试夹具后通过，原始失败保留。新固定源码隔离全量848项，37FAIL/17ERROR；新增失败ID []，新增错误ID []。基线6de5cf3实测记录与候选记录SHA均保存，不继承旧833结果，不声称全绿。
English:46 targeted tests pass. An initial fixture left UNKNOWN unclosed and raised ASSOCIATED_TREE_UNVERIFIED on exit; the corrected fixture passes and original output is retained. The clean fixed-source full suite runs848 tests with37 failures/17 errors; added failure IDs [], added error IDs []. Measured6de5cf3 baseline and candidate result hashes are recorded. No old833-result inheritance or all-green claim.

中文：新AMD64禁用包5057文件，固定CPython及业务依赖；实际解压核验UNKNOWN，实际包内Worker操作输入探针PASSED，回滚组件对应PASSED（4960文件）。组件对应不等于现场备份或实际回滚。未安装、未启用服务、未触发Inventory、未发信、未写生产数据库。
English: New disabled AMD64 archive contains5057 files with pinned CPython and business dependencies. Actual extraction verification:UNKNOWN; actual packaged Worker operation probe:PASSED; rollback component parity:PASSED (4960 files). Component parity is not a site backup or actual rollback. No installation, service activation, Inventory trigger, email or production database write occurred.

Install SHA256: 32cb4b3676d2c5b38e63fec0b0bd4516cc13f86d76c6021463df3d137e062720
Rollback tools SHA256: 3f0e113a5f520a2a7aff0ef4d03c9b100f7cc4e27df5adc21538166a14777801
Manifest SHA256: 8d54c268a77095a7ad8d4e3c82ac5a7887b4f2aa992c3ba5024ad79d3cbeba18

中文：整包最终复核超时840秒，整体UNKNOWN；四项检查通过但不替代最终完整性复核。额外原Owner组合33项7ERROR，与上一固定源码错误ID比较见ORIGINAL_OWNER_COMPARISON.json，门禁未改。C盘09:19:45仅余2762534912字节，未删除历史证据。
English: Final archive revalidation exceeded840seconds, overall UNKNOWN; four passing checks do not replace final integrity verification. Additional original-owner combination runs33 tests with7errors; compare prior fixed-source IDs in ORIGINAL_OWNER_COMPARISON.json. No gate changes. C drive had2762534912bytes free at09:19:45; no historical evidence deleted.

中文：默认执行仍CONTRACT_MISSING/exit78，不调用外部服务、不签终态或计费回执；后端UNKNOWN不重放。缺少operation/run/claim权威绑定、终态、幂等保证、取消费用回执、账单账户/project/SKU、使用量周期/数量/单位、金额/币种/credits及账单证据引用；browser_maps另缺来源授权和请求回执。内部命名不构成阻塞。独审PENDING，真实业务执行闭环及Windows安装/启动/注销/跨登录验收未完成。全部最终状态false，BUSINESS_GROWTH=UNKNOWN；安装/派发/取消/SMTP门禁false。
English: Default execution remains CONTRACT_MISSING/exit78 without external requests or terminal/billing receipts; backend UNKNOWN is never replayed. Missing authoritative operation/run/claim binding, terminal status, idempotency guarantee, cancellation-fee receipts, billing account/project/SKU, usage period/quantity/unit, amount/currency/credits and billing evidence reference; browser_maps additionally lacks source authorization and request receipts. Internal naming is not a blocker. Independent review PENDING; real business closure and Windows install/start/logoff/across-login acceptance remain incomplete. All final states false, BUSINESS_GROWTH UNKNOWN; install/dispatch/cancel/SMTP gates false.

中文：本轮实际08:49:20启动，09:34:20截止；平台无整轮硬超时字段，子进程有界，最多两条重型工作线。保留历史锁及他人文件。未执行生产安装或实际回滚，未伪造Reviewer通过。
English: Actual cycle08:49:20 to09:34:20; no platform whole-turn hard-timeout field, individually bounded subprocesses and at most two heavy workstreams. Historical locks and other work are preserved. No production installation/actual rollback or fabricated Reviewer approval.

下一动作 / Next action: 先处理可重建暂存空间并完成21568c8最终文件完整性复核，再继续实际业务调用及权威回执费用接线；不重跑已通过检查、不绕过门禁。
Address reproducible staging space and finish21568c8 final file integrity verification, then continue business invocation and authoritative receipt/cost wiring; do not repeat passed checks or bypass gates.

自检 / Self-check: 中英双语、计数、风险、未执行项及下一步齐备，无凭据或伪完成。 Bilingual, counts, risks, omissions and next action recorded; no credentials or false completion.
