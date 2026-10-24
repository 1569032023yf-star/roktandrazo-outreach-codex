# Provider 最终独立复审 / Final Independent Provider Review

日期 / Date: 2026-10-25 (Asia/Taipei)
Reviewer: independent reliability agent
Candidate: `8d63d2d45393509589261a1ddd0bbcf650a0d1b2`
Base: `eceb019b70a3b24a1d90a4efeebd3692c446dd2c`
Verdict: **PASS_WITH_RELEASE_GATES_PENDING**
REVIEW_PASSED=true
RELEASE_READY=NOT_ESTABLISHED_BY_THIS_REVIEW
PRODUCTION_DEPLOYED=NOT_ESTABLISHED_BY_THIS_REVIEW
LIVE_PROVIDER_ACCEPTED=UNKNOWN
BUSINESS_GROWTH_VERIFIED=UNKNOWN

## 复核结论 / Review result

中文：在前次逐项审查相对 eceb019 的完整诊断变更基础上，独立复核本固定 SHA 相对 475b359 的全部差异。前次两项 P1 阻断均已解决：卡片操作异常通过 classify 保留明确超时、代理、DNS及浏览器退出证据，未知异常保持 UNKNOWN；selector 等待失败不再根据 feed 存在猜测 DOM 变化。直接单店成功路径恢复空后继游标，避免本候选新增重复搜索。未发现当前审核范围内新的阻断问题。旧拒绝报告保存在 REVIEW_REJECTED_475b359.md。

English: Building on the previous complete review of diagnostic changes against eceb019, independently reviewed every change from 475b359 to this pinned SHA. Both prior P1 blockers are resolved: card-operation failures preserve explicit timeout, proxy, DNS and browser-exit evidence through classify, with unknown errors remaining UNKNOWN; selector failures no longer infer a layout change from feed presence. Direct single-place success again has an empty continuation cursor, avoiding additional repeated searches introduced by the earlier candidate. No new blocking finding was identified within this review scope. The previous rejection is preserved as REVIEW_REJECTED_475b359.md.

## 合同、资源及数据边界 / Contract, resources and data boundaries

中文：固定 code:stage 合同位于已有 discovery/models.py；生产 Provider 直接依赖 models，不依赖开发兼容 re-export 新文件。异常文字不写入诊断字段，缓存错误通过 allowlist 校验；缺依赖、启动、代理、DNS、超时、退出、HTTP429/访问受限/验证页均有封闭分类，不能识别则 UNKNOWN。结构/字段形状检查与错误状态阻止把失败伪装成空成功。正常空结果保留成功语义。资源在 finally 分别尝试释放 page、context、browser，任何单次关闭失败不会跳过其余释放，保留主要故障。没有加入验证码、封锁或来源政策规避；旧反检测参数已移除。

English: The fixed code:stage contract resides in existing discovery/models.py; production Providers depend directly on models rather than the new development compatibility re-export. Exception text does not enter diagnostic fields, and cache errors pass an allowlist. Missing dependencies, launch, proxy, DNS, timeout, process exit, HTTP429, access restrictions and verification pages have bounded classifications, with unrecognized errors remaining UNKNOWN. Shape checks and error states prevent failure from masquerading as empty success. Normal empty results retain success semantics. Finally blocks independently attempt page, context and browser cleanup, continue after individual cleanup failures and retain the primary error. No challenge, access-block or source-policy bypass was added; old anti-detection options were removed.

中文：Service 非 ok 页在结果插入和成功页游标 checkpoint 前返回。新增真实临时 SQLite 测试验证第一页成功后第二页 partial，随后三次重开连接仍停留 page2；数据库始终只有一个已成功结果，失败页商家不插入，不产生 leads，不重复消费成功页。测试模拟 orchestrator 的 commit 边界，不代表真实崩溃恢复、生产 Windows 进程树回收或真实在线验证。

English: Service returns non-ok pages before result insertion and successful-page cursor checkpoint. The new temporary SQLite test verifies first-page success followed by second-page partial failure and three reopened connections remaining at page2. Exactly one successful result remains, failed-page merchants are not inserted, no leads are created and the successful page is not reconsumed. The test simulates the orchestrator commit boundary; it does not establish real crash recovery, production Windows process-tree cleanup or live online validation.

## 行为变化须明确 / Behavioral changes must remain explicit

中文：候选包含诊断及独立确定性缺陷修复，不应描述成纯日志变更。详情操作错误由静默空字段变为 partial/failure；异常布局不再当空成功；缓存形状严格校验；成功缓存限定实例目录；直接单店结果统一身份标准化，但仍保持终止游标。上述边界按故障注入及已有 Service 非 ok 合同审核通过，不代表历史生产 scrape_error 根因已修复。生产发布只能包含既有 models.py、browser_maps.py、browser_maps_scraper.py，实际包仍须通过独立字节/回滚及正式部署门禁。

English: The candidate includes diagnostics and independently demonstrated deterministic fixes and must not be described as logging-only. Detail-operation errors become partial/failure rather than silently empty fields; abnormal layouts no longer become empty success; cache shapes are strict; success caching uses the instance directory; direct-place results receive normalized identity while keeping a terminal cursor. These boundaries passed fault-injection review against the existing Service non-ok contract; they do not establish that historical production scrape_error was fixed. The production package must contain only existing models.py, browser_maps.py and browser_maps_scraper.py and still requires byte/rollback verification and formal deployment gates.

## 独立测试 / Independent testing

命令 / Command:
`python -B -m unittest tests.test_provider_failure_diagnostics tests.test_browser_maps_direct_place tests.test_browser_maps_integration -q`

中文：固定 SHA 上独立运行 26 项，全部通过（24 项诊断/服务测试，加2项 direct/integration 相关测试），耗时3.450秒。覆盖此前两项误分类修复、direct终止游标、临时SQLite断点重开、部分失败结果不消费、缓存重放、字段形状、脱敏、资源释放和未知结果。未启动完整 suite；完整回归由父级执行，不能据此称全部项目测试全绿。

English: Independently ran 26 tests on the pinned SHA: all passed in 3.450 seconds, comprising 24 diagnostic/service tests and two direct/integration tests. Coverage includes both prior classification fixes, the terminal direct-place cursor, temporary SQLite restart checkpoints, non-consumption of partial failures, cache replay, field shape, redaction, resource cleanup and unknown outcomes. No full suite was launched; the parent runs full regression, so this result does not assert the whole project is green.

## 未执行、风险和下一步 / Not executed, risks and next steps

中文：没有真实浏览器联网、生产数据库访问、正式 Inventory、邮件、register/apply或生产写入。审核只写报告，未修改源码或发布清单。历史线上失败根因仍 UNKNOWN；线上DOM变化及来源响应未实测。下一步固定包字节并验证三个既有文件生产before-SHA、正反补丁、独立回滚与安全窗口，再经既有正式授权通道 register/preflight/apply/status，保留唯一Inventory及SMTP关闭；按自然运行验证业务结果。生产兼容与发布就绪不能仅由本源码审核推断。

English: No real browser networking, production database access, formal Inventory, email, register/apply or production write occurred. Only review reports were written; source and release manifests were not changed. Historical online root cause remains UNKNOWN, and live DOM/source behavior was not tested. Next pin package bytes and verify the three existing production before-SHAs, forward/reverse patches, independent rollback and safe window before the existing authorized register/preflight/apply/status flow, preserving the sole Inventory and disabled SMTP. Validate business results through natural runs. Source review alone cannot establish production compatibility or release readiness.

中文：报告自检通过：中英双语、执行与未执行、数量、风险和下一步完整；无 Token、代理地址、Cookie、客户资料或完整请求 URL。测试输入均为固定合成夹具。

English: Report self-check passed: bilingual results, unperformed actions, counts, risks and next steps are included, without tokens, proxy addresses, cookies, customer data or complete request URLs. Test inputs are fixed synthetic fixtures.
