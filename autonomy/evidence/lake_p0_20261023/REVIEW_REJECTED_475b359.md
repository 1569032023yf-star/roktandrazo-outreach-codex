# Provider 固定候选独立审核 / Pinned Provider Independent Review

日期 / Date: 2026-10-24 (Asia/Taipei)
Reviewer: independent reliability agent
Candidate: `475b359d38f1e8eceb0190ee46c019b64fa81655`
Base: `eceb019b70a3b24a1d90a4efeebd3692c446dd2c`
Verdict: **CHANGES_REQUIRED**
REVIEW_PASSED=false
RELEASE_READY=false

## 阻断发现 / Blocking findings

### P1：卡片异常分类丢失明确证据 / Card classification discards explicit evidence

文件 / File: discovery/providers/browser_maps_scraper.py:185

中文：extract_place_data_from_card 把所有异常统一变成 RESULT_PARSE_ERROR。独立注入 TimeoutError、Playwright TargetClosedError 类型及含 net::ERR_PROXY_CONNECTION_FAILED 的错误，三者全部返回 RESULT_PARSE_ERROR:PARSE。这使本任务要诊断的浏览器退出、代理与超时再次被错误分类覆盖；已存在 classify 能识别它们。应保留明确传输/进程证据，仅对有确定解析证据的失败使用 RESULT_PARSE_ERROR；不明异常仍 UNKNOWN。补相应回归用例。

English: extract_place_data_from_card maps every exception to RESULT_PARSE_ERROR. Independent injection of TimeoutError, a Playwright TargetClosedError type and net::ERR_PROXY_CONNECTION_FAILED all returned RESULT_PARSE_ERROR:PARSE. Browser exits, proxy failures and timeouts are therefore overwritten even though classify recognizes them. Preserve explicit transport/process evidence, use RESULT_PARSE_ERROR only for established parsing failures, retain UNKNOWN otherwise, and add regression cases.

### P1：等待超时不能证明 DOM 变化 / Selector timeout does not prove a DOM change

文件 / File: discovery/providers/browser_maps_scraper.py:410-415

中文：wait_for_selector 超时后只要页面已有 feed，就改报 DOM_LAYOUT_CHANGED。正常 feed 先出现、结果卡片稍后加载或加载超时同样满足条件。独立模拟 feed=True + TimeoutError 得到 DOM_LAYOUT_CHANGED:DOM，说明把已知超时错误归因到未经证实的布局变化。现有 test_no_unproven_empty_result 固化该误判，测试通过不能证明分类合同成立。应保留超时；若要标记布局变化，需额外明确结构证据，不能仅凭未出现期望节点。

English: After wait_for_selector times out, the mere existence of a feed changes the result to DOM_LAYOUT_CHANGED. A normally loading feed whose cards are delayed or time out has the same observations. Independent feed=True plus TimeoutError injection produced DOM_LAYOUT_CHANGED:DOM, attributing an established timeout to an unproven layout change. test_no_unproven_empty_result currently codifies this misclassification. Preserve the timeout unless additional explicit structural evidence establishes a layout change.

## 已验证事项 / Verified scope

中文：合同迁入已有 discovery/models.py；两份生产 Provider 直接导入 models，兼容导出文件不是生产依赖。因此可用三个既有路径制作候选，避免旧包新增文件的 apply/rollback 不支持问题，但本审核没有验证重制发布包及生产字节。错误文本通道采用闭集 code:stage；缓存不可信错误文本不回显。正常空结果与非 ok 页分开；非 ok 页清空后继游标。资源 finally 逐一尝试关闭 page/context/browser，前一关闭失败不跳过后续关闭，原始错误优先保留。未看到新增验证码规避或封锁绕过。

English: The contract now lives in existing discovery/models.py and both production Providers import it directly; the compatibility re-export is not a production dependency. A candidate can therefore use three existing paths, avoiding the old added-file apply/rollback limitation, although this review did not verify the rebuilt package or production bytes. Error text uses a closed code:stage contract; untrusted cache error text is not echoed. Empty success and non-ok pages are distinguished; failed pages clear continuation cursors. Cleanup independently attempts page/context/browser closure and retains the primary error. No new challenge or access-block bypass was found.

中文：只读核查 DiscoveryService：先审计 Provider 页；非 ok 时记录失败并返回，尚未进入 result upsert 或成功页 checkpoint，因此部分失败结果不会在该路径作为成功数据插入或推进游标。现有22项诊断测试覆盖实例缓存重复读取不再次采集，但未包含正式生产等价 service 两页成功后失败的持久化重启集成测试；不要把代码检查表述成该集成测试已通过。

English: Read-only inspection of DiscoveryService shows provider audit first, then failure recording and return for non-ok pages before result upsert or successful-page checkpoint. Partial failures are therefore not inserted as success or used to advance that cursor on this path. The 22 diagnostic tests cover repeated instance-cache reads without another scrape, but do not include a production-equivalent persistent service restart after successful pages followed by failure. Code inspection is not proof that such integration testing passed.

## 诊断与行为变化 / Diagnostics versus behavior changes

中文：本候选并非纯日志增强。详情页错误从忽略改为整页 partial/failure；缺失布局从空成功改为失败；缓存形状严格校验；直接单店结果统一 _enrich（生成 place_id，并将原空 next_page_cursor 改成结果数量）；成功结果保存到实例缓存；去掉旧反检测参数。这些变化有些属于安全失败处理或真实缺陷修复，但发布说明应逐项明确，不能宣称采集行为完全不变。尤其直接单店额外游标可能触发下一次相同搜索，需保留原终止行为或独立证明新增请求预算符合合同。

English: This is not a logging-only change. Detail-page errors change from ignored failures to partial/page failure; missing layouts change from empty success to failure; cache shapes become strict; direct single-place results pass through _enrich, generating a place_id and changing an empty continuation cursor to the result count; success uses the instance cache; old anti-detection options are removed. Some are safety handling or real bug fixes, but release notes must enumerate them rather than claim unchanged collection behavior. In particular, a direct-place continuation cursor can cause another identical search and should preserve terminal behavior or independently establish the added-request budget contract.

## 测试、限制及下一步 / Tests, limitations and next steps

中文：独立运行 `python -B -m unittest tests.test_provider_failure_diagnostics tests.test_browser_maps_direct_place tests.test_browser_maps_integration -q`，24项通过（22项新增诊断及2项相关测试）。额外四次纯模拟注入重现上述两项阻断。没有运行完整测试、真实浏览器、网络采集、生产数据库或 SMTP；没有修改源码或发布清单。父级提供的初版完整回归为候选848/基线826，失败集合43 failures/17 errors相同，本次未独立重跑；不能称全绿。

English: Independently ran `python -B -m unittest tests.test_provider_failure_diagnostics tests.test_browser_maps_direct_place tests.test_browser_maps_integration -q`: 24 passed, comprising 22 diagnostic tests and two related tests. Four additional pure simulated injections reproduced the blockers. No full suite, real browser, live collection, production database or SMTP was used; no source or release manifest was modified. The parent reported the earlier full comparison as candidate 848/base 826 with matching 43 failures/17 errors; this review did not rerun it and does not call it fully green.

中文：先修复两项分类阻断，明确直接单店游标行为与服务重启集成覆盖，再固定新 SHA 复审和重建仅含既有路径的包。生产兼容、部署、实时 Provider 验收及业务增长均未由本审核建立。报告双语与敏感信息自检通过，仅包含合成异常类型和代码，无凭据、代理地址、Cookie或客户资料。

English: Fix both classification blockers, clarify direct-place cursor behavior and service restart integration coverage, then pin a new SHA for review and rebuild an existing-path-only package. This review establishes no production compatibility, deployment, live Provider acceptance or business growth. Bilingual and sensitive-information checks passed; only synthetic exception types and codes appear, with no credentials, proxy addresses, cookies or customer data.
