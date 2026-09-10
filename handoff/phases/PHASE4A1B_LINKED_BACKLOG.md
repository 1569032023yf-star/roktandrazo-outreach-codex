# 已关联积压重连 / Linked-staging backlog reconnection

## 范围与路由 / Scope and routing

仅开发修改；未部署。生产源文件仅 `bd_orchestrator.py` 与 `discovery/discovery_service.py`。无数据库迁移。 / Development changes only; not deployed. Only two production source files change: `bd_orchestrator.py` and `discovery/discovery_service.py`. No database migration.

262 条已关联空邮箱记录：人工审核 259、网站恢复 3；原因码分别为网站待查 255、网站恢复 3、无公开邮箱或表单 4。网站存在 7、缺失 255；official_match=1 为 4、=0 为 258；旧摘录存在 262，但完整官方邮箱证据 0。证据 URL 存在 250、缺失 12。所有原始原因明细精确计数见路由审计附件。 / Of 262 linked empty-email records, 259 are manual review and 3 recovery. Reason codes: website lookup 255, recovery 3, no email/form 4. Websites: 7 present, 255 missing. Official match: 4 true, 258 false. All 262 have legacy snippets, none has the full official email contract. Evidence URLs: 250 present, 12 missing. See the routing audit for exact counts of every original reason detail.

当前 Ithaca 有 20 条，其中 18 条符合重试路由、2 条网站身份审核被拦截。其他 242 条已关联记录不在本次城市处理范围。166 条未关联待补库保持不动；不合成 staging、不伪造 provider ID、不按名称批量关联。 / Ithaca contains 20 rows: 18 retryable and 2 blocked for website identity review. The other 242 linked rows are outside this run's city scope. The 166 actionable unlinked leads remain untouched: no synthesized staging, fabricated provider IDs, or name-only bulk linkage.

## 实现 / Implementation

- 确定性白名单：已有明确关联、空邮箱、允许的审核原因、同城市州及身份字段一致；拒绝历史发送、退信、抑制、拒绝、组织冲突、地址冲突、身份审核、第三方来源与目录/社交网站。历史检查覆盖相关身份及同组织成员。 / Deterministic allowlist requires existing linkage, empty email, permitted review reasons and consistent city/state/identity. History, organization/address conflicts, identity review, third-party sources and directory/social sites are blocked; related identities and organization members are checked.
- 复用现有网站解析和 staging 后处理。关联重试不得插入新 lead，邮箱证据仍经 Phase 3D 完整证据门控。无效证据不会绕过冻结 V2/MX。 / Reuses website resolution and staging postprocessing. Linked retries cannot insert leads; Phase 3D complete-evidence gating remains authoritative. Invalid evidence never bypasses frozen V2/MX.
- 每次最多 20 条，并取两个现有 lane 配置上限的较小值；只处理当前城市。先未尝试记录，再按最近尝试时间及 ID 排序。原始状态、原因、次数、时间保存在既有 JSON metadata；单条异常回滚业务写入但保留重试检查点。 / At most 20 rows per run, further capped by the smaller existing lane budget, current city only. Never-attempted rows precede oldest attempts with ID tie-breaks. Existing JSON metadata retains original state/reason, attempt count and timestamp. Per-row exceptions roll back business writes while retaining checkpoints.
- 本窄版本的标准 Inventory 仅消费已关联积压，不运行新商户 discovery 或未关联后处理；恢复新增发现需后续明确范围审查。旧扫描器文件未删除，但不再是此 Inventory 路径的证据来源。 / This narrow canonical Inventory consumes linked backlog only, with no new-place discovery or unlinked postprocessing. Restoring new discovery requires a later explicit scope review. The legacy scanner file is retained but is not an evidence authority in this Inventory path.
- 完成信号来自未改动的冻结 selector 内部 V2 判定，计数非空唯一 organization_key；不创建 FSP 或授权。BroadReady 仅显示。现有工作日 Inventory 30 与 Outreach 40 的差异仅报告、不修改；周末目标也保持原逻辑。 / Completion uses the unchanged frozen selector's V2 decisions and unique nonempty organization keys, without plans or authorizations. BroadReady is informational. Existing weekday Inventory 30 versus Outreach 40 is reported, not changed; weekend target logic also remains unchanged.

## 离线验证 / Offline validation

FULL_SUITE_PASS = 322; SUBTEST_PASS = 76; FULL_SUITE_FAIL = 0; FULL_SUITE_ERROR = 0.

新增 10 项测试覆盖虚假完成、真实形态的完整证据关联、网站恢复、历史状态与日志拦截、冲突、第三方来源、隐藏邮箱、TLS、幂等、有界公平轮转、异常检查点。既有 Phase 3D 正反例仍通过。 / Ten additional tests cover false completion, full evidence linkage, recovery, history states/logs, conflicts, third-party sources, hidden email, TLS, idempotency, bounded fairness and exception checkpoints. Existing Phase 3D positive/negative cases remain passing.

FROZEN_FILES_CHANGED = 0.

开发最终 SHA256 / Final development SHA256:

- bd_orchestrator.py: `175d9af8df54aa7f36f10da44c6ee633dc864e10a1f66c674dff1b8f50fd3b16`
- discovery/discovery_service.py: `dc47a37f8491d7e3954d2defaec0229fe686dc67d600daa668d24475cf82057d`

## 未关联线索后续建议 / Future unlinked recommendation

单独审查 166 条的原始来源和稳定供应商身份，以人工可复核的地址、官网及供应商证据建立真实关联；本阶段不实现、不写入。 / Separately review original provenance and stable provider identities for the 166 rows, using auditable address, official-site and provider evidence to establish genuine linkage. Not implemented or written in this phase.

## 新鲜副本演练 / Fresh-copy rehearsal

首轮使用 WorkBuddy Python 的浏览器驱动，被开发护栏正确拒绝，记录保存在 `PHASE4A1B_COPY_VALIDATION.json`，不作为 Maps 成功证据。随后使用独立新鲜副本和开发虚拟环境驱动复验，护栏未修改，结果在 `PHASE4A1B_FINAL_COPY_VALIDATION.json`。两轮均未部署、未写生产。 / The first run's WorkBuddy Python browser driver was correctly blocked by development guards; its record is retained in `PHASE4A1B_COPY_VALIDATION.json`, not counted as successful Maps evidence. A separate fresh copy was then validated using the development virtual-environment driver without changing guards; see `PHASE4A1B_FINAL_COPY_VALIDATION.json`. Neither run deployed or wrote production.

最终运行 / Final run: `phase4a1b-dev-20260910T072719Z`.

| 指标 / Metric | 结果 / Result |
|---|---:|
| BroadReady before | 34 |
| Linked backlog eligible / processed | 18 / 18 |
| Website resolution processed | 11 |
| Safe postprocess processed | 7 |
| New visible first-party emails | 0 |
| New full evidence records | 0 |
| New existing leads linked | 0 |
| SAFE_READY before / after | 1 / 1 |
| Remaining gap / 剩余缺口 | 29 |
| target_met | false |
| Job status / 作业状态 | partial |

11 个真实 Maps 查询均返回 0 条列表结果；这不能证明商户不存在。7 条官网后处理中，4 条未取得可接受页面、3 条没有可晋级的公开邮箱。没有推测邮箱或虚构证据来制造增量。网络/供应商产出仍需后续独立审查，本阶段不修改第三个生产文件。 / All 11 real Maps queries returned zero list results; this does not establish that merchants do not exist. Of seven official-site postprocess attempts, four yielded no acceptable page and three yielded no promotable public email. No guessed email or fabricated evidence was used to manufacture growth. Network/provider yield needs separate follow-up; no third production file is changed here.

副本对比确认：所有未关联 lead 原样保留；lead/staging 总数未变；发送、退信、抑制、FSP、授权及授权明细表完整内容哈希未变。 / Copy comparisons confirm all unlinked leads unchanged, unchanged lead/staging counts, and identical content hashes for send, bounce, suppression, FSP, authorization and authorization-entry tables.

SMTP=0; IMAP=0; FSP_CREATED=0; AUTHORIZATION_CREATED=0; PRODUCTION_DB_WRITES=0; PRODUCTION_FILES_CHANGED=0; SCHEDULER_CHANGES=0; FROZEN_FILES_CHANGED=0; LEGACY_UNSAFE_EVIDENCE_PROMOTED=0.

## 结论 / Decision

ROUTING_AUDIT_COMPLETE = true

BROADREADY_FALSE_COMPLETION_FIXED = true

LINKED_BACKLOG_RECONNECTED = true

READY_FOR_CONTROLLED_PRODUCTION_PATCH = true

上述就绪仅表示此两文件窄补丁通过开发验证、可提交受控生产补丁审查；不是补库目标达成，也不是部署授权。整体生产仍保持暂停，SAFE 库存不足。旧 Phase 3 发布包未更新，不得用旧包代替本次补丁。 / Readiness means only that this two-file narrow patch passed development validation and can be reviewed for controlled production patching. It does not mean the inventory target was met or authorize deployment. Production remains held and SAFE inventory remains insufficient. The old Phase 3 release package is not updated and must not be substituted for this patch.
