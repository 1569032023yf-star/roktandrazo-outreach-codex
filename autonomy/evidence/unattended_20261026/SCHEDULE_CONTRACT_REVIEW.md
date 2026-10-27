# 调度缺槽合同独审 / Schedule missed-slot contract review

固定检查版本 / Inspected revision: `86772d3298b3e3fcdd448e30e6d646282974560b`。
范围 / Scope: autonomy/durable_slots.py::admit_due，签名missed列表与调用参数合同。
结论 / Verdict: **CHANGES_REQUIRED_FOR_SCHEDULE_PROTOCOL**。

## 实证发现 / Reproduced findings

1. **P1，121行：空调用参数绕过签名missed一致性检查。** 验签后的schedule含missed=[["missed", T]]，调用方省略missed时默认空tuple；`if missed`为假，最新slot被接纳pending，而缺失slot没有持久化。实际snapshot只有latest。这会静默遗漏已被正式证据声明的缺槽记录，不涉及创建额外执行，但破坏缺槽审计完整性。 / An authenticated nonempty missed list is ignored when the caller omits the optional argument. The latest slot is admitted while the missed slot is absent from durable state. This loses audit evidence without creating an extra execution.

   建议：将验签后的missed作为唯一规范来源，或对默认空值也进行无条件严格一致性检查；明确旧合同缺字段是否等同空列表。校验签名列表及元素形状、严格类型、数量及重复冲突，再进入事务。 / Use authenticated missed data as the canonical source or compare it unconditionally, including empty caller values. Explicitly define absent-field compatibility and validate shape, strict types, count and duplicate conflicts before mutation.

2. **P2，116行：未验证元素形状即解包，泄露非合同异常。** missed=(("only-one",),)实际抛出ValueError；missed=(None,)实际抛出TypeError，均不是LedgerError。调用方仅捕获协议异常时会中断恢复流程。这两个输入未发生数据库变更。 / Tuple members are unpacked before shape validation, producing raw ValueError and TypeError instead of the documented LedgerError boundary. Recovery callers catching protocol errors can fail unexpectedly. These inputs did not mutate the database.

   建议：每个元素先验证允许的sequence类型、长度恰为2，然后严格校验slot/due，统一返回INVALID_MISSED_SLOTS；不要把未验证输入拼入错误文本。 / Validate each item's permitted sequence type and exact arity before unpacking, then validate slot/due strictly and return a fixed INVALID_MISSED_SLOTS error.

## 最小复现 / Minimal reproduction

独立单进程、TemporaryDirectory SQLite、合成HMAC、真实EvidenceConsumer及LedgerEvidenceVerifier；固定clock，未联网或访问生产。 / Independent single-process reproduction used temporary SQLite, synthetic HMACs and real EvidenceConsumer/LedgerEvidenceVerifier with a fixed clock; no network or production access.

- 签名非空missed但调用省略：pending；snapshot仅latest。 / Signed nonempty missed, omitted argument: pending; snapshot contains latest only.
- 单字段元素：ValueError: not enough values to unpack (expected 2, got 1)。 / One-field member produces raw ValueError.
- None元素：TypeError: cannot unpack non-iterable NoneType object。 / None member produces raw TypeError.
- 复现脚本退出0；未执行全量或多进程测试。 / Reproduction exited 0; no full or multiprocessing tests ran.

建议定向回归覆盖：签名非空/调用空，签名空/调用非空，签名与调用完全一致，缺字段兼容，畸形元素及无副作用拒绝。 / Targeted regression should cover signed-nonempty/caller-empty, signed-empty/caller-nonempty, exact match, absent-field compatibility, malformed entries and mutation-free rejection.

本结论仅针对离线协议缺陷，不推断生产发生过缺槽丢失；未修改实现、未提交或部署。 / This finding concerns the offline protocol and does not assert that production lost missed-slot evidence. No implementation changes, commit or deployment were performed.

## 修复复审 / Fix re-review

固定修复 / Pinned fix: `41a5516370766464fa5a2a501203f5b406bfcf92`。
最终结论 / Final scoped verdict: **PASS_FOR_MISSED_SLOT_CONTRACT_FIX**，覆盖并关闭上述两项发现。 / Both findings above are resolved within this scope.

无条件比较签名missed与调用tuple，签名缺字段明确兼容空列表；签名元素严格list/str/int，调用元素先验证tuple和长度再解包，布尔due不能伪装整数。全部检查在事务前完成。 / Signed and supplied missed lists are now compared unconditionally; absent signed fields explicitly mean an empty list. Signed elements use strict list/string/integer types; caller elements are validated before unpacking, and boolean due values cannot masquerade as integers. Validation precedes transaction mutation.

独立运行 `python -B -m unittest test_durable_slots.DurableTests.test_signed_missed_slots_cannot_be_omitted -q`：**1 test passed，0.069秒，退出0**。该测试覆盖省略拒绝且snapshot不变、三种畸形元素统一LedgerError，以及完整匹配后s2持久化deferred/s3 pending。 / Independently executed the targeted test: **1 passed in 0.069 seconds, exit 0**. It verifies omission rejection without state mutation, three malformed forms yielding LedgerError, and matched evidence persisting s2 deferred and s3 pending.

仅定向修复通过；全量回归、多进程及生产调度验收未执行。Reviewer未改实现或提交。 / Only this targeted fix passes review; full regression, multiprocessing and production scheduling acceptance were not performed. Reviewer made no implementation change or commit.
