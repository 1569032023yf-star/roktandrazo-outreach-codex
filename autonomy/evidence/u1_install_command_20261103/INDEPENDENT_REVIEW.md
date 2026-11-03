# 独立离线范围审核 / Independent offline scoped review

固定源码 / Source: `e279e5505a1526969ce1e1f4769cc11e02bce66d`
基线 / Baseline: `2c17b8cdb7f23eea3fa7b6ca50e3588924f4ac37`

结论：已证实的配置测试回归修复并独立复验后，本次增量 **OFFLINE_SCOPED_REVIEW_PASSED**。未发现尚未关闭的新增阻断。所有生产安装/发布门禁仍为 false，这不是完整调用链或生产验收批准。

Conclusion: After independently verifying the fix for the demonstrated configuration-test regression, this increment is **OFFLINE_SCOPED_REVIEW_PASSED**, with no remaining new blocking findings. All production installation/release gates remain false. This is not full-chain or production acceptance approval.

## 发现与修复 / Finding and fix

原候选 efe78a14ade785fffa5bd06de8c6e82a97025485 独立运行21项：20通过、1error（10.141秒）。test_u1_provision.py:14 仍从旧公开入口提取配置区块，抛出 substring not found。已先向主代理反馈，未修改产品。新固定候选仅补该测试读取 Host-PackagePreparation.ps1；最终21项全部重跑，不继承旧成绩。

The original candidate efe78a14ade785fffa5bd06de8c6e82a97025485 independently ran 21 tests: 20 passed and one errored in 10.141 seconds. test_u1_provision.py:14 still extracted the configuration block from the old public entry, causing substring not found. This was reported before any product change. The new pin changes that test to read Host-PackagePreparation.ps1. All 21 tests were rerun on the final pin without inheriting the old result.

## 实现审核 / Implementation inspection

InstallInputPins 使用真实Windows句柄逐级固定父目录（拒重命名/删除）、文件（拒写与canonical名称删除），拒reparse、类型/身份变化、超限与普通文件hardlink。普通文件pin后新建alias仍不能修改内容，并在重验时被links检查拒绝。系统hardlink例外只允许GetWindowsDirectory确定的六个既有.NET路径及固定系统PowerShell；批准摘要仍须匹配。其他hardlink alias在Windows可能允许删除，报告不声称alias均不可删除。关闭失败、pins未活跃、重复使用均拒绝。

InstallInputPins uses actual Windows handles to pin parent directories against rename/delete and files against write/canonical-name deletion, rejecting reparses, type/identity changes, limits and ordinary-file hardlinks. A new alias after ordinary-file admission cannot change bytes and fails link-count revalidation. The system-hardlink exception admits only six existing .NET paths and system PowerShell under GetWindowsDirectory, still requiring approved hashes. Windows can allow deletion of other hardlink aliases; this review does not claim every alias is undeletable. Handle-close failure, inactive pins and reuse are rejected.

pin_package 绑定独立批准manifest摘要/source、精确九脚本集合、每个文件size/hash与安全配置；禁止保留路径/冲突。运行时计划、Python、token、snapshot、参考目录及系统组件在同一pins生命周期内固定。InstallCommand 只生成固定系统PowerShell与包内私有脚本的内部命令；会话source/manifest绑定，upgrade要求旧receipt摘要；正向install/upgrade过期拒绝，recover/rollback仅跳过expiry，仍须实时维护权。公开Execute在加载helper前保持硬拒绝。私有入口先原维护RPC ACK再访问包。准备主体与原正文对比，除脚本集合、补偿expiry与维护权传递外一致。

pin_package binds independently approved manifest digest/source, an exact nine-script set, every file size/hash and safe configuration, rejecting reserved paths and collisions. The runtime plan, Python, token, snapshot, reference directories and system components are held within the same pin lifetime. InstallCommand constructs only a fixed internal system-PowerShell/package-private-script command. Sessions bind source/manifest; upgrade requires the previous-receipt digest. Expired forward install/upgrade is refused; recover/rollback skip only expiry and still require live authority. Public Execute remains a hard refusal before helper loading. The private entry requires the original maintenance RPC ACK before package access. Comparison with the old preparation body found only the intended script-set, compensation-expiry and maintenance-authority changes.

observer 使用同一pins下的固定PowerShell与脚本，绑定operation/nonce、实时维护权并在前后重验pins，非零返回/非空stderr/响应绑定不符均拒绝。未添加ExecutionPolicy覆盖。审批摘要是受信内部输入契约；当前未提供seal验证器，不能把构造器或测试fixture当作正式授权。

The observer uses fixed PowerShell/script bytes under the same pins, binds operation/nonce, checks live ownership and revalidates pins before/after execution. Nonzero exit, nonempty stderr and response-binding mismatch are rejected. No ExecutionPolicy override is added. Approval hashes are a trusted internal-input contract; no seal verifier is provided here, and the constructor/test fixtures are not formal authorization.

## 独立实测 / Independent execution

`python -m unittest test_install_inputs test_install_command test_disabled_host_package test_u1_provision -v`：最终固定源码 **21/21通过，12.826秒，零error/failure**。包括真实Windows共享/父目录锁、hardlink/reparse/已开writer拒绝、批准摘要不符、系统例外闭集合、私有入口无ACK拒绝、expiry与维护权、observer绑定及包/公开门禁/配置生成回归。实际固定安装成功命令未运行；SCM/ACL成功仍未验收。

On the final pin the command above passed **21/21 tests in 12.826 seconds with zero errors/failures**. Coverage includes actual Windows sharing/ancestor locks; hardlink/reparse/existing-writer refusal; mismatched approvals; the closed system exception; private-entry refusal without ACK; expiry/live authority; observer binding; and package/public-gate/configuration regressions. No successful actual fixed installer command was run; successful SCM/ACL acceptance remains unverified.

三个额外隔离探针在最终pin重跑：pin后新增hardlink导致LINKS_OR_SIZE拒绝；新增alias写入被Windows拒绝；pins关闭后保留observer回调拒绝PINS_NOT_ACTIVE且零进程启动。未修改源码或生产对象。

Three extra isolated probes were rerun on the final pin: a newly added hardlink triggers LINKS_OR_SIZE; Windows refuses writes through that alias; retaining an observer callback beyond pin closure produces PINS_NOT_ACTIVE with zero process launch. No source or production object was modified.

## 工程包独立核验 / Independent engineering-package checks

BUILD source与当前pin一致。外层manifest SHA256 `6074910fc6ad7c6fe33292b7b4a446002a5da0218e500d347599f0f13d03420a`，71条payload逐字节摘要/精确集合验证；host manifest `bed132e61467cc2852ab7a990b97fe53847ac0eb5fce978d356edbace77009d7`、九脚本集合/当前源码字节及所有声明文件size/hash验证。install.zip SHA256 `352d3c363135e70fb2869fd2c06d7837ad4d698efc3e8ddd252aaef4f61bf43d`（72文件含外manifest）、rollback-tools.zip `c92ebe64ad8e8cc9971a3134aeb7c5eee4998f2f4df90c3c13262bec1c9d23ba`（18文件）均与解包树精确逐字节一致，PE machine=0x8664 AMD64。DELIVERY formal_maintenance/backend/production_ready/allow_install均false，公开Execute仍硬拒绝。这只是工程包，不能授权安装。

BUILD source matches the final pin. The outer manifest SHA256 shown above binds exactly 71 payload entries; the host manifest, nine-script set/current source bytes and every declared size/hash were verified. Both ZIP SHA256 values shown above match BUILD and their entries exactly match extracted-tree bytes (72 install files including its outer manifest; 18 rollback-tool files). The PE machine is 0x8664 AMD64. DELIVERY formal_maintenance/backend/production_ready/allow_install are false and public Execute still refuses. This is an engineering package and cannot authorize installation.

全部变动文件实际/Git blob SHA256见INDEPENDENT_RESULT.json，CRLF/LF规范化匹配固定源码且无tracked diff。正式auth/seal入口、生产SCM/ACL与全链验收未完成。未修改执行策略或生产ACL/服务/DB/Inventory。`RELEASE_READY=false`、`FULL_CHAIN_VERIFIED=false`。

Actual/Git-blob SHA256 values for every changed file are in INDEPENDENT_RESULT.json; CRLF/LF-normalized bytes match the pin with no tracked diff. Formal auth/seal admission, production SCM/ACL and full-chain acceptance remain incomplete. No execution policy or production ACL/service/DB/Inventory was changed. `RELEASE_READY=false`, `FULL_CHAIN_VERIFIED=false`.
