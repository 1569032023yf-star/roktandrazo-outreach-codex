## 2026-10-19 PHASE 5A 授权更新 / PHASE 5A authority update

中文：用户已单独授权在全部条件满足后受控恢复 new_outreach，并批准三版 V6 的内部试发。后文历史“V6 不部署、不发送”冻结由本次具体授权取代，但不等于目前已具备发送条件。内部测试仅使用用户最新确认的单一受控白名单邮箱，可暂不附邮寄地址；开发副本仍禁止真实 SMTP。正式客户发送仍必须具备有效实体邮寄地址、真实业务承诺、退订、收件端认证证据、MX/历史/组织去重及完整发送链门禁。follow_up 关闭。生产发布、内部试发和自动化恢复均只能通过正式支持入口；现有 SAFE50 release 不可用于 V6。

English: The user separately authorized controlled new_outreach resumption after all gates pass and internal tests of all three V6 variants. This specific authority supersedes historical “do not deploy/send V6” wording, without asserting present readiness. Internal QA uses only the latest user-confirmed single controlled mailbox and may temporarily omit a postal address; development copies still cannot use real SMTP. Customer sending still requires a valid physical postal address, verified business claims, unsubscribe handling, receiver authentication evidence, MX/history/organization deduplication, and the complete gated sending chain. Keep follow_up disabled. Production releases, internal tests and automation recovery require supported authorized entry points; never reuse the SAFE50 release for V6.

详见 / See [Phase 5A report](handoff/phases/PHASE5A_V6_TEMPLATES_SEND_RESUMPTION.md)。

﻿# Guardrails / 项目护栏

## Bilingual Report Requirement / 双语报告要求

中文：首先读取 [Codex 工程与部署责任制](docs/CODEX_ENGINEERING_AND_DEPLOYMENT_CHARTER.md)。正常工程通过门禁后由 Codex 通过正式通道部署，无需逐次批准。开发隔离和商业邮件冻结继续有效；历史“WorkBuddy 必须部署”和发送步骤不构成当前操作授权。

English: First read the [Codex engineering and deployment charter](docs/CODEX_ENGINEERING_AND_DEPLOYMENT_CHARTER.md). Codex deploys gated routine fixes through the authorized channel without repeated approval. Development isolation and commercial email freeze remain effective; historical WorkBuddy-only deployment and sending steps do not authorize current actions.

All project reports, audit reports, handoff reports, fix reports, daily reports, and weekly reviews must be written in Chinese and English.

所有项目报告、审计报告、交接报告、修复报告、日报和周复盘必须使用中英双语。

A report that is not bilingual is considered incomplete and must be rewritten before the task can be marked done.

任何非双语报告都视为未完成，必须重写后才能标记任务完成。

## Report Self-Check Before Completion / 完成前报告自检

Before generating or finalizing any project document or report, run the report self-check and make sure every item passes.

在生成或最终确认任何项目文档或报告前，必须执行报告自检，并确保每一项都通过。

The self-check must confirm: bilingual Chinese-English content, Chinese explanation, English version, no sensitive information, execution results, non-executed items, risks, next steps, no unfinished work marked complete, and alignment with the BD automation project framing.

自检必须确认：中英双语、包含中文解释、包含英文版本、没有敏感信息、包含执行结果、包含未执行事项、包含风险、包含下一步、没有把未完成事项写成已完成，并且符合 BD 自动化项目口径。
