# 城市生产补丁重建 / Production City Patch Rebase

已按生产快照逐函数重建城市补丁，两文件精确正反向校验通过，14项恢复测试通过；扩展回归95项中94通过、1项静态扫描失败，原开发副本同项复现。独立审核、登记、部署与真实城市验收待完成。

Rebuilt the city patch function by function against pinned production snapshots. Both files pass exact forward/reverse checks and all 14 recovery tests pass. Expanded regression: 94/95 passed; the static-scan failure also reproduces on the original development tree. Independent review, registration, deployment and production city acceptance remain pending.

上轮retail的PATCH_HUNK_COUNT_INVALID来自诊断调用遗漏expected_hunks参数（默认3），不是补丁语法错误；discovery生产上下文差异仍真实存在。本轮传真实块数并精确正反向校验。

Prior retail PATCH_HUNK_COUNT_INVALID came from the diagnostic omitting expected_hunks (default 3), not malformed patch syntax. Discovery production context incompatibility was real. This cycle supplies actual hunk counts for exact forward/reverse checks.

补丁 / Patch: patches/production/phase4a8u/city_recovery.patch

SHA256: 53143f5326a16df3ef7acbde21607d53745ab0b0a963da5d307027d8f9f500bb

风险与下一步：候选未独立审核；扩展回归存在原副本同项失败，不宣称全通过。下周期独立复核后再受控登记和实时预检。无生产DB或SMTP访问，无客户外发。

Risks and next steps: candidate lacks independent review; expanded regression has a reproduced baseline failure and is not all passing. Next independently review before controlled registration and live preflight. No production DB/SMTP access or customer sending.
