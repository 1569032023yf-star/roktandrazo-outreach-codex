# 观测客户端独立审核 / Independent observation-client review

结论：APPROVED_SCOPED_READ_ONLY_CLIENT。仅审核tools/city_channel_client.py与tests/test_city_channel_observations.py，对照本地交接OBSERVABILITY_CONTRACT.md；无阻断发现。
Verdict: APPROVED_SCOPED_READ_ONLY_CLIENT. Reviewed only the candidate client and its observation tests against the local observability contract; no blocking finding identified.

新增runtime/city/provider-audit/scheduler/safe均由argparse闭集选择，固定loopback POST /v1/{operation}，无任意URL、SQL、生产路径、refresh或执行器指令入口。数值范围严格int排除bool；run_id与城市名称fullmatch；跨operation参数拒绝；新观测拒绝release/operation标识。safe请求体为空，不触发refresh。凭据读取沿用既有本机受控桥接，不输出token，候选diff未修改桥接。
All five additions use closed argparse choices and fixed loopback POST endpoints, without arbitrary URL/SQL/production-path/refresh/executor input. Numeric ranges exclude booleans; run IDs and city names use fullmatch; cross-operation parameters and release/operation IDs on new observations are rejected. SAFE sends an empty body and never refreshes. Credential loading remains the existing local mechanism without token output; the bridge was not modified.

独立6项合同测试通过。另以假凭据载入器及假HTTP执行main完整路径5次，分别核对URL、POST、精确body、45秒超时及输出artifact；全部通过。两文件测试前后SHA一致，见tests.json。未读取真实凭据，未发真实HTTP，未修改源码。
Six independent contract tests pass. Five additional full-main runs use synthetic credential loading and HTTP responses, verifying URL, POST, exact body, 45-second timeout and output artifacts. All pass, with unchanged pre/post source hashes in tests.json. No real credentials or HTTP were used and no source was modified.

候选可进入真实只读验收，但此前未实调的事实保持不变。下一步由既有授权调用runtime(--limit 1)、city(--city Cooperstown)、provider-audit(--hours 24)、scheduler(--hours 24)、safe(无参数)，只将响应存ignored受限证据目录，并逐项核对http200、schema、test_mode和脱敏。不能以本次mock或外部41/41报告代替候选CLI真实运行；也不能据新endpoint存在就把SAFE或城市根因宣称已验证。
The candidate is ready for live read-only validation under existing authorization, but has not yet been live-invoked by this reviewer. Validate each fixed operation with bounded parameters and store receipts in an ignored evidence directory, checking HTTP status, schema, test mode and redaction. Neither these mocks nor the external 41-test report substitutes for live execution of this candidate CLI. Endpoint availability alone establishes neither SAFE authority nor the city root cause.

限制：合同支持城市数值ID但候选仅名称，这是更窄安全子集；raw响应持久化不是脱敏消费者或业务资格验收；旧register/apply能力不在本diff扩权范围。所有报告中英双语。
Limitations: numeric city IDs supported by the contract are omitted as a narrower safe subset; raw receipt persistence is not a redacting consumer or business-qualification acceptance. Existing register/apply capabilities were not expanded by this diff.
