# 双来源离线候选交接合同 / Dual-source offline candidate handoff

状态：开发完成，9项合成离线测试通过，待父代理独立审核；非生产验收。
Status: implementation complete with nine passing synthetic offline tests, pending independent parent review; not production acceptance.

接口 / Interfaces: `brand_acquisition.dual_source_handoff.export_observations(list)` returns a JSON-safe dictionary; `validate_handoff(payload)` reconstructs derived fields and rejects tampering. Neither performs network, file, DB or production writes.

中文：输入source仅google/osm，必需provider_id、source_url、带时区captured_at、name、非空location及64位package_sha256。可选site_candidate、email_evidence；邮箱证据必须含email、source_url、captured_at及包含该邮箱的excerpt。保留原始来源身份、时间、地点、网站候选、邮箱证据和包哈希，拒绝缺失结构证据。不验证哈希对应文件、URL所有权、地理真实性或provider来源签名；文本完整不等于真实来源。

English: source is google/osm; provider_id, source_url, timezone-bearing captured_at, name, nonempty location and a 64-hex package_sha256 are required. Optional site_candidate and email_evidence retain discovery facts. Email evidence requires email, source_url, captured_at and an excerpt containing that email. Missing structural evidence is rejected. File/hash correspondence, URL ownership, geographical truth and provider signatures are not verified; complete text does not establish authentic provenance.

中文：复用BrandCandidate默认资格和无数据库配置的HistoryChecker，history始终UNKNOWN；输入safe/live/history/ownership声明从allowlist排除。候选标记DISCOVERY_ONLY、UNVERIFIED_IMPORT、资格PENDING、safe=false；business_email与official_website不填，网站留official_site_candidates，邮箱留observations证据。只有既有资格流程可以后续核实；本接口不引入SAFE规则，不连接44条专用入口，也不接受生产数据库路径。

English: Reuse BrandCandidate defaults and HistoryChecker without a configured database, yielding UNKNOWN history. Imported safe/live/history/ownership assertions are excluded by an allowlist. Candidates remain DISCOVERY_ONLY and UNVERIFIED_IMPORT with PENDING qualification and safe=false. Leave business_email and official_website empty; retain websites in official_site_candidates and email evidence in observations. Only the existing qualification pipeline may verify them later. This interface adds no SAFE rules, does not connect the 44-record-specific entry point and accepts no production database path.

中文：同一source/provider_id只输出一个候选，完全相同观察去重，不同时间/名称/证据完整保留；不按名称合并。相同网站hostname（仅去www前缀）只给potential_duplicates引用，包括跨来源同域；不是注册域判定，不强并组织。不选择哪个矛盾观察是真的，candidate名称仅确定性展示，实际核验须检查全部observations。

English: Group only source/provider_id identities. Remove identical observations while retaining distinct timestamps, names and evidence; never merge by name. Matching website hostnames (only stripping www) annotate potential_duplicates, including cross-source matches, without merging organizations or claiming registered-domain equivalence. No contradictory observation is declared true: candidate name is only a deterministic display value and reviewers must inspect every observation.

验证 / Validation: `python -m unittest tests.test_dual_source_handoff -v` — 9 passed. Covers forged SAFE/live/ownership/history claims, no DB access, same-name different-domain separation, cross-source same-domain hints, missing evidence, email evidence validation, duplicate source observations, tampered exports and deterministic output. No network or package collectors ran.

风险与下一步：结构校验不能提供Google/OSM真实请求或同城对照验收。未实施生产导入、历史副本接入、地理边界过滤、真实性签名或发信。父代理独立审核后，保留独立来源回执与累计预算门禁，再经既有身份/官网/历史/MX流程处理，不把导入观察记作今日新增SAFE。

Risks and next steps: structural validation cannot establish real Google/OSM requests or same-city comparison. Production import, history-copy access, geographical filtering, provenance signatures and email sending remain unimplemented. After independent parent review, preserve separate source receipts and cumulative budget gates and pass candidates through the existing identity/site/history/MX pipeline. Imported observations are never today's new SAFE count.

自检 / Self-check: 中英双语、无凭据、结果/未执行/风险/下一步齐备，待审核不冒充验收。 Bilingual and credential-free with results, non-execution, risks and next steps; pending review is not acceptance.
