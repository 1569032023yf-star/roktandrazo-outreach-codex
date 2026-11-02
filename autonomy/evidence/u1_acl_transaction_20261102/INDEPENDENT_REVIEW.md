# U1 ACL 事务独立审核 / Independent ACL transaction review

日期 / Date: 2026-11-02（Asia/Taipei）  
审核者 / Reviewer: independent `acl_review` agent  
源码提交 / Source commit: `0db17b51d8ce464f1f57dd5ef40d0df266dcf3f8`  
结论 / Verdict: **SCOPED_REVIEW_PASSED=true**；仅离线 ACL 事务范围 / offline ACL transaction scope only.

中文：已独立阅读最终安装器差异、完整事务助手、打包逻辑和故障注入测试，并独立执行下述测试。最终范围内没有未关闭的阻断发现。接受 Comment `6520202418` 的非对称裁决：代码根保留继承并增加服务 RX；状态根保护 DACL，仅保留 SYSTEM、Administrators FullControl 和服务 Modify。此结论不授予安装或生产执行权限。

English: Independently inspected the final installer diff, complete transaction helper, packaging logic and fault-injection tests, then independently executed the tests below. No blocking findings remain within the final reviewed scope. Accept the asymmetric ruling in Comment `6520202418`: preserve code-root inheritance and add service RX; protect the state DACL with SYSTEM/Administrators FullControl and service Modify only. This verdict grants no installation or production authority.

## 失败路径检查 / Failure-path inspection

中文：检查了 PREPARED 中两个修改前 DACL、目标 DACL、operation_id 与 manifest 绑定；每次 APPLY_INTENT 持久化后才修改，每一步回读精确 SDDL；失败时先核对两个实际状态，再以 ROLLBACK_INTENT 记录逆序补偿；恢复只允许 before/after 已知状态，不重放 APPLY；截断日志、错误 manifest 和意外 ACL 均拒绝写入。CreateNew 防止旧操作自动重试，独占文件句柄保护日志，WriteThrough 加 Flush(true) 为持久化边界。打包 manifest 包含新助手的字节散列，安装器固定该文件句柄后才加载助手。

English: Verified that PREPARED binds both before/target DACLs, operation_id and manifest; each APPLY_INTENT is persisted before mutation and each result receives exact SDDL readback. Compensation prechecks both observations and records reverse-order ROLLBACK_INTENT operations. Recovery permits only known before/after observations and never replays APPLY. Truncated journals, wrong manifests and unexpected ACLs refuse writes. CreateNew prevents automatic old-operation retry, an exclusive file handle protects the journal, and WriteThrough plus Flush(true) defines durability boundaries. The package manifest hashes the new helper, which the installer pins before loading.

中文：初审提出的三个问题已关闭：(1) 日志文件自身可能保留不可信显式 ACE：现通过已打开句柄校验 owner/ACE；(2) 对已完成或在用安装执行 ACL 补偿：现拒绝完成凭据，并要求存在的服务为同一账户、映像、Disabled、Stopped；(3) 状态根先继承 ProgramData Users 写权限会产生子对象预植窗口：现先持久记录创建意图，再使用 SYSTEM/Admin-only DACL 原子创建，不暴露可写中间状态。测试清理曾因 .NET 只写入标记修改的 ACL 而失败，已修复并通过最终独立复测。

English: Three initial findings were closed: (1) an existing journal file could retain an untrusted explicit ACE; owner/ACEs are now checked through its open handle; (2) compensation could affect a completed or active installation; completion receipts are now rejected and any existing service must match account/image and be Disabled/Stopped; (3) initially inheriting ProgramData Users write rights exposed a child-object preplanting window; creation intent is now durable before atomic SYSTEM/Admin-only directory creation. A test cleanup failure caused by .NET writing only modified ACL sections was repaired and passed final independent retesting.

## 实测结果与限制 / Executed evidence and limits

- 主组合 / Main combination: **39 tests, 37.646 s, exit 0, OK**.
- 配置生成兼容测试 / Provision compatibility module: **2 tests, 1.954 s, exit 0, OK**.
- 命令和 SHA 机器证据 / Commands and SHA evidence: `INDEPENDENT_TEST_RESULT.json`.

中文：真实 Windows 临时目录测试覆盖双根成功、第二步写入失败、首步回读后退出、第二步意图后退出、第二步写入后回读前退出、回滚中退出、回滚失败后显式恢复、持久化失败、未知 ACL、截断日志、错误 manifest、禁止重复操作、原子安全创建及恢复准入。使用当前用户 SID 代替真实服务 SID；非提权事务测试仅替换审计根和日志文件信任门禁，ACL 读写与持久日志为真实系统操作。信任门禁另有真实普通用户目录/文件拒绝测试和合成 SYSTEM/Admin 正反例。没有执行真实服务注册、启动、生产 ACL、生产目录创建、Inventory 修改或生产数据库写入；未核实实际生产审计目录或整机断电持久性。

English: Real Windows temporary-directory tests cover both-root success, second-step failure, exits after first readback/before second write/after second write before readback, interruption during rollback, rollback failure followed by explicit recovery, persistence failure, unexpected ACLs, truncated journals, wrong manifests, no replay, atomic secure creation and recovery admission. The current user SID substitutes for the real service SID. Unprivileged transaction fixtures replace only audit-root/journal trust gates; DACL I/O and durable journals use real OS operations. Separate tests reject real user-owned directories/files and exercise synthetic SYSTEM/Admin positive/negative gates. No real service registration/start, production ACL, production directory creation, Inventory change or production database write occurred. Actual production audit-root readiness and whole-machine power-loss durability were not established.

中文：State Root 创建过程的独立日志保留 ABSENT 与目标 DACL；如创建结果或日志未知，应保留证据并人工核对，不删除目录或自动重试。安全恢复范围是 ACL 补偿，不代表完整安装器的注册、文件发布或业务验收均已事务化。下一步仅合并此离线候选与双语 checkpoint/发布清单；生产安装仍需独立正式门禁，不在本轮授权内。

English: The separate State Root creation journal retains ABSENT and target DACL. Unknown creation/journal outcomes require evidence preservation and explicit reconciliation, not directory deletion or automatic retry. Recovery here means ACL compensation, not a claim that registration, file publication or business acceptance is fully transactional. Next, incorporate this offline candidate into the bilingual checkpoint/release manifest. Production installation still requires separate formal gates and is outside this round's authority.

`PRODUCTION_DEPLOYED=false`; `PRODUCTION_ACCEPTED=false`; `RELEASE_READY=false`; `allow_install=false`.

## 固定文件 SHA-256 / Pinned file SHA-256

| 文件 / File | SHA-256 |
|---|---|
| `autonomy/windows/Install-DisabledHost.ps1` | `306a89462050375130460827d72a4bb687ee3d87c6e2bbbbb9a855c5e21b8483` |
| `autonomy/windows/Acl-Transaction.ps1` | `a3fb4ab1fa251bc80e9d6a9f682b6efa48a628ed96a2253492d89af4ccfe8057` |
| `autonomy/disabled_host_package.py` | `f5591d625d98be8a8043e24f59ed7c08fb13a605761188588aa0e098b87b8625` |
| `test_windows_acl_transaction.py` | `1fd4f9865d2d9aea040b06e8ee670ded5ee82cac8c59501677d5194790b67d0c` |
| `test_disabled_host_package.py` | `dd103ed6769bcf3d763904cdd4b679204061394f0790ce97bd03001fc03684ed` |
| `test_u1_provision.py` | `f116689bc05081d08daf526893cff70709d6fc0f48ed1d3c7fb6593631a4138f` |

中文：报告自检通过：中英双语、实际结果、未执行事项、限制、风险、下一步、状态边界齐全；未包含凭据。  
English: Report self-check passed: bilingual content, actual results, unexecuted items, limitations, risks, next steps and scoped status are included; no credentials are present.
