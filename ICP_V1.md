# ICP V1 — Ideal Customer Profile（理想客户画像）

> 版本：icp_v1 · 建立日期：2026-08-12 · 依据：用户要求 + 数据库只读数据画像
> 状态：V1 初版，随数据累积迭代

---

## 1. 数据事实基础（2026-08-12 只读核实）

- leads 总数 738；TN=177 / AR=67 / KY=66（三州 310）。
- 三州已发送 154（send_log），未发送有邮箱 17，有官网无邮箱 35（可回收）。
- store_type 碎片化严重（~100 种），Top8 = game_store 115 / toy_store 31 / game store 27 / toy store 20 / comic_store 18 / comic_book_store 10 / gift_shop 9 / gift shop 6。
- 全库 email_source_type：official_page_visible 280 / guessed_email 168 / unknown 139。
- 按来源退信率：official_page_visible 1% / guessed_email 10% / web_search 10% / unknown 25%。
- 三州 Route B 型（gift/museum 等）仅 29 条；负面 ICP（大牌/平台）0 条。
- evidence_url / snippet / fit_reason 三州填充率 41% / 20% / 6.5%（缺口大）。

## 2. 三条路线

| Route | 定义 | 核心判断 | 主推价值 |
|-------|------|----------|----------|
| **A: Retail Distributor** | 独立玩具/桌游/拼图/hobby/书店/教育玩具/漫画卡牌店 | 店是否**真正卖** puzzles / board games / family games / toys / gifts / educational | 批发分销（ready-to-stock） |
| **B: Custom / Private Label** | 礼品店/博物馆店/游客中心/旅游礼品店/独立艺术家品牌/特色零售商 | 是否可能有 custom / private label / branded merchandise / printing / packaging / souvenir / local brand 需求 | 定制生产 |
| **U: UNCLASSIFIED** | 无法自动分类 | — | 人工复核 |

**自动判定**：store_type 含 `game|toy|comic|puzzle|hobby|bookstore|board|card|children|educational|novelty|retro|nerd` → A；含 `gift|museum|national park|souvenir|historic|tourist|vintage|general store|visitor center|art|designer|boutique|specialty` → B；双命中归 A（secondary=B）。

## 3. 优先级（与 A0/B2/BroadReady 技术等级**分离**，纯商业优先级）

| Priority | 条件 | 说明 |
|----------|------|------|
| **P1** | email local-part 匹配 `buyer/owner/purchas/wholesale/manager/...` **且** 邮箱域=官网域 | 最直接采购决策人 |
| **P2** | `info@/hello@/contact@/sales@/support@/store@...` 且域=官网域（或该商户自有域其他邮箱） | **主池** |
| **P3** | 官网公开 Gmail/Yahoo/Outlook 免费邮箱，store 高度符合 ICP | 保留，低优先 |
| **UNQUALIFIED** | 不满足以上 | 不入自动候选，进人工/补数据队列 |

> 注意：存量数据中 P1 严格定义仅 1 条（Clobberin Comics `store@clobberincomics.com`）；P2 约 33 条；P3 约 37 条。P1 在当前阶段是"加分项"而非门槛。

## 4. Negative ICP（排除，不作为自动发送优先客户）

- 全国大型连锁：walmart/target/best buy/amazon/etsy/marketplace/costco/kroger/michaels/hobby lobby/gamestop/barnes 等。
- 平台仅存卖家：无法确认独立品牌官网的 marketplace-only / Amazon / Etsy / eBay 卖家。
- 只有第三方目录邮箱、无官方来源证据。
- 只有 Facebook / Yelp / Google Maps、无法确认官网。
- website 失效 / 明显非目标零售 / 与 puzzle·toy·game·gift·custom manufacturing 完全无关。

## 5. 每条 Lead 最少应具备的数据

store_name / city / state / store_type / official_website / email / email_type / **evidence_url** / **evidence_snippet** / email_source_type / organization_key / icp_route / icp_priority / icp_reason / timezone（可解析则解析）。

**evidence_url + evidence_snippet 是硬要求**：必须能说明"为什么相信这个邮箱属于这家商户"。

## 6. 【业务事实】【当前假设】【建议】标注

### 业务事实（DB 已确认）
- official_page_visible 邮箱退信率最低（1%），guessed_email 高 10 倍（10%）→ **优先采用官网可见邮箱**。
- 三州 Route A 型（game/toy/comic）是绝对主体，Route B 型仅 29 条 → **当前主市场是 Route A**。
- 三州有官网无邮箱 35 条是**最优先回收目标**（官网存在但缺可靠联系方式）。
- 8/5 快采（web_search）退信率 60%，与数据画像"web_search 10%、guessed 10%"不一致 → 快采还叠加了邮箱猜测+域名未验证，教训明确。

### 当前假设（未验证）
- P1 采购决策人邮箱的回复率高于 P2/P3（无数据支撑，纯商业常识假设）。
- Route B 客户（博物馆/游客中心）存在定制生产需求且愿意回复。
- 本地/独立店对"定制自有品牌产品"的兴趣高于全国连锁。

### 建议
- **当前阶段优先队列**：① 35 条有官网无邮箱 → 官网扫描回收；② 三州未发送 17 条有邮箱 → 补 evidence 后入池；③ 新发现优先 Route A（game/toy/comic/puzzle/hobby/bookstore），Route B 作为第二lane。
- **证据优先级**：official page 邮箱 > 官网公开 gmail（P3，可测）> guessed_email（低优先）。
- **不依赖 Google Places**：它不可用时走 Web Search / 官网扫描 / 目录 / Facebook recovery。

---

*规则代码实现：`icp_profile.py`（classify_route / classify_priority / is_negative_icp / qualify_lead）*
