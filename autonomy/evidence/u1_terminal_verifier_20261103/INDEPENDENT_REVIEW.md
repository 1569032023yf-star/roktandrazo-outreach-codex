# 独立离线范围审核 / Independent offline scoped review

固定源码 / Pinned source: `6ff9f61653957eec06887030b17333153e80d1c5`
比较基线 / Baseline: `f1b88420304484c2cc5d99e4afb9b02477786c92`

结论：本次增量在声明的受信内部接口与离线范围内未发现新增阻断，状态为 **OFFLINE_SCOPED_REVIEW_PASSED**。`RELEASE_READY=false`、`allow_install=false`、`FULL_CHAIN_VERIFIED=false`。这不是完整调用链、生产安装或生产验收批准。

Conclusion: No new blocking issue was identified in this increment within its declared trusted-internal-interface and offline scope. Status is **OFFLINE_SCOPED_REVIEW_PASSED**. `RELEASE_READY=false`, `allow_install=false`, and `FULL_CHAIN_VERIFIED=false`. This does not approve the complete call chain, production installation, or production acceptance.

## 源码审核 / Source inspection

逐一审核基线到固定源码的十个变动文件。核验器独立读取实际文件与凭据，检查精确新旧自有文件集合、receipt 的 source/manifest/operation 绑定、备份/内容摘要、文件日志 sequence/previous 链、暂存残留、根身份和回滚目录清理。主机日志绑定目标 operation/manifest，PREPARED 现在先记录根身份和升级前 DACL；终态仅接受 COMMITTED 或 ROLLED_BACK，recover/rollback 仅接受后者。升级回滚验证批准旧 receipt、旧文件、旧根身份和原 DACL；首装回滚要求服务和两个根全部 ABSENT。

All ten changed files were inspected against the baseline. The verifier reads actual files and receipts, verifies exact old/new owned-file scope, source/manifest/operation receipt binding, backup/content hashes, the file-journal sequence/previous chain, staging artifacts, root identity and directory cleanup. Host records bind the target operation and manifest. PREPARED now records root identities and pre-upgrade DACLs before mutation. Only COMMITTED or ROLLED_BACK is terminal, with recover/rollback restricted to the latter. Upgrade rollback verifies the independently approved previous receipt, old files, root identities and original DACLs; first-install rollback requires the service and both roots to be ABSENT.

核验不信任安装器 stdout。两次带随机 nonce 的观察及日志摘要/实际文件重读用于拒绝不稳定结果；两次进程终止证明必须相同。证据先写入同一维护会话的 FINAL_VERIFY_INTENT，再交由原会话释放状态机处理。拒绝转为 UNKNOWN 并保留维护权。正式 observer 对固定路径进行 reparse、审计目录所有者/ACE、日志句柄 ACL/摘要、SCM 与根 DACL 只读观察。新增脚本纳入 manifest 哈希与固定源码构建检查；公开 Execute 的维护门禁保持关闭。

Installer stdout is not trusted. Two nonce-bound observations, journal-digest checks and actual-file rereads reject unstable results; both process-quiescence proofs must match. Terminal evidence is durably recorded in the same maintenance session before the existing release state machine proceeds. Refusal leaves UNKNOWN and retains maintenance ownership. The observer reads fixed paths, rejecting reparses and untrusted audit owners/ACEs while collecting journal handle ACLs/digests, SCM and root DACLs. The added script is included in manifest hashing and source-pinned build checks; the public Execute maintenance gate remains closed.

注意：只有文件事务日志具 sequence/previous 哈希链。主机、ACL、State 创建日志检查实际原始字节摘要、受信存储及所需绑定/终态，并非全部日志都具哈希链。外部管理员并发修改不由此离线核验器提供跨文件系统/SCM/SQLite 原子性。

Only the file transaction journal has a sequence/previous hash chain. Host, ACL and state-create logs use actual-byte digests, trusted storage and required binding/terminal checks; they do not all have hash chains. This offline verifier does not supply cross-filesystem/SCM/SQLite atomicity against external administrative changes.

## 独立实测 / Independent execution

`python -m unittest test_install_verifier test_maintenance_control test_disabled_host_package -v`：**22/22 通过，68.042 秒**。包括真实临时文件、真实协调器与 stdio 维护桥、隔离 SQLite 会话、首装→升级→升级回滚→首装回滚、CODE_CREATE_VERIFIED 后真实子进程退出再显式补偿、文件/receipt/暂存/截断日志拒绝、未知进程拒绝、ACL/SCM/nonce 不匹配拒绝及包/公开门禁回归。真实 Windows PowerShell/.NET 只读观察器在临时目录验证不可信 audit owner 拒绝；未修改执行策略。

**22/22 tests passed in 68.042 seconds** using the command above. Coverage includes actual temporary files, the real coordinator and stdio authority bridge, isolated SQLite sessions, install→upgrade→upgrade rollback→first-install rollback, a real child exit after CODE_CREATE_VERIFIED followed by explicit compensation, mismatched file/receipt/staging/torn-journal refusal, unknown-process refusal, ACL/SCM/nonce mismatch refusal, and package/public-gate regression. The real Windows PowerShell/.NET read-only observer rejected an untrusted temporary audit owner; no execution policy was changed.

另外独立增加三个运行时探针（未修改产品或测试源码）：实际文件日志 previous 摘要篡改→FILE_JOURNAL_CHAIN；第二次观察服务变为 Running→UNSTABLE_OBSERVATION；两次进程 identity 摘要变化→PROCESS_IDENTITY_CHANGED。三者均实际触发 STOP_AND_PRESERVE，维护标记保留且会话 UNKNOWN。

Three additional runtime probes were executed without modifying product or test source: actual file-journal previous-digest tampering→FILE_JOURNAL_CHAIN; the second observation changing service state to Running→UNSTABLE_OBSERVATION; changed process-identity digests→PROCESS_IDENTITY_CHANGED. All three produced STOP_AND_PRESERVE, retained the maintenance marker and left the session UNKNOWN.

## 限制与交付阻断 / Limits and delivery blockers

正式 pinned command 与持久进程实例身份证明适配器尚未完成；observer/confirm_stopped 是受信内部接口，当前不能由任意请求提供。SCM/ACL 成功路径仍使用隔离替身，不能称为真实生产服务与 ACL 成功验收。未操作生产目录、ACL、服务、Inventory 或生产数据库。全部安装/发布门禁保持 false。

Formal pinned-command and durable process-instance identity-proof adapters remain incomplete. Observer/confirm_stopped are trusted internal interfaces and cannot be supplied by arbitrary requests. SCM/ACL success paths still use isolated doubles and do not establish real production service/ACL acceptance. No production directory, ACL, service, Inventory or production database was operated on. All installation/release gates remain false.

十个变动文件的实际工作区 SHA256 与固定 Git blob SHA256 见同目录 INDEPENDENT_RESULT.json；读取前后 HEAD 均为上述固定源码，受审核文件无 tracked diff。仅允许 CRLF/LF 工作区规范化差异。

Actual working-tree and pinned Git-blob SHA256 values for all ten changed files are recorded in INDEPENDENT_RESULT.json. HEAD was the pinned revision before and after execution, with no tracked diff in reviewed files; only CRLF/LF normalization is permitted.
