# U1 Worker引用接线 / Worker reference wiring

时间 / Time: 2026-11-04T11:34:36.294895+00:00
固定源码 / Fixed source: f85a5f070a848823ffd5abe438afe4a41687583a

中文：ProcessBackend新增可选成对Provider配置绝对路径/批准SHA256；在写执行意图之前验证真实输入，持有文件及祖先句柄直至子进程清理和结果提交。子进程仅接收路径/摘要CLI引用，不把凭据放入宿主环境、stdin或回执。将引用加入持久执行身份绑定，配置变化不能复用原执行缓存或自动重放。继续要求isolated_offline、原Owner及同一Inventory，Job Object/预算/UNKNOWN保护未绕过。
English: ProcessBackend accepts an optional paired absolute Provider config path/approved SHA256. It validates actual input before execution intent and holds file/ancestor handles through child cleanup and result commit. The child receives only CLI path/digest references; credentials are not exported to host environment, stdin or receipts. The reference joins the durable execution binding, so changed configuration cannot reuse the original cached execution or authorize replay. isolated_offline, original Owner and unique Inventory remain required; Job Object/budget/UNKNOWN protections remain.

中文：38项ProcessBackend/配置固定/原Owner/Stage组合通过，包括真实子进程清理及原锁恢复用例。引用argv/写保护检查使用受控transport替身，不作为正式Provider验收。首轮37项有1项0.15秒用例在进入子进程前耗尽期限，原始输出保留；未改源码生产wall上限。将真实child超时用例设为原1秒上限内的0.8秒，并新增确定性的启动前过期UNKNOWN/不启动child检查；固定69eb的单项0.15秒对照曾通过，不能将该差异隐去。
English: All38 combined ProcessBackend/configuration-pin/original Owner/Stage tests pass, including actual child cleanup and original-lock recovery. Reference argv/write-protection checks use a controlled transport substitute, not formal Provider acceptance. The first37-test combination had one0.15-second test expire before child entry; raw output is preserved. Production wall limits were not changed. The actual child-timeout test now uses0.8 seconds within its original1-second maximum, with a separate deterministic prelaunch-expiry UNKNOWN/no-child check. The fixed69eb single-test0.15-second comparison passed; this difference is not concealed.

中文：本次尚未接通宿主到backend的实际构造调用，也未实现消费配置的正式业务Worker、真实请求/费用/回执结算，均未宣布完成。全量回归/新包/独审PENDING，不能继承69eb包或848项结果。上一69eb包四项运行探针通过但最终完整性600秒超时UNKNOWN，保持原证据，不重放安装。
English: Actual host-to-backend construction and a formal business Worker consuming this reference, real requests/charges/receipt settlement remain incomplete. Full regression/new package/review are PENDING; neither the69eb package nor its848-test result is inherited. The preceding69eb archive passed four runtime probes but final integrity timed out after600 seconds and remains UNKNOWN. Evidence is retained; installation is not replayed.

中文：本周期18:52:23开始，19:37:23前停止领新工作并保存；整轮无平台硬超时字段。没有安装服务/任务、改生产DB、触发Inventory/Provider/邮件。所有最终状态false、BUSINESS_GROWTH=UNKNOWN，allow_install/allow_dispatch/allow_cancel_dispatch/SMTP=false。必读CURRENT_STATUS.md及FILE_MANIFEST.md在此仓库根缺失；已读现有canonical/checkpoint/规范，不据旧文件猜当前状态。报告自检：双语、无凭据、测试/未执行项/风险/下一步明确。
English: This cycle starts18:52:23 and stops new work/checkpoints before19:37:23; no platform whole-turn hard-timeout field is available. No service/task installation, production DB change or Inventory/Provider/email operation occurred. All final statuses are false, BUSINESS_GROWTH UNKNOWN, and all four gates false. Required CURRENT_STATUS.md and FILE_MANIFEST.md are absent at this repository root; existing canonical/checkpoint/rules were read without inferring current state from old documents. Report self-check: bilingual, no credentials, explicit tests/unexecuted work/risks/next action.

下一动作 / Next action:
将宿主已固定Provider引用绑定到原Owner控制的业务Worker构造与入口消费；明确权威费用/终态回执缺失，保持门禁；之后对最终固定源码执行新回归/包验证，不继承69eb结果。
Wire the host-pinned Provider reference into the original owner-controlled business Worker construction and entrypoint consumption; preserve missing authoritative charge/terminal contracts and gates; then run regression/package verification for the final fixed source without inheriting69eb results.
