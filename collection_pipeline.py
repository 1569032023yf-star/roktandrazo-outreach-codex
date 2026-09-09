"""
Roktandrazo BD Outreach - Collection Pipeline
采集流水线：定义完整的自动采集流程，供AI agent调用

用法:
  python collection_pipeline.py select-cities    # 选择城市
  python collection_pipeline.py search           # 搜索门店
  python collection_pipeline.py verify           # 验证官网
  python collection_pipeline.py extract          # 提取联系信息
  python collection_pipeline.py score            # 评分
  python collection_pipeline.py save             # 保存到数据库
  python collection_pipeline.py report           # 生成报告
  python collection_pipeline.py full             # 完整流程（需要AI agent调用工具）
"""

import sys
import json
from datetime import datetime

from city_selector import select_cities, get_search_queries, get_search_stats
from auto_collector import (
    collect_leads_for_city,
    save_leads_to_db,
    generate_collection_report,
    get_collection_summary,
)


def cmd_select_cities(count: int = 3, strategy: str = "mixed"):
    """选择城市"""
    print(f"\n=== Selecting Cities (strategy: {strategy}, count: {count}) ===")
    
    cities = select_cities(count=count, strategy=strategy)
    
    print(f"\nSelected {len(cities)} cities:")
    for i, city in enumerate(cities, 1):
        print(f"  {i}. {city['city']}, {city['state']} - {city.get('reason', '')}")
    
    # 生成搜索查询
    print(f"\nSearch queries for each city:")
    for city in cities:
        queries = get_search_queries(city)
        print(f"\n  {city['city']}, {city['state']}:")
        for q in queries:
            print(f"    - {q}")
    
    # 保存城市信息到临时文件
    output = {
        "cities": cities,
        "timestamp": datetime.now().isoformat(),
    }
    
    with open("temp_cities.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nCities saved to temp_cities.json")
    return cities


def cmd_search():
    """搜索门店（需要AI agent调用WebSearch工具）"""
    print("\n=== Search Phase ===")
    print("This step requires AI agent to call WebSearch tool.")
    print("Please use the following queries:")
    
    try:
        with open("temp_cities.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        cities = data["cities"]
        
        for city in cities:
            queries = get_search_queries(city)
            print(f"\n{city['city']}, {city['state']}:")
            for q in queries:
                print(f"  - {q}")
        
        print("\nSave search results to temp_search_results.json")
        print("Format: {city_key: [results...]}")
        
    except FileNotFoundError:
        print("Error: temp_cities.json not found. Run select-cities first.")


def cmd_verify():
    """验证官网（需要AI agent调用WebFetch工具）"""
    print("\n=== Verify Phase ===")
    print("This step requires AI agent to call WebFetch tool.")
    print("Please verify each website URL from search results.")
    
    try:
        with open("temp_search_results.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        urls = set()
        for city_key, results in data.items():
            for result in results:
                url = result.get("url", "")
                if url:
                    urls.add(url)
        
        print(f"\nFound {len(urls)} unique URLs to verify:")
        for url in sorted(urls):
            print(f"  - {url}")
        
        print("\nSave website HTMLs to temp_website_htmls.json")
        print("Format: {url: html_content}")
        
    except FileNotFoundError:
        print("Error: temp_search_results.json not found. Run search first.")


def cmd_extract():
    """提取联系信息"""
    print("\n=== Extract Phase ===")
    
    try:
        with open("temp_cities.json", "r", encoding="utf-8") as f:
            cities_data = json.load(f)
        
        with open("temp_search_results.json", "r", encoding="utf-8") as f:
            search_data = json.load(f)
        
        with open("temp_website_htmls.json", "r", encoding="utf-8") as f:
            html_data = json.load(f)
        
        cities = cities_data["cities"]
        
        all_leads = []
        
        for city_info in cities:
            city_key = f"{city_info['city']}_{city_info['state']}".lower()
            search_results = search_data.get(city_key, [])
            
            print(f"\nExtracting {city_info['city']}, {city_info['state']}...")
            
            leads = collect_leads_for_city(city_info, search_results, html_data)
            all_leads.extend(leads)
        
        # 保存提取结果
        with open("temp_leads.json", "w", encoding="utf-8") as f:
            json.dump(all_leads, f, indent=2, ensure_ascii=False)
        
        print(f"\nExtracted {len(all_leads)} leads, saved to temp_leads.json")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")


def cmd_score():
    """评分"""
    print("\n=== Score Phase ===")
    
    try:
        with open("temp_leads.json", "r", encoding="utf-8") as f:
            leads = json.load(f)
        
        print(f"Scoring {len(leads)} leads...")
        
        # 评分已经在extract阶段完成
        # 这里只是显示统计
        
        by_score = {"A": 0, "B": 0, "C": 0}
        for lead in leads:
            score = lead.get("confidence_score", "C")
            by_score[score] = by_score.get(score, 0) + 1
        
        print(f"\nScore distribution:")
        print(f"  A: {by_score['A']}")
        print(f"  B: {by_score['B']}")
        print(f"  C: {by_score['C']}")
        
    except FileNotFoundError:
        print("Error: temp_leads.json not found. Run extract first.")


def cmd_save():
    """保存到数据库"""
    print("\n=== Save Phase ===")
    
    try:
        with open("temp_leads.json", "r", encoding="utf-8") as f:
            leads = json.load(f)
        
        print(f"Saving {len(leads)} leads to database...")
        
        stats = save_leads_to_db(leads)
        
        print(f"\nSave results:")
        print(f"  Total: {stats['total']}")
        print(f"  Inserted: {stats['inserted']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  By score: {stats['by_score']}")
        
    except FileNotFoundError:
        print("Error: temp_leads.json not found. Run extract first.")


def cmd_report():
    """生成报告"""
    print("\n=== Report Phase ===")
    
    try:
        with open("temp_cities.json", "r", encoding="utf-8") as f:
            cities_data = json.load(f)
        
        with open("temp_leads.json", "r", encoding="utf-8") as f:
            leads = json.load(f)
        
        cities = cities_data["cities"]
        
        # 按城市分组
        city_leads = {}
        for lead in leads:
            city_key = f"{lead['city']}_{lead['state']}".lower()
            if city_key not in city_leads:
                city_leads[city_key] = []
            city_leads[city_key].append(lead)
        
        # 生成报告
        reports = []
        for city_info in cities:
            city_key = f"{city_info['city']}_{city_info['state']}".lower()
            city_leads_list = city_leads.get(city_key, [])
            
            # 统计
            stats = {
                "total": len(city_leads_list),
                "inserted": len(city_leads_list),
                "skipped": 0,
                "by_score": {"A": 0, "B": 0, "C": 0},
            }
            
            for lead in city_leads_list:
                score = lead.get("confidence_score", "C")
                stats["by_score"][score] = stats["by_score"].get(score, 0) + 1
            
            report = generate_collection_report(city_leads_list, stats, city_info)
            reports.append(report)
        
        # 保存报告
        full_report = "\n\n---\n\n".join(reports)
        
        with open("collection_report.md", "w", encoding="utf-8") as f:
            f.write(full_report)
        
        print(f"\nReport saved to collection_report.md")
        
        # 显示摘要
        print(f"\nSummary:")
        print(f"  Cities: {len(cities)}")
        print(f"  Total leads: {len(leads)}")
        
        by_score = {"A": 0, "B": 0, "C": 0}
        for lead in leads:
            score = lead.get("confidence_score", "C")
            by_score[score] = by_score.get(score, 0) + 1
        
        print(f"  A-grade: {by_score['A']}")
        print(f"  B-grade: {by_score['B']}")
        print(f"  C-grade: {by_score['C']}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")


def cmd_full():
    """完整流程（需要AI agent调用工具）"""
    print("\n=== Full Collection Pipeline ===")
    print("This is a multi-step process that requires AI agent to call tools.")
    print("\nSteps:")
    print("1. Run: python collection_pipeline.py select-cities")
    print("2. AI agent calls WebSearch for each city")
    print("3. AI agent calls WebFetch for each website")
    print("4. Run: python collection_pipeline.py extract")
    print("5. Run: python collection_pipeline.py save")
    print("6. Run: python collection_pipeline.py report")
    print("\nOr use the automated workflow in auto_collector.py")


def cmd_status():
    """显示系统状态"""
    print("\n=== Collection System Status ===")
    
    summary = get_collection_summary()
    
    print(f"\nDatabase:")
    db_stats = summary["database"]
    print(f"  Total leads: {db_stats.get('total', 0)}")
    print(f"  With email: {db_stats.get('with_email', 0)}")
    print(f"  Suppressed: {db_stats.get('suppressed', 0)}")
    print(f"  By status: {db_stats.get('by_status', {})}")
    print(f"  By score: {db_stats.get('by_score', {})}")
    
    print(f"\nSearch History:")
    search_stats = summary["search_history"]
    print(f"  Total searched: {search_stats.get('total_searched', 0)}")
    print(f"  By category: {search_stats.get('by_category', {})}")
    print(f"  By state: {search_stats.get('by_state', {})}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    commands = {
        "select-cities": cmd_select_cities,
        "search": cmd_search,
        "verify": cmd_verify,
        "extract": cmd_extract,
        "score": cmd_score,
        "save": cmd_save,
        "report": cmd_report,
        "full": cmd_full,
        "status": cmd_status,
    }
    
    if cmd in commands:
        if cmd == "select-cities":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            strategy = sys.argv[3] if len(sys.argv) > 3 else "mixed"
            commands[cmd](count, strategy)
        else:
            commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available commands: {', '.join(commands.keys())}")