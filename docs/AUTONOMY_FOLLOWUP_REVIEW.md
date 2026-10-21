# 恢复补修复审 / Recovery follow-up review



独立审核发现写入与关闭同时失败会覆盖主异常，父进程纯内存复现；22项登记回归通过，仍需补修

Independent review found primary-error masking when write and close both fail; parent reproduced it in memory. 22 registration regressions passed; further repair required



Trigger / 触发: 2026-10-20T17:29:53.906Z; cycle: 4e13f42a-1305-4ee9-aed9-46b1e6954797

结论：请求补修。静态审核确认未知结果隔离、禁止自动重执行、queue权威、receipt按需恢复及developer恢复后审核去重符合主要要求；对照cd9f454至9af8a23，未发现放宽旧断言。仍发现一项主异常保留缺口。22项原测试均未执行：全部依赖临时目录，其中一项启动子进程，不符合本次纯内存限制；另行准备的纯内存验证也因Python不在PATH、直接执行Python312被拒绝访问而未运行。历史测试通过声明未获本轮独立确认。未修改文件、联网、启动代理或访问生产DB、SMTP、凭据。空间预检、输出限额及异常进程清理仍未验收；CURRENT_STATUS.md、FILE_MANIFEST.md缺失。

Decision: changes requested. Static review supports unknown-outcome quarantine, prevention of automatic re-execution, queue authority, selective receipt recovery and deduplicated review registration after developer recovery. Comparing cd9f454 through 9af8a23 revealed no weakened existing assertions. One primary-exception preservation gap remains. None of the 22 original tests ran: all require temporary directories and one launches subprocesses, outside this review's memory-only scope. A separate memory-only check also could not run: Python was absent from PATH and direct Python312 execution was denied. Historical test-pass claims were not independently confirmed. No files changed, networking, agents, production DB, SMTP or credentials accessed. Space preflight, output limits and exceptional process cleanup remain unaccepted; CURRENT_STATUS.md and FILE_MANIFEST.md are missing. Memory served only to locate prior audit context; conclusions were checked against current files.




autonomy/supervisor.py:43-48; autonomy/test_supervisor.py:240-273; docs/AUTONOMY_UNKNOWN_OUTCOME_RECOVERY.md

atomic_json仅在文件上下文管理器退出后捕获异常。如果dump或显式flush先失败，而随后关闭缓冲文件时再次flush也失败，__exit__的关闭异常会成为顶层异常；原始写入异常只留在异常上下文中。外层临时文件及锁清理保护无法恢复原始异常身份。现有测试叠加的是unlink失败，未覆盖写入失败与close失败组合，因此文档关于保留原始写入异常的表述仍不完整。应在关闭文件前捕获主异常，关闭失败仅附注，并新增纯内存组合故障测试，断言传播的仍是原异常对象。此发现来自静态控制流分析，运行复现被Python执行权限阻止。

atomic_json catches exceptions only after the file context manager exits. If dump or explicit flush fails and closing the buffered file also fails during its final flush, the __exit__ exception becomes the top-level exception; the original write error remains only in exception context. Temporary-file and lock-cleanup protection cannot restore its identity. Existing tests combine write failures with unlink failures, not close failures, leaving the documentation's original-write-exception preservation claim incomplete. Capture the primary exception before closing, annotate secondary close failures, and add a memory-only combined-fault test asserting original exception identity. This finding follows static control-flow analysis; execution permissions prevented runtime reproduction.



下一项 / Next: D-write-close-preservation

未部署、未发信、业务UNKNOWN；原有三文件哈希不变。 / No deployment or sending; business metrics UNKNOWN; three pre-existing file hashes unchanged.