"""
Roktandrazo Outreach - Main Runner
主入口：一键运行完整流水线

用法:
  python main.py scrape     # 只采集新线索 (需传入数据)
  python main.py score      # 重新评分所有线索
  python main.py draft      # 起草邮件 (dry run)
  python main.py send       # 实际发送邮件 (需配置SMTP)
  python main.py dashboard  # 生成仪表盘
  python main.py status     # 查看统计
  python main.py pipeline   # 运行完整流水线
"""

import sys
import json
from datetime import datetime

from db import init_db, get_stats, get_leads, get_leads_ready_for_email, update_lead_status
from scorer import score_lead
from drafter import draft_initial_email
from sender import send_email_to_lead
from dashboard import generate_dashboard

LEGACY_LIVE_DISABLED_COMMANDS = {"send", "send-now", "pipeline-live"}
LEGACY_LIVE_DISABLED_MESSAGE = (
    "LEGACY_LIVE_DISABLED: legacy live command is disabled. "
    "Use bd_sender.py/daily_operator_auto.py controlled workflow only."
)


def fail_closed_legacy_live(command: str) -> int:
    print(f"{LEGACY_LIVE_DISABLED_MESSAGE} command={command}")
    return 2


def cmd_status():
    """查看当前统计"""
    stats = get_stats()
    print("\n" + "📊"*20)
    print("  ROKTANDRAZO OUTREACH - 系统状态")
    print("📊"*20)
    print(f"\n  总线索数：{stats.get('total_leads', 0)}")
    print(f"  有邮箱数：{stats.get('with_email', 0)}")
    print(f"\n  按评分：{json.dumps(stats.get('by_score', {}), ensure_ascii=False)}")
    print(f"  按状态：{json.dumps(stats.get('by_status', {}), ensure_ascii=False)}")
    print(f"  邮件统计：{json.dumps(stats.get('email_stats', {}), ensure_ascii=False)}")
    print(f"\n  门店类型分布：")
    for stype, count in stats.get('by_store_type', {}).items():
        print(f"    {stype}: {count}")
    print(f"\n  州分布：")
    for state, count in stats.get('by_state', {}).items():
        print(f"    {state}: {count}")
    print()


def cmd_score():
    """重新评分"""
    leads = get_leads(limit=1000)
    print(f"\n重新评分 {len(leads)} 条线索...")
    
    graded = {"A": 0, "B": 0, "C": 0}
    for lead in leads:
        scoring = score_lead(lead)
        graded[scoring["grade"]] = graded.get(scoring["grade"], 0) + 1
        print(f"  {lead['store_name']:35s} → {scoring['grade']} ({scoring['total_score']:3d}分) | {'; '.join(scoring['reasons'][:2])}")
    
    print(f"\n评分结果：A={graded.get('A',0)} B={graded.get('B',0)} C={graded.get('C',0)}")


def cmd_draft():
    """起草邮件"""
    leads = get_leads_ready_for_email(limit=50)
    print(f"\n📝 为 {len(leads)} 条合格线索起草邮件...\n")

    drafted = []
    for lead in leads:
        email = draft_initial_email(lead)
        update_lead_status(lead["id"], "drafted")
        drafted.append({
            "store_name": lead["store_name"],
            "email": lead.get("email", ""),
            "subject": email["subject"],
            "score": lead.get("confidence_score", ""),
        })
        print(f"  ✅ {lead['store_name']:35s} | {lead.get('email','(no email)'):35s} | {email['subject']}")

    print(f"\n起草完成：{len(drafted)} 封")
    
    # 保存草稿摘要
    summary_path = "output/drafts_summary.json"
    import os
    os.makedirs("output", exist_ok=True)
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(drafted, f, ensure_ascii=False, indent=2)
    print(f"草稿摘要已保存：{summary_path}")


def cmd_send(dry_run: bool = True, force_send: bool = False):
    """发送邮件"""
    leads = get_leads(status="drafted", limit=50)
    if not leads:
        leads = [l for l in get_leads(status="new", limit=50) if l.get("email")]
    
    banner = '[FORCE SEND] ' if force_send else ''
    print(f"\n{'🚀'}{banner}{'[DRY RUN] ' if dry_run else '[LIVE] '}准备发送 {len(leads)} 封邮件...\n")

    results = {"sent": 0, "failed": 0, "no_email": 0}
    for lead in leads:
        if not lead.get("email"):
            results["no_email"] += 1
            continue

        email_draft = draft_initial_email(lead)
        result = send_email_to_lead(lead, email_draft, dry_run=dry_run, force_send=force_send)
        
        if result["success"]:
            results["sent"] += 1
            print(f"  ✅ {lead['store_name']:35s} | {result['message']}")
        else:
            results["failed"] += 1
            print(f"  ❌ {lead['store_name']:35s} | {result['message']}")

    print(f"\n发送完成：成功 {results['sent']}，失败 {results['failed']}，无邮箱 {results['no_email']}")


def cmd_dashboard():
    """生成仪表盘"""
    path = generate_dashboard()
    print(f"\n✅ 仪表盘已生成：{path}")
    return path


def cmd_pipeline(dry_run: bool = True):
    """运行完整流水线"""
    print("\n" + "🔷"*30)
    print("  ROKTANDRAZO OUTREACH - FULL PIPELINE")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("🔷"*30)

    # 1. 评分
    cmd_score()

    # 2. 起草
    cmd_draft()

    # 3. 发送
    cmd_send(dry_run=dry_run)

    # 4. 仪表盘
    cmd_dashboard()

    # 5. 状态
    cmd_status()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"

    if command in LEGACY_LIVE_DISABLED_COMMANDS:
        sys.exit(fail_closed_legacy_live(command))

    init_db()
    
    commands = {
        "status": lambda: cmd_status(),
        "score": lambda: cmd_score(),
        "draft": lambda: cmd_draft(),
        "send": lambda: cmd_send(dry_run=False),
        "send-dry": lambda: cmd_send(dry_run=True),
        "send-now": lambda: cmd_send(dry_run=False, force_send=True),
        "dashboard": lambda: cmd_dashboard(),
        "pipeline": lambda: cmd_pipeline(dry_run=True),
        "pipeline-live": lambda: cmd_pipeline(dry_run=False),
    }

    if command in commands:
        commands[command]()
    else:
        print(f"未知命令: {command}")
        print(f"可用命令: {', '.join(commands.keys())}")
