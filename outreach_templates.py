"""Outreach Template Routing v3 — deterministic template selection.

Two templates:
  1. hybrid_wholesale_custom_v1 — DEFAULT for retail, distributor, uncertain
  2. custom_production_v1 — ONLY for own-brand, institution custom needs

Key fixes v3:
  - "Made in China" alone does NOT exclude (product origin ≠ seller country)
  - Structured field checks (country, country_verification, source_platform)
  - cn_seller and competitor_printer separately classified
  - Platform recognition via source_platform AND URL patterns
  - customer_type matches template correctly (online_brand → custom, not retail_store → custom)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# ============================================================
# Templates
# ============================================================

TEMPLATES = {
    "hybrid_wholesale_custom_v1": {
        "id": "hybrid_wholesale_custom_v1",
        "type": "hybrid",
        "subject_template": "Premium puzzles & card games for {store_name} (Low MOQ / DDP)",
        "body_template": (
            "Hi {store_name} team,\n\n"
            "I'm Ian from rokt&razo. We are a puzzle and family card game brand with 10+ years "
            "of experience in product development, manufacturing, and custom production. "
            "In addition to our own branded products, we also support many U.S. brands and "
            "independent artists with custom production.\n\n"
            "We are currently expanding our U.S. retail and distributor network, and I wanted "
            "to see if there may be an opportunity to work together. We offer:\n\n"
            "- Low MOQs and DDP pricing for rokt&razo branded products\n"
            "- Premium jigsaw puzzles and family card games\n"
            "- Custom and private-label production options\n"
            "- Supply chain support to help improve cost, quality, and production efficiency\n\n"
            "If you're interested, I'd be happy to send over our latest catalogue, including "
            "our unique 24-in-1 puzzle series, which has received very positive customer feedback.\n\n"
            "If you also have your own branded products, we'd be happy to discuss custom "
            "production opportunities as well.\n\n"
            "Best regards,\nIan\nBusiness Development Specialist\nrokt&razo"
        ),
    },
    "custom_production_v1": {
        "id": "custom_production_v1",
        "type": "custom",
        "subject_template": "Custom Production & Procurement Support for {store_name}",
        "body_template": (
            "Hi {store_name} team,\n\n"
            "I'm Ian from rokt&razo. We are a custom printing and production partner with "
            "10+ years of experience in the industry. We've supported many U.S. brands and "
            "independent artists with custom printed products, from small-batch samples to "
            "full production.\n\n"
            "{custom_intro}\n\n"
            "We offer:\n\n"
            "- Custom printing for playing cards, puzzles, boxes, and packaging\n"
            "- Flexible MOQ and door-to-door pricing\n"
            "- Cost reduction and quality improvement for existing products\n"
            "- OEM and private-label manufacturing\n"
            "- Professional project support, quality control, and hassle-free service\n\n"
            "If you're interested, we'd be happy to discuss your needs and see how we can "
            "support your business. We hope to become a long-term production partner that "
            "supports your continued growth.\n\n"
            "Best regards,\nIan\nBusiness Development Specialist\nrokt&razo"
        ),
    },
}

INSTITUTION_INTRO = (
    "I noticed your organization offers distinctive gifts and merchandise "
    "connected to your location, community, or mission."
)
BRAND_INTRO = (
    "I noticed you have your own product line, so I wanted to reach out to see if "
    "we could help improve your procurement efficiency, production cost, or product quality."
)


# ============================================================
# Signals
# ============================================================

# Strong custom-production signals (own-brand, self-designed)
CUSTOM_SIGNALS = [
    (re.compile(r"own\s*(product|brand|line|design)", re.I), 0.8),
    (re.compile(r"private\s*label", re.I), 0.9),
    (re.compile(r"original\s*(design|product|artwork|game)", re.I), 0.7),
    (re.compile(r"branded\s*(product|merchandise|goods|gift)", re.I), 0.7),
    (re.compile(r"custom\s*(merchandise|product|design|print|production)", re.I), 0.7),
    (re.compile(r"wholesale\s*manufactur", re.I), 0.8),
    (re.compile(r"crowdfunding|crowd\s*funding", re.I), 0.9),
    (re.compile(r"design(?:ed)?\s*(?:our|own|in.house|original)", re.I), 0.8),
]

# Platform URL patterns
PLATFORM_URLS = {
    "Amazon": [
        re.compile(r"amazon\.com/stores/", re.I),
        re.compile(r"amazon\.com/shop/", re.I),
        re.compile(r"amazon\.com/brands/", re.I),
        re.compile(r"amazon\.com/.*seller", re.I),
        re.compile(r"sellercentral\.amazon", re.I),
        re.compile(r"amazon\.com/[^/]+/dp/", re.I),
    ],
    "Etsy": [
        re.compile(r"etsy\.com/shop/", re.I),
        re.compile(r"etsy\.com/.*listing", re.I),
    ],
    "TikTok Shop": [
        re.compile(r"shop\.tiktok\.com", re.I),
        re.compile(r"tiktok\.com/@", re.I),
    ],
    "Kickstarter": [re.compile(r"kickstarter\.com/project", re.I)],
    "Gamefound": [re.compile(r"gamefound\.com", re.I)],
    "BackerKit": [re.compile(r"backerkit\.com", re.I)],
    "Indiegogo": [re.compile(r"indiegogo\.com", re.I)],
    "Shopify": [re.compile(r"myshopify\.com", re.I)],
}

# Institution keywords
INSTITUTION_KEYWORDS = {
    "museum": ["museum"],
    "national_park_or_visitor_center": ["national park", "visitor center"],
    "tourism_or_destination_shop": ["tourism bureau"],
    "school_or_university_store": ["school store", "university store", "college store", "campus store"],
    "zoo_or_aquarium": ["zoo", "aquarium"],
    "botanical_garden": ["botanical garden"],
    "cultural_center": ["cultural center"],
    "historic_site": ["historic site"],
    "postal_or_postcard_business": ["postal museum", "postcard"],
}

INSTITUTION_STORE_TYPES = frozenset({
    "school_store", "university_store", "museum_store", "visitor_center",
    "national_park_store", "zoo_store", "aquarium_store", "botanical_garden",
    "cultural_center", "historic_site", "tourism_bureau", "postal_museum",
    "postcard_business", "foundation_store",
})

# Exclusion: confirmed Chinese sellers (NOT product origin)
CN_SELLER_SIGNALS = [
    # Structured field (most reliable)
    ("cn_entity_excluded", 1.0),
    # Official address
    (re.compile(r"guangzhou|shenzhen|yiwu|fujian|zhejiang|dongguan|shanghai|beijing", re.I), 0.6),
    # Platform entity
    (re.compile(r"aliexpress|alibaba\.com|1688", re.I), 0.9),
    # Company info
    (re.compile(r"company\s*(?:registered|located|based)\s*in\s*.*?(?:china|cn)", re.I), 0.9),
    (re.compile(r"headquarters?:?\s*(?:guangzhou|shenzhen|shanghai|beijing|dongguan|yiwu)", re.I), 0.8),
]

# Exclusion: competing print factories
COMPETITOR_SIGNALS = [
    (re.compile(r"printing\s*(?:factory|company|service|plant)", re.I), 0.8),
    (re.compile(r"custom\s*(?:print|box|packaging)\s*(?:manufactur|factor)", re.I), 0.8),
    (re.compile(r"印刷|打印|代工|生产厂家", re.U), 0.9),
]


# ============================================================
# Helpers
# ============================================================

def _detect_platform(lead: dict) -> str:
    """Detect source platform from structured field or URL."""
    # Structured field first
    sp = (lead.get("source_platform") or "").strip()
    if sp:
        sp_lower = sp.lower()
        for name in PLATFORM_URLS:
            if name.lower() in sp_lower:
                return name
    # URL detection
    website = (lead.get("official_website") or "").lower()
    if website:
        for name, patterns in PLATFORM_URLS.items():
            for pat in patterns:
                if pat.search(website):
                    return name
    return ""


def _detect_customer_type(lead: dict, platform: str, is_institution: bool,
                          inst_type: str = "") -> str:
    """Determine customer_type based on structured fields and signals."""
    store_type = (lead.get("store_type") or "").lower()
    source_platform = (lead.get("source_platform") or "").lower()
    evidence = (lead.get("evidence_snippet") or "").lower()
    product_fit = (lead.get("product_fit") or "").lower()
    combined = f"{store_type} {source_platform} {evidence} {product_fit}"

    # Institution types
    if is_institution and inst_type:
        return inst_type
    if store_type in INSTITUTION_STORE_TYPES:
        return store_type

    # Direct store_type matches
    if store_type in ("online_brand", "independent_creator"):
        return store_type
    if store_type == "crowdfunding":
        return "crowdfunding_project"
    if store_type == "distributor":
        return "distributor"
    if store_type in ("printer", "manufacturer", "factory"):
        return "competitor_printer"

    # Platform-based types
    platform_lower = platform.lower()
    if any(k in platform_lower for k in ["kickstarter", "gamefound", "backerkit", "indiegogo"]):
        return "crowdfunding_project"
    if any(k in platform_lower for k in ["amazon", "etsy", "tiktok"]):
        return "online_brand"
    # Shopify alone → keep as retail_store (not automatically online_brand)

    # Text-based
    for kw in ["distributor", "wholesale"]:
        if kw in combined:
            return "distributor"
    for kw in ["creator", "artist", "designer", "independent"]:
        if kw in combined:
            return "independent_creator"
    for kw in ["museum", "zoo", "aquarium", "garden", "park", "visitor"]:
        if kw in combined:
            return "museum_or_cultural_institution"
    for kw in ["school", "universit", "college", "campus"]:
        if kw in combined:
            return "school_or_university_store"
    for kw in ["postal", "postcard"]:
        if kw in combined:
            return "postal_or_postcard_business"

    return "retail_store"


# ============================================================
# Route function
# ============================================================

@dataclass
class RouteResult:
    customer_type: str
    template_id: str
    routing_reason: str
    routing_confidence: float
    custom_intro: str = ""
    excluded: bool = False
    exclude_reason: str = ""


def route_outreach_template(lead: dict) -> RouteResult:
    """Route lead to correct template. Returns RouteResult."""
    store_name = lead.get("store_name", "")
    store_type = (lead.get("store_type") or "").lower()
    website = (lead.get("official_website") or "").lower()
    evidence = (lead.get("evidence_snippet") or "").lower()
    notes = (lead.get("notes") or "").lower()
    product_fit = (lead.get("product_fit") or "").lower()
    country_verification = (lead.get("country_verification") or "").lower()
    country = (lead.get("country") or "").lower()
    business_entity_country = (lead.get("business_entity_country") or "").lower()
    source_platform_field = (lead.get("source_platform") or "").lower()
    seller_entity_type = (lead.get("seller_entity_type") or "").lower()

    combined_text = f"{store_name} {website} {evidence} {notes} {product_fit}".lower()

    # ——— Step 0: Structured field CN exclusion ———
    # cn_entity_excluded → confirmed Chinese seller
    if country_verification == "cn_entity_excluded":
        return RouteResult(
            customer_type="cn_seller",
            template_id="",
            routing_reason="Country verification = cn_entity_excluded — confirmed Chinese seller",
            routing_confidence=1.0,
            excluded=True,
            exclude_reason="cn_entity_excluded",
        )

    # Business entity country = CN
    if business_entity_country in ("cn", "china"):
        return RouteResult(
            customer_type="cn_seller",
            template_id="",
            routing_reason=f"Business entity country = {business_entity_country}",
            routing_confidence=0.9,
            excluded=True,
            exclude_reason="cn_business_entity",
        )

    # seller_entity_type = cn_seller
    if seller_entity_type == "cn_seller":
        return RouteResult(
            customer_type="cn_seller",
            template_id="",
            routing_reason="seller_entity_type = cn_seller",
            routing_confidence=0.9,
            excluded=True,
            exclude_reason="cn_seller_entity",
        )

    # ——— Step 1: Platform detection ———
    platform = _detect_platform(lead)

    # ——— Step 2: CN seller text signals (company address, platform entity) ———
    cn_signal_score = 0.0
    cn_signal_detail = ""
    # Check structured source_platform field for AliExpress/Alibaba
    if any(k in source_platform_field for k in ["aliexpress", "alibaba", "1688"]):
        cn_signal_score = 0.9
        cn_signal_detail = f"source_platform = {source_platform_field}"

    for item in CN_SELLER_SIGNALS:
        if isinstance(item, tuple) and len(item) == 2:
            if isinstance(item[0], re.Pattern):
                if item[0].search(combined_text) or item[0].search(evidence) or item[0].search(notes):
                    cn_signal_score += item[1]
                    cn_signal_detail = item[0].pattern[:40]

    if cn_signal_score >= 1.0:
        return RouteResult(
            customer_type="cn_seller",
            template_id="",
            routing_reason=f"CN seller signals ({cn_signal_detail}): score={cn_signal_score:.1f}",
            routing_confidence=min(1.0, cn_signal_score),
            excluded=True,
            exclude_reason=f"cn_seller: {cn_signal_detail}",
        )

    # ——— Step 3: Competitor printer ———
    comp_score = 0.0
    comp_detail = ""
    for pat, weight in COMPETITOR_SIGNALS:
        if pat.search(combined_text):
            comp_score += weight
            comp_detail = pat.pattern[:40]

    if comp_score >= 0.7:
        return RouteResult(
            customer_type="competitor_printer",
            template_id="",
            routing_reason=f"Competitor printer signals ({comp_detail}): score={comp_score:.1f}",
            routing_confidence=min(1.0, comp_score),
            excluded=True,
            exclude_reason=f"competitor_printer: {comp_detail}",
        )

    # ——— Step 4: Institution detection ———
    is_institution = False
    inst_type = "museum_or_cultural_institution"

    # Check store_type first
    if store_type in INSTITUTION_STORE_TYPES:
        is_institution = True
        inst_type = store_type
    else:
        # Check keyword matches
        for itype_name, keywords in INSTITUTION_KEYWORDS.items():
            for kw in keywords:
                if kw in combined_text:
                    is_institution = True
                    inst_type = itype_name
                    break
            if is_institution:
                break

    # ——— Step 5: Custom signal accumulation ———
    custom_score = 0.0
    custom_signals_found = []
    for pat, weight in CUSTOM_SIGNALS:
        if pat.search(combined_text):
            custom_score += weight
            custom_signals_found.append(pat.pattern[:40])

    # Add platform signal weight
    if platform in ("Amazon", "Etsy", "TikTok Shop"):
        custom_score += 0.5
        custom_signals_found.append(f"platform:{platform}")
    if platform in ("Kickstarter", "Gamefound", "BackerKit", "Indiegogo"):
        custom_score += 1.0
        custom_signals_found.append(f"platform:{platform}")

    # ——— Step 6: Multi-brand context check ———
    multi_brand = any(kw in combined_text for kw in [
        "multi brand", "multi-brand", "also sell", "also carry",
        "also stocks", "sell brands", "carry brands", "variety of", "assortment",
    ])

    # ——— Step 7: Routing decision ———

    # Crowdfunding → custom
    if platform in ("Kickstarter", "Gamefound", "BackerKit", "Indiegogo"):
        ctype = _detect_customer_type(lead, platform, is_institution, inst_type)
        return RouteResult(
            customer_type=ctype,
            template_id="custom_production_v1",
            routing_reason=f"Crowdfunding platform ({platform}) — original product",
            routing_confidence=0.9,
            custom_intro=BRAND_INTRO,
        )

    # Online brand platform (Amazon/Etsy/TikTok Shop) → custom
    if platform in ("Amazon", "Etsy", "TikTok Shop") and custom_score >= 0.5:
        ctype = _detect_customer_type(lead, platform, is_institution, inst_type)
        return RouteResult(
            customer_type=ctype,
            template_id="custom_production_v1",
            routing_reason=f"Online brand ({platform}) with custom signals: {custom_signals_found}",
            routing_confidence=min(0.9, custom_score),
            custom_intro=BRAND_INTRO,
        )

    # Institution with custom signals → custom
    if is_institution and custom_score >= 0.5:
        return RouteResult(
            customer_type=inst_type,
            template_id="custom_production_v1",
            routing_reason=f"Institution ({inst_type}) with custom signals: {custom_signals_found}",
            routing_confidence=min(0.9, custom_score),
            custom_intro=INSTITUTION_INTRO,
        )

    # Institution (any) → custom
    if is_institution:
        return RouteResult(
            customer_type=inst_type,
            template_id="custom_production_v1",
            routing_reason=f"Institution ({inst_type}) — likely has themed gift products",
            routing_confidence=0.5,
            custom_intro=INSTITUTION_INTRO,
        )

    # Own brand (strong signal, NOT multi-brand) → custom
    if custom_score >= 1.0 and not multi_brand:
        ctype = _detect_customer_type(lead, platform, is_institution, inst_type)
        return RouteResult(
            customer_type=ctype,
            template_id="custom_production_v1",
            routing_reason=f"Strong own-brand signals: {custom_signals_found}",
            routing_confidence=min(1.0, custom_score / 2),
            custom_intro=BRAND_INTRO,
        )

    # Own brand but multi-brand context → hybrid
    if custom_score >= 0.7 and multi_brand:
        return RouteResult(
            customer_type="retail_store",
            template_id="hybrid_wholesale_custom_v1",
            routing_reason="Retail store with own brand AND other brands — hybrid",
            routing_confidence=0.75,
        )

    # Distributor → hybrid
    ctype = _detect_customer_type(lead, platform, is_institution, inst_type)
    if ctype == "distributor":
        return RouteResult(
            customer_type="distributor",
            template_id="hybrid_wholesale_custom_v1",
            routing_reason="Distributor — wholesale + custom potential",
            routing_confidence=0.8,
        )

    # Default → hybrid
    return RouteResult(
        customer_type=ctype,
        template_id="hybrid_wholesale_custom_v1",
        routing_reason="Default hybrid: retail or uncertain",
        routing_confidence=0.7,
    )


def render_email(lead: dict) -> dict:
    route = route_outreach_template(lead)
    if route.excluded:
        return {"error": "excluded", "reason": route.exclude_reason}
    tmpl = TEMPLATES[route.template_id]
    store_name = lead.get("store_name", "your store")
    subject = tmpl["subject_template"].replace("{store_name}", store_name)
    body = tmpl["body_template"].replace("{store_name}", store_name)
    if "{custom_intro}" in body and route.custom_intro:
        body = body.replace("{custom_intro}", route.custom_intro)
    return {
        "subject": subject, "body_text": body,
        "template_id": route.template_id, "customer_type": route.customer_type,
        "routing_reason": route.routing_reason, "routing_confidence": route.routing_confidence,
    }


# ============================================================
# Tests
# ============================================================

def run_tests():
    tests = [
        # 1-5: Legacy tests (hybrid)
        ("1. Toy store → hybrid",
         {"store_name": "Happy Toys", "store_type": "toy_store", "official_website": "https://happytoys.com"},
         "hybrid_wholesale_custom_v1", "retail_store", False),
        ("2. Board game store → hybrid",
         {"store_name": "Dice & Decks", "store_type": "game_store"},
         "hybrid_wholesale_custom_v1", "retail_store", False),
        ("3. Gift shop → hybrid",
         {"store_name": "Little Gift", "store_type": "gift_shop", "evidence_snippet": "gifts and souvenirs"},
         "hybrid_wholesale_custom_v1", "retail_store", False),
        ("4. Multi-brand retail → hybrid",
         {"store_name": "Brand Central", "store_type": "toy_store", "product_fit": "sell brands own branded products"},
         "hybrid_wholesale_custom_v1", "retail_store", False),
        ("5. Unknown → hybrid",
         {"store_name": "Mystery", "store_type": ""},
         "hybrid_wholesale_custom_v1", "retail_store", False),
        # 6-8: Online brand / crowd
        ("6. Amazon own brand → custom",
         {"store_name": "CardMasters", "source_platform": "Amazon", "official_website": "https://amazon.com/stores/cardmasters",
          "product_fit": "own brand playing cards"},
         "custom_production_v1", "online_brand", False),
        ("7. Etsy own puzzle → custom",
         {"store_name": "PuzzleArt", "source_platform": "Etsy", "official_website": "https://etsy.com/shop/puzzleart",
          "product_fit": "custom puzzle original design"},
         "custom_production_v1", "online_brand", False),
        ("8. Kickstarter → custom",
         {"store_name": "GameQuest", "store_type": "crowdfunding",
          "official_website": "https://kickstarter.com/projects/gamequest", "product_fit": "original card game"},
         "custom_production_v1", "crowdfunding_project", False),
        # 9-10: Institutions
        ("9. Museum shop → custom",
         {"store_name": "Art Museum Store", "store_type": "museum_store",
          "evidence_snippet": "custom merchandise branded gifts"},
         "custom_production_v1", "museum_store", False),
        ("10. National park → custom",
         {"store_name": "Yellowstone Shop", "store_type": "visitor_center",
          "evidence_snippet": "national park souvenirs"},
         "custom_production_v1", "visitor_center", False),
        ("11. University store → custom",
         {"store_name": "Campus Bookstore", "store_type": "school_store",
          "product_fit": "school branded merchandise"},
         "custom_production_v1", "school_store", False),
        # 12: CN exclude
        ("12. country_verification=cn_entity → reject",
         {"store_name": "Shenzhen Trading", "country_verification": "cn_entity_excluded"},
         "", "cn_seller", True),
        # 13-20: NEW tests
        ("13. US brand, Made in China → keep",
         {"store_name": "American Puzzle Co", "store_type": "online_brand", "official_website": "https://ampuzzle.com",
          "evidence_snippet": "proudly designed in USA, made in China"},
         "hybrid_wholesale_custom_v1", "online_brand", False),
        ("14. CN company address → reject",
         {"store_name": "EnglishBrand", "evidence_snippet": "company registered in Shenzhen, China"},
         "", "cn_seller", True),
        ("15. Amazon /stores/ own brand → custom",
         {"store_name": "ToyBrands", "source_platform": "Amazon", "store_type": "online_brand",
          "official_website": "https://amazon.com/stores/toybrands", "product_fit": "own branded toys"},
         "custom_production_v1", "online_brand", False),
        ("16. TikTok Shop own brand → custom",
         {"store_name": "PuzzleFun", "source_platform": "TikTok Shop", "store_type": "online_brand",
          "official_website": "https://shop.tiktok.com", "product_fit": "own puzzle brand"},
         "custom_production_v1", "online_brand", False),
        ("17. Kickstarter URL no store_type → custom",
         {"store_name": "NewGame", "official_website": "https://kickstarter.com/projects/newgame",
          "evidence_snippet": "original board game project"},
         "custom_production_v1", "crowdfunding_project", False),
        ("18. Shopify multi-brand → hybrid",
         {"store_name": "ToyGalaxy", "official_website": "https://toygalaxy.myshopify.com",
          "product_fit": "variety of toys games puzzles sell brands"},
         "hybrid_wholesale_custom_v1", "retail_store", False),
        ("19. China printer → competitor",
         {"store_name": "PrintFast", "evidence_snippet": "custom printing factory packaging manufacturer"},
         "", "competitor_printer", True),
        ("20. Alibaba source → cn_seller",
         {"store_name": "Global Toys", "source_platform": "alibaba.com", "official_website": "https://alibaba.com"},
         "", "cn_seller", True),
    ]

    passed = 0
    for name, lead, expected_template, expected_type, expected_excluded in tests:
        result = route_outreach_template(lead)
        ok = (
            result.template_id == expected_template
            and expected_type in result.customer_type
            and result.excluded == expected_excluded
        )
        mark = "✓" if ok else "✗"
        print(f"  {mark} {name}")
        print(f"       → template={result.template_id} type={result.customer_type} excluded={result.excluded} conf={result.routing_confidence:.1f}")
        if not ok:
            print(f"       EXPECTED: template={expected_template} type={expected_type} excluded={expected_excluded}")
            print(f"       REASON: {result.routing_reason}")
        if ok:
            passed += 1

    print(f"\n  {passed}/{len(tests)} passed")
    return passed


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        run_tests()
    else:
        print("Template routing v3 loaded.")
        run_tests()
