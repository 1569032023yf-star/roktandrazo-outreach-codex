# 桥接证据分类 / Bridge evidence classification

新增纯离线分类器，区分同会话两次独立调用、进程重启、登录变化、跨登录端点及跨重启端点。输入要求POST健康成功、认证成功、脱敏身份/进程启动/boot/唯一logon标识和严格递增时间；重复call及缺失/错误形状失败关闭。没有主动访问8791，也未更改HKCU Run。

Added an offline classifier separating independent same-session calls, process restart, login-state changes, cross-logon endpoints and cross-reboot endpoints. Inputs require successful authenticated POST health, opaque identity/process-start/boot/unique-logon identifiers and increasing timestamps. Duplicate calls and missing/malformed evidence fail closed. No live8791 probe or HKCU Run modification occurred.

联合9项测试通过 / Nine combined tests passed: `python -B -m unittest test_unattended_policy test_bridge_acceptance -v`。此前必要条件模块独审通过，仅固定9a7e3ccb源码范围，新增桥接模块另行送审。

The previous precondition module passed independent review only for pinned9a7e3ccb source; the new bridge module is separately submitted for review.

边界：分类器不校验签名或来源、不保证采样间持续存活；输入由可信只读消费者核验。即使两次interactive_login_present=false，也不能证明自启动以来无人登录，故不返回UNATTENDED_ACCEPTED。真正跨登录/无人登录需受控维护窗口、操作系统登录/启动审计及自然计划运行证据，尚未执行。

Limits: the classifier does not authenticate source/signatures or prove uninterrupted uptime. A trusted read-only consumer must validate inputs. Two observations with no interactive login do not prove no login since boot, so UNATTENDED_ACCEPTED is never returned. Actual cross-login/no-login acceptance requires an approved window, OS boot/logon audit and natural scheduled execution; none was performed.

Issue2已只读检查，最新仍为消费回执6402130583，无新补证，不重复催办。整体DEVELOPMENT_COMPLETE=false，RELEASE_READY=false，PRODUCTION_DEPLOYED=false，LIVE_PROVIDER_ACCEPTED=UNKNOWN，BUSINESS_GROWTH_VERIFIED=UNKNOWN。下一自动动作是临时数据库持久slot与预算并发/重启故障注入，禁止连接生产数据库。

Issue2 was read; the latest comment remains acknowledgement6402130583 with no new evidence, so no duplicate request was sent. Overall development and release remain incomplete. Next is temporary-database slot/budget concurrency and restart fault injection, with no production database access.
