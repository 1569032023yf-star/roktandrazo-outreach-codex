# U1 安装输入性能修复 / Installer input performance fix

固定源码 / Fixed source: 1bf8d59aa1d9ce8ecb78da6590626bcf4380962f
时间 / Time: 2026-11-05T01:32:39.427007+00:00

中文：真实Publisher安装输入校验原先逐项扫描已见路径，并通过列表成员判断区分文件和脚本。现改为文件集合、父目录集合和显式条目类别，路径冲突检查随路径深度增长，避免完整CPython包数千文件的平方级扫描。保留全部逐文件大小、SHA256、句柄、硬链接、reparse、身份复核与安全门禁。不声称该开销是上一轮超时的唯一原因。
English: The real Publisher installer validator previously scanned all prior paths and used list membership to classify files/scripts. It now uses file/parent sets and explicit entry categories, bounding namespace checks by path depth for thousands of CPython files. File size, SHA256, handle, hardlink, reparse, identity revalidation and safety gates remain enforced. This overhead is not claimed as the sole cause of the previous timeout.

中文：20项定向测试通过，包含真实Windows句柄禁止写入/删除/祖先重命名，大小写别名和双向前缀冲突拒绝；测试命令见STATUS.json。新固定源码完整回归、新包和独审PENDING。既有21568c8包最终完整性仍UNKNOWN；未重复构建或删除历史证据。C盘只读采样2714652672字节可用。未执行安装、服务启用、生产采集或邮件。
English: 20 targeted tests pass, including real Windows write/delete/ancestor-rename exclusion, case aliases and both prefix collision orders; see STATUS.json for command. New-source full regression, package and independent review remain PENDING. Existing21568c8 archive final integrity remains UNKNOWN. No rebuild or historical evidence deletion. C-drive read-only sample:2714652672 free bytes. No installation, service activation, production collection or email.

中文：不重置此前09:34:20运行截止时间来继续领取重任务。当前恢复点更新canonical、Git投影及交付状态。全部最终状态false，BUSINESS_GROWTH UNKNOWN，门禁false；正常下一步自主推进。
English: The existing09:34:20 cycle deadline is not reset to claim more heavy work. Canonical queue, Git projection and delivery status are synchronized. All final states false, BUSINESS_GROWTH UNKNOWN, safety gates false; routine next steps remain autonomous.

下一动作 / Next action: 对1bf8d59进行可比回归；单独核验现有21568c8包最终完整性，不重建、不继承旧验收。Run comparable regression for1bf8d59 and separately check existing21568c8 final integrity without rebuild or inherited acceptance.
