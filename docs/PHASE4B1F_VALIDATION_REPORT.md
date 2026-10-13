# 4B.1F 验收交接 / Validation handoff

日期 / Date: 2026-10-13 (Asia/Taipei)

基线 / Baseline: `32cd1208405686aab42dae4e87e03cac290b85e7`

分支 / Branch: `codex/phase4b1f-authorized-live-directory-validation`

## 结果 / Outcome

已执行真实公开网页 Canary；完整资格链尚未通过。 / Real public-page canary executed; the full qualification chain remains unvalidated.

4 个来源首次各尝试 1 页；Toy Fair 修复后同一目录页追加第2次请求，其他来源不重复，均未超过每来源2页。成功保存4个真实HTML捕获与SHA256清单（3个不同URL）；没有捕获第一方官网页。 / Each of four sources initially attempted one page. After the Toy Fair fix, its same directory page was requested once more; other sources were not refetched. No source exceeded two requests. Four real HTML captures (three distinct URLs) and SHA256 manifest records were saved; no first-party website page was captured.

| 来源 / Source | 真实结果 / Live outcome |
| --- | --- |
| Toy Fair | 首次PARSE_EMPTY；修复真实布局后解析2469条名称/国家记录，预算保留22条；没有显式官网。 / Initially PARSE_EMPTY; capture-backed layout fix parsed 2469 name/country rows and retained 22 under the existing budget; no explicit websites. |
| GCA | HTTP 200 挑战/登录识别，ACCESS_RESTRICTED，停止且未绕过。 / HTTP 200 challenge/login detected, ACCESS_RESTRICTED; stopped without bypass. |
| NY NOW | 原页面解析 403 条目录记录；既有 90 总候选预算按 4 来源分配，保留 22 个待验证候选。 / Original page parsed 403 directory records; existing 90 total candidate budget allocated across four sources retained 22 unverified candidates. |
| ASTRA | HTTP 200，PARSE_EMPTY，未知结构或无可解析记录。 / HTTP 200, PARSE_EMPTY; unsupported layout or no parseable records. |

NY NOW 候选没有显式官网候选，产品分类与组织身份未经验证，不能计作已验证品牌；未猜测域名。 / NY NOW candidates contain no explicit official website candidates, verified product classification, or verified organizational identity; they are not verified brands. No domains were guessed.

```text
LIVE_CAPTURE_RECORDS = 4
LIVE_DIRECTORY_CANDIDATES_RETAINED = 44
LIVE_BRANDS_DISCOVERED = 0
LIVE_FIRST_PARTY_EMAILS = 0
OFFICIAL_SITES_VERIFIED = 0
MX_OK = 0
HISTORY_CLEAN_UNIQUE_ORGS_WITH_EMAIL = 0
```

没有批准的开发历史副本，历史门禁保持 UNKNOWN；没有执行生产数据库读写。 / No approved development history copy was available. History remains UNKNOWN; no production database reads or writes occurred.

## 修复与验证 / Fix and verification

首次默认开发保护导致 transport RuntimeError 中止。新增失败测试先证明入口未识别此保护；修复后 CLI 在 catalog、DNS、fetcher 和输出目录操作前返回 `DEVELOPMENT_TRANSPORT_BLOCKED` 与 requests_made=0。 / Initial default development guard caused a transport RuntimeError. New failing tests first demonstrated the missing preflight. The CLI now returns DEVELOPMENT_TRANSPORT_BLOCKED with requests_made=0 before catalog, DNS, fetcher, or output-directory work.

保持既有开发保护不变；仅调用已存在的受控公开网页模式（80/443），SMTP/IMAP 仍被阻断。沙箱禁网优先级高于受控模式，不会由入口自动启用受控模式。 / Existing development guards remain unchanged. Only the existing controlled public-web mode (80/443) was used; SMTP/IMAP remain blocked. Sandbox network policy takes precedence, and the entrypoint never enables controlled web automatically.

新增 5 个前置测试：默认阻塞、沙箱优先、无效 opt-in 阻塞、脚本启动 marker 阻塞、受控模式进入既有有界 runner；品牌相关回归共 78 项通过。 / Five preflight tests cover default blocking, sandbox precedence, invalid opt-in blocking, script-startup marker blocking, and controlled-mode entry into the existing bounded runner. All 78 acquisition regression tests passed.

真实捕获清单4条校验通过；离线replay去重得到60个discovery_only候选（离线每来源30预算与live每来源22不同），所有live验证指标为0。 / Four capture records passed manifest validation. Offline replay deduplicated to 60 discovery_only candidates (30 per source offline versus 22 live), with all live verification metrics at zero.

同目录临时恢复基线原文件执行全仓：449 项，2 失败、12 错误；修改快照452项同样2失败12错误，14项失败名称逐项一致。原因属于缺少 .env 与历史归档目录，不属于4B1F新增回归；日志完整保留，不降低断言。新增startup修复后78项相关回归再次通过，默认实际CLI前置阻塞实证通过。编译与 git diff --check 通过。 / Full-suite execution after temporarily restoring the original baseline files in the same directory: 449 tests, 2 failures and 12 errors. A modified snapshot ran 452 tests with exactly the same 14 failing names. Missing .env and historical archive directories are baseline/environment failures, not new 4B1F regressions. Complete logs are retained without weakening assertions. After the startup fix, all 78 targeted tests passed again and the actual default CLI preflight blocked successfully. Compilation and git diff --check passed.

## 复现 / Reproduction

仅在获准联网且沙箱未禁网环境调用；禁止设置或修改沙箱禁网变量来规避限制。 / Run live capture only in an authorized environment without a sandbox network prohibition. Never change the sandbox prohibition to bypass it.

```powershell
$env:ROKT_DEV_CONTROLLED_WEB='1'
python scripts/run_industry_directory_canary.py --mode capture-public --output-dir output/brand_acquisition/phase4b1f
python scripts/run_industry_directory_canary.py --mode validate-manifest --manifest output/brand_acquisition/phase4b1f/captures/capture_manifest.json
python scripts/run_industry_directory_canary.py --mode replay --manifest output/brand_acquisition/phase4b1f/captures/capture_manifest.json --output-dir output/brand_acquisition/phase4b1f/replay
```

本地证据位于 Git 忽略的 `output/brand_acquisition/phase4b1f/`，包含 captures、source_checkpoints、结果、测试日志、迭代记录；公开网页内容不提交。 / Local evidence resides in Git-ignored output/brand_acquisition/phase4b1f/, including captures, source checkpoints, results, test logs, and iteration records. Captured public-page contents are not committed.

当前阻塞：Toy Fair与NY NOW捕获记录缺少显式可归属官网，GCA访问挑战、ASTRA第三方脚本目录、未提供批准历史副本。Toy Fair已用来源特定结构修复，不把可定位布局问题当权限阻塞。 / Current blockers: captured Toy Fair and NY NOW rows contain no explicit attributable official website; GCA challenge, ASTRA third-party scripted locator, and no approved history copy. The identifiable Toy Fair layout defect has been fixed rather than deferred as a permission blocker.

```text
PRODUCTION_DEPLOYMENT = false
PRODUCTION_DB_WRITES = 0
WORKBUDDY_CHANGED = false
CANONICAL_INVENTORY_CHANGED = false
V1_CHANGED = false
V2_CHANGED = false
MX_POLICY_CHANGED = false
SMTP_CONNECTIONS = 0
EMAILS_SENT = 0
SEND_PLANS_CREATED = 0
SEND_AUTHORIZATIONS_CREATED = 0
V6_EMAIL_TEMPLATES_CHANGED = false
```



## 第5轮真实布局修复 / Round 5 captured-layout fix

Toy Fair真实页包含2026 participating retailers标题及inner-tab-data段落；每条为strong名称加显式Country。新增3个可移植结构测试先1失败后全通过；只在Toy Fair及指定标题/容器内解析，逐行隔离证据，不能将兄弟行链接或国家污染当前组织。真实捕获解析2469条、官网0；第2次公开请求保留22条，合并NY NOW22条为44未验证候选。 / The captured Toy Fair page has a 2026 participating retailers heading and inner-tab-data paragraphs, with strong names followed by explicit countries. Three portable structural tests first exposed one failure and then all passed. Parsing is scoped to Toy Fair and the specific heading/container, with per-row evidence isolation. The real capture parsed 2469 rows and zero websites. The second public request retained 22 rows, combined with 22 NY NOW rows for 44 unverified candidates.

ASTRA证据：原HTML第808行仅code.metalocator.com动态脚本，不含实体行；未猜测API或登录取数。NY NOW当前行companyName为纯文本，只带eventmap.aspx地图链接；唯一eBooth链接指向Winter2018赞助，不将旧年份页面当2026官网证据。Toy Fair名单无官网或组织详情链接，已耗尽该来源2次请求预算。 / ASTRA evidence: line 808 of captured HTML embeds only a dynamic code.metalocator.com script without entity rows; no guessed API or authenticated request was used. Current NY NOW companyName cells are plain text with eventmap.aspx map links. The only eBooth link is a Winter2018 sponsor and is not treated as 2026 website evidence. Toy Fair rows contain no websites or organization detail links, and its two-request budget is exhausted.

最终受影响模块回归81/81通过；新增测试共8项（5前置+3真实布局），无新增已知回归。全仓后续快照453项同2失败12错误，与449项原基线同14个失败名称；之后真实布局改动以81项定向回归验证，全仓结果不宣称全绿。 / Final affected-module regression passed 81/81; eight new tests comprise five preflight and three captured-layout tests. No known new regression. A later full-suite snapshot ran 453 tests with the same 2 failures and 12 errors and the same 14 failing names as the 449-test original baseline. Subsequent layout changes were checked by the 81 targeted tests; the full suite is not claimed green.

## 指标字段对应 / Metric field mapping

原始live_directory_result.json沿用通用品牌管线命名：metrics.LIVE_DISCOVERED_BRANDS=44与metrics.RAW_BRANDS_DISCOVERED=44计数的是未验证目录候选，不能解释为44个验证品牌。目录专用directory_metrics.VERIFIED_UNIQUE_ORGS=0、directory_metrics.BRAND_OWNER_CANDIDATES=0、FIRST_PARTY_EMAILS_FOUND=0。最终汇总PHASE_4B1F_LIVE_BRANDS=0与本报告LIVE_BRANDS_DISCOVERED=0采用完整验证链口径；LIVE_DIRECTORY_CANDIDATES_RETAINED=44才对应legacy原始44。 / The raw live_directory_result.json retains generic brand-pipeline names: metrics.LIVE_DISCOVERED_BRANDS=44 and metrics.RAW_BRANDS_DISCOVERED=44 count unverified directory candidates, not 44 verified brands. Directory-specific directory_metrics.VERIFIED_UNIQUE_ORGS=0, directory_metrics.BRAND_OWNER_CANDIDATES=0, and FIRST_PARTY_EMAILS_FOUND=0. The final PHASE_4B1F_LIVE_BRANDS=0 and this report's LIVE_BRANDS_DISCOVERED=0 use the complete-verification-chain definition. LIVE_DIRECTORY_CANDIDATES_RETAINED=44 maps to the legacy raw count of 44.

## 当前最终代码完整测试 / Complete suite on final code

实现提交399e78fc9be81ea9da81281ea69d41448af9fe04上重新执行完整测试：457项，443通过，2失败、12错误，68.018秒；新增8项全通过。与原基线449项的14个失败/错误ID逐项一致，没有新增失败ID。此457项才是最终代码完整suite，前述452/453为历史迭代快照。 / The complete suite was rerun on implementation commit 399e78fc9be81ea9da81281ea69d41448af9fe04: 457 tests, 443 passed, 2 failures and 12 errors, in 68.018 seconds. All eight added tests passed. Every failing/error test ID matches the original 449-test baseline, with no new failing ID. The 457-test run is the final-code complete suite; earlier 452/453 counts are historical iteration snapshots.

完整日志 / Complete log: output/brand_acquisition/phase4b1f/current_final_full_tests.txt。测试失败原因保持既有缺.env/历史归档环境问题，无降低断言或隐藏失败。 / Existing missing-.env and historical-archive environment failures remain; assertions were not weakened and failures were not hidden.
