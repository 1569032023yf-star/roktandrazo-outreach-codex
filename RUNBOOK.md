# Runbook / 运行手册

## Safe Read-Only Commands / 安全只读命令

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
