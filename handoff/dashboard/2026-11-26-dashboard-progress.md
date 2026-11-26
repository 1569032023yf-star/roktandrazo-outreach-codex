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
