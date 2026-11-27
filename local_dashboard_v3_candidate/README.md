# ROKT & RAZO 本机候选看板 / Local candidate dashboard

## 打开方式 / Opening

中文：此候选版本使用本机 8793 端口。可以在项目根目录运行 `python -B -m local_dashboard_v3_candidate.server --port 8793`，然后打开 `http://127.0.0.1:8793/`。服务运行的窗口需要保持打开。`START_DASHBOARD_8793.cmd` 是同一命令的手动启动脚本，尚未单独验证。8791 正式桥接需要另行运行；桥接不可用时，页面会标明读取失败、历史快照或未知，不能据此推断搜索已经停止。

English: This candidate listens on local port 8793. From the project root, run `python -B -m local_dashboard_v3_candidate.server --port 8793` and open `http://127.0.0.1:8793/`. Keep the server window open. `START_DASHBOARD_8793.cmd` is a manual launcher for the same command; it has not been independently verified. The official bridge on 8791 must run separately. When the bridge is unavailable, the page identifies read failures, historical snapshots or unknown values; these do not prove that discovery has stopped.

## 当前能力 / Current capabilities

中文：页面可只读查看桥接状态、城市目录、商家资料、可关联的历史 Inventory 作业与查询明细。作业次数、查询记录和城市完整搜索次数不是同一指标。记录无法确认时显示未知。城市选择目前不能提交正式搜索；固定策略与执行器尚未正式接通。

English: The dashboard reads bridge status, the city catalog, merchant records, attributable historical Inventory jobs and request details. Job counts, query records and completed city searches are different measures. Unsupported facts remain unknown. City selection cannot submit a formal search, and the fixed strategy is not yet integrated with the executor.

中文：保留线索的本机补充和来源快照、模板草稿、图片及版本存放在 `autonomy/runtime/local_dashboard_v3_preview/`；用户应自行备份该目录。它们是本机资料，不会修改正式商家记录或自动进入发送名单。模板尚未接入正式发布或发送，预览效果也不保证与邮件客户端一致。数据可能包含业务信息，不要将该目录提交到版本库。

English: Local lead annotations and source snapshots, template drafts, images and versions are stored under `autonomy/runtime/local_dashboard_v3_preview/`; the user should back up this directory. These local records do not change official merchant records or automatically enter a sending list. Templates are not connected to formal publishing or sending, and previews do not guarantee email-client rendering. The directory can contain business data and must not be committed.

## 安全边界 / Safety boundaries

中文：此候选看板不启动搜索、不向正式队列提交城市、不发送邮件，也不证明生产执行器在线。正式城市入口、Lake Placid 推进修复、独立线索库和发送接入仍需完成、审查与通过原有门禁。各项验证状态以本地实施记录为准。

English: This candidate dashboard does not start discovery, submit a city to the official queue, send email, or establish that the production executor is online. Formal city admission, the Lake Placid advancement fix, an independent lead library and sending integration still require implementation, review and existing release gates. Detailed verification remains in the local implementation records.
