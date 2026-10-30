# U1恢复状态读取层独立审核 / Independent review of recovery-status inspection

固定源码 / Pinned source: `079792aa848aba979e2c0680eee73ec91b7f0b3a`。

中文：独立Reviewer读取了本固定提交的Git源码，并核对当前源码/测试与该提交无差异。`SCOPED_OFFLINE_REVIEW_PASSED=true`，仅适用于本次新增状态读取层；不是整体U1复审或生产批准。未修改实现代码或提交，未碰启动前存在的HTTP候选文件。

English: The independent reviewer read the pinned Git source and checked that current source/tests match it. `SCOPED_OFFLINE_REVIEW_PASSED=true` applies only to this added inspection layer, not whole-U1 reapproval or production approval. No implementation or commits were changed; pre-existing HTTP candidate files were untouched.

## 实际审阅 / Actual review

- `autonomy/recovery_status.py`：全部入口、快照头/哈希/schema/记录/资源限制、内存查询及输出权限。 / All input, header/hash/schema/record/resource checks, in-memory queries and authority outputs.
- `test_recovery_status.py`：真实SQLite固定夹具及真实恢复PREPARED故障、后继COMPLETED快照集成。 / Actual SQLite fixtures and integration with interrupted PREPARED recovery followed by COMPLETED inspection.
- `autonomy/cancellation_recovery.py`：真实schema1恢复日志、四字段固定binding、PREPARED/COMPLETED语义。 / Real schema1 recovery journal, four-field fixed binding and journal-phase semantics.
- `autonomy/growth_snapshot.py`：既有内存反序列化及大小/VM/时间限制模式。 / Existing in-memory deserialization and size/VM/time limits.

中文：该模块只接收bytes和独立预期SHA/身份，不接收路径；唯一数据库连接硬编码为`:memory:`，反序列化后query_only及trusted_schema关闭。精确schema拒绝额外对象/新版本；SQL参数绑定，不返回日志binding、handoff、旧token或异常文本。接受仅代表该快照记录形状可读，来源授权保持UNKNOWN。

English: The module accepts bytes and independently expected hash/identity, never a path. Its sole connection is hardcoded to memory, with query-only and untrusted-schema handling. Exact schema rejects extra objects/versions, SQL parameters are bound, and outputs contain no binding, handoff, old token or exception details. Acceptance only establishes readable snapshot shape; source authorization remains UNKNOWN.

## 发现与修复复核 / Findings and fix verification

1. 中文：原版本未限制binding JSON深度/大小，`json.loads`的RecursionError未捕获。已加入严格str及1024字符上限、RecursionError失败关闭；固定提交测试包含深层JSON、超长字符串和BLOB，确认不会泄漏内容或误授权限。 / English: The initial implementation had no binding-size bound and did not catch JSON RecursionError. The pin adds strict string/1024-character limits and fail-closed recursion handling. Deep JSON, overlong strings and BLOB tests verify safe rejection without disclosure or authority.
2. 中文：原NOT_RECORDED早返回路径绕过最终时间检查。已在记录分支前检查时间，存在/缺失身份均有超时负例通过。 / English: The original absent-record early return bypassed the final time check. Time is now checked before branching; timeout negatives cover both present and absent identities.

中文：修复后未发现本次离线状态读取层仍有阻断性源码问题。大小上限16MiB、SQLite进度限制及2秒检查是合作式资源门禁，不是线程/进程强制终止的生产硬时限；不能扩展此结论。

English: No remaining blocking source issue was found for this scoped offline layer after these fixes. The16MiB bound, SQLite progress limit and two-second checks are cooperative gates, not production process/thread hard termination.

## 独立实测 / Independent execution

`python -X utf8 -B -m unittest test_recovery_status test_cancellation_recovery test_growth_snapshot -q`

中文：23项通过，5.915秒。包含7项新增状态测试及既有恢复/快照测试，实际覆盖PREPARED、COMPLETED、NOT_RECORDED的区分，未知schema/记录/哈希/输入、损坏/截断/尾随/WAL快照、解析边界、脱敏与两条超时路径。真实恢复集成证明PREPARED故障后读取不改变文件，完成恢复后读取亦不改变文件，backend仍只调用一次。

English:23 tests passed in5.915s, including seven added status tests and existing recovery/snapshot tests. Coverage includes phase/absence distinction, schema/record/hash/input rejection, corrupted/truncated/trailing/WAL images, parse bounds, redaction and both timeout paths. Actual recovery integration checks byte-preserving reads after PREPARED interruption and after recovery completion, with only one backend call.

## 未验收与下一步 / Open gates and next steps

中文：COMPLETED仅为恢复日志阶段，execution_terminal/lock_closed/source_authorized仍UNKNOWN；派发、取消、对账、重放和生产验收标记始终false。该层未接入8791、SCM宿主、正式信任根或生产快照出口，也未证明实时一致性。旧833项比较及整体独审仅覆盖旧固定候选，不覆盖本新增源码；本报告不宣称最新候选NO_NEW_REGRESSION。后续由主线完成字节清单、隔离包导入、推送及受控接口集成。

English: COMPLETED is a recovery-journal phase only; execution terminal, lock closure and source authorization remain UNKNOWN. Dispatch, cancellation, reconciliation, replay and production acceptance remain false. There is no8791/SCM/production-trust/export integration or proof of live consistency. Earlier833-test comparison/whole-candidate review remains tied to its old pin and does not cover this addition; this report makes no new full-suite regression claim. The parent completes byte manifests, isolated imports, push verification and controlled interface integration.

中文：生产安装/服务启用/ACL修改/生产数据库操作/采集/SMTP均未执行；原Inventory保留。报告自检：中英双语、固定范围、实际数量、风险、未执行与下一步明确，无凭据、客户信息或代理地址。

English: No installation, service activation, ACL changes, production database operations, collection or SMTP occurred; the original Inventory is preserved. Self-check: bilingual, pinned scope, actual counts, risks, non-actions and next steps, without credentials/customer information/proxy addresses.
