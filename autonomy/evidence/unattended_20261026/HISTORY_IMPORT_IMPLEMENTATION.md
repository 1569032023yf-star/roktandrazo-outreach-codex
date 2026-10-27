# 历史导入合同修复 / History import contract repair

原实现对已成功导入的空历史，仅检查organizations/baselines，第二个新事件会触发history_complete唯一键冲突并误报存储结果未知。现在显式检查历史标记及已有assets；相同回执仍返回DUPLICATE，新事件返回HISTORY_ALREADY_INITIALIZED，事务不留下新回执。 / Previously an empty imported history was not recognized as initialized: a new event collided with history_complete and was misclassified as unknown storage outcome. Explicit marker and asset checks now preserve duplicate receipt idempotency and reject new initialization without leaving a receipt.

新增列表形状、组织资格布尔值及各类内部重复ID校验，在事务前返回固定脱敏合同错误。sites/emails原有可省略合同保留；跨类别相同opaque ID不错误合并。 / List shapes, boolean qualification and duplicate IDs within each category are validated before transaction with fixed redacted errors. Existing optional sites/emails compatibility remains; IDs across different categories are not conflated.

新增3项临时SQLite测试；组合87项通过（5.402秒）。初次测试夹具未显式关闭连接导致Windows清理失败3项，已改为closing并复测通过；该失败不是生产故障。 / Three new temporary SQLite tests; combined87 passed in5.402 seconds. The initial fixtures left connections open, causing three Windows cleanup errors; explicit closing fixed them and the rerun passed. This was not a production incident.

独审见HISTORY_IMPORT_REVIEW.md；尚不能以此证明完整迁移、生产导入或U1完成。无生产数据库、Inventory、SMTP或配额变化。下一步继续批准导出合同与正式依赖闭包；Issue2最新仍6435605069，无重复请求。 / See HISTORY_IMPORT_REVIEW.md for independent review. This does not prove complete migration, production import or U1 completion. No production DB, Inventory, SMTP or quota changes. Next: approved export contracts and formal dependency closure; Issue2 still ends at6435605069, without duplicate requests.

DEVELOPMENT_COMPLETE=false (overall U1); RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.

自检：中英双语，实际失败与复测、未执行项、限制及下一步均明确，无敏感信息。 / Self-check: bilingual, actual failure/rerun, exclusions, limits and next steps stated; no sensitive data.
