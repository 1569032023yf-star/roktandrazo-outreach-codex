# 固定交接消费 / Pinned handoff consumption

中文：验证器只接收调用方从可信 Git 连接器取得的精确字节和固定 blob SHA；不自行联网、刷新或访问数据库。先校验 Git 对象，再校验版本、生成时间和生产方的带空格排序 JSON 摘要。MD 仅检查 Git 完整性。没有 payload 字段时不得声称 payload 已验证。

English: The verifier accepts exact bytes and a pinned blob SHA supplied by a trusted Git connector. It performs no network, refresh or database access. It checks the Git object before schema, freshness and the producer's sorted JSON digest with default separators. Markdown receives Git integrity checks only. An absent payload digest is never claimed verified.

中文：runtime 包装层覆盖了原生成时间；固定证据只有显式恢复原时间后才匹配摘要。回执必须公开该差异，不自动猜测或改变原始文件。完整性通过不等于全局唯一、城市结案、阶段轨迹或业务新增验收。

English: The runtime wrapper overwrote the original generation time. This pinned evidence matches its digest only with an explicitly supplied original timestamp. Receipts disclose the discrepancy; the verifier neither guesses it nor alters source bytes. Integrity does not establish global uniqueness, city closure, stage traversal or business growth acceptance.
