# Windows观测交付 / Windows observation delivery

源码9ff81dcc40e25a767a358ac74f1db8f4928e75b6新增可实际执行的只读观测器：默认关闭，显式启用才通过Windows API定位系统PowerShell，固定脚本采集当前身份SID、session和启动/观测时间；仅返回SID哈希及必要事实。10秒超时且不重试，无任意命令入口或签名密钥。 / Source adds an executable read-only observer: disabled by default, opt-in uses Windows API to locate system PowerShell and a fixed script for SID/session/boot/time facts. Only an opaque SID hash and necessary facts are returned. A10-second timeout has no retry; there is no arbitrary-command interface or signing key.

本机真实canary得到LOCAL_FACTS_OBSERVED，脱敏事实仅存ignored runtime/u1_windows_observation_local.json。它只证明当前开发会话能够读取本机事实；不证明生产身份、无登录运行、8791存活、排空/互斥或网络出口。signed=false、production_ready=false。 / A real local canary returned LOCAL_FACTS_OBSERVED; redacted facts remain only in ignored runtime. This proves local observation in the current development session, not production identity, login-free execution,8791 survival, drain/exclusion or egress. signed and production_ready remain false.

独审发现Unicode数字可穿过SID正则并触发ASCII编码异常，已改为ASCII数字及新增回归用例。独立7项通过（0.005秒）；最终主线模块组合114项通过（8.534秒）。见WINDOWS_OBSERVATION_REVIEW.md。 / Independent review reproduced Unicode SID digits escaping validation and raising an ASCII encoding error. ASCII-only validation plus a regression test fixes it. Independent7 tests passed; final combined114 tests passed. See the review report.

首次尝试从stdin运行多进程测试触发Windows spawn无法载入stdin，已停止该次尝试，改用标准python -m unittest成功完成；中断运行不算通过。输出2KiB是接收后校验，不是原生进程内存硬限。SID短暂存在子进程及Python内存，不写报告或日志。 / An initial stdin-based multiprocessing run failed because Windows spawn cannot reload stdin; it was stopped and replaced by a successful standard module run. The interrupted attempt is not a pass. The2KiB output bound is post-capture validation, not a native-process memory sandbox. SID exists briefly in process memory and is not logged.

Issue2最新仍6435605069，无重复请求；没有生产数据库访问、网络采集、任务安装、ACL/身份变更或邮件。下一步仍为正式collector信任根及现有Inventory backend/发布器合同接入；可审核生产包后才申请最小权限。 / Issue2 still ends at6435605069 without duplicate requests. No production DB access, collection, installation, ACL/identity changes or mail. Next: formal collector trust provisioning and existing Inventory backend/publisher contracts; minimum permissions follow a reviewable production package.

DEVELOPMENT_COMPLETE=false (overall U1); SCOPED_REVIEW_PASSED=true; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.

报告自检：双语，实际失败与复测、未执行、限制及下一步明确，无原SID、客户资料和秘密。 / Self-check: bilingual with actual failure/rerun, exclusions, limits and next steps; no raw SID, customer data or secrets.
