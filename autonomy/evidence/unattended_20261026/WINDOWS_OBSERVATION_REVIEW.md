# Windows 本机观测独立审核 / Independent local Windows observation review

结论 / Verdict: PASS_FOR_OPT_IN_LOCAL_OBSERVATION_CONTRACT

范围 / Scope: `autonomy/windows_observation.py`, `test_windows_observation.py`。仅离线注入测试与源码审查，未执行本机 canary 或生产验收。 / Offline injected tests and source review only; no local canary or production acceptance was performed by this reviewer.

实际执行 / Executed: `python -B -m unittest test_windows_observation -q`: 6 tests passed, 0.007 s.

## 已修复发现 / Resolved finding

SID 正则使用 Python Unicode 模式的 `\d`，因此 `S-1-٥-٢١` 通过验证，但随后异常捕获范围外的 `.encode('ascii')` 抛出 `UnicodeEncodeError`。独立注入该 JSON 已复现。这破坏异常分类合同并可能将输入内容带入异常信息。建议使用 `[0-9]` 限定 SID 并加入负例，要求返回 INVALID_OBSERVATION。 / SID validation uses Unicode-aware `\d`, accepting `S-1-٥-٢١`; subsequent `.encode('ascii')` outside the catch raises UnicodeEncodeError. Independently reproduced with injected JSON. This breaks classified failure behavior and may expose input through the exception. Restrict SID digits to `[0-9]` and add a negative test requiring INVALID_OBSERVATION.

审核时字节 / Initial reviewed SHA256:
- implementation: `da19f0508b64535f16a368d782a57bdd13b19a7a7fdd77b0dc6c0b03fb2df4e9`
- tests: `f525b4bed6cfdacaac717016e45fa993c6d8d19dca454844c41e4e918a1649c1`

## 已核查边界 / Reviewed boundaries

默认关闭；默认执行路径由 GetWindowsDirectoryW 构造系统 PowerShell 绝对路径，参数及只读命令固定，超时10秒。严格 JSON 键、重复键、session 整数及日期验证；stderr 和已捕获异常均不回显；signed 与 production_ready 恒为 False。 / Disabled by default; the default executable is built from GetWindowsDirectoryW as an absolute system PowerShell path, with fixed arguments/read-only commands and a ten-second timeout. Exact JSON keys, duplicate keys, integer session and dates are validated. stderr and caught exceptions are not echoed. signed and production_ready always remain False.

runner、directory_resolver、platform 是可信测试注入点，不能作为允许不可信调用方选择命令的接口。2 KiB 是输出验收限制，不是子进程捕获内存硬限制。SID 哈希是稳定伪标识，不是匿名保证。仅有本机事实不能证明完整登录事件覆盖、无人登录运行或生产可信采集者身份。 / runner, directory_resolver and platform are trusted test injection points, not an interface for untrusted command selection. The 2 KiB limit validates output rather than hard-bounding subprocess capture memory. SID hashing provides a stable pseudonym, not anonymity. Local facts alone do not establish full login-event coverage, no-login execution or a production trusted collector identity.

## 最终复核 / Final re-review

最终提交 / Final commit: `9ff81dcc40e25a767a358ac74f1db8f4928e75b6`。
作者已将 SID 数字限制为 ASCII [0-9] 并新增 Unicode SID 负例；独立复跑 `python -B -m unittest test_windows_observation -q`：7 tests passed, 0.005 s。此前阻断问题已关闭，本范围无剩余阻断发现。 / The author restricted SID digits to ASCII [0-9] and added a Unicode SID negative test. Independent rerun: 7 tests passed, 0.005 s. The previous blocking finding is resolved; no remaining blocking finding within scope.

最终 Windows 文件 SHA256 / Final Windows file SHA256:
- implementation: `047a17c8bbc1e3756329eaa10514a46739c8668ccaef0a6c1d6538aa51c3a44c`
- tests: `29bc4075057a2e71877119843f960b389c630264ae436e730a059b0e83841005`

根代理报告了真实本机 canary，但本审核没有独立消费其原始结果，不将其计为本审核执行证据；即使本机 canary 成功，也不是生产验收。 / The root agent reported a local canary; this reviewer did not independently consume its raw result and does not count it as reviewer execution evidence. A successful local canary is not production acceptance.
