# 桥接会话证据聚合 / Bridge session evidence aggregation

新增autonomy/bridge_session_evidence.py与test_bridge_session_evidence.py。此模块只消费EvidenceConsumer已认证的配置、两次POST health观察和完整OS事件窗口；不采集OS、不联网、不安装桥接、不触发注销或重启，也不修改host_preparation门禁。

The new module consumes authenticated configuration, two POST-health observations and a complete OS event window through EvidenceConsumer. It performs no OS collection, network access, bridge installation, logoff or reboot, and does not modify host admission.

## 输入合同 / Input contract

配置kind=bridge_configuration，绑定configuration_id（64位哈希标识）和bridge_principal_id；两探针kind=bridge_observation，使用现有classify_pair合同，加同配置/服务身份绑定。配置观测不能晚于探针，两个call_id、receipt_id及时间必须独立有序。配置、探针、OS窗口必须来自同一已配置可信source及collector身份；缺配置或身份更改拒绝。

Configuration binds a64-character configuration identifier and bridge principal. Bridge observations use classify_pair plus these same bindings. Configuration must precede probes; call IDs, receipt IDs and times must be independent and ordered. All evidence must share the provisioned source and collector identity; missing or changed identities fail closed.

OS窗口kind=bridge_os_event_window，要求complete=true、gaps_detected=false、all_interactive_sessions_included=true，覆盖起止包含两次调用且结束不晚于窗口签发时间。事件序列连续、时间有序、末条coverage_end与coverage_to一致，最多1024条；未知事件类型、缺序或缺覆盖拒绝扩展验收。此声明必须由批准的完整OS事件采集器产生，签名不能证明采集器本身正确。

OS evidence requires explicit completeness, gap-free collection of all interactive sessions, coverage containing both probes and no future events. Event sequences must be consecutive and ordered, ending at coverage_to, with a1024-event limit. Unknown event types or coverage gaps reject extended acceptance. The approved collector must establish these facts; signatures do not establish collector correctness.

## 四项独立结果 / Four independent results

- HKCU_RUN_CONFIGURED仅表示可信配置观察；不会推导无人登录能力。 / HKCU configuration is an independent observation and never establishes no-login capability.
- CROSS_CALL_VERIFIED要求同会话同实例两次独立成功调用。 / Cross-call acceptance requires independent successful calls in the same session and instance.
- CROSS_LOGON_VERIFIED要求同boot、同配置/服务身份，旧登录ID的注销事件先于新登录ID的登录事件，二者用户身份相同且位于两调用之间。允许桥接进程重新启动；PROCESS_OBSERVATION明确同实例或不同实例端点，不宣称期间连续可用。 / Cross-logon acceptance requires ordered logout/login events for the same user between probes under one boot and configuration/service identity. Process restart is permitted; the process field explicitly reports same/different-instance endpoints, never continuous uptime.
- NO_LOGIN_BOOT_VERIFIED仅在配置为machine_boot且无interactive依赖、窗口从boot事件开始、初始交互会话数为0、整个窗口无任何登录/注销事件且两探针均无交互登录时成立。即使用户曾登录后注销、两个端点均显示无人登录，也不能通过。 / No-login acceptance requires machine-boot configuration without interactive dependency, coverage starting at boot, zero initial interactive sessions, no login/logout anywhere in the interval and two login-free probes. Logging in and out between apparently login-free endpoints cannot pass.

所有VERIFIED均为VERIFIED_AT_OBSERVATION，不代表当前持续在线，不输出统一BRIDGE_HEALTHY。evidence_digest用于具体证据包审计；稳定acceptance_id仅绑定配置、服务身份及两个真实观察标识/时间/boot/logon/instance，重签同事实不产生新周期。计数消费者必须按acceptance_id去重，本模块本身不累计生产周期。

All verified statuses are observation-scoped, not ongoing health; no combined healthy flag exists. The evidence digest audits a particular package, while stable acceptance_id binds the configuration, service identity and actual probe identities/times/boot/logon/instance. Re-signing the same facts does not create a new cycle. Counter consumers must deduplicate this ID; this module maintains no production counter.

## 验证与未完成 / Validation and remaining work

执行python -B -m unittest test_bridge_session_evidence -q：12项通过（0.005秒）。覆盖正常重登录、无人登录启动、HKCU不等同无人登录、缺OS窗口、事件断档、期间登录后注销、重放ID、身份/配置/boot变化、签名篡改及过期、重签不新增周期。新增生命周期要求：两观察关联会话的中间事件必须严格为旧会话注销、新会话登录；新会话提前注销或旧会话复活均拒绝。全部合成签名和固定夹具，不接触生产。

Twelve deterministic tests passed in0.005 seconds, covering relogon, login-free boot, HKCU separation, missing windows, event gaps, intervening login/logout, duplicate IDs, identity/config/boot changes, signatures, stale evidence and re-signing deduplication. Related-session transitions must be exactly old logout followed by new login; early new-session logout or old-session revival is rejected. All evidence is synthetic and offline.

正式OS采集器、信任根配置、维护窗口、真实跨登录及无人登录样本尚未提供。独立审核PENDING，真实四项状态不能以本测试代替，PRODUCTION_ACCEPTED=false。下一步独审最终源码，随后由既有WorkBuddy只读合同提供脱敏证据；不得擅自启动服务或修改注册表。报告无Token、代理地址、Cookie、客户资料或完整请求URL。

Production collection, trust provisioning, maintenance approval and real session/boot samples remain absent. Independent review is pending and synthetic tests do not establish any real bridge status; production acceptance is false. Next: review the final code and consume redacted evidence through the existing WorkBuddy channel, without service or registry mutations. No secrets or customer data are included.
