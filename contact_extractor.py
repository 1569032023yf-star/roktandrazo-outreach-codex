"""
Roktandrazo BD Outreach - Contact Extractor
联系信息提取器：从官网提取邮箱、联系表单、wholesale页面

整合官网验证器功能，提供完整的联系信息提取
"""

from typing import Dict, List, Optional
from website_verifier import (
    verify_website,
    extract_emails_from_html,
    find_contact_page,
    find_wholesale_page,
    extract_contact_form_from_html,
    determine_email_type,
    extract_store_type_from_html,
    extract_store_name_from_html,
    normalize_url,
)


def extract_contact_info(url: str, html: str = None) -> Dict:
    """
    从官网提取完整的联系信息
    
    Args:
        url: 官网URL
        html: 页面HTML内容（可选）
    
    Returns:
        联系信息字典
    """
    # 首先验证官网
    verification = verify_website(url, html)
    
    if not verification["is_valid"]:
        return {
            "success": False,
            "error": verification.get("error", "Website verification failed"),
            "url": url,
        }
    
    # 提取联系信息
    contact_info = {
        "success": True,
        "url": verification["url"],
        "contact_page": verification["contact_page"],
        "wholesale_page": verification["wholesale_page"],
        "emails": verification["emails"],
        "contact_form": verification["contact_form"],
        "evidence_url": verification["evidence_url"],
        "store_name": "",
        "store_type": "",
        "primary_email": None,
        "email_type": None,
    }
    
    # 如果有HTML，提取更多信息
    if html:
        contact_info["store_name"] = extract_store_name_from_html(html)
        contact_info["store_type"] = extract_store_type_from_html(html)
    
    # 选择主要邮箱
    if contact_info["emails"]:
        # 优先选择批发/供应商邮箱
        wholesale_emails = []
        vendor_emails = []
        buyer_emails = []
        general_emails = []
        other_emails = []
        
        for email in contact_info["emails"]:
            email_type = determine_email_type(email)
            
            if email_type == "wholesale":
                wholesale_emails.append(email)
            elif email_type == "vendor":
                vendor_emails.append(email)
            elif email_type == "buyer":
                buyer_emails.append(email)
            elif email_type == "general":
                general_emails.append(email)
            else:
                other_emails.append(email)
        
        # 按优先级选择
        if wholesale_emails:
            contact_info["primary_email"] = wholesale_emails[0]
            contact_info["email_type"] = "wholesale"
        elif vendor_emails:
            contact_info["primary_email"] = vendor_emails[0]
            contact_info["email_type"] = "vendor"
        elif buyer_emails:
            contact_info["primary_email"] = buyer_emails[0]
            contact_info["email_type"] = "buyer"
        elif general_emails:
            contact_info["primary_email"] = general_emails[0]
            contact_info["email_type"] = "general"
        elif other_emails:
            contact_info["primary_email"] = other_emails[0]
            contact_info["email_type"] = "unknown"
    
    # 如果没有邮箱，但有联系表单
    if not contact_info["primary_email"] and contact_info["contact_form"]:
        contact_info["email_type"] = "contact_form_only"
    
    return contact_info


def extract_contact_from_multiple_pages(base_url: str, pages: List[Dict]) -> Dict:
    """
    从多个页面提取联系信息
    
    Args:
        base_url: 基础URL
        pages: 页面列表，每个页面包含url和html
    
    Returns:
        合并的联系信息
    """
    all_emails = []
    contact_page = None
    wholesale_page = None
    contact_form = None
    evidence_url = None
    store_name = ""
    store_type = ""
    
    for page in pages:
        url = page.get("url", base_url)
        html = page.get("html", "")
        
        if not html:
            continue
        
        # 提取邮箱
        emails = extract_emails_from_html(html)
        all_emails.extend(emails)
        
        # 查找联系页面
        from website_verifier import extract_links_from_html
        links = extract_links_from_html(html, url)
        
        if not contact_page:
            found_contact = find_contact_page(links)
            if found_contact:
                contact_page = found_contact
        
        # 查找批发页面
        if not wholesale_page:
            found_wholesale = find_wholesale_page(links)
            if found_wholesale:
                wholesale_page = found_wholesale
        
        # 提取联系表单
        if not contact_form:
            found_form = extract_contact_form_from_html(html, url)
            if found_form:
                contact_form = found_form
        
        # 提取门店信息
        if not store_name:
            store_name = extract_store_name_from_html(html)
        
        if not store_type:
            store_type = extract_store_type_from_html(html)
    
    # 去重邮箱
    unique_emails = list(set(all_emails))
    
    # 选择证据URL
    if unique_emails:
        evidence_url = base_url
    elif contact_page:
        evidence_url = contact_page
    elif wholesale_page:
        evidence_url = wholesale_page
    
    # 选择主要邮箱
    primary_email = None
    email_type = None
    
    if unique_emails:
        # 按类型分组
        wholesale_emails = []
        vendor_emails = []
        buyer_emails = []
        general_emails = []
        other_emails = []
        
        for email in unique_emails:
            etype = determine_email_type(email)
            
            if etype == "wholesale":
                wholesale_emails.append(email)
            elif etype == "vendor":
                vendor_emails.append(email)
            elif etype == "buyer":
                buyer_emails.append(email)
            elif etype == "general":
                general_emails.append(email)
            else:
                other_emails.append(email)
        
        # 按优先级选择
        if wholesale_emails:
            primary_email = wholesale_emails[0]
            email_type = "wholesale"
        elif vendor_emails:
            primary_email = vendor_emails[0]
            email_type = "vendor"
        elif buyer_emails:
            primary_email = buyer_emails[0]
            email_type = "buyer"
        elif general_emails:
            primary_email = general_emails[0]
            email_type = "general"
        elif other_emails:
            primary_email = other_emails[0]
            email_type = "unknown"
    
    return {
        "success": True,
        "url": base_url,
        "contact_page": contact_page,
        "wholesale_page": wholesale_page,
        "emails": unique_emails,
        "contact_form": contact_form,
        "evidence_url": evidence_url,
        "store_name": store_name,
        "store_type": store_type,
        "primary_email": primary_email,
        "email_type": email_type,
    }


def format_contact_info(contact_info: Dict) -> str:
    """格式化联系信息为可读字符串"""
    if not contact_info.get("success"):
        return f"Failed to extract contact info: {contact_info.get('error', 'Unknown error')}"
    
    lines = []
    lines.append(f"URL: {contact_info['url']}")
    
    if contact_info.get("store_name"):
        lines.append(f"Store Name: {contact_info['store_name']}")
    
    if contact_info.get("store_type"):
        lines.append(f"Store Type: {contact_info['store_type']}")
    
    if contact_info.get("primary_email"):
        lines.append(f"Primary Email: {contact_info['primary_email']} ({contact_info.get('email_type', 'unknown')})")
    
    if contact_info.get("emails"):
        lines.append(f"All Emails: {', '.join(contact_info['emails'])}")
    
    if contact_info.get("contact_page"):
        lines.append(f"Contact Page: {contact_info['contact_page']}")
    
    if contact_info.get("wholesale_page"):
        lines.append(f"Wholesale Page: {contact_info['wholesale_page']}")
    
    if contact_info.get("contact_form"):
        lines.append(f"Contact Form: {contact_info['contact_form']}")
    
    if contact_info.get("evidence_url"):
        lines.append(f"Evidence URL: {contact_info['evidence_url']}")
    
    return "\n".join(lines)


def prepare_lead_data(contact_info: Dict, city: str, state: str, source_keyword: str = "") -> Dict:
    """
    将联系信息转换为线索数据格式
    
    Args:
        contact_info: 联系信息字典
        city: 城市名
        state: 州代码
        source_keyword: 来源关键词
    
    Returns:
        线索数据字典
    """
    if not contact_info.get("success"):
        return None
    
    # 确定产品适配性
    product_fit = "both"  # 默认两者都适配
    store_type = contact_info.get("store_type", "").lower()
    store_name = contact_info.get("store_name", "").lower()
    
    # 根据门店类型判断产品适配性
    if "puzzle" in store_type or "puzzle" in store_name:
        product_fit = "puzzles"
    elif "game" in store_type or "game" in store_name:
        product_fit = "card_games"
    elif "toy" in store_type or "toy" in store_name:
        product_fit = "both"
    elif "gift" in store_type or "gift" in store_name:
        product_fit = "both"
    elif "museum" in store_type or "museum" in store_name:
        product_fit = "puzzles"
    elif "book" in store_type or "book" in store_name:
        product_fit = "both"
    elif "educational" in store_type or "learning" in store_type:
        product_fit = "both"
    
    # 确定置信度分数
    confidence_score = "C"  # 默认C级
    
    has_email = bool(contact_info.get("primary_email"))
    has_contact_form = bool(contact_info.get("contact_form"))
    has_wholesale_page = bool(contact_info.get("wholesale_page"))
    has_contact_page = bool(contact_info.get("contact_page"))
    
    if has_email:
        # 有邮箱
        email_type = contact_info.get("email_type", "unknown")
        
        if email_type in ["wholesale", "vendor", "buyer"]:
            # 有明确的商务邮箱
            confidence_score = "A"
        elif email_type == "general":
            # 有通用邮箱
            if has_wholesale_page:
                confidence_score = "A"
            else:
                confidence_score = "B"
        else:
            # 其他类型邮箱
            confidence_score = "B"
    elif has_contact_form:
        # 只有联系表单
        confidence_score = "B"
    elif has_contact_page:
        # 有联系页面但没提取到邮箱
        confidence_score = "C"
    else:
        # 信息不完整
        confidence_score = "C"
    
    # 构建适合性原因
    fit_reason_parts = []
    if store_type:
        fit_reason_parts.append(f"Store type: {store_type}")
    if has_email:
        fit_reason_parts.append(f"Has email: {contact_info['primary_email']}")
    if has_wholesale_page:
        fit_reason_parts.append("Has wholesale page")
    if has_contact_page:
        fit_reason_parts.append("Has contact page")
    
    fit_reason = "; ".join(fit_reason_parts) if fit_reason_parts else "Information incomplete"
    
    return {
        "store_name": contact_info.get("store_name", ""),
        "store_type": contact_info.get("store_type", ""),
        "city": city,
        "state": state,
        "official_website": contact_info.get("url", ""),
        "contact_page": contact_info.get("contact_page", ""),
        "wholesale_or_vendor_page": contact_info.get("wholesale_page", ""),
        "email": contact_info.get("primary_email", ""),
        "email_type": contact_info.get("email_type", ""),
        "contact_form_url": contact_info.get("contact_form", ""),
        "evidence_url": contact_info.get("evidence_url", ""),
        "source_keyword": source_keyword,
        "fit_reason": fit_reason,
        "product_fit": product_fit,
        "confidence_score": confidence_score,
        "status": "new",
        "notes": f"Auto-collected from {city}, {state}",
    }


if __name__ == "__main__":
    # 测试联系信息提取器
    print("=== Contact Extractor Test ===")
    
    # 模拟HTML
    test_html = """
    <html>
    <head><title>Test Store - Toys & Games</title></head>
    <body>
        <a href="/contact">Contact Us</a>
        <a href="/wholesale">Wholesale Inquiries</a>
        <a href="mailto:info@teststore.com">General Info</a>
        <a href="mailto:wholesale@teststore.com">Wholesale</a>
        <p>Contact us at info@teststore.com or wholesale@teststore.com</p>
    </body>
    </html>
    """
    
    # 提取联系信息
    contact_info = extract_contact_info("https://teststore.com", test_html)
    
    print("\nContact Info:")
    print(format_contact_info(contact_info))
    
    # 准备线索数据
    lead_data = prepare_lead_data(contact_info, "Portland", "OR", "test search")
    
    print("\nLead Data:")
    for key, value in lead_data.items():
        print(f"  {key}: {value}")