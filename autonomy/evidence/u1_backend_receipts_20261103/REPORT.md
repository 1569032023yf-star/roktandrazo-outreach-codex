# U1 backend 回执解析修复 / Backend receipt parsing fix

固定源码 / Fixed source: `870c7980ac6bec0abe687c781e05b95b2d46e71a` | 2026-11-03T09:07:49.999469+00:00

实际修复：子进程输出及持久缓存回执递归拒绝重复JSON键和非有限常量。歧义输出持久标记UNKNOWN，重试拒绝执行，不进入账本结算。
Implementation: reject duplicate JSON keys recursively and nonfinite constants in worker output and durable cached receipts. Ambiguous worker output persists UNKNOWN and retries cannot replay execution or settle ledgers.

验证 / Validation: `python -B -m unittest test_process_backend -q`: 6 tests PASS, 4.015s; includes three real subprocess malformed-output cases and restart/no-replay checks.

本SHA独审PENDING，未重建安装包，未运行本SHA全量比较；旧版本审核、包和833项结果不能继承。本次不声明正式backend整链接通。
Independent review PENDING for this SHA. No package rebuilt or full regression compared for this SHA; previous review, archives and 833-test results are not inherited. Formal backend integration remains incomplete.

下一步：完成正式backend与原Inventory所有者、服务事件消费者的合同接线，随后冻结完整源码、重建包并独审。
Next: complete formal backend contracts with the original Inventory owner and service event consumer, then freeze the complete source, rebuild packages and obtain independent review.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.

未安装服务、未触发Inventory、未写生产DB；复用既有WorkBuddy证据，无重复消费回执。
No service installed, Inventory triggered or production database written. Existing WorkBuddy evidence reused without duplicate consumption receipts.
