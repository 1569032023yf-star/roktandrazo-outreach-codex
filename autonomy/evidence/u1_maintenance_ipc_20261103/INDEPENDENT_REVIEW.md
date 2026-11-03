# 维护权 stdio IPC 独立范围审核 / Maintenance stdio IPC scoped review

固定源码 / Fixed source: `b4332e4e2144c36076849ecd5315eeae758ee56a`  
基线 / Baseline: `30284684317bf6310c2b1d8eea3f464c22da6fd4`

结论：**OFFLINE_SCOPED_REVIEW_PASSED**。本轮发现的一项已知失败后仍发 ACK 问题已关闭；最终固定源码未发现新增可确认阻断。此结论不代表完整现场调用链或正式安装适配完成，RELEASE_READY=false。

Result: **OFFLINE_SCOPED_REVIEW_PASSED**. The reported ACK-after-known-failure defect is closed, with no new confirmed actionable blockers in the final fixed source. This does not approve the complete site call chain or formal installer adapter; RELEASE_READY remains false.

## 代码与协议审核 / Code and protocol review

独立审查全部12文件改动及读线程、主线程授权、非阻塞 ACK、Windows 句柄继承、清理和包 pin 路径。请求严格限定 schema/字段/整数 sequence，重复键、错序/重放、超长、重叠、破损请求和错误绑定停止；只接受 handler 严格 True。session handler 在主线程核验 context、INSTALL_INTENT、实际动作与持久维护权。ACK 仅固定 sequence/held，不回显任意请求内容；不开放监听、命令或释放权限。

Reviewed all 12 changed files plus reader-thread/main-thread authority, nonblocking ACK, Windows handle inheritance, cleanup and package pins. The protocol restricts schema/fields/integer sequence and rejects duplicate keys, replay/order errors, oversized/overlapping/torn requests and binding errors. Only exact True authorizes an ACK. The session handler verifies context, INSTALL_INTENT, action and durable authority on the caller thread. ACKs contain fixed sequence/held fields, with no listener, command or release authority.

Windows 使用 suspended process、Job 和 STARTUPINFOEX HANDLE_LIST，仅继承本次 stdin/stdout/stderr；API 失败进入已有清理流程。ACK 写端非阻塞，短写/满管道异常停止。公开 Execute hard gate 保持关闭；包构造、清单依赖和构建源码检查包含新 PS helper。旧无控制流调用仍通过进程回归测试。

Windows uses a suspended process, Job and STARTUPINFOEX HANDLE_LIST for only this invocation's stdin/stdout/stderr; API failures enter existing cleanup. Nonblocking ACK writes stop on short writes/full pipes. The public Execute hard gate stays closed; package manifests/dependencies and build-source checks include the new helper. Legacy non-control calls pass process regressions.

## 已关闭发现 / Closed finding

**P1 — ack_after_known_protocol_failure — CLOSED**：在49a36e7已确定性复现：reader收到seq0和重叠seq1后记录ControlProtocolError，但下一poll仍发seq0 held=true。最终版本采用持久sticky failure；Capture与control共享锁，reader失败与ACK发送在同一锁下线性化；handler在锁外执行，发ACK前重新检查failure，tick也先拒capture.failure。已知失败、handler期间重叠、handler期间capture错误均有零ACK负例。锁释放与异常路径未发现新的死锁。

**P1 — CLOSED**: In 49a36e7, seq0 followed by overlapping seq1 deterministically set a reader error but still allowed a seq0 held ACK. The final source latches failure, shares the Capture/control lock, runs handlers outside it, rechecks failure under that lock before ACK, and checks capture failure before polling. Zero-ACK tests cover known failure, overlap during handler execution and capture failure during the handler. Exception/lock paths show no new confirmed deadlock.

## 独立验证 / Independent validation

固定SHA后独立执行 `python -m unittest test_maintenance_control autonomy.test_process_job test_publisher_install_maintenance test_disabled_host_package -q`：**43项，21.565秒，0失败/错误/跳过**。覆盖真实PS协调器经IPC在隔离夹具完成COMMITTED、FILES_VERIFIED后拒绝时不创建服务/不释放marker、协议错误、非读child、Job清理、句柄隔离与API故障注入、维护会话及包构造。SCM/ACL仍是替身，fixture verifier不是生产final verifier。

After pinning, independently ran the command above: **43 tests, 21.565s, zero failures/errors/skips**. Coverage includes real PowerShell coordinator RPC through isolated COMMITTED, denial after FILES_VERIFIED without service creation/release, protocol rejection, nonreading children, Job cleanup, handle isolation/API failure injection, sessions and packaging. SCM/ACL are doubles; the fixture verifier is not production final verification.

另两项在同一固定源码上的独立探针：真实无人读取ACK管道在145次ACK后0.002秒以ControlProtocolError停止，无阻塞；监督父在收到真实PS请求后、ACK前突然exit44，子PS因Job关闭退出，后续危险marker未生成。它们分别验证管道填满和父死，不以一般超时测试代替。

Two additional probes on the same fixed source: an actual unread ACK pipe stopped at 145 ACKs in 0.002s with ControlProtocolError; a supervisor exited 44 after a real PS request but before ACK, the Job-contained child died, and its post-ACK marker was absent. These directly test pipe saturation and parent death rather than inferring them from generic timeout behavior.

旧49a36e7及修改中的工作树成绩不作为最终pin验收。所有源码实际字节与Git blob SHA-256见JSON，最终12文件均匹配固定提交（仅换行归一化）。

Old-source and changing-worktree runs are not final-pin acceptance evidence. JSON records actual-byte/Git-blob SHA-256; all 12 final files match the fixed commit after newline normalization.

## 边界与交付阻断 / Limits and delivery blockers

- 真实 IPC 已连接隔离协调器的 AssertHeld 边界；不能推导每个 helper 内部文件/ACE 操作均单独 RPC，也不构成维护数据库事务与文件系统副作用的原子提交。

  Real IPC connects the isolated coordinator AssertHeld boundaries; it does not prove a separate RPC for every internal helper file/ACE action or atomic commit across maintenance DB and filesystem effects.

- 正式命令构造、固定身份/进程适配器、独立目标/真实 SCM/ACL final verifier 和 seal/部署授权仍未完成。

  Formal command construction, pinned identity/process adaptation, independent target/real SCM/ACL final verification and seal/deployment authorization remain incomplete.

- 本次真实执行仅 Windows 临时目录/SQLite/Job；POSIX 分支仅静态审查；SCM/ACL 及最终核验器仍是隔离替身。

  Actual execution is Windows temporary files/SQLite/Jobs only; POSIX received static review. SCM/ACL and final verification remain isolated fixtures.

本轮未写生产数据库、操作生产服务/ACL或修改现场发布器/Inventory。审核者未修改实现。保持 `allow_install=false; allow_dispatch=false; SMTP=false; RELEASE_READY=false`，不得据此开始正式安装或无人值守生产验收。

No production DB, service/ACL, site publisher or Inventory mutation occurred; the reviewer changed no implementation. Keep installation, dispatch, SMTP and RELEASE_READY false. This review does not authorize installation or unattended production acceptance.
