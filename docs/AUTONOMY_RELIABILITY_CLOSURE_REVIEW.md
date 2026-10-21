# 可靠性闭环独立审核 / Independent reliability closure review

atomic_json写入加关闭补修通过限定独立审核；未知隔离、queue权威、按需receipt恢复及开发者恢复审核去重静态保留。整体可靠性未闭环，历史三文件不可直接宣称整合完成。

The atomic_json write-plus-close repair passes scoped independent review; quarantine, queue authority, selective receipt repair and deduplicated developer recovery review remain intact on static inspection. Overall reliability is not closed; the three historical files cannot be claimed integrated.

基线 / Baseline: 9af8a23596969dabd44e9ab57ef99ea6e03fa9ed
时间 / Time: 2026-10-20T19:38:59.954734+00:00

限定通过：atomic_json在关闭前捕获dump/flush/fsync主异常，close次异常仅附注；close单独失败仍是主异常。对照9af8a23，未放宽原测试断言。
Scoped pass: atomic_json captures dump/flush/fsync failures before close and annotates secondary close failures; standalone close failures remain primary. No previous assertions were weakened relative to 9af8a23.

独立执行：注入已提交HEAD启动器后运行2项纯内存测试（8种组合）通过；未提交启动器的7项合成进程测试全部通过；另复现R4。未启动真实代理。24项完整supervisor回归由父进程负责，本审核不冒称独立复跑。
Independently executed: 2 memory-only tests (8 combinations) passed with the committed HEAD launcher injected; 7 synthetic process tests passed against the uncommitted launcher; R4 reproduced separately. No real agent was launched. The parent owns the full 24 supervisor regressions; this review does not claim to rerun them.

已提交启动器仍有无限临时输出/内存缓冲和异常清理证据缺口。未提交版本提供双流累计限额、单事件限额、Job清理核验及错误属性，但仅属于候选；默认源码导入会使用工作区未提交文件，不能与HEAD注入运行混称。
The committed launcher still has unbounded temporary output/memory buffering and exceptional-cleanup evidence gaps. The uncommitted candidate adds per-stream/event limits, Job cleanup verification and error attributes. Default source imports use the working copy; they must be distinguished from HEAD-injected execution.

## R1 — MEDIUM — autonomy/supervisor.py:270

启动前仍无runtime、工作树和TEMP卷空间预检；加入可配置余量及提交预算，低空间或检查异常禁止调用runner，覆盖多卷模拟测试。

There is still no prelaunch free-space gate for runtime, worktree and TEMP volumes. Add configurable headroom and commit reserve; low space or inspection failure must prevent runner invocation, with multi-volume mocked tests.

## R2 — HIGH — autonomy/lock_recovery.py:40; autonomy/supervisor.py:72

恢复模块未接线：要求schema2/token/process_identity/tree_state，但现行锁只含pid/started_at；exclusive不参与recovery guard。不能将新文件视为有效锁恢复。先实现统一互斥协议与进程实例/关联树生命周期证据，旧锁保持拒绝；添加PID重用、存活后代、恢复并发测试。

Recovery is not integrated: it requires schema2/token/process_identity/tree_state, whereas current locks contain only pid/started_at; exclusive does not participate in the recovery guard. Implement shared exclusion and process-instance/tree lifecycle evidence before enabling recovery; reject legacy locks and test PID reuse, surviving descendants and concurrent recovery.

## R3 — MEDIUM — autonomy/supervisor.py:228; autonomy/supervisor.py:310

未提交启动器输出异常含OUTPUT_LIMIT及cleanup_verified/cleanup_errors，但run_agent超时分支丢弃清理证据，cycle通用捕获只存类型。UNKNOWN仍禁止重跑，然而无法区分清理已证实与未证实。只序列化白名单reason/清理布尔及有界错误类别，禁止存异常正文；补端到端合成故障测试。

The uncommitted launcher exposes OUTPUT_LIMIT and cleanup_verified/cleanup_errors, but run_agent discards timeout cleanup evidence and cycle keeps only exception type. UNKNOWN still prevents retry, but verified and unverified cleanup become indistinguishable. Persist allowlisted reason/cleanup flags and bounded error classes, never exception messages; add end-to-end synthetic fault tests.

## R4 — MEDIUM — autonomy/process_job.py:58; autonomy/process_job.py:296

未提交启动器_Capture.read的finally直接close，close异常不进入capture.failure，真实线程异常可能退出后被当作清理成功；无读取线程时的直接close也可能覆盖主异常。纯内存复现close失败后capture.failure仍None。将全部关闭异常纳入清理错误通道并保持主异常，添加组合测试后再整合。

In the uncommitted launcher, _Capture.read closes directly in finally; close errors never enter capture.failure, so thread failure can be treated as clean completion. The direct close path with no reader threads may also mask a primary error. An in-memory reproduction leaves capture.failure None after close fails. Route every close error through cleanup reporting while preserving the primary exception, then add combined-fault tests before integration.

建议最小顺序：先接通磁盘预检并保留失败原因；再补R4、完成启动器异常清理测试与整合；最后设计锁schema和共同恢复互斥，旧锁不自动删除。
Minimal order: add disk preflight and preserve failure reasons, fix R4 and complete launcher integration tests, then implement lock schema/shared recovery exclusion without automatically deleting legacy locks.

未修改源代码、队列、状态；仅生成本双语报告和对应JSON。无生产访问、网络请求、采集或发信；CURRENT_STATUS.md和FILE_MANIFEST.md缺失。自主运行及完整可靠性验收仍false。
No source, queue or state edits; only this bilingual report and matching JSON were written. No production access, network requests, discovery or sending. CURRENT_STATUS.md and FILE_MANIFEST.md are missing. Overall autonomy and reliability acceptance remain false.
