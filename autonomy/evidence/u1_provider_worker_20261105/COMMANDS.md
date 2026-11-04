# 实际验证命令 / Actual validation commands

固定源码 / Fixed source: 9d5ecb6b8062f916ac7869957eb6589665ce9113

- 定向 / Targeted: `python -X utf8 -B -m unittest test_provider_worker test_process_backend test_provider_adapter_binding -v` — 20 PASS.
- 隔离全量 / Clean full suite: `python -X utf8 -B tools/run_comparable_suite.py ABS_EVIDENCE/clean-candidate-suite` in detached `u1-worker-candidate-9d5ecb6`, development-copy marker only; 848 run,37 FAIL,17 ERROR. 原始结果不是全绿 / Raw result is not all green.
- 构建 / Build: `python -X utf8 -B -m autonomy.build_u1_delivery --output ABS/u1-delivery-worker-9d5ecb6 --source-commit 9d5ecb6b8062f916ac7869957eb6589665ce9113 --python-runtime ABS/u1-runtime-32f0246 --runtime-manifest-sha256 5ca4bd5242a6432ea41d18e0140ae0b7b0a999565cb8319aa7cb2dca392a897e` — exit0, timeout1200s.
- 解压核验 / Extracted verification: `python -X utf8 -B autonomy/evidence/u1_provider_worker_20261105/verify_driver.py` — exit0,840s bounded child, VERIFIED,4 probes plus final integrity.
- 包内Worker / Packaged Worker: `python -X utf8 -B autonomy/evidence/u1_provider_worker_20261105/packaged_worker_probe.py` — PASSED,90s child bound, no external requests.

中文：ABS为仓库父目录；实际安装归档位于 C:\Users\15690\Documents\ChatGPT\线下\u1-delivery-worker-9d5ecb6\install.zip。回滚工具同目录rollback-tools.zip，摘要见BUILD.json。未执行安装、服务切换、实际回滚或生产采集。独审PENDING。
English: ABS is the repository parent. Actual archives are in the absolute directory above; rollback-tools.zip is adjacent. Digests are in BUILD.json. No installation, service switch, actual rollback or production collection occurred. Independent review PENDING.
