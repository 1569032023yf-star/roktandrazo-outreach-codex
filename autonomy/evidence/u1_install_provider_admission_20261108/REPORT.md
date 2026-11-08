本轮核查真实Publisher安装调用链并修复安装前只验证Provider外层配置的问题：现复用宿主的真实适配器构造验证，Google位置配置为数组时在安装前拒绝。保留配置哈希/文件锁及所有安装门禁，无网络请求。24项定向组合通过（15.473秒），覆盖真实安装器拒绝、无进程启动、输入不变及失败释放锁。

Audited the real Publisher install chain and fixed outer-only Provider validation: installer now reuses host real-adapter construction admission, rejecting Google location arrays before installation. Configuration hashes and locks and all install gates remain in force; no requests.24 targeted combined tests pass in15.473s, including real installer rejection, no process launch, unchanged inputs and released handles after failure.

Source: c2e81ff6e333ae64c2af1a2160ddcd972953bd74
Start:2026-11-08T17:07:39.9799555+08:00
End:2026-11-08T09:11:08.997286+00:00
Worktree:D:\CODEX\roktandrazo-workspace\u1-provider-paths-20261108
Start SHA:351af24fdbb0c236a5c8362bb506beac102d6b1f

Validation: python -B -m unittest test_install_command test_provider_environment test_u1_host_runtime
24 PASS;15.473 seconds; controlled dev_cycle deadline180 seconds.

Independent review PENDING. New source archive NOT_BUILT; previous package applies only to70d85c6. Main/canonical unchanged because shared chat-entry coordination is unverified; Git queue is projection only. DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN. allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false. Billing/terminal evidence CONTRACT_MISSING. Next: fixed-source package verification and independent review, then coordinated main integration; no production installation.
