# 无人值守方案断点 / Unattended design checkpoint

固定交接 / Pinned handoff: `1569032023yf-star/workbuddy-task-window@6ba549fc687ab5670801e5472893a2c047a53f64`。三个新增文件Git blob逐字节匹配，两份JSON解析通过；原始材料仅在ignored runtime中，不公开身份、代理或凭据元数据。消费回执 / Receipt: https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/2#issuecomment-6402130583

## 已确认边界 / Evidence boundaries

三次后续firing恢复，不能继续把认证失败作为持续阻塞。桌面停运因果仅为推断。8791跨调用不存活，HKCU Run存在不是跨登录验收。7877用户会话代理是无人登录运行的独立前置依赖。SAFE56为历史快照，非当前增长证明。

Three later firings recovered; authentication is no longer an established persistent blocker. Desktop downtime causality is inferred. Bridge cross-call persistence failed; HKCU Run is not cross-login acceptance. The user-session proxy is a separate unattended prerequisite. SAFE56 is historical, not growth acceptance.

## 提议架构，未批准部署 / Proposed architecture, not approved for deployment

使用专用非管理员执行身份及系统级任务计划程序宿主，显式批处理登录权限、机器可读运行时及浏览器。不得默认LocalSystem；不得启动缺失映像的旧BDExecutionHost。S4U不支持网络及加密文件访问，不能作为网络采集默认身份。运行时只读，数据库日志/缓存/审计目录最小写权限，不授予部署凭据或SMTP凭据。用户Credential Manager内容不可假设跨身份可读。

Use a dedicated non-admin identity and machine-level Task Scheduler host with explicit batch logon rights and accessible runtime/browser. Do not default to LocalSystem or revive the missing-image legacy service. S4U cannot access network or encrypted files. Limit writes to required journal/cache/audit directories; exclude deployment and SMTP credentials. User credential storage is not assumed accessible across identities.

7877必须另行验证经批准的非交互网络出口；未满足则失败关闭，不复制用户代理秘密或规避来源限制。启动仅做有界DNS/TLS/代理健康验证，网络失败持久化延期；认证/政策拒绝不自动重试。429遵守Retry-After及总预算。

Require separately approved noninteractive egress; fail closed if unavailable. Do not copy proxy secrets or bypass restrictions. Bound DNS/TLS/proxy readiness probes and persist deferred retries. Do not retry auth/policy rejection. Respect Retry-After and total budgets.

保持Inventory1784775229336的逻辑身份及历史。切换前停止旧权威派发、等待运行排空并核对UNKNOWN；确认唯一权威后才启用新宿主。同时采用原排他锁与持久slot账本；UNKNOWN不可因lease超时直接重放。重启恢复先对账，遗漏slot不无限补跑。回滚先禁用并排空新宿主，再恢复旧权威，不删除账本或回滚生产业务数据。

Preserve the logical Inventory identity and history. Stop old dispatch, drain and reconcile unknown outcomes before enabling the replacement authority. Retain exclusion plus a durable slot ledger; lease expiry never authorizes replay of unknown effects. Reconcile after reboot and bound catch-up. Roll back by disabling/draining the new authority before resuming the old one; preserve business data and ledgers.

## 8791验收 / Bridge acceptance

分别记录配置、同登录会话跨两次独立调用、自然注销/登录后再次跨调用及重启无人登录四个层级。收集脱敏boot/session标识、监听状态、POST health、进程归属与持续时间；不用GET404或缺operation_id的status400判断服务故障。HKCU Run最多满足登录后机制，不能宣称无人登录。不得绕过Job限制。测试注销/重启需单独维护窗口授权。

Separate configuration, two independent calls within a login, calls after a normal new login, and reboot without login. Capture redacted boot/session identifiers, listener state, POST health, process ownership and duration. GET404 and status400 without an operation ID do not prove outage. HKCU Run is login-dependent. Do not bypass job restrictions. Disruptive logout/reboot testing requires an approved window.

## 增量获客 / Incremental acquisition

只读审计发现本仓stage_inventory在SAFE达标后仍执行受限发现，target_met仅为终态库存口径；外层调度短路仍需对应代码/事件证据。不能从SAFE56直接推断本仓停止发现。

Read-only audit found local stage_inventory continues bounded discovery even when SAFE meets target; target_met is an outcome label. Outer scheduler skipping requires matching code/event evidence.

建议每日业务日期冻结baseline与规则版本，以全历史组织去重和首次合格事件账本统计新增企业；既有企业首次达标另计，SAFE净增长单独计入流失/撤销原因。跨周期不得重置baseline。预留并扣减日级页数、网站请求、时间、费用上限，UNKNOWN占用预算至核对；单轮和单日双上限，达预算停止，禁止为达目标降低资格门槛。具体新增目标和费用数字待实际单位成本证据及批准，不更改50/60生产配额。

Freeze each business-day baseline and rule version. Count new organizations through historical identity deduplication and first qualification events; report existing organizations newly qualified separately, and explain SAFE churn independently. Never reset the baseline per firing. Reserve daily page/site/time/cost budgets and retain unknown reservations until reconciliation. Enforce per-run and daily caps without weakening qualification. Numeric targets require cost evidence and approval; existing quotas remain unchanged.

## 状态及下一步 / Status and next steps

交接核验与回执完成；方案草案完成。实现、故障注入、完整独立审查、发布清单均待完成，RELEASE_READY=false，PRODUCTION_DEPLOYED=false，LIVE_PROVIDER_ACCEPTED=UNKNOWN，BUSINESS_GROWTH_VERIFIED=UNKNOWN。独立审计代理因账户用量上限退出，未形成审核通过结论。

Handoff verified and acknowledged; draft design complete. Implementation, fault injection, independent review and release manifest remain incomplete. The audit agent stopped at an account usage limit; no review approval is claimed.

下一自动动作：实现纯离线准入/slot恢复/桥接验收判定及确定性测试，再独审、固定SHA、发布清单。生产授权请求必须等可审核包完成：专用身份和目录ACL、禁用态系统任务、非交互出口、排空后唯一调度权威切换与维护窗口。配额修改另项审批，不包含在架构授权中。

Next: implement offline readiness/slot recovery/bridge acceptance decisions and deterministic tests, then independent review and a pinned release manifest. Request production authorization only after a reviewable package exists: dedicated identity and ACLs, disabled machine task, noninteractive egress, drained single-authority cutover and maintenance window. Quota changes require separate approval.

参考 / References: https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype ; https://learn.microsoft.com/en-us/windows/win32/services/localsystem-account
