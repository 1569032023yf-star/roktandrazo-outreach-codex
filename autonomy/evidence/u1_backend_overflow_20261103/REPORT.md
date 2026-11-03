# U1 回执数值溢出修复 / Receipt numeric overflow fix

固定源码 / Fixed source: 177c6decad24d23ba0091a21a03e00f1ef6eae99 | 2026-11-03T12:07:42.502949+00:00

修复backend回执解析：1e999及-1e999原本绕过parse_constant转换为Infinity，现在parse_float显式拒绝非有限值；UNKNOWN持久化和禁止重放合同保持有效。
Backend receipt parsing now rejects overflowing numeric literals such as 1e999 and -1e999 via parse_float. Previously these bypassed parse_constant. Durable UNKNOWN and no-replay contracts remain enforced.

验证 / Validation: python -B -m unittest test_process_backend -q — 6 PASS, 3.927s, including real subprocess overflow output and restart retry rejection.

本次源码独审PENDING，完整回归NOT_RUN，包未重建；旧SHA审核和包不继承。
Independent review PENDING, full regression NOT_RUN, package not rebuilt. Previous SHA reviews and archives are not inherited.

发现另一开发线程因额度限制终止；其未跟踪autonomy/original_inventory_owner.py已保留，未提交、修改或当作已接线实现。下一项：恢复该原所有者会话接线，核验原锁/进程身份与服务消费者及预算结算。
The other development thread stopped on a usage limit. Its untracked autonomy/original_inventory_owner.py is preserved without modification, publication or claims of integration. Next: recover that original-owner session integration and verify original lock/process identity with the service consumer and budget settlement.

DEVELOPMENT_COMPLETE=false; RELEASE_READY=false; PRODUCTION_DEPLOYED=false; PRODUCTION_ACCEPTED=false; BUSINESS_GROWTH=UNKNOWN.
allow_install=false; allow_dispatch=false; allow_cancel_dispatch=false; SMTP=false.
未安装服务或触发Inventory，未写生产数据库。复用既有WorkBuddy证据。
No service installed, Inventory triggered or production database written. Existing WorkBuddy evidence reused.
