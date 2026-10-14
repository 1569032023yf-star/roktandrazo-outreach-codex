# 4A.8S 精确补丁离线审查 / Exact patch offline review

中文：本包仅用于 WorkBuddy 独立审查与开发目录中的副本演练。Codex 未部署生产，未手动运行真实 Inventory。生产部署需要另行授权，由 WorkBuddy 负责。

English: This package is for independent WorkBuddy review and copy rehearsals in a development directory. Codex has not deployed production or manually run live Inventory. Production deployment requires separate authorization and is WorkBuddy's responsibility.

## 精确来源 / Exact source

中文：用户指定的 WorkBuddy 4A.5U 报告认可的生产指纹与已有开发副本 `roktandrazo-outreach-dev/bd_orchestrator.py` 完全一致；该目录有 `.development-copy` 标记。副本也逐字节等于开发仓库提交 `a636a99893e19605a3a4e701dc7bf3b9235b6c40` 中的同名 Git blob。读取范围仅为开发副本及 Git 对象，没有访问 WorkBuddy 生产目录。没有采用 WorkBuddy GitHub 的陈旧同名文件。

English: The production fingerprint attested by the user-specified WorkBuddy 4A.5U report exactly matches the existing `roktandrazo-outreach-dev/bd_orchestrator.py` development copy in a directory marked `.development-copy`. This copy is also byte-identical to the same Git blob at development commit `a636a99893e19605a3a4e701dc7bf3b9235b6c40`. Reads were limited to development copies and Git objects, with no access to the WorkBuddy production directory. The stale same-named WorkBuddy GitHub file was not used.

| 字段 / Field | 值 / Value |
|---|---|
| 原始 SHA256 / Before SHA256 | `7afc4d7f6ac18e22bba7cc6a9ea2250dc6d6bafe92128c00c08252731bb2e969` |
| 结果 SHA256 / After SHA256 | `e7e619d3e40f415c1894aa3e1087978875c6f26570755254ab535b68e5580903` |
| 补丁 SHA256 / Patch SHA256 | `3c7ba8d9baf9c6c4e35ecd5cfa5ef91e87b949ef10abad560fe191f768714bda` |
| 原始 / 结果字节数 / Before / after bytes | 30645 / 31552 |
| 原始 / 结果换行 / Before / after endings | LF 651 / LF 661; CRLF 0; BOM absent / 无 BOM |
| 修改范围 / Change scope | `bd_orchestrator.py`; 1 file / 文件; 3 hunks / 补丁块 |

中文：应用结果逐字节等于已验证的 4A.8R 提交 `df209f529ac1925da3689ebf0bc38c8b8ada8c0d` 的 Git blob。不是用整份开发工作树文件覆盖生产；Windows 开发检出文件本身采用 CRLF，不能作为精确生产补丁的结果来源。

English: The applied result is byte-identical to the Git blob at the validated 4A.8R commit `df209f529ac1925da3689ebf0bc38c8b8ada8c0d`. This is not a whole-development-file production replacement. The Windows development working-tree file uses CRLF and must not be substituted for the exact production result.

## 独立核验 / Independent verification

中文：在开发仓库克隆内，将获准的原始文件按二进制复制到 `output/review-4a8s/source.py`。其 SHA 必须匹配上表。核验器只允许读取 `.development-copy` 根目录之内的文件，输出目录必须不存在。它不导入或执行生产业务模块，不打开数据库，不使用网络，不调用 Git，不改变输入副本。

English: In a development repository clone, copy the approved original file in binary mode to `output/review-4a8s/source.py`. Its SHA must match the table. The verifier only reads files inside a root marked `.development-copy`, and the output directory must not already exist. It does not import or execute production business modules, open databases, use the network, invoke Git, or change the input copy.

```powershell
python -X utf8 patches/production/phase4a8s/verify_production_patch.py --source output/review-4a8s/source.py --review-root . --output-dir output/review-4a8s/rehearsal
```

中文：成功退出码为 0；任何原始 SHA、补丁 SHA、上下文字节、结果 SHA 或备份校验失败都退出 2。拒绝 CRLF/BOM/混合换行源文件，不能通过换行归一化“修复”指纹。重复应用也会拒绝。成功的 `verification.json` 是离线演练证明，不是部署证明。

English: Success exits with code 0. Any source SHA, patch SHA, context-byte, result SHA, or backup verification failure exits with code 2. CRLF, BOM, and mixed-ending source files are rejected; do not normalize their endings to bypass the fingerprint check. Repeat application is rejected. A successful `verification.json` proves offline rehearsal, not deployment.

## Windows 字节保护 / Windows byte protection

中文：补丁在开发仓库 `.gitattributes` 中标记为 `-text`，防止 `core.autocrlf=true` 在克隆/检出时改写补丁。核验器使用 `read_bytes`/`write_bytes`，不经过 Git checkout、文本重编码或换行转换。另已在隔离 Git 仓库中，用 `core.autocrlf=true` 和临时属性 `bd_orchestrator.py -text` 验证 `apply --check`、应用、`apply --reverse --check` 和逆向回滚，均得到预期 SHA。临时属性仅用于演练，没有修改生产属性或 Git 配置。

English: The development `.gitattributes` marks the patch as `-text`, preventing `core.autocrlf=true` from rewriting it during clone/checkout. The verifier uses `read_bytes`/`write_bytes`, without Git checkout, text re-encoding, or newline conversion. A separate isolated Git repository also verified `apply --check`, application, `apply --reverse --check`, and reverse rollback with `core.autocrlf=true` and the temporary attribute `bd_orchestrator.py -text`; all hashes matched. This temporary attribute was rehearsal-only; production attributes and Git configuration were not changed.

## 备份与回滚 / Backup and rollback

中文：演练先校验原文件，创建原始字节备份并重新校验，再写入候选副本并重新读取校验。回滚使用重新校验后的备份字节；逆向补丁也必须产生相同原始 SHA。备份损坏或换行改变则拒绝回滚。实际部署前由 WorkBuddy 另行复核实时原始 SHA、持久化备份及备份 SHA；部署后复核结果 SHA、字节数及 LF。出现任何不一致应停止，不得仅以 diff 看似正确作为验收。

English: Rehearsal verifies the original, creates and re-verifies a byte-exact backup, then writes and re-reads the candidate copy. Rollback uses the re-verified backup bytes; reverse application must independently reproduce the original SHA. Corrupted or newline-converted backups are rejected. Before a separately authorized deployment, WorkBuddy must re-check the current source SHA and persist and verify its backup. After deployment, verify the result SHA, byte count, and LF endings. Any mismatch requires stopping; an apparently correct diff is insufficient acceptance.

中文：`DISCOVERY_PATH_EXECUTED=true` 表示进入受控发现调用，不能据此宣称真实 Provider 请求成功或新商家/邮箱增长。生产成效需要 WorkBuddy 在获准部署后独立观测。

English: `DISCOVERY_PATH_EXECUTED=true` means entry into the bounded discovery call; it does not prove successful live Provider requests or growth in merchants/emails. WorkBuddy must independently observe production effectiveness after an authorized deployment.
