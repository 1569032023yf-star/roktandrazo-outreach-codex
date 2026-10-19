# 工作线 C：V6 回归与发布准备 / Workstream C: V6 regression and release preparation

## 结果与范围 / Results and scope

中文：基线为 `0ce0b10`，独立分支 `codex/autonomy-v6`。四套 V6 的注册、内容哈希、路由、冻结正文、CID 原图和发送门禁通过58项定向测试。增加了七项测试，覆盖四类内部QA失败边界及三类开发启动安全合同；不是实际发送。完整结果和可比基线见同目录 `AUTONOMY_V6_VALIDATION_20261020.json`，全量仍未全绿，禁止声称客户发布已放行。

English: Baseline is `0ce0b10`, isolated branch `codex/autonomy-v6`. Four V6 registrations, content hashes, routing, frozen bodies, pinned CID image and sending gates passed 58 targeted tests. Seven added tests cover four internal-QA failure boundaries and three development-startup safety contracts; none sends real email. Full results and the comparable baseline appear in `AUTONOMY_V6_VALIDATION_20261020.json`. The full suite remains non-green and customer release is not cleared.

中文：5a 工作树未提交的 PHASE5A1_FOUR_TEMPLATES_PROGRESS.md 已只读引用，未覆盖；SHA256 为 `c61432e8b26c0dba2da60337ac53f673fa6f0c430fa23ce846bfdc3c04814be8`。未触碰其他工作线业务源文件、生产数据库或 Inventory。

English: The uncommitted PHASE5A1_FOUR_TEMPLATES_PROGRESS.md in the 5a worktree was read only and not overwritten; SHA256 is `c61432e8b26c0dba2da60337ac53f673fa6f0c430fa23ce846bfdc3c04814be8`. Other workstreams' business sources, production databases and Inventory were untouched.

## 工程差异 / Engineering differences

- 中文：回归运行器增加 main 保护及失败退出码；Windows spawn 子进程不得重新执行全量测试、覆盖同一日志或制造假的 network_retry。English: The regression runner now has a main guard and failing exit status; Windows spawn children cannot rerun the suite, overwrite its log or generate false network_retry outcomes.
- 中文：有 .development-copy 标记时，缺 .env 仍使用开发护栏已安装的禁传输及安全数据库配置；无开发标记时仍因缺 .env 报错。未复制生产配置或凭据。English: A marked development worktree without .env retains the already installed blocked transports and safe database; missing .env still fails outside development. No production configuration or credentials were copied.
- 中文：显式UTF-8解码开发路径子进程输出，避免中文路径乱码断言；内部QA新增超时不重试、收件拒绝中止、策略漂移及审计写失败断言。English: Explicit UTF-8 decoding prevents Chinese-path assertion corruption; QA tests now assert no retry after timeout, stopping on recipient rejection/policy drift, and no transport after audit failure.
- 中文：QA 登记清单固定最新唯一收件人及最多四封，新增只含三模块的独立内部补丁和详细正式登记方案；全客户补丁没有扩大发布范围。English: The QA request pins the latest sole recipient and maximum four messages, adds an internal-only three-module patch and a supported registration plan; the customer proposal's release scope was not expanded.

## 四套 V6 状态 / Four V6 states

| 模板 / Template | 开发验证 / Development | 当前正式条件 / Current external condition |
|---|---|---|
| TikTok 历史类目 / Historical category | 通过 / Passed | 截图日期、平台、商品身份未核实；禁止对外排名声称 / Capture date, platform and product identity unverified; external claim blocked |
| 普通零售 / Ordinary retail | 通过 / Passed | TikTok 证据不足自动回退此版 / Automatic fallback when TikTok evidence is insufficient |
| 品牌定制 / Custom production | 通过 / Passed | 已核实业务类型优先于 info@ / Verified business type precedes info@ |
| 转介绍 / Referral | 通过 / Passed | 未知业务类型泛收件箱按门禁路由 / Gated routing for generic inbox with unknown type |

中文：原PNG完整哈希仍为 d2c82e81da5ad3071b2644d3edc2727985edb1c54a1c6a632ac43162874ae81b；没有伪造截图日期或平台证明。普通零售/定制/转介绍不被排名证据缺失阻塞。所有模板尚未生产登记或真实发送。

English: Original PNG SHA256 remains d2c82e81da5ad3071b2644d3edc2727985edb1c54a1c6a632ac43162874ae81b; no date/platform attestation was invented. Missing ranking evidence does not block retail/custom/referral engineering. All variants remain unregistered in production and unsent.

## 回归证据 / Regression evidence

中文：最终对比双方均使用 Python3.13、`-X utf8`、同一受 main 保护运行器、根目录 sys.path 插入和开发护栏。原始0ce基线使用无凭据空开发.env文件，当前开发树无.env；两者都禁用真实外部传输。旧未保护运行器的546/556报告不作为可信可比验收，因 spawn 可重复运行并破坏日志。

English: Both final comparison runs use Python3.13, `-X utf8`, the same main-guarded runner, root sys.path insertion and development guards. Pristine 0ce uses an empty credential-free development .env; the current tree needs no .env. Both block real external transport. Old unguarded 546/556 reports are not reliable comparable acceptance because spawn could rerun tests and corrupt logs.

中文：遗留归档工件位于 Git 未收录的 _archived_scripts/2026-08-07，相关两个失败及一个异常保留原断言，未删除、跳过、用空替身或更改预期。开发副本未包含归档源不能证明真实生产缺档；也不能据此标记全绿。新增V6回归为0时仍保留完整套件非全绿状态。

English: Legacy archive artifacts under Git-omitted _archived_scripts/2026-08-07 are absent; the two failures and one error retain original assertions without deletion, skipping, empty substitutes or changed expectations. Their absence in development does not prove production archives are missing and cannot be presented as a green suite. Zero new V6 regressions still leaves the complete suite non-green.

## 正式入口与未执行事项 / Supported entrypoint and unexecuted work

中文：2026-10-20 00:48:45 +08，实际 rokt-deploy-channel health=200、仅四操作，独立 QA preflight=400 UNKNOWN_RELEASE_ID。凭据从本机Windows凭据管理器取入内存，未输出或保存。没有调用 apply、rollback、生产CLI或真实SMTP。已完成10文件客户候选正反字节演练及仅内部三模块补丁正反演练；离线可逆不等于生产回滚验收。

English: At 2026-10-20 00:48:45 +08, live rokt-deploy-channel health=200 exposed only four operations and the QA preflight returned 400 UNKNOWN_RELEASE_ID. The credential stayed in memory after retrieval from Windows Credential Manager and was neither printed nor persisted. No apply, rollback, production CLI or real SMTP was invoked. The ten-file customer proposal passed byte-exact offline forward/reverse rehearsal, and the internal-only three-module patch passed its separate rehearsal. Offline reversibility is not runtime rollback acceptance.

中文：正式登记具体步骤见 patches/production/phase5a/QA_REGISTRATION_PLAN.md。只通过新登记的内部操作使用腾讯企业邮箱向1569032023yf@gmail.com四模板各最多一封；Gmail无需OAuth。当前发信0，收件/SPF/DKIM/DMARC为UNKNOWN。新客户仍缺有效邮寄地址及其他门禁实际证据；follow_up关闭。CURRENT_STATUS.md和FILE_MANIFEST.md在Git副本缺失，本轮不执行live send。

English: See patches/production/phase5a/QA_REGISTRATION_PLAN.md for precise registration steps. Only a newly registered internal operation may use Tencent enterprise SMTP to send at most one of each template to 1569032023yf@gmail.com; Gmail OAuth is unnecessary. Actual sends=0 and receipt/SPF/DKIM/DMARC=UNKNOWN. Customer sending still lacks a valid postal address and other real gated evidence; follow_up stays disabled. CURRENT_STATUS.md and FILE_MANIFEST.md are absent in the Git copy, and this run performs no live send.

## 风险、下一步及自检 / Risks, next actions and self-check

中文：主要阻塞为正式QA入口未登记、全量归档工件不完整、客户邮寄地址和真实认证缺失；TikTok排名证据只阻塞相关声称。下一步由总控独立review合并开发修复，并通过通道维护方的正式流程登记新发布；新入口支持后实时预检、备份及互斥，再内部试发和收件认证。未修改服务权限或开第二采集调度器。业务新增组织、邮箱、SAFE增长和生产当前运行状态均UNKNOWN；本工作线不伪造业务增量。

English: Main blockers are unregistered QA operations, incomplete archive artifacts, and missing customer postal address/real authentication; TikTok evidence blocks only that claim. Next the coordinator independently reviews and integrates development fixes and arranges new registration through the maintainer's supported process. Then perform live preflight, backup/exclusion and internal QA/receiver verification. Service permissions and acquisition scheduling were unchanged. New business organizations, emails, SAFE growth and current production runtime are UNKNOWN, without fabricated increments.

中文：报告自检通过：中英双语；执行与未执行事项、风险、数量、下一步完整；未完成工作未标完成；无token、密码、cookie、原始客户数据库或凭据。实际内部/客户发送均0。父代理独立review与生产发布验收由总控另记，本报告不虚报已批准。

English: Report self-check passed: bilingual; execution/unexecuted scope, risks, counts and next steps present; unfinished work is not marked complete; no token, password, cookie, raw customer database or credentials. Actual internal/customer messages are both zero. Parent independent review and runtime acceptance are recorded separately by the coordinator and are not falsely claimed here.
