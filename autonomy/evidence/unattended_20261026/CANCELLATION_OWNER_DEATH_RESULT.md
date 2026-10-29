# 完整离线所有者退出测试 / Whole offline owner-death tests

固定测试提交 / Pinned test commit: `e07a85e10e9494983d1d3d4ef609d70575e96275`。运行源码仍9b28eb9，主机合同源码仍922a696；本轮仅新增测试，不更改生产包。 / Runtime remains9b28eb9 and host contract922a696. This increment changes tests only, not the production candidate.

中文：实际开始2026-10-29T18:50:39+08，触发时间18:50:30+08；开始时主树干净、远端与本地01102c6一致，无既有supervisor锁或U1 Python测试进程。其他creator桥接进程保留。环境代理仅确认存在，未输出值或修改。用户给定附件路径缺少分隔点而不存在；纠正到用户.codex目录后可读，仅读取历史目的不覆盖现态。独立host工作树4d394cb不修改。本轮未创建调度器或生产锁，没有可用平台级45分钟硬时限设置；各真实子进程由25秒timeout硬性限制，组合执行正常结束。

English: Actual start18:50:39+08 against trigger18:50:30+08. The main checkout was clean, local/remote01102c6 matched, and no existing supervisor lock or U1 Python test process was present. An unrelated creator bridge process was preserved. Proxy presence only was inspected without values or mutation. The supplied attachment path was missing a separator; the corrected .codex path was readable and used only for historical purpose. The independent host tree4d394cb was untouched. No scheduler or production lock was created. No platform-wide45-minute hard-limit control was available; each real subprocess has a25-second timeout and the combined run completed normally.

## 实际覆盖 / Actual coverage

中文：新增两项真实完整适配器所有者进程退出测试。子进程自己创建并持有实际supervisor锁、执行合成backend、预留费用及取消意图，再以os._exit(74)退出；父进程没有存活的原lease。所有数据来自测试临时目录，没有真实外部副作用。

English: Two new tests terminate the entire offline adapter-owner process. The child creates and holds its own real supervisor lock, executes a synthetic backend, reserves cancellation cost/intent and exits via os._exit(74). No parent holds the original lease. All data resides in temporary test directories with no real external effects.

- 未知执行退出：实际进程死亡后，unverified关联树仍拒绝recover_lock和新lease；原锁字节及slot/budget/journal三文件SHA256保持不变，取消预算保留。 / Unknown execution exit: despite actual owner death, an unverified associated tree blocks recover_lock and new leases; lock bytes and all three ledger/journal hashes remain unchanged, preserving cancellation cost.
- 已有可信drained终态后退出：先经现有适配器核验合成签名回执并完成原执行结算，再退出；合法recover_lock成功、新lease不同，旧admission取消预留因BINDING_MISMATCH拒绝，重建backend调用0，取消费用和三文件字节保持不变。 / Drained terminal exit: existing adapter verifies synthetic signed terminal receipts and settles original execution before exit. Legitimate lock recovery succeeds; a fresh lease rejects cancellation under the old admission with BINDING_MISMATCH. Reconstructed backend calls remain0; cancellation cost and all three files remain unchanged.

中文：2项定向通过（0.971秒）；U1预算/slot/取消/真实进程故障及主机合同组合126项通过（15.052秒）。这补齐前一父锁持续存活测试的范围限制，但并非Windows服务死亡、注销、重启、真实取消送达或生产后端验收。合成drained回执不证明真实外部树已关闭。

English: Two targeted tests passed in0.971s; the combined U1 budget/slot/cancellation/real-process-fault and host-contract suite passed126 tests in15.052s. This extends the earlier surviving-parent-lock scope, but does not establish Windows service death/logoff/reboot, real cancellation delivery or production backend acceptance. Synthetic drained receipts do not prove closure of a real external process tree.

中文：独立审核PENDING，未将自检或测试成功称为独审。仅测试变更，不机械重复922a696已完成的833项基线/候选对比（同37失败17错误）。下次继续完整所有者退出后迟到回执/可信drain与现有锁恢复接口的离线绑定，未知效果不重放，未确认费用不退款；主机正式runtime/wrapper/publisher合同继续经原Issue2消费，不重复请求。

English: Independent review remains PENDING; self-inspection/testing is not independent review. Test-only changes do not warrant repeating the completed922a696833-test comparison with identical37 failures/17 errors. Next: offline binding of late receipts/trusted drain after whole-owner death to the existing lock recovery interface. Never replay unknown effects or refund unconfirmed costs. Consume formal host runtime/wrapper/publisher contracts through existing Issue2 without duplicate requests.

DEVELOPMENT_COMPLETE=false
RELEASE_READY=false
PRODUCTION_DEPLOYED=false
PRODUCTION_ACCEPTED=false
BUSINESS_GROWTH=UNKNOWN
allow_dispatch=false
allow_cancel_dispatch=false

无生产代码/配置/调度/数据库/SMTP修改，无新证据消费回执。 / No production code/configuration/schedule/database/SMTP mutation and no duplicate evidence-consumption receipt.
