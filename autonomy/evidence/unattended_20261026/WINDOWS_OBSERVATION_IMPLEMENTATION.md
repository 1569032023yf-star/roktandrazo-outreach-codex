# Windows 本机只读观测 / Windows local read-only observation

实现 / Implementation: autonomy/windows_observation.py 默认 disabled，无进程或网络。显式启用仅支持 Windows，Windows API GetWindowsDirectoryW 定位系统 PowerShell 绝对路径，固定参数、固定脚本、shell=False、隐藏窗口、10 秒 timeout、不重试。脚本只读取 Win32_OperatingSystem 启动时间、当前 WindowsIdentity SID、当前进程 SessionId 与观测 UTC。
Default-disabled collection performs no IO. Explicit opt-in uses Windows API system-directory resolution and fixed PowerShell arguments/script without shell, a hidden window and a ten-second timeout with no retry. Only OS boot time, current identity SID, process session and UTC observation time are collected.

输出 / Output: 严格四字段 JSON，拒绝重复键/额外字段/非法类型与日期；stdout/stderr 各限 2048 字节，固定失败原因，无原始异常输出。SID 只在子进程及 Python 内存短暂存在，再以域分离 SHA256 输出 opaque 标识，不记录原 SID。输出 signed=false、production_ready=false；观测失败 facts=null，不能解释为生产零值或已排空。
Strict four-field JSON rejects duplicates, extra fields, invalid types and dates. Each captured stream has a 2048-byte validation limit. Failure codes are fixed and exceptions are not echoed. Raw SID exists transiently in child/Python memory only, then becomes a domain-separated SHA256 opaque identifier. Output is unsigned and never production-ready; missing facts remain unknown.

测试 / Tests: python -B -m unittest test_windows_observation -q，6 项通过。覆盖默认关闭/非 Windows 不执行、固定 argv、脱敏成功、timeout/进程错误、输出限制、严格 schema、重复键、非法时间与 JSON。
Six tests pass, covering disabled/non-Windows behavior, fixed invocation, redaction, timeouts/errors, output limits, strict schema and malformed JSON/timestamps.

限制与未执行 / Limits and non-actions: subprocess.run 捕获流的长度限制在进程返回后生效，不是恶意进程硬内存上限；固定脚本输出字段有界。SID 哈希是稳定假名，不等于不可逆匿名。未执行真实 canary、网络/7877 探测、数据库、签名、注册表、ACL、任务安装或生产操作；不证明无人登录运行、可信 OS 来源或生产身份批准。
The capture limit is post-return validation, not a hard memory sandbox against a malicious child. Fixed script fields are bounded. Stable SID hashes are pseudonyms, not anonymization. No live canary, network/7877 probe, database, signing, registry, ACL, task installation or production action was performed. Local observations do not prove unattended operation, collector authenticity or approved production identity.

下一步 / Next step: 父任务独审，可显式执行一次本机 canary，只保存脱敏结果；不签名批准。开发定向测试完成，审核 PENDING，未提交/发布/部署。报告自检中英双语、结果/数量/风险/未执行/下一步齐全，无真实身份或秘密。
Parent review precedes an optional explicit local canary retaining redacted output only. Targeted development tests complete; review pending, with no commit/release/deployment. Bilingual report self-check covers outcomes, counts, risks, non-actions and next steps without real identities or secrets.
