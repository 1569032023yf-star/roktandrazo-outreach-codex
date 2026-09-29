# PHASE 4A.8I — Bounce candidate header normalization / 退信候选邮件头规范化

## Scope / 范围

This is a narrow development-only fix from baseline `641b36b87af596a503cdcb8fb518eab66d5ffbb9`.  It changes only the bounce-candidate header type boundary and its regression test.  No production deployment, IMAP connection, SMTP operation, production database access, scheduler change, or send-path change occurred.

这是从基线 `641b36b87af596a503cdcb8fb518eab66d5ffbb9` 开始的开发环境窄修复。它只改变退信候选邮件头的类型边界及其回归测试。未发生生产部署、IMAP 连接、SMTP 操作、生产数据库访问、调度变更或发送路径变更。

## Root cause / 根因

`_fetch_bounce_candidates()` parsed mailbox headers and passed `Message.get("From")` and `Message.get("Subject")` directly to regular-expression matching.  Under the legacy/8-bit parser path, either value may be an `email.header.Header` object rather than `str`.  `re.Pattern.search()` rejects that object with `TypeError: expected string or bytes-like object, got 'Header'`, terminating the bounce scan.

`_fetch_bounce_candidates()` 解析邮箱邮件头后，直接把 `Message.get("From")` 与 `Message.get("Subject")` 传入正则匹配。在 legacy/8-bit 解析路径中，这两个值任一都可能是 `email.header.Header` 对象而非 `str`。`re.Pattern.search()` 会拒绝该对象并抛出 `TypeError: expected string or bytes-like object, got 'Header'`，从而终止退信扫描。

## Minimal correction / 最小修正

Both fields are converted with `str(value or "")` before regex matching and before being placed in the candidate tuple.  Missing headers remain empty strings.  Candidate patterns, bounce classification, suppression behavior, schema, scheduler, and recovery orchestration are unchanged.

两个字段都会在正则匹配前及写入候选元组前通过 `str(value or "")` 转为文本。缺失邮件头仍为空字符串。候选模式、退信分类、抑制规则、数据库 schema、调度和恢复编排均未改变。

## Regression coverage / 回归覆盖

The new offline test uses a fake IMAP client and parsed-header doubles.  It first reproduces the original failure class by giving a `Header` object directly to `_FROM_PAT.search()`, which raises `TypeError`.  It then exercises the real `_fetch_bounce_candidates()` filter with `Header` objects in both From and Subject and proves:

新增的离线测试使用假 IMAP 客户端和解析邮件头替身。它首先将 `Header` 对象直接传给 `_FROM_PAT.search()`，复现原始会抛出 `TypeError` 的失败类别。随后使用 From 与 Subject 均为 `Header` 对象的真实 `_fetch_bounce_candidates()` 过滤路径，并证明：

- bounce-like `MAILER-DAEMON` / `postmaster` headers are still selected; / 类退信 `MAILER-DAEMON` / `postmaster` 邮件头仍会被选中；
- selected tuple fields are `str`, never `Header`; / 候选元组字段均为 `str`，绝不是 `Header`；
- a non-bounce message remains excluded; / 非退信消息仍被排除；
- no production mailbox or database is involved. / 未涉及生产邮箱或数据库。

## Validation / 验证

| Check / 检查 | Result / 结果 |
| --- | --- |
| `tests.test_bounce_pipeline` | 22 passed; 0 failed; 0 errors / 22 通过；0 失败；0 错误 |
| `compileall bounce_pipeline.py tests/test_bounce_pipeline.py` | Passed / 通过 |
| `git diff --check` | Passed / 通过 |
| Standard offline project unittest | 424 passed; 0 failed; 0 errors / 424 通过；0 失败；0 错误 |

Existing test-only `ResourceWarning` messages about temporary poller-status file handles were observed but do not fail tests and are unrelated to this header normalization fix.

观察到既有测试关于临时 poller-status 文件句柄的 `ResourceWarning`，但不导致测试失败，也与本次邮件头规范化修复无关。

## Scope audit / 范围审计

- Production code changed: `bounce_pipeline.py` only. / 生产代码仅修改：`bounce_pipeline.py`。
- Test changed: `tests/test_bounce_pipeline.py` only. / 测试仅修改：`tests/test_bounce_pipeline.py`。
- No changes: `result_recovery_sync.py`, scheduling, SMTP/send execution, Final Send Plan, V2, MX, Inventory/discovery, or database schema. / 未修改：`result_recovery_sync.py`、调度、SMTP/发送执行、Final Send Plan、V2、MX、Inventory/discovery 或数据库 schema。

## Decision / 决定

`READY_FOR_PRODUCTION_REVIEW = true`.  This records a reviewed development fix only; production deployment remains separately unauthorized.

`READY_FOR_PRODUCTION_REVIEW = true`。这仅记录已完成评审准备的开发修复；生产部署仍需单独授权。
