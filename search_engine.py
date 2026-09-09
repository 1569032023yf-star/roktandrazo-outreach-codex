"""
Roktandrazo BD Outreach - Search Engine
搜索引擎模块：定义搜索逻辑，过滤结果，去重

注意：实际的WebSearch调用在主流程中完成，本模块定义搜索策略和结果处理逻辑
"""

import re
from typing import List, Dict, Set
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """从URL提取域名"""
    if not url:
        return ""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    # 移除www.前缀
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def is_valid_store_url(url: str) -> bool:
    """检查URL是否是有效的门店官网"""
    if not url:
        return False
    
    # 排除的域名
    excluded_domains = [
        "google.com", "yelp.com", "tripadvisor.com", "facebook.com",
        "instagram.com", "twitter.com", "linkedin.com", "pinterest.com",
        "youtube.com", "tiktok.com", "reddit.com", "wikipedia.org",
        "amazon.com", "ebay.com", "etsy.com", "shopify.com",
        "yellowpages.com", "bbb.org", "angieslist.com",
        "mapquest.com", "foursquare.com", "zomato.com",
    ]
    
    domain = extract_domain(url)
    for excluded in excluded_domains:
        if excluded in domain:
            return False
    
    # 检查是否是有效的URL格式
    if not url.startswith(("http://", "https://")):
        return False
    
    return True


def extract_store_info_from_snippet(snippet: str, title: str = "") -> Dict:
    """从搜索结果片段中提取门店信息"""
    info = {
        "store_name": "",
        "store_type": "",
        "address": "",
        "phone": "",
    }
    
    # 尝试从标题提取门店名
    if title:
        # 移除常见后缀
        title_clean = re.sub(r'\s*[-–|].*$', '', title)
        title_clean = re.sub(r'\s*\(.*?\)', '', title_clean)
        info["store_name"] = title_clean.strip()
    
    # 从片段中提取地址
    address_pattern = r'\d+\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct|Place|Pl)\b'
    address_match = re.search(address_pattern, snippet, re.IGNORECASE)
    if address_match:
        info["address"] = address_match.group(0).strip()
    
    # 从片段中提取电话
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phone_match = re.search(phone_pattern, snippet)
    if phone_match:
        info["phone"] = phone_match.group(0).strip()
    
    # 从片段中提取门店类型
    store_type_keywords = {
        "toy store": ["toy store", "toy shop", "toy retailer"],
        "puzzle store": ["puzzle store", "puzzle shop", "puzzle retailer"],
        "board game store": ["board game", "game store", "game shop"],
        "gift shop": ["gift shop", "gift store", "gift retailer"],
        "museum store": ["museum store", "museum shop", "museum gift"],
        "bookstore": ["bookstore", "book store", "book shop"],
        "educational store": ["educational", "learning store", "teaching"],
    }
    
    snippet_lower = snippet.lower()
    title_lower = title.lower()
    combined_text = f"{snippet_lower} {title_lower}"
    
    for store_type, keywords in store_type_keywords.items():
        if any(keyword in combined_text for keyword in keywords):
            info["store_type"] = store_type
            break
    
    return info


def filter_search_results(results: List[Dict], city: str, state: str) -> List[Dict]:
    """
    过滤搜索结果，只保留有效的门店官网
    
    Args:
        results: WebSearch返回的结果列表
        city: 城市名
        state: 州代码
    
    Returns:
        过滤后的结果列表
    """
    filtered = []
    seen_domains: Set[str] = set()
    
    for result in results:
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        
        # 检查URL是否有效
        if not is_valid_store_url(url):
            continue
        
        # 去重
        domain = extract_domain(url)
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        
        # 提取门店信息
        store_info = extract_store_info_from_snippet(snippet, title)
        
        # 检查是否与目标城市相关
        combined_text = f"{title} {snippet}".lower()
        city_lower = city.lower()
        state_lower = state.lower()
        
        # 如果片段中没有提到城市，但URL可能包含城市信息
        city_related = (
            city_lower in combined_text or
            state_lower in combined_text or
            city_lower in url.lower()
        )
        
        filtered.append({
            "url": url,
            "title": title,
            "snippet": snippet,
            "domain": domain,
            "store_info": store_info,
            "city_related": city_related,
            "city": city,
            "state": state,
        })
    
    return filtered


def deduplicate_results(results: List[Dict]) -> List[Dict]:
    """
    去重：同一门店不同搜索结果合并
    
    Args:
        results: 搜索结果列表
    
    Returns:
        去重后的结果列表
    """
    seen: Dict[str, Dict] = {}
    
    for result in results:
        domain = result.get("domain", "")
        if not domain:
            continue
        
        if domain not in seen:
            seen[domain] = result
        else:
            # 合并信息：保留更完整的那个
            existing = seen[domain]
            
            # 如果新结果有更多信息，更新
            if len(result.get("snippet", "")) > len(existing.get("snippet", "")):
                seen[domain] = result
    
    return list(seen.values())


def rank_results(results: List[Dict]) -> List[Dict]:
    """
    对结果进行排序，优先显示更相关的结果
    
    Args:
        results: 搜索结果列表
    
    Returns:
        排序后的结果列表
    """
    def relevance_score(result: Dict) -> int:
        score = 0
        
        # 城市相关加分
        if result.get("city_related"):
            score += 10
        
        # 标题中包含门店关键词加分
        title_lower = result.get("title", "").lower()
        store_keywords = ["toy", "puzzle", "game", "gift", "store", "shop"]
        for keyword in store_keywords:
            if keyword in title_lower:
                score += 5
        
        # 片段中包含联系方式加分
        snippet = result.get("snippet", "").lower()
        if "email" in snippet or "@" in snippet:
            score += 3
        if "contact" in snippet:
            score += 2
        if "wholesale" in snippet:
            score += 2
        
        return score
    
    results.sort(key=relevance_score, reverse=True)
    return results


def process_search_results(results: List[Dict], city: str, state: str) -> List[Dict]:
    """
    处理搜索结果：过滤、去重、排序
    
    Args:
        results: WebSearch返回的原始结果
        city: 城市名
        state: 州代码
    
    Returns:
        处理后的结果列表
    """
    # 1. 过滤无效结果
    filtered = filter_search_results(results, city, state)
    
    # 2. 去重
    deduplicated = deduplicate_results(filtered)
    
    # 3. 排序
    ranked = rank_results(deduplicated)
    
    return ranked


if __name__ == "__main__":
    # 测试搜索引擎逻辑
    print("=== Search Engine Test ===")
    
    # 模拟搜索结果
    mock_results = [
        {
            "url": "https://www.thinkertoystore.com/",
            "title": "Thinker Toys - Independent Toy Store in Portland, OR",
            "snippet": "Thinker Toys is an award-winning independent toy store in Portland, Oregon. We carry puzzles, games, and educational toys."
        },
        {
            "url": "https://www.yelp.com/biz/thinker-toys-portland",
            "title": "Thinker Toys - Portland, OR - Yelp",
            "snippet": "Reviews of Thinker Toys in Portland, OR"
        },
        {
            "url": "https://www.cloudcapgames.com/",
            "title": "Cloud Cap Games & Puzzles - Portland, OR",
            "snippet": "Board games, card games, and puzzles in Portland, Oregon. Contact us at info@cloudcapgames.com"
        },
        {
            "url": "https://www.amazon.com/toys",
            "title": "Amazon Toys",
            "snippet": "Shop toys on Amazon"
        },
    ]
    
    # 处理结果
    processed = process_search_results(mock_results, "Portland", "OR")
    
    print(f"\nProcessed {len(processed)} results:")
    for result in processed:
        print(f"  {result['domain']}: {result['title']}")
        print(f"    City related: {result['city_related']}")
        print(f"    Store info: {result['store_info']}")
        print()