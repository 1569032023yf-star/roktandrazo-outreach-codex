# PHASE 5A.1 四模板进度 / Four-template progress

## 里程碑 A / Milestone A

中文：四模板已在开发注册表注册并以完整 SHA-256 锁定。TikTok 版采用本次用户提供的候选英文；普通零售去掉 DDP、低起订量及样品表述。品牌定制及转介绍保留。info@ 仍优先按核实业务类型路由。

English: All four templates are registered in development with full SHA-256 locks. TikTok uses the candidate English supplied for this task. Retail fallback removes DDP/minimum-order/sample emphasis. Custom/referral variants remain. Verified business type takes precedence over an info@ prefix.

中文：仅相关零售且日期/平台/商品身份证据通过时优先 TikTok。证据不齐回退普通零售；人工指定也不能绕过。正式排名渲染明确历史日期和类目范围，纯文本完整保留；HTML CID 仅使用哈希锁定原图，不使用外链或像素。原始 PNG 未改动。内部未核实候选有醒目标注，不嵌未核实图片。当前真实截图证据仍未通过，不声称当前第一。

English: TikTok takes priority only for relevant retailers with approved date/platform/product evidence. Missing evidence falls back to retail; overrides cannot bypass it. External rendering binds the historical date/category in full plain text and embeds only the pinned original through CID, without remote images or pixels. The original PNG is unchanged. Pending internal previews are conspicuously marked and omit unverified imagery. Actual ranking evidence remains unverified; no current-rank claim is made.

中文：最终 119 项定向测试全部通过，四套内部文字/HTML 预览已生成，无真实 SMTP 调用。独立 QA 发布申请清单已生成，尚未获正式入口登记。旧 V5 历史数据未改。完整可比结果见下；里程碑 B 的回归目标通过，独立审查签核仍待完成。

English: All 119 final targeted tests passed. Four internal text/HTML previews were generated with zero actual SMTP calls. An independent QA release request manifest exists but is not registered at a supported entry point. V5 historical data was not changed. Comparable results follow below. Milestone B meets its regression target; independent review sign-off remains pending.

## 回归修复与审阅 / Regression fixes and review

中文：真实兼容性修复包括：全部输入不合格时不读取发送策略或写入预算；历史 follow-up 冻结计划在创建授权前阻断，保持历史只读；SMTP 名额预留前重新核对最新策略与冻结正文，避免证据日期或路由在发送中变化。旧 V5 渲染测试显式选用历史模板；新发信夹具迁移至 V6 完整正文、身份审核及有效组织字段。SMTP 接受后数据库异常的测试仍要求回滚，并验证持久停发阻止重发，而非恢复危险重试。

English: Actual compatibility fixes avoid policy/quota work for wholly ineligible inputs, block historical frozen follow-up plans before authorization without rewriting history, and revalidate frozen content against current policy immediately before SMTP reservation. Historical V5 rendering tests explicitly select legacy templates. New-send fixtures use full V6 content, reviewed identity and organization fields. The post-SMTP database-failure test still verifies rollback and now verifies the durable halt prevents retransmission rather than permitting unsafe retries.

中文：已进行与实现分开的自检轮次，检查模板/原图哈希、纯文本与 CID、info@ 路由、生产隔离、历史保护、持久预留及发送失败边界。此记录是 Codex 自检，不冒充第二位独立审查者的批准；独立审查尚无签核，完整客户发布不得据此放行。没有删除测试，也未放宽 V1/V2、MX、历史或发送授权。

English: A separate self-review pass inspected template/image hashes, plain text/CID, info@ routing, production isolation, history preservation, durable reservations and send-failure boundaries. This is Codex self-review, not approval by a second independent reviewer. Independent review is not signed off, so a complete customer release is not cleared. No tests were deleted and V1/V2, MX, history and sending-authorization gates were not relaxed.

## 真实内部测试 / Actual internal QA

中文：里程碑 C 的发信阻塞仅为正式 QA 发布/测试入口尚未登记。2026-10-20 00:38:37 +08 实测通道 health=200，新 QA release preflight=400 UNKNOWN_RELEASE_ID。登记申请见 GitHub issue #1。所有内部及未来客户发信始终使用现有腾讯企业邮箱 SMTP；1569***yf@gmail.com 仅为收件人，不使用 Gmail SMTP/API，也不请求 OAuth。Gmail 连接不是试发前置条件。用户人工检查收件箱、垃圾箱及原始认证头前，收件与 SPF/DKIM/DMARC 为 UNKNOWN。最多四封、每模板一封，不建立客户 FSP/授权、不启用全局客户 SMTP、不重试不确定结果。

English: The only sending blocker for milestone C is the unregistered supported QA release/test operation. Live verification at 2026-10-20 00:38:37 +08 returned health=200 and new QA release preflight=400 UNKNOWN_RELEASE_ID. Registration was requested in GitHub issue #1. All internal and future customer sending always uses existing Tencent enterprise SMTP; the Gmail address is a recipient only. Never use Gmail SMTP/API or request OAuth. Gmail connectivity is not a sending prerequisite. Receipt and SPF/DKIM/DMARC remain UNKNOWN until the user checks Inbox/Spam and original authentication headers. Limit QA to four messages, one per template, without customer FSP/authorization/global SMTP or ambiguous retries.

中文：生产默认使用比例尚未测得；这是条件优先级，不是固定配额。客户邮件本阶段为 0，生产客户发送关闭。机器字段及本次代码提交见同目录 PHASE5A1_VALIDATION_RESULT.json。

English: Actual production usage ratios are not measured. Routing is conditional priority, not a fixed quota. Customer messages for this phase are zero and production customer sending is disabled. Machine fields and code commit appear in PHASE5A1_VALIDATION_RESULT.json.

## 完整可比回归 / Comparable full regression

| 版本 / Version | Run | Pass | Fail | Error |
|---|---:|---:|---:|---:|
| Baseline 72bdd70 | 505 | 493 | 10 | 2 |
| Initial branch ec3c182 | 546 | 508 | 25 | 13 |
| Final code 0ce0b10 | 556 | 544 | 10 | 2 |

中文：同 Python 3.13、同 sys.path/cwd 启动、同开发隔离环境。最终新增回归为 0，全套未全绿；最终失败 ID 与基线完全一致。以下 26 条初始新增失败/错误记录（含子测试）已消除。

English: Same Python 3.13, sys.path/cwd startup and development isolation. Final new regressions: 0. The full suite is not green; final failing IDs exactly match baseline. All 26 initially added failure/error records below (including subtests) were eliminated.

- `test_compact_renderer.CompactRendererTests.test_apply_email_to_lead_propagates_metadata`
- `test_general_inbox_referral_routing.GeneralInboxReferralRoutingTests.test_exact_generic_local_parts_route_to_referral_template`
- `test_general_inbox_referral_routing.GeneralInboxReferralRoutingTests.test_existing_recipient_and_referral_metadata_freeze_into_fsp`
- `test_general_inbox_referral_routing.GeneralInboxReferralRoutingTests.test_named_or_non_exact_local_parts_keep_existing_direct_routing`
- `test_p0_runtime_semantics.P0RuntimeSemanticsTests.test_deferred_follow_up_is_preview_blocked_then_live_skipped`
- `test_p0_runtime_semantics.P0RuntimeSemanticsTests.test_dry_run_final_plan_is_zero_write_and_followup_is_previewed`
- `test_p0_runtime_semantics.P0RuntimeSemanticsTests.test_follow_up_live_success_updates_count_time_log_and_plan`
- `test_p0_runtime_semantics.P0RuntimeSemanticsTests.test_new_outreach_rechecks_live_lead_and_does_not_replace_skipped_entry`
- `test_p0_runtime_semantics.P0RuntimeSemanticsTests.test_outreach_dry_run_is_zero_write_and_ignores_live_window`
- `test_p0_runtime_semantics.P0RuntimeSemanticsTests.test_smtp_test_mode_only_writes_test_history`
- `test_preflight_gate.PreflightGateTestCase.test_all_clean_passes`
- `test_preflight_gate.PreflightGateTestCase.test_dns_cached_ok_within_24h_passes`
- `test_preflight_gate.PreflightGateTestCase.test_dns_stale_cache_is_replaced_by_successful_live_refresh`
- `test_review_workflow.ReviewWorkflowTests.test_b2_cannot_directly_enter_final_plan`
- `test_review_workflow.ReviewWorkflowTests.test_manual_never_enters_auto_final_plan`
- `test_sender_transaction.SenderTransactionTest.test_scenario_a_atomic_commit_success`
- `test_sender_transaction.SenderTransactionTest.test_scenario_b_second_run_skips_without_smtp`
- `test_sender_transaction.SenderTransactionTest.test_scenario_c_smtp_rejected_no_send_log`
- `test_sender_transaction.SenderTransactionTest.test_scenario_d_db_failure_rollback_then_retry_succeeds`
- `test_sender_transaction.SenderTransactionTest.test_scenario_e_lead_id_impersonation_rejected`
- `test_sender_transaction.SenderTransactionTest.test_scenario_e_lead_id_mismatch_rejected`
- `test_sender_transaction.SenderTransactionTest.test_scenario_e_non_int_or_empty_rejected (bad='abc')`
- `test_sender_transaction.SenderTransactionTest.test_scenario_e_non_int_or_empty_rejected (bad=None)`
- `test_sender_transaction.SenderTransactionTest.test_scenario_e_non_int_or_empty_rejected (bad=True)`
- `test_sender_transaction.SenderTransactionTest.test_scenario_g_sender_copy_failure_reported`
- `test_v6_bestseller_evidence.BestsellerEvidenceTests.test_actual_receipt_is_not_approved_evidence`

### 仍存在的基线问题 / Remaining baseline issues

- `test_dashboard_consolidated.TestSourceAudit.test_archived_dashboards_have_disable_marker`
- `test_inventory_followup.TestInventoryArchival.test_archived_scripts_have_disable_marker`
- `test_phase2b_safe_replenishment.SafeReplenishmentTests.test_directory_or_social_url_is_not_promoted_to_official_site`
- `test_phase2b_safe_replenishment.SafeReplenishmentTests.test_discovery_to_official_evidence_to_frozen_v2_dev_fsp`
- `test_phase2b_safe_replenishment.SafeReplenishmentTests.test_identity_mismatch_and_cross_domain_redirect_fail_closed`
- `test_phase4a2_v2_transport_regression.V2TransportRegressionTests.test_current_safe_replenishment_fixture_has_zero_v2_policy_diff`
- `test_phase4a3o_dev_db_routing.Phase4A3ODevDatabaseRoutingTests.test_explicit_development_copy_is_preserved_after_env_loader`
- `test_phase4a8q_identity_terminal_hotfix.IdentityTerminalHotfixTests.test_identity_review_is_durable_and_not_reselected`
- `test_phase4a8q_identity_terminal_hotfix.IdentityTerminalHotfixTests.test_linked_merchant_resolution_path_still_updates_website`
- `test_phase4a8q_identity_terminal_hotfix.IdentityTerminalHotfixTests.test_not_found_and_network_retry_keep_existing_semantics`
- `test_single_smtp_authority.TestSingleSmtpAuthority.test_archived_scripts_fail_closed`
- `test_website_resolver_lifecycle.WebsiteResolverLifecycleTests.test_next_lead_runs_after_timeout`

中文：本阶段未安装四模板到生产，未测得生产使用比例。真实内部及客户邮件均为 0；四封均无发送时间和 Message-ID，SMTP 接受状态为 NOT_SENT。登记申请不等于已登记：[GitHub #1](https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/1)。

English: No four-template production installation was performed this phase; production usage ratios are unmeasured. Actual internal/customer messages are both zero. All four have no send time or Message-ID, and SMTP status is NOT_SENT. A registration request is not registration: [GitHub #1](https://github.com/1569032023yf-star/roktandrazo-outreach-codex/issues/1).
