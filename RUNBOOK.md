## 2026-10-19 PHASE 5A 授权更新 / PHASE 5A authority update

中文：用户已单独授权在全部条件满足后受控恢复 new_outreach，并批准三版 V6 的内部试发。后文历史“V6 不部署、不发送”冻结由本次具体授权取代，但不等于目前已具备发送条件。内部测试仅使用用户最新确认的单一受控白名单邮箱，可暂不附邮寄地址；开发副本仍禁止真实 SMTP。正式客户发送仍必须具备有效实体邮寄地址、真实业务承诺、退订、收件端认证证据、MX/历史/组织去重及完整发送链门禁。follow_up 关闭。生产发布、内部试发和自动化恢复均只能通过正式支持入口；现有 SAFE50 release 不可用于 V6。

English: The user separately authorized controlled new_outreach resumption after all gates pass and internal tests of all three V6 variants. This specific authority supersedes historical “do not deploy/send V6” wording, without asserting present readiness. Internal QA uses only the latest user-confirmed single controlled mailbox and may temporarily omit a postal address; development copies still cannot use real SMTP. Customer sending still requires a valid physical postal address, verified business claims, unsubscribe handling, receiver authentication evidence, MX/history/organization deduplication, and the complete gated sending chain. Keep follow_up disabled. Production releases, internal tests and automation recovery require supported authorized entry points; never reuse the SAFE50 release for V6.

详见 / See [Phase 5A report](handoff/phases/PHASE5A_V6_TEMPLATES_SEND_RESUMPTION.md)。

﻿# Runbook / 运行手册

## Safe Read-Only Commands / 安全只读命令

中文：以 [Codex 工程与部署责任制](docs/CODEX_ENGINEERING_AND_DEPLOYMENT_CHARTER.md) 为当前授权依据。正常发现和工程自主完成，发布仅通过正式通道并通过全部门禁。后文历史发送步骤暂不执行，SMTP / PreSend / Preflight / Outreach 冻结。通道缺失时按 [一次性接入要求](docs/CONTROLLED_DEPLOYMENT_CHANNEL.md) 处理，不绕过开发隔离。

English: The [Codex engineering and deployment charter](docs/CODEX_ENGINEERING_AND_DEPLOYMENT_CHARTER.md) governs current authority. Complete routine discovery and engineering autonomously; release only through the authorized channel after all gates pass. Historical sending steps below remain inactive; SMTP / PreSend / Preflight / Outreach stay frozen. Follow [one-time connection requirements](docs/CONTROLLED_DEPLOYMENT_CHANNEL.md) if the channel is unavailable; do not bypass development isolation.

中文：
允许执行只读 schema 检查、pool count、scheduled task 状态检查、process 检查、`py_compile`、报告读取和脱敏候选审计。只读命令不得输出 `.env`、SMTP/IMAP 密码、token、cookie 或 auth json。

English:
Allowed read-only actions include schema inspection, pool counts, scheduled task status checks, process checks, `py_compile`, report reading, and masked candidate audits. Read-only commands must not output `.env`, SMTP/IMAP passwords, tokens, cookies, or auth json.

## Dry-Run Commands / Dry-run 命令

中文：
dry-run 必须先于 live send。dry-run 必须输出候选数量、计划发送数量、脱敏邮箱、domain、store_name、state、city、evidence_url、evidence_snippet、排除原因、header 检查和 Message-ID 唯一性检查。

English:
Dry-run must run before live send. Dry-run must output candidate count, planned send count, masked email, domain, store_name, state, city, evidence_url, evidence_snippet, exclusion reasons, header check, and Message-ID uniqueness check.

## Header-Only Validation / Header-only 验证

中文：
header-only 验证必须确认 Date、Message-ID、MIME-Version、Content-Type、Reply-To 存在，并确认连续两封邮件 Message-ID 不同。

English:
Header-only validation must confirm Date, Message-ID, MIME-Version, Content-Type, and Reply-To are present, and must confirm two consecutive messages have different Message-ID values.

## Preflight / 发信前检查

中文：
preflight 必须检查 Message-ID fix、send_pause、auto_send_enabled、scheduled task 风险、sendable_pool、今日已发数量、发送窗口、V5 模板、suppression、bounce、delivery_issue、sent、duplicate domain 和 evidence_snippet gate。

English:
Preflight must check Message-ID fix, send_pause, auto_send_enabled, scheduled task risk, sendable_pool, today's sent count, send window, V5 template, suppression, bounce, delivery_issue, sent, duplicate domain, and evidence_snippet gate.

## Controlled Live Send / 受控 live send

中文：
live send 只有在所有 gate 通过且当前位于 Asia/Shanghai 09:00-13:00 时才允许执行。最多 20 封，只能发送 A0 / approved_manual_send，必须写 send_log，并且不得在窗口外发送客户邮件。

English:
Live send is allowed only when all gates pass and the current time is within Asia/Shanghai 09:00-13:00. It is capped at 20 emails, may only send A0 / approved_manual_send, must write send_log, and must not send customer email outside the window.

## Inventory Rebuild / 库存补池

中文：
库存补池目标是 sendable_pool >= 60。只允许 TN/AR/KY。Google Maps 只能做候选发现，不能直接升级 A0。只有官网真实邮箱 + evidence_url + evidence_snippet 才能升级 A0。

English:
Inventory rebuild target is sendable_pool >= 60. Only TN/AR/KY are allowed. Google Maps may only be used for candidate discovery and must not directly upgrade candidates to A0. Only official-site real emails with evidence_url and evidence_snippet may be upgraded to A0.

## Report Generation / 报告生成

中文：
所有项目报告必须中英双语，并在完成前执行报告自检。报告必须包含执行结果、未执行事项、风险、数量统计、下一步和敏感信息检查。

English:
All project reports must be bilingual Chinese-English and must run report self-check before completion. Reports must include execution results, non-executed items, risks, counts, next steps, and sensitive information checks.
