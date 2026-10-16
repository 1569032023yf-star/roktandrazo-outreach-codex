# PHASE 4A.8S 部署后验收记录 / Post-deployment acceptance record

## 结论与证据范围 / Conclusion and evidence scope

已部署，生产实时文件指纹正确；正式生产效果验收尚未完成。2026-10-16 17:54:39 +08 通过原有 rokt-deploy-channel 实测，未重复 apply、未回滚、未手动启动 Inventory。只有发布接口，没有日志或 MX 控制探针权限。当前没有可调用的 WorkBuddy 消息入口；[一次性只读验收请求](WORKBUDDY_READONLY_ACCEPTANCE_REQUEST_20261016.md)已准备，未声称送达、执行或收到回报。后续发布仍由 Codex 负责。

Deployment is confirmed and the live production file fingerprint is correct; formal production-effectiveness acceptance is incomplete. The original rokt-deploy-channel was queried at 2026-10-16 17:54:39 +08, without reapplying, rolling back, or manually starting Inventory. The channel exposes release operations only, without logs or the MX control probe. No callable WorkBuddy messaging entry point is available. A [one-time read-only acceptance request](WORKBUDDY_READONLY_ACCEPTANCE_REQUEST_20261016.md) is prepared; delivery, execution, and receipt of a response are not claimed. Codex retains ownership of subsequent releases.

## 正式通道实时结果 / Live results through the official channel

| 项目 / Item | 本次结果 / Current result | 证据与限制 / Evidence and limit |
|---|---|---|
| 历史发布 / Historical release | `op-20261015-104202-5ecde6` = `applied` | status HTTP 200；完成时间 / finished at `2026-10-15T10:42:04+08:00` |
| 当前文件 SHA / Current file SHA | `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903` | 本次 preflight `source_sha_matches.actual`，不是旧操作 after / This preflight's actual value, not historical operation after |
| 指定 Inventory / Designated Inventory | `1784775229336` = `ACTIVE` | 下一次 / next `2026-10-16 23:10:38 +08`；接口不能证明全局唯一 / endpoint cannot prove global uniqueness |
| SMTP | `0` | 本次实时 / live preflight |
| PreSend / Preflight / Outreach | 全部 / all `PAUSED`, `deleted=true` | 本次实时发送任务门禁 / live sending-task gate |
| 可执行发送授权 / Executable send authorization | `0` | 本次实时门禁 / live gate |
| 当前运行 / Current execution | `running=[]`；锁 / lock `released` | 当前快照正常，不代表历史无冲突 / healthy snapshot, not a historical conflict audit |
| 旧未结束记录 / Old unfinished rows | `6`，最早 / oldest `2026-07-23 02:54:03` | 通道标记为超过 2h TTL 的陈旧残留，不能当作本次新异常 / channel labels these stale residue beyond 2h TTL, not new release failures |

通道最初出现 WinError 10061，现场无监听和桥接进程。核实 bridge/executor SHA 未变后，按原入口包启动同一 pythonw 桥接，PID 42100，隐藏窗口，无提权或配置修改。仅调用 GET healthz、POST status、POST preflight。凭据只在内存中读取，指纹一致；不输出凭据。没有直接调用执行器或查询生产数据库。

The initial connection returned WinError 10061, with no listener or bridge process. After checking unchanged bridge/executor hashes, the same documented pythonw bridge was started hidden as PID 42100, without elevation or configuration changes. Calls were limited to GET healthz, POST status, and POST preflight. The credential was read in memory with a matching fingerprint and was not disclosed. The executor was not directly invoked and production databases were not queried.

部署后 preflight 返回 HTTP 409、9/14 门禁通过，因为它仍要求部署前的 SHA；源指纹和依赖候选的四项检查因补丁已应用而不通过。不能把该结果称作新的部署前全门禁通过，也不能把它当作生产运行故障。此次实时 after-SHA 与固定发布目标独立比对一致。

Post-deployment preflight returned HTTP 409 with 9/14 gates passing because it still requires the before-SHA. The source fingerprint and four candidate-dependent checks fail because the patch is already applied. This is neither a new full pre-deployment pass nor evidence of a runtime failure. The current actual SHA independently matches the pinned after-SHA.

## WorkBuddy 既有报告的参考观察 / Supplementary observations from an existing WorkBuddy report

仅阅读 WorkBuddy 已生成的 `4a5g_state_checkpoint_20261016_162320.json`，其 AT 为 `2026-10-16 16:21:26`（字段本身没有时区）。该报告不是本轮由 WorkBuddy 响应一次性验收请求产生，也未携带 MX 控制探针通过证据；不能替代正式验收。

Only the existing WorkBuddy-generated report `4a5g_state_checkpoint_20261016_162320.json` was read. Its AT is `2026-10-16 16:21:26` without an explicit timezone. It was not produced in response to this acceptance request and contains no passing MX control-probe evidence; it does not substitute for formal acceptance.

| 检查点字段 / Checkpoint field | 报告内容 / Reported value |
|---|---|
| 当前城市 / Active city | Cooperstown, NY；ID 22 |
| 查询族 / Query families | completed=17；pending=3 |
| 累计城市页数 / Cumulative city pages | 47 |
| 过去24小时请求 / Requests in last 24h | 10；non-OK=0 |
| 最近列出的运行 / Latest listed run | `inventory:2026-10-16:cdf0ebd2`；requests=2；pages=2；completed；family=`tourist gift shop` |
| 另外列出的运行 / Other listed runs | `fbcc7295`: 3 requests/pages, `visitor center gift shop`；`69235b78`: 2 requests/pages, `family game store`；`76940963`: 3 requests/pages, `children's store` |
| 当日运行 / Runs reported for the day | total=2；failed=0；lock=released |
| lead 总行数 / Total lead rows | 1211；不是本次新增已验收值 / not an accepted count of new leads |

这些是采集执行和查询族变化的积极参考，但“过去24h请求数”不能直接充当指定验收区间的请求总数。尚未核实运行时间字段的 UTC/+08 转换、正常调度关联、SAFE≥50 的运行入口证据、请求流水、逐轮预算、历史锁冲突及唯一性。不得凭旧 target_met 停止原因或零新增判定失败。未通过正式 MX 控制探针前，不发布任何检查点 SAFE 数字作为最新权威读数。

These are encouraging secondary observations of collection and query-family changes. A last-24h request count cannot be substituted for the requested acceptance interval. UTC/+08 conversion, normal-scheduler linkage, SAFE>=50 at run entry, request audit, each run's budget, historical lock conflicts, and uniqueness remain unverified. Neither the legacy target_met stop reason nor zero additions alone establishes failure. No checkpoint SAFE number is published as a current authoritative count before the formal MX control probe passes.

## 状态字段 / Status fields

```text
PHASE = 4A.8S_POST_DEPLOYMENT_ACCEPTANCE
CHANNEL_EXISTS = true
CODEX_CAN_CALL_CHANNEL = true
DEPLOYED = true
PRODUCTION_DEPLOYED = true
PRODUCTION_SHA_VERIFIED = true
LIVE_STATE_CHECKS_PASSED = true
PREFLIGHT_ALL_GATES_PASSED = false
PRODUCTION_EFFECTIVENESS_VERIFIED = false
NORMAL_INVENTORY_RUN_OBSERVED = UNKNOWN
PROVIDER_REQUESTS_AFTER_DEPLOY = UNKNOWN
NEW_ORGANIZATIONS = UNKNOWN
NEW_LEADS_AFTER_DEPLOY = UNKNOWN
NEW_FIRST_PARTY_EMAILS = UNKNOWN
MX_CONTROL_PROBE_PASSED = UNKNOWN
CURRENT_SAFE = UNKNOWN
INVENTORY_GLOBAL_UNIQUENESS_VERIFIED = false
SMTP_ENABLED = 0
EMAILS_SENT_BY_CODEX_THIS_TASK = 0
PRODUCTION_EMAILS_SENT_IN_ACCEPTANCE_WINDOW = UNKNOWN
REAPPLY_CALLS = 0
ROLLBACK_CALLS = 0
MANUAL_INVENTORY_TRIGGERS = 0
ADDITIONAL_SCHEDULERS_CREATED = 0
PHASE4B1G_DEPLOYED = false
WORKBUDDY_ACCEPTANCE_REQUEST_PREPARED = true
WORKBUDDY_ACCEPTANCE_REQUEST_DELIVERED = false
RESULT = DEPLOYED_AWAITING_WORKBUDDY_READONLY_ACCEPTANCE
```

UNKNOWN 表示证据不足，不是计数为零或业务失败。本轮代码和生产资格规则均未修改；未执行新功能测试，未把历史测试当成本次生产验收。全局发送历史未能读取，故只确认 Codex 本轮发送数为零及实时冻结有效。

UNKNOWN means insufficient evidence, not a zero count or a business failure. No application code or production eligibility rule changed. No new feature tests were run, and historical tests were not substituted for current production acceptance. Global sending history is unavailable, so only zero sends by Codex in this task and the live freeze are confirmed.

## 证据、阻塞和下一步 / Evidence, blockers, and next action

- 正式通道原始返回保留于 Git 忽略的本地 `output/channel_20261016/readonly_channel_snapshot.json`，SHA-256 `ed9a8103f08e9c64327bb635f0bce726401011b73ae92eea9bd4a0e53efb513e`。 / Raw channel responses remain locally in Git-ignored output with this SHA-256.
- WorkBuddy 参考检查点 SHA-256：`1f386d896fe9bca4be3fbf84740654bcc9542bd30c79fba385e7707c0523aef2`。未复制客户明细到 Git。 / WorkBuddy supplementary checkpoint SHA-256; no customer records were copied into Git.
- 阻塞：正式通道没有日志/MX接口，当前工具没有 WorkBuddy 消息入口，未取得符合本次范围的一次性验收报告。 / Blockers: no channel log/MX interface, no callable WorkBuddy messaging entry point, and no one-time acceptance report meeting this request.
- 下一步：由 WorkBuddy 在原权限环境只执行一次所附只读验收，返回脱敏报告及证据来源；Codex 复核后更新效果结论。不扩权，不加接口，不触发 Inventory，不扩大部署。 / Next: WorkBuddy performs the attached read-only acceptance once within its existing permissions and returns a sanitized report with evidence provenance. Codex reviews it before changing the effectiveness verdict. Do not expand privileges or interfaces, trigger Inventory, or expand deployment.

报告自检：中英双语、已执行与未执行区分、UNKNOWN 保留、发送冻结、风险与下一步、无秘密和客户明细，均已复核。报告提交和推送结果以本次最终 Git 核验为准。 / Report self-check: bilingual content, completed/incomplete separation, preserved UNKNOWN values, sending freeze, risks/next steps, and absence of secrets or customer records were reviewed. Commit and push results depend on final Git verification.
