# U1 全量回归断点 / U1 full-regression checkpoint

基线 / Baseline: b3a0d3ae26ef99fea5f458ec029301d233a27f7c。
独立工作树 / Isolated worktree: roktandrazo-u1-regression-baseline。
状态 / Status: BASELINE_INTERRUPTED_MEMORY_PRESSURE。

启动前观测可用物理内存1194724KB，超过1GB门槛；已读取development_safety.py及回归隔离测试，基线自带跟踪的.development-copy，不复制生产库、环境文件或秘密。运行已有 `python -B tools/run_comparable_suite.py autonomy/runtime/u1-regression-baseline`。

Observed1194724KB available physical memory before preparation, above the1GB threshold. Read development_safety.py and regression isolation tests. The baseline includes the tracked .development-copy marker; no production database, environment file or secret was copied. Used the existing comparable-suite runner.

运行开始后主代理报告内存降至675936KB，立即通过Ctrl-C停止。进程已退出，检查没有残留run_comparable_suite.py进程。仅本地原始日志存在，result.json未生成，测试未完成；不能提取完整失败/错误ID集合，也不能沿用历史43/17作为本轮结果。

After startup, the parent reported memory falling to675936KB; execution was immediately interrupted with Ctrl-C. The process exited and no comparable-suite process remained. Only a local raw log exists; no result.json was generated. The run is incomplete, so complete failure/error ID sets are unavailable and historical43/17 counts cannot substitute for this run.

候选全量尚未启动；NO_NEW_REGRESSION=UNKNOWN，FULL_SUITE_PASSED=UNKNOWN。下一步在内存稳定>=1GB且最终候选固定后串行重新执行基线与候选，比较各自完整失败/错误ID集合。局部测试通过不替代全量回归。

The candidate full suite has not started. NO_NEW_REGRESSION=UNKNOWN and FULL_SUITE_PASSED=UNKNOWN. Once memory is stably at least1GB and the candidate is pinned, rerun baseline then candidate serially and compare complete failure/error ID sets. Targeted tests do not replace full regression.
