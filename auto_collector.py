"""
Roktandrazo BD Outreach - Auto Collector
自动采集器：整合城市选择、搜索、验证、提取、评分、入库的完整流程

注意：本模块定义采集流程，实际的WebSearch/WebFetch调用在主流程中完成
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from city_selector import select_cities, get_search_queries, get_search_stats
from search_engine import process_search_results
from website_verifier import verify_website
from contact_extractor import extract_contact_info, prepare_lead_data
from scorer import score_lead
from bd_db import init_db, insert_lead, get_stats


def collect_leads_for_city(city_info: Dict, search_results: List[Dict], website_htmls: Dict[str, str]) -> List[Dict]:
    """
    为指定城市收集线索
    
    Args:
        city_info: 城市信息
        search_results: 搜索结果列表
        website_htmls: 网页HTML内容字典 {url: html}
    
    Returns:
        收集到的线索列表
    """
    city = city_info["city"]
    state = city_info["state"]
    
    # 处理搜索结果
    processed_results = process_search_results(search_results, city, state)
    
    leads = []
    
    for result in processed_results:
        url = result["url"]
        html = website_htmls.get(url)
        
        # 提取联系信息
        contact_info = extract_contact_info(url, html)
        
        if not contact_info.get("success"):
            print(f"  [SKIP] {url}: {contact_info.get('error', 'Failed to extract')}")
            continue
        
        # 准备线索数据
        lead_data = prepare_lead_data(contact_info, city, state, result.get("source_keyword", ""))
        
        if not lead_data:
            print(f"  [SKIP] {url}: Failed to prepare lead data")
            continue
        
        # 评分
        scoring = score_lead(lead_data)
        lead_data["confidence_score"] = scoring["grade"]
        lead_data["scoring_detail"] = scoring
        
        leads.append(lead_data)
        
        print(f"  [OK] {lead_data['store_name']:35s} | {lead_data['email']:35s} | {lead_data['confidence_score']}")
    
    return leads


def save_leads_to_db(leads: List[Dict]) -> Dict:
    """
    保存线索到数据库
    
    Args:
        leads: 线索列表
    
    Returns:
        保存结果统计
    """
    init_db()
    
    stats = {
        "total": len(leads),
        "inserted": 0,
        "skipped": 0,
        "by_score": {"A": 0, "B": 0, "C": 0},
        "by_status": {"new": 0},
    }
    
    for lead in leads:
        lead_id = insert_lead(lead)
        
        if lead_id:
            stats["inserted"] += 1
            score = lead.get("confidence_score", "C")
            stats["by_score"][score] = stats["by_score"].get(score, 0) + 1
        else:
            stats["skipped"] += 1
    
    return stats


def generate_collection_report(leads: List[Dict], stats: Dict, city_info: Dict) -> str:
    """
    生成采集报告
    
    Args:
        leads: 收集到的线索列表
        stats: 保存统计
        city_info: 城市信息
    
    Returns:
        报告内容
    """
    report = []
    report.append(f"# 线索采集报告 - {city_info['city']}, {city_info['state']}")
    report.append(f"采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    report.append("## 统计概览")
    report.append(f"- 总采集: {stats['total']}")
    report.append(f"- 成功入库: {stats['inserted']}")
    report.append(f"- 跳过(重复): {stats['skipped']}")
    report.append(f"- A级: {stats['by_score'].get('A', 0)}")
    report.append(f"- B级: {stats['by_score'].get('B', 0)}")
    report.append(f"- C级: {stats['by_score'].get('C', 0)}")
    report.append("")
    
    report.append("## 线索详情")
    report.append("")
    
    # 按评分分组
    a_leads = [l for l in leads if l.get("confidence_score") == "A"]
    b_leads = [l for l in leads if l.get("confidence_score") == "B"]
    c_leads = [l for l in leads if l.get("confidence_score") == "C"]
    
    if a_leads:
        report.append("### A级线索（可直接进入发信池）")
        for lead in a_leads:
            report.append(f"- **{lead['store_name']}** ({lead['city']}, {lead['state']})")
            report.append(f"  - 邮箱: {lead['email']}")
            report.append(f"  - 类型: {lead['store_type']}")
            report.append(f"  - 产品适配: {lead['product_fit']}")
            report.append(f"  - 理由: {lead['fit_reason']}")
        report.append("")
    
    if b_leads:
        report.append("### B级线索（需要人工审核）")
        for lead in b_leads:
            report.append(f"- **{lead['store_name']}** ({lead['city']}, {lead['state']})")
            report.append(f"  - 邮箱: {lead['email'] or '无'}")
            report.append(f"  - 类型: {lead['store_type']}")
            report.append(f"  - 理由: {lead['fit_reason']}")
        report.append("")
    
    if c_leads:
        report.append("### C级线索（信息不完整）")
        for lead in c_leads:
            report.append(f"- **{lead['store_name']}** ({lead['city']}, {lead['state']})")
            report.append(f"  - 邮箱: {lead['email'] or '无'}")
            report.append(f"  - 理由: {lead['fit_reason']}")
        report.append("")
    
    return "\n".join(report)


def run_collection_cycle(cities: List[Dict], search_results_map: Dict[str, List[Dict]], website_htmls: Dict[str, str]) -> Dict:
    """
    运行一个完整的采集周期
    
    Args:
        cities: 城市列表
        search_results_map: 搜索结果字典 {city_key: results}
        website_htmls: 网页HTML内容字典 {url: html}
    
    Returns:
        采集结果统计
    """
    all_leads = []
    city_reports = []
    
    for city_info in cities:
        city_key = f"{city_info['city']}_{city_info['state']}".lower()
        search_results = search_results_map.get(city_key, [])
        
        print(f"\n=== Collecting {city_info['city']}, {city_info['state']} ===")
        print(f"Search results: {len(search_results)}")
        
        # 收集线索
        leads = collect_leads_for_city(city_info, search_results, website_htmls)
        all_leads.extend(leads)
        
        # 保存到数据库
        stats = save_leads_to_db(leads)
        
        # 生成报告
        report = generate_collection_report(leads, stats, city_info)
        city_reports.append(report)
        
        print(f"Collected: {len(leads)} leads (A: {stats['by_score'].get('A', 0)}, B: {stats['by_score'].get('B', 0)}, C: {stats['by_score'].get('C', 0)})")
    
    # 总体统计
    total_stats = {
        "cities": len(cities),
        "total_leads": len(all_leads),
        "by_score": {"A": 0, "B": 0, "C": 0},
    }
    
    for lead in all_leads:
        score = lead.get("confidence_score", "C")
        total_stats["by_score"][score] = total_stats["by_score"].get(score, 0) + 1
    
    return {
        "stats": total_stats,
        "leads": all_leads,
        "reports": city_reports,
    }


def get_collection_summary() -> Dict:
    """获取采集摘要"""
    init_db()
    db_stats = get_stats()
    search_stats = get_search_stats()
    
    return {
        "database": db_stats,
        "search_history": search_stats,
    }


if __name__ == "__main__":
    # 测试自动采集器
    print("=== Auto Collector Test ===")
    
    # 选择城市
    cities = select_cities(count=2, strategy="mixed")
    print(f"\nSelected cities:")
    for city in cities:
        print(f"  {city['city']}, {city['state']}")
    
    # 生成搜索查询
    for city in cities:
        queries = get_search_queries(city)
        print(f"\nSearch queries for {city['city']}, {city['state']}:")
        for q in queries[:3]:  # 只显示前3个
            print(f"  {q}")
    
    # 获取采集摘要
    summary = get_collection_summary()
    print(f"\nCollection Summary:")
    print(f"  Database: {summary['database']}")
    print(f"  Search History: {summary['search_history']}")