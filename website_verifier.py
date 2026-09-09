"""
Roktandrazo BD Outreach - Website Verifier
官网验证器：访问官网确认存在，查找contact/wholesale页面

注意：实际的WebFetch调用在主流程中完成，本模块定义验证逻辑
"""

import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse


def normalize_url(url: str) -> str:
    """标准化URL"""
    if not url:
        return ""
    
    # 添加协议
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    # 移除末尾斜杠
    url = url.rstrip("/")
    
    return url


def extract_links_from_html(html: str, base_url: str) -> List[Dict]:
    """从HTML中提取链接"""
    links = []
    
    # 简单的链接提取正则
    link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
    matches = re.findall(link_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for href, text in matches:
        # 处理相对URL
        full_url = urljoin(base_url, href)
        
        # 清理文本
        text_clean = re.sub(r'<[^>]+>', '', text).strip()
        
        links.append({
            "url": full_url,
            "text": text_clean,
        })
    
    return links


def find_contact_page(links: List[Dict]) -> Optional[str]:
    """从链接列表中查找contact页面"""
    contact_keywords = [
        "contact", "contact us", "contact-us", "contactus",
        "reach us", "get in touch", "send us", "email us",
    ]
    
    for link in links:
        url_lower = link["url"].lower()
        text_lower = link["text"].lower()
        
        # 检查URL
        if any(keyword in url_lower for keyword in contact_keywords):
            return link["url"]
        
        # 检查链接文本
        if any(keyword in text_lower for keyword in contact_keywords):
            return link["url"]
    
    return None


def find_wholesale_page(links: List[Dict]) -> Optional[str]:
    """从链接列表中查找wholesale/vendor页面"""
    wholesale_keywords = [
        "wholesale", "vendor", "supplier", "partner",
        "work with us", "work-with-us", "workwithus",
        "become a vendor", "become a supplier",
        "sell with us", "carry our products",
        "business", "b2b", "trade",
    ]
    
    for link in links:
        url_lower = link["url"].lower()
        text_lower = link["text"].lower()
        
        # 检查URL
        if any(keyword in url_lower for keyword in wholesale_keywords):
            return link["url"]
        
        # 检查链接文本
        if any(keyword in text_lower for keyword in wholesale_keywords):
            return link["url"]
    
    return None


def extract_emails_from_html(html: str) -> List[str]:
    """从HTML中提取邮箱地址"""
    emails = []
    
    # 邮箱正则表达式
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # 从mailto:链接提取
    mailto_pattern = r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    mailto_matches = re.findall(mailto_pattern, html, re.IGNORECASE)
    emails.extend(mailto_matches)
    
    # 从文本中提取
    text_matches = re.findall(email_pattern, html)
    emails.extend(text_matches)
    
    # 去重
    unique_emails = list(set(emails))
    
    # 过滤无效邮箱
    valid_emails = []
    for email in unique_emails:
        email_lower = email.lower()
        
        # 排除常见无效邮箱
        invalid_patterns = [
            "example.com", "test.com", "sample.com",
            "email.com", "domain.com", "yourdomain.com",
            "placeholder", "noreply", "no-reply",
        ]
        
        if not any(pattern in email_lower for pattern in invalid_patterns):
            valid_emails.append(email)
    
    return valid_emails


def extract_contact_form_from_html(html: str, base_url: str) -> Optional[str]:
    """从HTML中提取联系表单URL"""
    # 查找form标签
    form_pattern = r'<form[^>]+action=["\']([^"\']+)["\'][^>]*>'
    form_matches = re.findall(form_pattern, html, re.IGNORECASE)
    
    for action in form_matches:
        # 处理相对URL
        full_url = urljoin(base_url, action)
        
        # 检查是否是联系表单
        action_lower = action.lower()
        if any(keyword in action_lower for keyword in ["contact", "inquiry", "message", "submit"]):
            return full_url
    
    # 如果没有找到明确的联系表单，返回None
    return None


def determine_email_type(email: str) -> str:
    """判断邮箱类型"""
    email_lower = email.lower()
    local_part = email_lower.split("@")[0]
    
    # 所有者/个人邮箱
    owner_patterns = ["owner", "founder", "ceo", "president", "director"]
    if any(pattern in local_part for pattern in owner_patterns):
        return "owner"
    
    # 买家/采购邮箱
    buyer_patterns = ["buyer", "purchasing", "procurement", "sourcing"]
    if any(pattern in local_part for pattern in buyer_patterns):
        return "buyer"
    
    # 批发邮箱
    wholesale_patterns = ["wholesale", "bulk", "trade", "b2b"]
    if any(pattern in local_part for pattern in wholesale_patterns):
        return "wholesale"
    
    # 供应商邮箱
    vendor_patterns = ["vendor", "supplier", "partner"]
    if any(pattern in local_part for pattern in vendor_patterns):
        return "vendor"
    
    # 支持邮箱
    support_patterns = ["support", "help", "service", "care"]
    if any(pattern in local_part for pattern in support_patterns):
        return "support"
    
    # 通用邮箱
    general_patterns = ["info", "contact", "hello", "hi", "admin", "office"]
    if any(pattern in local_part for pattern in general_patterns):
        return "general"
    
    # 默认
    return "unknown"


def verify_website(url: str, html: str = None) -> Dict:
    """
    验证官网并提取信息
    
    Args:
        url: 官网URL
        html: 页面HTML内容（可选，如果为None则返回需要获取的URL）
    
    Returns:
        验证结果字典
    """
    result = {
        "url": normalize_url(url),
        "is_valid": False,
        "contact_page": None,
        "wholesale_page": None,
        "emails": [],
        "contact_form": None,
        "evidence_url": None,
        "error": None,
    }
    
    if not url:
        result["error"] = "No URL provided"
        return result
    
    # 如果没有HTML，返回需要获取的URL
    if html is None:
        result["need_fetch"] = True
        result["fetch_url"] = normalize_url(url)
        return result
    
    try:
        # 提取链接
        links = extract_links_from_html(html, url)
        
        # 查找联系页面
        contact_page = find_contact_page(links)
        if contact_page:
            result["contact_page"] = contact_page
        
        # 查找批发页面
        wholesale_page = find_wholesale_page(links)
        if wholesale_page:
            result["wholesale_page"] = wholesale_page
        
        # 提取邮箱
        emails = extract_emails_from_html(html)
        result["emails"] = emails
        
        # 提取联系表单
        contact_form = extract_contact_form_from_html(html, url)
        if contact_form:
            result["contact_form"] = contact_form
        
        # 设置证据URL
        if emails:
            result["evidence_url"] = url
        elif contact_page:
            result["evidence_url"] = contact_page
        elif wholesale_page:
            result["evidence_url"] = wholesale_page
        
        # 标记为有效
        result["is_valid"] = True
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def extract_store_type_from_html(html: str) -> str:
    """从HTML中提取门店类型"""
    html_lower = html.lower()
    
    # 门店类型关键词
    type_keywords = {
        "toy store": ["toy store", "toy shop", "toy retailer", "toy store"],
        "puzzle store": ["puzzle store", "puzzle shop", "puzzle retailer"],
        "board game store": ["board game store", "game store", "game shop"],
        "gift shop": ["gift shop", "gift store", "gift retailer"],
        "museum store": ["museum store", "museum shop", "museum gift"],
        "bookstore": ["bookstore", "book store", "book shop"],
        "educational store": ["educational store", "learning store", "teaching store"],
    }
    
    for store_type, keywords in type_keywords.items():
        if any(keyword in html_lower for keyword in keywords):
            return store_type
    
    return "retail store"


def extract_store_name_from_html(html: str) -> str:
    """从HTML中提取门店名称"""
    # 尝试从title标签提取
    title_pattern = r'<title[^>]*>(.*?)</title>'
    title_match = re.search(title_pattern, html, re.IGNORECASE | re.DOTALL)
    
    if title_match:
        title = title_match.group(1).strip()
        # 清理title
        title = re.sub(r'\s*[-–|].*$', '', title)  # 移除分隔符后的内容
        title = re.sub(r'\s*\(.*?\)', '', title)  # 移除括号内容
        return title.strip()
    
    return ""


if __name__ == "__main__":
    # 测试官网验证器
    print("=== Website Verifier Test ===")
    
    # 测试邮箱类型判断
    test_emails = [
        "info@store.com",
        "wholesale@store.com",
        "buyer@store.com",
        "owner@store.com",
        "support@store.com",
        "john@store.com",
    ]
    
    print("\nEmail type detection:")
    for email in test_emails:
        email_type = determine_email_type(email)
        print(f"  {email}: {email_type}")
    
    # 测试链接提取
    test_html = """
    <html>
    <head><title>Test Store - Toys & Games</title></head>
    <body>
        <a href="/contact">Contact Us</a>
        <a href="/wholesale">Wholesale Inquiries</a>
        <a href="mailto:info@teststore.com">Email Us</a>
        <p>Contact us at info@teststore.com or wholesale@teststore.com</p>
    </body>
    </html>
    """
    
    print("\nWebsite verification:")
    result = verify_website("https://teststore.com", test_html)
    print(f"  URL: {result['url']}")
    print(f"  Valid: {result['is_valid']}")
    print(f"  Contact page: {result['contact_page']}")
    print(f"  Wholesale page: {result['wholesale_page']}")
    print(f"  Emails: {result['emails']}")
    print(f"  Evidence URL: {result['evidence_url']}")
    
    # 测试门店名称提取
    store_name = extract_store_name_from_html(test_html)
    print(f"\nStore name: {store_name}")