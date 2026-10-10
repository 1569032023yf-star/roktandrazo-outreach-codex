# 获准开发环境的品牌页面采集运行手册
# Authorized Development Capture Runbook

## 目的与范围 / Purpose and scope

本手册只适用于经单独授权、与生产隔离的开发环境。它不授权生产采集、WorkBuddy 调度、数据库访问、SAFE 池变更或邮件发送。执行器仅请求普通公开 HTTPS 页面，禁网策略开启时会在任何请求之前退出。

This runbook is only for a separately authorized development environment isolated from production. It does not authorize production collection, WorkBuddy scheduling, database access, SAFE-pool changes, or email sending. The runner requests ordinary public HTTPS pages only and exits before any request when network policy is disabled.

## 准备来源目录 / Prepare the source catalog

默认目录是可编辑的模板，不代表 URL 已被实时验证。先按来源政策核实可访问的公开类目 URL，并为每个来源准备最多两条 URL 的首轮目录。JSON 格式：

The built-in catalog is an editable template; its URLs are not claimed to have been live-validated. First verify permitted public category URLs for each source and prepare no more than two URLs per source for the initial canary. JSON format:

```json
{
  "schema_version": "1.0",
  "sources": {
    "tiktok_shop": [{"category": "greeting_cards", "url": "https://public.example/category"}],
    "amazon": [{"category": "playing_cards", "url": "https://www.amazon.com/s?k=playing+cards"}],
    "wholesale": [{"category": "paper_goods", "url": "https://public.example/directory"}]
  }
}
```

Each source accepts its own parser (`tiktok_shop`, `amazon`, `wholesale`). Per-source live page attempts remain capped at 3 by the current runner; the initial authorized canary should be limited to 2 per source in the supplied catalog. HTTP workers are capped at 4, browser workers at 1, and candidates at 90.

每个来源只走各自 parser；当前 runner 单来源每轮最多尝试 3 页。首轮授权 canary 应在目录中每来源只放 2 页。HTTP 并发最多 4、浏览器并发 1、候选总量最多 90。

## 命令 / Commands

```powershell
python scripts/run_brand_capture.py --mode capture-public --catalog path\to\authorized_catalog.json
python scripts/run_brand_capture.py --mode validate-manifest --manifest output\brand_acquisition\phase4b1d\captures\capture_manifest.json
python scripts/run_brand_capture.py --mode import-pages --manifest path\to\capture_manifest.json
python scripts/run_brand_capture.py --mode replay --manifest path\to\capture_manifest.json
```

`capture-public` fetches provider pages and, when the existing verifier accepts an explicit official-site candidate, stores those HTTPS pages too. It allows at most one short retry for transient transport/5xx errors; rate limits and access restrictions stop that source. `import-pages`, `replay`, and `validate-manifest` perform no network access. Imports are discovery-only and must be revalidated through the official live verification path before email qualification.

`capture-public` 抓取来源页；既有验证器接受显式官网候选时，也保存对应 HTTPS 官网页面。传输/5xx 临时错误最多短暂重试一次；限流或访问限制会停止该来源。`import-pages`、`replay`、`validate-manifest` 不联网。导入只用于发现，邮箱资格必须经官网实时正式验证。

## 中止条件与验收 / Stop conditions and acceptance

立即停止受限来源：登录页、验证码、403/429、访问挑战、跨域重定向、私网解析或明显非公开页面。不得切换代理/IP/账户、绕过访问控制或更改 sandbox 环境变量。检查报告中的来源标签与 hash；hash 不证明来源真实性或 TLS。

Stop the affected source on login, CAPTCHA, 403/429, access challenge, cross-party redirect, private-address resolution, or clearly non-public pages. Do not rotate proxies/IPs/accounts, bypass access controls, or alter sandbox variables. Inspect provenance labels and hashes in the report; a hash does not establish source authenticity or TLS.

首轮目标是观测，不制造结果：至少一张真实公开页、一个通过独立证据确认的品牌方、一个验证官网、一个官网第一方商务邮箱。任一项不足都报告 pending，并保留失败证据。成功后由负责人决定是否扩大批次；本工具不会创建生产计划，也不会发送邮件。

The first run is observational; never manufacture results. The acceptance target is at least one real public page, one independently confirmed brand owner, one verified official site, and one first-party business email. If any is missing, report pending and preserve the failure evidence. An owner may authorize a larger batch after success. This tool creates no production plan and sends no email.

输出默认保存在 `output/brand_acquisition/phase4b1d/`，该目录属于本地开发产物，不应提交真实客户数据、cookie、凭据或浏览器会话。

Default outputs are under `output/brand_acquisition/phase4b1d/`. These are local development artifacts; never commit real customer data, cookies, credentials, or browser sessions.
