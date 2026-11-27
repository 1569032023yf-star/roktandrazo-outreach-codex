# 商家搜索看板进展 / Discovery dashboard progress

日期 / Date: 2026-11-26 (Asia/Taipei)

## 当前状态 / Current status

中文：现有本地看板可查看最近一次作业的城市、保存的阶段计数、城市查询记录、候选商家、完成检查、卡点和各数据来源的读取时间。计划只能保存为本地草稿，尚不能提交正式任务。执行器的实时心跳、当前活动和每轮新增商家归属仍未知。

English: The existing local dashboard can show the city associated with the latest recorded job, saved stage counts, city query records, candidate merchants, completion checks, blockers and observation timestamps. Plans are local drafts only and cannot be submitted as formal jobs. Live executor heartbeat, current activity and per-run new-merchant attribution remain unknown.

中文：开发候选版新增最近保存步骤和事件时间，使用独立端口与本地存储；这不是实时心跳。候选版未完成真实浏览器验收，不能视为已正式发布。

English: The development candidate adds the last persisted stage and event time using a separate port and local store; this is not a live heartbeat. Browser acceptance remains incomplete, and the candidate is not a production release.

## 搜索修复 / Search fix

中文：开发代码调整了城市完成检查，使社交网站网址不再被计为实际关联处理入口无法执行的官网重试。隔离测试验证线索保留及符合其他结束条件时的城市推进；生产环境尚未应用，不能声称生产问题已解决。

English: Development code adjusts the city completion check so a social URL is not counted as official-site retry work that the linked processor cannot execute. Isolated tests cover lead preservation and city advancement when other completion conditions pass. The change has not been applied in production; production resolution is not established.

## 验证与未完成事项 / Validation and remaining work

中文：针对性离线测试 20 项通过；本机 HTTP 测试因执行环境套接字权限受限未通过。扩展回归 82 项通过、3 项失败；三项失败使用修改前队列代码也可复现，根因尚未明确。正式计划接入、按城市保留并手动补充邮箱的线索库、真实搜索结果及受控邮件发送链仍需开发与验收。不能把测试数量当成业务成果。

English: Twenty targeted offline tests passed; loopback HTTP verification was blocked by socket permissions in the execution environment. Broader regression produced 82 passes and 3 failures; all three also reproduced with the pre-change queue code, and their root cause remains unknown. Formal plan intake, a city-scoped retained-lead store with manual email entry, real discovery results and the controlled sending chain still require development and acceptance. Test counts are not business outcomes.

中文：用户已手动关闭 WorkBuddy 每日自动任务；本次未重启、新建或恢复。未执行真实搜索、发信、安装、部署或修改生产数据库。

English: The user manually disabled WorkBuddy daily automations; none were restarted, created or restored. No real search, email sending, installation, deployment or production database modification was performed.

## 下一步 / Next steps

中文：定位三项回归失败，检查生产补丁兼容性，完成候选看板本机验收，然后继续按城市保存线索和正式任务链路。自动上传后续任务结果及自动触发判断尚未实现。

English: Investigate the three regression failures, check production patch compatibility, complete local dashboard acceptance, then continue city-scoped lead retention and the formal task chain. Automatic upload of future task results and automatic evaluation have not yet been implemented.


## 2026-11-27 更新：本机验收与生产修复状态 / Update: local acceptance and production repair

中文：以下更新取代上文关于“候选看板未完成浏览器验收”和“本机 HTTP 测试受限”的旧状态。本机只读看板已在 http://127.0.0.1:8792/ 启动，连接 8791 既有桥接和生产数据库只读视图；已通过浏览器检查首页、刷新和城市详情。11 月 27 日重新启动看板和已有桥接后，页面显示桥接读取成功。服务未设置新的开机自启。

English: This update supersedes the earlier statements that browser acceptance was incomplete and loopback HTTP verification was blocked. The local read-only dashboard was started at http://127.0.0.1:8792/ using the existing 8791 bridge and a read-only production database view. The home page, refresh and city details were checked in a browser. On November 27 the dashboard and existing bridge were restarted and the page reported a successful bridge read. No new startup automation was configured.

中文：Lake Placid 的 LDR 653 网址判断修复仅存在开发代码中。对当时生产记录进行只读模拟，原规则将 653 列为关联重试，调整判断后现有完成检查通过，Oneonta 是下一候选；653 原始线索保留。生产代码未部署，未执行真实关城或切城；一城一次和资料补充独立的完整流程仍未完成。

English: The LDR 653 URL-gate fix exists only in development. A read-only evaluation of then-current production records showed that the old rule listed 653 for linked retry; with the adjusted rule the existing completion checks passed and Oneonta was the next candidate, while the original lead remained intact. No production fix, actual city closure or transition was performed. The complete one-search-per-city and separate enrichment workflow remains unfinished.

中文：看板没有可靠的执行器实时心跳或本轮新增归属，相关项目显示未知。正式任务提交未接通，保留线索为只读视图，手动补充邮箱和受控发送链仍未交付。原有业务数据库未修改，未执行真实商家搜索或客户邮件发送；用户关闭的 WorkBuddy 每日自动任务未恢复。

English: The dashboard lacks reliable live executor heartbeat and per-run new-merchant attribution, which remain unknown. Formal task submission is disconnected; retained leads are a read-only view, and manual email enrichment and the controlled sending chain are not yet delivered. The business database was not modified, and no real merchant discovery or customer email was performed. The user's disabled WorkBuddy daily automation was not restored.

中文：本机看板代码和城市修复工作当时仍为本地未提交文件；本报告更新不代表代码已经上传或生产部署。之前扩展回归的三项失败原因仍未查明。

English: The local dashboard code and city fix were still uncommitted local files at the time of acceptance; this report update does not mean the code was uploaded or deployed to production. The causes of the three earlier broader regression failures remain unresolved.
