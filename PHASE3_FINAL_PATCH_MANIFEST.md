# Phase 3 最终补丁清单 / Phase 3 Final Patch Manifest

仅限审查；未部署。 / Review only; not deployed.

DB_MIGRATION_REQUIRED = false
FROZEN_FILES_IN_PATCH = 0

bd_db.py 仅选择性补丁；禁止复制开发保护代码。 / bd_db.py is selective-patch only; development guards are excluded.

```text
PATH = bd_db.py
ACTION = SELECTIVE_PATCH_ONLY
PRODUCTION_BASELINE_SHA256 = 5C18DBD91871EEC3AE742C0730D65294F87E84DB720ADA3C2E86860F96B3ADAB
TARGET_SHA256 = C06FE7EBB3D6330BFCCF078634C5AB6DC16563423E8E975E44DA859AAA7CE0C7
PATCH_SCOPE = Phase 2/3 approved upstream replenishment; existing evidence linkage / 已批准上游补库与已有线索证据关联
```

```text
PATH = bd_orchestrator.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = 3B8DC6355C85476CD0277A1F484A09B94D10F8B89C4D3C82D57C58D389C3FE74
TARGET_SHA256 = 49E38BB1D80832E65F33752D4F7B0E64F5DF41753DC6056B4D1A5A2446ACECDC
PATCH_SCOPE = Phase 2/3 approved upstream replenishment; existing evidence linkage / 已批准上游补库与已有线索证据关联
```

```text
PATH = discovery/discovery_service.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = CC8D9C6B1E4E7C4FD72F43BDF61AD284BBADEC64FABD0FA1139E7F8755EF4627
TARGET_SHA256 = 735D70FE9BD38698024B5587C5CB5E447024B4AE7236FBB6CC3E426C418CCF6F
PATCH_SCOPE = Phase 2/3 approved upstream replenishment; existing evidence linkage / 已批准上游补库与已有线索证据关联
```

```text
PATH = discovery/providers/browser_maps.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = 4530CD188E7ACA2AEE83CEF1CDA1B2324587B68342980B19ADCF5380591744C6
TARGET_SHA256 = 245ED26C92A1624CB8F1BC1754F1DF1EFC887D4343B86BA0CEEF769DC040D31A
PATCH_SCOPE = Phase 2/3 approved upstream replenishment; existing evidence linkage / 已批准上游补库与已有线索证据关联
```

```text
PATH = history_crosscheck.py
ACTION = REPLACE
PRODUCTION_BASELINE_SHA256 = 88FEF144EB4DCF88A318F8256FC1266F0B025350EC0BDC209DA4BF453D52F776
TARGET_SHA256 = 0BA0D0CC25FE3BAA2404B31B8A01070AB02CB6D8CF8588CF3F68F527EFD60631
PATCH_SCOPE = Phase 2/3 approved upstream replenishment; existing evidence linkage / 已批准上游补库与已有线索证据关联
```

```text
PATH = discovery/website_resolver.py
ACTION = ADD
PRODUCTION_BASELINE_SHA256 = MISSING
TARGET_SHA256 = FFBCACDF68992217B6680B19E69713CED045684D2A48F7375DB1E092F667B33F
PATCH_SCOPE = Phase 2/3 approved upstream replenishment; existing evidence linkage / 已批准上游补库与已有线索证据关联
```

## 部署与回滚 / Deployment and rollback

沿用 Phase 3C 手册的备份、维护暂停和回滚流程；制品路径改为 PHASE3_RELEASE_PACKAGE，基线与目标 SHA 使用本清单。 / Reuse the Phase 3C backup, maintenance hold, and rollback procedures with PHASE3_RELEASE_PACKAGE and this manifest’s baseline/target hashes.
现有 schema 足够，无迁移；回滚仅恢复原始代码，不自动清除新证据或恢复发送状态。 / Existing schema is sufficient; no migration. Restore original code for rollback without deleting evidence or resetting delivery state.
