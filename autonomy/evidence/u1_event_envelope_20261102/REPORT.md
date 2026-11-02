# U1 执行响应门禁修复 / Execution-response gate repair

时间 / Updated: 2026-11-02T12:01:00.497851+00:00
源码 / Source: `c6a500876d9e61881c14cff188bbdb538aa50fe4`
恢复时远端 / Remote at recovery: `ec857d67d8087222c8b190dcb2776d072080ac14`

中文：实际执行接线此前只检查 Inventory 与 allow_dispatch，未拒绝取消/重放/生产验收门禁缺失或开启、重复 JSON 字段、非有限常量与超长回复。现有 ExistingOwnerBridge 在向执行器交付事件前统一拒绝上述回复，保留原 owner、租约、预算和取消日志链，不新增调度器，不重派 UNKNOWN。修改两份源码/测试文件，非单纯增加报告。
English: ExistingOwnerBridge previously checked only Inventory and allow_dispatch. Before delivery to the executor it now rejects missing/open cancellation, replay, reconciliation or acceptance gates, duplicate JSON keys, non-finite constants and oversized responses. Existing owner/lease/budget/cancellation paths remain authoritative; UNKNOWN never replays.

中文：源码定向 24 PASS（7.064 秒）；实际包内导入执行 24 PASS（10.424 秒）。65 文件逐 SHA256、两份 ZIP 逐字节及真实 AMD64 PE 校验通过。新源码独审 PENDING，70ee721 的独审只保留原范围，不继承。可比回归见 comparison/COMPARISON.json；既有 833 项结果不套用到本候选。
English: Source-targeted 24 PASS; actual packaged imports 24 PASS. All 65 file hashes, both archives and AMD64 PE verified. Independent review is PENDING for this pin; the earlier review remains scoped to 70ee721. Fresh baseline/candidate runs each execute833 tests, each with37 failures/17 errors; failure/error IDs match, NO_NEW_REGRESSION=true, NOT ALL GREEN.

安装包 / install.zip SHA256: `cece699786bc4c0fb2d7d8dffe3020acc6bcb05757a09a41d75b50b60b2c5b97`
回滚包 / rollback-tools.zip SHA256: `f432a2f1b764c28f100a8a252489d68001840033039d7f1393820e9aab8001fd`
外清单 / Outer manifest SHA256: `33a3577e893253688ea6ab5a85f63f8c858e5c5b6265f9e89857cf3b3f169597`
安装器 host 清单 / Host manifest SHA256: `d423f5397e237f340eaa04db60b4e2a251e128ca5a2acc559270eb37726d4199`

中文：恢复时本地 canonical 队列仍指82031ac，实际远端及首段 checkpoint 已为70ee721集成成果。本轮实际读取二者、核对已存独审，将首装/升级/精确回滚/ABSENT/现有owner离线链记回本地canonical；不重复实现、不用Git投影冒充本地队列。
English: Local canonical queue lagged at82031ac while remote/checkpoint documented70ee721. Both were read and reconciled against stored review; completed lifecycle/transport work was restored to canonical without reimplementation.

中文：读取 WorkBuddy 新固定提交 `1c7ba79ac5fec334ae80cabcb2083157ab0a0a71` 两份Windows兼容文件并重算 Git blob SHA1。JSON schema标识、producer、必需字段、采样与生成时间检查通过；无独立JSON Schema，结构检查不冒充正式schema认证。JSON blob `eefd74f48c1520801c4a670bdc061f037240073e`；Markdown blob `cc0937f5321302c6f5c996d60ced4c8c6f4247f4`。采样 `2026-11-02T17:36:02+08:00 .. 2026-11-02T17:38:10+08:00`；生成 `2026-11-02T17:38:10+08:00`；Git提交 `2026-11-02T17:39:40+08:00`。来源 Issue2/6573893220 已读，无重复合同申请。其1/6候选绑定结论针对旧0db17b5，不改写、不套用到后续包。
English: Read and recomputed blobs for two Windows compatibility files at the pinned WorkBuddy commit. Schema marker, producer, structural fields and independent sample/generation/commit timestamps were checked; no independent JSON Schema was supplied. The historical1/6 binding finding applies to0db17b5 only. This is Windows evidence, not new SAFE/Inventory acceptance.

中文：8791跨调用与自启仍未通过；7877无人登录可用 NOT_SUPPORTED_OBSERVED（N=2），注销/重启实际出口 UNKNOWN。SAFE/Inventory沿用此前生产证据，不从Windows报告推导业务增长或零漏跑。未重启采集、未更改生产服务/ACL/调度/数据库/账本/SMTP。
English:8791 persistence/autostart remain unaccepted;7877 unattended availability is NOT_SUPPORTED_OBSERVED(N=2), actual logoff/reboot egress UNKNOWN. Existing production SAFE/Inventory evidence remains scoped; no collection, service, ACL, scheduling, DB, ledger or mail changes occurred.

下一唯一动作 / Next action: 在现有安装器接入强制实时维护排斥校验；随后补正式后端与唯一原 owner 配置。不重复采集环境，不安装服务。
Implement enforced live maintenance-exclusion admission in the existing installer; then formal backend and sole-owner configuration. Do not repeat environment collection or install services.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false. 原Inventory / Sole Inventory:1784775229336.
