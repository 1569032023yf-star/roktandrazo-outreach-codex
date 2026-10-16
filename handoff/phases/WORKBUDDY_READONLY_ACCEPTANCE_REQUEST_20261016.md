# WorkBuddy 一次性只读运行验收请求 / One-time read-only runtime acceptance request

状态：已准备，当前无可调用的 WorkBuddy 消息入口，尚未确认送达或执行。请将本文件交给既有 WorkBuddy 运行方；它不是可执行脚本、发送授权或新调度器。

Status: prepared; no callable WorkBuddy messaging entry point is available and delivery/execution are not confirmed. Forward this file to the existing WorkBuddy runtime operator. It is not an executable script, email authorization, or new scheduler.

## 范围 / Scope

用户已授权一次只读验收。不要重新开发或部署补丁，不 apply、不 rollback、不手动启动 Inventory。仅检查唯一 Inventory `1784775229336` 于 `2026-10-15T15:41:00+08:00` 后的正常计划运行。发布操作 `op-20261015-104202-5ecde6` 已于 `2026-10-15T10:42:04+08:00` 完成。当前通道 SHA 已核实为 `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903`，无需重部署。

The user authorized one read-only acceptance pass. Do not redevelop or deploy the patch, apply, roll back, or manually start Inventory. Inspect only normal scheduled runs of Inventory `1784775229336` after `2026-10-15T15:41:00+08:00`. Release operation `op-20261015-104202-5ecde6` finished at `2026-10-15T10:42:04+08:00`. The channel already confirmed the current SHA as `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903`; redeployment is unnecessary.

## 必须返回的证据 / Required evidence

1. 报告采样时间与时区、实际运行来源、run ID、开始/结束时间（统一 +08，并注明原字段时区）、automation ID/正常计划触发关联；确认没有重复 Inventory 调度器。 / Report sampling time/timezone, execution source, run IDs, start/end times normalized to +08 with original field timezones, and automation/normal-schedule linkage; verify no duplicate Inventory scheduler.
2. 每轮运行入口 SAFE≥50 的证据，以及真实 Provider 请求数、请求审计标识、返回状态、页数和查询族；逐轮页预算≤3。无需为验收额外发起采集请求。 / Evidence of SAFE>=50 at each run's entry, actual Provider request counts/audit references, response statuses, pages and query families; each run must stay within three pages. Do not initiate collection requests for acceptance.
3. Cooperstown 的城市 ID、查询族与分页游标前后值及时间，证明推进来自上述运行。 / Cooperstown city ID, before/after query-family and pagination cursor values with timestamps, linked to those runs.
4. 新真实独立组织、新 lead、新官网第一方邮箱的实际数量、去重口径、时间区间、首方证据和历史门禁结果。报告零新增可以通过；不得把新增行数当新增独立组织。仅返回脱敏汇总，不提供客户明细。 / Actual new independent organizations, leads and first-party official-site emails, with deduplication definitions, interval, first-party evidence and history-gate outcomes. Zero additions may pass. Do not substitute new rows for independent organizations. Return sanitized aggregates without customer records.
5. **先执行既有正式 MX 控制探针**，提供既有探针标识/版本、时间、控制结果、解析环境与通过判据。仅允许已支持的无业务写入只读探针；如果探针需要业务数据修改、扩权或额外发送，停止并报告阻塞。通过后再以现有完整 V1/V2/MX/历史/退订/抑制门禁读取最新 SAFE 独立组织数及采样时间；探针未通过则 CURRENT_SAFE=UNKNOWN，不用旧50或存储 ready flag 替代。 / **First run the existing formal MX control probe**, reporting its identity/version, time, control results, resolver environment and passing criteria. Use only an existing read-only probe without business-data writes. Stop and report a blocker if it requires business modifications, elevated permissions or sending. Only after it passes, read the latest unique-organization SAFE count using the unchanged complete V1/V2/MX/history/unsubscribe/suppression gates with a sampling time. Otherwise set CURRENT_SAFE=UNKNOWN; do not substitute the old 50 or stored ready flags.
6. 检查指定区间的新异常、Provider错误、锁冲突、并发/重叠、重复组织；旧陈旧运行残留另列，不归因于本次发布。核实 SMTP=0、PreSend/Preflight/Outreach 暂停、区间实际发送数。 / Audit new exceptions, Provider errors, lock conflicts, concurrency/overlaps and duplicate organizations in the requested interval. Separate old stale residue from release failures. Verify SMTP=0, paused PreSend/Preflight/Outreach, and actual sends in the interval.

## 返回与边界 / Return and boundaries

返回一份中英双语脱敏 Markdown/JSON 报告，列出证据来源（不含凭据）、时间、已确认/UNKNOWN、Provider 是否确实执行，以及 DEPLOYED 与 PRODUCTION_EFFECTIVENESS_VERIFIED 两项独立结论。保留本地详细证据供原运行方追溯；不要把邮箱、客户明细或秘密推到公开 Git。一次验收即可，不创建循环或新计划。

Return a bilingual sanitized Markdown/JSON report with evidence provenance excluding credentials, timestamps, confirmed/UNKNOWN fields, actual Provider execution, and separate DEPLOYED and PRODUCTION_EFFECTIVENESS_VERIFIED verdicts. Retain detailed evidence locally for the runtime operator. Do not publish emails, customer records or secrets to Git. Perform one acceptance pass without a loop or new schedule.

全部商业邮件冻结；不得启 SMTP 或恢复发送自动化，不改 SAFE/MX/历史资格，不删除历史客户或 SAFE 批次，不部署 4B.1G。此次仅委托 WorkBuddy 运行环境取证；正常工程、后续受控发布和最终验收判断仍由 Codex 统一负责。

All commercial email remains frozen. Do not enable SMTP or sending automations, change SAFE/MX/history eligibility, delete historical customers or SAFE batches, or deploy 4B.1G. This delegates only runtime evidence collection to WorkBuddy; Codex retains ownership of routine engineering, subsequent controlled releases and final acceptance judgments.
