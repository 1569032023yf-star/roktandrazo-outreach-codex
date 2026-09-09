"""
Roktandrazo BD Outreach - City Selector
按策略自动选择美国城市进行线索采集
"""

import json
import os
import random
from datetime import datetime

# 城市候选池
CITY_POOL = {
    "tourist": [
        # 旅游城市
        {"city": "Asheville", "state": "NC", "priority": 1, "reason": "艺术文化重镇，独立零售密集"},
        {"city": "Bar Harbor", "state": "ME", "priority": 1, "reason": "Acadia国家公园门户，礼品店密集"},
        {"city": "Sedona", "state": "AZ", "priority": 1, "reason": "艺术社区，礼品店众多"},
        {"city": "Carmel-by-the-Sea", "state": "CA", "priority": 1, "reason": "艺术村，精品店密集"},
        {"city": "Taos", "state": "NM", "priority": 1, "reason": "艺术殖民地，独立零售"},
        {"city": "Eureka Springs", "state": "AR", "priority": 1, "reason": "维多利亚式小镇，礼品店"},
        {"city": "Savannah", "state": "GA", "priority": 1, "reason": "历史名城，旅游零售"},
        {"city": "Charleston", "state": "SC", "priority": 1, "reason": "历史名城，精品店密集"},
        {"city": "Stowe", "state": "VT", "priority": 1, "reason": "滑雪胜地，独立零售"},
        {"city": "Woodstock", "state": "VT", "priority": 1, "reason": "艺术社区，独立零售"},
        {"city": "Park City", "state": "UT", "priority": 1, "reason": "滑雪胜地，旅游零售"},
        {"city": "Bend", "state": "OR", "priority": 1, "reason": "户外运动中心，独立零售"},
        {"city": "Traverse City", "state": "MI", "priority": 1, "reason": "五大湖旅游，独立零售"},
        {"city": "Lake Geneva", "state": "WI", "priority": 1, "reason": "度假胜地，礼品店"},
        {"city": "Portsmouth", "state": "NH", "priority": 1, "reason": "历史港口城市，独立零售"},
        {"city": "Key West", "state": "FL", "priority": 1, "reason": "旅游胜地，礼品店密集"},
        {"city": "Santa Fe", "state": "NM", "priority": 1, "reason": "艺术之都，博物馆商店"},
        {"city": "Jackson Hole", "state": "WY", "priority": 1, "reason": "国家公园门户，旅游零售"},
        {"city": "Nashville", "state": "TN", "priority": 2, "reason": "音乐之城，旅游零售"},
        {"city": "Austin", "state": "TX", "priority": 2, "reason": "文化之城，独立零售"},
        {"city": "Portland", "state": "OR", "priority": 2, "reason": "独立零售密集，游戏文化"},
        {"city": "Boulder", "state": "CO", "priority": 2, "reason": "大学城，独立零售"},
        {"city": "Cape Cod", "state": "MA", "priority": 2, "reason": "海滨度假，礼品店"},
        {"city": "Williamsburg", "state": "VA", "priority": 2, "reason": "历史名城，旅游零售"},
        {"city": "San Antonio", "state": "TX", "priority": 2, "reason": "历史名城，旅游零售"},
        {"city": "New Orleans", "state": "LA", "priority": 2, "reason": "文化名城，独立零售"},
        {"city": "Miami Beach", "state": "FL", "priority": 2, "reason": "旅游胜地，精品店"},
        {"city": "Sausalito", "state": "CA", "priority": 2, "reason": "艺术社区，精品店"},
        {"city": "Monterey", "state": "CA", "priority": 2, "reason": "海滨城市，旅游零售"},
        {"city": "Santa Barbara", "state": "CA", "priority": 2, "reason": "海滨城市，精品店"},
    ],
    "cultural": [
        # 文化重镇
        {"city": "Seattle", "state": "WA", "priority": 1, "reason": "文化多元，独立零售发达"},
        {"city": "San Francisco", "state": "CA", "priority": 1, "reason": "文化多元，独立零售发达"},
        {"city": "Los Angeles", "state": "CA", "priority": 1, "reason": "文化多元，独立零售发达"},
        {"city": "San Diego", "state": "CA", "priority": 1, "reason": "海滨城市，旅游零售"},
        {"city": "Denver", "state": "CO", "priority": 1, "reason": "文化多元，独立零售发达"},
        {"city": "Chicago", "state": "IL", "priority": 1, "reason": "文化多元，独立零售发达"},
        {"city": "Boston", "state": "MA", "priority": 1, "reason": "历史名城，独立零售发达"},
        {"city": "New York", "state": "NY", "priority": 1, "reason": "文化多元，独立零售发达"},
        {"city": "Philadelphia", "state": "PA", "priority": 1, "reason": "历史名城，独立零售发达"},
        {"city": "Washington", "state": "DC", "priority": 1, "reason": "首都，博物馆商店密集"},
    ],
    "independent_retail": [
        # 独立零售密集区
        {"city": "Portland", "state": "OR", "priority": 1, "reason": "独立零售密集，游戏文化"},
        {"city": "Austin", "state": "TX", "priority": 1, "reason": "文化之城，独立零售"},
        {"city": "Asheville", "state": "NC", "priority": 1, "reason": "艺术文化重镇，独立零售密集"},
        {"city": "Burlington", "state": "VT", "priority": 1, "reason": "大学城，独立零售"},
        {"city": "Boulder", "state": "CO", "priority": 1, "reason": "大学城，独立零售"},
        {"city": "Ann Arbor", "state": "MI", "priority": 1, "reason": "大学城，独立零售"},
        {"city": "Madison", "state": "WI", "priority": 1, "reason": "大学城，独立零售"},
        {"city": "Ithaca", "state": "NY", "priority": 1, "reason": "大学城，独立零售"},
        {"city": "Eugene", "state": "OR", "priority": 1, "reason": "大学城，独立零售"},
        {"city": "Fort Collins", "state": "CO", "priority": 1, "reason": "大学城，独立零售"},
    ]
}

# 搜索关键词模板
SEARCH_QUERIES = [
    "independent toy store {city} {state}",
    "board game store {city} {state}",
    "puzzle shop {city} {state}",
    "gift shop {city} {state} toys games",
    "museum store {city} {state}",
    "bookstore gifts {city} {state}",
    "educational toy store {city} {state}",
    "family activity store {city} {state}",
]

# 已搜索城市记录文件
SEARCHED_CITIES_FILE = os.path.join(os.path.dirname(__file__), "data", "searched_cities.json")


def load_searched_cities() -> dict:
    """加载已搜索城市记录"""
    if os.path.exists(SEARCHED_CITIES_FILE):
        with open(SEARCHED_CITIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_searched_cities(searched: dict):
    """保存已搜索城市记录"""
    os.makedirs(os.path.dirname(SEARCHED_CITIES_FILE), exist_ok=True)
    with open(SEARCHED_CITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(searched, f, indent=2, ensure_ascii=False)


def get_city_key(city_info: dict) -> str:
    """生成城市唯一键"""
    return f"{city_info['city']}_{city_info['state']}".lower()


def select_cities(count: int = 3, strategy: str = "mixed") -> list[dict]:
    """
    按策略选择城市
    
    Args:
        count: 选择城市数量
        strategy: 选择策略
            - "tourist": 只选旅游城市
            - "cultural": 只选文化重镇
            - "independent_retail": 只选独立零售密集区
            - "mixed": 混合选择（默认）
            - "random": 随机选择
    
    Returns:
        选中的城市列表
    """
    searched = load_searched_cities()
    
    if strategy == "mixed":
        # 混合策略：从每个类别中按优先级选择
        candidates = []
        for category, cities in CITY_POOL.items():
            for city in cities:
                key = get_city_key(city)
                if key not in searched:
                    candidates.append({**city, "category": category})
        
        # 按优先级排序，优先选择未搜索过的高优先级城市
        candidates.sort(key=lambda x: (x["priority"], random.random()))
        selected = candidates[:count]
        
    elif strategy == "random":
        # 随机策略：从所有城市中随机选择
        all_cities = []
        for category, cities in CITY_POOL.items():
            for city in cities:
                key = get_city_key(city)
                if key not in searched:
                    all_cities.append({**city, "category": category})
        
        random.shuffle(all_cities)
        selected = all_cities[:count]
        
    else:
        # 按类别策略
        if strategy not in CITY_POOL:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        candidates = []
        for city in CITY_POOL[strategy]:
            key = get_city_key(city)
            if key not in searched:
                candidates.append({**city, "category": strategy})
        
        candidates.sort(key=lambda x: (x["priority"], random.random()))
        selected = candidates[:count]
    
    # 记录已搜索城市
    for city in selected:
        key = get_city_key(city)
        searched[key] = {
            "city": city["city"],
            "state": city["state"],
            "searched_at": datetime.now().isoformat(),
            "category": city.get("category", "unknown"),
            "reason": city.get("reason", "")
        }
    
    save_searched_cities(searched)
    return selected


def get_search_queries(city_info: dict) -> list[str]:
    """为指定城市生成搜索查询"""
    queries = []
    for query_template in SEARCH_QUERIES:
        query = query_template.format(
            city=city_info["city"],
            state=city_info["state"]
        )
        queries.append(query)
    return queries


def get_search_stats() -> dict:
    """获取搜索统计信息"""
    searched = load_searched_cities()
    
    stats = {
        "total_searched": len(searched),
        "by_category": {},
        "by_state": {},
        "recent_searches": []
    }
    
    for key, info in searched.items():
        # 按类别统计
        category = info.get("category", "unknown")
        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
        
        # 按州统计
        state = info.get("state", "unknown")
        stats["by_state"][state] = stats["by_state"].get(state, 0) + 1
    
    # 最近搜索的10个城市
    recent = sorted(searched.values(), key=lambda x: x.get("searched_at", ""), reverse=True)[:10]
    stats["recent_searches"] = recent
    
    return stats


def reset_search_history():
    """重置搜索历史（谨慎使用）"""
    if os.path.exists(SEARCHED_CITIES_FILE):
        os.remove(SEARCHED_CITIES_FILE)
    print("[City Selector] Search history reset")


if __name__ == "__main__":
    # 测试城市选择
    print("=== City Selector Test ===")
    
    # 选择3个混合城市
    cities = select_cities(count=3, strategy="mixed")
    print(f"\nSelected {len(cities)} cities (mixed strategy):")
    for city in cities:
        print(f"  {city['city']}, {city['state']} - {city.get('reason', '')}")
    
    # 生成搜索查询
    if cities:
        queries = get_search_queries(cities[0])
        print(f"\nSearch queries for {cities[0]['city']}, {cities[0]['state']}:")
        for q in queries:
            print(f"  {q}")
    
    # 显示统计
    stats = get_search_stats()
    print(f"\nSearch Stats:")
    print(f"  Total searched: {stats['total_searched']}")
    print(f"  By category: {stats['by_category']}")
    print(f"  By state: {stats['by_state']}")