# PHASE 5A — V6 内部测试准备与受控恢复状态 / Internal QA and controlled resumption status

## 结论 / Result

中文：RESULT = V6_ENGINEERING_OR_DEPLOYMENT_BLOCKED。V6 代码及发布提案已形成，内部测试预览已生成；生产未部署、真实内部试发 0 封、客户邮件 0 封。35 项定向测试通过；完整回归未通过，不能宣称开发全部完成或生产可发布。DEPLOYED=false，PRODUCTION_EFFECTIVENESS_VERIFIED=false。

English: RESULT = V6_ENGINEERING_OR_DEPLOYMENT_BLOCKED. V6 code/release proposals and internal previews exist. No production deployment, zero actual internal tests, zero customer messages. All 35 targeted tests pass; full regressions fail, so engineering completion or release readiness is not claimed. DEPLOYED=false and PRODUCTION_EFFECTIVENESS_VERIFIED=false.

## 最新授权与白名单 / Latest authority and allowlist

中文：以用户最新确认的 Gmail（公开报告脱敏为 1569***yf@gmail.com）作为唯一内部测试收件人，旧地址已排除。完整地址和实际 From 仅保存在被 Git 忽略的本地内部策略中，未提交。三版均已生成内部预览，带 INTERNAL V6 TEST 标识，暂不附公司地址；没有附件、外链或像素，不创建客户 FSP、授权或客户发送历史。此例外只适用于内部 QA，不能用于客户邮件。用户未提供邮寄地址或确认商业承诺；没有填写虚构地址或将承诺默认置真。

English: Only the latest user-confirmed Gmail (publicly masked as 1569***yf@gmail.com) is allowlisted; the obsolete address is excluded. Full recipient/From values remain only in ignored local internal policy. All three previews are marked INTERNAL V6 TEST, omit the address under the internal-only exception, contain no attachments/links/pixels, and create no customer FSP, authorization or outreach history. The exception does not apply to customers. Postal/business-claim evidence was not supplied and has not been invented or assumed.

## 工程实现与验证 / Engineering and verification

中文：三版 V6 使用完整 64 位中央模板锁、统一签名、纯文本/HTML 同义渲染；业务核实与人工批准优先于邮箱前缀。info@ 玩具店进入零售、hello@ 贺卡品牌进入定制；身份不明不自动发送。保留 V5 历史渲染，但新 FSP、preflight 和 SMTP 必须精确匹配 V6 冻结内容。follow_up 发送关闭；旧 test-mode 捷径被拒绝。

English: Three V6 variants use full 64-character central template locks, a shared signature and equivalent plain/HTML rendering. Verified business identity and approved overrides precede mailbox-prefix routing. An info@ toy store routes retail; a hello@ greeting-card brand routes custom; unknown identity cannot auto-send. V5 remains for historical rendering, while new FSP/preflight/SMTP require exact V6 frozen content. Follow_up sending is disabled and the legacy test-mode shortcut is blocked.

中文：阶段限额 5/10/20/40，在 FSP 与 SMTP 侧执行；升级需要至少 24 小时反馈证据。SQLite 事务在连接 SMTP 前永久预留组织/计划名额，跨批次、并发及模糊结果不会释放。首轮累计 5 个预留后即使跨日也需复核；SMTP/提交异常锁存停止。内部 QA 使用独立白名单、独立审计和每模板唯一预留，不自动重试。模拟 SMTP 仅属于离线测试，不计作真实发信。

English: Stage caps of 5/10/20/40 apply at FSP and SMTP, with at least 24 hours of feedback before escalation. SQLite reserves organization/plan slots before SMTP; batches, concurrency and ambiguous outcomes cannot free them. Five lifetime first-stage reservations require review even across dates. SMTP/commit errors latch a halt. Internal QA has a separate allowlist/audit and unique per-template reservations, without automatic retries. Mock SMTP is offline testing, never actual sending.

| 检查 / Check | 实测结果 / Observed result |
|---|---|
| V6 定向 / Targeted | 35/35 PASS，含冻结内容篡改、首批 5、20 并发、重复组织、QUIT 失败、内部三版模拟 / includes tamper, cap, 20 workers, duplicate orgs, QUIT failure and three internal mocks |
| 基线全量 / Baseline full | 505 tests；3 failures + 1 error |
| 本分支全量 / Branch full | 540 tests；17 failures + 12 errors；NOT PASSED |
| 补丁演练 / Patch rehearsal | 4 个既有文件 + 3 个新模块；正向 SHA、反向字节一致 / 4 existing + 3 new; forward SHA and reverse bytes passed |
| 真实投递 / Actual delivery | 0；未检查 Gmail / 0; Gmail not inspected |

中文：失败涉及新增缺省禁发、旧 V5/通用邮箱优先路由、follow_up 成功与旧 test-mode 的既有测试假设；另外四项基线失败同样存在。尚需迁移测试契约并复核运行兼容性；不能把所有失败自动归为无害旧测试，也不能据此降低门禁。最后一次内部审计字段调整后重新运行 35 项定向测试通过；全量结果来自该调整前的最近完整运行。没有独立第二审查者签字。

English: Failures include old assumptions about default sending, V5/prefix-first routing, successful follow_up and legacy test-mode; four baseline failure/error outcomes also remain. Contract fixtures and runtime compatibility still require migration/review. Do not dismiss all failures as harmless or weaken gates. The final internal-audit field adjustment was followed by another passing 35-test targeted run; full-suite figures describe the latest complete run before that adjustment. No independent second reviewer sign-off exists.

## 正式通道与生产状态 / Authorized channel and production state

中文：2026-10-19 17:43:40 +08，经原有通道 health/preflight 只读返回：生产 orchestrator SHA=e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903；SMTP=0；指定 Inventory 1784775229336 ACTIVE，下次记录为 19:34:47 +08；PreSend/Preflight/Outreach PAUSED 且 deleted=true。ACTIVE 仅证明指定任务状态，不能证明唯一性、真实抓取或最新 SAFE。通道无运行日志/MX探针访问，CURRENT_V2_SAFE 与可发送独立组织均 UNKNOWN，未沿用历史 50/56。

English: At 2026-10-19 17:43:40 +08, read-only health/preflight returned production orchestrator SHA=e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903, SMTP=0, designated Inventory 1784775229336 ACTIVE (next recorded run 19:34:47 +08), and PreSend/Preflight/Outreach PAUSED with deleted=true. ACTIVE proves only that task state, not uniqueness, actual discovery or current SAFE. No runtime-log/MX-probe access is provided; CURRENT_V2_SAFE and send-eligible unique organizations remain UNKNOWN, without reusing historical 50/56.

中文：通道真实连通，但仍只支持 preflight/apply/status/rollback 和原 SAFE50 release。HTTP 409 是已部署 after-SHA 与原 before-SHA 不同的预期拒绝，未重复 apply 或 rollback。桥接曾停止；核实桥接/执行器哈希未变且无桥接监听后，按既有交接恢复隐藏桥接进程，没有变更配置、凭据、ACL、执行策略或业务调度。未手动运行 Inventory，未创建调度器，未部署 4B.1G。

English: The channel is callable but still exposes only preflight/apply/status/rollback and the original SAFE50 release. HTTP 409 is expected because the deployed after-SHA differs from the original before-SHA; no apply/rollback was repeated. After verifying unchanged bridge/executor hashes and no active bridge listener, the documented hidden bridge was restored, without config, credential, ACL, execution-policy or business-scheduling changes. Inventory was not manually run; no scheduler or 4B.1G was deployed.

## 阻塞与下一步 / Blockers and next actions

中文：内部试发的直接阻塞是缺少已登记的 V6 内部 QA 运维入口及 Gmail 连接。已请求 Gmail 官方插件安装，但返回 completed=false/user_confirmed=false；没有声称安装、OAuth 或查信成功，不需要密码。完整客户版本还有工程回归和合规证据阻塞。准备的 [最小接入要求](../../docs/PHASE5A_CONTROLLED_OPERATIONS_REQUIREMENTS.md) 可先提供独立的内部 QA 发布与受限试发操作，保持全局 SMTP=0 及客户任务暂停。完整发布需要新的多文件执行与失败恢复门禁；现有单文件执行器不能直接执行。

English: Internal tests are directly blocked by the missing registered internal-QA operations entry point and Gmail connection. Official Gmail installation was requested but returned completed=false/user_confirmed=false; installation, OAuth and mailbox access are not claimed, and no password is needed. The full customer version also has regression and compliance blockers. The [minimum operations requirements](../../docs/PHASE5A_CONTROLLED_OPERATIONS_REQUIREMENTS.md) allow a separate internal-QA release/restricted test operation while global SMTP=0 and customer tasks stay paused. A complete release requires newly registered multi-file execution and failure-recovery gates; the existing single-file executor cannot execute it directly.

中文：后续由 Codex 统一负责发布。工程回归需继续修复；正式入口具备后内部每版各一封，以 Message-ID、收件位置和原始 Authentication-Results 验证；SPF/DKIM/DMARC 当前均 UNKNOWN。外部客户恢复须补足邮寄地址及全部真实证据，再使用唯一正式发送链进行首批 5 个组织及至少 24 小时观察。回滚方案必须保留历史、预算预留和发送/停止审计。离线可逆不等于生产回滚已验收。

English: Codex retains release ownership. Continue regression repair. Once supported internal operations exist, send one per variant and verify Message-ID, placement and original Authentication-Results; SPF/DKIM/DMARC are currently UNKNOWN. External restoration requires the postal address and all real evidence, then a unique supported chain with the first five organizations and at least 24-hour observation. Rollback must preserve history, reservations and send/halt audits. Offline reversibility does not prove production rollback acceptance.

依据 / References: [FTC CAN-SPAM](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)；[Google sender FAQ](https://support.google.com/mail/answer/14229414?hl=en)。中文：商业邮件邮寄地址及退订要求仍适用于正式客户发送，内部例外来自用户本次具体授权，非法律结论。English: Postal/opt-out requirements remain gates for customer commercial mail; the internal exception is task-specific user authority, not a legal conclusion.

## 报告自检 / Report self-check

中文：已区分预览、模拟 SMTP、真实接受、收件、认证和生产效果；未知指标保留 UNKNOWN，发送计数只涵盖本次真实操作。无密码/token/完整个人邮箱/生产数据库/完整敏感源码；包含已执行、未执行、风险及下一步。代码提交、推送及完整机器字段见同目录 RESULT.json；本报告不构成可执行发送授权。

English: Preview, mock SMTP, real acceptance, receipt, authentication and production effectiveness are distinguished. Unknown metrics stay UNKNOWN and send counts cover actual task operations only. No passwords/tokens/full personal mailbox/production DB/full sensitive source is included. Executed/unexecuted work, risks and next actions are stated. Code commit/push and machine fields are in RESULT.json. This report is not executable sending authorization.
