# 唯一firing/run归因 / One-to-one firing/run attribution

中文：2026-10-31 07:36实际恢复本地/远端7aa866de0d295e896ddf5719c70794e3076b2954；WorkBuddy仍74140982，沿用Issue2消费回执6535746968，不重复发布。发现交接验证器虽拒绝重复runtime行，仍可能把同一真实run归到两条firing，或接受重复/缺失firing_id。本轮固定源码71a539a50b6f79d8f09ae5adaf4a785802df6751补一对一约束：所有相关歧义对都拒绝，不任意保留第一条；原stage/trigger/window和权限关闭合同保持。

English: Actual cycle07:36 restored local/remote7aa866de0d295e896ddf5719c70794e3076b2954. WorkBuddy remains74140982; preserve Issue2 receipt6535746968 without duplication. The validator rejected duplicate runtime rows but could count one run for two firings or accept duplicate/missing firing identities. Source71a539a50b6f79d8f09ae5adaf4a785802df6751 requires one-to-one attribution, rejecting all ambiguous pairs instead of choosing the first. Existing stage/trigger/window and closed-authority contracts remain.

中文：新增2项测试覆盖同run不同firing、同firing不同run及空/未知ID。37项组合通过3.423秒，包括归因、HTTP、恢复状态、独立安装计划及开发包合同；不是安装实测。固定新源码重新核对原七份生产Git blob及实际7对数据，仍仅6对Inventory通过、1对post-send拒绝，不改变旧回执。独审PENDING；没有新全量回归，不扩用旧833结论。该纯离线验证器不进入生产包、不接数据库/OS执行器。

English: Two new tests cover one run claimed by distinct firings, one firing naming distinct runs, and empty/unknown identities.37 combined tests pass in3.423s, covering attribution, HTTP, recovery status, independent installation plan and development package contracts; this is not installation verification. Rechecking all seven source blobs and actual seven pairs at the new pin still verifies six Inventory pairs and rejects one post-send pair, without changing the prior receipt. Independent review PENDING; no fresh full regression or inheritance of old833 results. This pure offline validator is not integrated into a production package/database/OS executor.

中文：下一步仍是固定HTTP/归因独审与受保护安装日志/OS适配层，尤其第二个Set-Acl失败后的保全合同；本轮未实现该安装日志，不把验证器修复当作安装闭环。正式维护租约、最小授权、可信签发/轮换、无人登录出口仍阻塞。生产证据69只对应旧采样，严格净增长UNKNOWN，8791仅旧会话UP，不升级生产或无人登录验收。没有生产DB、SMTP、ACL、服务、代理或调度变更，原未提交目录保持。

English: Next remains pinned HTTP/attribution review and protected installation journal/OS adapter, especially preservation after the second Set-Acl fails. That journal is not implemented by this change; validation is not installation closure. Formal maintenance lease, minimal authority, trusted issuance/rotation and unattended egress remain blocked. SAFE69 belongs to its old sample, strict growth UNKNOWN; prior session-scoped8791 UP grants no production/unattended acceptance. No production database, SMTP, ACL, service, proxy or scheduler mutation occurred; existing untracked evidence remains intact.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN; allow_dispatch=false; allow_cancel_dispatch=false.

自检：双语、结果/风险/未完成项/下一步完整，无秘密。 / Self-check: bilingual results/risks/incomplete work/next steps complete; no secrets.
