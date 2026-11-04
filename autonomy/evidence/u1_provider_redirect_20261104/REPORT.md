# 正式Provider跳转边界 / Real Provider redirect boundary

时间 / Time: 2026-11-04T10:18:36.044149+00:00
固定源码 / Fixed source: 5dde9061ee97eeb756ed52f40b30b18afd2ddb8b

中文：已读取用户完整三阶段总指令，保留正式Provider、完整独立安装包及真实Windows全生命周期范围，未将读附件或单项修复作为最终完成。旧候选及旧包成绩保留，不继承至本SHA。
English: Read the full three-stage directive and retained the real Provider, standalone package and actual Windows lifecycle scope. Reading the attachment or fixing one issue does not complete the goal. Historical candidate/archive results remain historical.

中文：真实Google Places请求改用拒绝自动重定向的urllib打开器，保留既有代理与TLS处理。301/302/303/307/308均不产生第二请求，保持原POST地址，结果进入provider_outcome_unknown且不重试。没有更换认证协议或启用SerpAPI。测试使用真实urllib错误/重定向管道和替身HTTPS传输，无真实Provider请求，不能作为业务验收。
English: Real Google Places requests now use a redirect-rejecting urllib opener, retaining existing proxy/TLS handling.301/302/303/307/308 never generate a second request; the original POST endpoint remains fixed and outcomes stay UNKNOWN without retry. Authentication is unchanged and SerpAPI remains disabled. Tests exercise the real urllib redirect/error pipeline with fake HTTPS transport, not actual Provider acceptance.

验证 / Validation:
python -B -m unittest tests.test_google_places_redirect tests.test_google_places_unknown test_provider_contracts -q
8 PASS / 1.016s; raw output: TEST_OUTPUT.txt. git diff --check PASS.
独审 / Independent review: PENDING. 全量 / Full regression: NOT_RUN. 新包 / New archive: NOT_BUILT.

官方依据 / Official sources:
- https://developers.google.com/maps/documentation/places/web-service/text-search — synchronous POST and field mask / 同步POST与字段掩码。
- https://developers.google.com/maps/documentation/places/web-service/usage-and-billing — SKU-based billing / 按SKU计费。
- https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery — account/project/SKU, usage, cost, credits and currency / 账单导出字段。

中文：外部合同仍CONTRACT_MISSING：operation_id与本地claim绑定、权威终态、幂等保证、取消回执/费用、账单账户/项目/SKU绑定、用量周期/数量/单位、金额/币种/抵扣、证据引用。官方接口说明及汇总账单不能自动证明本地单次请求的精确费用。真实计费请求仍需单独受控授权，本轮不请求开通；先继续离线开发。未索要内部命名或旧环境资料。
English: External contracts remain CONTRACT_MISSING for operation-to-claim binding, authoritative terminal state, idempotency, cancellation receipt/fee, billing account/project/SKU mapping, usage period/quantity/unit, amount/currency/credits and evidence reference. API documentation and aggregate billing do not prove exact per-request charges. Any billable request requires separate controlled authorization; this turn does not request activation and offline engineering continues.

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

下一步：分离原入口的批准配置读取并将输出状态路径接入固定宿主；随后真实业务worker与预算/回执合同集成。Windows安装、重启、注销、Session0、升级、中断和回滚均未验收。没有生产写入、采集、SMTP、权限更改或凭据输出。
Next: separate approved configuration loading and propagate the output state path through the pinned host, then integrate the real worker with budget/receipt contracts. Windows installation, reboot, logoff, Session0, upgrade, interruption and rollback remain unaccepted. No production writes, collection, SMTP, ACL changes or credential output occurred.
