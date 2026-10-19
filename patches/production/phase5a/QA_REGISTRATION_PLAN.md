# V6 正式新登记方案 / V6 new-release registration plan

中文：这是受控入口的新登记申请，不是生产登记或可执行发送授权。既有 SAFE50 release 不适用于 V6。2026-10-20 00:48:45 +08 的实际入口 health=200，仅公布 preflight/apply/status/rollback；独立 QA release 的 preflight=400 UNKNOWN_RELEASE_ID。

English: This is a new-registration request, not production registration or executable sending authority. Never reuse the SAFE50 release for V6. At 2026-10-20 00:48:45 +08, the live entrypoint returned health=200 and exposed only preflight/apply/status/rollback; preflight for the independent QA release returned 400 UNKNOWN_RELEASE_ID.

## 最小 QA 范围 / Minimal QA scope

中文：登记 `phase5a1-v6-four-template-internal-qa`，只允许 `internal_qa_once`；固定收件人 `1569032023yf@gmail.com`，最多四封，每模板一次。现有腾讯企业邮箱为唯一发件传输，Gmail 仅收件，无需 OAuth。`internal-qa.patch` 只创建 v6_outreach.py、v6_bestseller_evidence.py、controlled_v6_test.py，PNG 原图另行按清单哈希登记。依赖原 bd_sender.py 指纹，不替换它，也不部署客户发送模块。

English: Register `phase5a1-v6-four-template-internal-qa` for `internal_qa_once` only, pinned to `1569032023yf@gmail.com`, at most four messages and once per template. Existing Tencent enterprise SMTP is the only sender; Gmail is solely the recipient and OAuth is unnecessary. `internal-qa.patch` creates only v6_outreach.py, v6_bestseller_evidence.py and controlled_v6_test.py; register the original PNG separately against its manifest hash. Pin the existing bd_sender.py dependency without replacing it or deploying customer sending modules.

中文：`internal-qa-request.json` 固定全部新增文件哈希及文本补丁哈希，仍标记 registered=false。文本正向与逆向演练通过；完整10文件客户候选补丁也通过离线正向及字节级回滚，但不代表已获生产发布资格。env_loader.py、回归工具及测试变更是开发环境改进，不在 QA 生产包中。

English: `internal-qa-request.json` pins all created-file and text-patch hashes and remains registered=false. The text-only forward/reverse rehearsal passed; the complete ten-file customer proposal also passed offline forward and byte-exact rollback, without establishing production readiness. Changes to env_loader.py, regression tooling and tests improve development only and are excluded from the production QA bundle.

## 正式入口一次性接入 / One-time supported-entrypoint provisioning

1. 中文：通道维护方使用其正式登记流程，审核清单/补丁/原图和独立审查证据；当前 API 没有登记动作，不由开发进程直接改 bridge/config/ACL。English: The channel maintainer uses its supported registration process to review manifests, patch, original image and independent-review evidence; the current API has no registration action, and development must not edit bridge/config/ACL directly.
2. 中文：登记固定 QA 文件、依赖、收件人和一次执行能力；正式入口必须拒绝任意文件、任意收件人、超过四封、过期授权及重放，不提供任意脚本执行接口。English: Register fixed QA files, dependency, recipient and one-shot capability; the supported entrypoint must reject arbitrary files/recipients, more than four messages, expired authority and replay, without arbitrary script execution.
3. 中文：入口原生验证实时指纹、无覆盖新增、Inventory 互斥、备份完整性及多文件失败恢复；试发前要求最新单收件人策略、已核实 From、24小时有效期和固定 test_run_id。English: The entrypoint itself verifies live fingerprints, create-if-absent constraints, Inventory exclusion, backup integrity and multi-file failure recovery; QA requires a fresh single-recipient policy, verified From, 24-hour validity and fixed test_run_id.
4. 中文：由入口触发已有 controlled_v6_test，持久预留必须先于 SMTP；超时、拒收、策略漂移、审计失败立即停止；不确定结果不得自动重试。不创建客户 FSP、客户授权或发送调度，不启用全局客户 SMTP。English: The entrypoint invokes existing controlled_v6_test with durable reservation preceding SMTP; timeout, rejection, policy drift or audit failure stops immediately, with no automatic ambiguous retry. Create no customer FSP, authority or schedule and do not enable global customer SMTP.
5. 中文：保存脱敏 Message-ID、接受时间和四模板结果，人工收件端核对 Inbox/Spam 及原始 SPF/DKIM/DMARC；SMTP 接受不等于收件或认证成功。English: Save masked results, Message-ID and acceptance time for all four templates; verify Inbox/Spam and original SPF/DKIM/DMARC at the receiver. SMTP acceptance does not establish delivery or authentication.

## 客户发布边界 / Customer-release boundary

中文：QA 正式登记与客户多文件发布为两个范围。客户邮寄地址、声明审核、真实收件认证、MX、历史、组织去重、抑制及完整发送授权链均需通过；follow_up 保持关闭。TikTok 缺日期/平台/商品身份排名证据时，相关零售自动回退普通零售，不阻塞普通零售、品牌定制或转介绍工程。

English: QA registration and the full customer multi-file release are separate scopes. Customer postal address, verified claims, actual receiver authentication, MX, history, organization deduplication, suppression and the complete sending-authority chain must pass; follow_up remains disabled. Missing TikTok capture-date/platform/product evidence routes relevant retailers to the ordinary retail fallback without blocking retail, custom-production or referral engineering.

中文：未执行任何生产写入、真实 SMTP 或客户发送；未修改权限、凭据、桥接、调度或生产数据库。数量：实际内部/客户邮件均0；正式 QA 登记0。风险：入口缺少受支持登记/试发动作，归档工件缺失导致全量未全绿；生产运行及认证状态 UNKNOWN。下一步由总控独立审查并推动通道维护方登记后，仅通过正式入口预检/试发。敏感信息检查通过：无凭据、token 或原始客户数据。

English: No production write, real SMTP or customer message was executed; permissions, credentials, bridge, schedules and production databases were unchanged. Counts: actual internal/customer messages=0; registered QA releases=0. Risks: supported registration/QA capability is absent and missing archived artifacts keep the full suite non-green; production runtime and authentication remain UNKNOWN. Next the coordinator independently reviews and arranges maintainer registration, then uses supported preflight/QA only. Sensitive-information review passed: no credentials, tokens or raw customer data.
