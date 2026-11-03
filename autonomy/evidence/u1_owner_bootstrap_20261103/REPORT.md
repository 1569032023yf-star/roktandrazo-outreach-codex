# U1 原所有者启动接线 / Original-owner bootstrap wiring

固定源码 / Fixed source: 748ccb0196786884611cb98fab97888e6a12d231 | 2026-11-03T15:10:42.508166+00:00

启动入口新增互斥--original-owner-db与--event-runtime，将原数据库只读连接接到既有open_host原owner观察器；不再仅能通过测试内注入连接工厂。绝对路径、普通文件、单硬链接、启动时文件身份固定及连接前后复验；mode=ro和query_only禁止建库、迁移及写入。
The host CLI now accepts mutually exclusive --original-owner-db and --event-runtime, routing a read-only original database connection to the existing owner observer instead of requiring test-only connection injection. It requires an absolute ordinary single-link file, captures file identity and checks it around connections. mode=ro and query_only prevent database creation, migration and writes.

路径身份检查依赖受信配置和受保护目录，不声明对敌对目录的完整TOCTOU防护。未放开生产执行或服务安装；固定服务runtime plan及supervisor参数仍待接线，正式Provider及实测费用仍未完成。
Path checks depend on trusted configuration and protected directories; they do not establish complete TOCTOU protection against hostile directory mutation. Production execution and service installation remain disabled. Pinned runtime-plan and supervisor arguments, formal Provider and measured costs remain incomplete.

验证 / Validation: python -B -m unittest test_u1_host_runtime test_original_process_backend test_inventory_event_bridge -q: 13 PASS, 7.775s. Actual SQLite missing-file/no-creation, write rejection and file-replacement checks plus existing HTTP/child/settlement integration.

本SHA独审PENDING，全量回归NOT_RUN，安装包未重建；不继承3fbaa5e审核或旧包。
Independent review PENDING for this SHA, full regression NOT_RUN, packages not rebuilt. The 3fbaa5e review and old packages are not inherited.

下一步 / Next: 把获准原owner数据库引用接入固定服务runtime plan与supervisor参数；完成正式Provider与实测费用合同后重建并审核完整发布版。
Wire the approved original-owner DB reference into the pinned service runtime plan and supervisor arguments; complete formal Provider and measured-cost contracts before rebuilding and reviewing the complete release.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false; Inventory=1784775229336.

本轮未操作生产数据库、服务、ACL或Inventory；复用既有WorkBuddy证据，不重复消费回执。平台硬超时未配置，不声明已强制45分钟。
No production database, service, ACL or Inventory operation occurred. Existing WorkBuddy evidence was reused without duplicate receipts. No platform hard timeout was configured or claimed.
