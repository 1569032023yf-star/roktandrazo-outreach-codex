# 4A.8R 持续发现交接 / Continuous discovery handoff

日期 / Date: 2026-10-13 (Asia/Taipei)

开发基线 / Development baseline: `a636a99893e19605a3a4e701dc7bf3b9235b6c40`

分支 / Branch: `codex/phase4a8r-continuous-discovery-target-decoupling`

## 结果与范围 / Outcome and scope

正常 Inventory 不再因 SAFE 达到补足目标而跳过新商家发现。每次调用仍只执行一个当前城市查询族的有界批次，随后执行原有官网解析、正常后处理和受保护的关联积压路径。 / Normal Inventory no longer skips merchant discovery when SAFE meets its replenishment target. Each invocation still runs one bounded batch for the current city query family, followed by existing website resolution, normal postprocessing, and guarded linked-backlog processing.

`INVENTORY_TARGET_MET` 表示库存是否足够；`DISCOVERY_PATH_EXECUTED` 表示调用发现路径，不表示 Provider 请求成功、找到新商家或生产验收通过。完整成功仍需正常发现返回状态及最终 SAFE 目标达成。 / INVENTORY_TARGET_MET describes inventory sufficiency; DISCOVERY_PATH_EXECUTED describes entry into the discovery call, not provider success, new merchants, or production acceptance. Run success still requires an accepted discovery status and the final SAFE target.

保留 `WORKBUDDY_DISCOVERY_MAX_PAGES=3`，默认与硬上限均为 3；显式 1 或 2 页预算仍被尊重，非正整数限制至 1，非法字符串失败关闭且不误记发现执行。无新增循环。 / WORKBUDDY_DISCOVERY_MAX_PAGES=3 is preserved with default and hard cap of three. Explicit one/two-page budgets remain respected; non-positive integers clamp to one. Invalid strings fail closed before logging execution. No additional loop was introduced.

Provider 非成功返回（含未知状态、配置阻塞、超时和配额错误）停止运行，即使 SAFE 已足够。Provider 异常仍通过既有 stopped/raise 路径处理；所有取得锁的退出路径释放锁。错误状态与原游标先按既有事务保存，以便恢复。 / Non-success provider results, including unknown status, configuration block, timeout, and quota error, stop the run even with sufficient SAFE inventory. Exceptions retain existing stopped/raise behavior and acquired locks are released. Existing transactions preserve failure state and cursor for recovery.

城市工作前/后的耗尽检查均保留；SAFE 达标不构成城市耗尽证据。查询族、城市游标、两页无新增的耗尽判断、4A.8Q identity_review 终态、官网/邮箱/历史/MX 门禁及发送逻辑均未修改。 / Both city-exhaustion checks remain. SAFE sufficiency is never exhaustion evidence. Query families, city cursors, two-page zero-yield exhaustion, the 4A.8Q identity_review terminal state, website/email/history/MX gates, and sending logic are unchanged.

## 测试与迭代 / Tests and iterations

所有执行均为隔离开发数据库与确定性 Provider/网页夹具；不是生产修复验收。 / All execution used isolated development databases and deterministic provider/page fixtures, not production acceptance.

| 验证 / Check | 结果 / Result |
| --- | --- |
| 最终定向 / Final targeted | 27/27 通过 / passed |
| 相关回归 / Related regression | 78/78 通过 / passed；随后新增无效预算用例已包含在最终定向 / later invalid-budget case included in final targeted |
| 最终全套 / Final full suite | 485 执行，481 通过，2 失败，2 错误，0 跳过 / run 485, passed 481, failed 2, errors 2, skipped 0 |
| 原始基线全套 / Baseline full suite | 476 执行，472 通过，2 失败，2 错误，0 跳过 / run 476, passed 472, failed 2, errors 2, skipped 0 |
| 编译与差异 / Compile and diff | compileall、py_compile、git diff --check 通过 / passed |
| 独立审查 / Independent review | 无阻塞缺陷；日志顺序观察已修复并加测 / no blocking defect; log-order observation fixed and tested |

新增9个测试方法全部通过；新增失败/错误ID为0。最终全套存在已核对的4项原有失败，不能称为全套通过。两侧失败ID与规范化原因均匹配；基线跟踪文件无变化。 / All nine new methods passed, with zero new failure/error IDs. The final full suite still has four verified existing failures and is not an all-green suite. Failure IDs and normalized causes match; baseline tracked files are unchanged.

确定性覆盖 SAFE/TARGET 的 49/50、50/50、51/50、59/60、60/60；Provider 抛异常及错误返回；锁冲突；城市未完成/已完成推进；dry-run 不构造 Provider、不取锁、不请求；预算上限、非法预算；真实 DiscoveryService 的错误游标保存与续跑；发送计划/授权/日志表不变。 / Deterministic coverage includes SAFE/TARGET 49/50, 50/50, 51/50, 59/60, 60/60; provider exceptions and error results; lock conflict; incomplete/completed city advancement; dry-run without provider construction, lock acquisition, or requests; budget cap and invalid budget; real DiscoveryService cursor persistence/resumption; unchanged plan/authorization/send-log tables.

最终夹具在原始基线动态加载后，9 个测试方法产生 16 个失败子用例、2 个错误子用例（未调用发现导致 call_args 为空），复现旧行为；修复后定向套件通过。较早夹具中的 dataclass 必填状态和重复建表错误已修正，没有将夹具错误计为产品回归。 / Loading the final fixtures against the original baseline produced 16 failing and two error subcases across nine methods (the skipped discovery call left call_args empty), reproducing prior behavior. The fixed implementation passed targeted validation. Earlier fixture errors concerning required dataclass status and duplicate table creation were corrected and were not counted as product regressions.

主要迭代：1 定位与失败测试；2 有界发现/Provider 失败关闭；3 真实游标恢复及旧测试前提修正；4 相关回归/独立审查；5 配置失败日志修复与最终验证；6 全套基线对照及交付。 / Main iterations: 1 diagnosis/red tests; 2 bounded discovery/provider failure closure; 3 real cursor recovery and old fixture prerequisite correction; 4 regressions/independent review; 5 configuration-failure logging and final validation; 6 full baseline comparison and delivery.

历史失败为开发 checkout 缺少 Git 忽略的归档脚本和历史数据库：dashboard 禁用标记、inventory 归档禁用标记、single SMTP 归档目录以及根目录 test_45min_delivery_guard 的 data/bd_leads.db。不读取生产副本、不伪造文件、不删除断言来掩盖失败。 / Existing failures concern absent Git-ignored archived scripts and a historical database: dashboard disable marker, inventory archive disable marker, single-SMTP archive directory, and data/bd_leads.db required by root test_45min_delivery_guard. No production copies, fabricated files, or removed assertions were used to hide these failures.

## 复现与证据 / Reproduction and evidence

在此开发 worktree 的根目录运行；`.development-copy`/`sitecustomize.py` 安装既有外部传输、SMTP/IMAP、进程与数据库路径保护。新 checkout 只需建立无凭据开发 `.env`，不得复制生产配置。 / Run at this development worktree root. Existing .development-copy/sitecustomize.py installs transport, SMTP/IMAP, process, and DB-path guards. A fresh checkout needs only a credential-free development .env; never copy production configuration.

```powershell
if (-not (Test-Path -LiteralPath .env)) { Set-Content -LiteralPath .env -Value '# Development tests only / 仅开发测试，无凭据' -Encoding utf8 }
New-Item -ItemType Directory -Path output/sprint4a8r/tmp -Force | Out-Null
$env:TEMP = Join-Path (Get-Location) 'output/sprint4a8r/tmp'
$env:TMP = $env:TEMP
python -X utf8 -c "import unittest; names=['tests.test_phase4a8r_continuous_discovery','tests.test_phase4a1c_discovery_coexistence','tests.test_phase4a1b_linked_backlog']; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names)); raise SystemExit(not r.wasSuccessful())"
python -X utf8 -c "import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('.')); raise SystemExit(not r.wasSuccessful())"
python -X utf8 -m compileall -q bd_orchestrator.py discovery retail_city_queue.py tests
git diff --check
```

全套基线在独立 detached worktree、相同 Python 3.13 与同一启动方式执行。根发现包含历史入口和现有重复导入的 TestCase；数量是实际 unittest 执行次数。 / Full baseline comparison used a separate detached worktree, the same Python 3.13, and identical startup. Root discovery includes historical entrypoints and previously duplicated imported TestCases; counts are actual unittest executions.

本地 `output/sprint4a8r/`（Git 忽略）保存迭代记录、红/绿日志、完整基线对照 JSON、最终原始日志和精确开发差异 development.patch。跟踪交付仅含代码、测试和本双语交接。 / Git-ignored output/sprint4a8r/ contains iterations, red/green logs, full-comparison JSON, final raw logs, and exact development.patch. Tracked delivery contains only code, tests, and this bilingual handoff.

## 生产补丁条件 / Production patch conditions

`PRODUCTION_PATCH_STATUS = NOT_READY`：尚无 WorkBuddy 真实生产代码基线 SHA、实际阻塞证据与精确差异匹配；开发差异可审查，但不能称为可部署生产补丁。未手动启动生产 Inventory。下一步由生产责任方提供这三项证据，再进行独立补丁审查。 / PRODUCTION_PATCH_STATUS=NOT_READY: the actual WorkBuddy production SHA, blocking evidence, and exact diff match are absent. The development diff is reviewable but is not a deployment-ready production patch. Production Inventory was not manually started. The production owner must provide these three items for independent patch review.

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

首批 SAFE40 与确认 SAFE50 数据未访问或改写；商业邮件继续待授权。 / Original SAFE40 and confirmed SAFE50 data were neither accessed nor rewritten; commercial emails remain pending authorization.
