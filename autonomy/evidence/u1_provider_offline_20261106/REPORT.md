# Provider 离线参数检查 / Offline Provider argument admission

中文：本轮手动开发始于 2026-11-06 14:34:30 UTC+8，基于 `03c2ec44e1ca4d8b1b8d10841756ded13380f571`，使用 D 盘独立分支 `codex/u1-provider-offline-20261106`。修复原 owner 桥在保存不可重放事件意图之前没有校验已签名的 Provider 查询参数的问题。先复现原行为：无效查询仍调用 prepare_event；修复后在意图之前拒绝，仍保留执行阶段原有检查。

English: This manually initiated development cycle started at 2026-11-06 14:34:30 UTC+8 from `03c2ec44e1ca4d8b1b8d10841756ded13380f571` in the isolated D: branch `codex/u1-provider-offline-20261106`. The owner bridge now validates signed Provider search arguments before recording a durable non-replayable event intent, while retaining execution-time checks. The initial regression test reproduced the old call to prepare_event for invalid input.

中文：改动 `autonomy/inventory_event_bridge.py` 和 `test_inventory_event_bridge.py`。在 `ROKT_DEV_ALLOW_LOOPBACK=1` 下运行 `python -m unittest test_inventory_event_bridge test_provider_worker.WorkerOperationTests test_provider_worker.WorkerAdmissionBoundaryTests test_provider_worker.BoundSearchRequestTests -q`，18 项通过。更广测试 32 项中 8 项因现有开发防护禁止本机连接或隔离子进程而报错；未关闭防护、未将该组标记通过。测试仅使用本机回环和临时数据，不证明正式 Provider 费用、回执或生产验收。

English: Changed `autonomy/inventory_event_bridge.py` and `test_inventory_event_bridge.py`. With `ROKT_DEV_ALLOW_LOOPBACK=1`, the command above passed 18 offline tests. A broader 32-test run had 8 errors because existing development guards rejected loopback or isolated subprocesses; those guards were not disabled and that run is not reported as passing. Tests used local loopback and temporary data only; they do not prove production Provider billing, receipts or acceptance.

中文：未进行真实商家采集、生产数据库写入、SMTP、生产派发、安装或配额变更；未创建调度器。敏感信息检查：本记录不包含凭据或客户数据。风险和下一步：正式 Provider 合同仍缺失，源码需独立审核；固定版本确认后继续业务参数接线及完整包。自动任务 ACTIVE，不把本轮手动开发当成定时运行；下一次触发时间未获平台确认。

English: No real merchant collection, production database write, SMTP, production dispatch, installation, quota change or scheduler creation occurred. Sensitive information check: this record includes no credentials or customer data. The formal Provider contract remains missing and independent review is pending; continue business parameter wiring and fixed-version package work. The automation is ACTIVE; this manual cycle is not a scheduled-run receipt and its next trigger time has not been confirmed by the platform.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false.
