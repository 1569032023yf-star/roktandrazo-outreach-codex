# 独立工程审核 / Independent engineering review

结论：APPROVED_SCOPED_ENGINEERING。最终候选未发现阻断本次工程范围的问题；这不是生产闭环验收或无人值守运行验收。
Verdict: APPROVED_SCOPED_ENGINEERING. No remaining blocking finding was identified within the reviewed engineering scope. This is not production closure or unattended-operation acceptance.

## 范围与验证 / Scope and validation

只读审核 process_job、lock_recovery、supervisor 的锁/执行器/dashboard、telemetry 消费器、observe_bd_production 工具、固定 Git 源恢复工具及 AST 隔离路径测试；未修改源码或提交。
Read-only review covered process containment, lock recovery, supervisor execution/dashboard, telemetry consumption, the production observation tool, fixed-Git-source reconstruction, and isolated AST path tests. No source edits or commits were made by this reviewer.

独立运行六个测试模块：C 46 + B 28 + A 7 = 81/81 PASS，13.338 秒，进程退出码 0。完整日志 tests.log，测试后源码 SHA256 清单 tests.json。
Independent execution of six test modules: C 46 + B 28 + A 7 = 81/81 PASS in 13.338 seconds, exit code 0. Full output is in tests.log; post-test source SHA256 values are in tests.json.

首次启动的 PowerShell 宿主报告 Out of memory，未产生测试结果；该基础设施失败单列，不计为代码通过或失败。未终止用户其他进程。
The first PowerShell launch reported Out of memory and produced no test result. This infrastructure failure is excluded from the code verdict. No unrelated user process was terminated.

## 已关闭发现 / Closed findings

1. 锁状态写入失败曾覆盖原始 AGENT_TIMEOUT 和 cleanup 证据。当前保留原始 reason、cleanup_verified/errors，新增固定 lock_state_update_failed/error_type；先持久化后更新内存，写入失败保留 unverified 锁并拒绝重跑。真实锁加故障注入测试通过。
   Lock-state persistence failure previously masked AGENT_TIMEOUT and cleanup evidence. The final implementation retains the original fields, records fixed lock-update failure metadata, updates memory only after persistence, quarantines the unverified lock, and rejects retries. Real-lock fault-injection tests pass.
2. 输出流关闭根因类别曾被上层 ProcessCleanupError 覆盖。当前保留 OUTPUT_READERS_CLEANUP、OUTPUT_STREAM_CLOSE_FAILED 和 OSError 固定类别，不保存敏感异常文本；队列持久化测试通过。
   Output-close root-cause classification was previously obscured by ProcessCleanupError. Fixed cleanup-step and root-cause classifications now survive durable queue storage without sensitive exception text; regression tests pass.
3. 已退出但句柄保留的 Windows 进程对象不再被当作存活。身份检查同时查询进程信号状态；未知检查拒绝恢复，PID 创建身份不一致才识别复用。真实 retained-handle 测试通过。
   An exited Windows process object retained by an open handle is no longer treated as live. Identity inspection checks process signaling; uncertain inspection blocks recovery, and creation identity distinguishes PID reuse. The retained-handle regression test passes.
4. 畸形嵌套 status 不再触发非预期 TypeError。缺失/陈旧遥测的 dashboard 当前段显示 UNKNOWN / NOT_VALIDATED，不再显示认证新鲜状态；历史记录保留。
   Malformed nested status values no longer trigger an unexpected TypeError. Missing or stale telemetry produces UNKNOWN / NOT_VALIDATED in the current dashboard section while preserving history.

## 验收边界 / Acceptance boundaries

Windows 真实进程树清理、父子死亡与延迟 marker 不写测试通过；API故障注入通过。不等于真实 Codex 长周期运行、跨多次心跳、断电、所有 POSIX 平台验证。旧锁只在 token、原进程实例死亡、已验证树状态等证据满足时恢复；legacy、不明身份、未验证树维持拒绝。
Real Windows process-tree termination, parent/child death and delayed-marker suppression tests pass, together with injected API failures. This does not establish long-running Codex behavior, multiple unattended heartbeats, power-loss behavior, or all POSIX platforms. Legacy, uncertain-identity and unverified-tree locks remain blocked.

B 消费器只接纳认证来源契约下的 allowlist 聚合，保留 UNKNOWN；actual 56 不提升为权威 SAFE，historical_total 不计新增，指定 Inventory 活跃不证明全局唯一。本人未独立发起本次生产遥测请求，仅审核消费代码并运行测试；父代理的真实调用证据需另行引用。
B consumes allowlisted aggregates under an authenticated-source contract and preserves UNKNOWN. Actual 56 is not promoted to authoritative SAFE; historical totals are not new acquisition; designated Inventory activity does not prove global uniqueness. This reviewer did not independently issue the production telemetry request; the parent's live-call evidence must be cited separately.

A 测试使用精确 Git SHA 恢复源码、AST 提取和模拟业务依赖。证明该固定源码中 SAFE 56 仍调用四条 discovery lane，不能证明生产当前入口、实际 active state 或真实停滞根因已定位。生产阶段日志、权威 SAFE 和真实无人值守多心跳验收仍待补证。
A tests use exact Git source reconstruction, AST extraction and mocked business dependencies. They show that SAFE 56 still invokes all four discovery lanes in that fixed source, but do not establish the actual production entry point, active state, or root cause. Production stage evidence, authoritative SAFE, and real unattended multi-heartbeat acceptance remain outstanding.
