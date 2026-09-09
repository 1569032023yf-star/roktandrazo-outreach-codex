"""
Roktandrazo Outreach - Pipeline Orchestrator
主流程编排：线索采集 → 评分 → 起草 → 发送
"""

import json
from datetime import datetime

from db import init_db, insert_lead, get_leads, get_stats, get_leads_ready_for_email, update_lead_status
from scorer import score_lead
from drafter import draft_initial_email, draft_followup_email
from sender import send_email_to_lead, batch_send

LEGACY_LIVE_DISABLED_MESSAGE = (
    "LEGACY_LIVE_DISABLED: legacy live pipeline is disabled. "
    "Use bd_sender.py/daily_operator_auto.py controlled workflow only."
)


def fail_closed_legacy_live(entrypoint: str):
    print(f"{LEGACY_LIVE_DISABLED_MESSAGE} entrypoint={entrypoint}")


def run_scrape_and_store(leads_data: list[dict]) -> dict:
    """
    阶段1：采集并存储线索
    输入：从搜索结果整理的线索列表
    """
    print("\n" + "="*60)
    print("📡 阶段1：线索采集与存储")
    print("="*60)

    results = {"added": 0, "skipped": 0, "total": len(leads_data)}

    for lead in leads_data:
        # 评分
        scoring = score_lead(lead)
        lead["confidence_score"] = scoring["grade"]

        # 存储
        new_id = insert_lead(lead)
        if new_id:
            results["added"] += 1
        else:
            results["skipped"] += 1

    print(f"\n✅ 采集完成：新增 {results['added']}，跳过 {results['skipped']}，共 {results['total']}")
    return results


def run_score_review():
    """
    阶段2：审查并更新评分
    对所有 new 状态的线索重新评分
    """
    print("\n" + "="*60)
    print("🔍 阶段2：评分审查")
    print("="*60)

    leads = get_leads(status="new", limit=500)
    print(f"待审查线索：{len(leads)} 条")

    graded = {"A": 0, "B": 0, "C": 0}
    for lead in leads:
        scoring = score_lead(lead)
        graded[scoring["grade"]] = graded.get(scoring["grade"], 0) + 1
        print(f"  {lead['store_name']:30s} → {scoring['grade']} ({scoring['total_score']}分) | {', '.join(scoring['reasons'][:2])}")

    print(f"\n评分结果：A={graded.get('A',0)} B={graded.get('B',0)} C={graded.get('C',0)}")
    return graded


def run_draft_emails(dry_run: bool = True) -> list[dict]:
    """
    阶段3：为合格线索起草邮件
    """
    print("\n" + "="*60)
    print(f"✉️  阶段3：起草邮件 {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print("="*60)

    leads = get_leads_ready_for_email(limit=50)
    print(f"可发邮件线索：{len(leads)} 条\n")

    drafted = []
    for lead in leads:
        email = draft_initial_email(lead)
        result = send_email_to_lead(lead, email, dry_run=True)  # 总是先 dry run
        
        # 更新线索状态为 drafted
        # Keep pipeline dry runs read-only for Patch 1 verification.
        if not dry_run:
            update_lead_status(lead["id"], "drafted")

        drafted.append({
            "lead_id": lead["id"],
            "store_name": lead["store_name"],
            "email": lead.get("email", ""),
            "subject": email["subject"],
            "score": lead.get("confidence_score", ""),
            "result": result,
        })

        print(f"  📝 {lead['store_name']:30s} | {lead.get('email','(no email)'):30s} | {lead.get('confidence_score','?')}-grade")

    print(f"\n✅ 起草完成：{len(drafted)} 封邮件")
    return drafted


def run_send_emails(dry_run: bool = True) -> list[dict]:
    if not dry_run:
        fail_closed_legacy_live("run_send_emails")
        return []

    """
    阶段4：发送邮件
    """
    print("\n" + "="*60)
    print(f"🚀 阶段4：发送邮件 {'(DRY RUN - 不会实际发送)' if dry_run else '⚠️ LIVE - 将实际发送邮件'}")
    print("="*60)

    # 获取已起草的邮件
    leads = get_leads(status="drafted", limit=50)
    print(f"待发送线索：{len(leads)} 条\n")

    results = []
    for lead in leads:
        email_draft = draft_initial_email(lead)
        result = send_email_to_lead(lead, email_draft, dry_run=dry_run)
        results.append({
            "store_name": lead["store_name"],
            "email": lead.get("email", ""),
            "result": result,
        })
        status_icon = "✅" if result["success"] else "❌"
        print(f"  {status_icon} {lead['store_name']:30s} | {result['message']}")

    sent = sum(1 for r in results if r["result"]["success"])
    failed = len(results) - sent
    print(f"\n{'✅' if dry_run else '📤'} 发送完成：成功 {sent}，失败 {failed}")
    return results


def run_full_pipeline(leads_data: list[dict] = None, dry_run: bool = True):
    if not dry_run:
        fail_closed_legacy_live("run_full_pipeline")
        return {"legacy_live_disabled": True}

    """
    运行完整流水线
    """
    print("\n" + "🔷"*30)
    print("  ROKTANDRAZO OUTREACH PIPELINE")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🔷"*30)

    init_db()

    # 阶段1：采集
    if leads_data:
        run_scrape_and_store(leads_data)

    # 阶段2：评分
    run_score_review()

    # 阶段3：起草
    drafted = run_draft_emails(dry_run=True)

    # 阶段4：发送
    if not dry_run:
        run_send_emails(dry_run=False)
    else:
        print("\n💡 提示：当前为 DRY RUN 模式，邮件不会实际发送")
        print("   配置好 SMTP 后，调用 run_full_pipeline(dry_run=False) 即可实际发送")

    # 统计
    stats = get_stats()
    print("\n" + "="*60)
    print("📊 当前数据库统计")
    print("="*60)
    print(f"  总线索数：{stats.get('total_leads', 0)}")
    print(f"  有邮箱数：{stats.get('with_email', 0)}")
    print(f"  按评分：{stats.get('by_score', {})}")
    print(f"  按状态：{stats.get('by_status', {})}")
    print()

    return stats


if __name__ == "__main__":
    # 初始化数据库
    init_db()
    
    # 导入 Week 1 数据
    from db import get_db
    import csv
    
    csv_path = "../roktandrazo-leads/week1_leads.csv"
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            leads = list(reader)
        
        print(f"从 CSV 读取 {len(leads)} 条线索")
        run_full_pipeline(leads_data=leads, dry_run=True)
    except FileNotFoundError:
        print(f"CSV 文件未找到: {csv_path}")
        print("运行空流水线...")
        run_full_pipeline(dry_run=True)
