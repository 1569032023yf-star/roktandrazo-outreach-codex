# 全量比较完成 / Complete regression comparison

基线 b3a0d3a 与候选 b69214d 使用同一候选运行器串行运行，均完成833项，37失败、17错误、0跳过；失败和错误ID集合完全相同，新增回归0。不是全绿。机器结果见REGRESSION_FINAL_COMPARISON.json。

Baseline b3a0d3a and candidate b69214d ran serially with the same candidate runner. Both completed833 tests, with37 failures,17 errors and0 skips. Failure and error ID sets are identical: zero new regressions, not an all-green suite. See the machine comparison.

根目录U1专项另有38项通过，包含多进程claim、退出故障与预算并发；host及runner另12项通过。不能将这些单独项目算入833项。

Separately,38 root U1 tests passed, including multiprocess claims, process-exit faults and concurrent budgets;12 host/runner tests also passed. These are outside the833-test count.

用户明确授权在处理内存期间继续，运行后可用内存升至约1.72GiB。没有实际内存异常或中断。测试为开发隔离副本，无生产采集、数据库写入或发信。

The user explicitly authorized continuation while addressing memory; available memory subsequently rose to about1.72GiB. No memory exception or interruption occurred. Development isolation remained in effect, with no production collection, database writes or sending.

此比较仅覆盖上述固定候选。正在开发的执行适配器不继承本次结论；其定向测试、最终独审与必要回归仍待完成。RELEASE_READY=false，PRODUCTION_DEPLOYED=false，PRODUCTION_ACCEPTED=false。下一步完成执行组合与发布兼容门禁。报告仅含测试ID、摘要和哈希，无秘密或客户资料。

This comparison covers only the pinned candidate. The execution adapter under development does not inherit acceptance; targeted tests, final review and necessary regression remain outstanding. Release, deployment and production acceptance remain false. Next: complete execution integration and compatibility gates. This report contains only test IDs, summaries and hashes, without secrets or customer data.
