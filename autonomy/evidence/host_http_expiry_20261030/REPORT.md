# HTTP凭据期限故障合同 / HTTP credential deadline fault contract

固定源码 / Source: `acdb1494ebb02f140e3ca0faf97aef82aa70a68f`；恢复基线 / Recovery HEAD: `411c2a4e82c2b6d70502c106633767f512971b86`。

中文：本轮补齐离线只读HTTP接口的显式凭据期限。构造时要求正整数期限，每次请求先验证时钟与Bearer；到期、负时间、布尔、NaN、Infinity、未知或异常时钟全部拒绝，且不读取后端。未认证写方法也返回401；认证HEAD拒绝且不发送正文。现有调用点已检查并适配。只使用隔离随机回环端口，未接8791、SCM或生产包。

English: The offline read-only HTTP adapter now requires an explicit positive integer credential deadline. Every request checks clock and Bearer before backend access. Expiry, negative/boolean/nonfinite/unknown/failing clocks fail closed. Unauthenticated mutations return401; authenticated HEAD is denied without a body. Existing callers were checked and updated. Testing uses isolated ephemeral loopback ports, with no8791/SCM/production-package integration.

中文：44项定向组合通过，最新可复现执行14.236秒，见TEST_RESULT.json；12份固定Git源码blob/SHA256及独立临时目录导入通过，见SOURCE_MANIFEST.json。新增2项HTTP测试覆盖多个时钟/期限边界。无独立Reviewer，本增量独审PENDING。按本轮局部认证改动风险执行定向组合，没有新全量回归；旧59926ebb的833对比结论不扩展到此pin。本轮不是全量NO_NEW_REGRESSION证明。

English:44 selected combined tests pass in the latest reproducible14.236-second run, recorded in TEST_RESULT.json. Twelve pinned Git files and isolated temporary-directory import pass. Two new HTTP tests cover multiple clock/deadline boundaries. Independent review remains PENDING. Risk-scoped combination was run for this local authentication change; no fresh full regression is claimed and the earlier59926ebb833-test comparison is not inherited.

中文：期限由调用者提供，不是生产信任根、签发者或轮换实现；未实现时钟回拨检测，也没有证明生产认证门禁。下一步先独审固定HTTP候选，并补正式身份/凭据生命周期与只读backend合同；独立禁用安装设计57bccd47的独审仅限设计，后续持久日志/OS适配层及维护租约仍待实现。

English: Caller-supplied expiry is not a production trust root, issuer or rotation mechanism. Clock rollback detection and production authentication acceptance are not established. Next: independently review this pinned HTTP candidate and implement formal identity/credential-lifecycle/read-only-backend contracts. The57bccd47 independent disabled-install review remains design-only; durable journaling, OS adapter and formal maintenance lease integration remain outstanding.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. allow_dispatch=false; allow_cancel_dispatch=false.

未修改生产DB、SMTP、调度、服务、ACL或代理。 / No production database, SMTP, scheduler, service, ACL or proxy mutation occurred.
