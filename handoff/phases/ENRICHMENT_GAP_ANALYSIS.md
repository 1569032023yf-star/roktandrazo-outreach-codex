# 安全补库断点 / Safe Lead Replenishment Gaps

日期 / Date: 2026-09-08。依据 / Evidence: development code and read-only snapshot; no network rechecks.

中文：首要问题是商户发现到合格库存之间没有闭环。库存任务用 Broad Ready 判定完成，而 FSP 使用 V2；“33 条库存”不是“33 条可发新线索”。以下严格区分静态缺陷、快照观察和待验证影响。

English: The primary problem is an incomplete path from merchant discovery to qualified inventory. Inventory completion uses Broad Ready, while FSP uses V2. A count of 33 is not 33 send-ready new leads. Static defects, snapshot observations and unverified impacts are distinguished below.

| 编号 / ID | 断点与证据 / Gap and evidence | 影响 / Impact |
|---|---|---|
| E1 | `browser_maps.py:214` 默认 `mode='file'`；赋值 `mode or os.getenv(...)`；`base.py:67` 无参构造。副本 env=direct。 / Nonempty file default masks configured direct mode. | 无缓存时返回 no_data_available，不能凭 env 开启浏览器发现。历史有 4 次该状态，但不能断言全部由此缺陷引起。 / Uncached queries cannot activate direct scraping from env alone; four historical no-data requests observed, causality not fully established. |
| E2 | `web_directory.py:177` 明确输出 `website=''`；`discovery_service.py:687` 转人工 website_lookup_required；`:414` 缺官网直接返回；后处理状态集合不含 manual_review_needed。 / Directory intentionally leaves official website blank; no automatic resolver consumes resulting manual-review rows. | 257 条 leads 待查官网；目录 280 条 discovery results 全部无官网，248 条 manual_review_needed。 / 257 leads need website lookup; all 280 directory discovery rows lack websites, 248 in manual review. |
| E3 | `bd_orchestrator.py:502` 仅选已有官网且空邮箱；`discovery_service.py:197` 仅处理有限 staging 状态。 / Recovery requires existing websites and staging processes only selected states. | 缺官网队列没有消费者；网络失败/identity_review 转人工后缺少自动重试闭环。 / Website-less and diverted review/recovery queues lack a complete automated retry consumer. |
| E4 | `inventory_monitor_executor.py:404,422,440,469` 生成说明句作为 snippet；`manual_email_workflow.py:77` 要求 snippet 是网页子串。 / Scanner synthesizes prose, verifier requires literal page evidence. | 静态可确认的契约冲突，正常提取仍可能被拒；本快照 inventory_lane 未记录该失败原因，不能声称已有 N 次该故障。 / Confirmed contract mismatch with potential rejection; no matching historical inventory-lane failure count in snapshot. |
| E5 | `bd_orchestrator.py:510` 只要存在任意 inventory_lane 提交就排除，与成功/失败/可重试无关。 / Any submission permanently excludes candidate, irrespective of result. | 短暂失败可能永久失去重试；7 次 manual_send_only、190 次 previously_sent、仅 1 次 promoted（198 次提交，不等于 198 个商户）。 / Temporary failures can lose retry eligibility; 198 submissions comprise 7 manual-only, 190 previously-sent and one promotion, not 198 unique merchants. |
| E6 | `bd_orchestrator.py:328,471,478` 以 Broad Ready 完成；`:108` 预发送使用 V2。 / Inventory and pre-send use different readiness predicates. | 09-07 inventory completed actual=33，pre-send actual=0，outreach=final_send_plan_missing。停止补库时机错误。 / Completion stops replenishment despite zero plan entries. |
| E7 | `lead_hygiene_gate.py:10,97` 零售限 TN/AR/KY；discovery/manual promotion 调用该函数；active_state=NY。 / Tri-state A0 promotion is still upstream of nationwide/state-selected discovery. | 新 NY 官方邮箱可被旧 A0 规则转人工，尚未到 V2。不是应放松 V2，而是要重新界定上游 A0 与安全候选契约。 / NY official contacts can be diverted before V2. Redefine upstream promotion contract without weakening V2. |
| E8 | `BrowserMapsProvider.search_places` fallback 匹配 query/city/state，未校验 cursor；direct scraper 不接受 cursor，next cursor=len(results)。 / Cache fallback ignores cursor; direct scraping has no cursor parameter. | 翻页可能反复返回同一批，浪费预算并影响耗尽判断。需要多页 fixture 证明修复。 / Potential repeated pages and misleading exhaustion; requires multi-page fixtures. |
| E9 | `http_scan_website` 原始 HTML regex + 首个 set 元素；重定向后未返回最终域；curl `-k` 且无 HTTP 成功验证。 / Raw-HTML regex, nondeterministic first match, no final-domain provenance, curl disables TLS verification and lacks HTTP-success validation. | 无法保证“官方可见邮箱”；脚本/隐藏内容/跨域页面可能被当证据。直接入库的 safe_write_a0 风险更高。 / Cannot guarantee visible first-party evidence; hidden/script/redirect content can be misclassified, especially through standalone writer. |
| E10 | 扫描 deadline 25 秒，但请求仍 timeout=10，curl 独立追加最长 15 秒；失败/无邮箱候选缺 next_retry_at，5 轮可重复查询。 / Nominal deadline is not a hard end-to-end bound and negative candidates lack retry scheduling. | 任务时长与失败预算不确定，空结果重复耗时。 / Unbounded relative to advertised budget and repeated wasted scans. |

## 需要保留的资格边界 / Eligibility boundaries to retain

中文：V2 目前明确 MX_OK 才通过；NXDOMAIN/NULL_MX/NO_ROUTE 阻断，DNS 暂不可用不可视为通过；证据要求 90 天内时间戳。不要把 guessed_email、directory/email 或失败 HTTP 结果直接改成 official_page_visible。SAFE_FSP 必须由现有 V2、MX、历史抑制、时区和计划规则实际接受后才计数。

English: V2 requires explicit MX_OK. NXDOMAIN, NULL_MX and NO_ROUTE block; unavailable DNS is not success. Evidence freshness requires a timestamp within 90 days. Never relabel guessed, directory or failed-HTTP evidence as official-page evidence. Count SAFE_FSP only after existing V2, MX, history/suppression, timezone and plan rules accept the candidate.

## 建议的补库契约 / Proposed replenishment contract

中文：为每个商户持久化发现来源与身份键 → 官网候选列表 → 官方身份匹配证据 → 实际页面 URL/最终 URL/抓取时间/可见原文片段与哈希 → 确定性邮箱选择 → V2/MX 判定与原因 → 可进入下一批 FSP 的资格快照。明确区分未发现、网络待重试、身份待审、无公开邮箱、已联系/退订、可发六类结果。失败不改写为成功，已联系商户不回流为新外联。

English: Persist merchant provenance and identity → website candidates → official-identity evidence → requested/final URL, fetch time, visible excerpt and content hash → deterministic email selection → V2/MX result and reasons → eligibility snapshot for the next FSP. Separate not-found, network-retry, identity-review, no-public-email, already-contacted/suppressed and eligible outcomes. Failures must not become successes and contacted organizations must not become new outreach.

中文：补库结束指标应为去重后可进入 FSP 的组织数及每层淘汰原因，不是 Broad Ready 或 A0 标签数。工作日库存目标 30 与发送上限 40 是不同政策，不能暗中提升配额；应在后续开发计划里明确需求缺口和缓冲策略。未进行真实 V2/MX 重算，所以此处不声称“现在 V2 恰好 0”；证据是最近实际计划产物为 0。

English: Stop based on unique organizations admissible to FSP and per-stage rejection reasons, not Broad Ready/A0 labels. Inventory target 30 and send cap 40 are different policies; do not silently change quotas. Define capacity and buffering explicitly in later development. V2/MX was not re-run live, so zero current V2 eligibility is not asserted; zero recent plan output is observed.
