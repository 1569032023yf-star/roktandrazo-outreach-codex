# WorkBuddy 通道连接独立核验 / Independent WorkBuddy Channel Connection Verification

日期 / Date: 2026-10-15 (Asia/Taipei)。状态 / State: CHANNEL_CONNECTED_PREFLIGHT_PASSED。尚未部署 / Not deployed at this record's creation.

已读取本地未同步的 DEPLOY_CHANNEL_ACCEPTANCE_REPORT.md 和 CODEX_ENTRYPOINT.md，并独立核实实际进程、源码、配置、监听、凭据身份及请求结果。未将报告自述当作实际连接证明。桥接为回环 HTTP，凭据来自 Windows 凭据管理器，全程只留在内存；没有修改策略、权限、凭据或隔离变量。

The local unsynchronized DEPLOY_CHANNEL_ACCEPTANCE_REPORT.md and CODEX_ENTRYPOINT.md were read, followed by independent verification of the running process, source, configuration, listener, credential identity, and requests. Report assertions were not treated as connection proof. The bridge uses loopback HTTP and an in-memory credential read from Windows Credential Manager. No policies, permissions, credentials, or isolation variables were changed.

| 核验项 / Check | 实际结果 / Actual result |
|---|---|
| 入口 / Endpoint | rokt-deploy-channel v1.0.0, 127.0.0.1:8791 only |
| 健康 / Health | HTTP 200; test_mode=false |
| 受限身份 / Restricted identity | 凭据指纹匹配；API 限定注册发布四操作；桥接使用既有 WorkBuddy 用户，不是独立低权限 OS 账户 / Matching credential fingerprint; API scoped to four registered-release operations; bridge uses existing WorkBuddy user, not a separate low-privilege OS account |
| 拒绝测试 / Rejection tests | 10/10 passed; missing/wrong credentials, command/file endpoint, traversal, unknown release, missing confirm, unknown status/rollback, wrong method |
| 实时 preflight / Live preflight | HTTP 200; 14/14 passed; 2026-10-15T10:39:57+08:00 |
| SMTP / SMTP | 0 |
| 发送任务 / Sending tasks | PreSend / Preflight / Outreach PAUSED, deleted=true |
| 正式运行 / Official run | ACTIVE; next run 2026-10-15 15:41:48 +08; no recent unfinished Inventory |
| 审计 / Audit | 本次调用包括拒绝均见本地审计 / Calls including denials confirmed in local audit |

### 发布固定值 / Release pins

```text
SOURCE_COMMIT = e1efb22023a37abae3d97bf78cb4ec80bc583bf4
RELEASE_ID = phase4a8s-safe50-continuous-discovery
TARGET = bd_orchestrator.py
BEFORE_SHA256 = 7afc4d7f6ac18e22bba7cc6a9ea2250dc6d6bafe92128c00c08252731bb2e969
AFTER_SHA256 = e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903
PATCH_SHA256 = 3c7ba8d9baf9c6c4e35ecd5cfa5ef91e87b949ef10abad560fe191f768714bda
MANIFEST_SHA256 = c89174c71fc3bc01ea8fe50d2826f63aa7fc3d68e46391069b3edbf89a613b18
EXECUTOR_SHA256 = 0f2b0840205266f85b225be9d8cf3ef335ba1723c98f699482835f52ddc283f6
BRIDGE_SHA256 = 7f30667a60c3425fb9f14c2e1b80a3babd84752164f947693de7133d8ffc0117
```

执行器和桥接的实测 SHA 与本地 WorkBuddy 验收报告一致；生产源 SHA 由实际授权 preflight 取得，并与固定 before 值一致。源码复核确认单文件、备份 fsync、原子替换、实际 Inventory 上海业务日锁协调、替换后 SHA 和回滚接口。功能测试仍须使用开发阶段验收；执行器的 targeted_tests_pass 仅语法和字节演练，不等于完整功能测试。preflight 允许写入通道审计及备份目录探针，但不写业务数据库或业务源码。

Measured executor and bridge hashes match the local WorkBuddy acceptance report. Production source SHA came from actual authenticated preflight and matches the pinned before value. Source review confirmed single-file scope, backup fsync, atomic replacement, actual Inventory Shanghai business-date lock coordination, post-replacement SHA, and rollback interface. Functional acceptance remains a development-stage requirement; executor targeted_tests_pass covers syntax and byte rehearsal, not the full functional suite. Preflight may write channel audit and a backup-directory probe, but does not write business databases or business source.

下一步：先同步此脱敏记录，再通过已核实入口部署；不得手动触发 Inventory。没有观测到部署后的正常运行前，不宣称产量或恢复。

Next: synchronize this sanitized handoff, then release through the verified entry point; never manually trigger Inventory. Do not claim yield or recovery before observing a normal post-release run.
