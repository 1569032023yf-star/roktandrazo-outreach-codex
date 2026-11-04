# 初始失败记录 / Initial failure record

中文：工作树尚未提交时，打包清单测试拒绝BUILD_INPUT_NOT_PINNED；随后已固定ec45401源码再验证。
English: Before source commit, the package source test rejected BUILD_INPUT_NOT_PINNED. Source was then pinned at ec45401 before revalidation.

中文：一次15项组合中，test_delivery_documents因test_regression_harness_safety导入的全局开发护栏拒绝git rev-parse HEAD，错误DEVELOPMENT_SUBPROCESS_BLOCKED。没有卸载护栏；按进程隔离职责分别运行14项配置/隔离测试及1项固定Git清单测试，分别通过。该拆分不证明同进程组合通过。
English: In one15-test combination, test_delivery_documents hit DEVELOPMENT_SUBPROCESS_BLOCKED for git rev-parse HEAD after test_regression_harness_safety installed process-global guards during discovery. Guards were retained. The14 configuration/isolation checks and1 fixed-Git manifest check passed in separate processes; this does not claim the combined same-process suite passed.
