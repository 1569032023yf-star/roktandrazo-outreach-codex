# PHASE 5A.1 四模板进度 / Four-template progress

## 里程碑 A / Milestone A

中文：四模板已在开发注册表注册并以完整 SHA-256 锁定。TikTok 版采用本次用户提供的候选英文；普通零售去掉 DDP、低起订量及样品表述。品牌定制及转介绍保留。info@ 仍优先按核实业务类型路由。

English: All four templates are registered in development with full SHA-256 locks. TikTok uses the candidate English supplied for this task. Retail fallback removes DDP/minimum-order/sample emphasis. Custom/referral variants remain. Verified business type takes precedence over an info@ prefix.

中文：仅相关零售且日期/平台/商品身份证据通过时优先 TikTok。证据不齐回退普通零售；人工指定也不能绕过。正式排名渲染明确历史日期和类目范围，纯文本完整保留；HTML CID 仅使用哈希锁定原图，不使用外链或像素。原始 PNG 未改动。内部未核实候选有醒目标注，不嵌未核实图片。当前真实截图证据仍未通过，不声称当前第一。

English: TikTok takes priority only for relevant retailers with approved date/platform/product evidence. Missing evidence falls back to retail; overrides cannot bypass it. External rendering binds the historical date/category in full plain text and embeds only the pinned original through CID, without remote images or pixels. The original PNG is unchanged. Pending internal previews are conspicuously marked and omit unverified imagery. Actual ranking evidence remains unverified; no current-rank claim is made.

中文：51 项定向测试通过，四套内部文字/HTML 预览已生成，无 SMTP 调用。独立 QA 发布申请清单已生成，尚未获正式入口登记。旧 V5 历史数据未改。完整回归和审查继续作为里程碑 B；基线与当前启动方式相同，结果尚在运行。

English: All 51 targeted tests passed. Four internal text/HTML previews were generated with zero SMTP calls. An independent QA release request manifest exists but is not registered at a supported entry point. V5 historical data was not changed. Comparable full suites and review continue as milestone B with identical startup; results are pending.

## 真实内部测试 / Actual internal QA

中文：里程碑 C 阻塞在正式 QA 发布/测试入口。Gmail 查询确认尚未安装/连接，已提供连接建议；没有收件端观测，不得把 SMTP 接受或预览当送达和认证。最多四封、每模板一封、仅本地白名单邮箱，不建立客户 FSP/授权、不启用全局客户 SMTP、不重试不确定结果。

English: Milestone C is blocked on the supported QA release/test operation. Gmail discovery confirms it is not installed/connected; a connection suggestion was provided. No receiver observations exist: preview/SMTP acceptance cannot prove delivery/authentication. Limit QA to four messages, one per variant, to the local single-recipient allowlist, without customer FSP/authorization/global SMTP or ambiguous retries.

中文：生产默认使用比例尚未测得；这是条件优先级，不是固定配额。客户邮件本阶段为 0，生产客户发送关闭。机器字段及本次代码提交见同目录 PHASE5A1_VALIDATION_RESULT.json。

English: Actual production usage ratios are not measured. Routing is conditional priority, not a fixed quota. Customer messages for this phase are zero and production customer sending is disabled. Machine fields and code commit appear in PHASE5A1_VALIDATION_RESULT.json.
