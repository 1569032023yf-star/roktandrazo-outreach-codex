# PHASE 4A.5 — General Inbox Referral Routing / 通用收件箱转介路由

## 中文

### 结果

已在开发环境新增第三个锁定新外联模板：

`general_inbox_referral_v1_locked`（SHA-256 短指纹：`af7b6f41`）。

它只针对已存在且已验证的公开邮箱的精确本地部分：`info`、`service`、`support`、`hello`、`contact`、`office`。邮件请求收件人将信息转发或连接给合适的 Purchasing、Product、Sales 或 Business Development 联系人；它不创建、猜测或变更任何收件人地址。

### 路由与不变量

| 场景 | 结果 |
|---|---|
| `info@example.test`、`service@example.test`、`support@example.test`、`hello@example.test`、`contact@example.test`、`office@example.test` | `general_inbox_referral_v1_locked` |
| `maria@example.test`，游戏商店 | 既有 `retail_distributor_v5_locked` |
| `buyer@example.test`，礼品商店 | 既有 `custom_printing_production_v5_locked` |
| `info+orders@example.test`、`information@example.test`、`contact.team@example.test` | 不视为通用收件箱，保持既有直接路由 |

- 现有零售模板指纹仍为 `ccb51505`。
- 现有定制生产模板指纹仍为 `5893dbc9`。
- 手工模板覆盖仍保持既有优先级；普通自动路由只会将精确通用本地部分导向新模板。
- 预发送现有链路会将 `template_key`、`content_sha256`、`renderer_version`、`renderer_sha256` 及已渲染主题/正文冻结写入 FSP 元数据。新增回归以内存 SQLite FSP 验证该行为。
- 未修改 V2、MX、证据策略、发送配额、跟进策略、发送器、授权语义或冻结文件。

### 测试

- 定向测试：13 passed，0 failures，0 errors。
- 完整项目测试（项目 `.venv`）：340 passed，0 failures，0 errors。
- 完整测试出现既有 `ResourceWarning`（测试文件未关闭读取句柄），但不构成失败或错误，且与本阶段无关。

### 安全与决策

```text
GENERIC_INBOX_ROUTING_PASS = true
NAMED_DIRECT_ROUTING_UNCHANGED = true
EXISTING_TWO_LOCKED_TEMPLATES_UNCHANGED = true
FSP_METADATA_FROZEN = true
ADDRESS_GUESSING = 0
NEW_RECIPIENTS_CREATED = 0
V2_POLICY_CHANGED = false
MX_POLICY_CHANGED = false
SMTP_CONNECTIONS = 0
IMAP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
READY_FOR_PRODUCTION_REVIEW = true
```

本阶段仅完成开发与测试。没有部署、没有真实 SMTP、没有创建发送计划或授权，也没有恢复任何调度。

## English

### Result

A third locked new-outreach template was added in development:

`general_inbox_referral_v1_locked` (short SHA-256 fingerprint: `af7b6f41`).

It applies only to existing, verified public email addresses whose exact local-part is `info`, `service`, `support`, `hello`, `contact`, or `office`. The message asks the recipient to connect or forward the note to the appropriate Purchasing, Product, Sales, or Business Development contact. It never creates, guesses, or alters a recipient address.

### Routing and invariants

| Case | Result |
|---|---|
| `info@example.test`, `service@example.test`, `support@example.test`, `hello@example.test`, `contact@example.test`, `office@example.test` | `general_inbox_referral_v1_locked` |
| `maria@example.test`, game store | existing `retail_distributor_v5_locked` |
| `buyer@example.test`, gift shop | existing `custom_printing_production_v5_locked` |
| `info+orders@example.test`, `information@example.test`, `contact.team@example.test` | not treated as a generic inbox; prior direct routing remains in force |

- The existing retail template fingerprint remains `ccb51505`.
- The existing custom-production template fingerprint remains `5893dbc9`.
- Existing manual template overrides retain their established precedence; normal automatic routing only sends exact generic local-parts to the new template.
- The existing pre-send chain freezes `template_key`, `content_sha256`, `renderer_version`, `renderer_sha256`, and rendered subject/body into FSP metadata. A new in-memory SQLite FSP regression verifies this behavior.
- V2, MX, evidence policy, send quota, follow-up policy, sender, authorization semantics, and frozen files were not changed.

### Tests

- Targeted tests: 13 passed, 0 failures, 0 errors.
- Full project suite (project `.venv`): 340 passed, 0 failures, 0 errors.
- The full suite emitted pre-existing `ResourceWarning` messages for unclosed test-file handles; they are neither failures nor errors and are unrelated to this phase.

### Safety and decision

```text
GENERIC_INBOX_ROUTING_PASS = true
NAMED_DIRECT_ROUTING_UNCHANGED = true
EXISTING_TWO_LOCKED_TEMPLATES_UNCHANGED = true
FSP_METADATA_FROZEN = true
ADDRESS_GUESSING = 0
NEW_RECIPIENTS_CREATED = 0
V2_POLICY_CHANGED = false
MX_POLICY_CHANGED = false
SMTP_CONNECTIONS = 0
IMAP_CONNECTIONS = 0
PRODUCTION_DB_WRITES = 0
PRODUCTION_FILES_CHANGED = 0
READY_FOR_PRODUCTION_REVIEW = true
```

This phase stops at development and test validation. No deployment, real SMTP, send-plan or authorization creation, or scheduler resumption occurred.
