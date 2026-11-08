# U1 Host 清理失败候选与恢复点 / Host cleanup-failure candidate and checkpoint

日期 / Date: 2026-11-08. 本分支起点 / Branch start: `4d394cb29eb174853867947c84365684ff60f5b1`. 候选基准 / Candidate baseline: `c2e81ff6e333ae64c2af1a2160ddcd972953bd74`, from `codex/u1-provider-paths-20261108`.

## 结果 / Results

中文：该基准的 `ServiceChild.Dispose` 在 Job 清理或直接子进程退出无法确认时仍关闭句柄并释放文件固定，可能允许仍未确认退出的进程所依赖的文件被修改。候选 `RoktU1Bridge.cs` 在 Job 终止、Job 清空、句柄关闭或进程退出未确认时抛出错误并保留尚持有的句柄和文件固定；可在对象仍存活时重试清理。源码是放在本目录的独立候选，不是已经接入当前分支安装器的生产代码。它仅相对上述基准的 Dispose 不同，须经 Agent C 复审、移植并重新构包。

English: At the pinned baseline, `ServiceChild.Dispose` releases file pins even if Job cleanup or direct-child termination cannot be confirmed. Files used by a process of unknown state may then become writable. The candidate retains still-held handles and file pins and raises on unverified termination, empty-Job observation, handle close or process exit; cleanup can be retried while the object remains alive. This directory is a standalone candidate, not code wired into this branch's installer. Only Dispose differs from that baseline; Agent C must review and port it and rebuild the package.

## 测试 / Tests

中文：使用本目录为 TEMP/TMP 的隔离临时目录，运行 `python -B -m unittest -v host_candidate_20261108.test_native_host_cleanup`，Windows 实际 Job 对象、子进程和孙进程的 5 项通过。注入一次 Job 查询失败时，运行中固定的脚本拒绝写入；第二次清理成功后可写。将同一测试用于基准源码，预期失败：清理失败后文件可写。原始系统临时目录测试因沙箱权限失败；改为工作区临时目录后通过。最初的基准注入方式不适配旧源码而超时，已修正注入方式并复测；超时产生的本轮临时文件已清理。

English: With TEMP/TMP pointed at an isolated workspace directory, `python -B -m unittest -v host_candidate_20261108.test_native_host_cleanup` passed 5 checks using actual Windows Jobs and fixture child/grandchild processes. With one injected Job-query failure, writing the pinned script was denied until successful cleanup retry. The same test against baseline failed as expected: the script was writable after cleanup failure. Initial use of the sandbox system temporary directory failed on permissions; the workspace temporary directory passed. An initial baseline injection did not match old source and timed out; the injection was corrected and rerun, and its workspace fixture files cleaned.

## 未执行、风险与下一步 / Not executed, risks and next steps

中文：未安装或启动 Windows 服务，未执行 SCM、注销/重启、真实升级回滚或生产验收；未改生产 ACL、计划任务、注册表、数据库、代理或 SMTP。独立审核、完整包、Worker 业务闭环和正式 Provider 合同仍待完成；最近固定 c2e81ff 的包内 bootstrap 在离线 stage 超时，原因 UNKNOWN。本候选并未解决这些问题，未验证对象被丢弃或进程终止后的固定句柄寿命，不可作为全链路故障恢复验收。共享锁跨聊天有效性未证明，未修改主控树或其 checkpoint。下一步复审该候选及所有调用方对清理失败的处理，集成后重跑定向测试和固定包验证，并在获准隔离 Windows 环境核验 SCM 生命周期。

English: No Windows service was installed or started; SCM, logoff/reboot, actual upgrade/rollback and production acceptance were not performed. No production ACL, task, registry, database, proxy or SMTP changes were made. Independent review, complete package, Worker business closure and formal Provider contracts remain outstanding; the latest c2e81ff packaged bootstrap timed out in offline stage, cause UNKNOWN. This candidate does not resolve those gaps. Pin lifetime after losing the object or process termination was not validated, so this is not end-to-end recovery acceptance. Cross-chat shared locking remains unproven; no main checkout or shared checkpoint was changed. Next review this candidate and all callers' cleanup-failure handling, integrate and repeat targeted/package checks, then verify SCM lifecycle in an authorized isolated Windows environment.

计数 / Counts: 1 standalone source candidate, 1 test file, 5 passing targeted checks; 1 expected baseline failure. `DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN`. 安装、派发、取消派发及 SMTP 未启用 / Install, dispatch, cancel dispatch and SMTP were not enabled.

敏感信息与报告自检 / Sensitive information and report self-check: 双语、结果、未执行、风险、数量及下一步已列；未包含凭据或收件人。 / Bilingual results, unexecuted work, risks, counts and next steps included; no credentials or recipients included.
