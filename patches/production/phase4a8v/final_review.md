# Inventory轨迹候选最终独审 / Final inventory trace candidate review

结论：APPROVED，限定为候选工程审核，不等于登记、部署或自然业务验收。作者codex:/root/legacy_retry_investigation，审核者codex:/root/independent_reviewer，身份不同。正式补丁唯一目标bd_orchestrator.py，4个hunk。
Verdict: APPROVED for candidate engineering only, not registration, deployment or natural business acceptance. Author and reviewer identities are distinct. The sole production patch target is bd_orchestrator.py, with four hunks.

patch SHA256: 2c4e1750fe7e39c996baa731bed740e8b2ef08546147b1f9976e25ae550c2081
before SHA256: e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903
after SHA256: 0ddb12feea430a30166a2d1b8acbb1650205d608c52e2e2d808db183665454c8

独立14/14离线测试通过，0.237秒；前后源码/补丁/测试hash一致。临时目录Git完整正向check+apply与反向check+apply逐字节匹配；显式core.autocrlf=false避免全局Windows转换干扰。另仅AST提取既有executor.apply_unified纯函数，未导入其模块，正反向同样精确匹配，见executor_roundtrip.json。未运行候选生产CLI或任何生产接口。
Independent offline tests pass 14/14 in 0.237 seconds, with stable pre/post hashes. Full Git forward/check/apply and reverse/check/apply match exact bytes in a temporary directory, explicitly disabling global newline conversion. AST-only extraction of the existing executor pure patch function also matches in both directions without module import. No candidate production CLI or production interface was run.

初审两项已关闭并保留证据：最终trace曾在finish之后，注入故障得到completed再stopped；现移finish前，失败仅stopped并释放锁。patch曾CRLF不能应用于LF精确基线；现diff_bytes/write_bytes产生LF，新增固定字节差异回归。
Two initial findings are closed with evidence retained: terminal trace formerly followed finish and could change completed to stopped; it now precedes finish and fails closed with one stopped outcome and lock release. CRLF patch text formerly failed against the exact LF baseline; byte-based generation and a regression now enforce exact LF patch bytes.

仅新增helper及inventory局部轨迹，其他AST不变。current_step保存有界20事件/16KiB白名单JSON序列，每项UTC时间、phase/outcome及可选非负数city_id/count；无商家、邮箱、域名、异常消息。正常路径16事件，阶段错误保留enter与inventory failed，不伪造未完成阶段complete。事件complete表示调用返回或路径结束，仍须结合job status/stop_reason，不能当Provider请求成功或业务完成。
Only the helper and inventory trace are changed; unrelated AST is identical. current_step stores an allowlisted bounded JSON sequence (20 events/16 KiB) with UTC timestamps, phase/outcome and optional integer city ID/count, without business identities or exception text. Normal flow has 16 events; failure retains entry plus inventory-failed evidence without fabricated completion. Complete means return/path end, not provider or business success; consumers must also inspect job status and stop reason.

所有带owner的跨连接update trace在with conn事务外，helper拒绝owner.in_transaction；临时SQLite双连接测试验证事务内拒绝、提交后写成功。原lane顺序/预算、目标满足仍discovery、dryrun/锁冲突不采集、状态错误及provider停止条件保持。异常清理保留原错误，二次trace失败被抑制，conn及锁走既有finally。
Cross-connection trace writes occur outside owner transactions and the helper rejects active ownership. A temporary real SQLite two-connection test verifies rejection during transaction and success after commit. Lane order/budgets, discovery despite sufficient inventory, dry-run/lock conflict, state/provider stops remain. Secondary trace errors do not replace primary errors, and connection/lock cleanup follows the existing finally paths.

observe_bd_production.py仅EXPECTED的orchestrator常量改为上述afterSHA，其他逻辑不变，独立AST核对匹配；未运行该helper。部署未成功前它预期failclosed，部署失败/回滚需对应恢复pin。此本地常量不是生产源已变化证据。
The observation helper changes only its orchestrator EXPECTED constant to the after SHA; AST inspection confirms the match. It was not invoked and must fail closed before successful deployment. Failure/rollback requires restoring its matching pin. The local constant is not evidence of a production source change.

限制：不回填旧run；不证明556重试ledger原因、SAFE净增长、全局唯一、无人值守C3或城市完成。正式门禁、备份、apply/status及原Inventory下一自然run阶段序列仍需真实证据。未更改SMTP或客户数据，报告双语，审核者不修改源码/不提交。
Limitations: no historical backfill or proof of the retry-ledger cause, SAFE growth, global uniqueness, C3 or city completion. Formal gates/backups/apply/status and stage evidence on the next original natural Inventory remain required. No SMTP/customer changes; reviewer made no source edits or commits.
