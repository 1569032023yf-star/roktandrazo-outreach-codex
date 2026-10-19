# PHASE 5A 排名截图核验 / Ranking screenshot review

核验时间 / Reviewed: 2026-10-19 18:10 +08.

## 已核实 / Verified

用户提供的原图已逐字节保留，未裁剪、缩放或重绘。大小 116,989 字节，适合后续作为轻量内嵌证据。SHA-256：`d2c82e81da5ad3071b2644d3edc2727985edb1c54a1c6a632ac43162874ae81b`。原图见 [evidence](../../assets/v6/evidence/tiktok_jigsaw_bestsellers_original.png)，机器收据见 [receipt](../../assets/v6/evidence/receipt.json)。

The user-provided original is preserved byte for byte without cropping, resizing or redrawing. Its size is 116,989 bytes, suitable for later lightweight inline evidence. SHA-256 and asset links are above.

人工目视确认图中标题为 Best sellers，选中 Jigsaw Puzzles 类目，商品旁有 1 名徽标。商品可读标题为 “rokt&razo Travel Series, 24 Mini Pack 1000 Pieces Jigsaw Puzzle, 8 Puzzl...”，尾部截断。图片本身没有截图日期、商品链接或明确平台地址；TikTok Shop 归属来自用户说明。不能由此独立确认完整 SKU、站点市场、拍摄日期或当前排名。

Visual inspection confirms the Best sellers heading, selected Jigsaw Puzzles category, rank 1 badge and the truncated product title quoted above. No capture date, listing link or explicit platform address is visible. TikTok Shop attribution comes from the user. Full SKU, marketplace, capture date and current rank remain unverified.

## 工程进度 / Engineering progress

已新增独立的证据准备模块及 6 项离线测试，覆盖原图哈希、篡改拒绝、缺失/未来日期、商品身份、类目排名范围及零售相关性。正向日期与身份记录均为测试夹具，不能当作生产证明。该模块尚未接入发送链，不会激活新模板。

A separate evidence preparation module and six offline tests cover original-byte integrity, tampering, missing/future capture dates, product identity, category-ranking scope and retailer relevance. Positive attestations are fixtures, not production evidence. The module is not connected to the sending chain and activates no template.

现有三套 V6 的 35 项定向测试再次通过，总计本次定向测试 41/41；没有重跑全量回归。此前报告的全量回归失败仍未解决，本次不宣称全量通过。历史 V5 发送记录未修改。

The existing 35 targeted V6 tests passed again: 41/41 targeted tests in this review. The full suite was not rerun; previously reported full-suite failures remain unresolved. No full-regression pass is claimed. Historical V5 sending records were not changed.

## 四套方案状态 / Four-template status

| 模板 / Template | 开发状态 / Development | 本次生产安装 / Installed by this work |
|---|---|---|
| retail_tiktok_bestseller_v6_locked | 等待确认版英文及带日期的身份凭据；未注册 / Awaiting approved English and dated identity evidence; unregistered | NO |
| retail_distributor_v6_locked | 现有开发模板保留 / Existing development template retained | NO |
| custom_production_v6_locked | 现有开发模板保留 / Existing development template retained | NO |
| general_inbox_referral_v6_locked | 现有开发模板保留 / Existing development template retained | NO |

目标路由为：具备真实相关性证明的拼图、玩具、桌游零售/分销客户优先 TikTok 历史热销版；其他零售使用普通零售版；品牌使用定制生产版；未知负责人且类型未确认的公共邮箱使用转介绍版。已确认业务类型的 info@ 不因此改走转介绍。该路由目标不是固定发送配额；真实生产使用比例为 NOT_MEASURED，不能把开发测试分布当作生产比例。

Intended routing prioritizes the historical TikTok bestseller version for relevant puzzle/toy/board-game retailers and distributors with reviewed evidence. Other retailers use retail fallback, brands use custom production, and unclassified public inboxes use referral. A known business type takes precedence over an info@ prefix. These priorities are not fixed quotas. Actual production usage ratios are NOT_MEASURED; fixture distributions are not production measurements.

第四套模板的英文锁定、CID 内嵌、FSP 冻结、Preflight/Sender 兼容及四模板实际试发仍待完成，不能把本次证据测试说成这些项目已验收。

Locking the fourth English template, CID embedding, FSP freezing, Preflight/Sender compatibility and actual four-template QA sends remain outstanding. Evidence tests do not establish acceptance of these features.

## 正式通道只读观察 / Read-only channel observation

18:10:09 +08，health 返回 200；SAFE50 preflight 返回 409，原因是实际文件已经为补丁后版本，并非应再次 apply。当前生产 SHA-256 为 `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903`。SMTP_enabled=0；PreSend、Preflight、Outreach 均 PAUSED，且报告 deleted=true。本次没有 apply、启动 Inventory、发邮件或修改生产数据。

At 18:10:09 +08, health returned 200. SAFE50 preflight returned 409 because the file already matches the patched version; this is not a reason to apply again. The current production SHA-256 is shown above. SMTP_enabled=0; PreSend, Preflight and Outreach are PAUSED and reported deleted=true. This work performed no apply, Inventory start, email send or production data mutation.

通道入口文档仍限定四项操作及 SAFE50 发布；本次未取得新的 V6 发布或内部试发入口。无 Gmail 收件端读取结果，四套送达、垃圾箱归类及 SPF/DKIM/DMARC 均 UNKNOWN。已确认的内部邮箱保持本地白名单；无真实试发。外发的邮寄地址、退订、资格、MX、历史及分阶段门禁继续有效。

The channel entry documentation still restricts operations to the four supported operations and the SAFE50 release. No new V6 release or internal-QA entry point was established. There are no Gmail receiver observations: delivery, spam placement and SPF/DKIM/DMARC are UNKNOWN for all four variants. The confirmed internal mailbox remains on the local allowlist; no real test was sent. Postal address, unsubscribe, eligibility, MX, history and staged external-sending gates remain required.

```text
PHASE = 5A_TIKTOK_EVIDENCE_PREPARATION
TARGETED_TESTS_PASSED = 41/41
FULL_REGRESSION_PASSED = NOT_ESTABLISHED
FOUR_TEMPLATES_REGISTERED = NO
PRODUCTION_DEPLOYED = NO
PRODUCTION_EFFECTIVENESS_VERIFIED = NO
PRODUCTION_USAGE_RATIOS = NOT_MEASURED
SMTP_ENABLED = 0
EMAILS_SENT_BY_THIS_WORK = 0
INBOX_AND_AUTHENTICATION_VERIFIED = UNKNOWN
RESULT = BLOCKED_PENDING_APPROVED_COPY_DATED_IDENTITY_EVIDENCE_AND_SUPPORTED_OPERATIONS
```

后续需提供已确认英文原文、可核实的截图日期和商品身份记录；Codex 随后完成四模板工程和回归，再通过获支持的正式通道部署、内部试发及收件端验收。不能以本收据绕过上述条件。

Next inputs are the approved English original, verifiable capture date and product identity record. Codex then completes four-template engineering and regression before supported controlled deployment, internal QA and receiver-side acceptance. This receipt cannot bypass those conditions.
