# Phase 4A.3C measured production-copy throughput / 生产副本吞吐实测

Fresh authoritative production DB copy: `PRAGMA integrity_check = ok`. No production writes, SMTP, IMAP, FSP, or authorization occurred. / 新鲜权威生产库副本完整性检查通过；未写生产、未 SMTP、IMAP、FSP 或授权。

`TIMEOUT_STALLS_WHOLE_BATCH = false`。18 条可重试积压全部被处理；11 条需要外部解析，均在 201–393ms 内返回 `network_retry`，随后下一条继续。 / All 18 retryable rows were processed; 11 external-resolution attempts returned `network_retry` in 201–393ms and subsequent rows continued.

`TOTAL_ATTEMPTS = 11`; `COMPLETED = 0`; `TIMEOUTS = 0`; `P50_MS = 233`; `P95_MS = 393`; `MAX_MS = 393`。

`RETRYABLE_TOTAL = 18`; `ALREADY_HAS_OFFICIAL_WEBSITE = 7`; `DISCOVERY_ROW_ALREADY_HAS_WEBSITE = 7`; `ACTUALLY_NEEDS_EXTERNAL_RESOLUTION = 11`。已有网站没有触发 resolver 调用。 / Existing websites did not invoke the resolver.

`TIMEOUT_LAYER_BREAKDOWN = provider configuration: 11`。每次失败的精确原因是 `GOOGLE_MAPS_API_KEY is not configured`；不是网络慢、DNS、TLS 或超时饱和。 / Exact failure reason: `GOOGLE_MAPS_API_KEY is not configured`, not network, DNS, TLS, or timeout saturation.

`MAPS_RESULTS_SEEN = NOT_RUN`; `MAPS_NEW_UNIQUE = NOT_RUN`; `WEBSITE_RESOLUTION_ATTEMPTS = 11`; `WEBSITE_RESOLUTION_RESOLVED = 0`; `WEBSITE_RESOLUTION_TIMEOUTS = 0`; `OFFICIAL_EMAILS_FOUND = 0`; `FULL_EVIDENCE_CREATED = 0`; `V2_SAFE_BEFORE = 0`; `V2_SAFE_AFTER = 0`; `NEW_SAFE_UNIQUE_ORGS = 0`。

`FSP_40_SIMULATION_PASS = NOT_RUN`; `FSP_40_UNIQUE_ORGS = NOT_RUN` because SAFE is below 40.

`NETWORK_GUARDRAIL_PROVEN = true`; `LEAD_FACTORY_THROUGHPUT_PROVEN = false`; `READY_FOR_CONTROLLED_PRODUCTION_PATCH = false`。

## Publication record / 发布记录

This handoff publication reused the completed Phase 4A.3C measurement and did not rerun the investigation or network rehearsal. / 本次交接发布复用了已完成的 Phase 4A.3C 测量，未重新执行调查或联网演练。
