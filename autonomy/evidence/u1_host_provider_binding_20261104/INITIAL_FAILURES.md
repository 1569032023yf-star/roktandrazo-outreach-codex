# 初始缺陷 / Initial defects

中文：配置接线候选13f989d的23项安装组合中4 ERROR，InstallVerifier把外置块字典传给base64.b64decode导致TypeError；其余19项通过。修复提交69eb188复用真实文件事务外置内容校验并放宽至包准入上限。修复后先7项验证通过，新增篡改和文件数边界后固定候选42项全部通过。初始组合终端输出未保存为完整文件，不伪造原始日志。
English: The23-test installation combination on13f989d had4 errors because InstallVerifier passed blob-reference dictionaries to base64.b64decode;19 checks passed.69eb188 reuses actual transaction payload verification and aligns capacity with package admission. The first7 verifier checks then pass; after adding tamper/capacity coverage,42 fixed-candidate checks pass. The initial terminal output was not saved as a complete raw file; no reconstructed raw log is claimed.
