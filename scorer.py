"""
Roktandrazo Outreach - Lead Scorer
AI 判断引擎：根据门店类型匹配度、邮箱质量、官网质量自动打分
"""

from config import STORE_TYPE_PRIORITY, MIN_SCORE_TO_EMAIL, AUTO_EMAIL_GRADES


def score_lead(lead: dict) -> dict:
    """
    对线索进行评分，返回评分结果和理由
    
    评分维度:
    1. 门店类型匹配度 (0-40分)
    2. 联系方式质量 (0-30分)
    3. 官网质量 (0-20分)
    4. 地理位置价值 (0-10分)
    
    总分 100:
    - A: 70+ (官网邮箱明确 + 门店类型高度匹配 + 有实体地址)
    - B: 50-69 (有官网/contact form + 类型匹配)
    - C: <50 (只有社媒或信息不完整)
    """
    scores = {
        "type_match": 0,
        "contact_quality": 0,
        "website_quality": 0,
        "location_value": 0,
    }
    reasons = []

    # ==========================================
    # 1. 门店类型匹配度 (0-40)
    # ==========================================
    store_type = (lead.get("store_type") or "").lower()
    type_score = 0

    for stype, priority in STORE_TYPE_PRIORITY.items():
        if stype in store_type:
            if priority == 1:
                type_score = 40  # 完美匹配
            elif priority == 2:
                type_score = 30  # 良好匹配
            else:
                type_score = 20  # 一般匹配
            reasons.append(f"门店类型 '{store_type}' 匹配度优先级 {priority}")
            break

    # 额外加分：拼图相关
    puzzle_keywords = ["puzzle", "jigsaw", "brainteaser", "brain teaser", "game"]
    fit_reason = (lead.get("fit_reason") or "").lower()
    store_name = (lead.get("store_name") or "").lower()
    for kw in puzzle_keywords:
        if kw in store_name or kw in fit_reason:
            type_score = min(type_score + 5, 40)
            reasons.append(f"名称/描述含拼图关键词 '{kw}'")
            break

    scores["type_match"] = type_score

    # ==========================================
    # 2. 联系方式质量 (0-30)
    # ==========================================
    email = lead.get("email", "")
    email_type = lead.get("email_type", "")
    contact_form = lead.get("contact_form_url", "")

    contact_score = 0
    if email and email.strip():
        contact_score = 30  # 有明确邮箱
        reasons.append(f"有明确商务邮箱: {email}")

        # 检查是否是通用邮箱 (info@, help@, contact@ 等)
        generic_prefixes = ["info@", "help@", "contact@", "hello@", "hi@", "store@", "shop@"]
        if any(email.lower().startswith(p) for p in generic_prefixes):
            contact_score = 28  # 通用邮箱略低
            reasons.append("通用邮箱前缀 (info/help/contact)")
        
        # 检查是否是 Gmail/Yahoo (可能是小门店)
        free_domains = ["gmail.com", "yahoo.com", "hotmail.com", "aol.com"]
        if any(email.lower().endswith(d) for d in free_domains):
            contact_score = 25  # 免费邮箱
            reasons.append("免费邮箱域名 (gmail/yahoo)")

    elif contact_form and contact_form.strip():
        contact_score = 15  # 只有联系表单
        reasons.append("仅有联系表单，无直接邮箱")
    else:
        contact_score = 0
        reasons.append("无可用的联系方式")

    scores["contact_quality"] = contact_score

    # ==========================================
    # 3. 官网质量 (0-20)
    # ==========================================
    website = lead.get("official_website", "")
    evidence = lead.get("evidence_url", "")

    web_score = 0
    if website and website.strip():
        web_score = 10  # 有官网
        reasons.append("有官方网站")

        if evidence and evidence.strip() and evidence != website:
            web_score += 5  # 有证据链接
            reasons.append("有证据链接")

        # 检查官网是否有专门的 contact/wholesale 页面
        contact_page = lead.get("contact_page", "")
        if contact_page and contact_page.strip():
            web_score += 5
            reasons.append("有专门的联系/wholesale页面")
    else:
        reasons.append("无官方网站")

    scores["website_quality"] = min(web_score, 20)

    # ==========================================
    # 4. 地理位置价值 (0-10)
    # ==========================================
    city = (lead.get("city") or "").lower()
    state = (lead.get("state") or "").lower()

    # 旅游城市加分
    tourist_cities = [
        "asheville", "bar harbor", "sedona", "carmel-by-the-sea", "taos",
        "eureka springs", "savannah", "charleston", "stowe", "woodstock",
        "park city", "bend", "traverse city", "lake geneva", "portsmouth",
        "key west", "santa fe", "jackson hole", "nashville", "austin",
        "portland", "boulder", "portland", "cape cod", "williamsburg",
        "san antonio", "new orleans", "savanah", "miami beach",
        "sausalito", "monterey", "santa barbara", "camel"
    ]
    
    loc_score = 5  # 基础分
    if any(tc in city for tc in tourist_cities):
        loc_score = 10
        reasons.append(f"旅游城市: {lead.get('city')}, {lead.get('state')}")
    else:
        reasons.append(f"非核心旅游城市: {lead.get('city')}, {lead.get('state')}")

    scores["location_value"] = loc_score

    # ==========================================
    # 计算总分和等级
    # ==========================================
    total = sum(scores.values())
    
    if total >= 70:
        grade = "A"
    elif total >= 50:
        grade = "B"
    else:
        grade = "C"

    return {
        "grade": grade,
        "total_score": total,
        "scores": scores,
        "reasons": reasons,
        "should_email": grade in AUTO_EMAIL_GRADES or (grade >= MIN_SCORE_TO_EMAIL),
        "auto_send": grade in AUTO_EMAIL_GRADES,
    }


def batch_score(leads: list[dict]) -> list[dict]:
    """批量评分，给每条线索添加评分结果"""
    for lead in leads:
        result = score_lead(lead)
        lead["confidence_score"] = result["grade"]
        lead["scoring_detail"] = result
    return leads


if __name__ == "__main__":
    # 测试评分
    test_leads = [
        {
            "store_name": "Liberty Puzzles",
            "store_type": "puzzle manufacturer/retail",
            "city": "Boulder",
            "state": "CO",
            "email": "help@libertypuzzles.com",
            "email_type": "business_email",
            "official_website": "https://libertypuzzles.com",
            "contact_page": "https://libertypuzzles.com/policies/contact-information",
            "evidence_url": "https://libertypuzzles.com",
            "fit_reason": "Wooden jigsaw puzzle maker with retail store, has wholesale page",
        },
        {
            "store_name": "Some Gift Shop",
            "store_type": "gift shop",
            "city": "Random Town",
            "state": "TX",
            "email": "",
            "email_type": "contact_form_only",
            "official_website": "https://somegiftshop.com",
            "contact_page": "",
            "evidence_url": "https://somegiftshop.com",
            "fit_reason": "Gift shop with some puzzles",
        },
    ]

    for lead in test_leads:
        result = score_lead(lead)
        print(f"\n{lead['store_name']}:")
        print(f"  等级: {result['grade']} (总分: {result['total_score']})")
        print(f"  评分: {result['scores']}")
        print(f"  理由: {'; '.join(result['reasons'])}")
        print(f"  自动发信: {result['auto_send']}")
