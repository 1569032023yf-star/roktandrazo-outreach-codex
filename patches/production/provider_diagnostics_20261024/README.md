# Provider 诊断发布候选 / Provider diagnostic release candidate

中文：固定源码 `8d63d2d45393509589261a1ddd0bbcf650a0d1b2`，基线 `eceb019b70a3b24a1d90a4efeebd3692c446dd2c`。生产补丁仅修改三个已有文件：discovery/models.py、discovery/providers/browser_maps.py、discovery/providers/browser_maps_scraper.py。开发兼容导出模块不进入生产包。现有正式执行器对新增文件的备份和删除式回滚不兼容，因此采用已有模块承载合同，无须改动执行器。

English: Source is pinned to `8d63d2d45393509589261a1ddd0bbcf650a0d1b2`, based on `eceb019b70a3b24a1d90a4efeebd3692c446dd2c`. Only three existing production files change: discovery/models.py, discovery/providers/browser_maps.py and discovery/providers/browser_maps_scraper.py. The development compatibility export module is excluded. The official executor cannot back up or restore absence for new files, so the contract lives in an existing module without changing the executor.

## 诊断与功能边界 / Diagnostic and behavioral boundaries

中文：固定枚举和阶段不携带原始异常文本。分类只保留明确证据；feed存在不把超时改判为DOM变化，卡片读取保留网络/浏览器异常，未知异常仍UNKNOWN。失败页不推进游标；单店成功仍终止分页。另有隔离夹具证实的行为修正：实例缓存不落入全局目录、空缓存正确复用、形状异常及带错误的成功缓存拒绝消费、资源逐项释放。它们不证明历史scrape_error根因，也不自动改变生产配置或重试政策。

English: Fixed enums and stages carry no raw exception text. Only explicit evidence is classified: feed presence does not turn a timeout into a layout diagnosis; card reads preserve network/browser evidence and unknown exceptions stay UNKNOWN. Failed pages do not advance cursors; direct-place success remains terminal. Fixture-proven behavior corrections also cover instance-local caching, empty-cache replay, rejection of malformed/conflicting success data, and independent resource cleanup. These do not establish the historical scrape_error cause or alter production configuration/retry policy automatically.

## 门禁 / Gates

中文：三文件补丁使用现有通道纯解析器通过正反向字节一致性验证。browser_maps与models基线LF字节匹配正式health指纹。scraper批准生产源码/指纹及该路径封签范围仍缺；生产service与开发基线不同，集成夹具不能替代精确生产兼容测试。完整测试已执行基线对照，不能掩盖基线既有失败。满足批准快照、独立审核、精确生产回归后才能正式register、preflight、安全窗口、apply、status。当前RELEASE_READY=false。

English: All three patches pass exact forward/reverse byte checks using the official channel's pure parser. Baseline browser_maps and models LF bytes match live health fingerprints. Approved scraper production source/hash and sealed path scope remain missing; production service differs from development, so integration fixtures cannot replace exact production compatibility checks. Full regression is baseline-compared without hiding existing baseline failures. Approved snapshots, independent review and exact production regressions precede register, preflight, safety window, apply and status. RELEASE_READY=false.

## 回滚 / Rollback

中文：正式通道在原Inventory互斥下验证逐文件before SHA并备份。apply后验证所有after SHA。未知结果先按operation_id查询status，禁止盲目重apply。回滚核对当前after SHA与备份before SHA，仅由原正式机制恢复三份原字节；本包不新增/删除生产文件。回滚后再次status/health验证，SMTP保持关闭。4A8V/4A8W不重复部署。

English: Under original Inventory exclusion, the official channel verifies and backs up every before hash, then verifies all after hashes following apply. Reconcile unknown outcomes with operation-ID status before any action; never blindly reapply. Rollback checks current after and backup before hashes and restores the three original byte sequences through the same official mechanism. No production file is added/deleted. Verify status/health again with SMTP off; never reapply 4A8V/4A8W.

## 未执行及续接 / Not executed and continuation

中文：无联网canary、生产写入、第二Inventory或邮件；固定夹具不计正式SAFE。继续消费Issue2正式交接，取得缺失快照后重建精确包并复审；跟踪原Inventory自然运行。历史根因、稳定性和业务增长均不宣称已验收。

English: No online canary, production mutation, second Inventory or email; fixtures never count toward production SAFE. Continue consuming the formal Issue2 handoff, rebuild/re-review against missing approved snapshots, and observe original natural Inventory runs. No historical-root-cause, stability or business-growth acceptance is claimed.
