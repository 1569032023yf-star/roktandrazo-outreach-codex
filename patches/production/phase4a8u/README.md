# 4A.8U 最小候选发布包 / Minimal candidate release

本包只修改 `discovery/discovery_service.py` 与 `retail_city_queue.py`。新 release_id 为 `phase4a8u-city-timeout-terminal-recovery`。这是一份开发基线候选包，不能视为已登记或生产兼容性已通过。

This package changes only `discovery/discovery_service.py` and `retail_city_queue.py`. The new release ID is `phase4a8u-city-timeout-terminal-recovery`. It is a development-baseline candidate, not a registered or production-compatible release.

## 行为 / Behavior

官网解析连续网络失败最多记录三次，每次间隔至少 30 分钟。次数、时间、错误原因、原状态和原错误保存在原 staging 行的 JSON 中。预算耗尽后进入人工复核；有效的完整重试证据允许自动化城市收尾。没有证明官网不存在，没有创建无邮箱的可发送客户。

Website resolution records at most three network failures, at least 30 minutes apart. Counts, timestamps, errors, and original state/reason are preserved in the staging row JSON. Exhaustion moves the row to manual review; complete validated retry evidence permits automated city completion. This neither proves the absence of an official website nor creates a sendable customer without an email.

历史超时次数不会凭用户摘要补写。部署后仍需正常计划任务积累可核验的新重试记录。其他未完成候选、查询族和分页继续阻止城市结束。重复 Provider 命中保留重试状态。没有新增数据库表或迁移。

Historical attempts are not inferred from the user's summary. Normal scheduled runs must accumulate verifiable new retry records after deployment. Other unfinished candidates, query families, and pagination continue to block city completion. Duplicate provider hits preserve retry state. No database table or migration is added.

## 已验证与未验证 / Verified and unverified

`release_request.json` 固定开发基线前后 SHA 和补丁 SHA。`tools/build_phase4a8u_candidate.py` 仅在临时开发目录演练正向补丁及反向回滚，逐字节比较，并检查语法。它不是生产执行器。候选文件采用 LF；实际生产文件的字节、换行及 SHA 尚未取得批准的只读证据。

`release_request.json` pins development-base before/after hashes and the patch hash. `tools/build_phase4a8u_candidate.py` rehearses forward and reverse patches only in a temporary development directory, compares exact bytes, and checks syntax. It is not a production executor. Candidate files use LF; approved read-only evidence of production bytes, line endings, and hashes is still missing.

## 正式登记要求 / Registration requirements

1. 由现有通道运维身份提供两个目标的批准只读源码快照及 SHA；若不同，停止并重新制作兼容候选，不强制覆盖。
2. 为新 release_id 登记严格限定两个文件的发布与回滚操作，不复用 SAFE50。现有通道只有 SAFE50 单文件登记，Codex 不修改通道权限或注册表。
3. 所有目标一次完成预检，在官方 Inventory 排他锁覆盖的空闲窗口备份、逐字节核验、同卷原子替换。先替换 `retail_city_queue.py`，再替换 `discovery/discovery_service.py`。任一步失败必须回滚两个目标并验证；回滚顺序相反。不能在中间状态释放锁。
4. 验证发送冻结、无可执行发送授权、无并行 Inventory。当前只读预检的下次计划时间过期，安全窗口须取得新的有效证据。
5. 发布后只观察唯一 Inventory `1784775229336` 正常计划运行，取得重试轨迹、20/20 查询族、9/9 完成门禁、Cooperstown 关闭、Lake Placid 激活和 Provider 请求证据。SAFE 实时数值须经正式 MX 控制探针确认。

1. The existing channel operator must provide approved read-only snapshots and SHA values for both production targets. On mismatch, stop and rebuild a compatible candidate; never force replacement.
2. Register a new release restricted to these two files and rollback operations; do not reuse SAFE50. The existing channel has only the SAFE50 single-file registration. Codex does not modify channel permissions or its registry.
3. Preflight all targets together. Within one official Inventory exclusion lock and idle window, back up, verify exact bytes, and atomically replace each file on the same volume. Replace `retail_city_queue.py` first, then `discovery/discovery_service.py`. Any failure must restore and verify both files, in reverse order. Do not release the lock between replacements.
4. Verify sending remains frozen, no executable send authorization exists, and no parallel Inventory runs. The current read-only preflight has an overdue next-run timestamp; fresh valid safety-window evidence is required.
5. After deployment, observe only normal scheduled runs of Inventory `1784775229336`. Obtain retry history, 20/20 query families, 9/9 completion checks, Cooperstown closure, Lake Placid activation, and provider-request evidence. A current SAFE count requires the formal MX control probe.

## 报告缺口 / Missing report

指定的 `handoff/workbuddy/phases/PHASE4A8S_POST_DEPLOY_RUNTIME_ACCEPTANCE_20261019.md` 未在已检查的本地工作区、WorkBuddy 文件名检索和已同步 Git 历史中找到。需通过批准的交接路径提供该报告及发布后的正常运行报告。不能用开发夹具代替生产验收。

The requested `handoff/workbuddy/phases/PHASE4A8S_POST_DEPLOY_RUNTIME_ACCEPTANCE_20261019.md` was not found in the checked local workspace, exact-filename WorkBuddy search, or synchronized Git history. Provide it and post-release normal-run reports through the approved handoff path. Development fixtures cannot substitute for production acceptance.
