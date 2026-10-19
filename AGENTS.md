## 2026-10-19 PHASE 5A 授权更新 / PHASE 5A authority update

中文：用户已单独授权在全部条件满足后受控恢复 new_outreach，并批准三版 V6 的内部试发。后文历史“V6 不部署、不发送”冻结由本次具体授权取代，但不等于目前已具备发送条件。内部测试仅使用用户最新确认的单一受控白名单邮箱，可暂不附邮寄地址；开发副本仍禁止真实 SMTP。正式客户发送仍必须具备有效实体邮寄地址、真实业务承诺、退订、收件端认证证据、MX/历史/组织去重及完整发送链门禁。follow_up 关闭。生产发布、内部试发和自动化恢复均只能通过正式支持入口；现有 SAFE50 release 不可用于 V6。

English: The user separately authorized controlled new_outreach resumption after all gates pass and internal tests of all three V6 variants. This specific authority supersedes historical “do not deploy/send V6” wording, without asserting present readiness. Internal QA uses only the latest user-confirmed single controlled mailbox and may temporarily omit a postal address; development copies still cannot use real SMTP. Customer sending still requires a valid physical postal address, verified business claims, unsubscribe handling, receiver authentication evidence, MX/history/organization deduplication, and the complete gated sending chain. Keep follow_up disabled. Production releases, internal tests and automation recovery require supported authorized entry points; never reuse the SAFE50 release for V6.

详见 / See [Phase 5A report](handoff/phases/PHASE5A_V6_TEMPLATES_SEND_RESUMPTION.md)。

# 项目执行指令 / Project execution instructions

所有回答使用中文；产生的报告必须中英双语。

All user replies must be Chinese; generated reports must be bilingual Chinese and English.

任务启动先读取 [工程与部署责任制](docs/CODEX_ENGINEERING_AND_DEPLOYMENT_CHARTER.md)、PROJECT_SKILLS.md、GUARDRAILS.md、RUNBOOK.md 和相关当前报告。Codex 负责正常工程的开发、审查、受控发布及真实生产验收，不再默认交给 WorkBuddy 部署。普通发布无需重复批准，但必须通过正式授权通道和全部门禁。开发隔离继续有效，全部商业邮件冻结；不得绕过护栏获取生产权限。历史文档中的旧分工及发送流程不能替代当前责任制或单独发送授权。

At task startup, read the [engineering and deployment charter](docs/CODEX_ENGINEERING_AND_DEPLOYMENT_CHARTER.md), PROJECT_SKILLS.md, GUARDRAILS.md, RUNBOOK.md, and relevant current reports. Codex owns routine development, review, controlled releases, and real production acceptance; deployment is no longer assigned to WorkBuddy by default. Routine releases require no repeated approval but must use an authorized channel and pass all gates. Development isolation remains effective and all commercial email remains frozen. Do not bypass guards to gain production permissions. Historical assignments and sending procedures cannot replace the current charter or separate sending authorization.
