# 脱敏聚合遥测合同 / Sanitized Aggregate Telemetry Contract

日期 / Date: 2026-10-20。状态：开发实现，待父代理独立审核；未接通真实遥测，未部署，未标记业务验收完成。

Status: development implementation awaiting independent parent review. No real telemetry feed connected, no deployment, no business acceptance claimed.

## 范围与信任边界 / Scope and trust boundary

`autonomy/telemetry.py` 默认只读 `autonomy/runtime/telemetry/inbox` 的直接 `.json` 文件，不递归、不消费、不写入。不存在或无有效快照返回 `UNKNOWN`，不是零。`inbox` 参数仅为本地测试与明确授权调用方的路径注入，不会自动寻找生产数据。此实现没有数据库、网络、WorkBuddy、SMTP、调度或采集接口。

The module reads only direct `.json` files under the default local inbox, without recursion, consumption or writes. Missing or invalid-only input yields `UNKNOWN`, never zero. The inbox argument supports local tests and explicitly authorized callers; it does not discover production data. There are no database, network, WorkBuddy, SMTP, scheduling or collection interfaces.

来源必须由可信调用方通过 `approved_sources` 显式白名单授权，默认空白名单拒绝全部。快照不能自授权；输入内批准标记、路径、URL、邮箱、任意说明一律不属于 schema。白名单不是数字签名，不能证明上游真实性或数据已经正确脱敏；目录必须由获准上游独占可信写入。所有来源名仅允许小写字母起始，随后小写字母、数字、下划线和连字符，最多64字符。

Trusted caller policy must explicitly supply `approved_sources`; the empty default denies all sources. Snapshots cannot authorize themselves. Approval flags, paths, URLs, emails and free text are outside the schema. The allowlist is not a digital signature and cannot prove upstream authenticity or correct sanitization; approved upstream writers must control the inbox. Source labels start with a lowercase letter and contain only lowercase letters, digits, underscores and hyphens, at most 64 characters.

## 严格输入 / Strict input

每文件一个 UTF-8 JSON 对象，最大32768字节；拒绝重复 JSON 键和链接文件、链接目录及链接祖先目录。只允许以下全部必需字段，任何额外字段都拒绝。

Each file contains one UTF-8 JSON object, at most 32768 bytes. Duplicate JSON keys, linked files, linked directories and linked ancestor directories are rejected. All fields below are required; all extra fields are rejected.

| 字段 / Field | 合同 / Contract |
|---|---|
| schema_version | 整数1，不接受布尔 / Integer 1, excluding booleans |
| snapshot_id | 规范小写带连字符 UUID / Canonical lowercase hyphenated UUID |
| source | 调用方获准来源标签 / Caller-approved source label |
| collected_at | UTC `YYYY-MM-DDTHH:MM:SSZ` |
| period | 仅 / Only `24h` or `7d` |
| window_start | 与结束严格相差24小时或7天 / Exactly 24 hours or seven days before end |
| window_end | 必须等于采集时间 / Must equal collection timestamp |
| counts | 非空指标对象，仅非负整数，最大 `2**63-1` / Nonempty metric object, nonnegative integers up to `2**63-1` |

采集、区间起止不得晚于当前时间，采集时间距离当前最多1小时（边界包含）。调用方可注入带时区 `now` 进行确定性测试；无时区属于配置错误。时间策略固定，不能由输入放宽。

Collection and window timestamps cannot be in the future. Collection age must be at most one hour, inclusive. Callers may inject timezone-aware `now` for deterministic tests; naive time is a configuration error. Input cannot weaken these fixed time rules.

允许指标 / Allowed metrics:

`new_verified_organizations`, `new_official_sites`, `new_first_party_emails`, `new_history_mx_verified`, `new_safe_organizations`, `customer_emails_sent`, `replies`, `bounces`, `unsubscribes`.

不接受累计总量、身份明细、邮箱地址、凭据、嵌套对象、列表、字符串计数、负数、浮点或布尔计数。`new_safe_organizations` 是区间新增计数，不是总库存或允许负数的净增长。历史累计和净增长如需支持必须另行定义合同，当前不推算。`new_official_sites` 和资格指标同样仅代表指定区间新增。

Cumulative totals, identity details, email addresses, credentials, nested values, lists, string counts, negative values, floats and boolean counts are rejected. `new_safe_organizations` counts additions in the window; it is neither total inventory nor signed net growth. Historical totals and net growth require a separate contract and are not inferred. Site and qualification metrics likewise count additions in the stated window.

## 输出与去重 / Output and deduplication

`validate_snapshot` 返回分离后的白名单对象，非法输入抛出仅固定原因码的 `InvalidSnapshot`。`read_inbox` 返回 `status`、`snapshots` 和仅含固定原因码数量的 `rejected`，不回显文件名、异常文本或被拒载荷。

`validate_snapshot` returns a detached allowlisted object or raises `InvalidSnapshot` with a fixed reason code. `read_inbox` returns `status`, `snapshots` and rejection counts keyed only by fixed codes, without filenames, exception text or rejected payloads.

同一读取批次中通过单对象验证的重复 UUID 全部拒绝，不能让文件排序决定胜者。`seen_ids` 可由可信调用方提供以拒绝跨调用重放；本模块不写持久账本，默认反复读取相同未变化文件会得到相同快照，不能计为新事件。持久化去重尚未接通，调用方必须保留已处理ID；本任务禁止改写队列或创建状态库。

All individually valid snapshots sharing a UUID in one read are rejected, independent of filename ordering. Trusted callers can supply `seen_ids` for cross-call replay rejection. This module writes no persistent ledger: rereading unchanged input returns the same snapshot and must never count as a new event. Persistent deduplication integration remains pending; callers must retain processed IDs. This task does not change queues or create a state database.

每个来源、每种区间只返回最新完整快照；最新时刻并列多个不同ID则该组无输出，不回退旧值。不同来源和区间保持分离，不相加、不相减、不跨快照补齐缺失指标。缺失来源、区间或指标由使用方展示UNKNOWN；`VALID` 只表示至少一个快照有效，不表示指标齐全或feed已接通。滚动24h不是本地自然日，7d不是当日新增。

Only the newest whole snapshot per source and period is returned. A tie between different IDs at the latest timestamp suppresses that group without stale fallback. Sources and periods remain separate: no sums, differences or filling missing metrics from old snapshots. Consumers must show UNKNOWN for missing sources, periods or metrics. VALID means at least one valid snapshot, not completeness or feed connectivity. Rolling 24h is not a local calendar day; 7d is not today's additions.

## 验证、限制与下一步 / Validation, limitations and next steps

仅临时目录中的合成fixture；未读取真实inbox、生产数据库或凭据，未访问WorkBuddy、联网、发信或创建采集调度器。测试使用 `python -B -m unittest autonomy.test_telemetry -v`（实际以已有Codex运行时Python绝对路径调用）。测试结果在交付JSON中给出，不修改既有验收状态。必读CURRENT_STATUS.md、FILE_MANIFEST.md在本工作树不存在，已读取现有总控、日报及独立审核记录。

Tests use synthetic fixtures in temporary directories only. No real inbox, production database or credentials were read; no WorkBuddy access, network, email or collection scheduler was used. Run `python -B -m unittest autonomy.test_telemetry -v` using the existing Codex runtime interpreter's absolute path. Actual test results are reported in the delivery JSON; existing acceptance state is unchanged. CURRENT_STATUS.md and FILE_MANIFEST.md are absent in this worktree; the existing supervisor document, daily report and independent review were read instead.

风险：只验证结构和时间，无法证明上游计数事实或拦截获准自由标签中伪装的秘密；调用方来源白名单不得放凭据。文件系统需保持可信且读取期间无恶意并发替换；没有实现对抗恶意本地写入者的原子无链接打开，也没有签名验证或全目录数量预算。下一步由父代理独立审核源码及失败路径；未来由正式授权通道提供真实脱敏feed、可信来源策略和持久去重后，另行验收。当前生产指标全部未知。

Risks: validation proves structure and timing, not factual counts or secrets disguised as approved labels; caller allowlists must never contain credentials. The filesystem must remain trusted without hostile concurrent replacement during reads. Atomic no-follow opening against hostile local writers, signature verification and a directory-wide file-count budget are not implemented. Next the parent independently reviews sources and failure paths. A future authorized feed, trusted source policy and persistent deduplication require separate integration and acceptance. Current production metrics remain unknown.

自检：中英双语；包含结果、未执行、风险、数量规则、下一步；仅合成数据，无真实敏感信息；未把开发测试当作生产接通或验收。

Self-check: bilingual; results, non-executed work, risks, count semantics and next steps included; synthetic data only, no real sensitive information; development tests are not production connectivity or acceptance.
