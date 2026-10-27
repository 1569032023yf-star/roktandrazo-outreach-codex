# Growth snapshot compatibility / 增量账本快照兼容检查

## 范围 / Scope
新增 `autonomy/growth_snapshot.py` 的 `inspect_snapshot(bytes, expected_sha256)`，仅处理调用方已经获准导出的完整快照字节；不接受文件路径。SHA256 只证明字节一致，**不能证明授权、来源真实性或新鲜度**。调用方负责批准来源与导出过程。
The inspector accepts only previously approved standalone snapshot bytes and their expected SHA256. A matching digest establishes byte identity only; authorization, provenance and freshness remain caller prerequisites.

## 实现 / Implementation
- 最大 16 MiB；只在 SQLite 内存连接 deserialize，query_only、trusted_schema=OFF，连接始终关闭。
- 拒绝 WAL 模式、非法页大小、长度与页数不一致、头部版本计数不一致；批准导出流程须生成一致的独立映像，不可直接复制带 WAL 或热 journal 的数据库。
- 精确匹配当前 SCHEMA 与 user_version；拒绝额外对象，随后 integrity_check，再读取状态计数。未知 reservation 状态直接拒绝，计数保持 UNKNOWN。
- 只输出固定原因枚举、兼容标记及 reserved/unknown/overrun 数量，不输出 SQL、路径、异常文本、组织或凭据。
- SQLite 每 1000 VM 指令检查预算，最大 2,000,000 指令及 2 秒软时限；最终也检查时限。内存载入受到字节上限约束，时限不是 OS 级硬中断。

The inspector uses an in-memory, query-only SQLite connection with trusted schema disabled and deterministic close. It rejects WAL and noncanonical/incomplete images, checks the exact known schema/version, then integrity and reservation states. Output contains only fixed reason codes and aggregate unresolved counts. SQL progress callbacks impose a VM budget and a soft wall-clock deadline; deserialize is size bounded, not an OS-killed operation.

## 验证 / Validation
`python -B -m unittest test_growth_snapshot -q`: 8 tests passed (2026-10-27).
Tests use actual temporary SQLite databases and cover compatible images, unchanged source bytes, reserved/unknown/overrun preservation, path/hash/size rejection, corrupt/truncated/WAL images, older or extra schema, unrecognized states, SQLite internal-prefix lookalikes, trailing bytes, and VM-budget exhaustion.
8 项真实临时 SQLite 测试通过；覆盖成功、源字节不变、未结算状态保留、路径/哈希/大小拒绝、损坏/截断/WAL、旧版本/额外对象、未知状态、内部名称近似对象、尾随字节及预算中止。

## 限制与未执行 / Limits and non-actions
兼容结果仅表示当前 schema 可读，不验证每一条业务字段语义，也不证明生产适配完成。无迁移、退款、重放、数据库覆盖或生产读写；不会取消任何未结算预留。没有执行生产 Inventory、邮件或配额变更。
Compatibility means schema readability only, not full business-row validation or production acceptance. No migration, refund, replay, restore, production access, Inventory, mail or quota change occurs. Unresolved reservations remain untouched.

## 状态与下一步 / Status and next step
本模块开发及定向测试完成；独立审核 PENDING，由父任务组织。未提交、未发布、未部署。整体 U1 与真实生产验收未由本模块证明。
Module implementation and targeted tests complete; independent review PENDING. No commit, release or deployment performed. Parent task should review these exact files and integrate only after approval; this does not establish U1 completion or live acceptance.
