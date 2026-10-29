# 所有者死亡后的迟到回执绑定 / Late-receipt binding after owner death

固定测试提交 / Pinned test commit: `45c621ac585d157f74aa3c020c6cbac830e60f88`。仅修改test_cancellation_owner_death.py，运行源码9b28eb9及主机合同922a696未改。 / Test-only change; runtime9b28eb9 and host contract922a696 remain unchanged.

中文：本轮实际开始2026-10-29T21:58:42+08，触发21:58:33+08。本地canonical可读，工作树干净、本地/远端1d7ece4一致，无既有U1 Python进程或supervisor锁；未触碰其他creator桥接进程。代理仅查存在性，不输出值。原附件路径不存在，纠正到用户.codex目录后可读，历史目的未替代现态。已读项目规则及前轮报告。现有Issue2最新仍6493117461，未有新operator合同，不重复请求或发布旧消费回执。

English: Actual start21:58:42+08 against trigger21:58:33+08. Local canonical was readable, checkout clean, local/remote1d7ece4 matched, and no U1 Python process or supervisor lock was present. The unrelated creator bridge was untouched. Proxy presence only was inspected without values. The original attachment path was absent; corrected .codex path was readable and historical purpose did not replace current facts. Repository rules and the prior report were read. Issue2 still ends at6493117461 without new operator contracts; no duplicate requests or prior-consumption receipts were posted.

## 新增合同 / Added contracts

- 中文：UNKNOWN所有者进程实际退出后，即使持有原合成签名终态回执，重建适配器也不能绕过缺失lease对账；精确EXPECTED_LOCK_REQUIRED，锁字节和slot/budget/journal哈希不变，backend调用0。
  English: Following actual UNKNOWN owner death, even synthetic signed terminal receipts cannot bypass the missing lease. Reconstructed adapter rejects with exact EXPECTED_LOCK_REQUIRED; lock bytes and all three file hashes remain unchanged, backend calls0.
- 中文：原所有者先通过可信合成drained回执完成结算、再退出，允许正常恢复dead verified_closed锁。新lease的新签名admission可重复消费原终态回执两次，结果幂等COMPLETED，三文件字节不变、取消费用仍reserved且charged=amount，backend调用0。
  English: If the original owner settles with trusted synthetic drained receipts before exiting, normal recovery of the dead verified_closed lock is allowed. A freshly signed admission under the new lease can consume the old terminal receipts twice idempotently as COMPLETED, preserving all three files and cancellation cost reserved at charged=amount, with backend calls0.
- 中文：新lease下正确签名但错run或错claim的迟到预算回执均BINDING_MISMATCH，拒绝发生在持久化变更前，三文件字节不变。
  English: Correctly signed late budget receipts carrying a wrong run or claim fail with BINDING_MISMATCH under the new lease before persistent mutation; all three files remain unchanged.

中文：新增3项；本文件5项通过2.379秒，最终精确错误码断言后5项复测2.556秒。组合129项通过16.380秒，最终变化仅收紧断言并单独复测。测试调用实际适配器、锁恢复及SQLite持久文件，而非另造恢复模型。子进程25秒硬timeout；平台无可设置的整轮45分钟硬终止入口，本轮远低于上限。

English: Three added tests; five file tests passed in2.379s and the final exact-error assertion rerun passed five in2.556s. Combined129 tests passed in16.380s; the final change only tightened that assertion and was rerun separately. Tests exercise actual adapter, lock recovery and persistent SQLite files rather than a parallel model. Child processes have25s hard timeouts; no platform-wide45-minute hard-termination control was available, and this run remained well below the limit.

中文：独审PENDING。这里的迟到是跨所有者进程的到达顺序，不代表超出签名有效期仍接受；合成时钟固定T+10。成功路径要求旧锁先已有verified_closed，未实现UNKNOWN死锁收到后来的drain证明后自动释放，也不证明Windows服务注销/重启或真实后端。下一步实现只读可信drain证据预检，绑定旧lock实例和持久claim/run，不发派发、不改锁、不退款；然后独审。旧833项全量对比已完成且源码未变，不重复或扩大结论。

English: Independent review PENDING. Late refers to cross-owner arrival order, not accepting expired signatures; the synthetic clock remainsT+10. Success requires the old lock already verified_closed. Automatic release of an UNKNOWN dead lock upon later drain proof is not implemented; Windows service logoff/reboot and real backend acceptance remain unproven. Next implement a read-only trusted-drain evidence preflight bound to old lock instance and persisted claim/run, with no dispatch, lock mutation or refund, then independent review. The completed833-test comparison is neither repeated nor expanded because runtime source is unchanged.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_dispatch=false
allow_cancel_dispatch=false

无生产代码、配置、数据库、调度、SMTP修改或手动采集。 / No production code/configuration/database/scheduler/SMTP changes or manual collection.
