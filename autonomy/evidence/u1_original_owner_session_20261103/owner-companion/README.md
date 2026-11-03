# 原所有者固定配套包 / Fixed original-owner companion

中文：仅含清单列出的八个固定源码文件及精确摘要，补齐原取锁入口的新依赖。不是自动更新器，不扩大宿主安装器白名单，不允许任意路径。expected_before 是固定 Git 基线的字节条件，不是现场取证；现场只有精确匹配后才能由原正式通道受审替换，缺失或未知已有文件必须 STOP_AND_PRESERVE。未部署，门禁全 false。

English: Only the eight listed fixed source files and exact digests are included, completing new dependencies of the original lock entry. This is not an updater, does not expand the host installer's allowlist, and permits no arbitrary paths. expected_before is a fixed Git-baseline byte condition, not site evidence. A reviewed original-channel update must match it exactly before replacement; missing or unknown existing files require STOP_AND_PRESERVE. Not deployed; every gate remains false.

中文：此包只完成原锁身份、事件和结算接线的工程依赖。正式 Provider 执行协议及服务启动配置仍未完成，不能宣称完整可安装发布版。不要直接解压覆盖现场；生产配置、数据库、凭据和调度器均不在包内。

English: This archive completes engineering dependencies for original-lock identity, event and settlement wiring only. The formal Provider protocol and service activation configuration remain incomplete; this is not a complete installable release. Never extract it over the site. Production configuration, databases, credentials and schedulers are absent.
