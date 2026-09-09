# 历史与重复组件审计 / Legacy and Duplicate Component Audit

日期 / Date: 2026-09-08。状态 / Status: classification only; no deletion or refactoring.

中文：历史文件不等于死代码，重复文件也不等于可删除。以下结论来自开发副本的导入关系、入口和归档痕迹，不包含外部 automation 的完整调用图。必须先证明无调度/无动态依赖，才能进入后续清理。

English: Historical does not mean dead, and duplicated does not mean disposable. Findings use copied imports, entrypoints and archive records, not a complete external automation call graph. Retirement requires proving absence of scheduler/dynamic dependencies.

| 类别 / Category | 文件 / Files | 结论 / Conclusion |
|---|---|---|
| 当前核心 / Current core | bd_orchestrator, discovery, bd_db, V1/V2, preflight, final_send_plan, daily_session, bd_sender, review/recovery | 保留；五个冻结文件零改动。 / Retain; five frozen files unchanged. |
| 共用函数与旧 main 混合 / Shared utility plus legacy runner | inventory_monitor_executor.py | canonical stage 使用 http_scan_website；不能整体删除，但 standalone main/safe_write_a0 是另一写入路径。 / Shared scanner is active; standalone runner is a separate writer. |
| 旧发送链 / Legacy send chain | sender.py, main.py, pipeline.py, send_phase2.py, send_phase3.py | 仍有调用和 SMTP 内容；BD_TEST_MODE 可解禁。未来应真正不可执行，当前保留审计。 / Still linked and conditionally enabled; retain for audit, do not execute. |
| 旧数据库体系 / Legacy databases | db.py, phase1_db.py, bd_main.py, config.py consumers | leads.db、phase1_leads.db 与 bd_leads.db 混存；不能随意合库或自动导入。 / Multiple database lineages; no automatic consolidation. |
| AI 辅助脚本 / AI-assisted tooling | collection_pipeline.py, search_engine.py, auto_collector.py, website_verifier.py, contact_extractor.py | 有查询/解析能力；collection_pipeline.search 明确要求 AI WebSearch 并读取手工结果文件，不能当无人值守官网发现器。 / Query/parsing helpers are not a complete unattended resolver. |
| Agent 命名组件 / Agent-named components | agent_lead_collector/sender/supervisor/verifier/reply/bounce/report; pipeline_orchestrator | 名称不代表独立服务；部分是 dry-run 选择器，部分写库或启动子进程。 / Names do not prove services; mixed previews, writers and process runners. |
| 候选镜像 / Candidate mirrors | workbuddy_candidate_modules/lead_hygiene_gate.py, production_adapter.py, b_pool_enrichment.py | 与根目录门禁/adapter 重复；b_pool 含其他工作区路径。部分 follow-up builder 仍被条件导入，不能统一判死。 / Duplicate gates/adapters, external paths and conditional imports prevent blanket deletion. |
| 静态报告与 UI / Reports and UI | bd_dashboard_v3.2.py, bd_ops_dashboard.html, bd_review_server.py, output dashboards | Dashboard module 被 ops API 动态载入；不能仅因另有 HTML 判断旧版无用。 / Dynamic API loading means old-looking dashboard is not necessarily dead. |
| 历史脚本 / Archived scripts | _archived_scripts, _retired, backup, backups, data/production_acceptance_backup_20260727/code | 完整保留，全部纳入静态扫描；含写库/发信/迁移和硬编码路径。 / Retained and scanned; includes mutating and machine-bound code. |
| 临时诊断 / Temporary diagnostics | 原 output 中的 .py、.bak_*、.ARCHIVED_* | 日期文件仍可能可执行；已隔离 output，不把它们恢复为生产入口。 / Dated files may remain executable; output is quarantined. |
| 主机辅助 / Host utilities | configure_bios_power, install_service_elevate, modern_standby_guard_test, disabled launcher files | 涉及 OS 服务、电源、计划任务；测试命名不代表无副作用。 / OS-mutating helpers, even when named test. |

## 配置重复的实际后果 / Consequences of duplicated configuration

中文：发现三个不应归为单纯“代码风格”的分歧：库存 Broad Ready 与 FSP V2 不同；NY discovery 与 tri-state A0 不同；Browser Maps file 默认遮蔽 direct 环境设置。修这些数据流契约应排在清理旧文件之前。30/40/60 多个数值也须区分库存目标与发送上限，不能做全局查找替换。

English: Three mismatches have behavioral impact, not merely style: Broad Ready inventory versus V2 FSP, NY discovery versus tri-state A0, and Browser Maps file defaults versus direct configuration. Fix these contracts before cleanup. The 30/40/60 values represent different policies and must not be globally replaced.

中文：两个语法错误文件都为历史 `_simple_check.py` 副本。其余可解析只意味着 AST 语法通过，不证明依赖齐全或运行正确。现有 SMTP 唯一权威测试把 `raise RuntimeError` 等任意字符串视为禁用标记，不能证明门禁在所有路径先于发送执行。

English: Both syntax errors occur in historical `_simple_check.py` copies. Other files parsing successfully proves neither dependency completeness nor correct execution. The single-SMTP-authority test accepts marker strings such as `raise RuntimeError`; this does not prove every path blocks before sending.

## 清理前置条件 / Cleanup prerequisites

中文：为每个候选保存文件哈希、调用方、DB 归属、最后任务来源和替代实现；在隔离测试验证替代路径后逐个退役。不得因 09-04 历史报告的建议自行删除七个 automation、两个 Windows task 或 quarantine 内容。本阶段这些外部对象均未操作。

English: Record each candidate's hash, callers, database ownership, last scheduler source and replacement. Retire individually after isolated validation. The old report is not authorization to delete seven automations, two Windows tasks or quarantined files; no external object was changed in Phase 1.
