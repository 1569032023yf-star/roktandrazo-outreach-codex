# Phase 2C Controlled Integration Results | Phase 2C 受控集成结果

## Verdict | 判定

The single valid RC2 provider run safely reached five real Google Maps merchants and resolved at least one real official website, but it did not extract a visible official email from this sample. Therefore controlled MX/V2-to-Dev-FSP materialization could not complete and the release candidate is **not ready** for production promotion review.

唯一一次有效的 RC2 provider 运行安全取得 5 个真实 Google Maps 商户，并成功解析至少一个真实官网；但本批样本未提取到可接受的可见官方邮箱。因此受控 MX/V2 到 Dev FSP 的物化未能完成，本发布候选**尚不具备**生产晋级评审条件。

RC1 stopped before any web request because the development process guard was not class-compatible with Playwright. Its evidence was preserved. The guard was narrowly corrected and offline-tested before RC2; RC1 was not counted as a provider run.

RC1 在任何网页请求发生前即停止，原因是开发进程保护层与 Playwright 的类继承机制不兼容。该证据已保留；保护层经最小修正和离线验证后才执行 RC2，RC1 不计为 provider 运行。

## Controlled path | 受控链路

```text
BrowserMaps direct / Google Maps
→ 5 real merchant results / 5 个真实商户
→ website identity and official-site checks / 官网身份与官方站点校验
→ visible-text-only email extraction / 仅可见文本邮箱提取
→ frozen V2/MX gate when an email exists / 有邮箱时进入冻结 V2/MX 门
→ dev_safe_fsp only / 仅写 dev_safe_fsp
```

Query / 查询：`board game store Nashville TN`

Development DB / 开发数据库：`data/phase2c_rc2_validation.db`

Machine evidence / 机器证据：`audit_evidence/phase2c_controlled_integration_rc2.json`

## Gate results | 门禁结果

```text
CONTROLLED_PROVIDER_TEST_PASS = true
REAL_WEBSITE_RESOLUTION_PASS = true
REAL_OFFICIAL_EMAIL_EXTRACTION_PASS = false
CONTROLLED_MX_PATH_EXECUTED = false
DEV_SAFE_FSP_CREATED = 0
SECOND_RUN_IDEMPOTENT = true
```

The five returned businesses were Tabletops Hobbies & Games, Game Point - A Game Store, The Game Cave, Game Point - A Board Game Cafe, and Middle Tennessee Gaming. Three records entered evidence processing; two were rejected before promotion. No address was guessed or accepted from hidden script content.

五个返回商户为 Tabletops Hobbies & Games、Game Point - A Game Store、The Game Cave、Game Point - A Board Game Cafe 与 Middle Tennessee Gaming。三条进入证据处理，两条在晋级前被拒绝；没有猜测邮箱，也没有接受隐藏脚本中的邮箱。

## Data-quality acceptance | 数据质量验收

```text
JUNK_BUSINESS_NAMES = 0
DIRECTORY_AS_OFFICIAL_SITE = 0
GUESSED_EMAILS = 0
HIDDEN_SCRIPT_EMAIL_ACCEPTED = 0
IDENTITY_MISMATCH_PROMOTED = 0
```

The `IDENTITY_MISMATCH_PROMOTED` definition counts only mismatched records actually materialized into `dev_safe_fsp`; rejected staging records are not “promoted.” / `IDENTITY_MISMATCH_PROMOTED` 仅统计实际物化进 `dev_safe_fsp` 的身份不匹配记录；已拒绝的 staging 记录不属于“已提升”。

## Idempotency | 幂等性

The exact same five provider results were replayed through the development pipeline. Counts were unchanged.

同一批五个 provider 结果再次送入开发链路，计数保持不变。

```text
DUPLICATE_LEADS = 0
DUPLICATE_ORGS = 0
DUPLICATE_DEV_FSP = 0
```

## Safety evidence | 安全证据

```text
REAL_SMTP_CONNECTIONS = 0
REAL_IMAP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
FROZEN_FILES_CHANGED = 0
```

SMTP/IMAP constructors remained fail-closed. All database and evidence writes targeted new files under the development root. No command targeted the WorkBuddy production root for mutation. / SMTP/IMAP 构造器持续故障关闭。所有数据库与证据写入均指向开发根目录中的新文件；没有任何命令以写入方式触及 WorkBuddy 生产根目录。

