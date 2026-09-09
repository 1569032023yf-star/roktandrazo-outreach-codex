# Project Skills / 项目技能

## Evidence Rule / 证据规则

中文：
本文件只记录已经由文件、目录、package 配置、历史产物或只读命令交叉验证的能力。不得凭记忆判断项目能力。恢复包中的结论如果与当前生产目录冲突，以当前实际文件和命令验证为准。

English:
This file only records capabilities verified by files, directories, package configuration, historical artifacts, or read-only commands. Project capabilities must not be inferred from memory. If recovery-package conclusions conflict with the current production directory, current files and command verification take precedence.

## Task Startup Rule / 任务启动规则

中文：
每次 Codex task window 开始前，必须先读取 `PROJECT_SKILLS.md`、`CURRENT_STATUS.md`、`GUARDRAILS.md`、`RUNBOOK.md`、`FILE_MANIFEST.md` 和最近相关报告。缺失必读规则文件时，不得直接 live send。

English:
At the start of every Codex task window, read `PROJECT_SKILLS.md`, `CURRENT_STATUS.md`, `GUARDRAILS.md`, `RUNBOOK.md`, `FILE_MANIFEST.md`, and the latest relevant reports. If required rule files are missing, live send must not proceed directly.

## Verified Capability Summary / 已验证能力摘要

中文：
以下 16 项能力已基于实际文件、目录或 package 配置确认。Google Maps 组件是普通工具，不是 skill。项目级 `.workbuddy/skills` 不存在；用户级 `.workbuddy/skills` 存在 94 个目录。

English:
The following 16 capabilities were verified from actual files, directories, or package configuration. Google Maps components are plain tools, not skills. Project-level `.workbuddy/skills` does not exist; user-level `.workbuddy/skills` contains 94 directories.

| # | Capability / 能力 | Evidence / 证据 | Status / 状态 | Notes / 说明 |
|---:|---|---|---|---|
| 1 | Browser Verification / 浏览器验证 | `browser_verifier.py` exists / 文件存在 | Ready / 可用 | Playwright based; must be TN/AR/KY filtered before broad use / 使用前需加州过滤 |
| 2 | Fast Lead Discovery / 快速线索发现 | `fast_lead_discovery.py` exists / 文件存在 | Ready / 可用 | HTTP-first + optional Playwright fallback / HTTP 优先，可回退浏览器 |
| 3 | Google Maps Branch / Google Maps 候选发现 | `tools/google-maps-scraper/gmaps_fast_poc.py` exists; POC report exists / 脚本和 POC 报告存在 | POC / 原型 | Candidate discovery only, not A0 verification / 只能发现候选，不能直接升级 A0 |
| 4 | B2 Manual Queue / B2 人工队列 | `b_pool_audit_v2.py`, B2 reports exist / 脚本和报告存在 | Ready / 可用 | B2 is manual review, no auto-send / B2 只人工审核 |
| 5 | Bounce Auditor / 退信审计 | `agent_bounce_auditor.py` exists / 文件存在 | Patched but needs periodic validation / 已修复但需复核 | Message-ID missing must not suppress / Message-ID 缺失不得 suppression |
| 6 | Reply Monitor / 回复监控 | `agent_reply_monitor.py` exists / 文件存在 | Ready / 可用 | IMAP dependent; do not output credentials / 依赖 IMAP，不输出凭据 |
| 7 | Daily Orchestrator / 日常编排 | `daily_operator_auto.py` exists / 文件存在 | Ready with gates / 有 gate 可用 | Do not restore long-term automation without user confirmation / 未确认不得恢复长期自动化 |
| 8 | State Deep Coverage / 州深度覆盖 | `city_selector_v2.py`, `primary_state_cities.json` exist / 文件存在 | Ready / 可用 | Primary states TN/AR/KY / 主攻 TN/AR/KY |
| 9 | Inventory Shift / 库存班次 | `inventory_shift_live.py`, `inventory_shift_ar_ky.py` exist / 文件存在 | POC / 原型 | Must not auto-send; candidate generation only until verified / 未验证前只做候选 |
| 10 | Pool Analysis / 池统计 | `pool_analysis.py` exists / 文件存在 | Ready / 可用 | Use for counts, not as send authorization / 用于统计，不等于发信授权 |
| 11 | Email Template / 邮件模板 | `bd_template.py` exists / 文件存在 | Ready / 可用 | V5 template current / 当前 V5 |
| 12 | Lead Scoring / 线索评分 | `scorer_v2.py` exists / 文件存在 | Ready / 可用 | A/B/C scoring; evidence gate still required / 评分后仍需证据 gate |
| 13 | IMAP/SMTP Email Skill / IMAP/SMTP 邮件 skill | `~/.workbuddy/skills/skill_2053082149365157888/SKILL.md` exists / skill 文件存在 | Installed / 已安装 | Credential sensitive / 涉及凭据风险 |
| 14 | US Retail Lead Collector Skill / 美国零售线索 skill | `~/.workbuddy/skills/us-retail-lead-collector/SKILL.md` exists with `disable: true` / skill 文件存在且禁用 | Disabled / 已禁用 | Do not enable without user approval / 未确认不得启用 |
| 15 | Playwright + Chromium / Playwright + Chromium | `pip show playwright` = 1.60.0 / package 配置 | Installed / 已安装 | Used by browser tools / 浏览器工具依赖 |
| 16 | HTTP Libraries / HTTP 库 | `httpx` 0.28.1, `beautifulsoup4` 4.15.0 / package 配置 | Installed / 已安装 | Used by fast discovery / 快速发现依赖 |

## Tool Evidence / 工具证据

中文：
生产目录实际存在以下核心脚本：`browser_verifier.py`、`fast_lead_discovery.py`、`pool_analysis.py`、`city_selector_v2.py`、`b_pool_import.py`、`b_pool_audit_v2.py`、`agent_reply_monitor.py`、`agent_daily_report.py`、`scorer_v2.py`、`daily_operator_auto.py`、`agent_bounce_auditor.py`。因此“当前系统缺少这些工具”的旧判断不适用于当前生产目录。

English:
The production directory actually contains these core scripts: `browser_verifier.py`, `fast_lead_discovery.py`, `pool_analysis.py`, `city_selector_v2.py`, `b_pool_import.py`, `b_pool_audit_v2.py`, `agent_reply_monitor.py`, `agent_daily_report.py`, `scorer_v2.py`, `daily_operator_auto.py`, and `agent_bounce_auditor.py`. Therefore, older statements that the current system lacks these tools do not apply to the current production directory.

## Google Maps Tool Status / Google Maps 工具状态

中文：
`gmaps_fast_poc.py`、`gmaps_playwright_poc.py`、`inventory_shift_ar_ky.py`、`inventory_shift_live.py`、`queries_tn.txt` 和 `gmaps-scraper.exe` 位于 `tools/google-maps-scraper/`。这些是普通工具，不是 skill。历史 POC 报告和样例 CSV 存在，但 Google Maps 结果只能作为候选发现，必须经官网验证后才能进入 A0。

English:
`gmaps_fast_poc.py`, `gmaps_playwright_poc.py`, `inventory_shift_ar_ky.py`, `inventory_shift_live.py`, `queries_tn.txt`, and `gmaps-scraper.exe` are located under `tools/google-maps-scraper/`. They are plain tools, not skills. Historical POC reports and sample CSV files exist, but Google Maps results are candidate discovery only and must pass official-site verification before A0.

## Installed Skills / 已安装 Skills

中文：
已验证用户级 WorkBuddy skills 中存在 `us-retail-lead-collector`、`skill_2053082149365157888`（IMAP/SMTP）、`skill_2054901281445961728`、`skill_2054901364493180928`。项目级 `.workbuddy/skills` 不存在。`us-retail-lead-collector` 当前 `disable: true`，不得未经用户确认启用。

English:
Verified user-level WorkBuddy skills include `us-retail-lead-collector`, `skill_2053082149365157888` (IMAP/SMTP), `skill_2054901281445961728`, and `skill_2054901364493180928`. Project-level `.workbuddy/skills` does not exist. `us-retail-lead-collector` currently has `disable: true` and must not be enabled without user confirmation.

## Pool Definitions / 池口径

中文：
A0 是可发送候选，必须有官方来源邮箱、evidence_url 和 evidence_snippet。B2/manual_review_needed 只用于人工审核，不自动发送。C/contact_form_pool 不发邮件。suppression、hard bounce、delivery_issue、unsubscribe 和已回复对象不得发送。

English:
A0 is the sendable class and must have official-source email, evidence_url, and evidence_snippet. B2/manual_review_needed is for manual review only and must not be auto-sent. C/contact_form_pool must not be emailed. suppression, hard bounce, delivery_issue, unsubscribe, and replied contacts must not be sent.

## Message-ID Header Requirement / Message-ID Header 要求

中文：
每封邮件必须包含 From、To、Subject、Date、Message-ID、MIME-Version、Content-Type、Reply-To。Message-ID 必须唯一，不得固定或复用。`message_id_missing` 不得触发 hard bounce suppression。

English:
Every email must include From, To, Subject, Date, Message-ID, MIME-Version, Content-Type, and Reply-To. Message-ID must be unique and must not be fixed or reused. `message_id_missing` must not trigger hard bounce suppression.

## Send Window / 发信窗口

中文：
客户 live send 只能在 Asia/Shanghai 09:00-13:00 内执行。窗口外只能 dry-run、生成待发清单或补池，不能客户发信。

English:
Customer live send may only run within Asia/Shanghai 09:00-13:00. Outside the window, only dry-run, pending-send list generation, or inventory rebuild may run; customer email must not be sent.

## Primary States / 主攻州

中文：
补池主攻州是 TN / AR / KY，即 Tennessee、Arkansas、Kentucky。不得全美泛扫或随机跨州。Google Maps 工具如使用，也必须限制在受控州/城市队列内。

English:
Primary rebuild states are TN / AR / KY: Tennessee, Arkansas, and Kentucky. Nationwide broad scanning or random cross-state processing is not allowed. If Google Maps tools are used, they must be constrained to the controlled state/city queue.

## Targets / 目标

中文：
sendable_pool 目标为 60，daily target 为 20。不要因为库存多就多发，也不要因为库存不足就绕过 gate。

English:
sendable_pool target is 60 and daily target is 20. Do not send more because inventory is high, and do not bypass gates because inventory is low.

## Evidence Gate / 证据 Gate

中文：
evidence_url + evidence_snippet 是 A0 发信 gate。不得盲目从 notes 全量复制 evidence_snippet。Google Maps 只能候选发现，不能直接升级 A0。

English:
evidence_url + evidence_snippet is an A0 send gate. Do not blindly copy all notes into evidence_snippet. Google Maps may only be used for candidate discovery and must not directly upgrade to A0.

## Email Exclusions / 邮件排除项

中文：
B2、C、guessed_email、suppression、hard bounce、delivery_issue、unsubscribe、duplicate domain、duplicate store、risky Microsoft 365 / Exchange MX 均不得自动发送。

English:
B2, C, guessed_email, suppression, hard bounce, delivery_issue, unsubscribe, duplicate domain, duplicate store, and risky Microsoft 365 / Exchange MX must not be auto-sent.

## Report Requirement / 报告要求

中文：
所有报告必须中英双语。每份报告必须包含执行结果、未执行事项、风险、数量统计、下一步和敏感信息检查。

English:
All reports must be bilingual Chinese-English. Every report must include execution results, non-executed items, risks, counts, next steps, and sensitive information checks.
