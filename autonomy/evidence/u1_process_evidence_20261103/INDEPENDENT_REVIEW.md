# 独立离线范围审核 / Independent offline scoped review

固定源码 / Source: `2db72ad5a016d24907e60c4481ffba1b870c959d`
基线 / Baseline: `bb2f6aabc8e955491e4ade0b75f4f3c512efc297`

结论：本轮增量未发现新增阻断，**OFFLINE_SCOPED_REVIEW_PASSED**。全部生产安装与发布门禁保持 false；这不是完整调用链或生产安装批准。

Conclusion: No new blocking issue was found in this increment. **OFFLINE_SCOPED_REVIEW_PASSED**. All production installation and release gates remain false; this is not full-chain or production installation approval.

## 源码审核 / Code inspection

审核五个变动文件以及已有维护会话/终态核验接口。Windows 路径先持久 LAUNCH_INTENT（命令摘要、随机 Global Job 名称、supervisor PID 与创建 FILETIME），再创建配置 kill-on-close 的命名 Job。CreateProcess 使用明确 executable、挂起及显式 HANDLE_LIST；AssignJob 成功后读取真实 child PID/creation FILETIME/image 并持久 CONTAINED，持久回调失败不得 Resume。Resume 前仍检查实时维护权。

Inspected all five changed files and the existing maintenance-session/terminal-verifier interfaces. The Windows path first persists LAUNCH_INTENT containing the command digest, random Global Job name, supervisor PID and creation FILETIME, then creates a named kill-on-close Job. CreateProcess uses an explicit executable, suspension and HANDLE_LIST. Only after successful Job assignment are the actual child PID, creation FILETIME and image read and durably recorded as CONTAINED. Failure of that durable callback prevents Resume. Live maintenance authority is still checked before Resume.

原有失败路径继续终止 Job、读回 ActiveProcesses=0、等待 child、关闭句柄并完成输出 reader；只有这些清理没有错误时才尝试持久 STOPPED。超时或其他原始错误仍上抛，不能因 STOPPED 而自动释放。SQLite 凭据绑定会话、命令、image、sequence 和 previous SHA；禁止重复/跳步/实例变化。confirm_stopped 要求三条完整记录及当前维护权。reconcile 不启动或终止进程；两条记录时必须证明原 supervisor incarnation 不再活跃、命名 Job 不存在、原 child incarnation 已死，才记录 reconciled STOPPED。访问拒绝、无法判断、LAUNCH-only 均停保留。维护会话交接后的旧会话不能新增 STOPPED。

Existing failure paths still terminate the Job, verify ActiveProcesses=0, wait for the child, close handles and finish output readers. STOPPED is attempted only when those cleanup steps report no error. Timeout or another primary error still propagates and STOPPED does not automatically release ownership. SQLite evidence binds session, command, image, sequence and previous SHA and rejects replay, skipped phases and identity changes. confirm_stopped requires all three records and current maintenance ownership. Reconcile neither launches nor terminates a process: with two records it requires the original supervisor incarnation to be gone, the named Job object to be absent and the original child incarnation to be dead before recording reconciled STOPPED. Access denial, uncertain observations and LAUNCH-only remain stopped and preserved. A handed-off old session cannot append STOPPED.

## 独立实测 / Independent tests

命令 / Command: `python -m unittest test_install_process autonomy.test_process_job test_install_verifier -v`

**26/26 通过，89.160 秒，0 failures、0 errors。** 新增六项测试使用真实 Windows Job 与隔离 SQLite；覆盖身份和 STOPPED 落盘、超时仍保留维护权、CONTAINED 已提交后 Resume 前异常无子进程动作、LAUNCH-only 未知禁止重放、真实 supervisor 死亡与只读恢复，以及实际协调器首装/升级/两次回滚接入真实进程终止证明。原 process 与终态核验测试同时回归。

**26/26 passed in 89.160 seconds, with zero failures and errors.** Six new tests use real Windows Jobs and isolated SQLite. They cover durable identity/STOPPED evidence, retained maintenance on timeout, failure after the CONTAINED commit but before Resume with no child action, LAUNCH-only uncertainty without replay, real supervisor death and read-only reconciliation, and the real coordinator performing first install/upgrade/both rollbacks with actual process-quiescence proof. Existing process and terminal-verifier regressions were also run.

另独立执行四个探针，未改产品/测试源码：STOPPED 写入前注入失败后仅两条凭据，confirm_stopped 拒绝且会话 UNKNOWN/维护权保留；原 supervisor 仍活时 reconcile 拒绝；不同命令重新打开同一凭据触发 JOURNAL_BINDING；重复真实父进程死亡场景并额外对实际孙进程 PID 读回终止状态，确认孙进程已终止。

Four additional probes were run without modifying product/test source: failure before STOPPED insertion leaves two records and confirm_stopped refuses while the session remains UNKNOWN and ownership held; reconciliation refuses while the original supervisor lives; reopening evidence with a different command triggers JOURNAL_BINDING; repeating real supervisor death and independently reading the actual grandchild PID confirms its termination.

## 范围限制 / Scope limitations

正式固定命令/package 身份及 auth/seal 授权适配器仍未完成。lifecycle/record 是受信内部接口，不是接受任意调用者自报安全终止的公共入口。成功路径的 SCM/ACL 观察仍为隔离替身，不能据此宣称真实生产服务/ACL 验收。LAUNCH-only 缺失 child identity 时保留 UNKNOWN；这不能证明 CreateProcess 与 AssignJob/CONTAINED 之间突然退出时没有挂起遗留进程，也不得自动重放。未修改生产 ACL、服务、目录、数据库、Inventory 或执行策略。

Formal pinned-command/package identity and auth/seal adapters remain incomplete. Lifecycle/record are trusted internal interfaces, not public acceptance of arbitrary callers' termination claims. Successful SCM/ACL observations remain isolated doubles and do not establish real production service/ACL acceptance. LAUNCH-only without child identity remains UNKNOWN; it does not prove absence of a suspended orphan if death occurs between CreateProcess and AssignJob/CONTAINED and must not be replayed automatically. No production ACL, service, directory, database, Inventory or execution policy was modified.

五个变动文件的实际 SHA256 与固定 Git blob SHA256 记录于 INDEPENDENT_RESULT.json。执行前后 HEAD 等于固定源码，受审核文件无 tracked diff，CRLF/LF 规范化后与固定 blob 完全匹配。`RELEASE_READY=false`、`allow_install=false`、`FULL_CHAIN_VERIFIED=false`。

Actual working-tree and pinned Git-blob SHA256 values for the five changed files are recorded in INDEPENDENT_RESULT.json. HEAD matched the pin before and after execution; reviewed files had no tracked diff and matched pinned blobs after CRLF/LF normalization. `RELEASE_READY=false`, `allow_install=false`, `FULL_CHAIN_VERIFIED=false`.
