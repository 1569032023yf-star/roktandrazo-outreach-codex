# U1 安装认证绑定 / Installed credential binding

时间 / Time: 2026-11-04T06:15:03.486948+00:00
固定源码 / Fixed source: c3ef1fcc94d1792421a8e15aa6e916be16cd67de

中文：安装器现在生成rokt.u1-python-runtime.v2，将批准计划的token_sha256纳入已固定runtime.json。bootstrap严格要求v2摘要并传入--token-sha256；宿主对同一次读取的原始token字节校验后才解码、访问快照/原owner或启动监听。变更后的token不能仅凭格式合法成为新的认证凭据。历史v1配置及直接CLI保留旧兼容路径，不把它们声明为新增摘要绑定。没有自动轮换凭据或提升权限。
English: Installer generation now emits rokt.u1-python-runtime.v2 and carries approved token_sha256 into pinned runtime.json. Bootstrap requires and forwards the v2 digest. The host checks the exact bytes from a single token read before decoding, snapshot/owner access or listener startup. A replacement token cannot become the credential merely by having valid syntax. Historical v1 configuration and direct CLI retain legacy compatibility and are not claimed to have the new binding. No automatic credential rotation or privilege grant was added.

验证 / Validation:
- python -B -m unittest test_bootstrap_arguments test_u1_provision test_u1_host_runtime.HostRuntimeTests.test_changed_provisioned_token_rejects_before_listener_or_state -q: 6 PASS / 4.740s.
- python -B -m unittest test_packaged_runtime_plan test_install_command test_bootstrap_arguments test_u1_provision -q: 13 PASS / 11.707s.
中文：包含实际PowerShell配置生成、独立Python进程拒绝token替换/非法摘要且不创建状态目录、缺失v2绑定拒绝、v1及原owner参数兼容。未重复受权限拒绝的HTTP监听测试。没有新源码全量回归或独审，均不得继承旧SHA结论。
English: Checks cover actual PowerShell generation, isolated Python rejection of token replacement/invalid digests without creating state, missing v2 binding rejection, and v1/original-owner argument compatibility. Permission-denied HTTP listener tests were not mechanically repeated. Full regression and independent review were not performed for this source and old-SHA results are not inherited.

既有证据 / Existing evidence: a3ce4a5安装包SHA256 1e753098a2424745b8423a10b74b03dc1244ca5091d6b53674b0c977ed39917b，回滚归档SHA256 52f9c951623b8bcc3c0237046d56e345ec7501377dcbe9d8a328da1087169e8d。新源码未入这两个旧包。既有ROLLBACK_A3CE4A5_PARITY_REPORT.json已完成VERIFIED/4961对应组件，仅归档清单一致性；rollback_verified仍false。旧72208会话句柄不可恢复，依实际持久报告更新定位状态，不声称执行过回滚。旧解压验证仍FAILED/WinError10013。
The prior a3ce4a5 archive hashes above do not contain this source. Durable rollback parity now reports VERIFIED for4961 components, scoped to archive/manifest parity only; rollback_verified stays false. Session72208 is no longer available; durable output, not an inferred process exit, establishes the result. Extracted delivery acceptance remains FAILED with WinError10013.

独审 / Independent review: PENDING. 全量 / Full regression: NOT_RUN_FOR_THIS_SHA.
DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; smtp_enabled=false.

未执行 / Not performed: 生产安装、服务启用、Inventory采集、生产数据库写入、发信、权限或网络门禁修改 / production installation, service enablement, Inventory collection, production DB writes, email, permission or network-gate changes.
风险 / Risk: 完整包重建与服务启动未验收；旧v1为兼容入口，不提供新增摘要保证 / full rebuild and service startup remain unaccepted; legacy v1 does not provide the added digest guarantee.
敏感信息检查 / Sensitive-data check: 仅临时fixture token，报告不含实际token或密钥 / fixture tokens only; no actual credentials or secrets in this report.
运行限制 / Runtime limits: 3小时周期、45分钟提示上限、最多两条重线保持；平台无硬超时字段，未宣称强制配置 / three-hour schedule,45-minute prompt limit and at most two heavy workstreams retained; no platform hard-timeout field claimed.

下一动作 / Next action: 将新固定源码整合进完整运行时归档并验证安装配置到服务启动链；独审保持PENDING，回环HTTP权限故障及正式Provider合同仍未解决。
Integrate the new fixed source into full-runtime archives and validate installer configuration through service startup; review remains PENDING, loopback HTTP permission failure and formal Provider contracts remain unresolved.
