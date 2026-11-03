# 进程维护权监督独立范围审核 / Process authority scoped independent review

固定源码 / Fixed source: `8dde11230772484cc86ee7dfc3d2d45f891ec58a`  
基线 / Baseline: `5fac8c7d13a9b5b678b3ea2e5024701a82027720`

结论：**OFFLINE_SCOPED_REVIEW_PASSED**。已独立审查五文件差异和失败清理路径，未发现本范围新增的可确认阻断；这不代表完整适配器、全调用链、可安装或 RELEASE_READY。

Result: **OFFLINE_SCOPED_REVIEW_PASSED**. Independent review of five changed files and failure cleanup paths found no new confirmed actionable blockers in scope. This does not approve the complete adapter/call chain, installation or RELEASE_READY.

## 代码证据 / Code evidence

run_tree 要求非空 assert_live 可调用，且仅接受返回值严格为 True；初始检查在创建子进程之前。Windows 子进程以 suspended 创建、加入 Job 后，在 resume 前再次检查；运行循环由调用主线程检查，异常进入已有 Job 树终止、存活计数及输出 reader 清理路径。失权不转换成成功，不释放维护权。正常返回还需在实际树清理完成后重新校验。没有 callback 的旧调用仍沿原监督路径。

run_tree validates a supplied assert_live callback and requires the exact return value True. Initial checks precede child creation. Windows creates the child suspended, assigns its Job, checks again before resume, and checks on the calling thread during execution. Failure follows the existing Job-tree termination, active-count and output-reader cleanup path; it cannot return success or release maintenance. Success additionally requires a fresh check after actual tree cleanup. Legacy callers without callbacks retain the original supervision path.

session.process_guard 固定完整 context、target/source/manifest/action，并要求共享 marker 与 session 均有效、最后阶段严格为 INSTALL_INTENT；上下文改变、UNKNOWN 或交接后的旧会话不能继续监督为有效。主线程回调兼容 SQLite connection 的线程约束。测试编排仅把既有 process_job 测试模块加入 host 组，未放松开发门禁。

session.process_guard binds the full context and target/source/manifest/action, requires held shared authority, and strictly requires INSTALL_INTENT. Context changes, UNKNOWN and handed-off old sessions cannot remain valid. Calling-thread checks respect SQLite connection affinity. The runner only adds the existing process-job test module to its host group without weakening development gates.

## 独立验证 / Independent validation

固定 SHA 后独立执行 `python -m unittest autonomy.test_process_job test_publisher_install_maintenance -q`：**27 项，5.865 秒，0 失败/错误/跳过**。覆盖旧清理失败与输出/超时行为、启动前严格拒绝、运行中失权清理实际子孙进程、主线程执行检查、session/context 门禁和失败后 marker/墓碑保留。

After pinning the SHA, independently ran the command above: **27 tests, 5.865 seconds, zero failures/errors/skips**. Coverage includes legacy cleanup failures/output/timeouts, strict prelaunch denial, real descendant cleanup on authority loss, calling-thread checks, session/context gates and retention of marker/tombstones after failure.

supervised session 测试通过 _transition(UNKNOWN) 模拟活跃阶段失效，并非实际 RECOVERY_ADMITTED 父子交接；实际 handoff 逻辑由既有独立测试覆盖，本轮未把两者混称。

The supervised-session test simulates active-session invalidation with _transition(UNKNOWN), not an actual RECOVERY_ADMITTED handoff. Existing separate tests cover handoff; the two evidence types are not equated.

另做两项隔离定向探针：第二次检查（Windows resume 前）返回 False，实际子进程 marker 未生成且 cleanup_verified=True；包装实际 _windows_job 的成功返回后才置位，使 callback 只在最终已清理阶段拒绝，确认仍抛 ProcessAuthorityLost 且 cleanup_verified=True。后一探针明确区分最终检查与运行中检查，不把原立即退出测试的时序当作最终检查证据。

Two additional isolated probes confirmed denial at the second/pre-resume assertion leaves no child marker and verifies cleanup; a wrapper around the real _windows_job return then denied only after verified cleanup, producing ProcessAuthorityLost with cleanup_verified=True. The latter explicitly distinguishes the final check from an in-flight check rather than relying on timing of the immediately exiting child test.

## 边界与交付阻断 / Limits and delivery blockers

- 父进程 watchdog 是周期检查，不是子进程每次文件/SCM/ACL mutation 的同步 IPC 权限桥。

  The parent watchdog polls authority; it is not a synchronous IPC authority bridge for each child file/SCM/ACL mutation.

- 原发布器支持入口到受控安装进程的完整正式适配、真实进程身份及独立目标/SCM/ACL final verifier、seal/授权仍待闭合。

  The supported publisher-to-installer adapter, real process identity, independent target/SCM/ACL final verifier and seal/authorization remain incomplete.

- 本次实测为 Windows；POSIX 分支仅静态审核，未在 POSIX 环境运行。

  Actual execution was on Windows; the POSIX path received static review only.

所有实测仅临时文件、隔离 Python 子进程/Job 与临时 SQLite；未操作生产服务/ACL、生产数据库或现场发布器。源码未由审核者修改。逐文件实际字节和 Git blob SHA-256 见 JSON，均与固定提交匹配（仅换行归一化）。保持 `allow_install=false; allow_dispatch=false; SMTP=false; RELEASE_READY=false`。

All execution used temporary files, isolated Python processes/Jobs and temporary SQLite. No production services/ACLs/database/site publisher were operated on, and the reviewer changed no source. JSON records actual-byte and Git-blob SHA-256 values matching the fixed commit after newline normalization. Keep installation, dispatch, SMTP and RELEASE_READY false.
