# 正式合同缺失清单 / Formal contract missing checklist

中文：状态 CONTRACT_MISSING。范围为当前仓库、已读取的既有交接记录；不推断外部服务不存在。用户明确暂不提供凭据，允许独立离线开发继续。以下事项在正式接入前确认，不要求提供密钥。

English: Status CONTRACT_MISSING within the current repository and reviewed handoff records; this does not imply no external service exists. The user withholds credentials and authorizes independent offline development. Confirm the following before formal integration; no secrets are requested.

| 待确认 / Confirmation | 所需材料 / Required evidence |
|---|---|
| 正式服务名称 / Formal service | Google Places、browser_maps 或其他已批准服务的准确名称、账户与环境类型；exact approved service, account/environment classification |
| 协议来源 / Contract source | 仓库路径或正式文档地址、版本、负责人；repository path or authoritative document URL, version and owner |
| 提交与身份 / Submission and identity | 请求字段、Provider request ID、幂等支持与重放语义；request schema, request ID, idempotency and replay semantics |
| 状态与取消 / Status and cancellation | 查询入口、终态定义、取消回执和未知结果对账方法；query contract, terminal states, cancellation receipt and UNKNOWN reconciliation |
| 费用 / Billing | 权威用量/账单来源、币种、金额精度、延迟与修订规则；authoritative usage/billing source, currency, precision, delay and correction rules |
| 信任与签名 / Trust and signatures | 已有签名协议、密钥标识和验证规则（不提供密钥）；existing signature protocol, key identity and verification rules, without secret material |
| Worker 与 SAFE / Worker and SAFE | 正式 Worker 入口及授权只读数据/快照来源、时间、摘要；formal Worker entry and authorized read-only source/snapshot, timestamp and digest |

中文：已实现的 Google Places 同步搜索适配器使用 urllib POST；browser_maps 包含文件缓存和直接浏览器分支；SerpAPI 明确禁用。现有 ProcessBackend 限定 isolated_offline，模拟回执/计数不能作为正式验收。现有计数 cost_units、paid_units 不是权威金额。未发现可据以实现上述完整合同的正式协议，不自创接口。

English: Google Places has a synchronous urllib POST search adapter. browser_maps includes file-cache and direct-browser branches; SerpAPI is explicitly disabled. ProcessBackend is restricted to isolated_offline, and simulated receipts/counters are not formal acceptance. cost_units and paid_units are not authoritative monetary charges. No formal protocol establishing the complete contract above was found; interfaces are not invented.

中文：allow_install、allow_dispatch、allow_cancel_dispatch、smtp_enabled 均 false。未发送生产请求或产生实际扣费。正式合同缺失不阻塞 CPython、依赖闭包、Publisher、Bootstrap 的离线开发。

English: allow_install, allow_dispatch, allow_cancel_dispatch and smtp_enabled remain false. No production requests or actual charges were initiated. Missing formal contracts do not block offline CPython, dependency closure, Publisher or Bootstrap development.
