# U1 Worker操作绑定接线 / Worker operation binding

固定源码 / Fixed source: 6de5cf3d421e0073be905a57e0dd3cd2cc1024a6
时间 / Time: 2026-11-04T22:26:37.826882+00:00

中文：正式Worker执行入口现在消费后端stdin操作，限制65536字节，拒绝重复JSON键、非有限数值、错误协议、Inventory、执行范围及幂等摘要。原事件或claim摘要出现时必须完整绑定锁、运行身份、账本及claim，并核对token摘要关联。无效操作在构造真实适配器前拒绝且不回显输入。此为完整性校验，父ProcessBackend仍负责Owner活性授权；不把摘要校验当作独立授权。
English: The real Worker entrypoint now consumes backend stdin, limits input to65536 bytes and rejects duplicate JSON keys, nonfinite values, invalid protocol/Inventory/scope and idempotency digests. Original event or claim digests require complete lock, identity, ledger and claim joins, including token-digest consistency. Invalid operations fail before adapter construction without echoing input. This validates integrity; the parent ProcessBackend remains responsible for live owner authority.

中文：24项定向测试通过；新固定源码隔离全量848项，37FAIL/17ERROR；新增失败ID []，新增错误ID []。基线9d5ecb6实测记录与候选记录SHA均保存，不继承旧833结果，不声称全绿。
English:24 targeted tests pass. The clean fixed-source full suite runs848 tests with37 failures/17 errors; added failure IDs [], added error IDs []. Measured9d5ecb6 baseline and candidate result hashes are recorded. No old833-result inheritance or all-green claim.

中文：新AMD64禁用包5057文件，固定CPython及业务依赖；实际解压核验VERIFIED，实际包内Worker操作输入探针PASSED，回滚组件对应PASSED（4960文件）。组件对应不等于现场备份或实际回滚。未安装、未启用服务、未触发Inventory、未发信、未写生产数据库。
English: New disabled AMD64 archive contains5057 files with pinned CPython and business dependencies. Actual extraction verification:VERIFIED; actual packaged Worker operation probe:PASSED; rollback component parity:PASSED (4960 files). Component parity is not a site backup or actual rollback. No installation, service activation, Inventory trigger, email or production database write occurred.

Install SHA256: 675ca73bc83565410ea48f6abbe3de5b5413483e55eae4cc4546a03e0a0570ae
Rollback tools SHA256: 13b22df446812f3af503a3d81fbf48045bb17cf1373412e2fa9a870580a55c0d
Manifest SHA256: 4601347e02ad85c32ec8f4953daca6a97f04b45c528f75acc4eaa2c41eb439f3

中文：默认执行仍CONTRACT_MISSING/exit78，不调用外部服务、不签终态或计费回执；后端UNKNOWN不重放。缺少operation/run/claim权威绑定、终态、幂等保证、取消费用回执、账单账户/project/SKU、使用量周期/数量/单位、金额/币种/credits及账单证据引用；browser_maps另缺来源授权和请求回执。内部命名不构成阻塞。独审PENDING，真实业务执行闭环及Windows安装/启动/注销/跨登录验收未完成。全部最终状态false，BUSINESS_GROWTH=UNKNOWN；安装/派发/取消/SMTP门禁false。
English: Default execution remains CONTRACT_MISSING/exit78 without external requests or terminal/billing receipts; backend UNKNOWN is never replayed. Missing authoritative operation/run/claim binding, terminal status, idempotency guarantee, cancellation-fee receipts, billing account/project/SKU, usage period/quantity/unit, amount/currency/credits and billing evidence reference; browser_maps additionally lacks source authorization and request receipts. Internal naming is not a blocker. Independent review PENDING; real business closure and Windows install/start/logoff/across-login acceptance remain incomplete. All final states false, BUSINESS_GROWTH UNKNOWN; install/dispatch/cancel/SMTP gates false.

中文：本轮实际05:51:28启动，06:36:28截止；平台无整轮硬超时字段，子进程有界，最多两条重型工作线。保留历史锁及他人文件。未执行生产安装或实际回滚，未伪造Reviewer通过。
English: Actual cycle05:51:28 to06:36:28; no platform whole-turn hard-timeout field, individually bounded subprocesses and at most two heavy workstreams. Historical locks and other work are preserved. No production installation/actual rollback or fabricated Reviewer approval.

下一动作 / Next action: 继续原Owner绑定的业务请求映射和权威回执接线；缺失费用、终态、幂等及取消合同不得执行外部请求或伪造回执。
Continue original-owner-bound business request mapping and authoritative receipt wiring; missing cost, terminal, idempotency and cancellation contracts prohibit external requests or fabricated receipts.

自检 / Self-check: 中英双语、计数、风险、未执行项及下一步齐备，无凭据或伪完成。 Bilingual, counts, risks, omissions and next action recorded; no credentials or false completion.
