# 4A.8S 首次受控生产发布 / First Controlled Production Release

日期 / Date: 2026-10-15 (Asia/Taipei)。

**结果 / Result: DEPLOYED_AWAITING_SCHEDULED_VALIDATION**

## 实际发布 / Actual release

Codex 在独立连接与拒绝测试通过后，使用已存在的 rokt-deploy-channel 正式桥接完成发布。先前未推送的 WorkBuddy 本地交接内容已独立核实并于提交 01018e2 脱敏同步，然后才执行 apply。没有重新开发 SAFE50 补丁，没有用开发工作树覆盖生产，没有直接 CLI 执行生产执行器。

After independent connection and rejection checks, Codex released through the existing authorized rokt-deploy-channel bridge. The previously unsynchronized local WorkBuddy handoff was independently checked and sanitized in pushed commit 01018e2 before apply. The SAFE50 patch was not redeveloped; no whole-tree production overwrite or direct executor CLI was used.

```text
CHANNEL_ID = rokt-deploy-channel
RELEASE_ID = phase4a8s-safe50-continuous-discovery
SOURCE_COMMIT = e1efb22023a37abae3d97bf78cb4ec80bc583bf4
OPERATION_ID = op-20261015-104202-5ecde6
DEPLOY_STARTED_AT = 2026-10-15T10:42:02+08:00
DEPLOY_FINISHED_AT = 2026-10-15T10:42:04+08:00
TARGET = bd_orchestrator.py
BEFORE_SHA256 = 7afc4d7f6ac18e22bba7cc6a9ea2250dc6d6bafe92128c00c08252731bb2e969
BEFORE_BYTES = 30645
AFTER_SHA256 = e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903
AFTER_BYTES = 31552
BACKUP = backups/op-20261015-104202-5ecde6/bd_orchestrator.py.before.bak
STATUS = applied
```

发布前实时 preflight 14/14 通过；本次复跑功能定向测试 127/127 通过。单文件三个补丁块，LF 字节保留。执行器持有正式 Inventory 同键锁，备份 fsync 后重核 before-SHA，同卷临时文件 fsync、保留 DACL 并 os.replace，随后重核 after-SHA。Codex 另外只读重读实际生产目标及备份，SHA 和字节数分别完全匹配；通过 status 接口确认 applied。未执行真实业务回滚，保留已校验备份和回滚接口，必要时仍须重新通过安全门禁。

Immediate preflight passed 14/14 and the functional targeted suite was rerun with 127/127 passing. Scope was one file and three hunks with LF bytes preserved. The executor held the official Inventory's matching lock, fsynced and rehashed the before backup, fsynced a same-volume temporary file, preserved DACL, used os.replace, and verified after-SHA. Codex separately reread the actual production target and backup and confirmed exact hashes and sizes, then confirmed applied through status. No actual business rollback was performed; the verified backup and rollback interface remain available subject to fresh safety gates.

## 通道核验与发送冻结 / Channel checks and sending freeze

实际回环连接和凭据指纹匹配成功；10 项认证/越权/参数拒绝检查全部通过，并核实调用审计。接口限制为 preflight / apply / status / rollback；API 身份受限，桥接使用既有 WorkBuddy 用户，不宣称独立低权限 Windows 账户。执行器、桥接、补丁、清单 SHA 均与已核实交接一致。未输出或落盘 token，未修改凭据、执行策略、访问控制或开发隔离变量。

Live loopback connection and credential fingerprint matching succeeded. All ten authentication/authorization/argument rejection checks passed and calls were confirmed in audit. The API is restricted to preflight / apply / status / rollback. Its API identity is scoped while the bridge uses the existing WorkBuddy user; no separate low-privilege Windows account is claimed. Executor, bridge, patch, and manifest hashes match the verified handoff. No token was printed or persisted, and no credentials, execution policies, access controls, or development isolation variables were changed.

10:42:26 +08 再次通过桥接读取实时状态：SMTP=0，PreSend / Preflight / Outreach 均 PAUSED 且 deleted=true；运行锁已 released，无近期运行中的 Inventory。部署后 apply 方向 preflight 返回 409 是预期的重复应用保护：当前文件已是 after，不能再套用 before→after 补丁，不是生产运行故障。status 和直接只读 SHA 核验仍确认部署成功。

Live state was read again through the bridge at 10:42:26 +08: SMTP=0; PreSend / Preflight / Outreach are PAUSED with deleted=true; the run lock is released and no recent Inventory is running. Apply-direction preflight returning 409 after release is expected double-application protection: the file is already after and cannot accept the before→after patch again. It is not a production runtime failure. Status and direct read-only SHA checks confirm deployment success.

## 尚待正常计划验收 / Scheduled acceptance pending

唯一正式 Inventory 为 1784775229336，实时计划下次为 **2026-10-15 15:41:48 +08**。截至本次核验，该部署后的正常计划运行尚未发生。没有手动触发 Inventory，没有创建调度器。Provider 请求、新线索、新第一方邮箱、SAFE 净增长、查询族/分页推进和生产运行异常尚未取得部署后验收数据；不能用代码测试替代。

The sole official Inventory is 1784775229336, with its next live scheduled run at **2026-10-15 15:41:48 +08**. At verification time, that normal post-release run has not occurred. Inventory was not manually triggered and no scheduler was created. Post-release provider requests, new leads, first-party emails, net SAFE growth, query/page progress, and runtime exceptions remain unmeasured; code tests cannot substitute for production acceptance.

本地只读检查点 4a5g_state_checkpoint_20261015_094614.json 的观测时间为 09:44:28：V2 SAFE 独立组织=50，leads=1205，城市 ID=22，查询族完成=13、待处理=7，当日发送=0。该检查点早于发布，仅作为最后已观测基线，不冒充当前实时 SAFE。03:29 的旧运行及旧日志也不计作部署后验收。

The local read-only checkpoint 4a5g_state_checkpoint_20261015_094614.json was observed at 09:44:28: V2 SAFE unique organizations=50, leads=1205, city ID=22, query families completed=13/pending=7, and sends today=0. This predates release and is only the last observed baseline, not a current live SAFE count. The old 03:29 run and old logs do not count as post-release acceptance.

后续验收读取原有正常计划运行记录：SAFE≥50 时确有 Provider 请求；查询族或分页推进；单轮最多 3 页；无新增重复 Inventory 或代码异常；历史、MX、去重门禁保持。没有部署 4B.1G，没有操作 SAFE40/50 客户、发送授权或业务资格门禁。首次发布仅修改 bd_orchestrator.py；生产 DB 写入仅执行器协调运行锁，未直接修改客户记录。

For acceptance, read the existing normal scheduled run: actual provider requests at SAFE≥50, query or page progress, at most three pages per run, no added duplicate Inventory or code errors, and preserved history/MX/deduplication gates. 4B.1G was not deployed, and SAFE40/50 customers, sending authorizations, and qualification gates were not operated on. Only bd_orchestrator.py was released; executor production DB writes were limited to run-lock coordination, with no direct customer record edits.

## 最终字段 / Final fields

```text
CHANNEL_EXISTS = true
CODEX_CAN_CALL_CHANNEL = true
PREFLIGHT_PASSED = true (immediately before release / 发布前即时)
PRODUCTION_DEPLOYED = true
PRODUCTION_SHA_VERIFIED = true
NORMAL_INVENTORY_RUN_OBSERVED = false (after release / 部署后)
PROVIDER_REQUESTS_AFTER_DEPLOY = NOT_MEASURED
NEW_LEADS_AFTER_DEPLOY = NOT_MEASURED
NEW_FIRST_PARTY_EMAILS = NOT_MEASURED
CURRENT_SAFE = NOT_MEASURED
LAST_OBSERVED_SAFE = 50 (2026-10-15 09:44:28 +08; before release / 发布前)
SMTP_ENABLED = 0 (live bridge verified / 实时桥接核实)
EMAILS_SENT = 0 (by this task / 本任务)
ROLLBACK_AVAILABLE = true (verified production backup and interface; not executed / 已校验生产备份及接口；未实际回滚)
RESULT = DEPLOYED_AWAITING_SCHEDULED_VALIDATION
```

以后普通工程默认复用 docs/CONTROLLED_DEPLOYMENT_CHANNEL.md 中的正式入口，每次保留实时门禁，不再要求 WorkBuddy 人工接力部署。原始响应和凭据以外的本地测试证据保留于开发 output/channel_20261015/；公开交接仅包含脱敏结果。本报告已经双语、敏感信息、未完成事项、执行边界和下一步自检。

Future routine engineering defaults to the formal entry point in docs/CONTROLLED_DEPLOYMENT_CHANNEL.md, with live gates every time and no manual WorkBuddy deployment handoff. Raw responses and local test evidence excluding credentials remain in development output/channel_20261015/; public handoff contains sanitized results only. This report was checked for bilingual content, secrets, unfinished work, execution boundaries, and next actions.
