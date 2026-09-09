# Browser Maps Discovery — 快速启动指南

## Nashville 单关键词采集实验

### 前置条件

```powershell
# 检查 Playwright 是否已安装
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

# 如未安装:
pip install playwright
playwright install chromium
```

### Step 1: 运行 Google Maps 采集器

```powershell
cd C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach

python discovery/providers/browser_maps_scraper.py `
    --query "board game store Nashville TN" `
    --city Nashville --state TN `
    --max-results 20 `
    --output data/browser_maps_nashville_boardgame.json
```

**如果你想看到浏览器窗口（调试用）**:
```powershell
python discovery/providers/browser_maps_scraper.py `
    --query "board game store Nashville TN" `
    --city Nashville --state TN `
    --max-results 20 `
    --no-headless `
    --output data/browser_maps_nashville_boardgame.json
```

### Step 2: 验证结果文件

采集完成后检查 JSON:
```powershell
python -c "
import json
with open('data/browser_maps_nashville_boardgame.json') as f:
    data = json.load(f)
print(f'Status: {data[\"status\"]}')
print(f'Results: {len(data[\"results\"])}')
for r in data['results'][:5]:
    print(f'  {r[\"business_name\"]} | {r.get(\"website\",\"no website\")} | {r.get(\"phone\",\"no phone\")}')
"
```

### Step 3: 运行集成测试

```powershell
# 使用 JSON 结果文件
python test_browser_maps_integration.py `
    --json-file data/browser_maps_nashville_boardgame.json `
    --city Nashville --state TN

# 或者直接抓取（需要 Playwright）
python test_browser_maps_integration.py `
    --scrape-now `
    --city Nashville --state TN `
    --query "board game store Nashville TN" `
    --max-results 20
```

### Step 4: 查看测试结果

测试会输出:
- 去重统计
- 每家公司的分类结果
- 测试数据库中的新 lead 数
- 详细 JSON 报告在 `output/` 目录

---

## 接入现有 Discovery Pipeline

### 配置 Provider

```powershell
# 设置环境变量使用 browser_maps provider
$env:DISCOVERY_PROVIDER = "browser_maps"

# 指定 JSON 文件路径
$env:BROWSER_MAPS_JSON_FILE = "data/browser_maps_nashville_boardgame.json"

# 或者使用缓存目录
$env:BROWSER_MAPS_CACHE_DIR = "data/browser_maps_cache"

# 运行 discovery
python -c "
from discovery.providers.base import load_provider
from retail_city_queue import search_queries

# Get first query family for Nashville
queries = search_queries({'city': 'Nashville', 'state': 'TN'})
first_query = queries[0]

provider = load_provider('browser_maps')
page = provider.search_places(first_query, 'Nashville', 'TN', '', 20)
print(f'Status: {page.status}, Results: {len(page.results)}')
for r in page.results[:5]:
    print(f'  {r.business_name} — {r.website}')
"
```

---

## 验收清单

完成以下步骤后填写:

### 浏览器能力验证

| # | 问题 | 结果 |
|---|------|------|
| 1 | WorkBuddy 能否打开浏览器？ | _________ |
| 2 | 能否访问 Google Maps？ | _________ |
| 3 | 搜索 "board game store Nashville TN" 是否成功？ | _________ |
| 4 | 能否读取左侧商家列表？ | _________ |
| 5 | 是否出现验证码/风控？ | _________ |
| 6 | 使用的浏览器技术路径？ | Playwright Chromium headless=True |

### 采集结果

| 指标 | 数量 |
|------|------|
| 实际采集到 | _________ |
| 去重后 | _________ |
| 有官网 | _________ |
| 有电话 | _________ |
| 进入 A0 | _________ |
| Manual Review | _________ |
| Contact Form | _________ |
| 历史已发/重复 | _________ |

### 代码交付

| 文件 | 状态 |
|------|------|
| `discovery/providers/browser_maps_scraper.py` | ✅ 已创建（Playwright Google Maps 采集器） |
| `discovery/providers/browser_maps.py` | ✅ 已创建（SearchProvider 兼容接口） |
| `discovery/providers/base.py` | ✅ 已更新（注册 browser_maps provider） |
| `test_browser_maps_integration.py` | ✅ 已创建（端到端集成测试） |
| 生产数据库修��� | ❌ 未修改 |
| 发送池修改 | ❌ 未触碰 |
