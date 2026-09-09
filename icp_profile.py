"""
ICP V1 — Ideal Customer Profile 规则引擎（2026-08-12）
======================================================
P0-2/P0-3 产物。业务定义来自用户要求 + 数据库数据画像（只读核实）。

三条路线：
  Route A: Retail Distributor（零售分销）
  Route B: Custom / Private Label（定制生产）
  Route U: UNCLASSIFIED（无法自动分类 → 需人工复核）

三个优先级（与 A0/B2/BroadReady 技术等级分离，纯商业优先级）：
  P1: buyer/owner/purchasing/wholesale/manager + store-domain 邮箱（最高）
  P2: info@/hello@/contact@/sales@ + store-domain 邮箱（主池）
  P3: 官网公开的免费邮箱（gmail/yahoo/outlook），store 高度符合 ICP
  另: UNQUALIFIED — 不满足以上 → 不入自动候选

Negative ICP（硬排除，不作为自动发送优先客户）：
  - 全国大型连锁（walmart/target/best buy/amazon/etsy/marketplace/costco/kroger/michaels/hobby lobby/gamestop/barnes）
  - 平台仅存卖家（marketplace-only / 无法确认独立品牌官网）
  - 无官方来源证据 / 只有 Facebook/Yelp/Google Maps 无官网
  - website 失效 / 明显非目标零售 / 与 puzzle/toy/game/gift/custom manufacturing 完全无关

本模块不修改 A0/B2/BroadReady 技术定义，只提供商业分类。
"""

import re
from urllib.parse import urlparse

# ─── 版本 ───
ICP_VERSION = "icp_v1"

# ─── Route A 关键词（store_type 命中即 Route A 候选） ───
ROUTE_A_TYPES = [
    "game", "toy", "comic", "puzzle", "hobby", "bookstore", "book store",
    "board", "card", "children", "educational", "novelty", "retro", "nerd",
]

# ─── Route B 关键词（store_type 命中即 Route B 候选） ───
ROUTE_B_TYPES = [
    "gift", "museum", "national park", "souvenir", "historic", "tourist",
    "vintage", "general store", "visitor center", "art", "designer",
    "boutique", "specialty", "botanical", "zoo", "aquarium",
]

# ─── Negative ICP 关键词（store_name / website 命中即排除） ───
NEGATIVE_ICP_NAMES = [
    "walmart", "target", "best buy", "amazon", "etsy", "marketplace",
    "costco", "kroger", "michaels", "hobby lobby", "gamestop", "barnes",
    "sams club", "home depot", "lowe", "meijer", "albertsons", "whole foods",
    "ebay", "wish.com", "temu", "shopify demo", "wix demo",
]
NEGATIVE_ICP_DOMAINS = [
    "amazon.com", "amazon.ca", "etsy.com", "ebay.com", "walmart.com",
    "target.com", "bestbuy.com", "costco.com", "temu.com", "wish.com",
    "tcgplayer.com", "cardmarket.com", "ebaystores",
]

# ─── P1 邮箱 local-part 关键词 ───
P1_EMAIL_PATTERN = re.compile(
    r"^(buyer|owner|purchas|wholesale|manager|salesmanager|buying|vendor|partnership|director)",
    re.IGNORECASE,
)

# ─── P2 邮箱 local-part（generic business email） ───
P2_EMAIL_PATTERN = re.compile(r"^(info|hello|contact|sales|support|general|store|office|shop|mail|business)", re.IGNORECASE)

# ─── 免费邮箱域名 ───
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                      "aol.com", "icloud.com", "live.com", "msn.com", "ymail.com"}


def _domain_of(website: str) -> str:
    if not website:
        return ""
    w = website.strip()
    if not w.startswith("http"):
        w = "https://" + w
    try:
        return urlparse(w).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _email_domain_of(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@")[-1].strip().lower()


def _local_part_of(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@")[0].strip().lower()


def classify_route(store_type: str, store_name: str = "", website: str = "") -> str:
    """返回 'A' / 'B' / 'U'（U = 无法分类）。"""
    st = (store_type or "").lower()
    sn = (store_name or "").lower()

    hit_a = any(k in st for k in ROUTE_A_TYPES)
    hit_b = any(k in st for k in ROUTE_B_TYPES)

    # 双命中（如 toy store / gift shop）→ 归 A，secondary 由调用方记
    if hit_a and hit_b:
        return "A"
    if hit_a:
        return "A"
    if hit_b:
        return "B"

    # store_type 缺失时兜底看名字
    if any(k in sn for k in ["game", "gaming", "games", "gear", "toy", "comic", "puzzle", "hobby",
                             "book", "card", "board", "miniature", "wargame", "rpg", "dungeons",
                             "cards", "collect", "collectible", "nerd", "pawn"]):
        return "A"
    if any(k in sn for k in ["gift", "museum", "souvenir", "boutique", "visitor", "art", "shop"]):
        return "B"
    return "U"


def is_negative_icp(store_name: str = "", website: str = "", email: str = "") -> bool:
    """Negative ICP 判定。命中任一条 → True（应排除）。"""
    sn = (store_name or "").lower()
    domain = _domain_of(website)
    edom = _email_domain_of(email)

    if any(k in sn for k in NEGATIVE_ICP_NAMES):
        return True
    if domain and any(k in domain for k in NEGATIVE_ICP_DOMAINS):
        return True
    if edom and any(k in edom for k in NEGATIVE_ICP_DOMAINS):
        return True
    return False


def classify_priority(route: str, email: str, website: str = "", store_name: str = "") -> str:
    """返回 'P1' / 'P2' / 'P3' / 'UNQUALIFIED'。"""
    if not email or "@" not in email:
        return "UNQUALIFIED"

    edom = _email_domain_of(email)
    site_domain = _domain_of(website)
    local = _local_part_of(email)

    # 免费邮箱 → P3（若 store 本身非 Negative）
    if edom in FREE_EMAIL_DOMAINS:
        return "P3"

    # store-domain 匹配：email 域 == 官网域（或官网域为空时降级，不强制）
    domain_match = bool(site_domain) and (edom == site_domain or edom.endswith("." + site_domain) or site_domain.endswith("." + edom))

    if P1_EMAIL_PATTERN.match(local) and (domain_match or not site_domain):
        return "P1"
    if P2_EMAIL_PATTERN.match(local) and (domain_match or not site_domain):
        return "P2"

    # 其他 store-domain 邮箱（非 generic 前缀）→ P2（属于该商户自己域名，优于免费邮箱）
    if domain_match:
        return "P2"

    return "UNQUALIFIED"


def qualify_lead(lead: dict) -> dict:
    """对单条 lead 做 ICP 分类。lead 需含 store_name/store_type/website/email 等。
    返回 dict：{route, priority, negative, reason, version}。
    """
    store_name = lead.get("store_name") or ""
    store_type = lead.get("store_type") or ""
    website = lead.get("official_website") or lead.get("website") or ""
    email = lead.get("email") or ""
    state = lead.get("state") or ""

    # 区域：优先 TN/AR/KY，非三州仍分类但 reason 注明
    region = "TN/AR/KY" if state.upper() in ("TN", "AR", "KY") else ("OUTSIDE_TARGET" if state else "UNKNOWN_REGION")

    neg = is_negative_icp(store_name, website, email)
    if neg:
        return {
            "route": None, "priority": "NEGATIVE_ICP", "negative": True,
            "reason": f"Negative ICP match (store/domain {store_name} / {website})",
            "region": region, "version": ICP_VERSION,
        }

    route = classify_route(store_type, store_name, website)
    priority = classify_priority(route, email, website, store_name)

    if priority == "UNQUALIFIED" or route == "U":
        reason = f"Route={route}; priority={priority}; cannot auto-classify (store_type={store_type!r}, email={email!r})"
    else:
        reason = f"Route {route} ({store_type or 'untyped'}), Priority {priority}, region {region}"

    return {
        "route": route, "priority": priority, "negative": False,
        "reason": reason, "region": region, "version": ICP_VERSION,
    }
