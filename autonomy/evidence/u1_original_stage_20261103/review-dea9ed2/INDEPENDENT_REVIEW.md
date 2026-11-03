# 原stage事件链独审 / Original stage event-chain review

固定源码 `dea9ed2d19c535ee0add6b564a5f48eca5777d0d`，结论 BLOCKED。独立75项通过，两个runner17.993+11.045=29.038秒，但额外故障探针仍重现P1，不能据已有测试通过批准。

Pinned source above: BLOCKED. All75 independent tests passed in29.038 summed runner seconds, but an additional failure injection reproduced a P1 defect.

## P1：锁更新零行仍提交job成功 / Zero-row lock release still commits job success

release_run_lock在原事务内先finalize_stage_locked，随后UPDATE原锁；它未在事务内验证rowcount，而是在with conn提交后返回rowcount==1。临时SQLite的BEFORE UPDATE触发器仅对Inventory release执行RAISE(IGNORE)，实际stage随后抛RELEASE_UNVERIFIED，但持久job为completed/50/0/target_met，原owner仍held。该探针未操作生产，也不声称现场存在该触发器；它明确验证数据库更新零行时不能满足“失败均rollback”。

The transaction finalizes the original job before updating the lock, but validates rowcount only after committing. An isolated trigger ignored the release update. Actual stage raised RELEASE_UNVERIFIED while the job remained completed/target_met and authority remained held. No production schema is alleged; this tests the promised rollback behavior under a zero-row write.

修复需在with conn事务内部要求UPDATE锁精确改变1行，否则立即raise回滚，使job与锁都保留原状。已有job更新ABORT负例正确，但不覆盖锁UPDATE零行。

Require exactly one affected lock row before transaction exit, otherwise raise and roll back both writes. Existing job-write ABORT coverage does not test this case.

## 其余范围 / Other reviewed scope

已核查实际stage入口绑定原running/live job与owner、不二次取锁、不fallback旧body，HTTP event→claim→真实Job子进程→预算终态→原job/release接线。新增ProcessBackend要求精确原authority，并将owner guard传至run_tree生命周期；丢失原owner的实际子进程测试保留UNKNOWN并验证cleanup。旧owner/旧receipt与取消alias修复仍在。业务SAFE和签名worker仍为隔离替身，正式Provider及完整受信命令未完成，不能称生产全链验收。

Reviewed actual source across stage identity, no reacquisition or legacy fallback, HTTP event/claim, real Job child, budget settlement and original finalization. Backend lifecycle guards use the exact original authority; real child tests exercise loss and cleanup. Prior owner/receipt/alias protections remain. Business SAFE and signed workers are doubles; formal Provider and full trusted command integration remain incomplete.

完整命令、摘要及限制见JSON。未改产品、生产DB、ACL、服务、Inventory、配置或凭据。所有生产门禁false。

Commands, pinned hashes and limits are in JSON. No product or production state was changed. Production gates remain false.
